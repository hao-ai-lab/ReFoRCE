from utils import search_file, get_api_name, get_dictionary, get_tb_info, get_external, compute_precision_recall, is_csv_empty, clear_name
from reconstruct_data import remove_digits, compress_ddl
import os
import json
import csv
from tqdm import tqdm
from chat import GPTChat
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import sys
import re
import numpy as np
csv.field_size_limit(sys.maxsize)
THRESHOLD = 200000
DEPS_DEV_V1 = ["sf_bq016", "sf_bq062", "sf_bq063", "sf_bq028"]

def reduce_columns(sql: str, subset_columns: set[str]) -> str:

    table_match = re.search(r'create\s+(?:or\s+replace\s+)?table\s+`?([^\s(]+)`?', sql, re.IGNORECASE)
    assert table_match, sql
    table_name = table_match.group(1)

    columns_block_match = re.search(r'\((.*?)\)\s*(PARTITION|CLUSTER|OPTIONS|;|$)', sql, re.DOTALL | re.IGNORECASE)
    if not columns_block_match:
        raise ValueError("Cannot extract columns block.")
    columns_block = columns_block_match.group(1)

    lines = columns_block.splitlines()
    filtered_lines = []
    for line in lines:
        line = line.strip().rstrip(',')
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        col_name = parts[0].strip('`",')
        if col_name in subset_columns:
            filtered_lines.append(f"  {line},")

    if filtered_lines:
        filtered_lines[-1] = filtered_lines[-1].rstrip(',')

    new_sql = f'CREATE TABLE {table_name} (\n' + '\n'.join(filtered_lines) + '\n);'
    return new_sql


def reduce_ddl(example_path, dictionaries, linked_json, reduce_col=False):
    print("Doing schema linking")
    for eg_id in tqdm(dictionaries):
        api = get_api_name(eg_id)
 
        ddl_paths = search_file(os.path.join(example_path, eg_id), "DDL.csv")

        if os.path.getsize(os.path.join(example_path, eg_id, "prompts.txt")) < THRESHOLD or eg_id in DEPS_DEV_V1:
            continue

        with open(linked_json) as f:
            sl = json.load(f)

        table_names = []
        columns = {}
        for ex_id, tbs in sl.items():
            if ex_id == eg_id:
                for tb in tbs:
                    if "answer" in tb:
                        if tb["answer"] == "Y":
                            table_names.append(tb["table name"])
                            columns[tb["table name"]] = tb['columns']
                    else:
                        raise NotImplementedError
                        print(tb)
                        table_names.append(tb)

        if not table_names:
            print("Empty result in table_names", eg_id)
            continue
        print("Doing sl for", eg_id)
        table_names_no_digit = [remove_digits(i) for i in table_names]

        temp_file_paths = []
        for ddl_path in ddl_paths:
            temp_file = ddl_path.replace("DDL.csv", "DDL_sl.csv")
            temp_file_paths.append(temp_file)
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
                    assert row[-1].upper().startswith("CREATE"), row
                    if "." in row[0]:
                        row[0] = row[0].split(".")[-1]

                    json_pth = ddl_path.replace("DDL.csv", row[0].strip()+".json")
                    if os.path.exists(json_pth):
                        with open(json_pth) as f:
                            table_fullname = json.load(f)["table_fullname"]
                    else:
                        print(f"{ex_id}: {json_pth} doesn't exist")
                        continue
                    
                    if any(remove_digits(table_fullname) in item for item in table_names_no_digit):
                        row_count_rm += 1
                        row_list_all.append(row)

                    if any(table_fullname == item for item in table_names):

                        row_count += 1

                        if reduce_col:
                            assert table_fullname in columns, print(table_names, table_fullname)
                            row[-1] = reduce_columns(row[-1], columns[table_fullname])
                            # print("After", row)
                        row_list.append(row)
                    total_count += 1
                print(f"{eg_id}: tables before linking: {total_count}, tables after linking: {row_count}, tables rm digits after linking: {row_count_rm}")
                if 0 < row_count < 10 or row_count_rm > 1000 or reduce_col:
                    writer.writerows(row_list)
                elif row_count_rm:
                    print("RM digits", len(row_list))
                    writer.writerows(row_list_all)
        if all(is_csv_empty(i) for i in temp_file_paths):
            print(f"{eg_id}: All empty DDL_sl.csv, remove, table_names", table_names)
            for i in temp_file_paths:
                os.remove(i)
    compress_ddl(example_path, add_description=True, add_sample_rows=True, rm_digits=True, schema_linked=True, clear_long_eg_des=True, reduce_col=reduce_col)

