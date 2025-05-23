import os
import argparse
import glob
from utils import get_table_info, initialize_logger, get_dictionary, get_sqlite_path
from agent import REFORCE
from chat import GPTChat
from prompt import Prompts
import threading, concurrent
from sql import SqlEnv
import time
import json

def execute(question, table_info, args, csv_save_path, log_save_path, sql_save_path, search_directory, format_csv, sql_data):
    db_id = None
    if full_db_id:
        db_id = full_db_id[sql_data]

    # sql
    sql_env = SqlEnv()
    # revote: execute sql if no csv
    if os.path.exists(os.path.join(search_directory, sql_save_path)) and not os.path.exists(os.path.join(search_directory, csv_save_path)) and args.revote:
        with open(os.path.join(search_directory, sql_save_path)) as f:
            sql = f.read()
        sql_env.execute_sql_api(sql, sql_data, os.path.join(search_directory, csv_save_path), sqlite_path=get_sqlite_path(args.db_path, sql_data, db_id, args.task))

    if args.rerun:
        if os.path.exists(os.path.join(search_directory, sql_save_path)):
            return
        else:
            print(f"Rerun: {search_directory}")
    # if log.log exists, pass
    elif os.path.exists(os.path.join(search_directory, log_save_path)):
        return

    # remove files
    self_files = glob.glob(os.path.join(search_directory, f'*{log_save_path}*'))
    for self_file in self_files:
        os.remove(self_file)

    # log
    log_file_path = os.path.join(search_directory, log_save_path)
    logger = initialize_logger(log_file_path)
    if format_csv:
        logger.info("[Answer format]\n" + format_csv + "\n[Answer format]")
    table_struct = table_info[table_info.find("The table structure information is "):]

    # chat
    chat_session_ex = None
    chat_session = None
    if args.do_column_exploration:
        chat_session_ex = GPTChat(args.azure, args.column_exploration_model, temperature=args.temperature)
    if args.generation_model:
        chat_session = GPTChat(args.azure, args.generation_model, temperature=args.temperature)

    # agent
    agent = REFORCE(args.db_path, sql_data, search_directory, prompt_all, sql_env, chat_session_ex, chat_session, sql_data+'/'+log_save_path, db_id, task=args.task)

    # do_column_exploration
    pre_info, response_pre_txt = None, None
    if args.do_column_exploration:
        pre_info, response_pre_txt, max_try = agent.exploration(question, table_struct, table_info, logger)
        if max_try <= 0:
            print(f"{sql_data+'/'+log_save_path} Inadequate preparation, skip")
            return
        print(f"{sql_data+'/'+log_save_path}: chat_session_ex len: {chat_session_ex.get_message_len()}")

    csv_save_path = os.path.join(search_directory, csv_save_path)
    sql_save_path = os.path.join(search_directory, sql_save_path)

    # answer
    if args.do_self_refinement:
        agent.self_refine(args, logger, question, format_csv, table_struct, table_info, response_pre_txt, pre_info, csv_save_path, sql_save_path, task=args.task)
    elif args.generation_model:
        agent.gen(args, logger, question, format_csv, table_struct, table_info, response_pre_txt, pre_info, csv_save_path, sql_save_path, task=args.task)
    if args.generation_model:
        agent.sql_env.close_db()
    

def main(args):
    # Use ThreadPoolExecutor to process each sql_data in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.num_workers) as executor:
        list(executor.map(process_sql_data, dictionaries))

    print("Finished")

