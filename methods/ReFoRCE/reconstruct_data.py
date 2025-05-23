import os
import pandas as pd
from tqdm import tqdm
import argparse
import shutil
import sqlite3
from utils import remove_digits, is_file, clear_description, clear_sample_rows, extract_column_names, extract_real_table_names, get_api_name, clear_name, remove_declare_lines, clear_byte
import json
pd.set_option('display.max_colwidth', None)
THRESHOLD = 200000
WRONG_GOLD_TABLES = ["bq095", "bq350", "bq379", "bq396", "sf_bq084", "sf_bq200","sf_bq226", "sf_bq295", "sf_bq358"]
SKIP_GOLD_SQLS = ["bq350", "local039", "bq095", "bq374", "bq379", "bq396", "bq403", "bq406", "sf_bq233", "sf_bq273", "sf_local039", "sf_bq295"]
def process_ddl(ddl_file):
    table_names = ddl_file['table_name'].to_list()
    representatives = {}
    for i in range(len(ddl_file)):
        if remove_digits(table_names[i]) in representatives.keys():
            representatives[remove_digits(table_names[i])] += [table_names[i]]
        else:
            representatives[remove_digits(table_names[i])] = [table_names[i]]

    for i in range(len(ddl_file)):
        if remove_digits(table_names[i]) in representatives:
            if len(representatives[remove_digits(table_names[i])]) > 10:
                if ddl_file['table_name'][i] != representatives[remove_digits(table_names[i])][0]:
                    ddl_file = ddl_file.drop(index=i)
            else:
                # representatives[table_names[i]] = [table_names[i]]
                del representatives[remove_digits(table_names[i])]
    return ddl_file, representatives

def process_ddl_gold(ddl_file, gold_table_names, entry=None):
    table_names = ddl_file['table_name'].to_list()
    representatives = {}

    for i in range(len(ddl_file)):
        if not any(table_names[i].upper() in t for t in gold_table_names):
            ddl_file = ddl_file.drop(index=i)
    ddl_file.reset_index(drop=True, inplace=True)
    table_names = ddl_file['table_name'].to_list()

    for i in range(len(ddl_file)):
        if remove_digits(table_names[i]) in representatives.keys():
            representatives[remove_digits(table_names[i])] += [table_names[i]]
        else:
            representatives[remove_digits(table_names[i])] = [table_names[i]]

    for i in range(len(ddl_file)):
        if remove_digits(table_names[i]) in representatives:
            if len(representatives[remove_digits(table_names[i])]) > 10:
                if ddl_file['table_name'][i] != representatives[remove_digits(table_names[i])][0]:
                    ddl_file = ddl_file.drop(index=i)
            else:
                # representatives[table_names[i]] = [table_names[i]]
                del representatives[remove_digits(table_names[i])]

    return ddl_file, representatives

def process_ddl_gold_schema(ddl_file, full_table_names_with_omit, entry):
    table_names = ddl_file['table_name'].to_list()
    representatives = {}

    for i in range(len(ddl_file)):
        if not any(table_names[i].upper() in t for t in full_table_names_with_omit):
            if not any(remove_digits(table_names[i].upper()) in t for t in full_table_names_with_omit):
                ddl_file = ddl_file.drop(index=i)
    ddl_file.reset_index(drop=True, inplace=True)
    table_names = ddl_file['table_name'].to_list()

    for i in range(len(ddl_file)):
        if remove_digits(table_names[i]) in representatives.keys():
            representatives[remove_digits(table_names[i])] += [table_names[i]]
        else:
            representatives[remove_digits(table_names[i])] = [table_names[i]]

    for i in range(len(ddl_file)):
        if remove_digits(table_names[i]) in representatives:
            if len(representatives[remove_digits(table_names[i])]) > 10:
                if ddl_file['table_name'][i] != representatives[remove_digits(table_names[i])][0]:
                    ddl_file = ddl_file.drop(index=i)
            else:
                # representatives[table_names[i]] = [table_names[i]]
                del representatives[remove_digits(table_names[i])]

    return ddl_file, representatives

