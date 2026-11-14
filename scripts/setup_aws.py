"""Create (idempotently) the AWS resources SecondLook uses and write aws_resources.json.

- S3 bucket for market snapshots and audit traces (private, encrypted, versioned)
- Bedrock Guardrail that blocks guaranteed-return claims and direct trade instructions in output

Usage: AWS_PROFILE=team10 python scripts/setup_aws.py
"""
import json
import sys
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
REGION = "us-east-1"
sess = boto3.Session(region_name=REGION)
acct = sess.client("sts").get_caller_identity()["Account"]
bucket = f"secondlook-{acct}-{REGION}"

s3 = sess.client("s3")
existing = [b["Name"] for b in s3.list_buckets()["Buckets"]]
if bucket not in existing:
    s3.create_bucket(Bucket=bucket)
s3.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration={
    "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
s3.put_bucket_encryption(Bucket=bucket, ServerSideEncryptionConfiguration={
    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]})
print("bucket:", bucket)

br = sess.client("bedrock")
NAME = "secondlook-responsible-output"
gid = next((g["id"] for g in br.list_guardrails()["guardrails"] if g["name"] == NAME), None)
spec = dict(
    name=NAME,
    description="Blocks guaranteed-return claims and direct trade instructions in SecondLook output (educational simulation).",
    topicPolicyConfig={"topicsConfig": [
        {"name": "Guaranteed returns",
         "definition": "Statements that promise or guarantee a future investment return, or claim that an investment cannot lose money.",
         "examples": ["This ETF is guaranteed to return 10% a year.", "You cannot lose money with this stock.",
                      "The S&P 500 will definitely go up next year."],
         "type": "DENY"},
        {"name": "Trade execution instructions",
         "definition": "Imperative instructions telling the reader to place a specific buy or sell order now, such as how many shares to buy or sell today.",
         "examples": ["Buy 100 shares of XSP today.", "Sell all your RY stock right now.", "Place an order for $15,000 of bitcoin immediately."],
         "type": "DENY"},
    ]},
    wordPolicyConfig={"wordsConfig": [{"text": "guaranteed return"}, {"text": "risk-free profit"}, {"text": "can't lose"}]},
    sensitiveInformationPolicyConfig={"piiEntitiesConfig": [
        {"type": "CA_SOCIAL_INSURANCE_NUMBER", "action": "BLOCK"},
        {"type": "CREDIT_DEBIT_CARD_NUMBER", "action": "BLOCK"},
        {"type": "US_BANK_ACCOUNT_NUMBER", "action": "BLOCK"},
    ]},
    blockedInputMessaging="SecondLook is an educational simulation and cannot process this request.",
    blockedOutputsMessaging="[Removed by guardrail: SecondLook does not promise returns or tell you to place trades. "
                            "It only checks whether an idea is consistent with the goals you described.]",
)
if gid:
    br.update_guardrail(guardrailIdentifier=gid, **spec)
else:
    gid = br.create_guardrail(**spec)["guardrailId"]
print("guardrail:", gid)

cfg = {"bucket": bucket, "guardrail_id": gid, "guardrail_version": "DRAFT", "region": REGION}
(ROOT / "aws_resources.json").write_text(json.dumps(cfg, indent=2))
print("wrote aws_resources.json")

sys.path.insert(0, str(ROOT))
from src.aws import guard, upload_dir  # noqa: E402
print(upload_dir(ROOT / "data" / "market", "market"))
for t in ["Moving condo savings into XSP is inconsistent with a 2.5-year horizon.",
          "Buy 200 shares of XSP today, it is guaranteed to go up."]:
    print(guard(t))
