#!/bin/bash
set -e
UPDATE=false
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --update)
      UPDATE=true
      shift # past argument
      ;;
    --task)
      TASK="$2"
      shift
      shift
      ;;
    --output_path)
      OUTPUT_PATH="$2"
      shift
      shift
      ;;
    *)
      shift
      ;;
  esac
done
python run.py \
    --task $TASK \
    --db_path examples_${TASK} \
    --output_path $OUTPUT_PATH\
    --revote \
    --do_vote \
    --num_votes 8 \
    --num_workers 16

echo "Evaluation for Step 1: revote"
CMD1="python eval.py --log_folder $OUTPUT_PATH --task $TASK"
if [ "$UPDATE" = true ]; then
  CMD1="$CMD1 --update_res"
fi
eval $CMD1

python run.py \
    --task $TASK \
    --db_path examples_${TASK} \
    --output_path $OUTPUT_PATH\
    --revote \
    --do_vote \
    --random_vote_for_tie \
    --num_votes 8 \
    --num_workers 16

echo "Evaluation for Step 2: random_vote_for_tie"
python eval.py --log_folder $OUTPUT_PATH --task $TASK

python run.py \
    --task $TASK \
    --db_path examples_${TASK} \
    --output_path $OUTPUT_PATH\
    --revote \
    --do_vote \
    --random_vote_for_tie \
    --final_choose \
    --num_votes 8 \
    --num_workers 16

echo "Evaluation for Step 3: final choose"
python eval.py --log_folder $OUTPUT_PATH --task $TASK