#!/usr/bin/env python3
"""One client's request budget, shared by every run of a night (docs/own-clients.md, "Pacing").

On 2026-11-23 nineteen Devin runs primed their waves at once on one account, and Devin refused seven of them with
"Reached request rate limit … Your limit will reset in 2 seconds (at 11:15 UTC)". From then on every run of a client
that has a budget (PACE_RPM) asks this module before each request it sends:

- at most `rpm` requests of the client in any 60 seconds, all runs of the night together;
- two requests at least 60 / `rpm` seconds apart, so that the runs' waves are spread and never bunch;
- primings use at most `rpm - reserve` of the 60 seconds: the rest is kept for checks, whose time is their age.

The shared state is a small JSON file of the recent request times beside a lock file, under the night's folder
(<client-home>/night-<date>/pacing/<client>.json and .lock, mode 600, folder 700), read and written under an
exclusive `flock`: kept across processes. `plan()` runs the night's runs on a simulated clock with the same pacer and
the real loop (harness/probe.py run_probe), for `--dry-run`'s expected times; it sends nothing.
"""
import contextlib
import json
import os
import random
import threading

WINDOW = 60.0
# The budget per client, requests per minute (night.py --pace devin=N changes it). Devin: see docs/own-clients.md,
# "Pacing", for the count it comes from. Codex: none (no rate refusal seen).
PACE_RPM = {"devin": 24}


