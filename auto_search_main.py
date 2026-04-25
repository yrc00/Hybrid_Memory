import argparse
import os
import json
import logging
import logging.handlers
import time
import toml
from queue import Empty
from typing import List
from tqdm import tqdm
from copy import deepcopy
from datasets import load_dataset

from util.runtime.execute_ipython import execute_ipython
from util.runtime import function_calling
from util.actions.action_parser import ResponseParser
from util.actions.action import ActionType
from util.prompts.prompt import PromptManager
from util.prompts import general_prompt
from util.prompts.pipelines import (
    simple_localize_pipeline as simple_loc,
    auto_search_prompt as auto_search,
)
from util.cost_analysis import calc_cost
from util.utils import *
from util.process_output import (
    parse_raw_loc_output,
    get_loc_results_from_raw_outputs,
    merge_sample_locations,
)
from plugins import LocationToolsRequirement
from plugins.location_tools.repo_ops.repo_ops import (
    set_current_issue,
    reset_current_issue,
)
import litellm
from litellm import Message as LiteLLMMessage
from openai import APITimeoutError
from evaluation.eval_metric import filtered_instances


from time import sleep
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import torch.multiprocessing as mp
from util.runtime.fn_call_converter import (
    convert_fncall_messages_to_non_fncall_messages,
    convert_non_fncall_messages_to_fncall_messages,
    STOP_WORDS as NON_FNCALL_STOP_WORDS
)
# litellm.set_verbose=True
# os.environ['LITELLM_LOG'] = 'DEBUG


