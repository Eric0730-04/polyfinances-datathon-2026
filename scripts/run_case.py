"""Run one persona + request through the pipeline from the command line.

Usage: AWS_PROFILE=team10 python scripts/run_case.py maya "I want to put $15,000 of my condo savings into XSP"
Saves the full trace to runs/<run_id>.json.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.orchestrator import run  # noqa: E402

pid, req = sys.argv[1], sys.argv[2]
persona = json.loads((ROOT / "personas" / f"{pid}.json").read_text())
trace = run(persona, req, on_step=lambda s: print("…", s, flush=True))
out = ROOT / "runs"
out.mkdir(exist_ok=True)
(out / f"{trace['run_id']}.json").write_text(json.dumps(trace, indent=2, default=str))
r = trace["result"]
print(f"\n[{r['verdict']}] ({r.get('confidence')}) {r.get('headline')}")
print(r.get("plain_summary"))
print("grounding:", trace.get("grounding", {}).get("summary"))
if r.get("verdict_adjustment"):
    print("ADJUSTED:", r["verdict_adjustment"])
for k in ("key_reasons", "no_longer_valid_if", "variants"):
    print(f"\n{k}:")
    for x in r.get(k, []):
        print(" -", x)
print(f"\n{trace['elapsed_s']}s, {trace.get('total_tokens')} tokens, trace runs/{trace['run_id']}.json")
