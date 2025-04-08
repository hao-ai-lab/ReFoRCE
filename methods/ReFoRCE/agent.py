from utils import hard_cut, get_values_from_table, search_file, get_api_name, get_table_info, compare_pandas_table, extract_between, get_sqlite_path
from sql import SqlEnv
from reconstruct_data import remove_digits, compress_ddl
import pandas as pd
from io import StringIO
import os
import ast
import csv
from prompt import Prompts
from typing import Type
from tqdm import tqdm
from chat import GPTChat
csv.field_size_limit(500000)

class REFORCE:
    def __init__(self, args, sql_data, search_directory, prompt_class: Type[Prompts], sql_env: Type[SqlEnv]=None, chat_session_pre: Type[GPTChat]=None, chat_session: Type[GPTChat]=None, log_save_path=None):
        self.csv_save_name = "result.csv"
        self.sql_save_name = "result.sql"
        self.log_save_name = "log.log"
        self.log_vote_name = "vote.log"
        self.empty_result = "No data found for the specified query.\n"

        self.api = get_api_name(sql_data)
        self.sqlite_path = get_sqlite_path(args, sql_data)

        self.sql_id = log_save_path

        self.complete_csv_save_path = os.path.join(search_directory, self.csv_save_name)
        self.complete_sql_save_path = os.path.join(search_directory, self.sql_save_name)
        self.complete_log_save_path = os.path.join(search_directory, self.log_save_name)
        self.complete_vote_log_path = os.path.join(search_directory, self.log_vote_name)

        self.prompt_class = prompt_class
        self.max_try = 3
        self.csv_max_len = 500

        self.sql_env = sql_env
        self.chat_session_pre = chat_session_pre
        self.chat_session = chat_session


    def execute_sqls(self, sqls, logger):
        result_dic_list = []
        error_rec = []
        while sqls:
            result_dic = {}
            sql = sqls[0]
            sqls = sqls[1:]
            logger.info("[Try to execute]\n" + sql + "\n[Try to execute]")
            results = self.sql_env.execute_sql_api(sql, self.sql_id, api=self.api, max_len=self.csv_max_len, sqlite_path=self.sqlite_path)

            if isinstance(results, str) and results != self.empty_result:
                result_dic['sql'] = sql
                result_dic['res'] = results
                self.chat_session_pre.messages.append({"role": "user", "content": f"Successfully executed. SQL:\n{sql}\nResults:\n{results}"})
                logger.info("[Successfully executed]\n" + self.chat_session_pre.messages[-1]['content'] + "\n[Successfully executed]")
                result_dic_list.append(result_dic)
            else:
                logger.info("[Error occurred]\n" + str(results) + "\n[Error occurred]")
                max_try = self.max_try
                simplify = False
                corrected_sql = None
                while not isinstance(results, str) or results == self.empty_result:
                    error_rec.append(0)
                    if max_try == 0:
                        break
                    if results == self.empty_result:
                        simplify = True
                    corrected_sql = self.self_correct(sql, results, logger, simplify=simplify)
                    if not isinstance(corrected_sql, list) or len(corrected_sql) < 1:
                        print(f"{self.sql_id}: Not a valid SQL: {corrected_sql}")
                        continue
                    corrected_sql = max(corrected_sql, key=len)
                    results = self.sql_env.execute_sql_api(corrected_sql, self.sql_id, api=self.api, max_len=self.csv_max_len, sqlite_path=self.sqlite_path)
                    logger.info("[Results for corrected sql]\n"+str(results)+"\n[Results for corrected sql]")
                    max_try -= 1
                    simplify = False

                if isinstance(results, str) and results != self.empty_result:
                    error_rec.append(1)
                    if sqls != []:
                        response = self.chat_session_pre.get_model_response(f"```sql\n{sql}``` is corrected to ```sql\n{corrected_sql}```. Please correct other sqls if they have similar errors. SQLs: {sqls}. For each SQL, answer in ```sql``` format.\n", "sql")

                        if isinstance(response, list) and response != []:
                            response_sqls = []
                            for s in response:
                                try:
                                    queries = [query.strip() for query in s.strip().split(';') if query.strip()]
                                    response_sqls += queries
                                except:
                                    pass
                            if len(response_sqls) >= len(sqls) // 2:
                                sqls = response_sqls
                                logger.info("[Corrected other sqls]\n"+self.chat_session_pre.messages[-1]['content']+"\n[Corrected other sqls]")
                else:
                    error_rec.append(0)
                    # Many times error, return
                    if len(error_rec) > 5 and sum(error_rec[-5:]) == 0:
                        return result_dic_list
                    continue
                if not corrected_sql:
                    continue
                result_dic['sql'] = corrected_sql
                result_dic['res'] = results
                self.chat_session_pre.messages.append({"role": "user", "content": f"Successfully corrected. SQL:\n{corrected_sql}\nResults:\n{results}"})
                logger.info("[Successfully corrected]\n" + self.chat_session_pre.messages[-1]['content'] + "\n[Successfully corrected]")
        return result_dic_list

    def self_correct(self, sql, error, logger, simplify=False):
        prompt = f"Input sql:\n{sql}\nThe error information is:\n" + str(error) + "\nPlease correct it based on previous context and output the thinking process with only one sql query in ```sql``` format. Don't just analyze without SQL or output several SQLs.\n"
        if simplify:
            prompt += "Since the output is empty, please simplify some conditions of the past sql.\n"
        response = self.chat_session_pre.get_model_response(prompt, "sql")

        max_try = self.max_try
        while max_try > 0 and (not isinstance(response, str) or len(response) > 1):
            response = self.chat_session_pre.get_model_response("Please generate only one SQL with thinking process.", "sql")
            max_try -= 1
        logger.info("[Corrected SQL]\n" + self.chat_session_pre.messages[-1]['content'] + "\n[Corrected SQL]")
        return response

    def format_answer(self, task, chat_session: Type[GPTChat]):
        format_prompt = self.prompt_class.get_format_prompt()
        response_csv = chat_session.get_model_response_txt("Task: " + task + format_prompt)
        return response_csv, chat_session

    def exploration(self, task, table_struct, table_info, logger):
        pre_info = ''
        task = table_info + "\nTask: " + task + "\n"
        max_try = self.max_try
        while max_try > 0:
            exploration_prompt = task + self.prompt_class.get_exploration_prompt(self.api, table_struct)

            response_pre = self.chat_session_pre.get_model_response(exploration_prompt, "sql")
            response_pre_txt = self.chat_session_pre.messages[-1]['content']
            logger.info("[Exploration]\n" + response_pre_txt + "\n[Exploration]")
            if not isinstance(response_pre, list):
                max_try -= 1
                continue
            
            if len(response_pre) == 1:
                response_pre = [query.strip() for query in response_pre[0].strip().split(';') if query.strip()]
            if len(response_pre) < 10:
                max_try -= 1
                print(f"{self.sql_id}: Few sqls, retry preparation.")
                continue
            results_pre_dic_list = self.execute_sqls(response_pre, logger)
            sql_count = 0
            for dic in results_pre_dic_list:
                pre_info += "Query:\n" + dic['sql'] + "\nAnswer:\n" + str(dic['res'])
                if isinstance(dic['res'], str):
                    sql_count += 1

            if sql_count < len(response_pre) // 2:
                print(f"{self.sql_id}: sql_count: {sql_count}, len(response_pre): {len(response_pre)}. Inadequate preparation, break.")
                max_try = 0
                break

            if len(pre_info) < 1e5:
                break
            print(f"{self.sql_id}: Too long, retry preparation.")
            pre_info = ''
            max_try -= 1

        return pre_info, response_pre_txt, max_try

    def self_refine(self, args, logger, task, format_csv, table_struct, table_info, response_pre_txt, pre_info, csv_save_path, sql_save_path):
        itercount = 0
        results_values = []
        results_tables = []

        self_refine_prompt = self.prompt_class.get_self_refine_prompt(table_info, response_pre_txt, pre_info, task, self.api, format_csv, table_struct)

        error_rec = []
        while itercount < args.max_iter:
            logger.info(f"itercount: {itercount}")
            logger.info("[Self-refine]\n" + self_refine_prompt + "\n[Self-refine]")
            
            max_try = self.max_try
            while max_try > 0:
                response = self.chat_session.get_model_response(self_refine_prompt, "sql")
                if not isinstance(response, list) or len(response) != 1:
                    self_refine_prompt = "Please output one SQL only."
                else:
                    break
                max_try -= 1
            if not isinstance(response, list) or response == []:
                if os.path.exists(csv_save_path):
                    os.remove(csv_save_path)
                print(f"{self.sql_id}: Error when generating final SQL.")
                break
            logger.info("[Try to run SQL in self-refine]\n" +self. chat_session.messages[-1]['content'] + "\n[Try to run SQL in self-refine]")
            response = response[0]
            executed_result = self.sql_env.execute_sql_api(response, self.sql_id, csv_save_path, api=self.api, sqlite_path=self.sqlite_path)
            error_rec.append(executed_result)
            if len(error_rec) > 3:
                # Eraly stop for repeatitive empty results
                if len(set(error_rec[-4:])) == 1 and error_rec[-1] == self.empty_result:
                    logger.info("No data found for the specified query, remove file.")                    
                    if os.path.exists(csv_save_path):
                        os.remove(csv_save_path)
                    break
            
            if executed_result == 0:
                self_consistency_prompt = self.prompt_class.get_self_consistency_prompt(task, format_csv)
                with open(csv_save_path) as f:
                    csv_data = f.readlines()
                    csv_data_str = ''.join(csv_data)
                logger.info(f"[Executed results in self-refine]\n{hard_cut(csv_data_str, self.csv_max_len)}\n[Executed results in self-refine]")
                self_consistency_prompt += "Current snswer: \n" + hard_cut(csv_data_str, self.csv_max_len)
                self_consistency_prompt += f"Current sql:\n{response}"
                if '"""' in csv_data_str:
                    self_consistency_prompt += 'Please remove """ in results. Use CAST: CAST(column_name AS STRING).\n'

                # Filter results with null columns
                csv_buffer = StringIO(csv_data_str)
                df_csv = pd.read_csv(csv_buffer).fillna("")

                nested_val = [(item) for i, row in enumerate(df_csv.values.tolist()) for j, item in enumerate(row) if isinstance(item, str) and '\n' in item in item]
                df_csv_copy = df_csv.copy()
                for col in df_csv.select_dtypes(include=['float']):
                    df_csv_copy[col] = df_csv[col].round(2)
                sort_col = df_csv_copy.columns[0]
                df_csv_copy_sorted = df_csv_copy[sort_col].astype(str)
                csv_data_str_round2 = df_csv_copy_sorted.to_string()
                df_csv_str = df_csv.astype(str)
                if get_values_from_table(csv_data_str_round2) not in results_values:
                    if nested_val:
                        self_consistency_prompt += f"Values {nested_val} are nested. Please correct them. e.g. Transfer '[\nA,\n B\n]' to 'A, B'.\n"
                    elif not ((df_csv_str == "0") | (df_csv_str == "")).all().any():
                            results_values.append(get_values_from_table(csv_data_str_round2))
                            results_tables.append(csv_data_str)
                    else:
                        empty_columns = df_csv_str.columns[((df_csv_str == "0") | (df_csv_str == "")).all()].to_list()
                        self_consistency_prompt += f"Empty results in Column {empty_columns}. Please correct them.\n"
                else:
                    # self-consistency
                    logger.info(f"[Consistent results]\n{hard_cut(csv_data_str, 500)}\n[Consistent results]")
                    with open(sql_save_path, "w") as f:
                        f.write(response)
                    break
                
                if any(keyword in response for keyword in self.prompt_class.get_condition_onmit_tables()):
                    self_consistency_prompt += self.prompt_class.get_prompt_dialect_list_all_tables(table_struct, self.api)
                if args.save_all_results:
                    save_path = save_path[:-4] + str(itercount) + save_path[-4:]
                self_refine_prompt = self_consistency_prompt
            
            elif not isinstance(executed_result, str) or executed_result == self.empty_result:
                self_refine_prompt = f"Input sql:\n{response}\nThe error information is:\n" + str(executed_result) + "\nPlease correct it and output only 1 complete SQL query."

            else:
                print(str(executed_result))
                break
            itercount += 1

        logger.info(f"Total iteration counts: {itercount}")
        if itercount == args.max_iter and not args.save_all_results:
            if os.path.exists(csv_save_path):
                os.remove(csv_save_path)
            logger.info("Max Iter, remove file")
        print(f"{self.sql_id}: chat_session len: {self.chat_session.get_message_len()}")

    
    def vote_result(self, search_directory, task, chat_session: Type[GPTChat], sql_paths, table_info):
        

        pre_info = f'Based on database info:\n{table_info}'
        prompt = f"The task is: {task}. Here are some candidate sqls and answers: \n"
        count = 0

        # filter answer
        result = {}
        all_values = []
        for v in sql_paths.values():
            if os.path.exists(os.path.join(search_directory, v)):
                all_values.append(os.path.join(search_directory, v))
        if len(all_values) > 1:
            for key, value in sql_paths.items():
                complete_value = os.path.join(search_directory, value)
                if os.path.exists(complete_value):
                    if any(v != complete_value and compare_pandas_table(pd.read_csv(v), pd.read_csv(complete_value), ignore_order=True) for v in all_values):
                        result[key] = value
        if result:
            sql_paths = result


        for sql, csv in sql_paths.items():
            sql_path = os.path.join(search_directory, sql)
            csv_path = os.path.join(search_directory, csv)
            logfile_path = os.path.join(search_directory, csv[0] + self.log_save_name)
            try:
                pre_info += extract_between(logfile_path, "Begin Exploring Related Columns\n", "End Exploring Related Columns\n")[0]
            except Exception as e:
                print([logfile_path, e])
            if os.path.exists(sql_path) and os.path.exists(csv_path):
                sql_path_exist = sql_path
                csv_path_exist = csv_path
                count += 1
                prompt += sql + "\n"
                with open(sql_path) as f:
                    prompt += f.read()
                prompt += csv + "\n"
                with open(csv_path) as f:
                    prompt += hard_cut(f.read(), 5000)

        if count == 0:
            print(f"{logfile_path} Empty")
            return
        elif count == 1:
            os.rename(sql_path_exist, self.complete_sql_save_path)
            os.rename(csv_path_exist, self.complete_csv_save_path)
        else:
            max_try = 3
            prompt += "Compare the SQL and results of each answer and choose one SQL as the correct answer and tell me the reason. Output the name of sql in ```plaintext\nxxx.sql``` format. You should not ingnore 'plaintext'.\n"
            response = chat_session.get_model_response(hard_cut(pre_info, 150000) + prompt, "plaintext")
            while max_try > 0:
                if not response or not isinstance(response, list) or ".sql" not in response[0]:
                    print(logfile_path, response)
                    chat_session.get_model_response("Please output the name of sql in ```plaintext\nxxx.sql``` format. You should not ingnore 'plaintext'.", "plaintext")
                else:
                    break
                max_try -= 1
            if max_try == 0:
                print(f"{logfile_path} Empty")
                return
            with open(os.path.join(search_directory, response[0].strip())) as f:
                selected_sql = f.read()
            sql_env = SqlEnv()
            if sql_env.execute_sql_api(selected_sql, self.sql_id, self.complete_csv_save_path, api=self.api, sqlite_path=self.sqlite_path) == 0:
                with open(self.complete_sql_save_path, "w") as f:
                    f.write(selected_sql)
                with open(self.complete_vote_log_path, "w") as f:
                    f.write(chat_session.messages[-1]['content'])
            sql_env.close_db()

