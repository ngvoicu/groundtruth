#!/usr/bin/env python3
"""Writes ledger.md: what every request of this folder used, per login, from the raw files alone.

    python3 results/logins-long-2026-11-17/ledger.py

Field tests (fields-*.jsonl): one row per request, the usage of its reply. Lifetime runs: one row per run, the
`spent` of its run file (every answered request's prompt, cached and output tokens as the replies report them), or of
its .partial.json while it is still running. A run with no file (AG4: ended before its control was answered) used
nothing that was answered.
Price: $0 per token. Every request went to a subscription login through CLIProxyAPI (plan quota, no per-token
charge); each reply's X-CPA-AUTH-KIND was `oauth` (a login), none `apikey`, see the column.
"""
import glob, json, os

D = os.path.dirname(os.path.abspath(__file__))
LOGIN = [("probe/", "Codex login"), ("devin/", "Devin login"), ("muse-", "Meta login"), ("gemini-", "Antigravity login"),
         ("gpt-oss-", "Antigravity login")]


def login(model):
    return next(v for k, v in LOGIN if model.startswith(k))


total = {}
lines = ["# Ledger, 2026-11-17 (logins-long)", "",
         "Price: $0 per token on every row (subscription logins through CLIProxyAPI: plan quota, no per-token charge;",
         "every answer's `X-CPA-AUTH-KIND` was `oauth`). Written by `ledger.py` from the raw files; rerun it to update",
         "the rows of runs still running.", "",
         "## Field tests (one row per request)", "",
         "| Login | Model | Sent | Status | Answered by | Input tokens (reply) | of them cached | Output tokens | Price | Running input total of the login |",
         "|---|---|---|---|---|---|---|---|---|---|"]
for f in sorted(glob.glob(f"{D}/fields-*.jsonl")):
    for line in open(f):
        r = json.loads(line)
        lg = login(r["model"])
        u = r.get("usage") or {}
        inp = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0) if "cache_read_input_tokens" in u or "cache_creation_input_tokens" in u else u.get("input_tokens", 0)
        cached = (u.get("input_tokens_details") or {}).get("cached_tokens", u.get("cache_read_input_tokens", 0))
        total[lg] = total.get(lg, 0) + inp
        sent = r["sent"] if len(r["sent"]) < 70 else r["sent"][:67] + "…"
        lines.append(f"| {lg} | `{r['model']}` | `{sent}` | {r['status']} | {r['auth_kind']} | {inp:,} | {cached:,} | "
                     f"{u.get('output_tokens', '–')} | $0 | {total[lg]:,} |")
lines += ["", "## Lifetime runs (one row per run)", "",
          "| Login | Run | Model | Status | Requests answered | Answered by | Input tokens | of them cached | Output tokens | Price | Running input total of the login |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
files = {}
for f in glob.glob(f"{D}/*-2026-11-*.json"):
    label = os.path.basename(f).split("-")[0]
    if label not in files or not f.endswith(".partial.json"):
        files[label] = f
for label in sorted(files):
    j = json.load(open(files[label]))
    s = j.get("spent") or {}
    lg = login(j["model"])
    total[lg] = total.get(lg, 0) + s.get("promptTokens", 0)
    kinds = ", ".join(f"{k} ×{v}" for k, v in (s.get("replyHeaders") or {}).get("x-cpa-auth-kind", {}).items())
    status = j["status"] + (" (progress file: still running)" if files[label].endswith(".partial.json") else "")
    lines.append(f"| {lg} | {label} | `{j['model']}` | {status} | {s.get('requests', 0)} | {kinds} | {s.get('promptTokens', 0):,} | "
                 f"{s.get('cachedTokens', 0):,} | {s.get('outputTokens', 0):,} | $0 | {total[lg]:,} |")
lines += ["", "AG4 (`gemini-3.8-flash-tiered`) left no run file: every request was answered 503 (Google's server capacity)",
          "until it was ended after 10 minutes; nothing was answered.", "",
          "## Per login", "", "| Login | Input tokens answered |", "|---|---|"]
lines += [f"| {k} | {v:,} |" for k, v in sorted(total.items())]
open(f"{D}/ledger.md", "w").write("\n".join(lines) + "\n")
print("\n".join(lines[-len(total) - 2:]))
