"""Thin wrapper around Amazon Bedrock (Converse API).

Credentials: uses the AWS profile in $AWS_PROFILE (e.g. `team10`) or the
standard AWS_* environment variables. Never commit credentials.
"""
import json
import os
import re

import boto3

REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
DEFAULT_MODEL = os.getenv("BEDROCK_MODEL_ID", "global.amazon.nova-2-lite-v1:0")

_client = None


def client():
    global _client
    if _client is None:
        _client = boto3.Session(region_name=REGION).client("bedrock-runtime")
    return _client


def chat(prompt, system=None, model_id=DEFAULT_MODEL, max_tokens=1024, temperature=0.2):
    """Send a single-turn prompt; return (text, usage)."""
    kwargs = {
        "modelId": model_id,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
    }
    if system:
        kwargs["system"] = [{"text": system}]
    resp = client().converse(**kwargs)
    return resp["output"]["message"]["content"][0]["text"], resp["usage"]


def chat_json(prompt, system=None, **kw):
    """Ask for JSON and parse the first JSON object/array in the reply."""
    text, usage = chat(prompt, system=system, **kw)
    m = re.search(r"(\{.*\}|\[.*\])", text, re.S)
    if not m:
        raise ValueError(f"No JSON in model reply: {text[:200]}")
    return json.loads(m.group(1)), usage
