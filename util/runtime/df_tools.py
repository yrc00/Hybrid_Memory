"""Tool definitions for Hybrid Memory (--use_dataflow) mode.

Provides ChatCompletionToolParam objects for the four graph-query tools that
expose the new edge types: exception_boundary, value_transform, and the
enriched inherit / invoke edge metadata.
"""

from litellm import ChatCompletionToolParam, ChatCompletionToolParamFunctionChunk

# ---------------------------------------------------------------------------
# get_exception_boundaries
# ---------------------------------------------------------------------------

_EXCEPTION_BOUNDARIES_DESC = """
[Exception Boundary]
Query exception_boundary edges connected to a specific node (function or class).

Returns:
- raise_sites where this node raises exceptions (with exc_type, line, unhandled flag).
- catch_sites where this node handles exceptions (with catches list, line).
- When crosses_file=True, the connected external file nodes are also returned.

When to use:
- Traceback에 등장하는 예외 타입을 기준으로 raise/catch 지점을 탐색할 때.
- invoke 경로만으로 탐색되지 않는 파일 간 연결을 찾을 때.
"""

GetExceptionBoundariesTool = ChatCompletionToolParam(
    type='function',
    function=ChatCompletionToolParamFunctionChunk(
        name='get_exception_boundaries',
        description=_EXCEPTION_BOUNDARIES_DESC,
        parameters={
            'type': 'object',
            'properties': {
                'node_id': {
                    'type': 'string',
                    'description': (
                        "Node ID of the function or class to query. "
                        "Format: 'file_path:QualifiedName' "
                        "(e.g., 'src/parser.py:Parser.parse')."
                    ),
                },
            },
            'required': ['node_id'],
        },
    ),
)

# ---------------------------------------------------------------------------
# get_value_transforms
# ---------------------------------------------------------------------------

_VALUE_TRANSFORMS_DESC = """
[Value Transform]
Query value_transform edges within a specific node (function or class).

Returns the list of type conversions detected in the function body:
- src_expr: expression before conversion.
- src_type: inferred type before conversion (may be 'unknown').
- dst_expr: variable receiving the converted value.
- dst_type: type after conversion (e.g., 'int', 'str', 'dict/list').
- line: line number of the conversion.
- description: optional LLM-generated explanation (absent if vLLM unavailable).

When to use:
- None 반환, 타입 불일치, 잘못된 파싱 결과 등이 의심될 때.
- 버그의 원인이 값의 변환 과정에 있을 때, 변환 전후 노드를 함께 탐색.
"""

GetValueTransformsTool = ChatCompletionToolParam(
    type='function',
    function=ChatCompletionToolParamFunctionChunk(
        name='get_value_transforms',
        description=_VALUE_TRANSFORMS_DESC,
        parameters={
            'type': 'object',
            'properties': {
                'node_id': {
                    'type': 'string',
                    'description': (
                        "Node ID of the function or class to query. "
                        "Format: 'file_path:QualifiedName'."
                    ),
                },
            },
            'required': ['node_id'],
        },
    ),
)

# ---------------------------------------------------------------------------
# get_inherit_meta
# ---------------------------------------------------------------------------

_INHERIT_META_DESC = """
[Inherit Meta]
Query the inheritance metadata attached to the inherits edges of a class node.

Returns for each parent class:
- child_has_init: whether the child class defines __init__.
- child_calls_super_init: whether the child's __init__ calls super().__init__().
- parent_init_sets: attributes set by the parent's __init__ (self.xxx).
- child_init_sets: attributes set by the child's __init__.
- missing_attrs: attributes present in parent but absent in child.
- description: optional LLM-generated explanation.

When to use:
- 속성 미초기화, MRO 관련 버그가 의심될 때.
- 상속 구조에서 __init__ 설정 누락, super().__init__() 미호출 등을 탐지할 때.
"""

GetInheritMetaTool = ChatCompletionToolParam(
    type='function',
    function=ChatCompletionToolParamFunctionChunk(
        name='get_inherit_meta',
        description=_INHERIT_META_DESC,
        parameters={
            'type': 'object',
            'properties': {
                'class_node_id': {
                    'type': 'string',
                    'description': (
                        "Node ID of the child class to query. "
                        "Format: 'file_path:ClassName'."
                    ),
                },
            },
            'required': ['class_node_id'],
        },
    ),
)

# ---------------------------------------------------------------------------
# get_invoke_meta
# ---------------------------------------------------------------------------

_INVOKE_META_DESC = """
[Invoke Meta]
Query the call-site metadata attached to a specific invokes edge (src → dst).

Returns:
- return_nullable: whether the callee can return None.
- nullable_reason: 'bare return' or 'return None' if nullable.
- return_bound_to: variable in the caller that receives the return value.
- guard_before_use: whether there is a None-check before the variable is used.
- first_use_expr: the first expression where the return value is used.
- first_use_line: line number of that first use.
- use_type: how the value is used ('subscript', 'attribute', 'call', etc.).
- description: optional LLM-generated explanation.

When to use:
- 반환값을 guard 없이 바로 subscript/attribute 접근하는 패턴이 의심될 때.
- 반환값이 None일 수 있는 경우와 그 사용 방식을 확인할 때.
"""

GetInvokeMetaTool = ChatCompletionToolParam(
    type='function',
    function=ChatCompletionToolParamFunctionChunk(
        name='get_invoke_meta',
        description=_INVOKE_META_DESC,
        parameters={
            'type': 'object',
            'properties': {
                'src_node_id': {
                    'type': 'string',
                    'description': "Node ID of the caller. Format: 'file_path:QualifiedName'.",
                },
                'dst_node_id': {
                    'type': 'string',
                    'description': "Node ID of the callee. Format: 'file_path:QualifiedName'.",
                },
            },
            'required': ['src_node_id', 'dst_node_id'],
        },
    ),
)

# Convenience list for registration
ALL_DF_TOOLS = [
    GetExceptionBoundariesTool,
    GetValueTransformsTool,
    GetInheritMetaTool,
    GetInvokeMetaTool,
]
