import re
import os
import json
import math
import pandas as pd
import argparse
from io import StringIO
import csv
from tqdm import tqdm
from sql import SqlEnv
from utils import get_api_name, get_db_id, get_sqlite_path
import sys
csv.field_size_limit(sys.maxsize)

def load_jsonl_to_dict(jsonl_file):
    data_dict = {}
    with open(jsonl_file, 'r') as file:
        for line in file:
            item = json.loads(line.strip())
            instance_id = item['instance_id']
            data_dict[instance_id] = item
    return data_dict

def load_json_list_to_dict(json_file_path):
    with open(json_file_path, 'r', encoding='utf-8') as file:
        data_list = json.load(file)
    data_dict = {item['instance_id']: item for item in data_list}
    return data_dict

def compare_multi_pandas_table(pred, multi_gold, multi_condition_cols=[], multi_ignore_order=False):
    if multi_condition_cols == [] or multi_condition_cols == [[]] or multi_condition_cols == [None] or multi_condition_cols == None:
        multi_condition_cols = [[] for _ in range(len(multi_gold))]
    elif len(multi_gold) > 1 and not all(isinstance(sublist, list) for sublist in multi_condition_cols):
        multi_condition_cols = [multi_condition_cols for _ in range(len(multi_gold))]
    multi_ignore_order = [multi_ignore_order for _ in range(len(multi_gold))]

    for i, gold in enumerate(multi_gold):
        if compare_pandas_table(pred, gold, multi_condition_cols[i], multi_ignore_order[i]):
            return 1
    return 0

def compare_pandas_table(pred, gold, condition_cols=[], ignore_order=False):
    """_summary_

    Args:
        pred (Dataframe): _description_
        gold (Dataframe): _description_
        condition_cols (list, optional): _description_. Defaults to [].
        ignore_order (bool, optional): _description_. Defaults to False.

    """
    # print('condition_cols', condition_cols)
    
    tolerance = 1e-2

    def vectors_match(v1, v2, tol=tolerance, ignore_order_=False):
        if ignore_order_:
            v1, v2 = (sorted(v1, key=lambda x: (x is None, str(x), isinstance(x, (int, float)))),
                    sorted(v2, key=lambda x: (x is None, str(x), isinstance(x, (int, float)))))
        if len(v1) != len(v2):
            return False
        for a, b in zip(v1, v2):
            if pd.isna(a) and pd.isna(b):
                continue
            elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if not math.isclose(float(a), float(b), abs_tol=tol):
                    return False
            elif a != b:
                return False
        return True
    
    if condition_cols != []:
        gold_cols = gold.iloc[:, condition_cols]
    else:
        gold_cols = gold
    pred_cols = pred

    t_gold_list = gold_cols.transpose().values.tolist()
    t_pred_list = pred_cols.transpose().values.tolist()
    score = 1
    for _, gold in enumerate(t_gold_list):
        if not any(vectors_match(gold, pred, ignore_order_=ignore_order) for pred in t_pred_list):
            score = 0
        else:
            for j, pred in enumerate(t_pred_list):
                if vectors_match(gold, pred, ignore_order_=ignore_order):
                    break

    return score


def evaluate_spider2sql(gold_result_dir, csv_pth, example_id, task="lite"):
    eval_standard_dict = load_jsonl_to_dict(os.path.join('/'.join(gold_result_dir.split("/")[:-1]), f"spider2{task}_eval.jsonl"))
    eval_ids = list(eval_standard_dict.keys())
    eval_ids = sorted(eval_ids)  # sorted, for reproduce result
    
    try:
        pred_pd = pd.read_csv(csv_pth)
        pattern = re.compile(rf'^{re.escape(example_id)}(_[a-z])?\.csv$')
        all_files = os.listdir(gold_result_dir)
        csv_files = [file for file in all_files if pattern.match(file)]
        csv_files = sorted(csv_files)
        if len(csv_files) == 1:
            gold_pd = pd.read_csv(os.path.join(gold_result_dir, example_id+".csv"))
            score = compare_pandas_table(pred_pd, gold_pd, eval_standard_dict.get(example_id)['condition_cols'], eval_standard_dict.get(example_id)['ignore_order'])
        elif len(csv_files) > 1:
            gold_pds = [pd.read_csv(os.path.join(gold_result_dir, file)) for file in csv_files]
            score = compare_multi_pandas_table(pred_pd, gold_pds, eval_standard_dict.get(example_id)['condition_cols'], eval_standard_dict.get(example_id)['ignore_order'])
    except Exception as e:
        print(f"{example_id} ERROR: {e}")
        score = 0
    return score

