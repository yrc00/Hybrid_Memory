
"""This file contains the function calling implementation for different actions.
"""

import json
from litellm import (
    ChatCompletionToolParam,
    ChatCompletionToolParamFunctionChunk,
    ModelResponse,
)
from util.actions.action import (
    Action,
    FinishAction,
    # CmdRunAction,
    IPythonRunCellAction,
    MessageAction,
)
from .finish import FinishTool
from .structure_tools import ExploreTreeStructure, ExploreTreeStructure_simple, make_explore_tree_structure
from .content_tools import SearchEntityTool, SearchRepoTool
<<<<<<< HEAD
from .df_tools import ALL_DF_TOOLS
=======
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
import logging
logger = logging.getLogger()

ALL_FUNCTIONS = ['explore_tree_structure', 'search_code_snippets', 'get_entity_contents']
<<<<<<< HEAD
ALL_DF_FUNCTIONS = [
    'get_exception_boundaries',
    'get_value_transforms',
    'get_inherit_meta',
    'get_invoke_meta',
]
=======
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e

SYSTEM_PROMPT = """You are a helpful assistant that can interact with a computer to solve tasks.
<IMPORTANT>
* If user provides a path, you should NOT assume it's relative to the current working directory. Instead, you should explore the file system to find the file before working on it.
</IMPORTANT>
"""

<<<<<<< HEAD
SYSTEM_PROMPT_DF = """You are a helpful assistant that can interact with a computer to solve tasks.
<IMPORTANT>
* If user provides a path, you should NOT assume it's relative to the current working directory. Instead, you should explore the file system to find the file before working on it.
</IMPORTANT>

When localizing bugs, follow this reasoning order:
1. Traceback에 등장하는 파일/함수를 시작점으로 삼는다.
2. invoke 엣지를 따라 호출 경로를 탐색한다.
3. invoke로 연결되지 않는 경우, exception_boundary 엣지로 연결된 파일을 추가 탐색한다 (get_exception_boundaries 사용).
4. 반환값이 None이거나 타입이 변환되는 경로가 의심되면 value_transform 엣지를 조회한다 (get_value_transforms 사용).
5. 상속 구조에서 속성 누락이 의심되면 inherit_meta를 확인한다 (get_inherit_meta 사용).
※ 실제 수정 위치는 값이 읽히는 곳이 아닌, 값이 변환되거나 결정되는 중간 지점에 있을 가능성이 높다.
"""

=======
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e

def combine_thought(action: Action, thought: str) -> Action:
    if hasattr(action, 'raw_content') and thought:
        action.raw_content = thought
    if hasattr(action, 'thought') and thought:
        action.thought += '\n' + thought
    return action


def response_to_actions(response: ModelResponse) -> list[Action]:
    actions: list[Action] = []
    assert len(response.choices) == 1, 'Only one choice is supported for now'
    assistant_msg = response.choices[0].message
    if assistant_msg.tool_calls:
        # Check if there's assistant_msg.content. If so, add it to the thought
        thought = ''
        if isinstance(assistant_msg.content, str):
            thought = assistant_msg.content
        elif isinstance(assistant_msg.content, list):
            for msg in assistant_msg.content:
                if msg['type'] == 'text':
                    thought += msg['text']

        # Process each tool call to OpenHands action
        for i, tool_call in enumerate(assistant_msg.tool_calls):
            action: Action
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.decoder.JSONDecodeError as e:
                raise RuntimeError(
                    f'Failed to parse tool call arguments: {tool_call.function.arguments}'
                ) from e
            if tool_call.function.name == 'finish':
                if list(arguments.values()):
                    action = FinishAction(thought=list(arguments.values())[0])
                else:
                    action = FinishAction()
                
<<<<<<< HEAD
            elif tool_call.function.name in ALL_FUNCTIONS + ALL_DF_FUNCTIONS:
=======
            elif tool_call.function.name in ALL_FUNCTIONS:
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
                # We implement this in agent_skills, which can be used via Jupyter
                func_name = tool_call.function.name
                code = f'print({func_name}(**{arguments}))'
                logger.debug(f'TOOL CALL: {func_name} with code: {code}')
                action = IPythonRunCellAction(code=code,
                                              function_name=func_name,
                                              tool_call_id=tool_call.id)  # include_extra=False
            else:
                raise RuntimeError(f'Unknown tool call: {tool_call.function.name}')

            # We only add thought to the first action
            if i == 0:
                action = combine_thought(action, thought)

            actions.append(action)
    else:
        actions.append(
            MessageAction(raw_content=assistant_msg.content, content=assistant_msg.content)
        )

    assert len(actions) >= 1
    return actions


def get_tools(
        codeact_enable_search_keyword: bool = False,
        codeact_enable_search_entity: bool = False,
        codeact_enable_tree_structure_traverser: bool = False,
        simple_desc: bool = False,
        use_dataflow: bool = False,
) -> list[ChatCompletionToolParam]:
    tools = [FinishTool]
    if codeact_enable_search_keyword:
        tools.append(SearchRepoTool)
    if codeact_enable_search_entity:
        tools.append(SearchEntityTool)
    if codeact_enable_tree_structure_traverser:
        tools.append(make_explore_tree_structure(use_dataflow=use_dataflow, simple_desc=simple_desc))
<<<<<<< HEAD
    if use_dataflow:
        tools.extend(ALL_DF_TOOLS)
    return tools


def get_active_functions(use_dataflow: bool = False) -> list[str]:
    """Return the list of callable function names for the current mode."""
    funcs = list(ALL_FUNCTIONS)
    if use_dataflow:
        funcs.extend(ALL_DF_FUNCTIONS)
    return funcs

=======
    return tools


>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
