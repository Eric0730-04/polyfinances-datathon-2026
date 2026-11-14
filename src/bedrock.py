"""Thin wrapper around Amazon Bedrock (Converse API).

Credentials: uses the AWS profile in $AWS_PROFILE (e.g. `team10`) or the
standard AWS_* environment variables. Never commit credentials.
"""
import json
import os
import re
import time

import boto3
from botocore.config import Config

REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
DEFAULT_MODEL = os.getenv("BEDROCK_MODEL_ID", "global.amazon.nova-2-lite-v1:0")

_client = None


def client():
    global _client
    if _client is None:
        _client = boto3.Session(region_name=REGION).client(
            "bedrock-runtime", config=Config(retries={"max_attempts": 6, "mode": "adaptive"}, read_timeout=120))
    return _client


def chat(prompt, system=None, model_id=DEFAULT_MODEL, max_tokens=2048, temperature=0.2):
    """Single-turn prompt. Returns (text, meta) where meta has usage, latency_ms and model."""
    kwargs = {
        "modelId": model_id,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
    }
    if system:
        kwargs["system"] = [{"text": system}]
    t0 = time.time()
    resp = client().converse(**kwargs)
    text = "".join(c.get("text", "") for c in resp["output"]["message"]["content"])
    return text, {"usage": resp["usage"], "latency_ms": int((time.time() - t0) * 1000), "model": model_id}


def _extract_json(text):
    text = re.sub(r"```(?:json)?", "", text)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError(f"No JSON in model reply: {text[:200]}")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj


def chat_json(prompt, system=None, retries=2, **kw):
    """Ask for JSON; parse it, retrying with a reminder if the reply is malformed."""
    last_err = None
    for attempt in range(retries + 1):
        p = prompt if attempt == 0 else prompt + "\n\nYour previous reply was not valid JSON. Reply with ONLY the JSON object."
        text, meta = chat(p, system=system, **kw)
        try:
            return _extract_json(text), meta
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
    raise ValueError(f"Model did not return valid JSON after {retries + 1} tries: {last_err}")
