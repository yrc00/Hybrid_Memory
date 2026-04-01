from litellm import (
    ChatCompletionToolParam,
    ChatCompletionToolParamFunctionChunk,
    ModelResponse,
)

_STRUCTURE_EXPLORER_DESCRIPTION_simple = """
A unified tool that traverses a pre-built code graph to retrieve dependency structure around specified entities, 
with options to explore upstream or downstream, and control traversal depth and filters for entity and dependency types.
"""


_TREE_EXAMPLE_simple = """
Example Usage:
1. Exploring Downstream Dependencies:
    ```
    explore_tree_structure(
        start_entities=['src/module_a.py:ClassA'],
        direction='downstream',
        traversal_depth=2,
        dependency_type_filter=['invokes', 'imports']
    )
    ```
2. Exploring the repository structure from the root directory (/) up to two levels deep:
    ```
    explore_tree_structure(
      start_entities=['/'],
      traversal_depth=2,
      dependency_type_filter=['contains']
    )
    ```
3. Generate Class Diagrams:
    ```
    explore_tree_structure(
        start_entities=selected_entity_ids,
        direction='both',
        traverse_depth=-1,
        dependency_type_filter=['inherits']
    )
    ```
"""


_STRUCTURE_EXPLORER_DESCRIPTION_BASE = """
Unified repository exploring tool that traverses a pre-built code graph to retrieve dependency structure around specified entities.
The search can be controlled to traverse upstream (exploring dependencies that entities rely on) or downstream (exploring how entities impact others), with optional limits on traversal depth and filters for entity and dependency types.

Code Graph Definition:
* Entity Types: 'directory', 'file', 'class', 'function'.
* Dependency Types: 'contains', 'imports', 'invokes', 'inherits'.
* Hierarchy:
    - Directories contain files and subdirectories.
    - Files contain classes and functions.
    - Classes contain inner classes and methods.
    - Functions can contain inner functions.
* Interactions:
    - Files/classes/functions can import classes and functions.
    - Classes can inherit from other classes.
    - Classes and functions can invoke others (invocations in a class's `__init__` are attributed to the class).
Entity ID:
* Unique identifier including file path and module path.
* Here's an example of an Entity ID: `"interface/C.py:C.method_a.inner_func"` identifies function `inner_func` within `method_a` of class `C` in `"interface/C.py"`.

Notes:
* Traversal Control: The `traversal_depth` parameter specifies how deep the function should explore the graph starting from the input entities.
* Filtering: Use `entity_type_filter` and `dependency_type_filter` to narrow down the scope of the search, focusing on specific entity types and relationships.

"""

_DATAFLOW_DESCRIPTION_ADDON = """
Data Flow Extensions (available in this graph):
* 'param_flow' (caller → callee): added at each call site; edge attribute `args_mapping` maps parameter names to the argument expressions passed by the caller.
* 'return_flow' (callee → caller): added at each call site; edge attribute `assigned_vars` lists the variables in the caller that receive the return value.
Use these edges to trace how data moves across function boundaries — e.g., find all callers that pass a specific variable as an argument, or locate where a function's return value is consumed.

"""

_STRUCTURE_EXPLORER_DESCRIPTION = _STRUCTURE_EXPLORER_DESCRIPTION_BASE


_TREE_EXAMPLE = """
Example Usage:
1. Exploring Outward Dependencies:
    ```
    explore_tree_structure(
        start_entities=['src/module_a.py:ClassA'],
        direction='downstream',
        traversal_depth=2,
        dependency_type_filter=['invokes', 'imports']
    )
    ```
    This retrieves the dependencies of `ClassA` up to 2 levels deep, focusing only on classes and functions with 'invokes' and 'imports' relationships.

2. Exploring Inward Dependencies:
    ```
    explore_tree_structure(
        start_entities=['src/module_b.py:FunctionY'],
        direction='upstream',
        traversal_depth=-1
    )
    ```
    This finds all entities that depend on `FunctionY` without restricting the traversal depth.
3. Exploring Repository Structure:
    ```
    explore_tree_structure(
      start_entities=['/'],
      traversal_depth=2,
      dependency_type_filter=['contains']
    )
    ```
    This retrieves the tree repository structure from the root directory (/), traversing up to two levels deep and focusing only on 'contains' relationship.
4. Generate Class Diagrams:
    ```
    explore_tree_structure(
        start_entities=selected_entity_ids,
        direction='both',
        traverse_depth=-1,
        dependency_type_filter=['inherits']
    )
    ```
"""


