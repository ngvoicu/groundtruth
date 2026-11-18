#!/usr/bin/env python3
"""What the proxy does with a lifetime field: one small request per variant, sequential (fields-*.jsonl).

    python3 fieldtest.py <out.jsonl> <path> <model> '<json extra>' ['<json extra>' ...]

Ran on 2026-11-17 18:23 - 18:25 local (build ngvoicu-local-c52243ab), from this folder:
  fields-codex.jsonl /v1/responses probe/gpt-6.1-sol '{}' '{"prompt_cache_retention":"24h"}'
      '{"prompt_cache_retention":"bogus-retention"}' '{"prompt_cache_options":{"ttl":"12h"}}'
      '{"prompt_cache_options":{"ttl":"bogus-ttl"}}' '{"unknown_field_xyz":"1"}', then twice each a 2,400-word prompt
      with prompt_cache_retention "24h" and with prompt_cache_options.ttl "12h" (__filler, own prompt_cache_key)
  fields-devin.jsonl /v1/responses devin/swe-2 '{}' '{"prompt_cache_retention":"24h"}'
      '{"prompt_cache_retention":"bogus-retention"}' '{"prompt_cache_options":{"ttl":"bogus-ttl"}}' '{"unknown_field_xyz":"1"}'
  fields-devin.jsonl /v1/messages devin/claude-haiku-5-5 '{"__ttl":"1h"}' '{"__ttl":"bogus-ttl"}'

path: /v1/responses or /v1/messages. Prints status, X-CPA-AUTH-KIND, usage and the start of an error. No key printed.
"""
import json, sys, time, urllib.request, urllib.error
import os


def client_key():  # the proxy's client key, read here and never printed or written
    return json.load(open(os.path.expanduser("~/.pi/agent/cliproxyapi.json")))["apiKey"]


out, path, model, *variants = sys.argv[1:]
key = client_key()
for v in variants:
    extra = json.loads(v)
    if path.endswith("/responses"):
        body = {"model": model, "input": [{"role": "user", "content": [{"type": "input_text", "text": "Reply with the single word OK."}]}],
                "max_output_tokens": 16, "store": False, "stream": False}
    else:
        body = {"model": model, "max_tokens": 16, "messages": [{"role": "user", "content": [
            {"type": "text", "text": "Reply with the single word OK.", "cache_control": {"type": "ephemeral"}}]}]}
    # extra: top-level fields; "__ttl" sets the ttl of the Messages cache marker
    if "__filler" in extra:  # a cacheable prompt: N filler words before the question
        import random
        rnd = random.Random(extra.pop("__filler_salt", "x"))
        words = " ".join(rnd.choice(["alpha", "bravo", "cedar", "delta", "ember", "fjord", "gamma", "harbor"]) for _ in range(extra.pop("__filler")))
        if path.endswith("/responses"):
            body["input"][0]["content"][0]["text"] = words + "\n\nReply with the single word OK."
        else:
            body["messages"][0]["content"][0]["text"] = words + "\n\nReply with the single word OK."
    if "__ttl" in extra:
        body["messages"][0]["content"][0]["cache_control"]["ttl"] = extra.pop("__ttl")
    body.update(extra)
    req = urllib.request.Request("http://127.0.0.1:8317" + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + key, "x-api-key": key, "Content-Type": "application/json",
                                          "anthropic-version": "2023-06-01"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            status, kind, text = r.status, r.headers.get("X-CPA-AUTH-KIND"), r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        status, kind, text = e.code, e.headers.get("X-CPA-AUTH-KIND"), e.read().decode(errors="replace")
    usage = None
    try:
        usage = json.loads(text).get("usage")
    except Exception:
        pass
    row = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "path": path, "model": model, "sent": v, "status": status,
           "auth_kind": kind, "usage": usage, "error": None if status == 200 else text[:300], "seconds": round(time.time() - t0, 1)}
    print(json.dumps(row))
    open(out, "a").write(json.dumps(row) + "\n")
    time.sleep(2)
