import argparse
import ast
import os
import re
from collections import Counter, defaultdict
from typing import List

import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

VERSION = 'v3.0'
NODE_TYPE_DIRECTORY = 'directory'
NODE_TYPE_FILE = 'file'
NODE_TYPE_CLASS = 'class'
NODE_TYPE_FUNCTION = 'function'
EDGE_TYPE_CONTAINS = 'contains'
EDGE_TYPE_INHERITS = 'inherits'
EDGE_TYPE_INVOKES = 'invokes'
EDGE_TYPE_IMPORTS = 'imports'
EDGE_TYPE_EXCEPTION_BOUNDARY = 'exception_boundary'
EDGE_TYPE_VALUE_TRANSFORM = 'value_transform'

VALID_NODE_TYPES = [NODE_TYPE_DIRECTORY, NODE_TYPE_FILE, NODE_TYPE_CLASS, NODE_TYPE_FUNCTION]
VALID_EDGE_TYPES = [EDGE_TYPE_CONTAINS, EDGE_TYPE_INHERITS, EDGE_TYPE_INVOKES, EDGE_TYPE_IMPORTS,
                    EDGE_TYPE_EXCEPTION_BOUNDARY, EDGE_TYPE_VALUE_TRANSFORM]

SKIP_DIRS = ['.github', '.git']
def is_skip_dir(dirname):
    for skip_dir in SKIP_DIRS:
        if skip_dir in dirname:
            return True
    return False


def handle_edge_cases(code):
    # hard-coded edge cases
    code = code.replace('\ufeff', '')
    code = code.replace('constants.False', '_False')
    code = code.replace('constants.True', '_True')
    code = code.replace("False", "_False")
    code = code.replace("True", "_True")
    code = code.replace("DOMAIN\\username", "DOMAIN\\\\username")
    code = code.replace("Error, ", "Error as ")
    code = code.replace('Exception, ', 'Exception as ')
    code = code.replace("print ", "yield ")
    pattern = r'except\s+\(([^,]+)\s+as\s+([^)]+)\):'
    # Replace 'as' with ','
    code = re.sub(pattern, r'except (\1, \2):', code)
    code = code.replace("raise AttributeError as aname", "raise AttributeError")
    return code


def find_imports(filepath, repo_path, tree=None):
    if tree is None:
        try:
            with open(filepath, 'r') as file:
                tree = ast.parse(file.read(), filename=filepath)
        except:
            raise SyntaxError
        # include all imports for file
        candidates = ast.walk(tree)
    else:
        # only include top level import for classes/functions
        candidates = ast.iter_child_nodes(tree)

    imports = []
    for node in candidates:
        if isinstance(node, ast.Import):
            # Handle 'import module' and 'import module as alias'
            for alias in node.names:
                module_name = alias.name
                asname = alias.asname
                imports.append({
                    "type": "import",
                    "module": module_name,
                    "alias": asname
                })
        elif isinstance(node, ast.ImportFrom):
            # Handle 'from ... import ...' statements
            import_entities = []
            for alias in node.names:
                if alias.name == '*':
                    import_entities = [{'name': '*', 'alias': None}]
                    break
                else:
                    entity_name = alias.name
                    asname = alias.asname
                    import_entities.append({
                        "name": entity_name,
                        "alias": asname
                    })

            # Calculate the module name for relative imports
            if node.level == 0:
                # Absolute import
                module_name = node.module
            else:
                # Relative import
                rel_path = os.path.relpath(filepath, repo_path)
                # rel_dir = os.path.dirname(rel_path)
                package_parts = rel_path.split(os.sep)

                # Adjust for the level of relative import
                if len(package_parts) >= node.level:
                    package_parts = package_parts[:-node.level]
                else:
                    package_parts = []

                if node.module:
                    module_name = '.'.join(package_parts + [node.module])
                else:
                    module_name = '.'.join(package_parts)

            imports.append({
                "type": "from",
                "module": module_name,
                "entities": import_entities
            })
    return imports


