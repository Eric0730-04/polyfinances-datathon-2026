"""Smoke test: AWS identity + Bedrock Nova Lite round trip.

Usage: AWS_PROFILE=team10 python scripts/check_aws.py
"""
import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.bedrock import DEFAULT_MODEL, chat  # noqa: E402

print("identity:", boto3.client("sts").get_caller_identity()["Arn"])
text, usage = chat("Reply with exactly: OK", max_tokens=10)
print(f"{DEFAULT_MODEL}: {text!r} {usage}")
