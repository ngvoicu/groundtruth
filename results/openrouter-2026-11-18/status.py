#!/usr/bin/env python3
"""Rebuilds the state of this folder from its files alone (after a restart or in another window):
which runs of plan.json finished, which run (a live pid of logs/<label>.pid whose command names the label), which were
cut off (pid gone, no final file), which are left; what each cost (ledger.py), the upstream that answered each
priming and check, and the money committed against the $18 stop.

    python3 results/openrouter-2026-11-18/status.py             # report only, sends nothing
    python3 results/openrouter-2026-11-18/status.py --launch    # also start what fits (run.sh), see below

--launch, in plan order: reads the key's usage (key_usage.py) and OpenRouter's model list, writes the model's
reading to offered.jsonl (offered or gone, the price), then starts a run when
  - no refusal about the account is open (decisions.json "halt" false; any run that ended on a 402/429 sets halt
    until a decision is written there),
  - fewer than MAX_PAID paid runs are running (one free run at a time; none after a free-limit refusal),
  - spent (the higher of the ledger and the key's usage) + what the running runs may still cost + its own worst
    case + the window requests still owed fit in the $18 stop. A run that does not fit blocks the ones after it
    until room frees; when nothing runs and it still does not fit, it is left out (decisions.json).
--enforce stops (by its own pid only) the newest running run while the money committed is above the stop.
"""
import glob
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import ledger as L  # noqa: E402

STOP = 18.0
MAX_PAID = int(os.environ.get("MAX_PAID", "20"))  # 12 until 10:21 UTC
WINDOW_TOKENS = 1_200_000
plan = json.load(open(os.path.join(HERE, "plan.json")))
runs = plan["runs"]
DEC = os.path.join(HERE, "decisions.json")
dec = json.load(open(DEC)) if os.path.exists(DEC) else {"halt": False, "left_out": {}, "refusals_seen": {}, "free_closed": False}


def save_dec():
    json.dump(dec, open(DEC, "w"), indent=1)


def alive(pid, label):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    cmd = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout
    return label in cmd


def usage_lines(label):
    p = os.path.join(HERE, "logs", f"{label}.usage.jsonl")
    return [json.loads(x) for x in open(p) if x.strip()] if os.path.exists(p) else []


def upstream_of():
    p = os.path.join(HERE, "upstreams.jsonl")
    return {json.loads(x)["id"]: json.loads(x)["upstream"] for x in open(p) if x.strip()} if os.path.exists(p) else {}


UP = upstream_of()


def upstreams(label, salt):
    """Per sample key: the upstream of every reply (priming first, the check last; upstream.py), and the samples where
    they differ. Third value: replies whose upstream is not known yet."""
    by = {}
    for r in usage_lines(label):
        if r.get("status") == 200 and r.get("sample"):
            by.setdefault(r["sample"], []).append(r.get("reply_provider") or UP.get(r.get("reply_id")))
    names, changed = set(), []
    for key, ups in by.items():
        names.update(u for u in ups if u)
        if len({u for u in ups if u}) > 1:
            changed.append({"sample": key.replace(f"groundtruth-{salt}-", "") if salt else key, "upstreams": ups})
    return sorted(names, key=str), changed, sum(1 for ups in by.values() for u in ups if not u)


def state(r):
    label = r["label"]
    pidf = os.path.join(HERE, "logs", f"{label}.pid")
    final = [f for f in glob.glob(os.path.join(HERE, f"{label}-2026-*.json")) if not f.endswith(".partial.json")]
    partial = glob.glob(os.path.join(HERE, f"{label}-2026-*.partial.json"))
    s = {"label": label, "model": r["model"], "group": r["group"]}
    if final:
        j = json.load(open(final[0]))
        s.update(state="finished", status=j["status"], file=os.path.basename(final[0]), error=j.get("error"), salt=j.get("runSalt"))
    elif os.path.exists(pidf):
        pid = int(open(pidf).read().split()[0])
        s["pid"] = pid
        if alive(pid, label):
            s["state"] = "running"
        else:
            s["state"] = "cut off"
        if partial:
            j = json.load(open(partial[0]))
            s.update(file=os.path.basename(partial[0]), salt=j.get("runSalt"), partial_status=j.get("status"))
    else:
        s["state"] = "left out" if label in dec["left_out"] else "not started"
    lines = usage_lines(label)
    s["refusals"] = [{"status": x["status"], "error": x.get("error")} for x in lines if x.get("status") in (402, 429)]
    return s