def load_dataset_local_or_hf(dataset_name: str, split: str):
    """dataset_cache/{name}/{split}/instances.jsonl 가 있으면 로컬에서 로드,
    없으면 HuggingFace에서 다운로드한 뒤 리스트로 반환."""
    from pathlib import Path
    # download_datasets.py 저장 경로 규칙: dataset_cache/<name>/<split>/instances.jsonl
    # dataset_name이 HF 형식("org/name")이면 name 부분만 추출
    local_name = dataset_name.split("/")[-1] if "/" in dataset_name else dataset_name
    local_path = Path(os.path.dirname(os.path.abspath(__file__))) / "dataset_cache" / local_name / split / "instances.jsonl"
    if local_path.exists():
        logging.info(f"Loading dataset from local cache: {local_path}")
        with open(local_path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    else:
        logging.info(f"Local cache not found ({local_path}). Loading from HuggingFace: {dataset_name}")
        hf_data = load_dataset(dataset_name, split=split)
        return list(hf_data)


def filter_dataset(dataset, filter_column: str, used_list: str):
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.toml')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding="utf-8") as file:
            data = toml.load(file)
            if used_list in data:
                selected_ids = set(data[used_list])
                logging.info(
                    f'Filtering {len(selected_ids)} tasks from "selected_ids"...'
                )
                filtered = [ex for ex in dataset if ex[filter_column] in selected_ids]
                logging.info(f'Retained {len(filtered)} tasks after filtering')
                return filtered
    return dataset


def get_task_instruction(instance: dict, task: str = 'auto_search', include_pr=False,
                         include_hint=False, use_dataflow: bool = False):
    output_format = None
    instruction = ""

    # for auto-search pipeline
    if task.strip() == 'auto_search':
        template = auto_search.TASK_INSTRUECTION_DF if use_dataflow else auto_search.TASK_INSTRUECTION
        task_description = template.format(
            package_name=instance['instance_id'].split('_')[0]
        )
    
    elif task.strip() == 'simple_localize':
        task_description = simple_loc.SEARCH_LOC_TASK_INSTRUCTION
        output_format = simple_loc.OUTPUT_FORMAT_LOC
        
    else:
        return None

    instruction += task_description
        
    if include_pr:
        problem_statement = instance['problem_statement']
        instruction += general_prompt.PR_TEMPLATE.format(
            title=problem_statement.strip().split('\n')[0],
            description = '\n'.join(problem_statement.strip().split('\n')[1:]).strip()
        )
    
    if output_format:
        instruction += output_format
    
    if include_hint:
        instruction += (
            'IMPORTANT: You should ONLY interact with the environment provided to you AND NEVER ASK FOR HUMAN HELP.\n'
            'Don\'t include any lambda functions!\n'
            'You should NOT modify any files!\n'
        )

    # NOTE: You can actually set slightly different instruction for different task
    # instruction += AGENT_CLS_TO_INST_SUFFIX
    return instruction


def vanilla_process(result_queue, model_name, messages, temp=1.0):
    """Single-shot LLM call with no tools, no code execution — model only."""
    # Reset inherited logging handlers to prevent BrokenPipeError on Manager proxy queues after fork
    logging.getLogger().handlers = []
    try:
        response = litellm.completion(
            model=model_name,
            messages=messages,
            temperature=temp,
        )
    except litellm.BadRequestError as e:
        result_queue.put({'error': str(e), 'type': 'BadRequestError'})
        return

    content = response.choices[0].message.content or ""
    logging.info("=" * 15)
    logging.info("\nFinal Response (vanilla):\n" + content)

    traj_data = {
        'messages': messages + [convert_to_json(response.choices[0].message)],
        'tools': None,
        'usage': {
            'prompt_tokens': response.usage.prompt_tokens,
            'completion_tokens': response.usage.completion_tokens,
        },
    }
    result_queue.put((content, messages, traj_data))


def auto_search_process(result_queue,
                        model_name, messages, fake_user_msg,
                        tools = None,
                        traj_data=None,
                        temp=1.0,
                        max_iteration_num=20,
                        use_function_calling=True):
    # Reset inherited logging handlers to prevent BrokenPipeError on Manager proxy queues after fork
    logging.getLogger().handlers = []
    if tools and ('hosted_vllm' in model_name
                  or 'qwen' in model_name.lower()
    #             #   or model_name=='azure/gpt-4o'
    #             #   or model_name == 'litellm_proxy/o3-mini-2025-01-31'
                ):
        use_function_calling = False
        
    # for LLM which do not support function calling
    if not use_function_calling:
        # 转换message
        messages = convert_fncall_messages_to_non_fncall_messages(messages, tools, add_in_context_learning_example=False)

    # code_history = []
    parser = ResponseParser()
    if not traj_data:
        traj_msgs = messages.copy()
        prompt_tokens = 0
        completion_tokens = 0
    else:
        # continue from last traj
        traj_msgs = traj_data['messages']
        prompt_tokens = traj_data['usage']['prompt_tokens']
        completion_tokens = traj_data['usage']['completion_tokens']

    # analysis mode tracking
    _call_count = 0
    _input_token = 0       # prompt tokens from the first LLM call (problem statement)
    _tool_calling = 0      # prompt tokens from subsequent calls (tool results in context)
    _tool_numbers = 0      # number of tool invocations

    cur_interation_num = 0
    last_message = None
    last_message_content = None
    finish = False
    while not finish:
        cur_interation_num += 1
        if cur_interation_num == max_iteration_num:
            messages.append({
                'role': 'user',
                'content': 'The Maximum number of interation has been reached, please generate your final output with required format and use <finish></finish> to exit.'
            })
            traj_msgs.append({
                'role': 'user',
                'content': 'The Maximum number of interation has been reached, please generate your final output with required format and use <finish></finish> to exit.'
            })

        try:
            # new conversation
            if tools and ('hosted_vllm' in model_name
                          or 'qwen' in model_name.lower()):
                messages = convert_fncall_messages_to_non_fncall_messages(messages, tools, add_in_context_learning_example=False)
                response = litellm.completion(
                    model=model_name,
                    temperature=temp, top_p=0.8, repetition_penalty=1.05, 
                    messages=messages,
                    stop=NON_FNCALL_STOP_WORDS
                )
            elif tools:
                response = litellm.completion(
                    model=model_name,
                    tools=tools,
                    messages=messages,
                    temperature=temp,
                    # stop=['</execute_ipython>'], #</finish>',
                )
            else:
                response = litellm.completion(
                    model=model_name,
                    messages=messages,
                    temperature=temp,
                    stop=['</execute_ipython>'], #</finish>',
                )
        except litellm.BadRequestError as e:
            # If there's an error, send the error info back to the parent process
            result_queue.put({'error': str(e), 'type': 'BadRequestError'})
            return
        
        if last_message and response.choices[0].message.content == last_message:
            messages.append({
                "role": "user",
                "content": "OBSERVATION:\n" + "Don't repeat your response.\n" + fake_user_msg,
            })
            traj_msgs.append({
                "role": "user",
                "content": "OBSERVATION:\n" + "Don't repeat your response.\n" + fake_user_msg,
            })
            continue
        
        raw_response = deepcopy(response)
        # logging.info('response.choices[0].message')
        if tools and ('hosted_vllm' in model_name
                      or 'qwen' in model_name.lower()
                      or 'deepseek' in model_name
                      ):
            try:
                non_fncall_response_message = response.choices[0].message
                fn_call_messages_with_response = (
                    convert_non_fncall_messages_to_fncall_messages(
                        [non_fncall_response_message], tools # messages + 
                    )
                )
                fn_call_response_message = fn_call_messages_with_response[-1]
                if not isinstance(fn_call_response_message, LiteLLMMessage):
                    fn_call_response_message = LiteLLMMessage(
                        **fn_call_response_message
                    )
                response.choices[0].message = fn_call_response_message
            except:
                logging.info('convert none fncall messages failed.')
                continue 
                
        last_message = response.choices[0].message.content
        print(response.choices[0].message)
        messages.append(convert_to_json(raw_response.choices[0].message))
        traj_msgs.append(convert_to_json(raw_response.choices[0].message))
        _call_count += 1
        if _call_count == 1:
            _input_token += response.usage.prompt_tokens
        else:
            _tool_calling += response.usage.prompt_tokens
        prompt_tokens += response.usage.prompt_tokens
        completion_tokens += response.usage.completion_tokens
            
        actions = parser.parse(response)
        if not isinstance(actions, List):
            actions = [actions]
        for action in actions:
            logging.debug(action.action_type)
            if action.action_type == ActionType.FINISH:
                final_output = action.thought
                # If the thought doesn't contain structured output (.py paths),
                # fall back to the last MESSAGE content which may have the structured format
                if last_message_content and '.py' not in final_output:
                    final_output = last_message_content + '\n' + final_output
                logging.info('='*15)
                logging.info("\nFinal Response:=\n" + final_output)
                finish = True # break
            elif action.action_type == ActionType.MESSAGE:
                last_message_content = action.content
                logging.debug("thought:\n" + action.content)
                # check if enough
                messages.append({"role": "user", "content": fake_user_msg})
                traj_msgs.append({"role": "user", "content": fake_user_msg})
                # continue
            elif action.action_type == ActionType.RUN_IPYTHON:
                _tool_numbers += 1
                ipython_code = action.code.strip('`')
                logging.info(f"Executing code:\n```\n{ipython_code}\n```")
                function_response = execute_ipython(ipython_code)
                try:
                    function_response = eval(function_response)
                except SyntaxError:
                    function_response = function_response
                if not isinstance(function_response, str):
                    function_response = str(function_response)
                
                logging.info("OBSERVATION:\n" + function_response)
                if not tools:
                    messages.append({
                        "role": "user",
                        "content": "OBSERVATION:\n" + function_response,
                    })
                    traj_msgs.append({
                        "role": "user",
                        "content": "OBSERVATION:\n" + function_response,
                    })
                else:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": action.tool_call_id,
                        "name": action.function_name,
                        "content": "OBSERVATION:\n" + function_response,
                    })
                    traj_msgs.append({
                        "role": "tool",
                        "tool_call_id": action.tool_call_id,
                        "name": action.function_name,
                        "content": "OBSERVATION:\n" + function_response,
                    })
            else:
                logging.warning('Error Action!')
                # return

    # save traj
    traj_data = {
        'messages': traj_msgs,
        'tools': tools,
        'usage': {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
        },
        'token_analysis': {
            'input_token': _input_token,
            'tool_calling': _tool_calling,
            'tool_numbers': _tool_numbers,
            'output_token': completion_tokens,
        },
    }
    # return final_output, messages, traj_data
    result_queue.put((final_output, messages, traj_data))


