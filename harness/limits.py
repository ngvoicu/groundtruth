#!/usr/bin/env python3
"""Measure a route's real context window and output limit, straight against a provider or through CLIProxyAPI.

    export CACHE_PROBE_KEY=...        # your own key; never on the command line, never written to a file
    python3 harness/limits.py --base-url https://api.openai.com/v1 --model gpt-6.1-sol --format responses \
        --lo 900000 --hi 930000 --out results/<folder>/limits.jsonl --dry-run

--base-url defaults to a local CLIProxyAPI (http://127.0.0.1:8317/v1); there, with no key in the environment, the
key is read from pi's CLIProxyAPI key file.

Context: prompts of " hello" x N (one token each on the tested tokenizers), binary search on N between --lo and --hi
until the accepted and rejected sizes are within --tol tokens. A rejection that names the limit ("... > 1000000
maximum") ends the search early. Only accepted requests cost quota; each asks for a 16-token reply.

Output: one request with a huge max_tokens; the error usually names the maximum. Free when rejected.

Every request is appended to --out as JSON lines. Usage tokens come from the response, so the reported window is the
provider's own count (prompt tokens incl. the small wrapper), not N.
"""
import argparse, json, os, re, sys, time, urllib.request, urllib.error

LOCAL = "http://127.0.0.1:8317/v1"
LOCAL_KEY_FILE = "~/.pi/agent/cliproxyapi.json"
BASE = LOCAL
KEY = None


def load_key(env="CACHE_PROBE_KEY"):
    """The key from the environment; on the local CLIProxyAPI with none set, from pi's key file (as before)."""
    global KEY
    KEY = os.environ.get(env)
    if not KEY and BASE == LOCAL and os.path.exists(os.path.expanduser(LOCAL_KEY_FILE)):
        KEY = json.load(open(os.path.expanduser(LOCAL_KEY_FILE)))["apiKey"]
    if not KEY:
        sys.exit(f"environment variable {env} is not set")
    return KEY


def post(path, body, timeout=600):
    # The scripts kept under results/ import this module and pass paths with /v1 in front: keep them working.
    if path.startswith("/v1/") and BASE.endswith("/v1"):
        path = path[3:]
    if KEY is None:
        load_key()
    # The key goes as a Bearer token and as x-api-key (Anthropic's API reads the second), as in the TypeScript probe.
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + KEY, "x-api-key": KEY,
                                          "Content-Type": "application/json", "anthropic-version": "2023-06-01"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}"), time.time() - t
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw), time.time() - t
        except Exception:
            return e.code, {"raw": raw[:2000]}, time.time() - t