class CodeAnalyzer(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.nodes = []
        self.node_name_stack = []
        self.node_type_stack = []

    def visit_ClassDef(self, node):
        class_name = node.name
        full_class_name = '.'.join(self.node_name_stack + [class_name])
        self.nodes.append({
            'name': full_class_name,
            'type': NODE_TYPE_CLASS,
            'code': self._get_source_segment(node),
            'start_line': node.lineno,
            'end_line': node.end_lineno,
        })

        self.node_name_stack.append(class_name)
        self.node_type_stack.append(NODE_TYPE_CLASS)
        self.generic_visit(node)
        self.node_name_stack.pop()
        self.node_type_stack.pop()

    def visit_FunctionDef(self, node):
        if self.node_type_stack and self.node_type_stack[-1] == NODE_TYPE_CLASS and node.name == '__init__':
            return
        self._visit_func(node)

    def visit_AsyncFunctionDef(self, node):
        self._visit_func(node)

    def _visit_func(self, node):
        function_name = node.name
        full_function_name = '.'.join(self.node_name_stack + [function_name])
        all_args = node.args
        params = (
            [arg.arg for arg in all_args.posonlyargs]
            + [arg.arg for arg in all_args.args]
            + [arg.arg for arg in all_args.kwonlyargs]
        )
        params = [p for p in params if p not in ('self', 'cls')]
        self.nodes.append({
            'name': full_function_name,
            'parent_type': self.node_type_stack[-1] if self.node_type_stack else None,
            'type': NODE_TYPE_FUNCTION,
            'code': self._get_source_segment(node),
            'start_line': node.lineno,
            'end_line': node.end_lineno,
            'params': params,
        })

        self.node_name_stack.append(function_name)
        self.node_type_stack.append(NODE_TYPE_FUNCTION)
        self.generic_visit(node)
        self.node_name_stack.pop()
        self.node_type_stack.pop()

    def _get_source_segment(self, node):
        with open(self.filename, 'r') as file:
            source_code = file.read()
        return ast.get_source_segment(source_code, node)


# Parese the given file, use CodeAnalyzer to extract classes and helper functions from the file
def analyze_file(filepath):
    with open(filepath, 'r') as file:
        code = file.read()
        # code = handle_edge_cases(code)
        try:
            tree = ast.parse(code, filename=filepath)
        except:
            raise SyntaxError
    analyzer = CodeAnalyzer(filepath)
    try:
        analyzer.visit(tree)
    except RecursionError:
        pass
    return analyzer.nodes


def resolve_module(module_name, repo_path):
    """
    Resolve a module name to a file path in the repo.
    Returns the file path if found, or None if not found.
    """
    # Try to resolve as a .py file
    module_path = os.path.join(repo_path, module_name.replace('.', '/') + '.py')
    if os.path.isfile(module_path):
        return module_path

    # Try to resolve as a package (__init__.py)
    init_path = os.path.join(repo_path, module_name.replace('.', '/'), '__init__.py')
    if os.path.isfile(init_path):
        return init_path

    return None


def add_imports(root_node, imports, graph, repo_path):
    for imp in imports:
        if imp['type'] == 'import':
            # Handle 'import module' statements
            module_name = imp['module']
            module_path = resolve_module(module_name, repo_path)
            if module_path:
                imp_filename = os.path.relpath(module_path, repo_path)
                if graph.has_node(imp_filename):
                    graph.add_edge(root_node, imp_filename, type=EDGE_TYPE_IMPORTS, alias=imp['alias'])
        elif imp['type'] == 'from':
            # Handle 'from module import entity' statements
            module_name = imp['module']
            entities = imp['entities']

            if len(entities) == 1 and entities[0]['name'] == '*':
                # Handle 'from module import *' as 'import module' statement
                module_path = resolve_module(module_name, repo_path)
                if module_path:
                    imp_filename = os.path.relpath(module_path, repo_path)
                    if graph.has_node(imp_filename):
                        graph.add_edge(root_node, imp_filename, type=EDGE_TYPE_IMPORTS, alias=None)
                continue  # Skip further processing for 'import *'

            for entity in entities:
                entity_name, entity_alias = entity['name'], entity['alias']
                entity_module_name = f"{module_name}.{entity_name}"
                entity_module_path = resolve_module(entity_module_name, repo_path)
                if entity_module_path:
                    # Entity is a submodule
                    entity_filename = os.path.relpath(entity_module_path, repo_path)
                    if graph.has_node(entity_filename):
                        graph.add_edge(root_node, entity_filename, type=EDGE_TYPE_IMPORTS, alias=entity_alias)
                else:
                    # Entity might be an attribute inside the module
                    module_path = resolve_module(module_name, repo_path)
                    if module_path:
                        imp_filename = os.path.relpath(module_path, repo_path)
                        node = f"{imp_filename}:{entity_name}"
                        if graph.has_node(node):
                            graph.add_edge(root_node, node, type=EDGE_TYPE_IMPORTS, alias=entity_alias)
                        elif graph.has_node(imp_filename):
                            graph.add_edge(root_node, imp_filename, type=EDGE_TYPE_IMPORTS, alias=entity_alias)


def resolve_symlink(file_path):
    """
    Resolve the absolute path of a symbolic link.
    
    Args:
        file_path (str): The symbolic link file path.
    
    Returns:
        str: The absolute path of the target file if the file is a symbolic link.
        None: If the file is not a symbolic link.
    """
    if os.path.islink(file_path):
        # Get the relative path to the target file
        relative_target = os.readlink(file_path)
        # Get the directory of the symbolic link
        symlink_dir = os.path.dirname(os.path.dirname(file_path))
        # Combine the symlink directory with the relative target path
        absolute_target = os.path.abspath(os.path.join(symlink_dir, relative_target))
        if not os.path.exists(absolute_target):
            print(f"The target file does not exist: {absolute_target}")
            return None
        return absolute_target
    else:
        print(f"{file_path} is not a symbolic link.")
        return None


# Traverse all the Python files under repo_path, construct dependency graphs
# with node types: directory, file, class, function
def build_graph(repo_path, fuzzy_search=True, global_import=False, use_dataflow=False):
    graph = nx.MultiDiGraph()
    file_nodes = {}

    ## add nodes
    graph.add_node('/', type=NODE_TYPE_DIRECTORY)
    dir_stack: List[str] = []
    dir_include_stack: List[bool] = []
    for root, _, files in os.walk(repo_path):

        # add directory nodes and edges
        dirname = os.path.relpath(root, repo_path)
        if dirname == '.':
            dirname = '/'
        elif is_skip_dir(dirname):
            continue
        else:
            graph.add_node(dirname, type=NODE_TYPE_DIRECTORY)
            parent_dirname  = os.path.dirname(dirname)
            if parent_dirname == '':
                parent_dirname = '/'
            graph.add_edge(parent_dirname, dirname, type=EDGE_TYPE_CONTAINS)

        # in reverse step, remove directories that do not contain .py file
        while len(dir_stack) > 0 and not dirname.startswith(dir_stack[-1]):
            if not dir_include_stack[-1]:
                # print('remove', dir_stack[-1])
                graph.remove_node(dir_stack[-1])
            dir_stack.pop()
            dir_include_stack.pop()
        if dirname != '/':
            dir_stack.append(dirname)
            dir_include_stack.append(False)

        dir_has_py = False
        for file in files:
            if file.endswith('.py'):
                dir_has_py = True

                # add file nodes
                try:
                    file_path = os.path.join(root, file)
                    filename = os.path.relpath(file_path, repo_path)
                    if os.path.islink(file_path):
                        continue
                    else:
                        with open(file_path, 'r') as f:
                            file_content = f.read()

                    graph.add_node(filename, type=NODE_TYPE_FILE, code=file_content)
                    file_nodes[filename] = file_path

                    nodes = analyze_file(file_path)
                except (UnicodeDecodeError, SyntaxError):
                    # Skip the file that cannot decode or parse
                    continue

                # add function/class nodes
                for node in nodes:
                    full_name = f'{filename}:{node["name"]}'
                    graph.add_node(full_name, type=node['type'], code=node['code'],
                                   start_line=node['start_line'], end_line=node['end_line'],
                                   params=node.get('params', []))

                # add edges with type=contains
                graph.add_edge(dirname, filename, type=EDGE_TYPE_CONTAINS)
                for node in nodes:
                    full_name = f'{filename}:{node["name"]}'
                    name_list = node['name'].split('.')
                    if len(name_list) == 1:
                        graph.add_edge(filename, full_name, type=EDGE_TYPE_CONTAINS)
                    else:
                        parent_name = '.'.join(name_list[:-1])
                        full_parent_name = f'{filename}:{parent_name}'
                        graph.add_edge(full_parent_name, full_name, type=EDGE_TYPE_CONTAINS)

        # keep all parent directories
        if dir_has_py:
            for i in range(len(dir_include_stack)):
                dir_include_stack[i] = True

    # check last traversed directory
    while len(dir_stack) > 0:
        if not dir_include_stack[-1]:
            graph.remove_node(dir_stack[-1])
        dir_stack.pop()
        dir_include_stack.pop()

    ## add imports edges (file -> class/function)
    for filename, filepath in file_nodes.items():
        try:
            imports = find_imports(filepath, repo_path)
        except SyntaxError:
            continue
        add_imports(filename, imports, graph, repo_path)

    global_name_dict = defaultdict(list)
    if global_import:
        for node in graph.nodes():
            node_name = node.split(':')[-1].split('.')[-1]
            global_name_dict[node_name].append(node)

    ## add edges start from class/function
    for node, attributes in graph.nodes(data=True):
        if attributes.get('type') not in [NODE_TYPE_CLASS, NODE_TYPE_FUNCTION]:
            continue

        caller_code_tree = ast.parse(graph.nodes[node]['code'])

        # construct possible callee dict (name -> node) based on graph connectivity
        callee_nodes, callee_alias = find_all_possible_callee(node, graph)
        if fuzzy_search:
            # for nodes with the same suffix, keep every nodes
            callee_name_dict = defaultdict(list)
            for callee_node in set(callee_nodes):
                callee_name = callee_node.split(':')[-1].split('.')[-1]
                callee_name_dict[callee_name].append(callee_node)
            for alias, callee_node in callee_alias.items():
                callee_name_dict[alias].append(callee_node)
        else:
            # for nodes with the same suffix, only keep the nearest node
            callee_name_dict = {
                callee_node.split(':')[-1].split('.')[-1]: callee_node
                for callee_node in callee_nodes[::-1]
            }
            callee_name_dict.update(callee_alias)

        # analysis invokes and inherits, add (top-level) imports edges (class/function -> class/function)
        if attributes.get('type') == NODE_TYPE_CLASS:
            invocations, inheritances = analyze_init(node, caller_code_tree, graph, repo_path)
        else:
            invocations = analyze_invokes(node, caller_code_tree, graph, repo_path)
            inheritances = []

        # add invokes edges (class/function -> class/function)
        for callee_name in set(invocations):
            callee_node = callee_name_dict.get(callee_name)
            if callee_node:
                if isinstance(callee_node, list):
                    for callee in callee_node:
                        graph.add_edge(node, callee, type=EDGE_TYPE_INVOKES)
                else:
                    graph.add_edge(node, callee_node, type=EDGE_TYPE_INVOKES)
            elif global_import:
                # search from global name dict
                global_fuzzy_nodes = global_name_dict.get(callee_name)
                if global_fuzzy_nodes:
                    for global_fuzzy_node in global_fuzzy_nodes:
                        graph.add_edge(node, global_fuzzy_node, type=EDGE_TYPE_INVOKES)

        # add inherits edges (class -> class)
        for callee_name in set(inheritances):
            callee_node = callee_name_dict.get(callee_name)
            if callee_node:
                if isinstance(callee_node, list):
                    for callee in callee_node:
                        graph.add_edge(node, callee, type=EDGE_TYPE_INHERITS)
                else:
                    graph.add_edge(node, callee_node, type=EDGE_TYPE_INHERITS)
            elif global_import:
                # search from global name dict
                global_fuzzy_nodes = global_name_dict.get(callee_name)
                if global_fuzzy_nodes:
                    for global_fuzzy_node in global_fuzzy_nodes:
                        graph.add_edge(node, global_fuzzy_node, type=EDGE_TYPE_INHERITS)

    if use_dataflow:
        add_hybrid_memory_edges(graph)

    return graph


# ---------------------------------------------------------------------------
# vLLM description helper
# ---------------------------------------------------------------------------

def vllm_generate_description(prompt: str):
    """Try to call a vLLM server for a short description. Returns None on failure."""
    import os
    base_url = os.environ.get('VLLM_BASE_URL', 'http://localhost:8000/v1')
    model = os.environ.get('VLLM_MODEL', '')
    try:
        import openai
        client = openai.OpenAI(base_url=base_url, api_key='dummy', timeout=5.0)
        if not model:
            models = client.models.list()
            if models.data:
                model = models.data[0].id
        if not model:
            return None
        resp = client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=80,
            temperature=0.0,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Exception boundary analysis
# ---------------------------------------------------------------------------

def _extract_exc_type(exc_node) -> str:
    """Return the exception class name from an AST raise/except node, or ''."""
    if exc_node is None:
        return ''
    if isinstance(exc_node, ast.Name):
        return exc_node.id
    if isinstance(exc_node, ast.Call):
        return _extract_exc_type(exc_node.func)
    if isinstance(exc_node, ast.Attribute):
        return exc_node.attr
    return ''


def _collect_exception_sites(func_ast_node):
    """Walk a function AST and return (raise_sites, catch_sites).
    Skips inner function/class definitions."""
    raise_sites = []
    catch_sites = []

    def _walk(node, in_try: bool):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(child, ast.Raise):
                exc_type = _extract_exc_type(child.exc)
                if exc_type:
                    raise_sites.append({'exc_type': exc_type, 'line': child.lineno,
                                        'unhandled': not in_try})
                _walk(child, in_try)
            elif isinstance(child, ast.Try):
                for stmt in child.body:
                    _walk(stmt, in_try=False)
                for handler in child.handlers:
                    catches = []
                    if handler.type is None:
                        catches = ['Exception']
                    elif isinstance(handler.type, ast.Tuple):
                        catches = [_extract_exc_type(e) for e in handler.type.elts]
                    else:
                        catches = [_extract_exc_type(handler.type)]
                    catches = [c for c in catches if c]
                    if catches:
                        catch_sites.append({'catches': catches, 'line': handler.lineno})
                    for stmt in handler.body:
                        _walk(stmt, in_try=True)
                for stmt in (child.finalbody if hasattr(child, 'finalbody') else []):
                    _walk(stmt, in_try)
            else:
                _walk(child, in_try)

    _walk(func_ast_node, in_try=False)
    return raise_sites, catch_sites


def _get_func_exception_sites(node_id: str, code: str):
    """Return raise_sites and catch_sites for the named function in code."""
    try:
        tree = ast.parse(code)
    except Exception:
        return [], []
    func_name = node_id.split(':')[-1].split('.')[-1]
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func_name:
            return _collect_exception_sites(n)
        if isinstance(n, ast.ClassDef) and n.name == func_name:
            for item in n.body:
                if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                    return _collect_exception_sites(item)
            return [], []
    return [], []


def build_exception_boundary_edges(graph):
    """Add EXCEPTION_BOUNDARY edges between raise and catch sites."""
    # Collect raise/catch info per node
    raise_map = defaultdict(list)   # exc_type -> [{node_id, line, unhandled}]
    catch_map = defaultdict(list)   # exc_type -> [{node_id, line, catches}]

    for node, attrs in graph.nodes(data=True):
        if attrs.get('type') not in [NODE_TYPE_FUNCTION, NODE_TYPE_CLASS]:
            continue
        code = attrs.get('code', '')
        if not code:
            continue
        raise_sites, catch_sites = _get_func_exception_sites(node, code)
        for rs in raise_sites:
            raise_map[rs['exc_type']].append({'node_id': node,
                                               'line': rs['line'],
                                               'unhandled': rs['unhandled']})
        for cs in catch_sites:
            for exc in cs['catches']:
                catch_map[exc].append({'node_id': node,
                                       'catches': cs['catches'],
                                       'line': cs['line']})

    # Create edges: every raise_site -> every catch_site of the same exc_type
    for exc_type, raisers in raise_map.items():
        catchers = catch_map.get(exc_type, []) + catch_map.get('Exception', [])
        for rs in raisers:
            for cs in catchers:
                raise_node = rs['node_id']
                catch_node = cs['node_id']
                raise_file = raise_node.split(':')[0]
                catch_file = catch_node.split(':')[0]
                crosses = raise_file != catch_file

                desc_prompt = (
                    f"Describe in one sentence: exception '{exc_type}' raised in "
                    f"'{raise_node}' and caught in '{catch_node}'."
                )
                desc = vllm_generate_description(desc_prompt)

                edge_attrs = {
                    'type': EDGE_TYPE_EXCEPTION_BOUNDARY,
                    'raise_site': {'node_id': raise_node, 'exc_type': exc_type,
                                   'line': rs['line']},
                    'catch_site': {'node_id': catch_node, 'catches': cs['catches'],
                                   'line': cs['line']},
                    'unhandled': rs['unhandled'],
                    'crosses_file': crosses,
                }
                if desc is not None:
                    edge_attrs['description'] = desc
                graph.add_edge(raise_node, catch_node, **edge_attrs)


# ---------------------------------------------------------------------------
# Value transform analysis
# ---------------------------------------------------------------------------

_VALUE_TRANSFORM_FUNCS = {
    'int': 'int', 'str': 'str', 'float': 'float', 'list': 'list',
    'dict': 'dict', 'bool': 'bool', 'tuple': 'tuple', 'bytes': 'bytes',
    'set': 'set', 'frozenset': 'frozenset',
}

_JSON_TRANSFORMS = {
    ('json', 'loads'): ('str', 'dict/list'),
    ('json', 'dumps'): ('dict/list', 'str'),
    ('json', 'load'): ('file', 'dict/list'),
    ('json', 'dump'): ('dict/list', 'file'),
}


def _check_transform_call(call_node):
    """If call_node is a known type-conversion, return (dst_type, label). Else (None, None)."""
    if isinstance(call_node.func, ast.Name):
        fn = call_node.func.id
        if fn in _VALUE_TRANSFORM_FUNCS:
            return _VALUE_TRANSFORM_FUNCS[fn], fn
    elif isinstance(call_node.func, ast.Attribute):
        if isinstance(call_node.func.value, ast.Name):
            key = (call_node.func.value.id, call_node.func.attr)
            if key in _JSON_TRANSFORMS:
                _, dst_t = _JSON_TRANSFORMS[key]
                return dst_t, f'{key[0]}.{key[1]}'
    return None, None


def _collect_value_transforms(func_ast_node, node_id: str):
    """Return list of transform dicts from a function body."""
    transforms = []

    def _walk(n):
        for child in ast.iter_child_nodes(n):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(child, ast.Assign) and isinstance(child.value, ast.Call):
                dst_type, label = _check_transform_call(child.value)
                if dst_type and child.value.args:
                    try:
                        src_expr = ast.unparse(child.value.args[0])
                        dst_expr = ast.unparse(child.targets[0]) if child.targets else '<unknown>'
                    except Exception:
                        src_expr = dst_expr = '<unknown>'
                    transforms.append({
                        'node_id': node_id, 'src_expr': src_expr,
                        'src_type': 'unknown', 'dst_expr': dst_expr,
                        'dst_type': dst_type, 'line': child.lineno,
                        'transform_func': label,
                    })
            elif isinstance(child, ast.AnnAssign) and child.value and isinstance(child.value, ast.Call):
                dst_type, label = _check_transform_call(child.value)
                if dst_type and child.value.args:
                    try:
                        src_expr = ast.unparse(child.value.args[0])
                        dst_expr = ast.unparse(child.target)
                    except Exception:
                        src_expr = dst_expr = '<unknown>'
                    transforms.append({
                        'node_id': node_id, 'src_expr': src_expr,
                        'src_type': 'unknown', 'dst_expr': dst_expr,
                        'dst_type': dst_type, 'line': child.lineno,
                        'transform_func': label,
                    })
            _walk(child)

    _walk(func_ast_node)
    return transforms


def build_value_transform_edges(graph):
    """Add VALUE_TRANSFORM self-loop edges for type conversions within functions."""
    for node, attrs in graph.nodes(data=True):
        if attrs.get('type') not in [NODE_TYPE_FUNCTION, NODE_TYPE_CLASS]:
            continue
        code = attrs.get('code', '')
        if not code:
            continue
        try:
            tree = ast.parse(code)
        except Exception:
            continue
        func_name = node.split(':')[-1].split('.')[-1]
        target_func = None
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func_name:
                target_func = n
                break
            if isinstance(n, ast.ClassDef) and n.name == func_name:
                for item in n.body:
                    if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                        target_func = item
                        break
                break
        if target_func is None:
            continue
        transforms = _collect_value_transforms(target_func, node)
        for t in transforms:
            desc_prompt = (
                f"Describe in one sentence: value transform '{t['transform_func']}' "
                f"converting '{t['src_expr']}' to '{t['dst_type']}' at line {t['line']} "
                f"in '{node}'."
            )
            desc = vllm_generate_description(desc_prompt)
            edge_attrs = {
                'type': EDGE_TYPE_VALUE_TRANSFORM,
                'src': {'node_id': node, 'expr': t['src_expr'],
                        'value_type': t['src_type'], 'line': t['line']},
                'dst': {'node_id': node, 'expr': t['dst_expr'],
                        'value_type': t['dst_type'], 'line': t['line']},
            }
            if desc is not None:
                edge_attrs['description'] = desc
            graph.add_edge(node, node, **edge_attrs)


# ---------------------------------------------------------------------------
# Inherit edge meta enrichment
# ---------------------------------------------------------------------------

def _get_init_attrs(class_ast_node):
    """Return list of self.xxx attributes set in __init__."""
    attrs = []
    for item in class_ast_node.body:
        if isinstance(item, ast.FunctionDef) and item.name == '__init__':
            for n in ast.walk(item):
                if isinstance(n, ast.Assign):
                    for tgt in n.targets:
                        if (isinstance(tgt, ast.Attribute)
                                and isinstance(tgt.value, ast.Name)
                                and tgt.value.id == 'self'):
                            attrs.append(tgt.attr)
                elif isinstance(n, ast.AnnAssign):
                    if (isinstance(n.target, ast.Attribute)
                            and isinstance(n.target.value, ast.Name)
                            and n.target.value.id == 'self'):
                        attrs.append(n.target.attr)
    return attrs


def _has_init(class_ast_node) -> bool:
    return any(isinstance(i, ast.FunctionDef) and i.name == '__init__'
               for i in class_ast_node.body)


def _calls_super_init(class_ast_node) -> bool:
    for item in class_ast_node.body:
        if isinstance(item, ast.FunctionDef) and item.name == '__init__':
            for n in ast.walk(item):
                if (isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)
                        and n.func.attr == '__init__'
                        and isinstance(n.func.value, ast.Call)
                        and isinstance(n.func.value.func, ast.Name)
                        and n.func.value.func.id == 'super'):
                    return True
    return False


