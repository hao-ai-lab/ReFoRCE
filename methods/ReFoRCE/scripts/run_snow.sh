#!/bin/bash
set -e
API=$1
# Set up
python spider_agent_setup_snow.py
# Reconstruct data
python reconstruct_data.py --example_folder examples_snow --add_description --make_folder --rm_digits
# Run
python run.py \
    --task snow \
    --db_path examples_snow \
    --output_path output/${API}-snow-log \
    --model ${API} \
    --pre_model ${API} \
    --schema_linking_model ${API} \
    --max_iter 5 \
    --model_vote \
    --num_votes 3 \
    --num_workers 16
# Evaluation
python get_metadata.py --result_path output/${API}-snow-log --output_path output/${API}-snow
cd ../../spider2-snow/evaluation_suite
python evaluate.py --mode exec_result --result_dir ../../methods/ReFoRCE/output/${API}-snow