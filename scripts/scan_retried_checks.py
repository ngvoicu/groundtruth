#!/usr/bin/env python3
"""Find published checks that were sent more than once (a retried check measures a re-send, not the age).

    python3 scripts/scan_retried_checks.py [--root <checkout with the local logs>] [--json]

Sources, per run of observed/manifest.json (runs and excluded):
- the TypeScript probe's console log, results/<folder>/logs/<label>.log (local, mostly not committed): a
  `retry in Ns: <error>` line is attributed to the next check or control line it precedes (`  15m r2: warm (…)`,
  `  control warm (…)`); before probe 0.3.5 a check and a priming could share the retry loop;
- the usage log, results/<folder>/logs/<label>.usage.jsonl (0.3.1 and later): a failed reply followed by another reply
  for the same sample key (`sample`, from 0.3.4);
- harness/probe.py's raw file: a `retry` event before a `check` event (before the own-client rules a check was tried
  up to three times).

A retry after HTTP 429 or 402 is a refusal before the request was processed; any other error (5xx, a lost reply,
"no usage in response") may have reached the model, and the re-send then reads what the first try wrote. A check
whose final attempt failed (ERROR) is not counted by the builder and is reported apart.
"""
import argparse
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAMP = re.compile(r"^\[(\d\d:\d\d:\d\d)\] ?(.*)$")
RETRY = re.compile(r"retry in (\d+)s: (.*)")
CHECK = re.compile(r"^\s*(\d+(?:\.\d+)?[smh]) r(\d+): (warm|cold|ERROR)")
CONTROL = re.compile(r"^\s*control (warm|COLD)")


def kind_of(error):
    m = re.match(r"HTTP (\d{3})", error)
    if m and m.group(1) in ("429", "402"):
        return "refused"  # refused before the request was processed
    if re.search(r"dial tcp|utls: dial|no such host|connection refused", error):
        return "not-sent"  # the connection to the provider was never made
    return "may-have-reached"


def scan_log(path):
    """[(target, outcome, [errors])] for every check or control line preceded by retries."""
    lines, out, pending = [], [], []
    with open(path, errors="replace") as f:
        for raw in f:
            m = STAMP.match(raw.rstrip("\n"))
            if m:
                lines.append(m.group(2))
            elif lines:
                lines[-1] += " " + raw.strip()
    for text in lines:
        r = RETRY.search(text)
        if r:
            pending.append(r.group(2)[:160])
            continue
        c, k = CHECK.match(text), CONTROL.match(text)
        if pending and (c or k):
            out.append((f"{c.group(1)} r{c.group(2)}" if c else "control", (c.group(3) if c else k.group(1)).lower(), pending))
        elif pending:
            out.append(("(priming or other)", "-", pending))
        pending = []
    return out


def scan_usage(path):
    rows = []
    with open(path) as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    out = []
    for i, r in enumerate(rows[:-1]):
        nxt = rows[i + 1]
        if r.get("status") != 200 and r.get("sample") and nxt.get("sample") == r.get("sample"):
            out.append((r["sample"], "retried", [f"HTTP {r.get('status')}"]))
    return out


def scan_harness(path):
    out, pending = [], []
    with open(path) as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("event") == "retry":
                pending.append(str(e.get("error"))[:160])
            elif e.get("event") in ("check", "prime") and pending:
                if e["event"] == "check":
                    out.append((e.get("age"), "warm" if e.get("warm") else "cold", pending))
                pending = []
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT, help="the checkout whose results/*/logs hold the console logs")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    with open(os.path.join(ROOT, "observed/manifest.json")) as f:
        manifest = json.load(f)
    entries = [(r["id"], r["file"], "runs") for r in manifest["runs"]]
    for e in manifest["excluded"]:
        m = re.search(r"(results/[^\s)]+?\.jsonl?)\b", e.get("reason", ""))
        if m:
            entries.append((e["id"], m.group(1), "excluded"))
            continue
        if "/" in e["id"] and " " not in e["id"]:
            folder, name = e["id"].split("/", 1)
            found = sorted(glob.glob(os.path.join(a.root, "results", folder, name + "-20*.json"))) or \
                sorted(glob.glob(os.path.join(a.root, "results", folder, name + ".jsonl")))
            if found:
                entries.append((e["id"], os.path.relpath(found[0], a.root), "excluded"))
    found, without_log, nolog = [], 0, []
    for rid, path, where in entries:
        folder = os.path.dirname(path)
        hits, sources = [], []
        if path.endswith(".jsonl"):
            p = os.path.join(a.root, path)
            if os.path.exists(p):
                hits += [("harness",) + h for h in scan_harness(p)]
                sources.append("raw")
        else:
            try:
                with open(os.path.join(a.root, path)) as f:
                    label = json.load(f).get("label")
            except (OSError, ValueError):
                label = None
            if label:
                log = os.path.join(a.root, folder, "logs", label + ".log")
                usage = os.path.join(a.root, folder, "logs", label + ".usage.jsonl")
                if os.path.exists(log):
                    hits += [("log",) + h for h in scan_log(log)]
                    sources.append("log")
                if os.path.exists(usage):
                    hits += [("usage",) + h for h in scan_usage(usage)]
                    sources.append("usage")
        if not sources:
            without_log += 1
            nolog.append(rid)
        for source, target, outcome, errors in hits:
            if target == "(priming or other)":
                continue
            kinds = sorted({kind_of(x) for x in errors})
            found.append({"id": rid, "in": where, "source": source, "check": target, "outcome": outcome,
                          "tries": len(errors) + 1, "errors": kinds, "first_error": errors[0][:100]})
    if a.json:
        print(json.dumps({"retried": found, "runs_without_a_log": nolog}, indent=1))
        return
    for x in found:
        counted = x["outcome"] not in ("error",)
        print(f"{x['id']:40} [{x['in']}] {x['check']:10} {x['outcome']:5} tries {x['tries']} "
              f"{'/'.join(x['errors']):16} {'counted' if counted else 'not counted'}: {x['first_error']}")
    print(f"{len(found)} retried checks; {without_log} runs with no log to read: {', '.join(nolog)}")


if __name__ == "__main__":
    main()