def worst_now(r, used):
    """The run's worst case, from its own replies once it has some (the largest prompt and output seen)."""
    p = L.prices()[r["model"]]
    prompt = max(plan["prompt_tokens"], used.get("prompt", 0))
    out = max(plan["output_tokens"], used.get("output", 0))
    return (plan["requests"] * prompt * max(p["in"], p["write"]) + plan["requests"] * out * p["out"]) / 1e6


def window_worst(r):
    p = L.prices()[r["model"]]
    return WINDOW_TOKENS * max(p["in"], p["write"]) / 1e6


def key_usage():
    kr = os.path.join(HERE, "key-readings.jsonl")
    rows = [json.loads(x) for x in open(kr) if x.strip()] if os.path.exists(kr) else []
    return (rows[-1].get("usage") or 0.0, rows[-1]["at"]) if rows else (0.0, None)


def windows_done():
    p = os.path.join(HERE, "windows.jsonl")
    return {json.loads(x)["model"] for x in open(p) if x.strip()} if os.path.exists(p) else set()


def report():
    led = L.compute(write=True)
    ku, kat = key_usage()
    states = [state(r) for r in runs]
    wd = windows_done()
    reserved = 0.0
    for r, s in zip(runs, states):
        used = led["per_run"].get(r["label"], {"usd": 0.0})
        s["usd"] = round(used["usd"], 4)
        if s["state"] == "running":
            s["reserve"] = max(0.0, worst_now(r, used) - used["usd"])
            reserved += s["reserve"]
        if r["window"] and r["model"] not in wd and s["state"] not in ("left out",):
            reserved += window_worst(r)
    spent = max(led["total"], ku)
    return led, ku, kat, states, spent, reserved


def offered_now():
    return {m["id"]: m for m in json.load(urllib.request.urlopen(
        urllib.request.Request("https://openrouter.ai/api/v1/models", headers={"User-Agent": "groundtruth"}), timeout=60))["data"]}