def _parse_class_ast(code: str, class_name: str):
    try:
        tree = ast.parse(code)
    except Exception:
        return None
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == class_name:
            return n
    return None


def enrich_inherit_edges(graph):
    """Add meta attributes to existing 'inherits' edges."""
    for u, v, key, data in list(graph.edges(keys=True, data=True)):
        if data.get('type') != EDGE_TYPE_INHERITS:
            continue
        child_name = u.split(':')[-1].split('.')[-1]
        parent_name = v.split(':')[-1].split('.')[-1]
        child_code = graph.nodes[u].get('code', '')
        parent_code = graph.nodes[v].get('code', '')

        child_ast = _parse_class_ast(child_code, child_name)
        parent_ast = _parse_class_ast(parent_code, parent_name)

        child_has_init = _has_init(child_ast) if child_ast else False
        child_calls_super = _calls_super_init(child_ast) if child_ast else False
        child_init_sets = _get_init_attrs(child_ast) if child_ast else []
        parent_init_sets = _get_init_attrs(parent_ast) if parent_ast else []
        missing_attrs = [a for a in parent_init_sets if a not in child_init_sets]

        desc_prompt = (
            f"Describe in one sentence: inheritance where '{u}' extends '{v}'. "
            f"child_has_init={child_has_init}, missing_attrs={missing_attrs}."
        )
        desc = vllm_generate_description(desc_prompt)

        meta = {
            'child_has_init': child_has_init,
            'child_calls_super_init': child_calls_super,
            'parent_init_sets': parent_init_sets,
            'child_init_sets': child_init_sets,
            'missing_attrs': missing_attrs,
        }
        graph[u][v][key]['meta'] = meta
        if desc is not None:
            graph[u][v][key]['description'] = desc


