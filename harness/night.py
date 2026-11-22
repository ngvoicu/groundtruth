#!/usr/bin/env python3
"""The run plan of docs/own-clients.md, section 4, narrowed for the first night, with the parity pairs of Provimux's
client-parity.md, section 7. The owner's steps are docs/own-clients-RUN.md.

    python3 harness/night.py --date 2026-11-23 untouched --save|--report
    python3 harness/night.py --date 2026-11-23 pi-setup                 # pi's own folder, with pi-provimux
    python3 harness/night.py --date 2026-11-23 --dry-run all            # every command, each tool's own dry run
    python3 harness/night.py --date 2026-11-23 --go smoke               # in the foreground, about 12 minutes
    python3 harness/night.py --date 2026-11-23 smoke-reviewed           # after reading the smoke results
    python3 harness/night.py --date 2026-11-23 --go night               # everything else, under a detached supervisor
    python3 harness/night.py --date 2026-11-23 status                   # what runs, what is done, what failed
    python3 harness/night.py --date 2026-11-23 stop all|<id>            # the supervisor and every run, or one run
    python3 harness/night.py --date 2026-11-23 --go window <model>      # one OpenRouter window request

Parts: openrouter (OR1 - OR5, straight to OpenRouter), windows (OW1 - OW9), smoke (S1 - S4, S3b, SP), claude (CC1 -
CC4 and the pi runs of pairs CC-1, CC-2), claude-5m (CC5 - CC8), codex (CX1 - CX6 and the pi runs of CX-1 to CX-3),
codex-plain (CX-S, the plain probe through Provimux), devin (DV1 - DV17, DV9d and the pi runs of DV-1 to DV-4),
devin-terra-pi (DV-6's pi run, only if S3b showed cached tokens), muse (MC1 - MC3 and MC-1's pi run, with Provimux's
payload rules as configured). `night` is all of them but the smoke runs: the supervisor launches openrouter, claude,
codex, codex-plain, devin, devin-terra-pi (decided from S3b), muse and windows, then claude-5m when CC1 - CC4 have
ended, then waits for the last run and writes the morning report of the everyday state.

Not in the first night: no input-limit walk through an own client (harness/client_limits.py is not yet trusted), no
Antigravity run, no second run of pair CX-3, no second OpenRouter run at 8,000 tokens.

Nothing is sent without --go. --dry-run prints each command and runs the tool's own --dry-run, which runs no client
and sends nothing. --go refuses `all`, refuses the smoke runs with anything else, and refuses a login's part until the
smoke results were reviewed. The owner's everyday state is protected by isolation, not by a stop: every client
process gets its state folder and a throwaway HOME under <client-home> (clients.throwaway_home), so a client that
ignores its state folder's variable writes there, and the Keychain, found through HOME on macOS, is out of its
reach. The owner may use his computer and his tools all night; the everyday folders and the Keychain's item names
are snapshot before the logins and reported in the morning (`untouched --report`), for a person to judge, never a
reason to stop. A step already done (a raw file, a pid file, a window row) is skipped on a rerun. Keys come from the Keychain only at --go, straight into the one process that
needs them, and are never printed or written (their fingerprints are left for the commit scan). OpenRouter is
reached directly, never through a proxy of the environment.
"""
import argparse
import glob
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import scan_secrets  # noqa: E402

OPENROUTER = "https://openrouter.ai/api/v1"
PROVIMUX = "http://127.0.0.1:8317/v1"  # the owner's proxy: only the plain-probe pair CX-S goes there
# The owner's Keychain items for this campaign (generic passwords, account = the user name). Read only, at --go.
KEYCHAIN = {"META_API_KEY": "groundtruth META_API_KEY", "OPENROUTER": "groundtruth OPENROUTER_API_KEY",
            "PROVIMUX": "groundtruth PROVIMUX_KEY"}
MONEY_STOP = 4.00  # USD on the campaign's OpenRouter key (its own limit is 5)
STD65 = "10m,15m,20m,25m,30m,40m,50m,60m,65m,75m,90m,120m"
PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy",
              "NODE_USE_ENV_PROXY", "GLOBAL_AGENT_HTTP_PROXY", "GLOBAL_AGENT_HTTPS_PROXY")
SECRETS = ("CACHE_PROBE_KEY", "META_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
           "CLIPROXYAPI_API_KEY")
PROVIMUX_CONFIG = "/opt/homebrew/etc/provimux.conf"  # only its payload section is read, by each pi run (--provimux-config)


def probe(id_, harness, model, ages=None, schedule=None, filler=None, env=None, extra=(), pair=None):
    args = ["--harness", harness, "--model", model, "--replicas", "3", "--label", id_]
    args += ["--ages", ages] if ages else ["--schedule", schedule or "std"]
    if filler:
        args += ["--filler", filler]
    for k, v in (env or {}).items():
        args += ["--client-env", f"{k}={v}"]
    args += list(extra)
    return {"id": id_, "kind": "probe", "harness": harness, "model": model, "args": args, "pair": pair}


def twin(own, pi_model, pair):
    """The pi-through-Provimux run of a pair: the own client's schedule, ages and filler, started beside it."""
    a = own["args"]
    keep = []
    for flag in ("--ages", "--schedule", "--filler"):
        if flag in a:
            keep += [flag, a[a.index(flag) + 1]]
    step = {"id": "P-" + own["id"], "kind": "probe", "harness": "pi", "model": pi_model, "pair": pair,
            "args": ["--harness", "pi", "--model", pi_model, "--replicas", "3", "--label", "P-" + own["id"], *keep]}
    own["pair"] = pair
    return step


def smoke(id_, harness, model, filler=None):
    """Baseline and the control checked at 30 s; the output kept, redacted, outside the repository."""
    return {"id": id_, "kind": "smoke", "harness": harness, "model": model,
            "args": ["--harness", harness, "--model", model, "--replicas", "0", "--waves", "1", "--label", id_,
                     "--schedule", "std", *(["--filler", filler] if filler else [])]}