ask_prompt = """
You are doing table level schema linking. Given a table with schema information and the task, you should think step by step and decide whether this table is related to the task. 
You should answer Y/N only. If the answer is Y, you should add columns that you think is related in python list format.

Please answer only in json code block like:
```json
{{
    "think": "think step by step to decide",
    "answer": "Y or N only",
    "columns": [col_name1, col_name2]
}}
```

Table info: {0}
Task: {1}
{2}
"""

def ask_model_sl(example_path, json_save_pth):
    linked_dic = {}

    def process_example(ex_id):
        if ex_id.startswith("local"):
            return None, None
        tb_info_pth = search_file(os.path.join(example_path, ex_id), "prompts.txt")
        assert len(tb_info_pth) == 1
        with open(tb_info_pth[0]) as f:
            tb_info = f.read()
        task = task_dict[ex_id]
        chat_session = GPTChat(azure=True, model="gpt-4o-rag-research", temperature=0)
        result = ask_model_sl_(tb_info, task, chat_session)
        return ex_id, result

    linked_dic = {}
    print("Doing table-level schema linking")
    with ThreadPoolExecutor(max_workers=32) as executor:
        futures = [executor.submit(process_example, ex_id) for ex_id in dictionaries]
        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing"):
            ex_id, result = future.result()
            if ex_id is not None:
                linked_dic[ex_id] = result

        with open(json_save_pth, "w") as f:
            json.dump(linked_dic, f, indent=4)

def ask_model_sl_(tb_info, task, chat_session):
    tbs = get_tb_info(tb_info)
    external = get_external(tb_info)
    linked = []

    for tb in tbs:
        chat_session.init_messages()
        max_try = 3
        input = ask_prompt.format(tb, task, external)
        while max_try:
            response = chat_session.get_model_response(input, "json")
            if len(response) == 1:
                response = response[0]
                try:
                    data = json.loads(response)
                    assert data["answer"] in ["Y", "N"], 'data["answer"] should be in ["Y", "N"]'
                    data["table name"] = re.search(r'^Table full name:\s*(.+)$', tb, re.MULTILINE).group(1)
                    break
                except Exception as e:
                    input = e+"Please generate again."
            max_try -= 1
        if max_try == 0:
            print("Failed", re.search(r'^Table full name:\s*(.+)$', tb, re.MULTILINE).group(1))
            continue
        # print(data)
        linked.append(data)

    return linked

def compute_metrics_sl(file_pth, db_path):
    with open(file_pth) as f:
        data = json.load(f)
    count = 0
    precision_all = []
    recall_all = []
    for example, tbs in data.items():
        for ex in gold:
            if ex['instance_id'] == example:
                gold_table = set(ex["gold_tables"])    

        if os.path.getsize(os.path.join(db_path, example, "prompts.txt")) > THRESHOLD:
            count += 1
            pred = []
            
            for tb in tbs:
                if "answer" in tb:
                    if tb["answer"] == "Y":
                        pred.append(tb["table name"])
                else:
                    print(tb)
                    pred.append(tb)
            precision, recall = compute_precision_recall(clear_name(pred), clear_name(gold_table))
            print(f"Res: {precision}, {recall}, {example}")

            if precision != 0 and recall != 0:
                if recall < 1:
                    # print(f"Failed: {precision}, {recall}, {pred}, {gold_table}, {example}")
                    print(f"Failed: {precision}, {recall}, {example}")
                precision_all.append(precision)
                recall_all.append(recall)
        
    print(f"Count: {count}, mean recall: {np.mean(recall_all)}, mean precision: {np.mean(precision_all)}, num recall < 1: {np.sum(np.array(recall_all) < 1)}")  

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', type=str, default="lite")
    parser.add_argument('--db_path', type=str, default="examples_lite_full")
    parser.add_argument('--linked_json_pth', type=str, default=None)
    parser.add_argument('--reduce_col', action="store_true")
    parser.add_argument('--gold_tb_pth', type=str, default=None)
    args = parser.parse_args()

    dictionaries, task_dict = get_dictionary(args.db_path, args.task)
    if args.linked_json_pth is not None and not os.path.exists(args.linked_json_pth):
        gold_tb = args.gold_tb_pth
        with open(gold_tb) as f:
            gold = [json.loads(i) for i in f]

        ask_model_sl(args.db_path, args.linked_json_pth)

        compute_metrics_sl(args.linked_json_pth, args.db_path)
    reduce_ddl(args.db_path, dictionaries, args.linked_json_pth, args.reduce_col)