# ---------------------------------------------------------------------------
# Invoke edge meta enrichment
# ---------------------------------------------------------------------------

def _check_return_nullable(callee_code: str, callee_name: str):
    """Return (nullable: bool, reason: str)."""
    try:
        tree = ast.parse(callee_code)
    except Exception:
        return False, ''
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == callee_name:
            for stmt in ast.walk(n):
                if isinstance(stmt, ast.Return):
                    if stmt.value is None:
                        return True, 'bare return'
                    if isinstance(stmt.value, ast.Constant) and stmt.value.value is None:
                        return True, 'return None'
            break
    return False, ''


def _find_return_binding_and_use(caller_code: str, caller_name: str, callee_simple_name: str):
    """Find where caller binds the callee return value and how it's first used."""
    result = {
        'return_bound_to': '',
        'guard_before_use': False,
        'first_use_expr': '',
        'first_use_line': -1,
        'use_type': '',
    }
    try:
        tree = ast.parse(caller_code)
    except Exception:
        return result

    func_name = caller_name.split('.')[-1]
    target_func = None
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func_name:
            target_func = n
            break
    if target_func is None:
        return result

    bound_var = ''
    for stmt in ast.walk(target_func):
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            call_name = ''
            if isinstance(call.func, ast.Name):
                call_name = call.func.id
            elif isinstance(call.func, ast.Attribute):
                call_name = call.func.attr
            if call_name == callee_simple_name and stmt.targets:
                try:
                    bound_var = ast.unparse(stmt.targets[0])
                except Exception:
                    bound_var = ''
                result['return_bound_to'] = bound_var
                break

    if not bound_var:
        return result

    stmts = list(ast.walk(target_func))
    for stmt in stmts:
        for n in ast.walk(stmt):
            if isinstance(n, ast.Name) and n.id == bound_var and hasattr(n, 'lineno'):
                if isinstance(stmt, (ast.If,)):
                    test_src = ''
                    try:
                        test_src = ast.unparse(stmt.test)
                    except Exception:
                        pass
                    if bound_var in test_src:
                        result['guard_before_use'] = True
                        continue
                if isinstance(n, ast.Name):
                    parent = stmt
                    for p in ast.walk(target_func):
                        for child in ast.iter_child_nodes(p):
                            if child is n:
                                parent = p
                                break
                    use_type = ''
                    expr = ''
                    try:
                        expr = ast.unparse(parent)
                    except Exception:
                        pass
                    if isinstance(parent, ast.Subscript):
                        use_type = 'subscript'
                    elif isinstance(parent, ast.Attribute):
                        use_type = 'attribute'
                    elif isinstance(parent, ast.Call):
                        use_type = 'call'
                    else:
                        use_type = type(parent).__name__.lower()
                    if use_type:
                        result['first_use_expr'] = expr
                        result['first_use_line'] = getattr(n, 'lineno', -1)
                        result['use_type'] = use_type
                        break
    return result


