#!/usr/bin/env python3
"""The detached supervisor of this folder: every 3 minutes `status.py --launch --enforce` (start what fits the $18
stop, in plan order; stop the newest run by its own pid if the money committed passes the stop), and the window
request (window.py) of each model whose figures disagree once its cache run has ended. Ends by itself when no run is
left to start and none runs, or when status.py halts on a refusal about the account. Its pid is in
logs/supervisor.pid, its output in logs/supervisor.log. Start (detached, under its own caffeinate):
    nohup caffeinate -i python3 results/openrouter-2026-11-18/supervise.py > results/openrouter-2026-11-18/logs/supervisor.log 2>&1 &
"""
import importlib  # noqa: F401
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
open(os.path.join(HERE, "logs", "supervisor.pid"), "w").write(f"{os.getpid()} {os.getppid()}\n")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S', time.gmtime())}Z] {msg}", flush=True)


while True:
    out = subprocess.run([sys.executable, os.path.join(HERE, "status.py"), "--launch", "--enforce"], cwd=ROOT,
                         capture_output=True, text=True)
    text = out.stdout + out.stderr
    for line in text.splitlines():
        if line.startswith(("ledger", "states", "started", "WAIT", "LEFT", "HALT", "STOPPED", "Traceback")) or " pid " in line:
            log(line)
    if out.returncode:
        log(f"status.py exited {out.returncode}: {text[-500:]}")
    # Window requests, after the model's cache run.
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import importlib
    import status as S  # noqa: E402
    S = importlib.reload(S)  # decisions.json and upstreams as they are now
    plan = json.load(open(os.path.join(HERE, "plan.json")))
    done = set()
    wp = os.path.join(HERE, "windows.jsonl")
    if os.path.exists(wp):
        done = {json.loads(x)["model"] for x in open(wp) if x.strip()}
    dec = json.load(open(os.path.join(HERE, "decisions.json")))
    for r in plan["runs"]:
        if r["window"] and r["model"] not in done and not dec.get("halt"):
            st = S.state(r)["state"]
            if st in ("finished", "cut off"):
                w = subprocess.run([sys.executable, os.path.join(HERE, "window.py"), r["model"]], cwd=ROOT, capture_output=True, text=True)
                log(f"window {r['model']}: {(w.stdout + w.stderr).strip()[:400]}")
    states = [S.state(r)["state"] for r in plan["runs"]]
    if dec.get("halt"):
        log("halt is set (a refusal about the account): no more launches; supervisor ends")
        break
    if "running" not in states and "not started" not in states:
        log("nothing left to start and nothing running: supervisor ends")
        break
    time.sleep(180)
