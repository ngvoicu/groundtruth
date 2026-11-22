#!/usr/bin/env python3
"""The weekly night's money ledger for the API-key routes (the owner's caps of 2026-11-22: a safety ceiling of $10 a
week for all API-key routes together and $2 a run; docs/weekly-night.md).

One file per week, `$G/ledger/<monday>.jsonl` (mode 600), one line per event:
- `reserve`: before a run or a window request starts, its worst case, read from the prices of just before;
- `spent`: when it ends, what the replies' usage cost at those prices (the reservation is then released);
- `reported`: the provider's own figure for it, where the provider gives one (OpenRouter's `usage.cost`).

A cache run starts only when its worst case is at most the run ceiling and fits what is left of the week:
    left = week cap - max(spent, reported) - reserved (of the runs and window checks of the night).
A window check (the owner's decision of 2026-11-22, "A") is not held to the run ceiling: it is sent only when its
worst case (the cost if the vendor answers instead of refusing) fits what is left. A refused check is charged $0 and
its reservation released before the next is considered; an answered one is charged what it cost (its worst case
when the answer gives none). Window checks go first, one at a time; the cache runs reserve from what is left.
The API-key part stops when the spent or the reported figure reaches the week's cap.

    python3 harness/ledger.py [--week <monday>]       # the week's sums
"""
import datetime as dt
import json
import os
import sys
import time

WEEK_CAP = 10.0
RUN_CAP = 2.0


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
    def __init__(self, folder, date, week_cap=WEEK_CAP, run_cap=RUN_CAP, dry=False, clock=None):
        self.folder, self.week = folder, week_of(date)
        self.week_cap, self.run_cap, self.dry = float(week_cap), float(run_cap), dry
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

    def spent(self):
        return sum(n(r.get("usd")) for r in self.rows if r["kind"] == "spent")

    def reported(self):
        return sum(n(r.get("usd")) for r in self.rows if r["kind"] == "reported")

    def reserved(self):
        open_ = {}
        for r in self.rows:
            if r["kind"] == "reserve":
                open_[r["label"]] = n(r.get("usd"))
            elif r["kind"] in ("spent", "release"):
                open_.pop(r["label"], None)
        return sum(open_.values())

    def used(self):
        return max(self.spent(), self.reported())

    def left(self):
        return round(self.week_cap - self.used() - self.reserved(), 6)

    def exhausted(self):
        """The week's cap is reached by the ledger's own figure or by the provider's."""
        return self.used() >= self.week_cap

    def admit(self, label, route, model, estimate, window=False):
        """'ok' (and the worst case reserved), 'no-price' (no worst case can be worked out: not started),
        'over-run-cap' (a cache run above the run ceiling: not started) or 'over-week' (does not fit what is left).
        A window check (`window`) is held to the week only, never to the run ceiling."""
        if estimate is None:
            return "no-price"
        if not window and estimate > self.run_cap:
            return "over-run-cap"
        if estimate > self.left():
            return "over-week"
        self._add({"kind": "reserve", "label": label, "route": route, "model": model, "usd": round(estimate, 6)})
        return "ok"

    def settle(self, label, route, model, usd, reported=None):
        """What a run cost by the ledger's prices, and the provider's own figure where it gives one."""
        self._add({"kind": "spent", "label": label, "route": route, "model": model, "usd": round(usd, 6)})
        if reported:
            self._add({"kind": "reported", "label": label, "route": route, "model": model, "usd": round(reported, 6)})

    def open_reservations(self):
        """The labels reserved and neither settled nor released."""
        out = {}
        for r in self.rows:
            if r["kind"] == "reserve":
                out[r["label"]] = r
            elif r["kind"] in ("spent", "release"):
                out.pop(r["label"], None)
        return list(out)

    def release(self, label):
        """A reservation given back with nothing spent (a window request refused: refusals are not billed)."""
        self._add({"kind": "release", "label": label})

    def by_route(self):
        out = {}
        for r in self.rows:
            if r["kind"] == "spent":
                out[r["route"]] = out.get(r["route"], 0.0) + n(r.get("usd"))
        return out


def main():
    home = os.environ.get("GROUNDTRUTH_CLIENT_HOME")
    if not home:
        raise SystemExit("ledger: GROUNDTRUTH_CLIENT_HOME is not set")
    week = sys.argv[sys.argv.index("--week") + 1] if "--week" in sys.argv else time.strftime("%Y-%m-%d")
    led = Ledger(os.path.join(home, "ledger"), week, dry=True)
    print(f"week of {led.week}: spent ${led.spent():.4f}, reported ${led.reported():.4f}, reserved "
          f"${led.reserved():.4f}, left ${led.left():.4f} of ${led.week_cap:.2f}")
    for route, usd in sorted(led.by_route().items()):
        print(f"  {route}: ${usd:.4f}")


if __name__ == "__main__":
    main()
