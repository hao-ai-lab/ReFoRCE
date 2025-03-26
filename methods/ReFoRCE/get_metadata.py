import os
import json
import shutil
import argparse

def save_to_jsonl(folder_names, file_path):
    with open(file_path, 'w', encoding='utf-8') as file:
        for name in folder_names:
            line = {'instance_id': name, "answer_type": "file", "answer_or_path": f"{name}.csv"}
            file.write(json.dumps(line, ensure_ascii=False) + '\n')

def get_csv_from_dic(folder_names, output_dic, file_type):
    for sql in folder_names:
        name = sql+f"/result.{file_type}"
        if os.path.exists(os.path.join(directory, name)):
            path_csv = os.path.join(directory, name)
            shutil.copy(path_csv, os.path.join(output_dic, f"{sql}.{file_type}"))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--result_path', type=str, default="output/o1-preview-snow-log")
    parser.add_argument('--output_path', type=str, default="output/o1-preview-snow")
    parser.add_argument('--file_type', type=str, default="csv")
    args = parser.parse_args()

    directory = args.result_path
    output_dic = args.output_path
    if not os.path.exists(output_dic):
        os.makedirs(output_dic)
    folder_names = [name for name in os.listdir(directory) if os.path.isdir(os.path.join(directory, name))]
    if args.file_type == "csv":
        save_to_jsonl(folder_names, os.path.join(output_dic, 'results_metadata.jsonl'))
    get_csv_from_dic(folder_names, output_dic, args.file_type)