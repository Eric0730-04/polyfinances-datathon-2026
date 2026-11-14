"""AWS integration beyond Bedrock model calls:
- S3: market-data snapshot + one JSON audit trace per analysis (governance / reproducibility)
- Bedrock Guardrails: final responsible-AI screen on the text shown to the investor
All calls are optional: if a resource is not configured the app still runs locally and says so.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import boto3

REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
CONFIG_FILE = Path(__file__).resolve().parents[1] / "aws_resources.json"  # written by scripts/setup_aws.py


def _cfg():
    cfg = json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else {}
    return {"bucket": os.getenv("SECONDLOOK_BUCKET", cfg.get("bucket")),
            "guardrail_id": os.getenv("SECONDLOOK_GUARDRAIL_ID", cfg.get("guardrail_id")),
            "guardrail_version": os.getenv("SECONDLOOK_GUARDRAIL_VERSION", cfg.get("guardrail_version", "DRAFT"))}


def s3():
    return boto3.Session(region_name=REGION).client("s3")


def save_trace(trace: dict) -> str | None:
    bucket = _cfg()["bucket"]
    if not bucket:
        return None
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"traces/{day}/{trace['persona_id']}/{trace['run_id']}.json"
    s3().put_object(Bucket=bucket, Key=key, Body=json.dumps(trace, default=str).encode(),
                    ContentType="application/json", ServerSideEncryption="AES256")
    return f"s3://{bucket}/{key}"


def upload_dir(path: Path, prefix: str) -> list[str]:
    bucket = _cfg()["bucket"]
    if not bucket:
        return ["no bucket configured (run scripts/setup_aws.py)"]
    out = []
    for f in Path(path).iterdir():
        if f.is_file():
            s3().upload_file(str(f), bucket, f"{prefix}/{f.name}")
            out.append(f"s3://{bucket}/{prefix}/{f.name}")
    return out


def guard(text: str) -> dict:
    """Screen model output with the Bedrock Guardrail. Returns {action, text, assessments}."""
    cfg = _cfg()
    if not cfg["guardrail_id"]:
        return {"action": "NOT_CONFIGURED", "text": text}
    br = boto3.Session(region_name=REGION).client("bedrock-runtime")
    r = br.apply_guardrail(guardrailIdentifier=cfg["guardrail_id"], guardrailVersion=cfg["guardrail_version"],
                           source="OUTPUT", content=[{"text": {"text": text}}])
    topics = [t["name"] for a in r.get("assessments", []) for t in a.get("topicPolicy", {}).get("topics", [])
              if t.get("action", "BLOCKED") == "BLOCKED"]
    detected = [t["name"] for a in r.get("assessments", []) for t in a.get("topicPolicy", {}).get("topics", [])
                if t.get("action") == "NONE" and t.get("detected", True)]
    words = [w["match"] for a in r.get("assessments", []) for w in a.get("wordPolicy", {}).get("customWords", [])]
    out_text = r["outputs"][0]["text"] if r.get("outputs") else text
    return {"action": r["action"], "text": out_text, "topics": topics, "words": words, "detected_only": detected}