def schema_linking(dictionaries, task_dict, example_path, chat_session_sl: Type[GPTChat], txt_len_threshold=100000):
    print("Doing schema linking")
    skip_flag = False
    for eg_id in tqdm(dictionaries):
        # if eg_id in ["sf_bq287"]:
        #     skip_flag = False
        chat_session_sl.init_messages()
        api = get_api_name(eg_id)
        task = task_dict[eg_id]
        table_info = get_table_info(example_path, eg_id, api, clear_des=True)
        print(f"Doing schema linking for {eg_id}, table len: {len(table_info)}")
        if len(table_info) < txt_len_threshold or skip_flag or len(table_info) > 400000:
            print(f"Skip, len: {len(table_info)}")
            continue
        
        table_struct = table_info[table_info.find("The table structure information is "):]

        prompt = f"Table information: {table_info}\nTask: {task}\nConsider which tables are related to the task. Remove unnecessary tables in {table_struct} and answer table names in ```python``` format in a list.\n"
        
        max_iter = 3
        while max_iter > 0:
            chat_session_sl.init_messages()
            e = None
            table_struct_response = chat_session_sl.get_model_response(prompt, "python")
            try:
                table_names = ast.literal_eval(table_struct_response[0])
                table_names = [name.split('.')[-1] for name in table_names]
                table_names_no_digit = [remove_digits(s) for s in table_names]
            except Exception as e:
                print(str(table_struct_response))
                continue
            if table_names_no_digit != []:
                break
            max_iter -= 1
        if e is not None or max_iter <= 0:
            print([max_iter, e])
            continue
        ddl_paths = search_file(os.path.join(example_path, eg_id), "DDL.csv")
        
        for ddl_path in ddl_paths:
            temp_file = ddl_path.replace("DDL.csv", "DDL_sl.csv")
            with open(ddl_path, "r", newline="", encoding="utf-8", errors="ignore") as infile, \
                open(temp_file, "w", newline="", encoding="utf-8", errors="ignore") as outfile:
                
                reader = csv.reader(infile)
                writer = csv.writer(outfile)

                header = next(reader)
                writer.writerow(header)
                row_count = 0
                row_count_rm = 0
                total_count = 0
                row_list_all = []
                row_list = []
                for row in reader:
                    if any(remove_digits(row[0]) in item for item in table_names_no_digit):
                        row_count_rm += 1
                        row_list_all.append(row)
                    if any(row[0] in item for item in table_names):
                        row_count += 1
                        row_list.append(row)
                    total_count += 1
                print(f"{eg_id}: tables before linking: {total_count}, tables after linking: {row_count}, tables rm digits after linking: {row_count_rm}")
                if row_count_rm > 500:
                    print(f"row_count_rm > 500: {eg_id}, row_count: {row_count}")
                    writer.writerows(row_list)
                elif row_count < 10:
                    # print(f"row_count < 10: {eg_id}")
                    writer.writerows(row_list)
                else:
                    writer.writerows(row_list_all)

    compress_ddl(example_path, add_description=True, add_sample_rows=True, rm_digits=True, schema_linked=True)