def build(fmt, model, n, max_tokens=16, effort="low"):
    text = "Reply with just OK." + " hello" * n
    if fmt == "messages":
        return "/messages", {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": text}]}
    if fmt == "responses":
        return "/responses", {"model": model, "input": text, "max_output_tokens": max_tokens, "reasoning": {"effort": effort}}
    return "/chat/completions", {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": text}]}


def request(fmt, model, n, max_tokens=16, effort="low"):
    return post(*build(fmt, model, n, max_tokens, effort))


def prompt_tokens(fmt, data):
    u = data.get("usage") or {}
    if fmt == "messages":
        return (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
    return u.get("input_tokens") or u.get("prompt_tokens") or 0


def message(data):
    err = data.get("error")
    if isinstance(err, dict):
        return str(err.get("message") or err)
    return str(err or data.get("raw") or data)[:600]


LIMIT_PATTERNS = [
    r"\d[\d,]*\s*>\s*(\d[\d,]*),?\s*which is the maximum",          # Anthropic output: max_tokens: 10000000 > 128000, which is the maximum
    r"(\d[\d,]*)\s*tokens?\s*>\s*(\d[\d,]*)\s*maximum",          # Anthropic: prompt is too long: 1000123 tokens > 1000000 maximum
    r"maximum context length is\s*(\d[\d,]*)",                    # OpenAI-style
    r"context (?:window|length) (?:of|is)\s*(\d[\d,]*)",
    r"max(?:imum)?[^0-9]{0,40}(\d[\d,]{3,})",
]


def named_limit(msg):
    for pat in LIMIT_PATTERNS:
        m = re.search(pat, msg, re.I)
        if m:
            return int(m.groups()[-1].replace(",", ""))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--format", choices=["messages", "responses", "chat"], required=True)
    ap.add_argument("--lo", type=int, required=True, help="N expected to be accepted")
    ap.add_argument("--hi", type=int, required=True, help="N expected to be rejected")
    ap.add_argument("--tol", type=int, default=2000)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-output", action="store_true", help="skip the output-limit check")
    ap.add_argument("--no-confirm", action="store_true", help="when the error names the limit, don't send an accepted request")
    ap.add_argument("--base-url", default=LOCAL, help=f"API base URL including /v1 (default: a local CLIProxyAPI, {LOCAL})")
    ap.add_argument("--key-env", default="CACHE_PROBE_KEY", help="environment variable holding the key (default: CACHE_PROBE_KEY)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and one request body, send nothing")
    a = ap.parse_args()
    global BASE
    BASE = a.base_url.rstrip("/")
    if a.dry_run:
        path, body = build(a.format, a.model, 3)
        print(f"POST {BASE}{path}: {'one request with a 10,000,000-token output cap, then ' if not a.no_output else ''}"
              f"a request of N = {a.hi:,} \" hello\" (expected refused), then halving between N = {a.lo:,} and {a.hi:,} "
              f"until {a.tol:,} apart; every request appended to {a.out}. Only accepted requests cost quota.")
        print(json.dumps(body, indent=2).replace("hello hello hello", "hello × N"))
        return
    load_key(a.key_env)
    log = open(a.out, "a")

    def rec(kind, n, code, data, secs, extra=None):
        row = {"kind": kind, "model": a.model, "n": n, "status": code, "seconds": round(secs, 1),
               "promptTokens": prompt_tokens(a.format, data) if code == 200 else None,
               "message": None if code == 200 else message(data), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        if extra:
            row.update(extra)
        log.write(json.dumps(row) + "\n"); log.flush()
        print(json.dumps(row)[:400], flush=True)
        return row

    if not a.no_output:
        code, data, secs = request(a.format, a.model, 10, max_tokens=10_000_000)
        r = rec("output", 10, code, data, secs)
        if code != 200:
            lim = named_limit(r["message"] or "")
            print(f"OUTPUT LIMIT named: {lim}", flush=True)

    lo, hi = a.lo, a.hi
    lo_tokens = None
    # Make sure hi is rejected; the rejection may name the window.
    code, data, secs = request(a.format, a.model, hi)
    r = rec("context", hi, code, data, secs)
    if code == 200:
        print("hi was accepted; raise --hi", flush=True)
        return
    named = named_limit(r["message"] or "")
    if named:
        print(f"CONTEXT LIMIT named: {named}", flush=True)
        if a.no_confirm:
            return
        # Confirm just under the named limit. The error's own count gives the tokens per " hello" (2 on Claude's
        # tokenizer); keep ~1k tokens of room for the wrapper and the reply.
        counted = re.search(r"(\d[\d,]*)\s*tokens?\s*>", r["message"] or "")
        per = int(counted.group(1).replace(",", "")) / hi if counted else 1.0
        n = int((named - 1000) / per)
        code, data, secs = request(a.format, a.model, n)
        rec("confirm", n, code, data, secs, {"named": named})
        return
    while hi - lo > a.tol:
        mid = (lo + hi) // 2
        code, data, secs = request(a.format, a.model, mid)
        r = rec("context", mid, code, data, secs)
        if code == 200:
            lo, lo_tokens = mid, r["promptTokens"]
        elif code in (400, 413, 422) or "context" in (r["message"] or "").lower() or "too long" in (r["message"] or "").lower():
            hi = mid
            n2 = named_limit(r["message"] or "")
            if n2:
                print(f"CONTEXT LIMIT named: {n2}", flush=True)
        else:
            print(f"unexpected status {code}; stopping", flush=True)
            return
    print(f"CONTEXT: accepted N={lo} ({lo_tokens} prompt tokens), rejected N={hi}", flush=True)


if __name__ == "__main__":
    main()
