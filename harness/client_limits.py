#!/usr/bin/env python3
"""NOT YET TRUSTED: not part of the first night, and scripts/build_observed.py publishes no own-client limits row.
The review of own-clients (finding 11) found that it can take a local diagnostic or a quota answer for the
provider's input refusal, count a two-request answer as one accepted size, and stop short of the boundary when the
refusal names no window. A live run needs --untrusted until that is fixed.

The input limit of a login through its vendor's own client (docs/own-clients.md, sections 1, 3 and 4.4).
harness/limits.py stays the walk of plain requests; this one drives a client of harness/clients.py, one new session
per request, the prompt "Reply with just OK." + " hello" x N.

    python3 harness/client_limits.py --harness claude --model claude-haiku-5-5 --out results/<folder>/client-limits.jsonl \
        [--accepted 997000 --refused 1003000] [--dry-run]

The walk, per model:
1. One request far above the window (--hi, default 1,200,000 x " hello"): refused, so free.
2. One small accepted request (--small), and a second (five times that) where the refusal states no count: they give
   tokens per " hello" and the client's own overhead (its system prompt and tools).
3. Where the refusal names the window ("... N tokens > M maximum"): one accepted request about 1,000 tokens under it.
   Where it names nothing and the proxy's row is given: one request just under its input_accepted (--accepted) and
   one just over its input_refused (--refused), in tokens.
A request that is answered where a refusal was expected ends the walk (it cost about a million tokens of the plan).
A refusal of the client's own (Codex's message size) or a quota refusal ends the walk with no refusal row: only the
provider's refusal makes a row count (section 3). Codex CLI is refused up front: it caps a message at 1,048,576
characters, so its route's input limit stays measured through the proxy.

Every request is appended to --out as the rows scripts/build_observed.py reads (kind, model, n, status, promptTokens,
message, at), plus client and exit (the client's exit code; the client's version goes to the console only). status is 200 for an answered request;
for a refused one the HTTP status the client printed, or "refused".
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clients as C  # noqa: E402
import limits as L  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT = "Reply with just OK."
HI, SMALL, MARGIN = 1_200_000, 2_000, 1_000
STATUS = re.compile(r"(?:HTTP|status(?: code)?|API Error:?)\s*(\d{3})\b", re.I)


class End(Exception):
    pass


def prompt(n):
    return TEXT + " hello" * n


def status_of(text):
    m = STATUS.search(text or "")
    return int(m.group(1)) if m else "refused"


def scrub(text):
    """A refusal's text as kept: the home folder's path left out."""
    home = os.path.expanduser("~")
    return (text or "").replace(home, "~")[-1500:]


def walk(session, model, client_id, version, record, hi=HI, small=SMALL, accepted=None, refused=None, say=print,
         only_refusal=False):
    """The walk. `session.start(prompt)` gives (handle, Usage) or raises clients.Refused; `record(row)` keeps a row.
    Returns the rows written."""
    rows = []

    def send(kind, n, expect):
        try:
            _, u = session.start(prompt(n))
        except C.Refused as e:
            if e.kind in ("client-cap", "quota"):
                raise End(f"{kind} N={n:,}: {e.kind} refusal ({e.text[:200]}): the walk ends, no row")
            row = {"kind": kind, "model": model, "n": n, "status": status_of(e.text), "promptTokens": None,
                   "message": scrub(e.text), "exit": getattr(e, "code", None)}
        except C.ClientError as e:
            raise End(f"{kind} N={n:,}: the client failed ({str(e)[:200]}): the walk ends, no row")
        else:
            row = {"kind": kind, "model": model, "n": n, "status": 200, "promptTokens": u.total, "message": None, "exit": 0}
        row.update(at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), client=client_id)
        if version is not None:
            row["client_version"] = version
        rows.append(row)
        record(row)
        say(json.dumps(row)[:400])
        answered = row["status"] == 200
        if expect == "refused" and answered:
            raise End(f"{kind} N={n:,} was answered ({u.total:,} tokens), not refused: the walk ends here")
        if expect == "accepted" and not answered:
            raise End(f"{kind} N={n:,} was refused where an answer was expected: the walk ends here")
        return row

    try:
        top = send("context", hi, "refused")
        if only_refusal:
            say("--only-refusal: the walk ends after the refusal")
            return rows
        named = L.named_limit(top["message"] or "")
        # tokens = per x N + overhead (the client's own prompt and tools): from a small accepted request and the
        # refusal's own count, or from two small accepted requests.
        a = send("small", small, "accepted")
        counted = re.search(r"(\d[\d,]*)\s*tokens?\s*>", top["message"] or "")
        if counted:
            per = (int(counted.group(1).replace(",", "")) - a["promptTokens"]) / (hi - small)
        else:
            b = send("small", small * 5, "accepted")
            per = (b["promptTokens"] - a["promptTokens"]) / (small * 4)
        over = a["promptTokens"] - per * small
        if per <= 0:
            raise End("no tokens per \" hello\" from the requests so far")
        say(f"tokens = {per:g} x N + {over:,.0f}")
        if named:
            n = int((named - MARGIN - over) / per)
            say(f"window named: {named:,}; confirming at N={n:,}")
            send("confirm", n, "accepted")
            return rows
        say("the refusal names no window")
        if accepted:
            send("context", int((accepted - over) / per), "accepted")
        if refused:
            send("context", int((refused - over) / per) + 1, "refused")
    except End as e:
        say(str(e))
    return rows


def plan_text(harness, model, hi, small, accepted, refused):
    lines = [f"{harness} {model}: one new session per request, the prompt \"{TEXT}\" + \" hello\" x N",
             f"  1. N = {hi:,}: expected refused by the provider (free)",
             f"  2. N = {small:,} (accepted, small), and N = {small * 5:,} where the refusal states no count",
             "  3. if the refusal names the window M: one request about 1,000 tokens under M (accepted, about M tokens of the plan)"]
    if accepted:
        lines.append(f"     if it names nothing: one request of about {accepted:,} tokens (just under the proxy's input_accepted; accepted)")
    if refused:
        lines.append(f"     and one of about {refused:,} tokens (just over the proxy's input_refused; expected refused)")
    lines.append("  An answer where a refusal was expected, a quota refusal or a refusal of the client's own ends the walk.")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--harness", required=True, choices=[h for h, c in C.CLIENTS.items() if c.own])
    ap.add_argument("--model", required=True)
    ap.add_argument("--effort", default="low")
    ap.add_argument("--out", required=True)
    ap.add_argument("--hi", type=int, default=HI, help=f"N of the first request, far above the window (default {HI:,})")
    ap.add_argument("--small", type=int, default=SMALL)
    ap.add_argument("--accepted", type=int, help="the proxy's input_accepted for this model, in tokens")
    ap.add_argument("--refused", type=int, help="the proxy's input_refused for this model, in tokens")
    ap.add_argument("--client-home", default=os.environ.get("GROUNDTRUTH_CLIENT_HOME"))
    ap.add_argument("--only-refusal", action="store_true",
                    help="send only the first request (a smoke run: what the client prints for an input above the window)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan; run nothing, send nothing")
    ap.add_argument("--untrusted", action="store_true", help="run it although it is not yet trusted (see the top)")
    a = ap.parse_args(argv)
    if a.harness == "codex" and not a.only_refusal:
        raise SystemExit("codex: no input limit through Codex CLI (it caps a message at 1,048,576 characters before "
                         "sending it); the route's input limit stays measured through the proxy")
    print(plan_text(a.harness, a.model, a.hi, a.small, a.accepted, a.refused) if not a.only_refusal else
          f"{a.harness} {a.model}: one request, N = {a.hi:,} \" hello\" (expected refused, free); nothing else")
    if a.dry_run:
        print(f"every request appended to {a.out}. Dry run: nothing run, nothing sent.")
        return
    if not a.untrusted:
        raise SystemExit("harness/client_limits.py is not yet trusted (review finding 11): no live run without --untrusted")
    client = C.CLIENTS[a.harness](a.model, a.effort)
    home = C.state_folder(client, a.client_home, ROOT)
    env = client.environment(home)
    tmp = tempfile.mkdtemp(prefix=f"groundtruth-limits-{a.harness}-")
    writable = [home, env.get("HOME"), tmp]
    try:
        # The client's version goes to the console only, never into a row (it is the client's own text).
        print(f"client version: {client.version(env, writable=writable)}", file=sys.stderr)
        version = None
        session = C.Session(client, env=env, io=os.path.join(tmp, "io"), work=os.path.join(tmp, "work"), timeout=1800,
                            home=home, writable=writable)
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "a") as out:
            def record(row):
                out.write(json.dumps(row) + "\n")
                out.flush()
            walk(session, a.model, client.client_id, version, record, hi=a.hi, small=a.small,
                 accepted=a.accepted, refused=a.refused, only_refusal=a.only_refusal)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
