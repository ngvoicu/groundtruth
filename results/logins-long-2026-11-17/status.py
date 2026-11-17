#!/usr/bin/env python3
"""Writes logs/status.md: where every run of this folder is, from its files alone (run file, progress file, log).

    python3 results/logins-long-2026-11-17/status.py

Per run: process alive or not, status, control, warm/checks per age so far, the next and the last planned check
(approximate: the run's start plus the age; priming adds a few minutes). A run stops by itself after two ages in a
row that are fully cold, so its last check can come much earlier than planned.
"""
import datetime as dt, glob, json, os, re

D = os.path.dirname(os.path.abspath(__file__))
L = f"{D}/logs"


def fmt(ms):
    s = ms / 1000
    return f"{s / 3600:g}h" if s >= 3600 and s % 3600 == 0 else f"{s / 60:g}m"


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


pids = {}
for f in sorted(glob.glob(f"{L}/sequence-*.log")):
    for line in open(f):
        m = re.search(r"started (\S+) pid (\d+)", line)
        if m:
            pids[m.group(1)] = int(m.group(2))
        m = re.search(r"sequence (\S+): .* pid (\d+)", line)
        if m:
            pids["sequence-" + m.group(1)] = int(m.group(2))

now = dt.datetime.now(dt.timezone.utc)
rows = []
for label in sorted(k for k in pids if not k.startswith("sequence-")):
    final = [f for f in glob.glob(f"{D}/{label}-2026-*.json") if not f.endswith(".partial.json")]
    partial = glob.glob(f"{D}/{label}-2026-*.partial.json")
    f = (final or partial or [None])[-1]
    j = json.load(open(f)) if f else None
    log = open(f"{L}/{label}.log", errors="replace").read() if os.path.exists(f"{L}/{label}.log") else ""
    proc = "running" if alive(pids[label]) else "ended"
    if not j:
        last = log.strip().splitlines()[-1][:120] if log.strip() else "(no output yet)"
        rows.append(f"| {label} | – | {proc} (pid {pids[label]}) | no run file yet | | | {last} |")
        continue
    if j["status"] != "running":
        proc = "ended"  # a finished probe may wait a moment to be reaped by its supervisor
    start = dt.datetime.fromisoformat(j["startedAt"].replace("Z", "+00:00"))
    ages = j["plannedAges"]
    per = {}
    for c in j["checks"]:
        a = per.setdefault(c["targetAgeMs"], [0, 0, 0])
        if c.get("error") or c.get("late"):
            a[2] += 1
        else:
            a[1] += 1
            a[0] += 1 if c["warm"] else 0
    seen = ", ".join(f"{fmt(a)} {w}/{n}" + (f" (+{x} left out)" if x else "") for a, (w, n, x) in sorted(per.items()))
    done = {a for a, v in per.items() if sum(v[1:]) >= j["replicas"]}
    nxt = next((a for a in ages if a not in done), None)
    ctl = j.get("control")
    ctl = "–" if not ctl else ("hit" if ctl["warm"] else "MISS") + f" ({ctl['check']['cachedTokens']}/{ctl['check']['promptTokens']})"
    kinds = (j.get("spent") or {}).get("replyHeaders", {}).get("x-cpa-auth-kind", {})
    due = lambda a: (start + dt.timedelta(milliseconds=a)).astimezone().strftime("%m-%d %H:%M")
    where = j["status"]
    if where == "running" and nxt is not None:
        where += f"; next {fmt(nxt)} ≈ {due(nxt)}, last planned {fmt(ages[-1])} ≈ {due(ages[-1])}"
    if j.get("error"):
        where += f"; {j['error'][:160]}"
    rows.append(f"| {label} | `{j['model']}` | {proc} (pid {pids[label]}) | {where} | {ctl} | {kinds or '–'} | {seen or '–'} |")

seqs = ", ".join(f"{k} pid {v} {'running' if alive(v) else 'ended'}" for k, v in pids.items() if k.startswith("sequence-"))
out = [f"# Status, written {dt.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}", "",
       f"Supervisors: {seqs or 'none'}", "",
       "Times are local and approximate (run start + age; priming adds minutes). A run ends by itself after two fully",
       "cold ages in a row.", "",
       "| Run | Model | Process | Where | Control | Answered by (X-CPA-AUTH-KIND) | Warm/checks per age so far |",
       "|---|---|---|---|---|---|---|"] + rows
open(f"{L}/status.md", "w").write("\n".join(out) + "\n")
