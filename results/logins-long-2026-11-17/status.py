#!/usr/bin/env python3
"""Writes logs/status.md: where every run of this folder is, from its files alone (run file, progress file, log).

    python3 results/logins-long-2026-11-17/status.py

Per run: process alive or not, status, control, warm/checks per age so far, the next and the last planned check
(approximate: the run's start plus the age; priming adds a few minutes). A run stops by itself after two ages in a
row that are fully cold, so its last check can come much earlier than planned.

The Mac was restarted at 10:16 local on 2026-11-18. A process id written down before the last boot of this machine is
no longer that process (an id can be reused), so such a process counts as ended without being looked up; a run whose
progress file still says "running" after the boot was cut off (CL1, CL3, ML1, ML3).
"""
import datetime as dt, glob, json, os, re, subprocess

D = os.path.dirname(os.path.abspath(__file__))
L = f"{D}/logs"


def fmt(ms):
    s = ms / 1000
    return f"{s / 3600:g}h" if s >= 3600 and s % 3600 == 0 else f"{s / 60:g}m"


def boot_time():
    m = re.search(r"sec = (\d+)", subprocess.run(["sysctl", "-n", "kern.boottime"], capture_output=True, text=True).stdout)
    return dt.datetime.fromtimestamp(int(m.group(1)), dt.timezone.utc) if m else None


BOOT = boot_time()
STARTED = {}  # label -> when its supervisor started it


def alive(pid, label=None):
    if BOOT and label in STARTED and STARTED[label] < BOOT:
        return False  # started before this machine's last boot: that process is gone
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
            STARTED[m.group(1)] = dt.datetime.fromisoformat(line.split()[0])
        m = re.search(r"sequence (\S+): .* pid (\d+)", line)
        if m:
            pids["sequence-" + m.group(1)] = int(m.group(2))
            STARTED["sequence-" + m.group(1)] = dt.datetime.fromisoformat(line.split()[0])

now = dt.datetime.now(dt.timezone.utc)
rows = []
for label in sorted(k for k in pids if not k.startswith("sequence-")):
    final = [f for f in glob.glob(f"{D}/{label}-2026-*.json") if not f.endswith(".partial.json")]
    partial = glob.glob(f"{D}/{label}-2026-*.partial.json")
    f = (final or partial or [None])[-1]
    j = json.load(open(f)) if f else None
    log = open(f"{L}/{label}.log", errors="replace").read() if os.path.exists(f"{L}/{label}.log") else ""
    proc = "running" if alive(pids[label], label) else "ended"
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
    seen = ", ".join(f"{fmt(a)} {w}/{n}" + (f" (+{x} error or late)" if x else "") for a, (w, n, x) in sorted(per.items()))
    done = {a for a, v in per.items() if sum(v[1:]) >= j["replicas"]}
    nxt = next((a for a in ages if a not in done), None)
    ctl = j.get("control")
    ctl = "–" if not ctl else ("hit" if ctl["warm"] else "MISS") + f" ({ctl['check']['cachedTokens']}/{ctl['check']['promptTokens']})"
    kinds = (j.get("spent") or {}).get("replyHeaders", {}).get("x-cpa-auth-kind", {})
    due = lambda a: (start + dt.timedelta(milliseconds=a)).astimezone().strftime("%m-%d %H:%M")
    where = j["status"]
    if where == "running" and proc == "ended":
        where = (f"cut off by the restart of {BOOT.astimezone().strftime('%Y-%m-%d %H:%M')} local, before its "
                 f"{fmt(nxt)} check (the progress file still says \"running\")" if nxt is not None else "cut off")
    elif where == "running" and nxt is not None:
        where += f"; next {fmt(nxt)} ≈ {due(nxt)}, last planned {fmt(ages[-1])} ≈ {due(ages[-1])}"
    if j.get("error"):
        where += f"; {j['error'][:160]}"
    rows.append(f"| {label} | `{j['model']}` | {proc} (pid {pids[label]}) | {where} | {ctl} | {kinds or '–'} | {seen or '–'} |")

seqs = ", ".join(f"{k} pid {v} {'running' if alive(v, k) else 'ended'}" for k, v in pids.items() if k.startswith("sequence-"))
out = [f"# Status, written {dt.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}", "",
       f"Supervisors: {seqs or 'none'}", "",
       "Times are local and approximate (run start + age; priming adds minutes). A run ends by itself after two fully",
       "cold ages in a row. Errors count neither warm nor cold.", "",
       "CL1 and CL3: from the 4-hour age every check is refused by the proxy (400 \"unknown provider for model",
       "probe/...\"): the owner's configuration of 20:50 excluded gpt-6.1-sol and gpt-6-astra from the Codex login.",
       "Nothing reaches OpenAI. No alias or backup of logins-long is left.", "",
       "The Mac was restarted at 10:16 local on 2026-11-18: CL1, CL3, ML1 and ML3 were cut off before their 24-hour",
       "checks. A run cannot be resumed; their progress files are kept as the restart left them.", "",
       "| Run | Model | Process | Where | Control | Answered by (X-CPA-AUTH-KIND) | Warm/checks per age so far |",
       "|---|---|---|---|---|---|---|"] + rows
open(f"{L}/status.md", "w").write("\n".join(out) + "\n")
