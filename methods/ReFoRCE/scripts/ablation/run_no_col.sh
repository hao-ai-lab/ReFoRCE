#!/bin/bash
set -e
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
AZURE=false
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --azure)
      AZURE=true
      shift # past argument
      ;;
    --task)
      TASK="$2"
      shift
      shift
      ;;
    --model)
      API="$2"
      shift
      shift
      ;;
    *)
      shift
      ;;
  esac
done

# Set up
if [ "$TASK" = "lite" ]; then
    gdown 'https://drive.google.com/uc?id=1coEVsCZq-Xvj9p2TnhBFoFTsY-UoYGmG' -O ../../spider2-lite/resource/
    rm -rf ../../spider2-lite/resource/databases/spider2-localdb
    mkdir -p ../../spider2-lite/resource/databases/spider2-localdb
    unzip ../../spider2-lite/resource/local_sqlite.zip -d ../../spider2-lite/resource/databases/spider2-localdb
fi

python spider_agent_setup_${TASK}.py --example_folder examples_${TASK}

# Reconstruct data
python reconstruct_data.py \
    --example_folder examples_${TASK} \
    --add_description \
    --add_sample_rows \
    --rm_digits \
    --make_folder \
    --clear_long_eg_des

echo "Number of prompts.txt files in examples_${TASK} larger than 200KB before reducing: $(find examples_${TASK} -type f -name "prompts.txt" -exec du -b {} + | awk '$1 > 200000' | wc -l)"

# Run Schema linking and voting
python schema_linking.py \
    --task $TASK \
    --db_path examples_${TASK} \
    --linked_json_pth ../../data/linked_${TASK}_tmp0.json \
    --reduce_col

echo "Number of prompts.txt files in examples_${TASK} larger than 200KB before reducing: $(find examples_${TASK} -type f -name "prompts.txt" -exec du -b {} + | awk '$1 > 200000' | wc -l)"




OUTPUT_PATH="output/${API}-${TASK}-log-${TIMESTAMP}"
# OUTPUT_PATH="output/${API}-${TASK}-log"
NUM_VOTES=8
NUM_WORKERS=16
echo "AZURE mode: $AZURE"
echo "Model: $API"
echo "Task: $TASK"
echo "Output Path: $OUTPUT_PATH"

# Step 1: Self-refinement + Majority Voting
CMD1="python run.py \
    --task $TASK \
    --db_path examples_${TASK} \
    --output_path $OUTPUT_PATH \
    --do_self_refinement \
    --generation_model ${API} \
    --max_iter 5 \
    --temperature 1 \
    --early_stop \
    --do_vote \
    --num_votes $NUM_VOTES \
    --num_workers $NUM_WORKERS"

# Step 2: Self-refinement + Majority Voting + Column Exploration + Rerun
CMD2="python run.py \
    --task $TASK \
    --db_path examples_${TASK} \
    --output_path $OUTPUT_PATH \
    --do_self_refinement \
    --generation_model ${API} \
    --do_column_exploration \
    --column_exploration_model ${API} \
    --max_iter 5 \
    --temperature 1 \
    --early_stop \
    --do_vote \
    --num_votes $NUM_VOTES \
    --num_workers $NUM_WORKERS \
    --rerun \
    --overwrite_unfinished"

if [ "$AZURE" = true ]; then
  CMD1="$CMD1 --azure"
  CMD2="$CMD2 --azure"
fi

eval $CMD1
echo "Evaluation for Step 1"
python eval.py --log_folder output/${API}-${TASK}-log --task $TASK

# Step 2: Random vote for tie
python run.py \
    --task $TASK \
    --db_path examples_${TASK} \
    --output_path $OUTPUT_PATH \
    --do_vote \
    --random_vote_for_tie \
    --num_votes $NUM_VOTES \
    --num_workers $NUM_WORKERS
echo "Evaluation for Step 2"
python eval.py --log_folder output/${API}-${TASK}-log --task $TASK

# eval $CMD2
# echo "Evaluation for Step 2"
# python eval.py --log_folder output/${API}-${TASK}-log --task $TASK

# Step 3: Random vote final_choose
python run.py \
    --task $TASK \
    --db_path examples_${TASK} \
    --output_path $OUTPUT_PATH \
    --do_vote \
    --random_vote_for_tie \
    --final_choose \
    --num_votes $NUM_VOTES \
    --num_workers $NUM_WORKERS
echo "Evaluation for Step 3"
python eval.py --log_folder output/${API}-${TASK}-log --task $TASK

# Final evaluation and get files for submission
python get_metadata.py --result_path $OUTPUT_PATH --output_path output/${API}-${TASK}-csv-${TIMESTAMP}
python get_metadata.py --result_path $OUTPUT_PATH --output_path output/${API}-${TASK}-sql-${TIMESTAMP} --file_type sql
cd ../../spider2-lite/evaluation_suite
python evaluate.py --mode exec_result --result_dir ../../methods/ReFoRCE/output/${API}-${TASK}-csv-${TIMESTAMP}