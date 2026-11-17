#!/usr/bin/env python3
"""Claude Fable 5.2 on Claude login A: one request just above 1,000,000 tokens and nothing else (no accepted large
request: Fable is the dearest model on the plan). Messages format, "Reply with just OK." + " hello" x 500,500 (two
tokens per " hello" on Claude's tokenizer), a 16-token reply, through the temporary alias probe/claude-fable-5-2.
The row goes to limits-claude.jsonl in the format of harness/limits.py.
    python3 results/logins-2026-11-17/fable_window.py
"""
import json, sys, time
sys.path.insert(0, "harness")
import limits as L

n = 500_500
model = "probe/claude-fable-5-2"
body = {"model": model, "max_tokens": 16, "messages": [{"role": "user", "content": "Reply with just OK." + " hello" * n}]}
code, data, secs = L.post("/v1/messages", body, timeout=600)
row = {"kind": "context", "model": model, "n": n, "status": code, "seconds": round(secs, 1),
       "promptTokens": L.prompt_tokens("messages", data) if code == 200 else None,
       "message": None if code == 200 else L.message(data), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
open("results/logins-2026-11-17/limits-claude.jsonl", "a").write(json.dumps(row) + "\n")
print(json.dumps(row)[:600])