def check_table_names(ddl_path):
    ddl_file = pd.read_csv(ddl_path)
    temp_path = ddl_path.replace("DDL.csv", "DDL_tmp.csv")
    ddl_file['table_name'] = ddl_file['table_name'].str.split('.').str[-1]
    ddl_file.to_csv(temp_path, index=False)
    os.replace(temp_path, ddl_path)

def make_folder(args):
    print("Make folders for some examples.")
    example_folder = args.example_folder
    for entry in tqdm(os.listdir(example_folder)):
        entry1_path = os.path.join(example_folder, entry)
        if os.path.isdir(entry1_path):
            for project_name in os.listdir(entry1_path):
                project_name_path = os.path.join(entry1_path, project_name)
                if os.path.isdir(project_name_path):
                    for db_name in os.listdir(project_name_path):
                        db_name_path = os.path.join(project_name_path, db_name)
                        if db_name == "json":
                            os.remove(os.path.join(project_name_path, "json"))
                        elif (entry.startswith("sf") and db_name.endswith(".json")) or (entry.startswith("bq")) or (entry.startswith("ga")):
                            assert '.' in db_name.strip(".json")
                            folder_name = db_name.split(".")[0]
                            file_name = '.'.join(db_name.split(".")[1:])
                            folder_path = os.path.join(project_name_path, folder_name)
                            if not os.path.exists(folder_path):
                                os.mkdir(folder_path)
                            if entry.startswith("bq") or entry.startswith("ga"):
                                shutil.move(db_name_path, os.path.join(folder_path, file_name))
                            elif entry.startswith("sf"):
                                shutil.copy(db_name_path, os.path.join(folder_path, file_name))
                                os.remove(db_name_path)                                
                    if entry.startswith("sf") and "DDL.csv" in os.listdir(project_name_path):
                        ddl_path = os.path.join(project_name_path, "DDL.csv")
                        shutil.copy(ddl_path, os.path.join(folder_path, "DDL.csv"))
                        os.remove(ddl_path)
                    if entry.startswith("bq") or entry.startswith("ga"):
                        shutil.move(folder_path, os.path.join(entry1_path, folder_name))
                        shutil.rmtree(project_name_path)