def get_tuple(csv_str):
    f = StringIO(csv_str)
    reader = csv.reader(f)
    next(reader)
    return [tuple(row) for row in reader]

def evaluate_bird(gold_result_dir, exec_result_path, example_id, task=None):
    try:
        with open(os.path.join(gold_result_dir, example_id+".csv")) as f:
            gold_csv = f.read()
        with open(os.path.join(exec_result_path)) as f:
            exec_result = f.read()
        if set(get_tuple(exec_result)) == set(get_tuple(gold_csv)):
            return 1
        return 0
    except Exception as e:
        print(f"{example_id} ERROR: {e}")
    return 0

def update_results(gold_result_dir):
    sql_env = SqlEnv()
    gold_sql_dir = gold_result_dir.replace("exec_result", "sql")
    for sql in os.listdir(gold_sql_dir):
        api = get_api_name(sql)
        with open(os.path.join(gold_sql_dir, sql)) as f:
            sql_query = f.read()
        save_pth = os.path.join(gold_result_dir, sql.replace(".sql", ".csv"))
        if api != "sqlite":
            result = sql_env.execute_sql_api(sql_query, sql.replace("sql", ""), save_pth, api)
            print(sql, result)
        else:
            db_id = get_db_id("../../spider2-lite", sql.replace(".sql", ""))
            sqlite_path = get_sqlite_path(db_id=db_id)
            # print(sql, db_id, sqlite_path)
            result = sql_env.execute_sql_api(sql_query, sql.replace(".sql", ""), save_pth, api, sqlite_path=sqlite_path)
            print(sql, result)            

def evaluate_passk(pth, task, update_res=False):
    eval_func = [evaluate_spider2sql]
    if task == "BIRD":
        gold_result_dir = "../../data/BIRD/gold_result"
        eval_func.append(evaluate_bird)
    else:
        gold_result_dir = f"../../spider2-{task}/evaluation_suite/gold/exec_result"
    if update_res:
        update_results(gold_result_dir)
    final_score = {}
    passk_score = {}
    
    for func in eval_func:
        print("Evaluate function:", func)
        for ex in tqdm(os.listdir(pth)):
            if ex.endswith("original"):
                continue
            ex_pth = os.path.join(pth, ex)
            ex_score = []
            for file in os.listdir(ex_pth):
                file_pth = os.path.join(ex_pth, file)
                if file_pth.endswith(".csv") and file != "result.csv":
                    ex_score.append(func(gold_result_dir, file_pth, ex, task=task))
                elif file == "result.csv":
                    final_score[ex] = func(gold_result_dir, file_pth, ex, task=task)
            if ex_score and sum(ex_score) >= 1:
                passk_score[ex] = 1
            else:
                passk_score[ex] = 0
        final_score = dict(sorted(final_score.items()))
        passk_score = dict(sorted(passk_score.items()))
        print("Final score dic", {k: v for k, v in final_score.items() if v == 1})
        print("Pass@k score dic", {k: v for k, v in passk_score.items() if v == 1})
        print(f"Final score: {sum(final_score.values())}/{len(passk_score)}={sum(final_score.values())/len(passk_score)}, valid: {len(final_score)}/{len(passk_score)}={len(final_score)/len(passk_score)}")
        print(f"Final score: {sum(passk_score.values())}/{len(passk_score)}={sum(passk_score.values())/len(passk_score)}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Setup for Spider 2.0")
    parser.add_argument("--log_folder", default=None, type=str)
    parser.add_argument("--task", type=str, default=None)
    parser.add_argument("--update_res", action="store_true")

    args = parser.parse_args()
    evaluate_passk(args.log_folder, args.task, args.update_res)