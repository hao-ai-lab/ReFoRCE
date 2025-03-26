#!/bin/bash
set -e

# Set up
python spider_agent_setup_snow.py
# Reconstruct data
python reconstruct_data.py --example_folder examples_snow --add_description --make_folder --rm_digits
# Run
python run.py \
    --task snow \
    --db_path examples_snow \
    --output_path output/o1-preview-snow-log \
    --model o1-preview \
    --pre_model o1-preview \
    --schema_linking_model o1-preview \
    --max_iter 5 \
    --model_vote \
    --num_votes 3 \
    --num_workers 16
# Evaluation
python get_metadata.py --result_path output/o1-preview-snow-log --output_path output/o1-preview-snow
cd ../../spider2-snow/evaluation_suite
python evaluate.py --mode exec_result --result_dir ../../methods/ReFoRCE/output/o1-preview-snow