def process_sql_data(sql_data):
    start_time = time.time()

    print(sql_data)

    question = task_dict[sql_data]
    search_directory = os.path.join(args.output_path, sql_data)

    # Create agent object
    agent_format = REFORCE(args.db_path, sql_data, search_directory, prompt_all)
    
    # Create the directory if it does not exist
    if not os.path.exists(search_directory):
        os.makedirs(search_directory)

    # Skip processing if results already exist and overwrite is not allowed
    if os.path.exists(agent_format.complete_sql_save_path) and not args.revote:
        return
    
    if args.overwrite_unfinished:
        if not os.path.exists(agent_format.complete_sql_save_path):
            for filename in os.listdir(search_directory):
                filepath = os.path.join(search_directory, filename)
                if os.path.isfile(filepath):
                    os.remove(filepath)
        else:
            return

    # Ensure the search directory exists (in case it was removed)
    if not os.path.exists(search_directory):
        os.makedirs(search_directory)

    # sqlite task
    if args.subtask == "sqlite":
        if not sql_data.startswith("local"):
            return

    # Get BIRD gold res
    if args.task == "BIRD":
        gold_pth = os.path.join(args.BIRD_gold_result_path, sql_data+".csv")
        if not os.path.exists(gold_pth):
            sql_env = SqlEnv()
            res = sql_env.execute_sql_api(full_gold_sql[sql_data], sql_data, gold_pth, sqlite_path=get_sqlite_path(args.db_path, sql_data, full_db_id[sql_data], args.task), timeout=1200)
            assert res == "0", (sql_data, res)

    # Get table information
    table_info = get_table_info(args.db_path, sql_data, agent_format.api, clear_des=True, full_tb_info=full_tb_info)
    if len(table_info) > 300000:
        print(f"Table info len: {len(table_info)}, return")

    if args.do_format_restriction:
        if args.use_gold_format:
            csv_pth = os.path.join("../../spider2-lite/evaluation_suite/gold/exec_result", sql_data+".csv")
            if not os.path.exists(csv_pth):
                csv_pth = csv_pth.replace(".csv", "_a.csv")
            with open(csv_pth) as f:
                format_csv = "```sql\n"+f.read().split("\n")[0]+"\n```"
        else:
            # Initialize sessions at the beginning of each thread
            chat_session_format = GPTChat(args.azure, args.format_model, temperature=args.temperature)
            # Format answer and update the pre-chat session
            format_csv = agent_format.format_answer(question, chat_session_format)
    else:
        format_csv = None

    if args.do_vote:
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
                    question, table_info, args,
                    csv_save_pathi, log_pathi, sql_save_pathi,
                    search_directory, format_csv, sql_data
                )
            )
            threads.append(thread)
            thread.start()

        # wait
        for thread in threads:
            thread.join()
        
        if args.revote:
            print(search_directory)
            if "result.sql" in os.listdir(search_directory):
                print("Revote, remove", os.path.join(search_directory, "result.sql"))
                os.remove(os.path.join(search_directory, "result.sql"))
            if "result.csv" in os.listdir(search_directory):
                print("Revote, remove", os.path.join(search_directory, "result.csv"))
                os.remove(os.path.join(search_directory, "result.csv"))
        if "result.sql" not in os.listdir(search_directory):
            if any(file.endswith('.sql') for file in os.listdir(search_directory) if os.path.isfile(os.path.join(search_directory, file))):
                # After all processes have completed, perform the vote result
                agent_format.vote_result(search_directory, args, sql_paths, table_info, question)
            else:
                print(f"{sql_data}: Empty")
    else:
        # Directly execute the task
        execute(
            question, table_info, args,
            agent_format.csv_save_name, agent_format.log_save_name, agent_format.sql_save_name,
            search_directory, format_csv, sql_data
        )

    print(f"Time for {sql_data}: {int((time.time() - start_time) // 60)} min")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', type=str, default="snow", choices=["snow", "lite", "BIRD"],)
    parser.add_argument('--subtask', type=str, default=None, choices=["sqlite"])
    parser.add_argument('--db_path', type=str, default=None)
    parser.add_argument('--output_path', type=str, default="output/o3-snow-log")

    parser.add_argument('--do_format_restriction', action="store_true")
    parser.add_argument('--use_gold_format', action="store_true")
    parser.add_argument('--format_model', type=str, default="o3")

    parser.add_argument('--do_column_exploration', action="store_true")
    parser.add_argument('--column_exploration_model', type=str, default="o3")    

    parser.add_argument('--do_self_refinement', action="store_true")
    parser.add_argument('--do_self_consistency', action="store_true")
    parser.add_argument('--generation_model', type=str, default=None)
    parser.add_argument('--azure', action="store_true")

    parser.add_argument('--max_iter', type=int, default=5)
    parser.add_argument('--temperature', type=float, default=1)
    parser.add_argument('--early_stop', action="store_true")

    parser.add_argument('--do_vote', action="store_true")
    parser.add_argument('--revote', action="store_true")
    parser.add_argument('--num_votes', type=int, default=3)
    parser.add_argument('--random_vote_for_tie', action="store_true")
    parser.add_argument('--model_vote', type=str, default=None)
    parser.add_argument('--final_choose', action="store_true")

    parser.add_argument('--save_all_results', action="store_true")
    parser.add_argument('--rerun', action="store_true")
    parser.add_argument('--overwrite_unfinished', action="store_true")
    parser.add_argument('--num_workers', type=int, default=16)

    parser.add_argument('--omnisql_format_pth', type=str, default=None)
    parser.add_argument('--BIRD_gold_result_path', type=str, default="../../data/BIRD/gold_result")
    args = parser.parse_args()
    prompt_all = Prompts()

    full_db_id = {}
    full_tb_info = {}
    full_gold_sql = {}
    if args.omnisql_format_pth:
        if args.subtask == "sqlite":
            with open(args.omnisql_format_pth) as f:
                data = json.load(f)
            dictionaries = []
            task_dict = {}
            full_tb_info = {}
            
            for example in data:
                if example["instance_id"].startswith("local"):
                    dictionaries.append(example["instance_id"])
                    task_dict[example["instance_id"]] = example["question"]
                    full_tb_info[example["instance_id"]] = example["db_desc"]
                    full_db_id[example["instance_id"]] = example["db_id"]
        elif args.task == "BIRD":
            with open(args.omnisql_format_pth) as f:
                data = json.load(f)
            dictionaries = []
            task_dict = {}
            full_tb_info = {}
            
            for example in data:
                q_id = example["question_id"]
                instance_id = f"local_BIRD_{q_id:04d}"
                dictionaries.append(instance_id)
                task_dict[instance_id] = example["question"]
                full_tb_info[instance_id] = example["input_seq"]
                full_db_id[instance_id] = example["db_id"]     
                full_gold_sql[instance_id] = example["SQL"]                     
    else:
        dictionaries, task_dict = get_dictionary(args.db_path, args.task)
    main(args)