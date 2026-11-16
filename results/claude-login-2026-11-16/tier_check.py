#!/usr/bin/env python3
"""Which cache tier the Claude login wrote: one request per model and setting, read cache_creation from the usage.

    python3 results/claude-login-2026-11-16/tier_check.py <out.jsonl> <model> [<model> ...]

Anthropic's usage splits a cache write into ephemeral_5m_input_tokens and ephemeral_1h_input_tokens, so one write
shows the lifetime the request ended up asking for. The prompt is a plain numbered list (the probe's filler is
refused by Claude Haiku 5.5 on this login), unique per request, about 4,500 tokens, marked like the probe's:
one cache_control on the system block, without a ttl ("default") or with ttl 1h ("1h").
"""
import json, sys, time, uuid
sys.path.insert(0, "harness")
import limits as L

out, models = sys.argv[1], sys.argv[2:]
log = open(out, "a")
for model in models:
    for setting in ("default", "1h"):
        nonce = uuid.uuid4().hex[:12]
        text = f"Reference list {nonce}.\n" + "".join(f"Item {i}: the shop opens at nine and closes at five on weekdays.\n" for i in range(300))
        marker = {"type": "ephemeral"} if setting == "default" else {"type": "ephemeral", "ttl": "1h"}
        body = {"model": model, "max_tokens": 16, "system": [{"type": "text", "text": text, "cache_control": marker}],
                "messages": [{"role": "user", "content": "Reply with the single word OK."}]}
        code, data, secs = L.post("/v1/messages", body, timeout=120)
        usage = data.get("usage") or {}
        row = {"model": model, "setting": setting, "status": code, "seconds": round(secs, 1),
               "input_tokens": usage.get("input_tokens"), "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
               "cache_read_input_tokens": usage.get("cache_read_input_tokens"), "cache_creation": usage.get("cache_creation"),
               "message": None if code == 200 else L.message(data), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        log.write(json.dumps(row) + "\n"); log.flush(); print(json.dumps(row))
