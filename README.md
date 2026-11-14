# PolyFinances Datathon 2026 — Team 10

## Setup

```bash
pip install -r requirements.txt
# AWS credentials (shared Team 10 workshop account, us-east-1):
# put them in a local profile or export the AWS_* variables — never commit them.
export AWS_PROFILE=team10 AWS_DEFAULT_REGION=us-east-1
python scripts/check_aws.py   # verifies identity + Bedrock Nova Lite
```

## Layout

- `src/bedrock.py` — Bedrock Converse wrapper (`chat`, `chat_json`); default model `global.amazon.nova-2-lite-v1:0` (workshop-recommended), override with `BEDROCK_MODEL_ID`
- `scripts/` — runnable entry points
- `data/` — local datasets (contents are git-ignored)

## Models available (Bedrock, us-east-1)

Nova Micro / Lite / Pro, Nova 2 Lite, Nova 2 multimodal embeddings. SageMaker domain is also provisioned.
