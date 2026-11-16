#!/usr/bin/env python3
"""Input window of Devin models from their listed window, with at most two accepted large requests per model.

    python3 results/limits-2026-11-16/devin_walk.py <out.jsonl> <model>:<listed window>[:<tokens per " hello">] ...
    python3 results/limits-2026-11-16/devin_walk.py <out.jsonl> --recall <model> <filler sizes, comma-separated> [max output]
    python3 results/limits-2026-11-16/devin_walk.py <out.jsonl> --calibrate <model>:<N> ...

--calibrate: one small request (kind "calibrate") per model, so that a walk with a single accepted request also has
a second accepted size: the two give the tokens per " hello" and the overhead, which turn a refused N into tokens.
A quota or rate refusal stops it, as the walk.

Walk (Chat Completions format, "Reply with just OK." + " hello" x N, a 16-token reply; rows in the format of
harness/limits.py): one request about 20,000 tokens above the listed window (a refusal is free). If it is accepted,
the model accepts more than it lists and the walk stops there: it never sends larger requests. If it is refused,
one request just under the listed window (or under the limit the refusal names); if that is refused too, it walks
down in steps of 2.5 % of the window (to 75 % at most) until a size is accepted, then halves the gap to the smallest refused size until
a second size is accepted or the gap is under 8,000 tokens. A request with no answer inside the time limit, or any
other error, ends the model. A quota or rate refusal ends the whole walk, with no retry.

--recall: the both-ends request of ../limits-2026-11-13 (one code word before the filler and one after it; the
answer must name both), Responses format as there, five minutes each, one request per size, in the order given.
The first five rows of swe-2-recall.jsonl asked for 16 output tokens and got empty replies (spent on reasoning); the
rows with maxOutput 256 record the response's status and output token count too.
"""
import json, re, sys, time
sys.path.insert(0, "harness")
import limits as L

TIMEOUT = 600
QUOTA = re.compile(r"quota|rate.?limit|resource.?exhausted|usage limit|too many requests|exceeded your", re.I)


def write(log, row):
    log.write(json.dumps(row) + "\n"); log.flush(); print(json.dumps(row)[:400], flush=True)


def ask(log, model, n, kind="context", timeout=TIMEOUT):
    text = "Reply with just OK." + " hello" * n
    body = {"model": model, "max_tokens": 16, "messages": [{"role": "user", "content": text}]}
    started = time.time()
    try:
        code, data, secs = L.post("/v1/chat/completions", body, timeout=timeout)
    except Exception as err:  # no answer: a time limit or a dropped connection
        code, data, secs = None, {"error": f"no answer in {timeout} s ({type(err).__name__})"}, time.time() - started
    row = {"kind": kind, "model": model, "n": n, "status": code, "seconds": round(secs, 1),
           "promptTokens": L.prompt_tokens("chat", data) if code == 200 else None,
           "message": None if code == 200 else L.message(data), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    write(log, row)
    return row


class Stop(Exception):
    pass


def outcome(row):
    """'ok', 'refused', or raises Stop (quota: everything; anything else: this model)."""
    if row["status"] == 200:
        return "ok"
    msg = row["message"] or ""
    if row["status"] == 429 or QUOTA.search(msg):
        raise Stop("quota")
    if row["status"] in (400, 413, 422):
        return "refused"
    raise Stop("model")


def walk(log, model, listed, per):
    above = (listed + 20_000) // per
    r = ask(log, model, above)
    if outcome(r) == "ok":
        return f"accepted above the listed window: {r['promptTokens']} tokens; no refusal seen"
    named = L.named_limit(r["message"] or "")
    ceiling = min(listed, named) if named else listed
    refused, accepted, n_ok = above, None, 0
    n = (ceiling - 1_500) // per
    step = max(1, int(listed * 0.025) // per)
    while accepted is None:
        r = ask(log, model, n)
        if outcome(r) == "ok":
            accepted, n_ok = n, 1
        else:
            refused, n = n, n - step
            if n * per < listed * 0.75:
                return "nothing accepted down to 75 % of the listed window"
    while n_ok < 2 and (refused - accepted) * per > 8_000:
        mid = (accepted + refused) // 2
        r = ask(log, model, mid)
        if outcome(r) == "ok":
            accepted, n_ok = mid, n_ok + 1
        else:
            refused = mid
    return f"accepted N={accepted}, refused N={refused}"


def recall(log, model, sizes, max_output):
    for n in sizes:
        text = ("The first code word is APRICOT." + " hello" * n +
                "\nThe second code word is WALNUT. Reply with the two code words and nothing else.")
        body = {"model": model, "input": text, "max_output_tokens": max_output, "reasoning": {"effort": "low"}}
        started = time.time()
        try:
            code, data, secs = L.post("/v1/responses", body, timeout=300)
        except Exception as err:
            code, data, secs = None, {"error": f"no answer in 300 s ({type(err).__name__})"}, time.time() - started
        reply = None
        if code == 200:
            reply = " ".join(c.get("text", "") for o in data.get("output", []) if o.get("type") == "message"
                             for c in o.get("content", [])).strip()
        row = {"kind": "recall", "model": model, "n": n, "status": code, "seconds": round(secs, 1),
               "promptTokens": L.prompt_tokens("responses", data) if code == 200 else None, "reply": reply,
               "message": None if code == 200 else ("timed out" if code is None else L.message(data)),
               "maxOutput": max_output, "responseStatus": data.get("status") if code == 200 else None,
               "incomplete": data.get("incomplete_details") if code == 200 else None,
               "outputTypes": [o.get("type") for o in data.get("output", [])] if code == 200 else None,
               "outputTokens": (data.get("usage") or {}).get("output_tokens") if code == 200 else None,
               "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        write(log, row)
        if code not in (200, None) and (code == 429 or QUOTA.search(row["message"] or "")):
            sys.exit("quota or rate refusal: stopping")


def main():
    log = open(sys.argv[1], "a")
    if sys.argv[2] == "--calibrate":
        for spec in sys.argv[3:]:
            model, n = spec.split(":")
            row = ask(log, model, int(n), kind="calibrate")
            try:
                outcome(row)
            except Stop as stop:
                if str(stop) == "quota":
                    sys.exit(f"QUOTA STOP at {model}")
        return
    if sys.argv[2] == "--recall":
        recall(log, sys.argv[3], [int(x) for x in sys.argv[4].split(",")], int(sys.argv[5]) if len(sys.argv) > 5 else 16)
        return
    for spec in sys.argv[2:]:
        parts = spec.split(":")
        model, listed, per = parts[0], int(parts[1]), int(parts[2]) if len(parts) > 2 else 1
        try:
            print(f"RESULT {model}: {walk(log, model, listed, per)}", flush=True)
        except Stop as stop:
            if str(stop) == "quota":
                left = sys.argv[sys.argv.index(spec):]
                sys.exit(f"QUOTA STOP at {model}; not finished: {' '.join(s.split(':')[0] for s in left)}")
            print(f"RESULT {model}: stopped (no answer or unexpected status)", flush=True)


if __name__ == "__main__":
    main()
