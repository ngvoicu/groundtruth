#!/usr/bin/env python3
"""Narrow a published input window (accepted / refused) with as few accepted requests as possible.

    python3 results/logins-2026-11-17/window_walk.py <out.jsonl> <spec> ...
    spec = model:format:per:overhead:round:accepted:refused:cap
      format     chat (Devin, as ../limits-2026-11-16/devin_walk.py) or responses (Codex login, as ../limits-2026-11-13)
      per        tokens per " hello" (2 on Claude's tokenizer, else 1); overhead: the tokens of the rest of the request,
                 from the earlier walk; together they turn a size N into tokens (tokens = per x N + overhead)
      round      the round number the published gap suggests (the documented or listed window)
      accepted, refused   the published bounds, in tokens
      cap        the most accepted requests allowed for the model

Requests are "Reply with just OK." + " hello" x N with a 16-token reply, rows in the format of harness/limits.py.
A refusal costs nothing and an accepted request its whole size, so the walk probes from above: first one request just
over the round number (round + 300 tokens), then one just under it (round - 500 tokens), both always (so that the
walk's own file holds an accepted and a refused size, and the refused size can be converted with this walk's own
count), then it halves the gap
between the largest accepted and the smallest refused size, until the gap is 1,500 tokens or less or the model's cap
of accepted requests is reached. Sizes are worked out with the overhead of the earlier walk, or of this walk once a
request of it was accepted. The walk never sends a size outside the published gap.

Stops: a quota or rate refusal (HTTP 429, or a message naming a quota or a usage limit) ends the whole walk at once,
with no retry. A request with no answer inside the time limit, or with an answer the walk does not expect (any
other status), ends that model without a retry (it may have cost quota; the row says so). On 2026-11-17 the first
version of this script ended the whole Devin walk at such an answer (GLM-5.3, 502); the walk was started again for
the models it had not reached (run-windows.sh, second Devin command).
"""
import json, re, sys, time
sys.path.insert(0, "harness")
import limits as L

TIMEOUT = 600
GAP = 1_500
QUOTA = re.compile(r"quota|rate.?limit|usage.?limit|resource.?exhausted|too many requests|model_cooldown|exceeded your", re.I)


class StopAll(Exception):
    pass


def ask(log, model, fmt, n):
    text = "Reply with just OK." + " hello" * n
    if fmt == "responses":
        path, body = "/v1/responses", {"model": model, "input": text, "max_output_tokens": 16, "reasoning": {"effort": "low"}}
    else:
        path, body = "/v1/chat/completions", {"model": model, "max_tokens": 16, "messages": [{"role": "user", "content": text}]}
    started = time.time()
    try:
        code, data, secs = L.post(path, body, timeout=TIMEOUT)
    except Exception as err:  # no answer: a time limit or a dropped connection
        code, data, secs = None, {"error": f"no answer in {TIMEOUT} s ({type(err).__name__})"}, time.time() - started
    usage = (data.get("usage") or {}) if code == 200 else {}
    row = {"kind": "context", "model": model, "n": n, "status": code, "seconds": round(secs, 1),
           "promptTokens": L.prompt_tokens(fmt, data) if code == 200 else None,
           "outputTokens": (usage.get("output_tokens") if fmt == "responses" else usage.get("completion_tokens")) if code == 200 else None,
           "message": None if code == 200 else L.message(data), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    log.write(json.dumps(row) + "\n"); log.flush(); print(json.dumps(row)[:400], flush=True)
    return row


def walk(log, spec):
    model, fmt, per, over, rnd, acc, ref, cap = spec.split(":")
    per, over, rnd, acc, ref, cap = int(per), int(over), int(rnd), int(acc), int(ref), int(cap)
    lo, hi, n_ok, overhead = acc, ref, 0, over        # bounds in tokens, as published

    def size(tokens):                                  # N whose request comes to at most `tokens`
        return (tokens - overhead) // per

    plan = [rnd + 300, rnd - 500]
    while n_ok < cap and (plan or hi - lo > GAP):
        target = plan.pop(0) if plan else (lo + hi) // 2
        if not lo < target < hi:
            continue
        n = size(target)
        r = ask(log, model, fmt, n)
        if r["status"] == 200:
            n_ok += 1
            overhead = r["promptTokens"] - per * n     # this walk's own count from now on
            lo = r["promptTokens"]
            if lo >= ref:
                return f"ACCEPTED {lo} tokens, at or above the published refusal {ref}: recorded, not chased"
        elif r["status"] is None:
            return f"no answer in {TIMEOUT} s at N={n}: model ended (the request may have cost quota)"
        elif r["status"] == 429 or QUOTA.search(r["message"] or ""):
            raise StopAll(f"quota or rate refusal at {model} N={n}")
        elif r["status"] in (400, 413, 422):
            refused_tokens = per * n + overhead
            if refused_tokens <= acc:
                return f"REFUSED {refused_tokens} tokens, at or below the published acceptance {acc}: recorded, not chased"
            hi = refused_tokens
        else:  # e.g. Devin's 502 "empty completion": neither accepted nor refused, and not retried
            return f"unexpected status {r['status']} at N={n}: model ended, not retried (the request may have cost quota)"
    return f"accepted {lo} tokens, refused {hi} tokens (converted with overhead {overhead}), gap {hi - lo}, {n_ok} accepted"


def main():
    log = open(sys.argv[1], "a")
    specs = sys.argv[2:]
    for i, spec in enumerate(specs):
        try:
            print(f"RESULT {spec.split(':')[0]}: {walk(log, spec)}", flush=True)
        except StopAll as stop:
            left = " ".join(s.split(":")[0] for s in specs[i:])
            sys.exit(f"STOP: {stop}; not finished: {left}")


if __name__ == "__main__":
    main()
