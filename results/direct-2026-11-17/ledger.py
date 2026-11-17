#!/usr/bin/env python3
"""The cost ledger of this folder, from the usage the providers reported (logs/<run>.usage.jsonl, one line per reply,
written by the probe's --usage-log). Writes ledger.jsonl (every request: tokens as reported, cost, running total) and
ledger.md (per run, per model, per provider). Exits 3 when the total reaches the stop.

    python3 results/direct-2026-11-17/ledger.py [--stop 40]
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STOP = float(sys.argv[sys.argv.index("--stop") + 1]) if "--stop" in sys.argv else 40.0

# USD per million tokens, standard tier, global processing, short context (every prompt here is under 5,000 tokens).
# Sources, read 2026-11-17: OpenAI https://developers.openai.com/api/docs/pricing (Standard: input, cached input,
# 30m write, 12h write, output); Anthropic https://platform.claude.com/docs/en/about-claude/pricing (base input,
# 5m cache writes, 1h cache writes, cache hits, output). Both agree with providers.dev dataset 5fbc15e7ef2ae90b.
# chat-latest and gpt-audio-1.5 have no cache-write price: a write is billed as input there.
PRICES = {
    "gpt-6-luna": {"in": 0.10, "read": 0.01, "w30m": 0.125, "w12h": 0.25, "out": 0.50},
    "gpt-6.1-terra": {"in": 1.00, "read": 0.05, "w30m": 1.25, "w12h": 2.50, "out": 5.00},
    "gpt-6-sol": {"in": 2.00, "read": 0.20, "w30m": 2.50, "w12h": 5.00, "out": 10.00},
    "gpt-6-astra": {"in": 10.00, "read": 1.00, "w30m": 12.50, "w12h": 25.00, "out": 50.00},
    "chat-latest": {"in": 5.00, "read": 0.50, "w30m": 5.00, "w12h": 5.00, "out": 30.00},
    "gpt-audio-1.5": {"in": 2.50, "read": 2.50, "w30m": 2.50, "w12h": 2.50, "out": 10.00},
    "gpt-daybreak-blue-latest": {"in": 4.00, "read": 0.40, "w30m": 5.00, "w12h": 10.00, "out": 20.00},
    "gpt-daybreak-red-latest": {"in": 12.50, "read": 1.25, "w30m": 15.625, "w12h": 31.25, "out": 75.00},
    "gpt-6-cyber": {"in": 20.00, "read": 2.00, "w30m": 25.00, "w12h": 50.00, "out": 100.00},
    "claude-haiku-5-5": {"in": 0.10, "read": 0.01, "w5m": 0.125, "w1h": 0.20, "out": 0.50},
    "claude-sonnet-5-5": {"in": 2.00, "read": 0.10, "w5m": 2.50, "w1h": 4.00, "out": 10.00},
    "claude-opus-5-5": {"in": 4.00, "read": 0.20, "w5m": 5.00, "w1h": 8.00, "out": 20.00},
    "claude-fable-5-2": {"in": 8.00, "read": 0.20, "w5m": 10.00, "w1h": 16.00, "out": 40.00},
}


def n(x):
    return x if isinstance(x, (int, float)) else 0


def cost(model, u):
    """Returns (tokens dict, USD) for one usage object as reported."""
    p = PRICES[model]
    if model.startswith("claude"):
        cc = u.get("cache_creation") or {}
        w5, w1 = n(cc.get("ephemeral_5m_input_tokens")), n(cc.get("ephemeral_1h_input_tokens"))
        if not cc:
            w5 = n(u.get("cache_creation_input_tokens"))
        t = {"input": n(u.get("input_tokens")), "write_5m": w5, "write_1h": w1,
             "read": n(u.get("cache_read_input_tokens")), "output": n(u.get("output_tokens"))}
        usd = (t["input"] * p["in"] + w5 * p["w5m"] + w1 * p["w1h"] + t["read"] * p["read"] + t["output"] * p["out"]) / 1e6
        return t, usd
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
    return t, usd


rows = []
for path in sorted(glob.glob(os.path.join(HERE, "logs", "*.usage.jsonl"))):
    for line in open(path):
        if line.strip():
            rows.append(json.loads(line))
rows.sort(key=lambda r: r["at"])

total = 0.0
per_run, per_model, per_provider = {}, {}, {}
with open(os.path.join(HERE, "ledger.jsonl"), "w") as out:
    for r in rows:
        model = r["model"]
        provider = "anthropic" if model.startswith("claude") else "openai"
        if r.get("usage"):
            tokens, usd = cost(model, r["usage"])
        else:
            tokens, usd = None, 0.0  # a refused request reports no usage and is not billed
        total += usd
        out.write(json.dumps({"at": r["at"], "run": r["label"], "model": model, "status": r["status"], "tokens": tokens,
                              "prices_per_mtok": PRICES[model], "usd": round(usd, 6), "running_usd": round(total, 6)}) + "\n")
        for key, table in ((r["label"], per_run), (model, per_model), (provider, per_provider)):
            s = table.setdefault(key, {"requests": 0, "usd": 0.0, "model": model, "provider": provider})
            s["requests"] += 1
            s["usd"] += usd

with open(os.path.join(HERE, "ledger.md"), "w") as md:
    md.write("# Ledger\n\nComputed by `ledger.py` from the usage each reply reported (`logs/*.usage.jsonl`), at the prices "
             "listed in `ledger.py` (OpenAI's and Anthropic's pricing pages, read 2026-11-17). Every request is in "
             "`ledger.jsonl` with its tokens, price and the running total.\n\n")
    md.write(f"**Total: ${total:.4f}** of the ${STOP:.0f} stop, {len(rows)} requests.\n\n")
    for title, table in (("Provider", per_provider), ("Model", per_model), ("Run", per_run)):
        md.write(f"| {title} | Requests | USD |\n|---|---|---|\n")
        for key, s in sorted(table.items()):
            md.write(f"| {key} | {s['requests']} | {s['usd']:.4f} |\n")
        md.write("\n")
print(f"total ${total:.4f} over {len(rows)} requests; " + ", ".join(f"{k} ${v['usd']:.4f}" for k, v in sorted(per_provider.items())))
sys.exit(3 if total >= STOP else 0)
