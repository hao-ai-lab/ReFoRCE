# Run Step by Step
Navigate to the ReFoRCE method folder:  
```bash
cd methods/ReFoRCE
```
## Spider2.0-snow
### Setup
Put `snowflake_credential.json` in this folder (`methods/ReFoRCE`).

Set up folders: 
```bash
python spider_agent_setup_snow.py
```

First, roughly compress.
```bash
python reconstruct_data.py --example_folder examples_snow --add_description --make_folder --rm_digits
```

### Run

Export keys: OPENAI or AZURE (optional):
```bash
export OPENAI_API_KEY=YOUR_API_KEY
export AZURE_ENDPOINT=YOUR_AZURE_ENDPOINT
export AZURE_OPENAI_KEY=YOUR_AZURE_API_KEY
```

Do Schema Linking:
```bash
python run.py \
--task snow \
--db_path examples_snow \
--schema_linking_model o3 \
--azure \
--schema_linking_only
```

Run Voting:
```bash
python run.py \
--task snow \
--db_path examples_snow \
--output_path output/o3-snow-log \
--model o3 \
--pre_model o3 \
--azure \
--model_vote
```

To rerun for the empty examples without overwriting, add `--rerun`.

### Evaluation
Preparing for evaluation files:
```bash
python get_metadata.py --result_path output/o3-snow-log --output_path output/o3-snow
```

Run evaluation:
```bash
cd ../../spider2-snow/evaluation_suite
python evaluate.py --mode exec_result --result_dir ../../methods/ReFoRCE/output/o3-snow
```

## Spider2.0-lite

### Setup
Put `snowflake_credential.json` and `bigquery_credential.json` in this folder (`snow-spider-agent/methods/ReFoRCE`).

Set up folders: 
```bash
gdown 'https://drive.google.com/uc?id=1coEVsCZq-Xvj9p2TnhBFoFTsY-UoYGmG' -O ../../spider2-lite/resource/
rm -rf ../../spider2-lite/resource/databases/spider2-localdb
mkdir -p ../../spider2-lite/resource/databases/spider2-localdb
unzip ../../spider2-lite/resource/local_sqlite.zip -d ../../spider2-lite/resource/databases/spider2-localdb
python spider_agent_setup_lite.py
```

First, roughly compress:
```bash
python reconstruct_data.py --example_folder examples_lite --add_description --make_folder --rm_digits
```

### Run
Export API keys: OPENAI or AZURE (optional):
```bash
export OPENAI_API_KEY=YOUR_API_KEY
export AZURE_ENDPOINT=YOUR_AZURE_ENDPOINT
export AZURE_OPENAI_KEY=YOUR_AZURE_API_KEY
```

Do Schema Linking:
```bash
python run.py \
--task lite \
--db_path examples_lite \
--schema_linking_model o3 \
--azure \
--schema_linking_only
```

Run Voting:
```bash
python run.py \
    --task lite \
    --db_path examples_lite \
    --output_path output/o3-lite-log \
    --model o3 \
    --pre_model o3 \
    --azure \
    --max_iter 5 \
    --model_vote \
    --num_votes 3 \
    --num_workers 16
```

To rerun for the empty examples without overwriting, add `--rerun`.

### Evaluation
Preparation for evaluation files:
```bash
python get_metadata.py --result_path output/o3-lite-log --output_path output/o3-lite
```

Run evaluation:
```bash
cd ../../spider2-lite/evaluation_suite
python evaluate.py --mode exec_result --result_dir ../../methods/ReFoRCE/output/o3-lite
```