def reserve_of(rpm):
    """Requests per minute kept for checks: a quarter of the budget, at least one (none for a budget of one)."""
    return max(1, rpm // 4) if rpm > 1 else 0


class MemoryStore:
    """The shared state in memory (one process: the plan's simulation, the tests)."""

    def __init__(self):
        self.state, self.mutex = {"times": []}, threading.Lock()

    @contextlib.contextmanager
    def locked(self):
        with self.mutex:
            yield self.state


class FileStore:
    """The shared state of one client in <folder>/<client>.json, under an exclusive flock on <folder>/<client>.lock.
    The folder is made by the caller (private, mode 700); both files are made mode 600 and never through a link."""

    def __init__(self, folder, client):
        self.path = os.path.join(folder, client + ".json")
        self.lock = os.path.join(folder, client + ".lock")

    @contextlib.contextmanager
    def locked(self):
        import fcntl
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(self.lock, os.O_RDWR | os.O_CREAT | nofollow, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                with open(self.path) as f:
                    state = json.load(f)
                if not isinstance(state, dict) or not isinstance(state.get("times"), list):
                    state = {"times": []}
            except (OSError, ValueError):
                state = {"times": []}
            yield state
            tmp = self.path + f".{os.getpid()}.tmp"
            wfd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | nofollow, 0o600)
            with os.fdopen(wfd, "w") as f:
                json.dump(state, f)
            os.replace(tmp, self.path)
        finally:
            os.close(fd)


class Pacer:
    """`acquire(kind)` returns once a request of `kind` (\"prime\" or \"check\") may be sent, and records it; the seconds
    it waited are returned. `clock` has now() and sleep() (harness/probe.py's Clock, or a simulated one)."""

    def __init__(self, store, rpm, clock, reserve=None, jitter=0.5, rng=None):
        if rpm < 1:
            raise ValueError("a request budget of at least 1 per minute")
        self.store, self.rpm, self.clock = store, rpm, clock
        self.reserve = reserve_of(rpm) if reserve is None else reserve
        self.gap = WINDOW / rpm
        self.jitter, self.rng = jitter, rng or random.Random()

    def wait_for(self, times, now, kind, checks_waiting=False):
        """Seconds before a request of `kind` may go, given the recent request times (0: now). A priming also waits
        while a check of any run is waiting for its turn (`checks_waiting`): checks go first."""
        recent = sorted(t for t in times if t > now - WINDOW)
        limit = self.rpm if kind == "check" else max(1, self.rpm - self.reserve)
        waits = [0.0]
        if recent:
            waits.append(recent[-1] + self.gap - now)
        if len(recent) >= limit:
            waits.append(recent[len(recent) - limit] + WINDOW - now)
        if kind != "check" and checks_waiting:
            waits.append(self.gap)
        return max(waits)

    def acquire(self, kind="prime", until=None):
        """Waits for a request of `kind`, records it, and returns True; with `until` (a clock time), returns False
        instead, recording nothing, once that time comes first (a run's own check falls due: harness/probe.py). A
        check that has to wait says so in the shared state (`checks`, with an expiry), so that no priming of any run
        takes its turn meanwhile. `self.waited`: the seconds the last call waited."""
        waited, token = 0.0, None
        self.waited = 0.0
        while True:
            with self.store.locked() as state:
                now = self.clock.now()
                state["times"] = [t for t in state["times"] if t > now - WINDOW]
                checks = {k: v for k, v in (state.get("checks") or {}).items() if v > now}
                others = any(k != token for k in checks)
                wait = self.wait_for(state["times"], now, kind, others)
                if wait <= 0:
                    state["times"].append(now)
                    checks.pop(token, None)
                    state["checks"] = checks
                    self.waited = waited
                    return True
                if until is not None and now >= until:
                    state["checks"] = checks
                    self.waited = waited
                    return False
                if kind == "check":
                    token = token or f"{os.getpid()}-{id(self)}-{self.rng.random():.12f}"
                    checks[token] = now + wait + 2 * WINDOW  # stale after that: a run that died does not block
                state["checks"] = checks
            pause = wait + (self.rng.uniform(0, self.jitter) if self.jitter else 0)
            if until is not None:
                pause = max(0.0, min(pause, until - now))
            self.clock.sleep(pause)
            waited += pause


# --- the plan: the night's runs on a simulated clock, the real loop and the same pacer -------------------------------

class SimClock:
    """A clock shared by threads that only wait: time moves on, to the earliest wake-up, once every live thread
    sleeps. Deterministic enough for a plan; nothing real waits."""

    def __init__(self, start=0.0):
        self.t, self.cv, self.sleeping, self.live = start, threading.Condition(), {}, 0

    def now(self):
        return self.t

    def join(self):
        with self.cv:
            self.live += 1

    def leave(self):
        with self.cv:
            self.live -= 1
            self._advance()

    def _advance(self):
        if self.live and len(self.sleeping) == self.live:
            self.t = max(self.t, min(self.sleeping.values()))
            for k in [k for k, w in self.sleeping.items() if w <= self.t]:
                del self.sleeping[k]
            self.cv.notify_all()

    def sleep(self, seconds):
        if seconds <= 0:
            return
        me = object()
        with self.cv:
            self.sleeping[me] = self.t + seconds
            self._advance()
            while me in self.sleeping:
                self.cv.wait()


class SimClient:
    """A client every cache of which is warm, whose requests take `took` seconds of the simulated clock."""

    def __init__(self, clock, pacer, took):
        self.clock, self.pacer, self.took, self.n = clock, pacer, took, 0
        self.times = []

    def start(self, prompt):
        self.n += 1
        self.times.append(self.clock.now())
        self.clock.sleep(self.took)
        return f"s{self.n}", {"total": 2000 + (6000 if "<doc>" in prompt else 0), "cached": 2000, "write": 0,
                              "calls": 1, "model": "m"}

    def resume(self, handle, prompt):
        self.times.append(self.clock.now())
        self.clock.sleep(self.took)
        return {"total": 8020, "cached": 8000, "write": 20, "calls": 1, "model": "m"}


def plan(runs, rpm_of, took_of, seed=1):
    """`runs`: [{"id", "client", "delay", "ages": [seconds], "labels", "replicas", "waves", "wave_gap"}]. Every run in
    its own thread, with run_probe itself, on one simulated clock; the runs of a client with a budget (rpm_of) share
    one Pacer. Every cache warm (the longest run). Returns {id: {"end", "requests", "late", "times"}} in seconds from
    the go, and {client: [request times]}."""
    import probe  # the real loop
    clock = SimClock()
    pacers = {c: Pacer(MemoryStore(), rpm, clock, rng=random.Random(seed)) for c, rpm in rpm_of.items() if rpm}
    out, threads = {}, []

    def one(r):
        try:
            clock.sleep(r["delay"])
            pacer = pacers.get(r["client"])
            sim = SimClient(clock, pacer, took_of.get(r["client"], 5.0))
            events = []
            probe.run_probe(sim, ages=r["ages"], labels=r["labels"], replicas=r["replicas"], words=10, salt="plan",
                            log=events.append, clock=clock, waves=r["waves"], wave_gap=r["wave_gap"],
                            pace=pacer.acquire if pacer else None)
            out[r["id"]] = {"end": clock.now(), "requests": len(sim.times), "times": sim.times,
                            "late": sum(1 for e in events if e.get("event") == "check" and e.get("late"))}
        finally:
            clock.leave()

    for r in runs:
        clock.join()
    for r in runs:
        t = threading.Thread(target=one, args=(r,), daemon=True)
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    by_client = {}
    for r in runs:
        by_client.setdefault(r["client"], []).extend(out[r["id"]]["times"])
    return out, by_client


def busiest_minute(times):
    """The most requests in any 60 seconds of `times`."""
    times, best, j = sorted(times), 0, 0
    for i, t in enumerate(times):
        while times[j] <= t - WINDOW:
            j += 1
        best = max(best, i - j + 1)
    return best
