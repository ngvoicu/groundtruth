#!/usr/bin/env python3
"""The weekly night's money ledger for the API-key routes: a **record**, never a limit (the owner, 2026-11-26: "I can
pay money just to have things done"; the caps of $10 a week and $2 a run of 2026-11-22 are retired). Nothing is
skipped, shortened or refused for what it costs; the ledger says what each run cost, per night and per week, and what
the night expected before it started (docs/weekly-night.md).

One file per week, `$G/ledger/<monday>.jsonl` (mode 600), one line per event, each with its night's date (`night`):
- `estimate`: before a night starts, what its API-key runs may cost at most (the cache runs' worst case; the window
  checks', which cost nothing when refused as expected, apart);
- `start`: when a run or a window request starts, its worst case from the prices of just before (null: no price
  known; it runs all the same);
- `spent`: when it ends, what the replies' usage cost at those prices;
- `reported`: the provider's own figure for it, where the provider gives one (OpenRouter's `usage.cost`);
- `release`: a start that ended with nothing to record.

    python3 harness/ledger.py [--week <monday>]       # the week's sums, per night and per route
"""
import datetime as dt
import json
import os
import sys
import time


def week_of(date):
    """The Monday of the week of `date` (YYYY-MM-DD): the ledger's key."""
    d = dt.date.fromisoformat(date)
    return (d - dt.timedelta(days=d.weekday())).isoformat()


def n(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else 0


def tokens(u):
    """A reply's usage in the four billed kinds (Responses, Chat Completions or Messages), as on 18 November."""
    d = u.get("input_tokens_details") or u.get("prompt_tokens_details") or {}
    if "cache_read_input_tokens" in u or "cache_creation_input_tokens" in u:  # Messages: input excludes the cache
        read, write = n(u.get("cache_read_input_tokens")), n(u.get("cache_creation_input_tokens"))
        return {"plain": n(u.get("input_tokens")), "read": read, "write": write, "output": n(u.get("output_tokens"))}
    total = n(u.get("input_tokens")) if "input_tokens" in u else n(u.get("prompt_tokens"))
    read = n(d.get("cached_tokens"))
    write = n(d.get("cache_write_tokens"))
    out = n(u.get("output_tokens")) if "output_tokens" in u else n(u.get("completion_tokens"))
    return {"plain": max(0, total - read - write), "read": read, "write": write, "output": out}


def cost(prices, t):
    """USD of one reply: prices in USD per million tokens {in, read, write, out}; a missing read or write price is
    the input price."""
    pin = prices.get("in") or 0.0
    read = prices.get("read") if prices.get("read") is not None else pin
    write = prices.get("write") if prices.get("write") is not None else pin
    return (t["plain"] * pin + t["write"] * write + t["read"] * read + t["output"] * (prices.get("out") or 0.0)) / 1e6


def usage_cost(path, prices):
    """(ledger USD, provider-reported USD, requests) of a usage log (the TypeScript probe's --usage-log)."""
    usd = rep = 0.0
    count = 0
    try:
        f = open(path)
    except FileNotFoundError:
        return 0.0, 0.0, 0
    with f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            count += 1
            u = row.get("usage")
            if isinstance(u, dict):
                usd += cost(prices, tokens(u))
                rep += n(u.get("cost"))
    return usd, rep, count


class Ledger:
    def __init__(self, folder, date, dry=False, clock=None):
        self.folder, self.week, self.dry = folder, week_of(date), dry
        self.clock = clock or (lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        self.path = os.path.join(folder, f"{self.week}.jsonl")
        self.rows = self._read()

    def _read(self):
        try:
            with open(self.path) as f:
                return [json.loads(x) for x in f if x.strip()]
        except FileNotFoundError:
            return []

    def _add(self, row):
        row = {"at": self.clock(), **row}
        self.rows.append(row)
        if self.dry:
            return
        os.makedirs(self.folder, mode=0o700, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "a") as f:
            f.write(json.dumps(row) + "\n")

    def _sum(self, kind, night=None):
        return sum(n(r.get("usd")) for r in self.rows
                   if r["kind"] == kind and (night is None or r.get("night") == night))

    def spent(self, night=None):
        return self._sum("spent", night)

    def reported(self, night=None):
        return self._sum("reported", night)

    def used(self, night=None):
        """What the week (or one night) cost: the higher of our figure and the provider's."""
        return max(self.spent(night), self.reported(night))

    def night_spent(self, night):
        return self.used(night)

    def estimate(self, night, cache, windows, values):
        """Before a night starts: what its API-key runs may cost at most (for the record)."""
        self._add({"kind": "estimate", "night": night, "usd": round(cache, 6), "windows_usd": round(windows, 6),
                   "values": values})

    def estimates(self):
        """night -> its estimate row (the last one written)."""
        return {r.get("night"): r for r in self.rows if r["kind"] == "estimate"}

    def start(self, label, route, model, estimate, night=None):
        """A run or a window request starting, with its worst case (None: no price known). Never a refusal."""
        self._add({"kind": "start", "night": night, "label": label, "route": route, "model": model,
                   "usd": round(estimate, 6) if estimate is not None else None})

    def settle(self, label, route, model, usd, reported=None, night=None):
        """What a run cost by the ledger's prices, and the provider's own figure where it gives one."""
        self._add({"kind": "spent", "night": night, "label": label, "route": route, "model": model,
                   "usd": round(usd, 6)})
        if reported:
            self._add({"kind": "reported", "night": night, "label": label, "route": route, "model": model,
                       "usd": round(reported, 6)})

    def open_starts(self):
        """The labels started and neither settled nor released."""
        out = {}
        for r in self.rows:
            if r["kind"] == "start":
                out[r["label"]] = r
            elif r["kind"] in ("spent", "release"):
                out.pop(r["label"], None)
        return list(out)

    def release(self, label):
        """A start given back with nothing to record."""
        self._add({"kind": "release", "label": label})

    def by_route(self, night=None):
        out = {}
        for r in self.rows:
            if r["kind"] == "spent" and (night is None or r.get("night") == night):
                out[r["route"]] = out.get(r["route"], 0.0) + n(r.get("usd"))
        return out

    def nights(self):
        """The nights the week's file names, in order."""
        return sorted({r["night"] for r in self.rows if r.get("night")})


def main():
    home = os.environ.get("GROUNDTRUTH_CLIENT_HOME")
    if not home:
        raise SystemExit("ledger: GROUNDTRUTH_CLIENT_HOME is not set")
    if "--week" not in sys.argv:
        raise SystemExit("ledger: --week <a day of the week> (YYYY-MM-DD)")
    led = Ledger(os.path.join(home, "ledger"), sys.argv[sys.argv.index("--week") + 1], dry=True)
    est = led.estimates()
    print(f"week of {led.week}: spent ${led.used():.4f} (ours ${led.spent():.4f}, "
          f"the providers' ${led.reported():.4f})")
    for night in led.nights():
        e = est.get(night)
        print(f"  night {night}: spent ${led.used(night):.4f}" +
              (f", estimated at most ${n(e.get('usd')):.4f} before it started" if e else ""))
        for route, usd in sorted(led.by_route(night).items()):
            print(f"    {route}: ${usd:.4f}")


if __name__ == "__main__":
    main()