def enrich_invoke_edges(graph):
    """Add meta attributes to existing 'invokes' edges."""
    for u, v, key, data in list(graph.edges(keys=True, data=True)):
        if data.get('type') != EDGE_TYPE_INVOKES:
            continue
        caller_code = graph.nodes[u].get('code', '')
        callee_code = graph.nodes[v].get('code', '')
        caller_name = u.split(':')[-1]
        callee_simple = v.split(':')[-1].split('.')[-1]

        nullable, nullable_reason = _check_return_nullable(callee_code, callee_simple)
        use_info = _find_return_binding_and_use(caller_code, caller_name, callee_simple)

        desc_prompt = (
            f"Describe in one sentence: function call from '{u}' to '{v}'. "
            f"return_nullable={nullable}, guard={use_info['guard_before_use']}."
        )
        desc = vllm_generate_description(desc_prompt)

        meta = {
            'return_nullable': nullable,
            'nullable_reason': nullable_reason,
            'return_bound_to': use_info['return_bound_to'],
            'guard_before_use': use_info['guard_before_use'],
            'first_use_expr': use_info['first_use_expr'],
            'first_use_line': use_info['first_use_line'],
            'use_type': use_info['use_type'],
        }
        graph[u][v][key]['meta'] = meta
        if desc is not None:
            graph[u][v][key]['description'] = desc


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def add_hybrid_memory_edges(graph):
    """Add exception_boundary, value_transform edges and enrich inherit/invoke edges."""
    build_exception_boundary_edges(graph)
    build_value_transform_edges(graph)
    enrich_inherit_edges(graph)
    enrich_invoke_edges(graph)


