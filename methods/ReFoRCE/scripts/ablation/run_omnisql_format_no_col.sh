#!/bin/bash
set -e
model=$1
NUM_VOTES=8
NUM_WORKERS=16
python run.py \
    --task lite \
    --subtask sqlite \
    --do_self_refinement \
    --generation_model $model \
    --azure \
    --do_vote \
    --num_votes $NUM_VOTES \
    --omnisql_format_pth ../../data/omnisql_spider2_sqlite.json \
    --output_path output/${model}-sqlite-omni-log \
    --num_workers $NUM_WORKERS
echo "Evaluation for Step 1: no vote for tie"
python eval.py --log_folder output/${model}-sqlite-omni-log --task lite

python run.py \
    --task lite \
    --subtask sqlite \
    --do_vote \
    --random_vote_for_tie \
    --final_choose \
    --num_votes $NUM_VOTES \
    --omnisql_format_pth ../../data/omnisql_spider2_sqlite.json \
    --output_path output/${model}-sqlite-omni-log \
    --num_workers $NUM_WORKERS
echo "Evaluation for Step 2: random_vote_for_tie"
python eval.py --log_folder output/${model}-sqlite-omni-log --task lite

python run.py \
    --task lite \
    --subtask sqlite \
    --do_self_refinement \
    --generation_model $model \
    --azure \
    --do_vote \
    --num_votes $NUM_VOTES \
    --omnisql_format_pth ../../data/omnisql_spider2_sqlite_OS_linked.json \
    --output_path output/${model}-sqlite-omni-OS-log \
    --num_workers $NUM_WORKERS
echo "Evaluation for OS Step 1: no vote for tie"
python eval.py --log_folder output/${model}-sqlite-omni-log --task lite

python run.py \
    --task lite \
    --subtask sqlite \
    --do_vote \
    --random_vote_for_tie \
    --final_choose \
    --num_votes $NUM_VOTES \
    --omnisql_format_pth ../../data/omnisql_spider2_sqlite_OS_linked.json \
    --output_path output/${model}-sqlite-omni-OS-log \
    --num_workers $NUM_WORKERS
echo "Evaluation for OS Step 2: random_vote_for_tie"
python eval.py --log_folder output/${model}-sqlite-omni-log --task lite