CC = [probe(f"CC{i}", "claude", m, ages=STD65, filler="list") for i, m in enumerate(
    ["claude-fable-5-2", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"], 1)]
CX = [probe(f"CX{i}", "codex", m, schedule="long") for i, m in enumerate(
    ["gpt-6.2-sol", "gpt-6.2-astra", "gpt-6.1-sol", "gpt-6.1-terra", "gpt-6-astra", "gpt-6-luna"], 1)]
DEVIN = [("DV1", "claude-opus-5-5-low", "std"), ("DV2", "claude-sonnet-5-5-low", "std"), ("DV3", "claude-haiku-5-5-low", "std"),
         ("DV4", "gpt-6-1-sol-low", "std"), ("DV5", "gpt-6-1-terra-low", "std"), ("DV6", "gpt-6-astra-low", "std"),
         ("DV7", "gpt-6-luna-low", "std"),
         ("DV8", "deepseek-v4-1-flash-1017-low", "long"), ("DV9", "glm-5-3-low", "std"), ("DV10", "kimi-k3-1-pro-low", "long"),
         ("DV11", "nemotron-3-5-super-none", "long"),
         ("DV12", "deepseek-v4-pro-low", "std"), ("DV13", "gemini-4-argon-low", "std"), ("DV14", "grok-4-7-low", "std"),
         ("DV15", "kimi-k3-low", "std"), ("DV16", "muse-wonder-1-0-low", "std"), ("DV17", "swe-2-medium", "std")]
DV = {i: probe(i, "devin", m, schedule=s) for i, m, s in DEVIN}
MC = [probe(f"MC{i}", "muse", m) for i, m in enumerate(["muse-wonder-1.0", "muse-ember-1.0", "muse-spark-1.3"], 1)]


def with_twins(runs, twins):
    out = []
    for r in runs:
        out.append(r)
        if r["id"] in twins:
            out.append(twin(r, *twins[r["id"]]))
    return out


PARTS = {
    "openrouter": [{"id": f"OR{i}", "kind": "openrouter", "model": m} for i, m in enumerate(
        ["openai/gpt-6-astra", "openai/gpt-6-luna", "meta/muse-spark-1.3", "deepseek/deepseek-v4.1-flash",
         "z-ai/glm-5.3-flash"], 1)],
    # Cheapest first; an answer instead of a refusal ends the list.
    "windows": [{"id": f"OW{i}", "kind": "window", "model": m} for i, m in enumerate(
        ["anthropic/claude-haiku-5.5", "anthropic/claude-opus-5.5", "anthropic/claude-sonnet-5.5",
         "deepseek/deepseek-v4.1-flash", "google/gemini-4-argon", "meta/muse-wonder", "moonshotai/kimi-k3.1-pro",
         "openai/gpt-6.1-sol", "openai/gpt-6.1-terra"], 1)],
    "smoke": [smoke("S1", "claude", "claude-haiku-5-5", filler="list"), smoke("S2", "codex", "gpt-6-luna"),
              smoke("S3", "devin", "claude-haiku-5-5-low"), smoke("S3b", "devin", "gpt-6-1-terra-low"),
              smoke("S4", "muse", "muse-spark-1.3"), smoke("SP", "pi", "gpt-6-luna")],
    "claude": with_twins(CC, {"CC3": ("claude-sonnet-5-5", "CC-1"), "CC4": ("claude-haiku-5-5", "CC-2")}),
    "claude-5m": [probe(f"CC{i}", "claude", m, ages="10m,15m", filler="list", env={"CLAUDE_CODE_PROMPT_CACHE_TTL": "5m"})
                  for i, m in enumerate(["claude-fable-5-2", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"], 5)],
    "codex": with_twins(CX, {"CX1": ("gpt-6.2-sol", "CX-3"), "CX3": ("gpt-6.1-sol", "CX-2"),
                             "CX4": ("gpt-6.1-terra", "CX-1")}),
    # CX-S (a): the plain probe through Provimux on GPT-6.1 Terra, to 30 minutes. CX-S (b), a request shaped like
    # pi's, needs a probe change that is not built: not in the plan.
    "codex-plain": [{"id": "CXS-a", "kind": "proxy-plain", "model": "gpt-6.1-terra", "pair": "CX-S (a)"}],
    "devin": with_twins([DV[i] for i, _, _ in DEVIN] + [probe("DV9d", "devin", "glm-5-3-low", schedule="std",
                                                              extra=["--devin-daemon"], pair="DV-5")],
                        {"DV1": ("devin/claude-opus-5-5-low", "DV-1"), "DV9": ("devin/glm-5-3-low", "DV-2"),
                         "DV11": ("devin/nemotron-3-5-super-none", "DV-3"), "DV14": ("devin/grok-4-7-low", "DV-4")}),
    "devin-terra-pi": [twin(dict(DV["DV5"]), "devin/gpt-6-1-terra-low", "DV-6")],
    # MC-1's pi run goes through Provimux's payload rules as configured (the Meta 24 h rule is not switched): Muse
    # Code caches no conversation, so the pair's question is answered; the rules are recorded with the run.
    "muse": with_twins(MC, {"MC1": ("muse-wonder-1.0", "MC-1")}),
}
ORDER = ["openrouter", "windows", "smoke", "claude", "claude-5m", "codex", "codex-plain", "devin", "devin-terra-pi",
         "muse"]
LOGIN_PARTS = {"claude", "claude-5m", "codex", "codex-plain", "devin", "devin-terra-pi", "muse"}
# `--go night`: the supervisor's launches, in this order; claude-5m when CC1 - CC4 have ended.
NIGHT = ["openrouter", "claude", "codex", "codex-plain", "devin", "devin-terra-pi", "muse", "windows"]
LATER = {"claude-5m": ("CC1", "CC2", "CC3", "CC4")}
ALL_STEPS = {s["id"]: s for part in ORDER for s in PARTS[part]}
PART_OF = {s["id"]: part for part in ORDER for s in PARTS[part]}
POSITION = {}
for _part in ORDER:
    for _s in PARTS[_part]:
        POSITION.setdefault(_s["id"], len(POSITION))
for _id in list(POSITION):
    if _id.startswith("P-") and _id[2:] in POSITION and PART_OF[_id] != PART_OF[_id[2:]]:
        POSITION[_id] = POSITION[_id[2:]] + 0.5  # a pair's pi run starts beside its own-client run
# Seconds between two detached starts (a pair's two runs start within 15 s; Devin's as on 8 November).
SPACING = {"devin": 20}


def folders(date):
    own = os.path.join("results", f"own-clients-{date}")
    return {"own": own, "smoke": os.path.join(own, "smoke"), "or": os.path.join("results", f"openrouter-direct-{date}")}


def folder_of(step, date):
    f = folders(date)
    return f["or"] if step["kind"] in ("openrouter", "window") else f["smoke"] if step["kind"] == "smoke" else f["own"]


def night_dir(date, client_home=None):
    base = client_home or os.environ.get("GROUNDTRUTH_CLIENT_HOME")
    return os.path.join(base, f"night-{date}") if base else f"<client-home>/night-{date}"


def command(step, date, client_home=None):
    """The argument list of a step, run from the repository's root."""
    folder = folder_of(step, date)
    pi = ["--provimux-config", PROVIMUX_CONFIG] if step.get("harness") == "pi" else []
    if step["kind"] == "probe":
        return [sys.executable, "harness/probe.py", *step["args"], *pi, "--out", folder]
    if step["kind"] == "smoke":
        return [sys.executable, "harness/probe.py", *step["args"], *pi, "--out", folder,
                "--keep-raw", os.path.join(night_dir(date, client_home), "raw", step["id"])]
    if step["kind"] in ("openrouter", "proxy-plain"):
        base = OPENROUTER if step["kind"] == "openrouter" else PROVIMUX
        ages = ["--schedule", "quick", "--ages", "15m,20m,25m,30m"] if step["kind"] == "proxy-plain" else []
        return ["node", "src/cli.ts", "--base-url", base, "--format", "responses", "--model", step["model"], *ages,
                "--stop-on-refusal", "--label", step["id"], "--out", folder,
                "--usage-log", os.path.join(folder, "logs", step["id"] + ".usage.jsonl")]
    if step["kind"] == "window":
        return [sys.executable, "harness/night.py", "--date", date, "--go", "window", step["model"]]
    raise ValueError(step)


def window_body(model, n=1_200_000):
    return {"model": model, "max_tokens": 16, "transforms": [],
            "messages": [{"role": "user", "content": "Reply with just OK." + " hello" * n}]}


def select(names):
    if names == ["all"]:
        names = ORDER
    if names == ["night"]:
        names = [p for p in ORDER if p != "smoke"]
    steps = []
    for n in names:
        if n in PARTS:
            steps += [s for s in PARTS[n] if s not in steps]
        elif n in ALL_STEPS:
            steps.append(ALL_STEPS[n])
        else:
            raise SystemExit(f"{n}: not a part ({', '.join(ORDER)}) nor an id of the plan")
    return sorted(steps, key=lambda s: POSITION[s["id"]])


def shown(argv):
    return " ".join(a if a and " " not in a else json.dumps(a) for a in ["python3" if argv[0] == sys.executable else argv[0], *argv[1:]])


def clean_env(extra=None):
    """The launcher's children: no key, no proxy of the shell, then what this step needs."""
    env = {k: v for k, v in os.environ.items() if k not in SECRETS and k not in PROXY_VARS}
    env.update(extra or {})
    return env


def dry_run(steps, date, out=print):
    for step in steps:
        argv = command(step, date)
        pair = f"  [pair {step['pair']}]" if step.get("pair") else ""
        out(f"== {step['id']}{pair}: {shown(argv)}")
        if step["kind"] == "window":
            body = window_body(step["model"], 3)
            out(f"   POST {OPENROUTER}/chat/completions {json.dumps(body).replace('hello hello hello', 'hello × 1,200,000')}"
                " (direct, no proxy; refused by OpenRouter itself, not billed). Dry run: nothing sent.")
            continue
        p = subprocess.run([*argv, "--dry-run"], cwd=ROOT, capture_output=True, text=True, timeout=120, env=clean_env())
        text = (p.stdout + p.stderr).strip()
        if step["kind"] in ("openrouter", "proxy-plain"):
            text = "\n".join(text.splitlines()[:2])  # the plan and the address; the body is the probe's usual one
        out("\n".join("   " + line for line in text.splitlines()))
        if p.returncode:
            raise SystemExit(f"{step['id']}: its dry run failed")


# --- the everyday state: folders (recursively) and the Keychain's item names, reported (never a stop) --------------

EVERYDAY = ["~/.claude", "~/.claude.json", "~/.codex", "~/.devin", "~/.config/devin", "~/.local/share/devin",
            "~/.config/muse", "~/.local/share/muse", "~/.muse", "~/.pi"]


def snapshot_files(user_home=None):
    """Path, size and modification time of every file, folder and link under the everyday folders (nothing read)."""
    home = user_home or os.path.expanduser("~")
    out = {}
    for d in EVERYDAY:
        top = home + d[1:]
        if not os.path.lexists(top):
            continue
        st = os.lstat(top)
        out[d] = [st.st_size, st.st_mtime_ns]
        if os.path.isdir(top) and not os.path.islink(top):
            for root, dirs, files in os.walk(top, followlinks=False):
                for name in dirs + files:
                    p = os.path.join(root, name)
                    st = os.lstat(p)
                    out[d + "/" + os.path.relpath(p, top)] = [st.st_size, st.st_mtime_ns]
    return out


def keychain_items(run=None):
    """The Keychain's items by class, service, account, label and modification date: `security dump-keychain`
    without -d lists attributes only, never a secret."""
    run = run or (lambda: subprocess.run(["security", "dump-keychain"], capture_output=True, text=True, timeout=120).stdout)
    items, cur = [], None
    for line in run().splitlines():
        line = line.strip()
        if line.startswith("keychain:"):
            if cur:
                items.append(cur)
            cur = {}
        elif cur is not None and line.startswith("class:"):
            cur["class"] = line.split(":", 1)[1].strip()
        elif cur is not None and "=" in line and line.startswith('"'):
            key = line.split('"')[1]
            if key in ("svce", "acct", "labl", "mdat", "srvr"):
                cur[key] = line.split("=", 1)[1].strip()
    if cur:
        items.append(cur)
    return sorted(json.dumps(i, sort_keys=True) for i in items)


def everyday_path(date):
    return os.path.join(night_dir(date), "everyday-before.json")


def compare_everyday(before, now):
    """What changed, as lines (empty: nothing): every path added, changed or removed under the everyday folders, and
    every Keychain item added, removed or changed (its modification date), by name."""
    lines = []
    bf, nf = before["files"], now["files"]
    for p in sorted(set(bf) | set(nf)):
        if p not in nf:
            lines.append(f"removed: {p}")
        elif p not in bf:
            lines.append(f"added: {p}")
        elif bf[p] != nf[p]:
            lines.append(f"changed: {p}")
    bk, nk = set(before["keychain"]), set(now["keychain"])
    gone = {identity(i): i for i in bk - nk}
    new = {identity(i): i for i in nk - bk}
    for ident in sorted(set(gone) | set(new)):
        item = new.get(ident) or gone[ident]
        what = "changed" if ident in gone and ident in new else "added" if ident in new else "removed"
        lines.append(f"Keychain item {what}: {describe_item(item)}")
    return lines


def top_folder(line):
    """The everyday folder a report line is about (`~/.pi`), or `Keychain`."""
    if line.startswith("Keychain"):
        return "Keychain"
    path = line.split(": ", 1)[1]
    return max((d for d in EVERYDAY if path == d or path.startswith(d + "/")), key=len, default=path)


def report_path(date, at=None):
    return os.path.join(night_dir(date), f"everyday-report-{at or time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.txt")


def identity(item):
    """An item without its modification date."""
    d = json.loads(item)
    d.pop("mdat", None)
    return json.dumps(d, sort_keys=True)


def describe_item(item):
    d = json.loads(item)
    return ", ".join(f"{k} {d[k]}" for k in ("class", "svce", "labl", "srvr") if k in d)


STATE_FOLDERS = ("claude-code", "codex-cli", "devin-cli", "muse-code", "pi-provimux")


def untouched(date, mode, user_home=None, lister=None, out=print, at=None):
    """`save`: the snapshot, once, before the logins (the state folders and their throwaway homes checked first).
    `report`: what changed since, written to <client-home>/night-<date>/everyday-report-<time>.txt and summarised;
    a report for a person to judge, never a stop. Returns the report's lines (empty: nothing changed)."""
    path = everyday_path(date)
    if path.startswith("<"):
        raise SystemExit("untouched: GROUNDTRUTH_CLIENT_HOME is not set")
    if mode == "save":
        # The state folders and the clients' throwaway homes are checked before any login: where each client will
        # write (no link out, no checkout, no everyday folder).
        import clients as C
        base = os.path.dirname(night_dir(date))
        real_user = os.path.realpath(user_home or os.path.expanduser("~"))
        for name in STATE_FOLDERS:
            folder = os.path.join(base, name)
            if not os.path.isdir(folder):
                raise SystemExit(f"untouched: {folder} does not exist: create the state folders first")
            C.check_folder(f"untouched: {name}", folder, ROOT, real_user)
            out_links = C.links_out(folder)
            if out_links:
                raise SystemExit(f"untouched: {name} holds links that leave it: {', '.join(out_links[:5])}")
            C.prepare_home(f"untouched: {name}", folder, base, ROOT, real_user)
    now = {"files": snapshot_files(user_home), "keychain": keychain_items(lister)}
    if mode == "save":
        if os.path.exists(path):
            raise SystemExit(f"untouched: a snapshot of {date} exists already; it is taken once, before the logins")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(now, f)
        os.chmod(path, 0o600)
        out(f"saved: {len(now['files'])} paths under the everyday folders, {len(now['keychain'])} Keychain items")
        return []
    if not os.path.exists(path):
        raise SystemExit(f"untouched: no snapshot of {date}: `untouched --save` is step 1, before the logins")
    with open(path) as f:
        before = json.load(f)
    changed = compare_everyday(before, now)
    report = report_path(date, at)
    os.makedirs(os.path.dirname(report), exist_ok=True)
    with open(report, "w") as f:
        f.write(f"The everyday state against the snapshot of {date}, taken before the logins: for a person to judge. "
                "The owner's own use of his tools changes these folders too.\n")
        f.write("".join(x + "\n" for x in changed) or "nothing changed\n")
    os.chmod(report, 0o600)
    if not changed:
        out("report: nothing changed under the everyday folders nor in the Keychain's item names")
        return changed
    counts = {}
    for x in changed:
        top = top_folder(x)
        counts.setdefault(top, {})
        kind = x.split(":", 1)[0].split()[-1]
        counts[top][kind] = counts[top].get(kind, 0) + 1
    out(f"report: {len(changed)} differences since the snapshot (every one in {report}):")
    for top in sorted(counts):
        out(f"  {top}: " + ", ".join(f"{n} {k}" for k, n in sorted(counts[top].items())))
    for x in changed:
        if x.startswith("Keychain"):
            out("  " + x)
    return changed


# --- --go: the owner's night only -----------------------------------------------------------------------------------

def keychain(item):
    return subprocess.run(["security", "find-generic-password", "-a", os.environ["USER"], "-s", item, "-w"],
                          check=True, capture_output=True, text=True).stdout.strip()


# Direct: no proxy of the environment (HTTPS_PROXY could name the owner's proxy), ever.
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def openrouter_get(path, key):
    req = urllib.request.Request(OPENROUTER + path, headers={"Authorization": "Bearer " + key, "User-Agent": "groundtruth"})
    with DIRECT.open(req, timeout=60) as r:
        return json.load(r)


def openrouter_post(path, body, key, timeout=900):
    req = urllib.request.Request(OPENROUTER + path, data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    t = time.time()
    try:
        with DIRECT.open(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}"), time.time() - t
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw), time.time() - t
        except ValueError:
            return e.code, {"raw": raw[:2000]}, time.time() - t


def done(step, date):
    """A step already done or running: its raw file, its pid file, its window row."""
    folder = os.path.join(ROOT, folder_of(step, date))
    if step["kind"] == "window":
        rows = os.path.join(folder, "windows.jsonl")
        if not os.path.exists(rows):
            return False
        with open(rows) as f:
            return any(json.loads(x).get("model") == step["model"] for x in f if x.strip())
    if os.path.exists(os.path.join(folder, "logs", step["id"] + ".pid")):
        return True
    return os.path.exists(os.path.join(folder, step["id"] + ".jsonl")) or bool(glob.glob(os.path.join(folder, step["id"] + "-20*.json")))


def estimate(step, key, get):
    """The most an OpenRouter cache run can cost: 90 requests of 3,000 prompt tokens and 32 output tokens at the dearest
    endpoint's price (a cache write billed as input). A window request is refused, so free."""
    if step["kind"] != "openrouter":
        return 0.0
    eps = (get(f"/models/{step['model']}/endpoints", key).get("data") or {}).get("endpoints") or []
    if not eps:
        return None
    price_in = max(float((e.get("pricing") or {}).get("prompt") or 0) for e in eps)
    price_out = max(float((e.get("pricing") or {}).get("completion") or 0) for e in eps)
    return round(90 * (3000 * price_in + 32 * price_out), 4)


def committed(date, steps_running):
    """The estimates of OpenRouter runs started and not finished (no result file yet)."""
    total = 0.0
    folder = os.path.join(ROOT, folders(date)["or"])
    for path in glob.glob(os.path.join(folder, "logs", "*.estimate")):
        rid = os.path.basename(path)[:-len(".estimate")]
        if not glob.glob(os.path.join(folder, rid + "-20*.json")):
            with open(path) as f:
                total += float(f.read().strip() or 0)
    return total + sum(steps_running)


def budget(step, key, date, get):
    """Checked before every OpenRouter request or run: what the key has spent, plus what runs already started may
    still spend, plus this one's worst case, must stay under the stop. An unknown spend stops."""
    usage = (get("/key", key).get("data") or {}).get("usage")
    if not isinstance(usage, (int, float)):
        raise SystemExit("OpenRouter: the key's spend is unknown: nothing started")
    est = estimate(step, key, get)
    if est is None:
        return None  # no longer offered
    owed = committed(date, [])
    if usage + owed + est > MONEY_STOP:
        raise SystemExit(f"{step['id']}: {usage:.2f} USD spent + {owed:.2f} committed + {est:.2f} for this run would pass "
                         f"the {MONEY_STOP:.2f} USD stop: not started")
    return est


def reviewed_path(date):
    return os.path.join(night_dir(date), "smoke-reviewed")


def guard(names, steps, date):
    parts = {PART_OF[s["id"]] for s in steps}
    if names == ["all"]:
        raise SystemExit("--go all: no; name the parts in the order of docs/own-clients-RUN.md")
    if "smoke" in parts and len(parts) > 1:
        raise SystemExit("--go: the smoke runs go alone; read their results, then `smoke-reviewed`, then the rest")
    if parts & LOGIN_PARTS and not os.path.exists(reviewed_path(date)):
        raise SystemExit("--go: a login's runs wait until the smoke results were read (`night.py --date ... smoke-reviewed`)")
    if night_dir(date).startswith("<"):
        raise SystemExit("--go: GROUNDTRUTH_CLIENT_HOME is not set")
    if any(s.get("harness") == "pi" for s in steps) and not pi_ready():
        raise SystemExit("--go: pi's folder is not set up: `night.py --date ... pi-setup` first")


def last_event(path):
    try:
        with open(path) as f:
            lines = [x for x in f if x.strip()]
        return json.loads(lines[-1]) if lines else None
    except (OSError, ValueError):
        return None


def go(steps, date, popen=None, run=None, sleep=None, get=None, out=print):
    popen, run = popen or subprocess.Popen, run or subprocess.run
    sleep, get = sleep or time.sleep, get or openrouter_get
    keys = {}

    def key(name):
        if name not in keys:
            keys[name] = keychain(KEYCHAIN[name])
            scan_secrets.remember(keys[name], name)
        return keys[name]
    failed = []
    for i, step in enumerate(steps):
        if done(step, date):
            out(f"{step['id']}: done or running already (a raw file, a pid file or a window row): skipped")
            continue
        argv = command(step, date)
        extra = {}
        if step["kind"] in ("openrouter", "window"):
            est = budget(step, key("OPENROUTER"), date, get)
            if est is None:
                out(f"{step['id']}: {step['model']} is no longer offered: written down, not run")
                continue
            extra["CACHE_PROBE_KEY"] = key("OPENROUTER")
        if step["kind"] == "proxy-plain":
            extra["CACHE_PROBE_KEY"] = key("PROVIMUX")
        if step.get("harness") == "muse":
            extra["META_API_KEY"] = key("META_API_KEY")
        if step.get("harness") == "pi":
            extra["CLIPROXYAPI_API_KEY"] = key("PROVIMUX")  # the variable pi-provimux reads first
        env = clean_env(extra)
        logs = os.path.join(ROOT, folder_of(step, date), "logs")
        os.makedirs(logs, exist_ok=True)
        if step["kind"] in ("smoke", "window"):
            # In the foreground, one after the other: the launcher waits for each, and a failure stops it.
            out(f"== {step['id']}: {shown(argv)}")
            code = run(["caffeinate", "-i", *argv], cwd=ROOT, env=env).returncode
            if step["kind"] == "window":
                if code == 3:
                    out("a window request was answered: the list ends here, the next one waits for a decision")
                    return failed
                if code:
                    raise SystemExit(f"{step['id']}: exited {code}: the night stops here")
                continue
            ev = last_event(os.path.join(ROOT, folder_of(step, date), step["id"] + ".jsonl"))
            if code or not ev or ev.get("event") != "done":
                failed.append(step["id"])
                out(f"{step['id']}: exit {code}, last event {json.dumps(ev)[:200] if ev else 'none'}")
            continue
        with open(os.path.join(logs, step["id"] + ".log"), "a") as log:
            p = popen(["nohup", "caffeinate", "-i", *argv], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                      stdin=subprocess.DEVNULL, start_new_session=True)
        with open(os.path.join(logs, step["id"] + ".pid"), "w") as f:
            f.write(f"{p.pid}\n")
        if step["kind"] == "openrouter":
            with open(os.path.join(logs, step["id"] + ".estimate"), "w") as f:
                f.write(f"{est}\n")
        line = f"{step['id']} pid {p.pid} started {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {step.get('model')}"
        with open(os.path.join(logs, "launches.txt"), "a") as f:
            f.write(line + "\n")
        out(line)
        nxt = steps[i + 1] if i + 1 < len(steps) else None
        if nxt and nxt["kind"] in ("probe", "openrouter", "proxy-plain"):
            sleep(SPACING.get(step.get("harness"), 15))
    if failed:
        raise SystemExit(f"smoke runs that did not end with `done`: {', '.join(failed)}: read them before going on")
    return failed


def window(model, date, live, out=print, post=None, get=None):
    """One window request straight to OpenRouter (never through a proxy): only with --go, inside the money stop."""
    body = window_body(model)
    if not live:
        out(f"POST {OPENROUTER}/chat/completions {json.dumps(window_body(model, 3)).replace('hello hello hello', 'hello × 1,200,000')}"
            " (direct). Not sent: add --go to send it.")
        return
    key = os.environ.get("CACHE_PROBE_KEY")
    if not key:
        raise SystemExit("window: run it through `night.py --go windows`, which reads the campaign's key")
    step = {"id": "window " + model, "kind": "window", "model": model}
    if budget(step, key, date, get or openrouter_get) is None:
        raise SystemExit(f"{model}: no longer offered")
    out_path = os.path.join(ROOT, folders(date)["or"], "windows.jsonl")
    if done(step, date):
        raise SystemExit(f"{model}: its window request was sent already")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    code, data, secs = (post or openrouter_post)("/chat/completions", body, key)
    sys.path.insert(0, HERE)
    import limits as L
    row = {"kind": "context", "model": model, "n": 1_200_000, "status": code, "seconds": round(secs, 1),
           "promptTokens": L.prompt_tokens("chat", data) if code == 200 else None,
           "message": None if code == 200 else L.message(data),
           "metadata": (data.get("error") or {}).get("metadata") if isinstance(data.get("error"), dict) else None, "at": at}
    with open(out_path, "a") as f:
        f.write(json.dumps(row) + "\n")
    out(json.dumps(row)[:800])
    if code == 200:
        sys.exit(3)


def group_commands(pgid):
    """The commands of a process group (empty when it has ended)."""
    lines = subprocess.run(["ps", "-ax", "-o", "pgid=,command="], capture_output=True, text=True).stdout.splitlines()
    return "\n".join(x.split(None, 1)[1] for x in lines if len(x.split(None, 1)) > 1 and x.split(None, 1)[0] == str(pgid))


def stop(step_id, date, ps=None, killpg=None, out=print):
    """Stop one detached run: its pid file in its own folder, the process checked to be that run before the signal."""
    step = ALL_STEPS.get(step_id)
    if not step:
        raise SystemExit(f"{step_id}: not an id of the plan")
    pid_file = os.path.join(ROOT, folder_of(step, date), "logs", step_id + ".pid")
    if not os.path.exists(pid_file):
        raise SystemExit(f"{step_id}: no pid file at {os.path.relpath(pid_file, ROOT)}")
    with open(pid_file) as f:
        pid = int(f.read().strip())
    seen = (ps or group_commands)(pid)
    if f"--label {step_id} " not in seen + " ":
        raise SystemExit(f"{step_id}: process group {pid} is not this run (it ended, or the pid was reused): nothing sent")
    (killpg or os.killpg)(pid, signal.SIGTERM)
    out(f"{step_id}: process group {pid} stopped")


# --- pi's own folder -------------------------------------------------------------------------------------------------

def pi_folder():
    base = os.environ.get("GROUNDTRUTH_CLIENT_HOME")
    if not base:
        raise SystemExit("pi-setup: GROUNDTRUTH_CLIENT_HOME is not set")
    return base, os.path.join(base, "pi-provimux")


def pi_package_dir():
    src = os.environ.get("PI_PROVIMUX_DIR")
    if not src:
        raise SystemExit("pi-setup: PI_PROVIMUX_DIR (the pi-provimux checkout) is not set")
    return os.path.realpath(src)


def pi_ready(folder=None, src=None):
    """pi's folder lists the pi-provimux checkout among its packages (pi's own settings.json)."""
    try:
        folder = folder or pi_folder()[1]
        src = src or pi_package_dir()
        with open(os.path.join(folder, "settings.json")) as f:
            packages = json.load(f).get("packages") or []
    except (SystemExit, OSError, ValueError):
        return False
    for p in packages:
        source = p.get("source") if isinstance(p, dict) else p
        if isinstance(source, str) and os.path.realpath(os.path.join(folder, os.path.expanduser(source))) == src:
            return True
    return False


def pi_setup(run=None, user_home=None, out=print):
    """Sets up <client-home>/pi-provimux with pi's own command (`pi install <checkout>`, PI_CODING_AGENT_DIR pointing
    there) and pi-provimux's configuration file with the proxy's address and no key: the key reaches pi only at the
    night's go, from the Keychain, in CLIPROXYAPI_API_KEY. ~/.pi is never read or copied; a folder that is not under
    GROUNDTRUTH_CLIENT_HOME (a link out of it) is refused."""
    import clients as C
    run = run or subprocess.run
    user_home = os.path.realpath(user_home or os.path.expanduser("~"))
    base, folder = pi_folder()
    src = pi_package_dir()
    os.makedirs(folder, exist_ok=True)
    real, real_base = os.path.realpath(folder), os.path.realpath(base)
    if real == real_base or not C.inside(real, real_base):
        raise SystemExit("pi-setup: <client-home>/pi-provimux is not under GROUNDTRUTH_CLIENT_HOME (a link out of it): refused")
    C.check_folder("pi-setup: pi's folder", folder, ROOT, user_home)
    out_links = C.links_out(folder)
    if out_links:
        raise SystemExit(f"pi-setup: pi's folder holds links that leave it: {', '.join(out_links[:5])}")
    if C.inside(src, os.path.join(user_home, ".pi")):
        raise SystemExit("pi-setup: PI_PROVIMUX_DIR is under ~/.pi: give the pi-provimux checkout, never ~/.pi")
    try:
        with open(os.path.join(src, "package.json")) as f:
            if "pi" not in json.load(f):
                raise ValueError
    except (OSError, ValueError):
        raise SystemExit("pi-setup: PI_PROVIMUX_DIR has no package.json with a `pi` manifest: not a pi package")
    config = os.path.join(folder, "cliproxyapi.json")
    current = {}
    if os.path.exists(config):
        with open(config) as f:
            current = json.load(f)
        if current.get("apiKey"):
            raise SystemExit("pi-setup: <client-home>/pi-provimux/cliproxyapi.json holds a key: remove it (the key "
                             "comes from the Keychain at the night's go)")
    env = {k: os.environ[k] for k in C.ALLOW if k in os.environ}
    # pi's own HOME, as every pi run has it: `pi install` writes nothing under the owner's home folder.
    env["HOME"] = C.prepare_home("pi-setup", folder, base, ROOT, user_home)
    env.update({"PI_CODING_AGENT_DIR": folder, "PI_SKIP_VERSION_CHECK": "1", "PI_OFFLINE": "1", "PI_TELEMETRY": "0"})
    if not pi_ready(folder, src):
        p = run(["pi", "install", src], env=env, cwd=folder, capture_output=True, text=True, timeout=300)
        if p.returncode:
            raise SystemExit(f"pi-setup: `pi install` exited {p.returncode}: {(p.stderr or p.stdout).strip()[-500:]}")
    current.update({"baseUrl": C.PROVIMUX_ROOT, "fast": False, "pause": False})
    with open(config, "w") as f:
        json.dump(current, f, indent=2)
    if not pi_ready(folder, src):
        raise SystemExit("pi-setup: pi's settings.json does not list the pi-provimux checkout after `pi install`")
    out("pi-setup: pi's folder lists pi-provimux; the proxy at " + C.PROVIMUX_ROOT + ", no key stored (it comes from the "
        "Keychain at the go)")
    return True


# --- --go night: the supervisor -------------------------------------------------------------------------------------

def logs_dir(date):
    return os.path.join(ROOT, folders(date)["own"], "logs")


def s3b_cached(date):
    """Whether the smoke run S3b (Devin, gpt-6-1-terra) saw any cached token: DV-6's pi run is worth it only then."""
    path = os.path.join(ROOT, folders(date)["smoke"], "S3b.jsonl")
    try:
        with open(path) as f:
            events = [json.loads(x) for x in f if x.strip()]
    except (OSError, ValueError):
        return False
    return any(e.get("event") == "check" and ((e.get("usage") or {}).get("cached") or 0) > 0 for e in events)


def night_parts(date):
    return [p for p in NIGHT if p != "devin-terra-pi" or s3b_cached(date)]


def state(step, date, ps=None):
    """not started, running, done, failed (with why), or a window's answer."""
    folder = os.path.join(ROOT, folder_of(step, date))
    if step["kind"] == "window":
        rows = os.path.join(folder, "windows.jsonl")
        if os.path.exists(rows):
            with open(rows) as f:
                for x in f:
                    r = json.loads(x) if x.strip() else {}
                    if r.get("model") == step["model"]:
                        return "done", f"status {r.get('status')}"
        return "not started", ""
    ev = last_event(os.path.join(folder, step["id"] + ".jsonl"))
    if ev and ev.get("event") == "done":
        return "done", ""
    if ev and ev.get("event") == "stop":
        return "failed", "stop: " + str(ev.get("reason") or ev.get("why") or "")[:120]
    if glob.glob(os.path.join(folder, step["id"] + "-20*.json")):
        return "done", ""
    pid_file = os.path.join(folder, "logs", step["id"] + ".pid")
    if not os.path.exists(pid_file):
        return "not started", ""
    with open(pid_file) as f:
        pid = f.read().strip()
    if f"--label {step['id']} " in (ps or group_commands)(pid) + " ":
        return "running", f"pid {pid}"
    return "failed", "ended without a `done` line (see its log)"


def ended(step, date, ps=None):
    return state(step, date, ps)[0] != "running"


def supervisor_pid(date, ps=None):
    """The supervisor's process group, when it runs."""
    path = os.path.join(logs_dir(date), "supervisor.pid")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        pid = f.read().strip()
    return int(pid) if f"--date {date} " in (ps or group_commands)(pid) and " supervise" in (ps or group_commands)(pid) else None


def supervise(date, go_=None, sleep=None, ps=None, out=None, poll=60):
    """The night after the smoke review, launch by launch; it runs detached (`--go night`). A part that cannot start
    (the money stop, a run no longer offered) is written down and the next part goes on. At the end, the morning
    report of the everyday state (never a stop)."""
    go_, sleep = go_ or go, sleep or time.sleep

    def say(line):
        line = time.strftime("%Y-%m-%dT%H:%M:%SZ ", time.gmtime()) + line
        (out or print)(line)
        if out is None:
            sys.stdout.flush()
    if not os.path.exists(reviewed_path(date)):
        raise SystemExit("supervise: the smoke results were not marked as read")
    say(f"supervisor: the night of {date} starts; parts {', '.join(night_parts(date))}, then claude-5m")
    if "devin-terra-pi" not in night_parts(date):
        say("devin-terra-pi: left out: S3b showed no cached token (DV5 measures nothing through Devin)")
    for part in night_parts(date):
        say(f"part {part}")
        try:
            go_(select([part]), date, out=say)
        except SystemExit as e:
            say(f"part {part}: {e}; the next part goes on")
    for part, first in LATER.items():
        while not all(ended(ALL_STEPS[i], date, ps) for i in first):
            sleep(poll)
        say(f"part {part}: {', '.join(first)} have ended")
        try:
            go_(select([part]), date, out=say)
        except SystemExit as e:
            say(f"part {part}: {e}")
    every = select(night_parts(date) + list(LATER))
    while not all(ended(s, date, ps) for s in every):
        sleep(poll * 5)
    say("every run has ended; the morning report of the everyday state:")
    try:
        untouched(date, "report", out=say)
    except (SystemExit, OSError) as e:
        say(f"the everyday report could not be written: {e}")
    say("the night is over")
    return True


def launch_night(date, popen=None, out=print, ps=None):
    """`--go night`: the checks in the foreground, then the supervisor, detached (it survives the terminal)."""
    steps = select(["night"])
    guard(["night"], steps, date)
    if supervisor_pid(date, ps):
        raise SystemExit("--go night: the supervisor runs already (`status`)")
    if not os.path.exists(everyday_path(date)):
        raise SystemExit("--go night: no snapshot of the everyday state (`untouched --save`, step 1): the morning "
                         "report needs it; nothing started")
    logs = logs_dir(date)
    os.makedirs(logs, exist_ok=True)
    argv = [sys.executable, "harness/night.py", "--date", date, "--provimux-config", PROVIMUX_CONFIG, "supervise"]
    with open(os.path.join(logs, "supervisor.log"), "a") as log:
        p = (popen or subprocess.Popen)(["nohup", "caffeinate", "-i", *argv], cwd=ROOT,
                                        env=clean_env({"GROUNDTRUTH_NIGHT_SUPERVISOR": "1"}), stdout=log,
                                        stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    with open(os.path.join(logs, "supervisor.pid"), "w") as f:
        f.write(f"{p.pid}\n")
    out(f"the night's supervisor runs (pid {p.pid}); the terminal may be closed. "
        f"`python3 harness/night.py --date {date} status` shows the night; its log: "
        f"{os.path.relpath(os.path.join(logs, 'supervisor.log'), ROOT)}")
    return p.pid


def dry_run_night(date, out=print):
    out(f"`--go night`: checks (smoke reviewed, pi's folder, step 1's snapshot taken), then a detached supervisor "
        f"(nohup caffeinate -i python3 harness/night.py --date {date} supervise; it survives the terminal). It "
        "launches, checking (OpenRouter) the money stop before each launch, skipping what is done; every client "
        "process has its state folder and its throwaway HOME under <client-home>:")
    for n, part in enumerate(NIGHT, 1):
        cond = " (only if S3b showed cached tokens: read from the smoke results at the go)" if part == "devin-terra-pi" else ""
        out(f"  {n}. {part}{cond}: {', '.join(s['id'] for s in select([part]))}")
    for part, first in LATER.items():
        out(f"  then {part} ({', '.join(s['id'] for s in select([part]))}) when {', '.join(first)} have ended")
    out("  then it waits for the last run and writes the morning report of the everyday state (never a stop).")
    steps = [s for part in NIGHT + list(LATER) for s in select([part])]
    dry_run(steps, date, out=out)
    out(f"Dry run of `--go night`: {len(steps)} steps; nothing run, nothing sent.")


def status(date, ps=None, out=print):
    sup = supervisor_pid(date, ps)
    out(f"supervisor: {'running, pid ' + str(sup) if sup else 'not running'}")
    log = os.path.join(logs_dir(date), "supervisor.log")
    if os.path.exists(log):
        with open(log) as f:
            tail = [x.rstrip() for x in f if x.strip()][-3:]
        out("\n".join("  " + x for x in tail))
    counts = {}
    for step in select(["smoke"]) + select(night_parts(date) + list(LATER)):
        st, why = state(step, date, ps)
        counts[st] = counts.get(st, 0) + 1
        out(f"{step['id']:8} {st}{'  ' + why if why else ''}")
    out(", ".join(f"{v} {k}" for k, v in counts.items()))
    return counts


def stop_all(date, ps=None, killpg=None, out=print):
    """The supervisor first (nothing more starts), then every run still running."""
    killpg = killpg or os.killpg
    sup = supervisor_pid(date, ps)
    if sup:
        killpg(sup, signal.SIGTERM)
        out(f"supervisor (process group {sup}) stopped")
    for step in select(["all"]):
        if state(step, date, ps)[0] == "running":
            stop(step["id"], date, ps=ps, killpg=killpg, out=out)


def main(argv=None):
    global PROVIMUX_CONFIG
    ap = argparse.ArgumentParser(description="The run plan of docs/own-clients.md, section 4")
    ap.add_argument("--date", required=True, help="the night's date, YYYY-MM-DD: names the results folders")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print every command and each tool's own dry run; send nothing")
    mode.add_argument("--go", action="store_true", help="run them (the owner's go only)")
    ap.add_argument("what", nargs="+", help="parts or ids (all = every part, for a dry run; night = all but the smoke "
                                             "runs, under the supervisor); or: untouched, pi-setup, smoke-reviewed, "
                                             "status, stop all|<id>, window <model>")
    ap.add_argument("--provimux-config", default=PROVIMUX_CONFIG,
                    help=f"Provimux's configuration: each pi run records its payload section, nothing else (default "
                         f"{PROVIMUX_CONFIG})")
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)
    PROVIMUX_CONFIG = a.provimux_config
    head = a.what[0]
    if head == "pi-setup":
        pi_setup()
        return
    if head == "status":
        status(a.date)
        return
    if head == "supervise":
        if os.environ.get("GROUNDTRUTH_NIGHT_SUPERVISOR") != "1":
            raise SystemExit("supervise: started by `--go night` only")
        supervise(a.date)
        return
    if head == "untouched":
        m = "save" if a.save else "report" if a.report else None
        if not m:
            raise SystemExit("untouched: --save (step 1, before the logins) or --report (any time after)")
        untouched(a.date, m)
        return
    if head == "smoke-reviewed":
        os.makedirs(night_dir(a.date), exist_ok=True)
        with open(reviewed_path(a.date), "w") as f:
            f.write(time.strftime("%Y-%m-%dT%H:%M:%SZ\n", time.gmtime()))
        print("the smoke results are marked as read: the logins' parts may start")
        return
    if head == "stop":
        if len(a.what) < 2:
            raise SystemExit("stop all, or stop <id>")
        stop_all(a.date) if a.what[1] in ("all", "night") else stop(a.what[1], a.date)
        return
    if head == "window":
        window(a.what[1], a.date, live=a.go)
        return
    steps = select(a.what)
    if a.what == ["night"] and a.dry_run:
        dry_run_night(a.date)
    elif a.what == ["night"] and a.go:
        launch_night(a.date)
    elif a.dry_run:
        dry_run(steps, a.date)
        print(f"Dry run of {len(steps)} steps: nothing run, nothing sent.")
    elif a.go:
        guard(a.what, steps, a.date)
        go(steps, a.date)
    else:
        for s in steps:
            print(f"{s['id']}: {shown(command(s, a.date))}")
        print("Listed only: --dry-run runs each tool's dry run, --go runs them.")


if __name__ == "__main__":
    main()