def compress_ddl(example_folder, add_description=False, add_sample_rows=False, rm_digits=False, schema_linked=False, clear_long_eg_des=False, sqlite_sl_path=None, reduce_col=False, use_gold_table=False, use_gold_schema=False):
    print("Compress DDL files.")
    for entry in tqdm(os.listdir(example_folder)):
        external_knowledge = None
        prompts = ''
        entry1_path = os.path.join(example_folder, entry)
        if os.path.isdir(entry1_path):

            gold_table_names = None
            gold_column_names = None
            if use_gold_table:
                for ex in gold:
                    if ex['instance_id'] == entry:
                        gold_table_names = set([i.upper() for i in ex["gold_tables"]])
                if gold_table_names is None or entry in WRONG_GOLD_TABLES:
                    shutil.rmtree(os.path.join(args.example_folder, entry))
                    print("Miss gold table", entry)
                    continue
            elif use_gold_schema:
                if entry in SKIP_GOLD_SQLS:
                    shutil.rmtree(os.path.join(args.example_folder, entry))
                    continue
                for ex in os.listdir(args.gold_sql_pth):
                    if ex.replace(".sql", "") == entry:
                        with open(os.path.join(args.gold_sql_pth, ex)) as f:
                            gold_sql = remove_declare_lines(f.read())
                        full_table_names_with_omit, gold_column_names = extract_real_table_names(gold_sql, get_api_name(ex))
                        gold_table_names = clear_name(full_table_names_with_omit, do_remove_digits=False)
                        gold_column_names = {i.upper() for i in gold_column_names}
                if gold_table_names is None:
                    shutil.rmtree(os.path.join(args.example_folder, entry))
                    continue
                # print(entry)
            if not entry.startswith("local"):
                table_dict = {}
                for project_name in os.listdir(entry1_path):
                    
                    if project_name == "spider":
                        continue
                    project_name_path = os.path.join(entry1_path, project_name)
                    if os.path.isdir(os.path.join(project_name_path)):
                        for db_name in os.listdir(project_name_path):
                            db_name_path = os.path.join(project_name_path, db_name)
                            assert os.path.isdir(db_name_path) == True and "DDL.csv" in os.listdir(db_name_path)
                            for schema_name in os.listdir(db_name_path):
                                schema_name_path = os.path.join(db_name_path, schema_name)
                                if schema_name == "DDL.csv":
                                    representatives = None
                                    if entry.startswith("sf0"):
                                        check_table_names(schema_name_path)
                                    ddl_sl_flag = False
                                    if schema_linked:
                                        if os.path.exists(schema_name_path.replace("DDL.csv", "DDL_sl.csv")):
                                            ddl_sl_flag = True
                                            schema_name_path = schema_name_path.replace("DDL.csv", "DDL_sl.csv")
                                    ddl_file = pd.read_csv(schema_name_path)
                                    
                                    # clear ddl_file for sf
                                    # if entry.startswith("sf"):
                                    #     table_names_ = []
                                    #     for i in os.listdir(db_name_path):
                                    #         if i.endswith(".json"):
                                    #             table_names_ += [i.replace(".json", "").split(".")[-1]]
                                    #     ddl_file = ddl_file[ddl_file["table_name"].isin(table_names_)].reset_index(drop=True)
                                    #     assert not ddl_file.empty
                                    #     ddl_file.to_csv(schema_name_path, index=False)
                                    # print(ddl_file, entry)
                                    if schema_linked and len(ddl_file['table_name'].to_list()) < 10:
                                        pass
                                    elif use_gold_table:
                                        ddl_file, representatives = process_ddl_gold(ddl_file, gold_table_names, entry)
                                    elif use_gold_schema:
                                        ddl_file, representatives = process_ddl_gold_schema(ddl_file, gold_table_names, entry)
                                    elif rm_digits:
                                        ddl_file, representatives = process_ddl(ddl_file)
                                    table_name_list = ddl_file['table_name'].to_list()
                                    ddl_file.reset_index(drop=True, inplace=True)
                                    for i in range(len(table_name_list)):
                                        if os.path.exists(os.path.join(db_name_path, table_name_list[i]+".json")):                               
                                            with open(os.path.join(db_name_path, table_name_list[i]+".json")) as f:
                                                table_json = json.load(f)
                                        elif os.path.exists(os.path.join(db_name_path, db_name+'.'+table_name_list[i]+".json")):
                                                with open(os.path.join(db_name_path, db_name+'.'+table_name_list[i]+".json")) as f:
                                                    table_json = json.load(f)
                                        else:
                                            # print(entry, f"No table: {os.path.join(db_name_path, table_name_list[i])}")
                                            continue

                                        if use_gold_table:
                                            if table_json["table_fullname"].upper() not in gold_table_names and not representatives:
                                                continue
                                        elif use_gold_schema:
                                            if table_json["table_fullname"].upper() not in gold_table_names and not representatives:
                                                continue
                                        
                                        prompts += "Table full name: " + table_json["table_fullname"] + "\n"
                                        
                                        project_name_, db_name_, table_name_ = table_json["table_fullname"].split(".")
                                        table_dict.setdefault(project_name_, {}).setdefault(db_name_, [])


                                        if reduce_col and ddl_sl_flag:
                                            assert schema_linked
                                            full_name = table_json["table_fullname"]
                                            short_name = full_name.split(".")[-1].strip()

                                            ddl_file.columns = ddl_file.columns.str.strip().str.lower()
                                            ddl_file["table_name"] = ddl_file["table_name"].str.strip()
                                            matched = ddl_file[ddl_file["table_name"] == short_name].iloc[0]
                                            # assert len(matched) == 1, print(ddl_file["table_name"], short_name, entry)
                                            
                                            col_names = matched["ddl"]
                                        column_prefix = "column_"
                                        for j in range(len(table_json[f"{column_prefix}names"])):
                                            table_des = ''
                                            if add_description:
                                                if j < len(table_json["description"]):
                                                    table_des = " Description: " + str(table_json["description"][j]) if table_json["description"][j] else ""
                                                elif table_json[f"column_names"][j] != "_PARTITIONTIME":
                                                    print(f"{entry} description unmatch {table_name_list[i]}")

                                            if reduce_col and ddl_sl_flag:

                                                if table_json[f"{column_prefix}names"][j] in col_names:
                                                    # print("Name matched", entry)
                                                    prompts += "Column name: " + table_json[f"{column_prefix}names"][j] + " Type: " + table_json[f"{column_prefix}types"][j] + table_des +"\n"
                                            elif use_gold_schema:
                                                if table_json[f"{column_prefix}names"][j].upper() in gold_column_names:
                                                    prompts += "Column name: " + table_json[f"{column_prefix}names"][j] + " Type: " + table_json[f"{column_prefix}types"][j] + table_des +"\n"
                                            else:
                                                prompts += "Column name: " + table_json[f"{column_prefix}names"][j] + " Type: " + table_json[f"{column_prefix}types"][j] + table_des +"\n"
                                        if add_sample_rows:                                            
                                            if reduce_col and ddl_sl_flag:
                                                sample_rows = [{col: row[col] for col in extract_column_names(col_names) if col in row} for row in table_json["sample_rows"]]
                                            elif use_gold_schema:
                                                rows = []
                                                for row in table_json["sample_rows"]:
                                                    for col in gold_column_names:
                                                        for s in row.keys():
                                                            if col in s.upper():
                                                                rows.append({col: row[s]})
                                                if table_json["sample_rows"]:
                                                    assert rows, str(entry)+str(table_json) + str(gold_column_names)
                                                sample_rows = rows
                                            else:
                                                sample_rows = table_json["sample_rows"]
                                            sample_rows = clear_byte(sample_rows)
                                            prompts += "Sample rows:\n" + str(sample_rows) + "\n"
                                        table_dict[project_name_][db_name_] += [table_name_list[i]]
                                        if representatives is not None:
                                            if remove_digits(table_name_list[i]) in representatives:
                                                if len(representatives[remove_digits(table_name_list[i])]) > 1:
                                                    assert len(representatives[remove_digits(table_name_list[i])]) >= 10, representatives[remove_digits(table_name_list[i])]
                                                    prompts += f"Some other tables have the similar structure: {representatives[remove_digits(table_name_list[i])]}\n"
                                                    table_dict[project_name_][db_name_] += representatives[remove_digits(table_name_list[i])]
                                        prompts += "\n" + "-" * 50 + "\n"
                                elif schema_name == "json":
                                    with open(schema_name_path) as f:
                                        prompts += f.read()
                                        print(f.read())

                    elif is_file(project_name_path, "md"):
                        with open(project_name_path) as f:
                            external_knowledge = f.read()                
            else:
                for sqlite in os.listdir(entry1_path):
                    if sqlite.endswith(".sqlite"):
                        sqlite_path = os.path.join(entry1_path, sqlite)
                if sqlite_sl_path:
                    with open(sqlite_sl_path, encoding="utf-8") as f:
                        sl_res = json.load(f)
                    for eg in sl_res:
                        if eg["instance_id"] == entry:
                            sl_info = eg
                            external_knowledge = "Retrieved columns and values: " + str(sl_info['L_values']) if sl_info['L_values'] else ""
                table_names, prompts = get_sqlite_data(sqlite_path, entry, add_description=add_description, add_sample_rows=add_sample_rows, gold_table_names=gold_table_names, gold_column_names=gold_column_names)
            with open(os.path.join(entry1_path, "prompts.txt"), "w") as f:
                if len(prompts) > THRESHOLD:
                    # print(f"{entry} len before clearing sample rows1: {len(prompts)}")
                    prompts = clear_sample_rows(prompts, byte_limit=10000)
                    # print(f"sample rows cleared len1: {len(prompts)}")                     
                if len(prompts) > THRESHOLD and clear_long_eg_des:
                    # print(f"{entry} len before clearing description: {len(prompts)}")
                    prompts = clear_description(prompts)
                    # print(f"description cleared len: {len(prompts)}")

                prompts += f"External knowledge that might be helpful: \n{external_knowledge}\n"
                if not entry.startswith("local"):
                    prompts += "The table structure information is ({database name: {schema name: [table name]}}): \n" + str(table_dict) + "\n"
                else:
                    prompts += "The table structure information is (table names): \n" + str(table_names) + "\n"
                f.writelines(prompts)