def get_inner_nodes(query_node, src_node, graph):
    inner_nodes = []
    for _, dst_node, attr in graph.edges(src_node, data=True):
        if attr['type'] == EDGE_TYPE_CONTAINS and dst_node != query_node:
            inner_nodes.append(dst_node)
            if graph.nodes[dst_node]['type'] == NODE_TYPE_CLASS:  # only include class's inner nodes
                inner_nodes.extend(get_inner_nodes(query_node, dst_node, graph))
    return inner_nodes


def find_all_possible_callee(node, graph):
    callee_nodes, callee_alias = [], {}
    cur_node = node
    pre_node = node

    def find_parent(_cur_node):
        for predecessor in graph.predecessors(_cur_node):
            for key, attr in graph.get_edge_data(predecessor, _cur_node).items():
                if attr['type'] == EDGE_TYPE_CONTAINS:
                    return predecessor

    while True:
        callee_nodes.extend(get_inner_nodes(pre_node, cur_node, graph))

        if graph.nodes[cur_node]['type'] == NODE_TYPE_FILE:

            # check recursive imported files
            file_list = []
            file_stack = [cur_node]
            while len(file_stack) > 0:
                for _, dst_node, attr in graph.edges(file_stack.pop(), data=True):
                    if attr['type'] == EDGE_TYPE_IMPORTS and dst_node not in file_list + [cur_node]:
                        if graph.nodes[dst_node]['type'] == NODE_TYPE_FILE and dst_node.endswith('__init__.py'):
                            file_list.append(dst_node)
                            file_stack.append(dst_node)

            for file in file_list:
                callee_nodes.extend(get_inner_nodes(cur_node, file, graph))
                for _, dst_node, attr in graph.edges(file, data=True):
                    if attr['type'] == EDGE_TYPE_IMPORTS:
                        if attr['alias'] is not None:
                            callee_alias[attr['alias']] = dst_node
                        if graph.nodes[dst_node]['type'] in [NODE_TYPE_FILE, NODE_TYPE_CLASS]:
                            callee_nodes.extend(get_inner_nodes(file, dst_node, graph))
                        if graph.nodes[dst_node]['type'] in [NODE_TYPE_FUNCTION, NODE_TYPE_CLASS]:
                            callee_nodes.append(dst_node)

            # check imported functions and classes
            for _, dst_node, attr in graph.edges(cur_node, data=True):
                if attr['type'] == EDGE_TYPE_IMPORTS:
                    if attr['alias'] is not None:
                        callee_alias[attr['alias']] = dst_node
                    if graph.nodes[dst_node]['type'] in [NODE_TYPE_FILE, NODE_TYPE_CLASS]:
                        callee_nodes.extend(get_inner_nodes(cur_node, dst_node, graph))
                    if graph.nodes[dst_node]['type'] in [NODE_TYPE_FUNCTION, NODE_TYPE_CLASS]:
                        callee_nodes.append(dst_node)

            break

        pre_node = cur_node
        cur_node = find_parent(cur_node)

    return callee_nodes, callee_alias


