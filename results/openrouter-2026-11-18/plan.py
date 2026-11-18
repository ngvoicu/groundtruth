#!/usr/bin/env python3
"""Builds plan.json, the list of cache runs of this folder and their order, from the website's API and OpenRouter's
model list (both read now, kept in sources/):
- providers.dev: OpenRouter entries of type chat, released on or after 2026-08-17, with no cache evaluation (short and
  long both 0);
- OpenRouter /api/v1/models: still offered, the price (USD per token) and the two context figures.
Order (the brief): the seven big releases first, in the owner's order; then the others from the cheapest input price
to the dearest; last OpenAI's `-pro` variants and the `~…-latest` aliases, cheapest first. Worst case of a run: 87
requests (control 3, priming 42, checks 42) of 3,000 prompt tokens each, every one billed at the higher of the input
and the cache-write price, plus 32 output tokens each.
    python3 results/openrouter-2026-11-18/plan.py
"""
import json
import os
import re
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "sources")
os.makedirs(SRC, exist_ok=True)
BIG = ["openai/gpt-6.2-sol", "google/gemini-4-hydrogen", "google/gemini-4-carbon", "qwen/qwen4-max", "meta/muse-ember",
       "anthropic/claude-fable-5.2", "openai/gpt-6.2-astra"]
REQUESTS, PROMPT, OUTPUT = 87, 3000, 32
# Anthropic caches only marked content: as the measured OpenRouter row of the same lab (openrouter-direct-v0.2/R1b),
# a top-level cache_control and a per-sample session_id, no ttl.
ANTHROPIC = ["--body-extra", '{"cache_control":{"type":"ephemeral"}}', "--session-id"]


def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "groundtruth"}), timeout=60))


rows, offset, meta = [], 0, None
while True:
    page = get(f"https://providers.dev/api/v1/entries?provider=openrouter&limit=200&offset={offset}")
    meta = meta or page["meta"]
    rows += page["data"]
    if page.get("next_offset") is None:
        break
    offset = page["next_offset"]
sel = [r for r in rows if r["type"] == "chat" and (r.get("release_date") or "") >= "2026-08-17"
       and r["cache_lifetime"]["short"]["evaluations"] == 0 and r["cache_lifetime"]["long"]["evaluations"] == 0]
models = {m["id"]: m for m in get("https://openrouter.ai/api/v1/models")["data"]}
read_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

site = [{"ref": r["ref"], "model": r["model"], "name": r["name"], "release_date": r["release_date"],
         "price_in": r["price_in"], "price_out": r["price_out"], "context": r["context"], "input": r["input"],
         "canonical_id": r.get("canonical_id"), "family": r.get("family"),
         "cache": r["cache"], "cache_lifetime_short": r["cache_lifetime"]["short"],
         "cache_lifetime_long": r["cache_lifetime"]["long"]} for r in sel]
json.dump({"read_at": read_at, "meta": meta, "total_entries": len(rows), "selected": len(sel), "entries": site},
          open(os.path.join(SRC, "providers-dev-entries.json"), "w"), indent=1)
offered = {m: {k: models[m].get(k) for k in ("id", "canonical_slug", "name", "created", "context_length", "pricing",
                                             "top_provider", "endpoints", "reasoning", "supported_parameters")}
           for m in (r["model"] for r in sel) if m in models}
json.dump({"read_at": read_at, "models": offered}, open(os.path.join(SRC, "openrouter-models.json"), "w"), indent=1)


def price(m, k):
    v = models[m]["pricing"].get(k)
    return float(v) * 1e6 if v not in (None, "") else None


def worst(m):
    return (REQUESTS * PROMPT * max(price(m, "prompt"), price(m, "input_cache_write") or 0)
            + REQUESTS * OUTPUT * price(m, "completion")) / 1e6


def last(m):
    return m.startswith("~") or (m.startswith("openai/") and m.endswith("-pro"))


def label(m):
    return re.sub(r"[^\w.-]+", "_", m.replace("~", "alias-").replace("/", "--").replace(":", "-"))


names = [r["model"] for r in sel]
missing = [m for m in names if m not in models]
rest = [m for m in names if m not in BIG and m in models]
mid = sorted((m for m in rest if not last(m)), key=lambda m: (price(m, "prompt"), worst(m), m))
tail = sorted((m for m in rest if last(m)), key=lambda m: (price(m, "prompt"), worst(m), m))
plan = []
for i, m in enumerate([b for b in BIG if b in models] + mid + tail, 1):
    mm = models[m]
    ctx, top = mm.get("context_length"), (mm.get("top_provider") or {}).get("context_length")
    plan.append({
        "n": i, "label": label(m), "model": m,
        "group": "big" if m in BIG else ("last" if last(m) else ("free" if m.endswith(":free") else "rest")),
        "args": ANTHROPIC if m.startswith("anthropic/") else [],
        "options": {"cache_control": {"type": "ephemeral"}, "session_id": True} if m.startswith("anthropic/") else {},
        "worst_usd": round(worst(m), 4),
        "window": ctx != top, "context_length": ctx, "top_provider_context_length": top,
    })
json.dump({"read_at": read_at, "dataset": meta.get("dataset_version"), "missing_on_openrouter": missing,
           "requests": REQUESTS, "prompt_tokens": PROMPT, "output_tokens": OUTPUT, "runs": plan},
          open(os.path.join(HERE, "plan.json"), "w"), indent=1)
print(f"{len(sel)} entries (dataset {meta.get('dataset_version')}), {len(plan)} planned, missing on OpenRouter: {missing}; "
      f"worst case total ${sum(p['worst_usd'] for p in plan):.2f}; window requests: {[p['model'] for p in plan if p['window']]}")
