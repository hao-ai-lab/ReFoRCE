#!/bin/bash
set -e
API=$1
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
    --output_path output/${API}-lite-log \
    --model ${API} \
    --pre_model ${API} \
    --azure \
    --schema_linking_model ${API} \
    --max_iter 5 \
    --model_vote \
    --num_votes 3 \
    --num_workers 16
# Evaluation
python get_metadata.py --result_path output/${API}-lite-log --output_path output/${API}-lite
cd ../../spider2-lite/evaluation_suite
python evaluate.py --mode exec_result --result_dir ../../methods/ReFoRCE/output/${API}-lite