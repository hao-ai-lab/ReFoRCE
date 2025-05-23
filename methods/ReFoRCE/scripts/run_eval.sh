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
    --log_folder)
      LOG_FOLDER="$2"
      shift
      shift
      ;;
    *)
      shift
      ;;
  esac
done
CMD1="python eval.py --log_folder $LOG_FOLDER --task $TASK"
if [ "$UPDATE" = true ]; then
  CMD1="$CMD1 --update_res"
fi

eval $CMD1