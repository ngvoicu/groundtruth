#!/usr/bin/env python3
"""Writes ledger.md: what every request of this folder used, per login, from the raw files alone.

    python3 results/logins-2026-11-17/ledger.py

Window walks: one row per request (limits-*.jsonl; a refusal reports no usage and costs nothing). Lifetime runs: one
row per run, the `spent` of its run file (probe 0.3.1: every answered request's prompt, cached and output tokens as
the replies report them), or of its .partial.json where the run was ended before it wrote its result.
No money is spent: every request went to a subscription login through CLIProxyAPI, which bills per plan, not per
token. The price column is therefore $0 (a plan's quota, not a price per token).
"""
import glob, json, os

D = os.path.dirname(os.path.abspath(__file__))
LOGIN = {"probe/claude-": "Claude login A", "probe/ag-": "Antigravity login", "probe/": "Codex login", "devin/": "Devin login", "muse-": "Meta login", "gemini-3.8": "Antigravity login"}


def login(model):
    return next(v for k, v in LOGIN.items() if model.startswith(k))


lines = ["# Ledger, 2026-11-17", "",
         "Price: $0 per token on every row: all requests went to subscription logins through CLIProxyAPI (plan quota, no",
         "per-token charge; the OpenAI and Claude API keys of the proxy served none of them, see README). Written by",
         "`ledger.py` from the raw files.", "",
         "## Window requests (one row per request)", "",
         "| Login | Model | N | Status | Input tokens (reply) | Output tokens (reply) | Price | Running input total of the login |",
         "|---|---|---|---|---|---|---|---|"]
total = {}
for f in sorted(glob.glob(f"{D}/limits-*.jsonl")):
    for line in open(f):
        r = json.loads(line)
        lg = login(r["model"])
        if r["status"] == 200:
            total[lg] = total.get(lg, 0) + r["promptTokens"]
        lines.append(f"| {lg} | `{r['model']}` | {r['n']:,} | {r['status']} | {r['promptTokens'] or '–'} | "
                     f"{r.get('outputTokens') if r.get('outputTokens') is not None else '–'} | $0 | {total.get(lg, 0):,} |")
lines += ["", "Refused requests report no usage (the Fable request above 1,000,000 tokens included). Devin's 502 on `devin/glm-5-3` and its second attempt (no answer) reported none either; they may still have",
          "counted against the plan (it ran 143 s).", "",
          "## Lifetime runs (one row per run)", "",
          "| Login | Run | Model | Status | Requests answered | Input tokens | of them cached | Output tokens | Price | Running input total of the login |",
          "|---|---|---|---|---|---|---|---|---|---|"]
files = {}
for f in glob.glob(f"{D}/L*-2026-*.json"):  # LD2's file is its last progress file, kept as *.ended-by-hand.json
    label = os.path.basename(f).split("-")[0]
    if label not in files or "ended-by-hand" in files[label]:
        files[label] = f
for label in sorted(files):
    j = json.load(open(files[label]))
    s = j.get("spent") or {}
    lg = login(j["model"])
    total[lg] = total.get(lg, 0) + s.get("promptTokens", 0)
    status = j["status"] + (" (ended by hand: its last progress file)" if "ended-by-hand" in files[label] else "")
    lines.append(f"| {lg} | {label} | `{j['model']}` | {status} | {s.get('requests', 0)} | {s.get('promptTokens', 0):,} | "
                 f"{s.get('cachedTokens', 0):,} | {s.get('outputTokens', 0):,} | $0 | {total[lg]:,} |")
lines += ["", "LD6 (`devin/grok-4-7`) left no run file: it was ended by hand while priming. The Devin login's request counter",
          "rose by 105 answered requests over the Devin lifetime runs; the files of LD1 to LD5 account for 100, so LD6 had about",
          "5 (its control: 3,860 input tokens per request). Its tokens are not in the totals below.", "",
          "## Per login", "", "| Login | Input tokens answered (windows and lifetime runs) |", "|---|---|"]
lines += [f"| {k} | {v:,} |" for k, v in sorted(total.items())]
open(f"{D}/ledger.md", "w").write("\n".join(lines) + "\n")
print("\n".join(lines[-len(total) - 2:]))
