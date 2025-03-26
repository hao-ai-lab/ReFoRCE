import os
import argparse
import glob
from utils import get_table_info, initialize_logger, get_dictionary
from agent import REFORCE, schema_linking
from chat import GPTChat
from prompt import Prompts
import threading, concurrent
from sql import SqlEnv
import time

def execute(task, table_info, args, csv_save_path, log_save_path, sql_save_path, search_directory, format_csv, sql_data):
    if args.rerun:
        if os.path.exists(os.path.join(search_directory, sql_save_path)):
            return
        else:
            print(f"Rerun: {search_directory}")
    # if log.log exists, pass
    elif os.path.exists(os.path.join(search_directory, sql_save_path)):
        return

    # remove files
    self_files = glob.glob(os.path.join(search_directory, f'*{log_save_path}*'))
    for self_file in self_files:
        os.remove(self_file)

    # log
    log_file_path = os.path.join(search_directory, log_save_path)
    logger = initialize_logger(log_file_path)
    logger.info("[Answer format]\n" + format_csv + "\n[Answer format]")
    table_struct = table_info[table_info.find("The table structure information is "):]

    # sql
    sql_env = SqlEnv()

    # chat
    if args.model:
        chat_session_pre = GPTChat(args.azure, args.pre_model, temperature=args.temperature)
        chat_session = GPTChat(args.azure, args.pre_model, temperature=args.temperature)

    # agent
    agent = REFORCE(args, sql_data, search_directory, prompt_all, sql_env, chat_session_pre, chat_session, sql_data+'/'+log_save_path)

    # preparation
    pre_info, response_pre_txt, max_try = agent.exploration(task, table_struct, table_info, logger)
    if max_try <= 0:
        print(f"{sql_data+'/'+log_save_path} Inadequate preparation, skip")
        return
    print(f"{sql_data+'/'+log_save_path}: chat_session_pre len: {chat_session_pre.get_message_len()}")
    csv_save_path = os.path.join(search_directory, csv_save_path)
    sql_save_path = os.path.join(search_directory, sql_save_path)

    # answer
    agent.self_refine(args, logger, task, format_csv, table_struct, table_info, response_pre_txt, pre_info, csv_save_path, sql_save_path)
    agent.sql_env.close_db()
    

def main(args):

    if args.schema_linking_model:
        chat_session_sl = GPTChat(args.azure, args.schema_linking_model, temperature=args.temperature) 
        schema_linking(dictionaries, task_dict, args.db_path, chat_session_sl)
        if args.schema_linking_only:
            return
    # Use ThreadPoolExecutor to process each sql_data in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.num_workers) as executor:
        list(executor.map(process_sql_data, dictionaries))

    print("Finished")

def process_sql_data(sql_data):
    start_time = time.time()
    # Initialize sessions at the beginning of each thread
    if args.model:
        chat_session_format = GPTChat(args.azure, args.pre_model, temperature=args.temperature)
    print(sql_data)

    task = task_dict[sql_data]
    search_directory = os.path.join(args.output_path, sql_data)

    # Create agent object
    agent_format = REFORCE(args, sql_data, search_directory, prompt_all)
    
    # Create the directory if it does not exist
    if not os.path.exists(search_directory):
        os.makedirs(search_directory)

    # Skip processing if results already exist and overwrite is not allowed
    if os.path.exists(agent_format.complete_sql_save_path):
        return

    # Ensure the search directory exists (in case it was removed)
    if not os.path.exists(search_directory):
        os.makedirs(search_directory)

    # Get table information
    table_info = get_table_info(args.db_path, sql_data, agent_format.api, clear_des=True)

    # Format answer and update the pre-chat session
    format_csv, chat_session_format = agent_format.format_answer(task, chat_session_format)

    # Skip task if the context is too long
    if chat_session_format.get_message_len() > 200000:
        print(f"{sql_data} Too long context, skip")
        return

    if args.model_vote:
        num_votes = args.num_votes
        sql_paths = {}
        threads = []

        for i in range(num_votes):
            csv_save_pathi = str(i) + agent_format.csv_save_name
            log_pathi = str(i) + agent_format.log_save_name
            sql_save_pathi = str(i) + agent_format.sql_save_name
            sql_paths[sql_save_pathi] = csv_save_pathi

            thread = threading.Thread(
                target=execute,
                args=(
                    task, table_info, args,
                    csv_save_pathi, log_pathi, sql_save_pathi,
                    search_directory, format_csv, sql_data
                )
            )
            threads.append(thread)
            thread.start()

        # wait
        for thread in threads:
            thread.join()
        
        if "result.sql" not in os.listdir(search_directory):
            if any(file.endswith('.sql') for file in os.listdir(search_directory) if os.path.isfile(os.path.join(search_directory, file))):
                # After all processes have completed, perform the vote result
                agent_format.vote_result(search_directory, task, chat_session_format, sql_paths, table_info)
            else:
                print(f"{sql_data}: Empty")
    else:
        # Directly execute the task
        execute(
            task, table_info, args,
            agent_format.csv_save_name, agent_format.log_save_name, agent_format.sql_save_name,
            search_directory, format_csv, sql_data
        )

    print(f"Time for {sql_data}: {int((time.time() - start_time) // 60)} min")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', type=str, default="snow")
    parser.add_argument('--db_path', type=str, default="examples")
    parser.add_argument('--output_path', type=str, default="output/o1-preview-snow-log")
    parser.add_argument('--model', type=str, default="o1-preview")
    parser.add_argument('--pre_model', type=str, default="o1-preview")
    parser.add_argument('--azure', action="store_true")
    parser.add_argument('--schema_linking_model', type=str, default=None)
    parser.add_argument('--schema_linking_only', action="store_true")
    parser.add_argument('--max_iter', type=int, default=5)
    parser.add_argument('--temperature', type=float, default=1)
    parser.add_argument('--model_vote', action="store_true")
    parser.add_argument('--num_votes', type=int, default=3)
    parser.add_argument('--save_all_results', action="store_true")
    parser.add_argument('--rerun', action="store_true")
    parser.add_argument('--num_workers', type=int, default=16)
    args = parser.parse_args()
    prompt_all = Prompts()
    dictionaries, task_dict = get_dictionary(args)
    main(args)