def analyze_init(node, code_tree, graph, repo_path):
    caller_name = node.split(':')[-1].split('.')[-1]
    file_path = os.path.join(repo_path, node.split(':')[0])

    invocations = []
    inheritances = []

    def add_invoke(func_name):
        # if func_name in callee_names:
        invocations.append(func_name)

    def add_inheritance(class_name):
        inheritances.append(class_name)

    def process_decorator_node(_decorator_node):
        if isinstance(_decorator_node, ast.Name):
            add_invoke(_decorator_node.id)
        else:
            for _sub_node in ast.walk(_decorator_node):
                if isinstance(_sub_node, ast.Call) and isinstance(_sub_node.func, ast.Name):
                    add_invoke(_sub_node.func.id)
                elif isinstance(_sub_node, ast.Attribute):
                    add_invoke(_sub_node.attr)

    def process_inheritance_node(_inheritance_node):
        if isinstance(_inheritance_node, ast.Attribute):
            add_inheritance(_inheritance_node.attr)
        if isinstance(_inheritance_node, ast.Name):
            add_inheritance(_inheritance_node.id)

    for ast_node in ast.walk(code_tree):
        if isinstance(ast_node, ast.ClassDef) and ast_node.name == caller_name:
            # add imports
            imports = find_imports(file_path, repo_path, tree=ast_node)
            add_imports(node, imports, graph, repo_path)

            for inheritance_node in ast_node.bases:
                process_inheritance_node(inheritance_node)

            for decorator_node in ast_node.decorator_list:
                process_decorator_node(decorator_node)

            for body_item in ast_node.body:
                if isinstance(body_item, ast.FunctionDef) and body_item.name == '__init__':
                    # add imports
                    imports = find_imports(file_path, repo_path, tree=body_item)
                    add_imports(node, imports, graph, repo_path)

                    for decorator_node in body_item.decorator_list:
                        process_decorator_node(decorator_node)

                    for sub_node in ast.walk(body_item):
                        if isinstance(sub_node, ast.Call):
                            if isinstance(sub_node.func, ast.Name):  # function or class
                                add_invoke(sub_node.func.id)
                            if isinstance(sub_node.func, ast.Attribute):  # member function
                                add_invoke(sub_node.func.attr)
                    break
            break

    return invocations, inheritances


