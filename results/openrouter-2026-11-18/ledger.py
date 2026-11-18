#!/usr/bin/env python3
"""The cost ledger of this folder, from the usage each reply reported (logs/<run>.usage.jsonl, written by the probe's
--usage-log, and logs/windows.usage.jsonl), at OpenRouter's prices: those read just before the run started
(offered.jsonl), else those of sources/openrouter-models.json. Uncached input at the input price, cache writes at the
cache-write price (the input price where OpenRouter lists none), cache reads at the read price (the input price where
it lists none), output (reasoning included) at the output price. OpenRouter's own figure for each reply (usage.cost)
is summed beside it. Writes ledger.jsonl (every request) and ledger.md (sums). Exits 3 when the total reaches the stop.

    python3 results/openrouter-2026-11-18/ledger.py [--stop 18]
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STOP = 18.0


def n(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else 0


def prices():
    """model -> USD per million tokens {in, read, write, out}: the reading at launch wins over the plan's snapshot."""
    table = {}

    def put(model, p):
        f = lambda k: float(p[k]) * 1e6 if p.get(k) not in (None, "") else None
        pin = f("prompt") or 0.0
        table[model] = {"in": pin, "read": f("input_cache_read") if f("input_cache_read") is not None else pin,
                        "write": f("input_cache_write") if f("input_cache_write") is not None else pin,
                        "out": f("completion") or 0.0}

    for model, m in json.load(open(os.path.join(HERE, "sources", "openrouter-models.json")))["models"].items():
        put(model, m["pricing"])
    path = os.path.join(HERE, "offered.jsonl")
    if os.path.exists(path):
        for line in open(path):
            row = json.loads(line)
            if row.get("pricing"):
                put(row["model"], row["pricing"])
    return table


def tokens(u):
    """The usage as reported, in the four billed kinds. Responses (input_tokens) or Chat Completions (prompt_tokens)."""
    d = u.get("input_tokens_details") or u.get("prompt_tokens_details") or {}
    total = n(u.get("input_tokens")) if "input_tokens" in u else n(u.get("prompt_tokens"))
    read = n(d.get("cached_tokens"))
    write = n(d.get("cache_write_tokens")) or n(u.get("cache_creation_input_tokens"))
    out = n(u.get("output_tokens")) if "output_tokens" in u else n(u.get("completion_tokens"))
    od = u.get("output_tokens_details") or u.get("completion_tokens_details") or {}
    return {"prompt": total, "plain": max(0, total - read - write), "write": write, "read": read, "output": out,
            "reasoning": n(od.get("reasoning_tokens"))}


def cost(p, t):
    return (t["plain"] * p["in"] + t["write"] * p["write"] + t["read"] * p["read"] + t["output"] * p["out"]) / 1e6


def rows():
    out = []
    for path in sorted(glob.glob(os.path.join(HERE, "logs", "*.usage.jsonl"))):
        for line in open(path):
            if line.strip():
                out.append(json.loads(line))
    out.sort(key=lambda r: r["at"])
    return out


def compute(write=False):
    table = prices()
    total = reported = 0.0
    per_run, per_model = {}, {}
    lines = []
    for r in rows():
        model = r.get("model")
        u = r.get("usage")
        t = tokens(u) if u else None
        usd = cost(table[model], t) if t and model in table else 0.0  # a refused request reports no usage, no cost
        rep = n((u or {}).get("cost"))
        total += usd
        reported += rep
        lines.append({"at": r["at"], "run": r["label"], "model": model, "status": r.get("status"),
                      "upstream": r.get("reply_provider"), "tokens": t, "prices_per_mtok": table.get(model),
                      "usd": round(usd, 7), "openrouter_cost": rep, "running_usd": round(total, 6)})
        for key, tab in ((r["label"], per_run), (model, per_model)):
            s = tab.setdefault(key, {"requests": 0, "usd": 0.0, "openrouter_cost": 0.0, "prompt": 0, "output": 0})
            s["requests"] += 1
            s["usd"] += usd
            s["openrouter_cost"] += rep
            if t:
                s["prompt"] = max(s["prompt"], t["prompt"])
                s["output"] = max(s["output"], t["output"])
    if write:
        with open(os.path.join(HERE, "ledger.jsonl"), "w") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")
        readings = []
        kr = os.path.join(HERE, "key-readings.jsonl")
        if os.path.exists(kr):
            readings = [json.loads(x) for x in open(kr) if x.strip()]
        with open(os.path.join(HERE, "ledger.md"), "w") as md:
            md.write("# Ledger\n\nComputed by `ledger.py` from the usage each reply reported (`logs/*.usage.jsonl`), at "
                     "OpenRouter's prices read before each run (`offered.jsonl`; `sources/openrouter-models.json` "
                     "otherwise). Every request is in `ledger.jsonl` with its tokens, upstream, price, OpenRouter's own "
                     "cost figure and the running total.\n\n")
            md.write(f"**Total: ${total:.4f}** by the ledger (OpenRouter's own per-reply `usage.cost` summed: "
                     f"${reported:.4f}), {len(lines)} requests, stop at ${STOP:.0f}.\n\n")
            if readings:
                md.write("What OpenRouter reported as used by the key (`GET /api/v1/key`, `key-readings.jsonl`):\n\n"
                         "| At (UTC) | Usage USD | Limit | Note |\n|---|---|---|---|\n")
                for k in readings:
                    md.write(f"| {k['at']} | {k.get('usage')} | {k.get('limit')} | {k.get('note') or ''} |\n")
                md.write("\n")
            for title, tab in (("Model", per_model), ("Run", per_run)):
                md.write(f"| {title} | Requests | USD (ledger) | USD (OpenRouter) |\n|---|---|---|---|\n")
                for key, s in sorted(tab.items()):
                    md.write(f"| `{key}` | {s['requests']} | {s['usd']:.4f} | {s['openrouter_cost']:.4f} |\n")
                md.write("\n")
    return {"total": total, "reported": reported, "requests": len(lines), "per_run": per_run, "per_model": per_model}


if __name__ == "__main__":
    stop = float(sys.argv[sys.argv.index("--stop") + 1]) if "--stop" in sys.argv else STOP
    s = compute(write=True)
    print(f"total ${s['total']:.4f} (OpenRouter's own figure ${s['reported']:.4f}) over {s['requests']} requests")
    sys.exit(3 if s["total"] >= stop else 0)
