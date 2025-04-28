import os
import pandas as pd
from tqdm import tqdm
import argparse
import shutil
import sqlite3
from utils import remove_digits, is_file, hard_cut, clear_description
import json
pd.set_option('display.max_colwidth', None)

def process_ddl(ddl_file):
    table_names = ddl_file['table_name'].to_list()
    representatives = {}
    for i in range(len(ddl_file)):
        if remove_digits(table_names[i]) in representatives.keys():
            representatives[remove_digits(table_names[i])] += [table_names[i]]
            ddl_file = ddl_file.drop(index=i)
        else:
            representatives[remove_digits(table_names[i])] = [table_names[i]]
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

def compress_ddl(example_folder, add_description=False, add_sample_rows=False, rm_digits=False, schema_linked=False):
    print("Compress DDL files.")
    for entry in tqdm(os.listdir(example_folder)):
        external_knowledge = None
        prompts = ''
        entry1_path = os.path.join(example_folder, entry)
        if os.path.isdir(entry1_path):
            if not entry.startswith("local"):
                table_dict = {}
                for project_name in os.listdir(entry1_path):
                    
                    if project_name == "spider":
                        continue
                    project_name_path = os.path.join(entry1_path, project_name)
                    if os.path.isdir(os.path.join(project_name_path)):
                        for db_name in os.listdir(project_name_path):
                            if project_name not in table_dict:
                                table_dict[project_name] = {db_name: []}
                            else:
                                table_dict[project_name][db_name] = []
                            db_name_path = os.path.join(project_name_path, db_name)
                            assert os.path.isdir(db_name_path) == True and "DDL.csv" in os.listdir(db_name_path)
                            for schema_name in os.listdir(db_name_path):
                                schema_name_path = os.path.join(db_name_path, schema_name)
                                if schema_name == "DDL.csv":
                                    representatives = None
                                    if entry.startswith("sf0"):
                                        check_table_names(schema_name_path)
                                    if schema_linked and os.path.exists(schema_name_path.replace("DDL.csv", "DDL_sl.csv")):
                                        schema_name_path = schema_name_path.replace("DDL.csv", "DDL_sl.csv")
                                    ddl_file = pd.read_csv(schema_name_path)
                                    if schema_linked and len(ddl_file['table_name'].to_list()) < 10:
                                        pass
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
                                        
                                        prompts += "Table full name: " + table_json["table_fullname"] + "\n"

                                        column_prefix = "column_"
                                        for j in range(len(table_json[f"{column_prefix}names"])):
                                            table_des = ''
                                            if add_description:
                                                if j < len(table_json["description"]):
                                                    table_des = " Description: " + str(table_json["description"][j])
                                                elif table_json[f"column_names"][j] != "_PARTITIONTIME":
                                                    print(f"{entry} description unmatch {table_name_list[i]}")
                                            prompts += "Column name: " + table_json[f"{column_prefix}names"][j] + " Type: " + table_json[f"{column_prefix}types"][j] + table_des +"\n"
                                        if add_sample_rows:
                                            prompts += "Sample rows:\n" + hard_cut(str(table_json["sample_rows"]), length=1000) + "\n"
                                        table_dict[project_name][db_name] += [table_name_list[i]]
                                        if representatives is not None:
                                            if len(representatives[remove_digits(table_name_list[i])]) > 1:
                                                prompts += f"Some other tables have the similar structure: {representatives[remove_digits(table_name_list[i])]}\n"
                                                table_dict[project_name][db_name] += representatives[remove_digits(table_name_list[i])]
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
                table_names, prompts = get_sqlite_data(sqlite_path, add_description=add_description, add_sample_rows=add_sample_rows)
            with open(os.path.join(entry1_path, "prompts.txt"), "w") as f:
                if len(prompts) > 200000:
                    print(f"{entry} len: {len(prompts)}")
                    prompts = clear_description(prompts)
                    print(f"cleared len: {len(prompts)}")
                prompts += f"External knowledge that might be helpful: \n{external_knowledge}\n"
                if not entry.startswith("local"):
                    prompts += "The table structure information is ({database name: {schema name: [table name]}}): \n" + str(table_dict) + "\n"
                else:
                    prompts += "The table structure information is (table names): \n" + str(table_names) + "\n"
                f.writelines(prompts)

def get_sqlite_data(path, add_description=False, add_sample_rows=False):
    connection = sqlite3.connect(path)
    cursor = connection.cursor()
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()

    table_names = [table[0] for table in tables]
    prompts = ""
    for table in tables:
        table_name = table[0]
        table_json = {}
        table_json["table_fullname"] = table_name

        cursor.execute("PRAGMA table_info({})".format(table_name))
        columns_info = cursor.fetchall()
        column_names = []
        column_types = []
        description = []
        for col in columns_info:
            column_names.append(col[1])
            column_types.append(col[2])
            description.append("")

        table_json["column_names"] = column_names
        table_json["column_types"] = column_types
        table_json["description"] = description

        sample_rows = []
        if add_sample_rows:
            try:
                cursor.execute("SELECT * FROM {} LIMIT 3".format(table_name))
                sample_rows = cursor.fetchall()
            except Exception as e:
                sample_rows = f"Error fetching sample rows: {str(e)}"
        table_json["sample_rows"] = str(sample_rows)

        prompts += "\n" + "-" * 50 + "\n"
        prompts += "Table full name: " + table_json["table_fullname"] + "\n"
        for j in range(len(table_json["column_names"])):
            table_des = ''
            if add_description:
                table_des = " Description: " + table_json["description"][j]
            prompts += "Column name: " + table_json["column_names"][j] + " Type: " + table_json["column_types"][j] + table_des + "\n"
        if add_sample_rows:
            prompts += "Sample rows:\n" + hard_cut(table_json["sample_rows"], length=1000) + "\n"

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
    args = parser.parse_args()
    if args.make_folder:
        make_folder(args)
    compress_ddl(args.example_folder, args.add_description, args.add_sample_rows, args.rm_digits, args.schema_linked)