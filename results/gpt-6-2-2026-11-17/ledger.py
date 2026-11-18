#!/usr/bin/env python3
"""The cost ledger of this folder, from the usage OpenAI reported (logs/<run>.usage.jsonl, one line per reply,
written by the probe's --usage-log, and logs/refusal.usage.jsonl, written by refusal.py). Writes ledger.jsonl (every
request: tokens as reported, cost, running total) and ledger.md (per run, per model). Exits 3 when the total reaches
the stop. As ../direct-2026-11-17/ledger.py, OpenAI only.

    python3 results/gpt-6-2-2026-11-17/ledger.py [--stop 12]
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STOP = float(sys.argv[sys.argv.index("--stop") + 1]) if "--stop" in sys.argv else 12.0

# USD per million tokens, Standard tier, global processing. Source, read 2026-11-17 at about 20:50 UTC:
# https://developers.openai.com/api/docs/pricing (Standard: input, cached input, 30m write, 12h write, output), the
# same as the model pages (developers.openai.com/api/docs/models/gpt-6.2-sol, .../gpt-6.2-astra) and models.dev.
# Short context: <= 272K input tokens; above it, the long-context row applies to the whole request.
PRICES = {
    "gpt-6.2-sol": {"in": 2.00, "read": 0.10, "w30m": 2.50, "w12h": 5.00, "out": 10.00},
    "gpt-6.2-astra": {"in": 8.00, "read": 0.40, "w30m": 10.00, "w12h": 20.00, "out": 40.00},
}
LONG = {
    "gpt-6.2-sol": {"in": 4.00, "read": 0.20, "w30m": 5.00, "w12h": 10.00, "out": 15.00},
    "gpt-6.2-astra": {"in": 16.00, "read": 0.80, "w30m": 20.00, "w12h": 40.00, "out": 60.00},
}


def n(x):
    return x if isinstance(x, (int, float)) else 0


def cost(model, u):
    """Returns (tokens dict, prices used, USD) for one usage object as reported."""
    p = LONG[model] if n(u.get("input_tokens")) > 272_000 else PRICES[model]
    d = u.get("input_tokens_details") or {}
    wd = d.get("cache_write_tokens_details") or {}
    w12 = n(wd.get("ttl_12h_tokens"))
    wtotal = n(d.get("cache_write_tokens"))
    w30 = wtotal - w12
    read = n(d.get("cached_tokens"))
    plain = n(u.get("input_tokens")) - read - wtotal
    t = {"input_total": n(u.get("input_tokens")), "plain": plain, "write_30m": w30, "write_12h": w12, "read": read,
         "output": n(u.get("output_tokens")),
         "reasoning": n((u.get("output_tokens_details") or {}).get("reasoning_tokens"))}
    usd = (plain * p["in"] + w30 * p["w30m"] + w12 * p["w12h"] + read * p["read"] + t["output"] * p["out"]) / 1e6
    return t, p, usd


rows = []
for path in sorted(glob.glob(os.path.join(HERE, "logs", "*.usage.jsonl"))):
    for line in open(path):
        if line.strip():
            rows.append(json.loads(line))
rows.sort(key=lambda r: r["at"])

total = 0.0
per_run, per_model = {}, {}
with open(os.path.join(HERE, "ledger.jsonl"), "w") as out:
    for r in rows:
        model = r["model"]
        if r.get("usage"):
            tokens, prices, usd = cost(model, r["usage"])
        else:
            tokens, prices, usd = None, PRICES[model], 0.0  # a refused request reports no usage and is not billed
        total += usd
        out.write(json.dumps({"at": r["at"], "run": r["label"], "model": model, "status": r["status"], "tokens": tokens,
                              "prices_per_mtok": prices, "usd": round(usd, 6), "running_usd": round(total, 6)}) + "\n")
        for key, table in ((r["label"], per_run), (model, per_model)):
            s = table.setdefault(key, {"requests": 0, "usd": 0.0})
            s["requests"] += 1
            s["usd"] += usd

with open(os.path.join(HERE, "ledger.md"), "w") as md:
    md.write("# Ledger\n\nComputed by `ledger.py` from the usage each reply reported (`logs/*.usage.jsonl`), at the prices "
             "listed in `ledger.py` (OpenAI's pricing page, read 2026-11-17). Every request is in `ledger.jsonl` with its "
             "tokens, price and the running total.\n\n")
    md.write(f"**Total: ${total:.4f}** of the ${STOP:.0f} stop, {len(rows)} requests.\n\n")
    for title, table in (("Model", per_model), ("Run", per_run)):
        md.write(f"| {title} | Requests | USD |\n|---|---|---|\n")
        for key, s in sorted(table.items()):
            md.write(f"| {key} | {s['requests']} | {s['usd']:.4f} |\n")
        md.write("\n")
print(f"total ${total:.4f} over {len(rows)} requests; " + ", ".join(f"{k} ${v['usd']:.4f}" for k, v in sorted(per_model.items())))
sys.exit(3 if total >= STOP else 0)
