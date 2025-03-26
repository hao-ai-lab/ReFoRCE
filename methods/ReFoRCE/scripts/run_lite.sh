#!/bin/bash
set -e

# Set up
gdown 'https://drive.google.com/uc?id=1coEVsCZq-Xvj9p2TnhBFoFTsY-UoYGmG' -O ../../spider2-lite/resource/
rm -rf ../../spider2-lite/resource/databases/spider2-localdb
mkdir -p ../../spider2-lite/resource/databases/spider2-localdb
unzip ../../spider2-lite/resource/local_sqlite.zip -d ../../spider2-lite/resource/databases/spider2-localdb
python spider_agent_setup_lite.py
# Reconstruct data
python reconstruct_data.py --example_folder examples_lite --add_description --make_folder --rm_digits
# Run Schema linking and voting
python run.py \
    --task lite \
    --db_path examples_lite \
    --output_path output/o1-preview-lite-log \
    --model o1-preview \
    --pre_model o1-preview \
    --schema_linking_model o1-preview \
    --max_iter 5 \
    --model_vote \
    --num_votes 3 \
    --num_workers 16
# Evaluation
python get_metadata.py --result_path output/o1-preview-lite-log --output_path output/o1-preview-lite
cd ../../spider2-lite/evaluation_suite
python evaluate.py --mode exec_result --result_dir ../../methods/ReFoRCE/output/o1-preview-lite