def analyze_invokes(node, code_tree, graph, repo_path):
    caller_name = node.split(':')[-1].split('.')[-1]
    file_path = os.path.join(repo_path, node.split(':')[0])

    # store all the invokes found
    invocations = []

    def add_invoke(func_name):
        # if func_name in callee_names:
        invocations.append(func_name)

    def process_decorator_node(_decorator_node):
        if isinstance(_decorator_node, ast.Name):
            add_invoke(_decorator_node.id)
        else:
            for _sub_node in ast.walk(_decorator_node):
                if isinstance(_sub_node, ast.Call) and isinstance(_sub_node.func, ast.Name):
                    add_invoke(_sub_node.func.id)
                elif isinstance(_sub_node, ast.Attribute):
                    add_invoke(_sub_node.attr)

    def traverse_call(_node):
        for child in ast.iter_child_nodes(_node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Skip inner function/class definition
                continue
            elif isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    add_invoke(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    add_invoke(child.func.attr)
            # Recursively traverse child nodes
            traverse_call(child)

    # Traverse AST nodes to find invokes
    for ast_node in ast.walk(code_tree):
        if (isinstance(ast_node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and ast_node.name == caller_name):
            # Add imports
            imports = find_imports(file_path, repo_path, tree=ast_node)
            add_imports(node, imports, graph, repo_path)

            # Traverse decorators
            for decorator_node in ast_node.decorator_list:
                process_decorator_node(decorator_node)

            # Traverse all the invokes nodes inside the function body, excluding inner functions and classes
            traverse_call(ast_node)
            break

    return invocations


def visualize_graph(G):
    node_types = set(nx.get_node_attributes(G, 'type').values())
    node_shapes = {NODE_TYPE_CLASS: 'o', NODE_TYPE_FUNCTION: 's', NODE_TYPE_FILE: 'D',
                   NODE_TYPE_DIRECTORY: '^'}
    node_colors = {NODE_TYPE_CLASS: 'lightgreen', NODE_TYPE_FUNCTION: 'lightblue',
                   NODE_TYPE_FILE: 'lightgrey', NODE_TYPE_DIRECTORY: 'orange'}

    edge_types = set(nx.get_edge_attributes(G, 'type').values())
    edge_colors = {EDGE_TYPE_IMPORTS: 'forestgreen', EDGE_TYPE_CONTAINS: 'skyblue',
                   EDGE_TYPE_INVOKES: 'magenta', EDGE_TYPE_INHERITS: 'brown'}
    edge_styles = {EDGE_TYPE_IMPORTS: 'solid', EDGE_TYPE_CONTAINS: 'dashed', EDGE_TYPE_INVOKES: 'dotted',
                   EDGE_TYPE_INHERITS: 'dashdot'}

    # pos = nx.spring_layout(G, k=2, iterations=50)
    pos = nx.shell_layout(G)
    # pos = nx.circular_layout(G, scale=2, center=(0, 0))

    plt.figure(figsize=(20, 20))
    plt.margins(0.15)  # Add padding around the plot

    # Draw nodes with different shapes and colors based on their type
    for ntype in node_types:
        nodelist = [n for n, d in G.nodes(data=True) if d['type'] == ntype]
        nx.draw_networkx_nodes(
            G,
            pos,
            nodelist=nodelist,
            node_shape=node_shapes[ntype],
            node_color=node_colors[ntype],
            node_size=700,
            label=ntype,
        )

    # Draw labels
    nx.draw_networkx_labels(G, pos, font_size=12, font_family='sans-serif')

    # Group edges between the same pair of nodes
    edge_groups = {}
    for u, v, key, data in G.edges(keys=True, data=True):
        if (u, v) not in edge_groups:
            edge_groups[(u, v)] = []
        edge_groups[(u, v)].append((key, data))

    # Draw edges with adjusted 'rad' values
    for (u, v), edges in edge_groups.items():
        num_edges = len(edges)
        for i, (key, data) in enumerate(edges):
            edge_type = data['type']
            # Adjust 'rad' to spread the edges
            rad = 0.1 * (i - (num_edges - 1) / 2)
            nx.draw_networkx_edges(
                G,
                pos,
                edgelist=[(u, v)],
                edge_color=edge_colors[edge_type],
                style=edge_styles[edge_type],
                connectionstyle=f'arc3,rad={rad}',
                arrows=True,
                arrowstyle='-|>',
                arrowsize=15,
                min_source_margin=15,
                min_target_margin=15,
                width=1.5
            )

    # Create legends for edge types and node types
    edge_legend_elements = [
        Line2D([0], [0], color=edge_colors[etype], lw=2, linestyle=edge_styles[etype], label=etype)
        for etype in edge_types
    ]
    node_legend_elements = [
        Line2D([0], [0], marker=node_shapes[ntype], color='w', label=ntype,
               markerfacecolor=node_colors[ntype], markersize=15)
        for ntype in node_types
    ]

    # Combine legends
    plt.legend(handles=edge_legend_elements + node_legend_elements, loc='upper left')
    plt.axis('off')
    plt.savefig('plots/dp_v3.png')


def traverse_directory_structure(graph, root='/'):
    def traverse(node, prefix, is_last):
        if node == root:
            print(f"{node}")
            new_prefix = ''
        else:
            connector = '└── ' if is_last else '├── '
            print(f"{prefix}{connector}{node}")
            new_prefix = prefix + ('    ' if is_last else '│   ')

        # Stop if the current node is a file (leaf node)
        if graph.nodes[node].get('type') == 'file':
            return

        # Traverse neighbors with edge type 'contains'
        neighbors = list(graph.neighbors(node))
        for i, neighbor in enumerate(neighbors):
            for key in graph[node][neighbor]:
                if graph[node][neighbor][key].get('type') == 'contains':
                    is_last_child = (i == len(neighbors) - 1)
                    traverse(neighbor, new_prefix, is_last_child)

    traverse(root, '', False)


def main():
    # Generate Dependency Graph
    graph = build_graph(args.repo_path, global_import=args.global_import)

    if args.visualize:
        visualize_graph(graph)

    inherit_list = []
    edge_types = []
    for u, v, data in graph.edges(data=True):
        if data['type'] == EDGE_TYPE_IMPORTS:
            inherit_list.append((u, v))
            # print((u, v))
        edge_types.append(data['type'])
    print()
    print(Counter(edge_types))

    node_types = []
    for node, data in graph.nodes(data=True):
        node_types.append(data['type'])
    print(Counter(node_types))

    traverse_directory_structure(graph)
    # breakpoint()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo_path', type=str, default='DATA/repo/pallets__flask-5063')
    parser.add_argument('--visualize', action='store_true')
    parser.add_argument('--global_import', action='store_true')
    args = parser.parse_args()

    main()