def main():
    global UP
    launch = "--launch" in sys.argv
    subprocess.run([sys.executable, os.path.join(HERE, "upstream.py"), "--max", "600"], check=False)
    UP = upstream_of()
    led, ku, kat, states, spent, reserved = report()
    # Refusals: any 402/429 opens a halt until a decision is written in decisions.json.
    for s in states:
        if s["refusals"] and s["label"] not in dec["refusals_seen"]:
            dec["refusals_seen"][s["label"]] = s["refusals"][0]
            msg = json.dumps(s["refusals"][0])
            if s["group"] == "free" and "free-models" not in msg:
                # An upstream's own refusal ("Provider returned error") on a free model ends that run only.
                pass
            elif s["group"] == "free":
                # A free-limit refusal closes the free runs only (the brief); the paid ones are not concerned.
                dec["free_closed"] = True
                dec["free_note"] = f"free runs closed after the refusal of {s['label']}: {json.dumps(s['refusals'][0])[:200]}"
                for r in runs:
                    if r["group"] == "free" and state(r)["state"] == "not started":
                        dec["left_out"][r["label"]] = f"free entry, left after the free-limit refusal of {s['label']}"
            else:
                dec["halt"] = True
            save_dec()
    counts = {}
    for s in states:
        counts[s["state"]] = counts.get(s["state"], 0) + 1
    print(f"ledger ${led['total']:.4f} (OpenRouter ${led['reported']:.4f}), key usage ${ku} at {kat}; spent ${spent:.4f}; "
          f"reserved ${reserved:.4f}; committed ${spent + reserved:.4f} of ${STOP}")
    print("states:", counts, "| halt:", dec["halt"], "| free closed:", dec["free_closed"])
    for s in states:
        if s["state"] in ("not started",):
            continue
        ups, changed, unnamed = upstreams(s["label"], s.get("salt")) if s["state"] != "left out" else ([], [], 0)
        extra = f" upstream {','.join(map(str, ups))}" + (f" CHANGED {len(changed)}" if changed else "") + (f" unnamed {unnamed}" if unnamed else "")
        print(f"  {s['label']:44} {s['state']:9} {s.get('status') or s.get('partial_status') or '':20} ${s['usd']:.4f}"
              f"{' reserve $%.3f' % s['reserve'] if 'reserve' in s else ''}{extra}{' REFUSAL ' + json.dumps(s['refusals'][0]) if s['refusals'] else ''}"
              f"{' ERROR ' + s['error'][:100] if s.get('error') else ''}")
    if "--enforce" in sys.argv and spent + reserved > STOP:
        running = sorted((s for s in states if s["state"] == "running"), key=lambda s: os.path.getmtime(os.path.join(HERE, "logs", s["label"] + ".pid")))
        while running and spent + reserved > STOP:
            s = running.pop()
            os.kill(s["pid"], signal.SIGTERM)
            reserved -= s["reserve"]
            dec["left_out"][s["label"]] = f"stopped by hand at {time.strftime('%H:%M:%SZ', time.gmtime())}: the money committed passed the stop"
            save_dec()
            print("STOPPED", s["label"], s["pid"])
    if not launch:
        return
    if dec["halt"]:
        print("HALT: a refusal is open; write a decision in decisions.json before launching")
        return
    subprocess.run([sys.executable, os.path.join(HERE, "key_usage.py"), "status.py --launch pass"], check=True, capture_output=True)
    led, ku, kat, states, spent, reserved = report()
    committed = spent + reserved
    running_paid = sum(1 for s in states if s["state"] == "running" and s["group"] != "free")
    running_free = any(s["state"] == "running" and s["group"] == "free" for s in states)
    anything_running = any(s["state"] == "running" for s in states)
    models = None
    started = []
    for r, s in zip(runs, states):
        if s["state"] != "not started":
            continue
        free = r["group"] == "free"
        if free and (dec["free_closed"] or running_free):
            continue
        if not free and running_paid >= MAX_PAID:
            break
        if models is None:
            models = offered_now()
        m = models.get(r["model"])
        row = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "model": r["model"], "offered": m is not None,
               "pricing": (m or {}).get("pricing"), "context_length": (m or {}).get("context_length"),
               "top_provider_context_length": ((m or {}).get("top_provider") or {}).get("context_length")}
        open(os.path.join(HERE, "offered.jsonl"), "a").write(json.dumps(row) + "\n")
        if m is None:
            dec["left_out"][r["label"]] = "no longer offered by OpenRouter at launch"
            save_dec()
            continue
        w = worst_now(r, {})  # with the price just read
        if committed + w > STOP:
            if not anything_running and not started:
                dec["left_out"][r["label"]] = f"worst case ${w:.2f} did not fit: committed ${committed:.2f} of ${STOP}"
                save_dec()
                print("LEFT OUT", r["label"], dec["left_out"][r["label"]])
                continue
            print(f"WAIT {r['label']}: worst ${w:.3f}, committed ${committed:.3f}")
            if free:
                continue
            break
        subprocess.run([os.path.join(HERE, "run.sh"), r["label"]], check=True, cwd=ROOT)
        started.append(r["label"])
        committed += w
        if free:
            running_free = True
        else:
            running_paid += 1
        time.sleep(15)  # the priming bursts of two runs apart
    print("started:", started, f"committed now ${committed:.4f}")


if __name__ == "__main__":
    main()