def run_localize(rank, args, bug_queue, log_queue, output_file_lock, traj_file_lock):
    queue_handler = logging.handlers.QueueHandler(log_queue)
    logger = logging.getLogger()
    logger.setLevel(logging.getLevelName(args.log_level))
    logger.handlers = []
    logger.addHandler(queue_handler)

    logger.debug(f"------ rank {rank} start ------")

    while True:
        try:
            bug = bug_queue.get_nowait()
        except Empty:
            break

        instance_id = bug["instance_id"]
        prompt_manager = PromptManager(
            prompt_dir=os.path.join(os.path.dirname(__file__), 'util/prompts'),
            agent_skills_docs=LocationToolsRequirement.documentation,
        )

        logger.info("=" * 60)
        logger.info(f"==== rank {rank} setup localize {instance_id} ====")
        set_current_issue(instance_data=bug, rank=rank, use_dataflow=args.use_dataflow)

        # loc result
        raw_output_loc = []
        loc_trajs = {'trajs': []}
        total_prompt_tokens, total_completion_tokens = 0, 0
        analysis_records = []  # per-trial token analysis (analysis mode only)

        for trial_idx in range(args.num_samples):
            logger.info("=" * 60)
            logger.info(f"==== rank {rank} begin localizing {instance_id} ====")
            max_attempt_num = args.max_attempt_num
            while max_attempt_num:
                logger.info("=" * 60)
                logger.info(f"==== {instance_id} Count down: attempt {max_attempt_num} ====")
                loc_start_time = time.time()
                try:
                    """
                    Basic instructions:
                        - CodeAct instruction
                        - Few-shot Examples
                    """
                    if args.vanilla_mode:
                        system_prompt = "You are a helpful assistant for software bug localization."
                    elif args.use_function_calling:
                        system_prompt = (function_calling.SYSTEM_PROMPT_DF
                                         if args.use_dataflow
                                         else function_calling.SYSTEM_PROMPT)
                    else:
                        system_prompt = prompt_manager.system_message

                    messages: list[dict] = [{
                        "role": "system",
                        "content": system_prompt
                    }]

                    if not args.vanilla_mode and args.use_example:
                        messages.append({
                            "role": "user",
                            "content": prompt_manager.initial_user_message
                        })

                    logger.info(f"==== {instance_id} start {'vanilla' if args.vanilla_mode else 'auto'} search ====")
                    messages.append({
                        "role": "user",
                        "content": get_task_instruction(
                            bug, include_pr=True, include_hint=not args.vanilla_mode,
                            use_dataflow=args.use_dataflow,
                        ),
                    })

                    ctx = mp.get_context('fork')  # use fork to inherit context!!
                    result_queue = ctx.Queue()  # pipe-based, fork-safe (no shared Manager socket)
                    tools = None
                    if args.vanilla_mode:
                        process = ctx.Process(target=vanilla_process, kwargs={
                            'result_queue': result_queue,
                            'model_name': args.model,
                            'messages': messages,
                            'temp': 1,
                        })
                    else:
                        if args.use_function_calling:
                            tools = function_calling.get_tools(
                                codeact_enable_search_keyword=True,
                                codeact_enable_search_entity=True,
                                codeact_enable_tree_structure_traverser=True,
                                simple_desc=args.simple_desc,
                                use_dataflow=args.use_dataflow,
                            )
                        process = ctx.Process(target=auto_search_process, kwargs={
                            'result_queue': result_queue,
                            'model_name': args.model,
                            'messages': messages,
                            'fake_user_msg': auto_search.FAKE_USER_MSG_FOR_LOC,
                            'temp': 1,
                            'tools': tools,
                            'use_function_calling': args.use_function_calling,
                        })
                    process.start()
                    # NOTE: result_queue.get() MUST come before process.join().
                    # ctx.Queue() is pipe-based; if the subprocess calls put() with
                    # a large payload (full message history) the pipe buffer fills up
                    # and the subprocess blocks inside put().  If the parent is
                    # simultaneously blocked in join() waiting for the subprocess to
                    # exit, neither side can proceed → deadlock.
                    # Reading from the queue first drains the pipe so the subprocess
                    # can finish, after which join() returns immediately.
                    try:
                        result = result_queue.get(timeout=args.timeout + 60)
                    except Exception:
                        result = None
                    process.join(timeout=30)
                    if process.is_alive():
                        logger.warning(f"{instance_id} attempt {max_attempt_num} execution flow "
                                        f"reconstruction exceeded timeout. Terminating.")
                        process.terminate()
                        process.join()
                        raise TimeoutError
                    if result is None:
                        raise TimeoutError
                    if isinstance(result, dict) and 'error' in result and result['type'] == 'BadRequestError':
                        if 'ContextWindowExceededError' in result['error']:
                            raise litellm.exceptions.ContextWindowExceededError(result['error'], args.model, args.model.split('/')[0])
                        raise litellm.BadRequestError(result['error'], args.model, args.model.split('/')[0])
                        # print(f"Error occurred in subprocess: {result['error']}")
                    else:
                        loc_result, messages, traj_data = result

                except Empty:
                    logger.warning(f"{instance_id} subprocess exited without result. Try again.")
                    max_attempt_num = max_attempt_num - 1
                    continue
                except litellm.BadRequestError as e:
                    logger.warning(f'{e}. Try again.')
                    continue
                except APITimeoutError:
                    logger.warning(f"APITimeoutError. Try again.")
                    sleep(10)
                    continue
                except TimeoutError:
                    logger.warning(f"Processing time exceeded 15 minutes. Try again.")
                    max_attempt_num = max_attempt_num - 1
                    continue
                except litellm.exceptions.ContextWindowExceededError as e:
                    logger.warning(f'{e}. Try again.')
                    max_attempt_num = max_attempt_num - 1
                    continue

                loc_end_time = time.time()
                if not loc_result:
                    continue # empty result

                total_prompt_tokens += traj_data['usage']['prompt_tokens']
                total_completion_tokens += traj_data['usage']['completion_tokens']
                traj_data['time'] = loc_end_time - loc_start_time
                loc_trajs['trajs'].append(traj_data)

                if args.analyze and 'token_analysis' in traj_data:
                    ta = traj_data['token_analysis']
                    analysis_records.append({
                        'instance_id': instance_id,
                        'trial': trial_idx + 1,
                        'input_token': ta['input_token'],
                        'tool_calling': ta['tool_calling'],
                        'tool_numbers': ta['tool_numbers'],
                        'output_token': ta['output_token'],
                    })

                # generate correct output or finish last attempt
                raw_output_loc.append(loc_result)
                break

        if not raw_output_loc:
            # loc generalization failed
            logger.info(f"==== localizing {instance_id} failed, save empty outputs ====")
            loc_res = {
                    "instance_id": instance_id,
                    "found_files": [[]],
                    "found_modules": [[]],
                    "found_entities": [[]],
                    "raw_output_loc": raw_output_loc,
                    "meta_data": {
                        'repo': bug['repo'],
                        'base_commit': bug['base_commit'],
                        'problem_statement': bug['problem_statement'],
                        'patch': bug['patch'],
                        # 'gt_file_changes': gt_file_changes
                    }
                }
            with output_file_lock:
                append_to_jsonl(loc_res, args.output_file)
        else:
            # process multiple loc outputs
            logger.info(f"==== localizing {instance_id} succeed, process multiple loc outputs ====")

            # all_valid_files = get_all_valid_files()
            all_found_files, all_found_modules, all_found_entities = get_loc_results_from_raw_outputs(
                instance_id, raw_output_loc
            )
            
            loc_res = {
                "instance_id": instance_id,
                "found_files": all_found_files,
                "found_modules": all_found_modules,
                "found_entities": all_found_entities,
                "raw_output_loc": raw_output_loc,
                "meta_data": {
                    'repo': bug['repo'],
                    'base_commit': bug['base_commit'],
                    'problem_statement': bug['problem_statement'],
                    'patch': bug['patch'],
                    # 'gt_file_changes': gt_file_changes
                }
            }
            
            with output_file_lock:
                append_to_jsonl(loc_res, args.output_file)

            cost = calc_cost(args.model, total_prompt_tokens, total_completion_tokens)
            loc_res['usage'] = {'cost($)': f'{round(cost, 5)}', 'prompt_tokens': total_prompt_tokens,
                                'completion_tokens': total_completion_tokens}
            loc_res['loc_trajs'] = loc_trajs
            traj_file = os.path.join(args.output_folder, 'loc_trajs.jsonl')
            with traj_file_lock:
                append_to_jsonl(loc_res, traj_file)

        if args.analyze and analysis_records:
            analysis_file = os.path.join(args.output_folder, 'token_analysis.jsonl')
            with output_file_lock:
                for record in analysis_records:
                    append_to_jsonl(record, analysis_file)

        reset_current_issue()


