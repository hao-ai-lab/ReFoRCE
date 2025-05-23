#!/bin/bash
set -e
model=$1
NUM_VOTES=8
NUM_WORKERS=16
OUTPUT_PATH=output/${model}-sqlite-omni-greedy-log
python run.py \
    --task lite \
    --subtask sqlite \
    --do_self_refinement \
    --generation_model $model \
    --azure \
    --temperature 0 \
    --omnisql_format_pth ../../data/omnisql_spider2_sqlite.json \
    --output_path $OUTPUT_PATH \
    --num_workers $NUM_WORKERS
echo "Evaluation for Step 1"
python eval.py --log_folder $OUTPUT_PATH --task lite

python run.py \
    --task $TASK \
    --db_path examples_${TASK} \
    --output_path $OUTPUT_PATH \
    --do_self_refinement \
    --generation_model $model \
    --do_column_exploration \
    --column_exploration_model $model \
    --max_iter 5 \
    --temperature 0 \
    --early_stop \
    --omnisql_format_pth ../../data/omnisql_spider2_sqlite.json \
    --num_workers $NUM_WORKERS \
    --rerun \
    --overwrite_unfinished
echo "Evaluation for Step 2: CE"
python eval.py --log_folder $OUTPUT_PATH --task lite