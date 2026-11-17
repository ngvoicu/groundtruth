#!/usr/bin/env python3
"""One request clearly above the documented window per model, to read the input window from the refusal.

    CACHE_PROBE_KEY="$(python3 results/gpt-6-2-2026-11-17/key.py openai)" \
        python3 results/gpt-6-2-2026-11-17/refusal.py [--dry-run] gpt-6.2-sol gpt-6.2-astra

Request: "Reply with just OK." + " hello" x N (one token per " hello" on OpenAI's tokenizer), Responses format, a
16-token reply, low effort: the request of harness/limits.py, sent straight to https://api.openai.com/v1.
N = 1,100,000, above both documented figures of the older GPT-6 models (input 922,000, context 1,050,000).
A refusal costs nothing. Nothing is sent near the limit, and nothing is sent twice.

Stops (no retry, no further model):
  - the request was accepted (HTTP 200): it cost money; its usage goes to logs/refusal.usage.jsonl for ledger.py;
  - a quota, rate or billing refusal, or any answer other than a refusal of the request's size.
Models are sent in the order given, so the cheaper one (Sol) goes first: Astra is only sent once Sol was refused.
Each request is one row of refusal.jsonl, in the format of harness/limits.py, with the limit the message names.
"""
import json, os, re, sys, time

sys.path.insert(0, "harness")
import limits as L

HERE = os.path.dirname(os.path.abspath(__file__))
N = 1_100_000
STOP = re.compile(r"quota|rate.?limit|billing|insufficient|too many requests|exceeded your", re.I)

args = sys.argv[1:]
dry = "--dry-run" in args
models = [a for a in args if a != "--dry-run"]
L.BASE = "https://api.openai.com/v1"
if dry:
    path, body = L.build("responses", models[0] if models else "<model>", 3)
    print(f"POST {L.BASE}{path} once per model, in this order: {models}; N = {N:,} \" hello\" (about {N:,} tokens)")
    print(json.dumps(body, indent=2).replace("hello hello hello", "hello × N"))
    sys.exit(0)
L.load_key()
out = open(os.path.join(HERE, "refusal.jsonl"), "a")
usage_log = open(os.path.join(HERE, "logs", "refusal.usage.jsonl"), "a")
for model in models:
    at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        code, data, secs = L.request("responses", model, N)
    except Exception as err:  # no answer: a time limit or a dropped connection
        code, data, secs = None, {"error": f"no answer ({type(err).__name__})"}, 0.0
    msg = None if code == 200 else L.message(data)
    row = {"kind": "context", "model": model, "n": N, "status": code, "seconds": round(secs, 1),
           "promptTokens": L.prompt_tokens("responses", data) if code == 200 else None,
           "message": msg, "error_type": (data.get("error") or {}).get("type") if isinstance(data.get("error"), dict) else None,
           "error_code": (data.get("error") or {}).get("code") if isinstance(data.get("error"), dict) else None,
           "error_param": (data.get("error") or {}).get("param") if isinstance(data.get("error"), dict) else None,
           "named": L.named_limit(msg or "") if msg else None, "at": at}
    out.write(json.dumps(row) + "\n"); out.flush()
    usage_log.write(json.dumps({"at": at, "label": "refusal", "model": model, "status": code,
                                "usage": data.get("usage") if code == 200 else None}) + "\n"); usage_log.flush()
    print(json.dumps(row)[:1000], flush=True)
    if code == 200:
        print("ACCEPTED: it cost money; stopping before any further model", flush=True); break
    if code == 429 or STOP.search(msg or "") or code not in (400, 413, 422):
        print("not a size refusal: stopping, no retry", flush=True); break