def localize(args):
    bench_data = load_dataset_local_or_hf(args.dataset, args.split)
    bench_tests = filter_dataset(bench_data, 'instance_id', args.used_list)
    if args.eval_n_limit:
        eval_n_limit = min(args.eval_n_limit, len(bench_tests))
        bench_tests = bench_tests[:eval_n_limit]
        logging.info(f'Limiting evaluation to first {eval_n_limit} instances.')

    manager = mp.Manager()
    queue = manager.Queue()
    output_file_lock, traj_file_lock = manager.Lock(), manager.Lock()

    # collect processed instances
    processed_instance = []
    if os.path.exists(args.output_file):
        traj_file = os.path.join(args.output_folder, 'loc_trajs.jsonl')
        locs = load_jsonl(args.output_file)        
        if args.rerun_empty_location:
            traj_datas = load_jsonl(traj_file)
            backup_loc_output = backup_file(args.output_file)
            backup_traj_output = backup_file(traj_file)
            clear_file(args.output_file)
            clear_file(traj_file)
            for loc in locs:
                if loc['found_files'] != [[]]:
                    append_to_jsonl(loc, args.output_file)
                    processed_instance.append(loc['instance_id'])
                    
            for loc_traj in traj_datas:
                if loc_traj['found_files'] != [[]]:
                    append_to_jsonl(loc_traj, traj_file)
        else:
            processed_instance = [loc['instance_id'] for loc in locs]
    
    num_bugs = 0
    for bug in bench_tests:
        instance_id = bug["instance_id"]
        if instance_id in processed_instance:
        # if instance_id in processed_instance or instance_id in filtered_instances:
            print(f"instance {instance_id} has already been processed, skip.")
        else:
            queue.put(bug)
            num_bugs += 1

    log_queue = manager.Queue()
    queue_listener = logging.handlers.QueueListener(log_queue, *logging.getLogger().handlers)
    queue_listener.start()
    mp.spawn(
        run_localize,
        nprocs=min(num_bugs, args.num_processes) if args.num_processes > 0 else num_bugs,
        args=(args, queue, log_queue, output_file_lock, traj_file_lock),
        join=True
    )
    queue_listener.stop()
    
    if args.rerun_empty_location:
        try:
            delete_file(backup_loc_output)
            delete_file(backup_traj_output)
        except:
            return


