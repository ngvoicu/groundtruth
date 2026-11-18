#!/usr/bin/env python3
"""The input window of GPT-6.2 Sol and Astra on the Codex login, from a refusal only: one request per model.

    python3 results/logins-gpt-6-2-2026-11-17/window.py results/logins-gpt-6-2-2026-11-17/limits-codex.jsonl

The request of ../logins-2026-11-17/window_walk.py (Responses format, low effort, "Reply with just OK." + " hello" x N,
a 16-token reply; rows in the format of harness/limits.py), at N = 929,989: 930,000 tokens with the 11-token overhead
of the Codex login's earlier walks, clearly above the 922,300 tokens at which GPT-6.1 Sol, GPT-6 Astra and GPT-6 Luna
were refused (and the 921,500 accepted) on 2026-11-17. One request per model, never repeated, no smaller request.
Sent only after both lifetime runs had ended. A quota or rate refusal (HTTP 429, or a message naming a quota or a
usage limit) ends the script at once.
"""
import json, re, sys, time
sys.path.insert(0, "harness")
import limits as L

N = 929_989
QUOTA = re.compile(r"quota|rate.?limit|usage.?limit|resource.?exhausted|too many requests|model_cooldown|exceeded your", re.I)
log = open(sys.argv[1], "a")
for model in ("probe/gpt-6.2-sol", "probe/gpt-6.2-astra"):
    body = {"model": model, "input": "Reply with just OK." + " hello" * N, "max_output_tokens": 16, "reasoning": {"effort": "low"}}
    started = time.time()
    try:
        code, data, secs = L.post("/v1/responses", body, timeout=600)
    except Exception as err:
        code, data, secs = None, {"error": f"no answer in 600 s ({type(err).__name__})"}, time.time() - started
    usage = (data.get("usage") or {}) if code == 200 else {}
    row = {"kind": "context", "model": model, "n": N, "status": code, "seconds": round(secs, 1),
           "promptTokens": L.prompt_tokens("responses", data) if code == 200 else None,
           "outputTokens": usage.get("output_tokens") if code == 200 else None,
           "message": None if code == 200 else L.message(data), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    log.write(json.dumps(row) + "\n"); log.flush(); print(json.dumps(row)[:400], flush=True)
    if code == 429 or (code != 200 and QUOTA.search(row["message"] or "")):
        sys.exit(f"STOP: quota or rate refusal at {model}")
