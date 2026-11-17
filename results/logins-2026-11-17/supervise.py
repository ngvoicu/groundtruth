#!/usr/bin/env python3
"""Start the lifetime runs of one login side by side and stop them all at that login's first quota or rate refusal.

    python3 results/logins-2026-11-17/supervise.py <group> <label>=<model>[@<extra probe option>@<value>...] ...

Each run is the plain probe (src/cli.ts, 0.3.1) through the local CLIProxyAPI with --stop-on-refusal, the standard
schedule and 3 samples per age, its output in logs/<label>.log. The probe ends its own run at a refusal; this
supervisor then ends the other runs of the same login (processes it started itself, by process id), so no request
goes to a login after it refused one. Its own log is logs/supervise-<group>.log, with every process id it started.
The client key is read by the caller into CACHE_PROBE_KEY (run-lifetimes.sh) and never written anywhere.
"""
import os, signal, subprocess, sys, time

R = "results/logins-2026-11-17"
group, specs = sys.argv[1], sys.argv[2:]
log = open(f"{R}/logs/supervise-{group}.log", "a")


def say(line):
    log.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {line}\n"); log.flush()


procs = {}
stopped = False


def refused():
    """Ends every run of this login at the first refusal seen in any run's log. True once that happened."""
    global stopped
    if stopped:
        return True
    for label in procs:
        text = open(f"{R}/logs/{label}.log", errors="replace").read()
        if "quota or rate refusal, not retried" in text:
            say(f"{label} met a quota or rate refusal: ending the other runs of this login, starting no more")
            for other, q in procs.items():
                if q.poll() is None:
                    q.send_signal(signal.SIGTERM)
                    say(f"sent SIGTERM to {other} pid {q.pid}")
            stopped = True
    return stopped


# The first version of this loop started every run first and only then watched the logs; on 2026-11-17 it went on
# starting Devin runs (LD5, LD6) after LD1 had been refused, and was ended by hand. Now it watches between starts.
for spec in specs:
    if refused():
        break
    label, rest = spec.split("=", 1)
    model, _, extra = rest.partition("@")
    cmd = ["node", "src/cli.ts", "--base-url", "http://127.0.0.1:8317/v1", "--model", model, "--label", label,
           "--schedule", "std", "--replicas", "3", "--concurrency", "2", "--stop-on-refusal", "--out", R] + extra.replace("@", " ").split()
    out = open(f"{R}/logs/{label}.log", "a")
    p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT)
    procs[label] = p
    say(f"started {label} pid {p.pid}: {' '.join(cmd[2:])}")
    for _ in range(15):
        time.sleep(1)
        if refused():
            break

while any(p.poll() is None for p in procs.values()):
    time.sleep(10)
    refused()
for label, p in procs.items():
    say(f"{label} exited with {p.returncode}")
say("done")