def merge(args):
    args.merge_file = os.path.join(args.output_folder, 'merged_' + os.path.basename(args.output_file))
    
    if args.ranking_method == 'mrr':
        args.merge_file = args.merge_file.replace('.jsonl', f'_{args.ranking_method}.jsonl')
        
    clear_file(args.merge_file)
    with open(args.output_file, 'r', encoding="utf-8") as file:
        for line in file:
            loc_data = json.loads(line)
            if loc_data['found_files'] == [[]]:
                loc_data['found_files'] = []
                loc_data['found_modules'] = []
                loc_data['found_entities'] = []
            else:
                loc_data['found_files'] = loc_data['found_files']
                loc_data['found_modules'] = loc_data['found_modules']
                loc_data['found_entities'] = loc_data['found_entities']
                ranked_files, ranked_modules, ranked_funcs = merge_sample_locations(loc_data['found_files'], 
                                                                    loc_data['found_modules'],
                                                                    loc_data['found_entities'],
                                                                    ranking_method=args.ranking_method,
                                                                    )
                loc_data['found_files'] = ranked_files
                loc_data['found_modules'] = ranked_modules
                loc_data['found_entities'] = ranked_funcs
            with open(args.merge_file, 'a', encoding="utf-8") as f:
                f.write(json.dumps(loc_data) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--localize", action="store_true")
    parser.add_argument("--merge", action="store_true")
    parser.add_argument("--use_example", action="store_true")
    parser.add_argument("--ranking_method", type=str, default='mrr',
                        choices=['mrr', 'majority'])
    
    parser.add_argument("--dataset", type=str, default="princeton-nlp/SWE-bench_Lite")
    parser.add_argument("--split", type=str, default="test")
    parser.add_argument("--eval_n_limit", type=int, default=0)
    parser.add_argument("--used_list", type=str, default='selected_ids')
    
    parser.add_argument("--output_folder", type=str, required=True)
    parser.add_argument("--output_file", type=str, default="loc_outputs.jsonl")
    parser.add_argument("--merge_file", type=str, default="merged_loc_outputs.jsonl")
    
    parser.add_argument(
        "--model", type=str,
        default="openai/gpt-4o-2024-05-13",
        choices=["gpt-4o", 
                 "azure/gpt-4o", "openai/gpt-4o-2024-05-13",
                 "deepseek/deepseek-chat", "deepseek-ai/DeepSeek-R1",
                 "litellm_proxy/claude-3-5-sonnet-20241022", "litellm_proxy/gpt-4o-2024-05-13", "litellm_proxy/o3-mini-2025-01-31",
                 # fine-tuned model
                 "openai/qwen-7B", "openai/qwen-7B-128k", "openai/ft-qwen-7B", "openai/ft-qwen-7B-128k",
                 "openai/qwen-32B", "openai/qwen-32B-128k", "openai/ft-qwen-32B", "openai/ft-qwen-32B-128k",

                 # models
                 "openai/Qwen/Qwen2.5-Coder-7B-Instruct", "openai/Qwen/Qwen2.5-Coder-32B-Instruct",
                 "openai/czlll/Qwen2.5-Coder-7B-CL", "openai/czlll/Qwen2.5-Coder-32B-CL",
                 "openai/mistralai/Devstral-Small-2-24B-Instruct-2512",
                 "openai/Qwen/Qwen3-Coder-30B-A3B-Instruct",
        ]
    )
    parser.add_argument("--use_dataflow", action="store_true",
                        help='Build the dependency graph with data flow edges (param_flow, return_flow). '
                             'Enables the LLM to reason about argument-to-parameter mappings and return value flows.')
    parser.add_argument("--vanilla_mode", action="store_true",
                        help='Skip all LocAgent tools (graph/indexing). The model answers using only the problem statement — useful for baseline performance evaluation.')
    parser.add_argument("--use_function_calling", action="store_true",
                        help='Enable function calling features of LLMs. If disabled, codeact will be used to support function calling.')
    parser.add_argument("--simple_desc", action="store_true",
                        help="Use simplified function descriptions due to certain LLM limitations. Set to False for better performance when using Claude.")
    
    parser.add_argument("--max_attempt_num", type=int, default=1, 
                        help='Only use in generating training trajectories.')
    parser.add_argument("--num_samples", type=int, default=2)
    parser.add_argument("--num_processes", type=int, default=-1)
    
    parser.add_argument("--log_level", type=str, default='INFO')
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--rerun_empty_location", action="store_true")
    parser.add_argument("--analyze", action="store_true",
                        help="Analysis mode: record per-trial token usage "
                             "(input_token, tool_calling, tool_numbers, output_token) "
                             "to token_analysis.jsonl.")
    args = parser.parse_args()

    args.output_file = os.path.join(args.output_folder, args.output_file)
    os.makedirs(args.output_folder, exist_ok=True)

    # write the arguments
    with open(f"{args.output_folder}/args.json", "w", encoding="utf-8") as f:
        json.dump(vars(args), f, indent=4, ensure_ascii=False)

    logging.basicConfig(
        level=logging.getLevelName(args.log_level),
        format="%(asctime)s %(filename)s %(levelname)s %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(f"{args.output_folder}/localize.log"),
            logging.StreamHandler()
        ]
    )
    
    if args.localize:
        localize(args)
    
    
    if args.merge:
        merge(args)


if __name__ == "__main__":

    start_time = time.time()
    main()
    end_time = time.time()
    logging.info("Total time: {:.4f} min".format((end_time - start_time)/60))