_DEPENDENCY_TYPE_FILTER_DESC_BASE = (
    "List of dependency types to include in the traversal. If None, all dependency types are included. "
    "Available types: 'contains', 'imports', 'invokes', 'inherits'."
)

_DEPENDENCY_TYPE_FILTER_DESC_DATAFLOW = (
    "List of dependency types to include in the traversal. If None, all dependency types are included. "
    "Available types: 'contains', 'imports', 'invokes', 'inherits', "
    "'param_flow' (caller→callee argument mapping), 'return_flow' (callee→caller return value flow)."
)

_STRUCTURE_EXPLORER_PARAMETERS_BASE = {
    'type': 'object',
    'properties': {
        'start_entities': {
            'description': (
                'List of entities (e.g., class, function, file, or directory paths) to begin the search from.\n'
                'Entities representing classes or functions must be formatted as "file_path:QualifiedName" (e.g., `interface/C.py:C.method_a.inner_func`).\n'
                'For files or directories, provide only the file or directory path (e.g., `src/module_a.py` or `src/`).'
            ),
            'type': 'array',
            'items': {'type': 'string'},
        },
        'direction': {
            'description': (
                'Direction of traversal in the code graph; allowed options are: `upstream`, `downstream`, `both`.\n'
                "- 'upstream': Traversal to explore dependencies that the specified entities rely on (how they depend on others).\n"
                "- 'downstream': Traversal to explore the effects or interactions of the specified entities on others (how others depend on them).\n"
                "- 'both': Traversal on both direction."
            ),
            'type': 'string',
            'enum': ['upstream', 'downstream', 'both'],
            'default': 'downstream',
        },
        'traversal_depth': {
            'description': (
                'Maximum depth of traversal. A value of -1 indicates unlimited depth (subject to a maximum limit).'
                'Must be either `-1` or a non-negative integer (≥ 0).'
            ),
            'type': 'integer',
            'default': 2,
        },
        'entity_type_filter': {
            'description': (
                "List of entity types (e.g., 'class', 'function', 'file', 'directory') to include in the traversal. If None, all entity types are included."
            ),
            'type': ['array', 'null'],
            'items': {'type': 'string'},
            'default': None,
        },
        'dependency_type_filter': {
            'description': _DEPENDENCY_TYPE_FILTER_DESC_BASE,
            'type': ['array', 'null'],
            'items': {'type': 'string'},
            'default': None,
        },
    },
    'required': ['start_entities'],
}


def make_explore_tree_structure(use_dataflow: bool = False, simple_desc: bool = False) -> ChatCompletionToolParam:
    """Return an ExploreTreeStructure tool whose description and parameter hints
    reflect whether data flow edges (param_flow / return_flow) are present in the graph."""
    import copy
    params = copy.deepcopy(_STRUCTURE_EXPLORER_PARAMETERS_BASE)
    if use_dataflow:
        params['properties']['dependency_type_filter']['description'] = _DEPENDENCY_TYPE_FILTER_DESC_DATAFLOW
        desc = _STRUCTURE_EXPLORER_DESCRIPTION_BASE + _DATAFLOW_DESCRIPTION_ADDON
        example = _TREE_EXAMPLE
    else:
        desc = _STRUCTURE_EXPLORER_DESCRIPTION_BASE
        example = _TREE_EXAMPLE

    if simple_desc:
        desc = _STRUCTURE_EXPLORER_DESCRIPTION_simple
        example = _TREE_EXAMPLE_simple

    return ChatCompletionToolParam(
        type='function',
        function=ChatCompletionToolParamFunctionChunk(
            name='explore_tree_structure',
            description=desc + example,
            parameters=params,
        ),
    )


# Convenience module-level instances (use_dataflow=False)
ExploreTreeStructure = make_explore_tree_structure(use_dataflow=False, simple_desc=False)
ExploreTreeStructure_simple = make_explore_tree_structure(use_dataflow=False, simple_desc=True)
