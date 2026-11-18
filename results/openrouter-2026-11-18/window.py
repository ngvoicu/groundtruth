#!/usr/bin/env python3
"""The input window from a refusal only, for the models of plan.json whose two OpenRouter figures disagree
(context_length and top_provider.context_length): after that model's cache run, one Chat Completions request of
"Reply with just OK." + " hello" x 1,200,000 (about 1.2 million tokens, clearly above the larger figure), a 16-token
reply, `transforms: []` (no OpenRouter middle-out compression), straight to OpenRouter with this campaign's key
(key.py), through harness/limits.py's post(). One request per model, never a second; the answer goes to windows.jsonl
in the format of harness/limits.py (and its usage, if one were accepted, to logs/windows.usage.jsonl for the ledger).
    python3 results/openrouter-2026-11-18/window.py <model>
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "harness"))
import limits as L  # noqa: E402

N = 1_200_000
model = sys.argv[1]
out = os.path.join(HERE, "windows.jsonl")
if os.path.exists(out) and any(json.loads(x)["model"] == model for x in open(out) if x.strip()):
    sys.exit(f"{model}: its window request was sent already")
L.BASE = "https://openrouter.ai/api/v1"
L.KEY = subprocess.run([sys.executable, os.path.join(HERE, "key.py")], check=True, capture_output=True, text=True).stdout.strip()
body = {"model": model, "max_tokens": 16, "transforms": [], "messages": [{"role": "user", "content": "Reply with just OK." + " hello" * N}]}
at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
code, data, secs = L.post("/chat/completions", body, timeout=600)
row = {"kind": "context", "model": model, "n": N, "status": code, "seconds": round(secs, 1),
       "promptTokens": L.prompt_tokens("chat", data) if code == 200 else None,
       "message": None if code == 200 else L.message(data),
       "metadata": (data.get("error") or {}).get("metadata") if isinstance(data.get("error"), dict) else None,
       "upstream": data.get("provider") if code == 200 else None, "at": at}
open(out, "a").write(json.dumps(row) + "\n")
usage = {"at": at, "label": "windows", "model": model, "status": code}
if isinstance(data.get("usage"), dict):
    usage["usage"] = data["usage"]
if data.get("id"):
    usage["reply_id"] = data["id"]
open(os.path.join(HERE, "logs", "windows.usage.jsonl"), "a").write(json.dumps(usage) + "\n")
print(json.dumps(row)[:800])