def get_sqlite_data(path, entry, add_description=False, add_sample_rows=False, gold_table_names=None, gold_column_names=None):
    connection = sqlite3.connect(path)
    cursor = connection.cursor()
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()

    table_names = [table[0] for table in tables]
    prompts = ""
    for table in tables:
        table_name = table[0]

        if gold_table_names:
            if table_name.upper() not in gold_table_names:
                continue

        table_json = {}
        table_json["table_fullname"] = table_name

        cursor.execute("PRAGMA table_info({})".format(table_name))
        columns_info = cursor.fetchall()
        column_names = []
        column_types = []
        for col in columns_info:
            column_names.append(col[1])
            column_types.append(col[2])

        if gold_column_names:
            table_json["column_names"] = []
            table_json["column_types"] = []
            for i in range(len(column_names)):
                if column_names[i].upper() in gold_column_names:
                    table_json["column_names"].append(column_names[i])
                    table_json["column_types"].append(column_types[i])
        else:
            table_json["column_names"] = column_names
            table_json["column_types"] = column_types

        if not table_json["column_names"]:
            print(entry, table_name, gold_table_names, gold_column_names)

        sample_rows = []
        if add_sample_rows:
            if gold_column_names:
                column_str = ", ".join(table_json["column_names"])
                query = f"SELECT {column_str} FROM {table_name} LIMIT 3"
            else:
                query = f"SELECT * FROM {table_name} LIMIT 3"
            # print(query)
            cursor.execute(query)
            sample_rows = cursor.fetchall()
        table_json["sample_rows"] = str(sample_rows)

        prompts += "\n" + "-" * 50 + "\n"
        prompts += "Table full name: " + table_json["table_fullname"] + "\n"
        for j in range(len(table_json["column_names"])):
            table_des = ''
            prompts += "Column name: " + table_json["column_names"][j] + " Type: " + table_json["column_types"][j] + table_des + "\n"
        if add_sample_rows:
            prompts += "Sample rows:\n" + table_json["sample_rows"] + "\n"
    connection.close()
    return table_names, prompts


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--example_folder', type=str, default="examples")
    parser.add_argument('--add_description', action="store_true")
    parser.add_argument('--add_sample_rows', action="store_true")
    parser.add_argument('--make_folder', action="store_true")
    parser.add_argument('--rm_digits', action="store_true")
    parser.add_argument('--schema_linked', action="store_true")
    parser.add_argument('--clear_long_eg_des', action="store_true")
    parser.add_argument('--sqlite_sl_path', type=str, default=None)
    parser.add_argument('--reduce_col', action="store_true")
    parser.add_argument('--use_gold_table', action="store_true")
    parser.add_argument('--gold_table_pth', type=str, default=None)
    parser.add_argument('--use_gold_schema', action="store_true")
    parser.add_argument('--gold_sql_pth', type=str, default=None)
    
    args = parser.parse_args()
    if args.make_folder:
        make_folder(args)
    if args.use_gold_table:
        gold_tb = args.gold_table_pth
        with open(gold_tb) as f:
            gold = [json.loads(i) for i in f]

    elif args.use_gold_schema:
        gold_sql_pth = args.gold_sql_pth

    compress_ddl(args.example_folder, args.add_description, args.add_sample_rows, args.rm_digits, args.schema_linked, args.clear_long_eg_des, args.sqlite_sl_path, args.reduce_col, args.use_gold_table, args.use_gold_schema)