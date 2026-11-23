#!/usr/bin/env python3
"""A night's schedule, planned before the go (docs/own-clients.md, section 1, rule 5).

On 2026-11-23 nineteen Devin runs primed their waves at once on one account, and Devin refused seven of them after
about 430 requests in one quarter hour; windows of 79 requests in 60 s had passed before. Nothing paces a run while it
runs: instead the night gives each run of a client its start, ahead of time, so that the client's whole schedule stays
at or under a limit per 60 s and per 15 minutes (LIMITS; `night.py --limit devin=40/300`).

How: every run's own request times are those of the real loop (harness/probe.py run_probe) on a simulated clock, with
every cache warm (every run goes to its end) and each request taking a fixed time; a run's times move only with its
start. The starts are chosen in the plan's order, each the earliest at least the client's spacing after the one before
at which the combined schedule keeps under the limits, for requests taking 2 s (the night's tenth percentile: the
densest) and 4 s (about its median: the end times). Nothing is sent, nothing written.
"""
import random

# Requests at most, per client, in any window of so many seconds (60 s and 15 minutes). Codex: none.
LIMITS = {"devin": {60: 40, 900: 300}}
# Seconds one request takes in the plan: the densest case (limits) and the usual one (end times).
TOOK = {"devin": (2.0, 4.0), "codex": (3.0, 6.0)}
STEP = 10.0  # seconds by which a run's start is pushed later until the schedule keeps under the limits


class SimClock:
    """A clock that only moves when the loop sleeps: wall and monotonic alike."""

    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    mono = now

    def sleep(self, seconds):
        if seconds > 0:
            self.t += seconds


class SimClient:
    """A client every cache of which is warm, every request taking `took` seconds; records each request's start."""

    def __init__(self, clock, took):
        self.clock, self.took, self.n, self.times = clock, took, 0, []

    def _send(self):
        self.times.append(self.clock.now())
        self.clock.sleep(self.took)

    def start(self, prompt):
        self._send()
        self.n += 1
        return f"s{self.n}", {"total": 2000 + (6000 if "<doc>" in prompt else 0), "cached": 2000, "write": 0,
                              "calls": 1, "model": "m"}

    def resume(self, handle, prompt):
        self._send()
        return {"total": 8020, "cached": 8000, "write": 20, "calls": 1, "model": "m"}


_profiles = {}


def profile(run, took):
    """(request times from the run's start, its end) of one run: run_probe itself on a SimClock."""
    import probe
    key = (tuple(run["ages"]), run["replicas"], run["waves"], run["wave_gap"], took)
    if key not in _profiles:
        clock = SimClock()
        sim = SimClient(clock, took)
        probe.run_probe(sim, ages=run["ages"], labels=run["labels"], replicas=run["replicas"], words=10,
                        salt="plan", log=lambda e: None, clock=clock, waves=run["waves"], wave_gap=run["wave_gap"],
                        rng=random.Random(1))
        _profiles[key] = (tuple(sim.times), clock.now())
    return _profiles[key]


def window_max(times, window):
    """The most of `times` within any `window` seconds (two times less than `window` apart are in one window)."""
    times, best, j = sorted(times), 0, 0
    for i, t in enumerate(times):
        while t - times[j] >= window:
            j += 1
        best = max(best, i - j + 1)
    return best


def over(times, limits):
    return any(window_max(times, w) > n for w, n in limits.items())


def schedule(runs, limits, took, spacing):
    """{run id: start in seconds after the go}: in the runs' order, each start the earliest at least `spacing` after
    the one before at which the combined request times of all runs keep under `limits` ({window s: requests}), for
    every request time in `took`. A run that alone passes a limit cannot be placed: ValueError."""
    starts, placed = {}, {t: [] for t in took}
    at = 0.0
    for r in runs:
        own = {t: profile(r, t)[0] for t in took}
        if limits and any(over(own[t], limits) for t in took):
            raise ValueError(f"{r['id']} alone passes the limits {limits}")
        while limits and any(over(placed[t] + [at + x for x in own[t]], limits) for t in took):
            at += STEP
        starts[r["id"]] = at
        for t in took:
            placed[t] += [at + x for x in own[t]]
        at += spacing
    return starts


def report(runs, starts, limits, took):
    """{"times": the client's request times (usual case), "max": {window: most requests in it, densest case},
    "ends": {run id: its end after the go}, "requests": how many}."""
    dense, usual = took[0], took[-1]
    times_dense = [starts[r["id"]] + x for r in runs for x in profile(r, dense)[0]]
    times = [starts[r["id"]] + x for r in runs for x in profile(r, usual)[0]]
    ends = {r["id"]: starts[r["id"]] + profile(r, usual)[1] for r in runs}
    windows = sorted(set(limits) | {60, 900})
    return {"times": times, "requests": len(times), "ends": ends,
            "max": {w: max(window_max(times_dense, w), window_max(times, w)) for w in windows}}
