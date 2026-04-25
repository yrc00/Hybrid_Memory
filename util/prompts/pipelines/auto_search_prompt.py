TASK_INSTRUECTION="""
Given the following GitHub problem description, your objective is to localize the specific files, classes or functions, and lines of code that need modification or contain key information to resolve the issue.

Follow these steps to localize the issue:
## Step 1: Categorize and Extract Key Problem Information
 - Classify the problem statement into the following categories:
    Problem description, error trace, code to reproduce the bug, and additional context.
 - Identify modules in the '{package_name}' package mentioned in each category.
 - Use extracted keywords and line numbers to search for relevant code references for additional context.

## Step 2: Locate Referenced Modules
- Accurately determine specific modules
    - Explore the repo to familiarize yourself with its structure.
    - Analyze the described execution flow to identify specific modules or components being referenced.
- Pay special attention to distinguishing between modules with similar names using context and described execution flow.
- Output Format for collected relevant modules:
    - Use the format: 'file_path:QualifiedName'
    - E.g., for a function `calculate_sum` in the `MathUtils` class located in `src/helpers/math_helpers.py`, represent it as: 'src/helpers/math_helpers.py:MathUtils.calculate_sum'.

## Step 3: Analyze and Reproducing the Problem
- Clarify the Purpose of the Issue
    - If expanding capabilities: Identify where and how to incorporate new behavior, fields, or modules.
    - If addressing unexpected behavior: Focus on localizing modules containing potential bugs.
- Reconstruct the execution flow
    - Identify main entry points triggering the issue.
    - Trace function calls, class interactions, and sequences of events.
    - Identify potential breakpoints causing the issue.
    Important: Keep the reconstructed flow focused on the problem, avoiding irrelevant details.

## Step 4: Locate Areas for Modification
- Locate specific files, functions, or lines of code requiring changes or containing critical information for resolving the issue.
- Consider upstream and downstream dependencies that may affect or be affected by the issue.
- If applicable, identify where to introduce new fields, functions, or variables.
- Think Thoroughly: List multiple potential solutions and consider edge cases that could impact the resolution.

## Output Format for Final Results:
Your final output should list the locations requiring modification, wrapped with triple backticks ```
Each location should include the file path, class name (if applicable), function name, or line numbers, ordered by importance.
Your answer would better include about 5 files.

### Examples:
```
full_path1/file1.py
line: 10
class: MyClass1
function: my_function1

full_path2/file2.py
line: 76
function: MyClass2.my_function2

full_path3/file3.py
line: 24
line: 156
function: my_function3
```

Return just the location(s)

Note: Your thinking should be thorough and so it's fine if it's very long.
"""

<<<<<<< HEAD
TASK_INSTRUECTION_DF = TASK_INSTRUECTION + """
---
## Hybrid Memory Reasoning Guide

When localizing bugs using the Hybrid Memory graph, follow this exploration order:

1. **Traceback 진입점**: Traceback에 등장하는 파일/함수를 시작점으로 삼는다.
2. **Invoke 탐색**: `explore_tree_structure` + `dependency_type_filter=['invokes']`로 호출 경로를 탐색한다.
3. **Exception Boundary 탐색**: invoke로 연결되지 않는 파일 간 흐름이 의심되면 `get_exception_boundaries(node_id)`로 raise/catch 지점을 탐색한다.
4. **Value Transform 탐색**: 반환값이 None이거나 타입 불일치가 의심되면 `get_value_transforms(node_id)`로 변환 경로를 확인한다.
5. **Inherit Meta 탐색**: 속성 미초기화나 MRO 버그가 의심되면 `get_inherit_meta(class_node_id)`로 상속 메타를 확인한다.
6. **Invoke Meta 탐색**: 반환값을 guard 없이 subscript/attribute로 접근하는 패턴이 의심되면 `get_invoke_meta(src, dst)`로 호출 메타를 확인한다.

※ 실제 수정 위치는 값이 읽히는 곳이 아닌, 값이 변환되거나 결정되는 중간 지점에 있을 가능성이 높다.
"""

=======
>>>>>>> 77306e872c6bb472e028b2923056c57a53c5f75e
FAKE_USER_MSG_FOR_LOC = (
    'Verify if the found locations contain all the necessary information to address the issue, and check for any relevant references in other parts of the codebase that may not have appeared in the search results. '
    'If not, continue searching for additional locations related to the issue.\n'
    'Verify that you have carefully analyzed the impact of the found locations on the repository, especially their dependencies. '
    'If you think you have solved the task, please send your final answer (including the former answer and reranking) to user through message and then call `finish` to finish.\n'
    'IMPORTANT: YOU SHOULD NEVER ASK FOR HUMAN HELP.\n'
)