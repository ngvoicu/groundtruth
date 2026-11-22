#!/usr/bin/env python3
"""The first night of docs/own-clients.md, section 4, cut down to the own clients' cache runs of Codex CLI and Devin
CLI, each through its own subscription login (the owner's decision of 2026-11-22: the two logins where differences
were seen; Claude Code and Muse Code wait for a later night, and every night command refuses them). The owner's steps
are docs/own-clients-RUN.md.

    python3 harness/night.py --date 2026-11-23 untouched --save|--report   # the everyday state: snapshot, report
    python3 harness/night.py --date 2026-11-23 login codex|devin           # a login, in the client's own folders
    python3 harness/night.py --date 2026-11-23 --dry-run all               # every command, each run's own dry run
    python3 harness/night.py --date 2026-11-23 --go smoke                  # in the foreground, about 10 minutes
    python3 harness/night.py --date 2026-11-23 smoke-reviewed              # checks the smoke results, then marks them
    python3 harness/night.py --date 2026-11-23 --go codex|devin|all        # a client's runs, in the background
    python3 harness/night.py --date 2026-11-23 status                      # which runs are alive (by their process)
    python3 harness/night.py --date 2026-11-23 stop codex|devin|all        # the launcher, then exactly its runs

Parts: smoke (S2, S3, S3b), codex (CX1 - CX6), devin (DV1 - DV17, DV9d). `all`, for --go and stop: the two clients.

Not in the first night: no Claude Code or Muse Code run, login or key (and so no overage logic and no key read from the
Keychain),
no pi run and no Provimux (the parity pairs come in a later night), no OpenRouter run and no
window request (and so no money stop), no supervisor, no input-limit walk, no Antigravity run.

`--go <client>` starts each of the client's runs as its own background process (`caffeinate -i`, a session of its
own: closing the terminal ends none), each told when to begin (--delay: the starts are staggered), and returns. A
client's launch is written once, in a lock file created exclusively (<client-home>/night-<date>/launch/<client>.json:
the launch's id, the launcher's own pid, written before any run starts, and each run's pid as it starts); a second go
of that client for that night is refused. Before each start the launcher looks for the client's stop mark
(launch/<client>.stop) and starts nothing more once it is there; right after each start (the run's pid recorded) it
looks again, and a mark found then stops the run it just started and ends the launch. `stop` writes that mark first,
before it looks anything up; then waits for this night's launcher (found on the process table, lock or no lock) to
end, at most a few seconds, signalling it if it does not; then signals the process group of exactly the client's runs:
those the lock records (pid alive, and its command line carrying the run's label and the launch's id), and any
process carrying this night's launch id for the client.

Every command honours --dry-run: it prints what it would do and does nothing else (no folder, no marker, no lock, no
signal, no client run). Nothing is sent without --go. The owner's everyday state is protected by isolation (each
client's state folder and throwaway HOME, and sandbox-exec: harness/clients.py) and reported in the morning
(`untouched --report`), never a reason to stop. No key is read: Codex and Devin use their logins in their state folders.
"""
import sys
sys.dont_write_bytecode = True  # a dry run writes nothing, not even the interpreter's cache
import argparse  # noqa: E402
import json
import os
import signal
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import clients as C  # noqa: E402

STD65 = "10m,15m,20m,25m,30m,40m,50m,60m,65m,75m,90m,120m"
PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy",
              "NODE_USE_ENV_PROXY", "GLOBAL_AGENT_HTTP_PROXY", "GLOBAL_AGENT_HTTPS_PROXY")
SECRETS = ("CACHE_PROBE_KEY", "META_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
           "CLIPROXYAPI_API_KEY")


def probe(id_, harness, model, ages=None, schedule=None, filler=None, env=None, extra=(), pair=None, after=0):
    args = ["--harness", harness, "--model", model, "--replicas", "3", "--label", id_]
    args += ["--ages", ages] if ages else ["--schedule", schedule or "std"]
    if filler:
        args += ["--filler", filler]
    for k, v in (env or {}).items():
        args += ["--client-env", f"{k}={v}"]
    args += list(extra)
    return {"id": id_, "kind": "probe", "harness": harness, "model": model, "args": args, "pair": pair, "after": after}


def smoke(id_, harness, model, filler=None):
    """Baseline and the control checked at 30 s; the output kept, redacted, outside the repository."""
    return {"id": id_, "kind": "smoke", "harness": harness, "model": model,
            "args": ["--harness", harness, "--model", model, "--replicas", "0", "--waves", "1", "--label", id_,
                     "--schedule", "std", *(["--filler", filler] if filler else [])]}


CX = [probe(f"CX{i}", "codex", m, schedule="long") for i, m in enumerate(
    ["gpt-6.2-sol", "gpt-6.2-astra", "gpt-6.1-sol", "gpt-6.1-terra", "gpt-6-astra", "gpt-6-luna"], 1)]
DEVIN = [("DV1", "claude-opus-5-5-low", "std"), ("DV2", "claude-sonnet-5-5-low", "std"), ("DV3", "claude-haiku-5-5-low", "std"),
         ("DV4", "gpt-6-1-sol-low", "std"), ("DV5", "gpt-6-1-terra-low", "std"), ("DV6", "gpt-6-astra-low", "std"),
         ("DV7", "gpt-6-luna-low", "std"),
         ("DV8", "deepseek-v4-1-flash-1017-low", "long"), ("DV9", "glm-5-3-low", "std"), ("DV10", "kimi-k3-1-pro-low", "long"),
         ("DV11", "nemotron-3-5-super-none", "long"),
         ("DV12", "deepseek-v4-pro-low", "std"), ("DV13", "gemini-4-argon-low", "std"), ("DV14", "grok-4-7-low", "std"),
         ("DV15", "kimi-k3-low", "std"), ("DV16", "muse-wonder-1-0-low", "std"), ("DV17", "swe-2-medium", "std")]
# DV9d: DV9 again with Devin's own process model and keepalive (pair DV-5 compares the two; both are Devin runs).
DV = [probe(i, "devin", m, schedule=s) for i, m, s in DEVIN] + [
    probe("DV9d", "devin", "glm-5-3-low", schedule="std", extra=["--devin-daemon"], pair="DV-5")]
PARTS = {
    "smoke": [smoke("S2", "codex", "gpt-6-luna"), smoke("S3", "devin", "claude-haiku-5-5-low"),
              smoke("S3b", "devin", "gpt-6-1-terra-low")],
    "codex": CX,
    "devin": DV,
}
CLIENT_PARTS = ("codex", "devin")
# Clients whose drivers stay in harness/clients.py (and their tests) but that no night command reaches.
NOT_THIS_NIGHT = {"claude": "Claude Code", "muse": "Muse Code"}
ORDER = ["smoke", *CLIENT_PARTS]
ALL_STEPS = {s["id"]: s for part in ORDER for s in PARTS[part]}
PART_OF = {s["id"]: part for part in ORDER for s in PARTS[part]}
# Seconds between two starts of one client's runs (Devin's as on 8 November).
SPACING = {"devin": 20}
SPACING_DEFAULT = 15
STATE_FOLDERS = tuple(C.CLIENTS[h].client_id for h in CLIENT_PARTS)
LOGINS = {"codex": ["codex", "login", "-c", 'cli_auth_credentials_store="file"', "-c", 'model_provider="openai"'],
          "devin": ["devin", "auth", "--process-model", "in-process", "login"]}


def folders(date):
    own = os.path.join("results", f"own-clients-{date}")
    return {"own": own, "smoke": os.path.join(own, "smoke")}


def folder_of(step, date):
    f = folders(date)
    return f["smoke"] if step["kind"] == "smoke" else f["own"]


def client_home():
    return os.environ.get("GROUNDTRUTH_CLIENT_HOME")


def night_dir(date, base=None):
    base = base or client_home()
    return os.path.join(base, f"night-{date}") if base else f"<client-home>/night-{date}"


def need_client_home(what):
    if not client_home():
        raise SystemExit(f"{what}: GROUNDTRUTH_CLIENT_HOME is not set")
    return client_home()


def make_night_dir(date):
    """<client-home>/night-<date>, mode 700, checked like a state folder (local, private, no link)."""
    base = need_client_home("night")
    d = night_dir(date)
    if os.path.islink(d):
        raise SystemExit(f"{d}: a link: refused")
    C.check_folder("<client-home>", base, ROOT, os.path.realpath(os.path.expanduser("~")))
    C.check_private("<client-home>", os.path.abspath(base))
    if not os.path.isdir(d):
        os.mkdir(d, 0o700)
        os.chmod(d, 0o700)
    C.check_folder("<client-home>/night-<date>", d, ROOT, os.path.realpath(os.path.expanduser("~")))
    C.check_private("<client-home>/night-<date>", d)
    return d


def delay_of(step, index):
    """When a client's run begins after its go: its place in the client's list, spaced, plus its own wait."""
    return index * SPACING.get(step.get("harness"), SPACING_DEFAULT) + step.get("after", 0)


def command(step, date, launch_id=None, delay=None):
    """The argument list of a step, run from the repository's root."""
    folder = folder_of(step, date)
    argv = [sys.executable, "harness/probe.py", *step["args"], "--out", folder]
    if step["kind"] == "smoke":
        argv += ["--keep-raw", os.path.join(night_dir(date), "raw", step["id"])]
    if delay:
        argv += ["--delay", str(delay)]
    if launch_id:
        argv += ["--launch-id", launch_id]
    return argv


def select(names):
    if names == ["all"]:
        names = list(CLIENT_PARTS)
    steps = []
    for n in names:
        if n in PARTS:
            steps += [s for s in PARTS[n] if s not in steps]
        elif n in ALL_STEPS:
            steps.append(ALL_STEPS[n])
        else:
            raise SystemExit(f"{n}: not a part ({', '.join(ORDER)}, all) nor an id of the plan")
    return steps


def shown(argv):
    return " ".join(a if a and " " not in a else json.dumps(a) for a in ["python3" if argv[0] == sys.executable else argv[0], *argv[1:]])


def clean_env(extra=None):
    """The launcher's children: no key, no proxy of the shell, then what this step needs."""
    env = {k: v for k, v in os.environ.items() if k not in SECRETS and k not in PROXY_VARS}
    env.update(extra or {})
    return env


def dry_run(steps, date, out=print):
    for i, step in enumerate(steps):
        argv = command(step, date, launch_id="<launch-id>" if step["kind"] == "probe" else None,
                       delay=delay_of(step, i) if step["kind"] == "probe" else None)
        out(f"== {step['id']}: {shown(argv)}")
        p = subprocess.run([*argv, "--dry-run"], cwd=ROOT, capture_output=True, text=True, timeout=120,
                           env=clean_env({"PYTHONDONTWRITEBYTECODE": "1"}))
        text = (p.stdout + p.stderr).strip()
        out("\n".join("   " + line for line in text.splitlines()))
        if p.returncode:
            raise SystemExit(f"{step['id']}: its dry run failed")


# --- the everyday state: folders (recursively) and the Keychain's item names, reported (never a stop) --------------

EVERYDAY = ["~/.claude", "~/.claude.json", "~/.codex", "~/.devin", "~/.config/devin", "~/.local/share/devin",
            "~/.config/muse", "~/.local/share/muse", "~/.muse", "~/.pi"]


def snapshot_files(user_home=None, vanished=None):
    """Path, size and modification time of every file, folder and link under the everyday folders (nothing read). A
    path the owner's own tools remove while the walk passes (a rotated log, a replaced session file) is not an error:
    it is left out and named in `vanished`."""
    home = user_home or os.path.expanduser("~")
    vanished = vanished if vanished is not None else []
    out = {}

    def stat(p, key):
        try:
            st = os.lstat(p)
        except FileNotFoundError:
            vanished.append(key)
            return
        out[key] = [st.st_size, st.st_mtime_ns]

    for d in EVERYDAY:
        top = home + d[1:]
        if not os.path.lexists(top):
            continue

        def gone(e, d=d, top=top):
            vanished.append(d + "/" + os.path.relpath(getattr(e, "filename", None) or top, top))
        stat(top, d)
        if os.path.isdir(top) and not os.path.islink(top):
            for root, dirs, files in os.walk(top, followlinks=False, onerror=gone):
                for name in dirs + files:
                    p = os.path.join(root, name)
                    stat(p, d + "/" + os.path.relpath(p, top))
    return out


def dump_keychain():
    """`security dump-keychain`'s output, or None when it fails (never taken for an empty Keychain)."""
    try:
        p = subprocess.run(["security", "dump-keychain"], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout if p.returncode == 0 else None


def keychain_items(run=None):
    """The Keychain's items by class, service, account, label and modification date: `security dump-keychain`
    without -d lists attributes only, never a secret. None when the Keychain could not be listed."""
    text = (run or dump_keychain)()
    if text is None:
        return None
    items, cur = [], None
    for line in text.splitlines():
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
    if before.get("keychain") is None or now.get("keychain") is None:
        return lines  # untouched() says the Keychain could not be compared
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


def check_state_folders(base, user_home):
    """Each client's state folder: local, private (700), outside the repository, every checkout, every everyday and
    every synced folder, no link out of it (Codex's own helpers excepted), its login file 600, its config on the route;
    its throwaway home made (mode 700) and checked."""
    C.check_folder("untouched: <client-home>", base, ROOT, user_home)
    C.check_private("untouched: <client-home>", os.path.abspath(base))
    for h in CLIENT_PARTS:
        client = C.CLIENTS[h]("m")
        folder = os.path.join(base, client.client_id)
        if not os.path.isdir(folder):
            raise SystemExit(f"untouched: {folder} does not exist: create the state folders first (mkdir -m 700)")
        C.check_folder(f"untouched: {client.client_id}", folder, ROOT, user_home)
        C.check_private(f"untouched: {client.client_id}", folder)
        out_links = C.links_out(folder, client.allowed_link_for())
        if out_links:
            raise SystemExit(f"untouched: {client.client_id} holds links that leave it: {', '.join(out_links[:5])}")
        for f in C.login_files(folder):
            C.check_private(f"untouched: the login file {client.client_id}/{os.path.relpath(f, folder)}", f, 0o600)
        client.preflight(folder)
        C.prepare_home(f"untouched: {client.client_id}", folder, base, ROOT, user_home)


def untouched(date, mode, user_home=None, lister=None, out=print, at=None, dry=False):
    """`save`: the snapshot, once, before the logins (the state folders and their throwaway homes checked first).
    `report`: what changed since, written to <client-home>/night-<date>/everyday-report-<time>.txt and summarised;
    a report for a person to judge, never a stop. Returns the report's lines (empty: nothing changed)."""
    if dry:
        if mode == "save":
            out(f"untouched --save: would check {', '.join(STATE_FOLDERS)} under <client-home> (local, mode 700, no "
                "link out, login files 600), make their throwaway homes, and record the names, sizes and dates under "
                f"{', '.join(EVERYDAY)} and the Keychain's item names in <client-home>/night-{date}/everyday-before.json."
                " Dry run: nothing checked or written.")
        else:
            out(f"untouched --report: would compare the everyday state with <client-home>/night-{date}/"
                "everyday-before.json and write everyday-report-<time>.txt beside it. Dry run: nothing written.")
        return []
    base = need_client_home("untouched")
    path = everyday_path(date)
    real_user = os.path.realpath(user_home or os.path.expanduser("~"))
    if mode == "save":
        check_state_folders(base, real_user)
        if os.path.exists(path):
            raise SystemExit(f"untouched: a snapshot of {date} exists already; it is taken once, before the logins")
    elif not os.path.exists(path):
        raise SystemExit(f"untouched: no snapshot of {date}: `untouched --save` is step 1, before the logins")
    make_night_dir(date)
    vanished = []
    now = {"files": snapshot_files(user_home, vanished), "keychain": keychain_items(lister)}
    if mode == "save":
        C.write_private(path, json.dumps(now))
        out(f"saved: {len(now['files'])} paths under the everyday folders, "
            + (f"{len(now['keychain'])} Keychain items" if now["keychain"] is not None else
               "and NOT the Keychain's items: `security dump-keychain` failed; the morning report will say it cannot "
               "compare them"))
        return []
    with open(path) as f:
        before = json.load(f)
    changed = compare_everyday(before, now)
    missing = [when for when, side in (("at the snapshot", before), ("now", now)) if side.get("keychain") is None]
    if missing:
        changed.append(f"Keychain not compared: its items could not be listed {' and '.join(missing)} (`security "
                       "dump-keychain` failed): nothing is known of them")
    gone = [f"vanished during the walk: {p}" for p in sorted(set(vanished))]
    report = report_path(date, at)
    C.write_private(report, f"The everyday state against the snapshot of {date}, taken before the logins: for a person "
                    "to judge. The owner's own use of his tools (Claude Code, Codex, Devin, Muse Code, pi) changes "
                    "these folders and items too: a line here is not, by itself, the night's doing.\n"
                    + ("".join(x + "\n" for x in changed) or "nothing changed\n") + "".join(x + "\n" for x in gone))
    if gone:
        out(f"report: {len(gone)} paths were removed while the walk passed them (the owner's tools at work); named in "
            "the report")
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
    out("  (the owner's own use changes these too: a line is not, by itself, the night's doing)")
    return changed


# --- the logins: each client's own command, in its own folders and under its sandbox ---------------------------------

def login(name, date, run=None, dry=False, out=print, user_home=None, status_run=None):
    """`login codex|devin`: the client's login command with exactly the environment every run of the night
    has (its state folder's variables, its throwaway HOME and TMPDIR, the short allow-list) and under sandbox-exec (no
    write under the home folder but its own folders). Only after step 1's snapshot. Success is said only when the
    client's login file is in its state folder (a regular, non-empty file, then set to mode 600) and the client's own
    status command, in the same folders and sandbox, shows the subscription login."""
    if name in NOT_THIS_NIGHT:
        raise SystemExit(f"login {name}: {NOT_THIS_NIGHT[name]} is not in the first night (Codex and Devin only)")
    if name not in LOGINS:
        raise SystemExit(f"login: one of {', '.join(LOGINS)}")
    client = C.CLIENTS[name]("m")
    if dry:
        out(f"login {name}: {' '.join(LOGINS[name])}" + (" under sandbox-exec" if C.CONFINED else "")
            + f", in <client-home>/{client.client_id} with HOME=<client-home>/home/{client.client_id} and "
            f"TMPDIR=<client-home>/tmp/{client.client_id}")
        out("   then: its login file found (non-empty) and set to mode 600, its status command run, the state folder "
            "checked. Dry run: nothing run.")
        return None
    base = need_client_home("login")
    if not os.path.exists(everyday_path(date)):
        raise SystemExit(f"login {name}: no snapshot of {date} (`untouched --save`, step 1): it comes before the logins")
    state = os.path.abspath(os.path.join(base, client.client_id))
    env = client.environment(state)
    user_home = os.path.realpath(user_home or os.path.expanduser("~"))
    C.state_folder(client, base, ROOT, user_home=user_home, env=env, check_login=False)
    argv = C.confine(LOGINS[name], env, [state, env["HOME"], env["TMPDIR"]])
    code = (run or subprocess.run)(argv, env=env, cwd=state).returncode
    if code:
        raise SystemExit(f"login {name}: the client exited {code}: not logged in")
    real = os.path.realpath(state)
    found = client.login_evidence(real)
    if not found:
        where = client.login_file or "credentials.toml or auth.json"
        raise SystemExit(f"login {name}: the client exited 0, but no login file is in <client-home>/{client.client_id} "
                         f"({where}, non-empty): the login is not in the night's folder; not done")
    for f in C.login_files(real):
        if not os.path.islink(f) and os.path.isfile(f):
            os.chmod(f, 0o600)
    C.state_folder(client, base, ROOT, user_home=user_home, env=env, check_login=False)
    why = C.login_status(client, real, env, status_run)
    if why:
        raise SystemExit(f"login {name}: the login file is there, but the client's status refuses: {why}; not done")
    out(f"login {name}: done; its login file <client-home>/{client.client_id}/{os.path.relpath(found, real)} is there, "
        "mode 600, and the client's status shows the subscription login")
    return code


# --- the smoke runs (in the foreground) and their review ----------------------------------------------------------

def read_events(path):
    try:
        with open(path) as f:
            return [json.loads(x) for x in f if x.strip()]
    except (OSError, ValueError):
        return None


BAD_EVENTS = ("check-invalid", "check-failed", "prime-failed", "prime-refused", "retry")
ISOLATION = {"home": "dedicated", "HOME": "throwaway", "work": "temporary"}
# S3b asks whether Devin still reports no cached token for gpt-6-1-terra: a control that reads none is an answer.
COLD_EXPECTED = {"S3b"}


def smoke_verdict(date):
    """(problems, notes) of the smoke results. Each run: a start line with the client's version and the isolation, one
    check (the control), one model request, made in time (not late), no failed or retried request, and a last line
    `done` with the check warm. S3b may instead end `stop`/`no-observable-cache` with its control cold: the expected
    answer to its question, noted. A late control, or a control that did not end the run as above, is a problem."""
    problems, notes = [], []
    folder = os.path.join(ROOT, folders(date)["smoke"])
    for step in PARTS["smoke"]:
        sid = step["id"]
        ev = read_events(os.path.join(folder, sid + ".jsonl"))
        if not ev:
            problems.append(f"{sid}: no results")
            continue
        start, last = ev[0], ev[-1]
        if start.get("event") != "start" or not start.get("client_version"):
            problems.append(f"{sid}: its first line is not a start with the client's version")
        if start.get("isolation") != ISOLATION:
            problems.append(f"{sid}: its start line does not show the isolation")
        bad = sorted({e.get("event") for e in ev if e.get("event") in BAD_EVENTS})
        if bad:
            problems.append(f"{sid}: {', '.join(bad)}")
        if last.get("event") == "stop" and last.get("reason") == "control-late":
            problems.append(f"{sid}: the control could not be checked in time (control-late)")
            continue
        checks = [e for e in ev if e.get("event") == "check"]
        if len(checks) != 1:
            problems.append(f"{sid}: {len(checks)} checks, not the control alone")
            continue
        c = checks[0]
        if c.get("age") != "control" or (c.get("usage") or {}).get("calls") != 1:
            problems.append(f"{sid}: its check is not the control's single model request")
        if c.get("late") is not False:
            problems.append(f"{sid}: the control was checked late ({c.get('realAgeSec')} s after its priming)")
            continue
        if last.get("event") == "done" and c.get("warm") is True:
            continue
        if sid in COLD_EXPECTED and last.get("event") == "stop" and last.get("reason") == "no-observable-cache" \
                and c.get("warm") is False:
            notes.append(f"{sid}: the control was cold (stop/no-observable-cache): the expected answer, noted")
            continue
        problems.append(f"{sid}: ended {last.get('event')}{'/' + str(last.get('reason')) if last.get('reason') else ''}"
                        f" with the control {'warm' if c.get('warm') else 'cold'}")
    return problems, notes


def go_smoke(date, run=None, out=print):
    """The smoke runs, one after the other, in the foreground; then the verdict."""
    run = run or subprocess.run
    need_client_home("--go smoke")
    if not os.path.exists(everyday_path(date)):
        raise SystemExit("--go smoke: no snapshot of the everyday state (`untouched --save`, step 1): nothing started")
    make_night_dir(date)
    for step in PARTS["smoke"]:
        if os.path.exists(os.path.join(ROOT, folder_of(step, date), step["id"] + ".jsonl")):
            out(f"{step['id']}: its results exist already: skipped")
            continue
        argv = command(step, date)
        out(f"== {step['id']}: {shown(argv)}")
        code = run(["caffeinate", "-i", *argv], cwd=ROOT, env=clean_env()).returncode
        if code:
            out(f"{step['id']}: exited {code}")
    problems, notes = smoke_verdict(date)
    for n in notes:
        out(n)
    for p in problems:
        out("problem: " + p)
    out("the smoke results pass the automatic checks: read them (docs/own-clients-RUN.md), then `smoke-reviewed`"
        if not problems else "the smoke results do not pass: hand them to whoever maintains harness/clients.py")
    return problems


def reviewed_path(date):
    return os.path.join(night_dir(date), "smoke-reviewed")


def smoke_reviewed(date, dry=False, out=print):
    """The mark that the smoke results were read: refused while they fail the automatic checks (smoke_verdict)."""
    problems, notes = smoke_verdict(date)
    for n in notes:
        out(n)
    if problems:
        raise SystemExit("smoke-reviewed: refused: " + "; ".join(problems))
    if dry:
        out("smoke-reviewed: the smoke results pass the automatic checks; would write the mark "
            f"<client-home>/night-{date}/smoke-reviewed. Dry run: nothing written.")
        return False
    make_night_dir(date)
    if not os.path.exists(reviewed_path(date)):
        C.write_private(reviewed_path(date), time.strftime("%Y-%m-%dT%H:%M:%SZ\n", time.gmtime()))
    out("the smoke results are marked as read: the clients' runs may start")
    return True


# --- the launcher: each client's runs in the background, one lock per client ---------------------------------------

def lock_path(date, client):
    return os.path.join(night_dir(date), "launch", client + ".json")


def read_lock(date, client):
    try:
        with open(lock_path(date, client)) as f:
            return json.load(f)
    except (FileNotFoundError, NotADirectoryError):
        return None


def refuse_other_clients(what, names):
    other = [NOT_THIS_NIGHT[n] for n in names if n in NOT_THIS_NIGHT]
    if other:
        raise SystemExit(f"{what}: {' and '.join(other)} not in the first night (Codex and Devin only)")


def guard(names, date):
    refuse_other_clients("--go", names)
    if not names or any(n not in CLIENT_PARTS for n in names):
        raise SystemExit(f"--go: smoke, or one of {', '.join(CLIENT_PARTS)}, or all (the two)")
    need_client_home("--go")
    if not os.path.exists(everyday_path(date)):
        raise SystemExit("--go: no snapshot of the everyday state (`untouched --save`, step 1): the morning report "
                         "needs it; nothing started")
    if not os.path.exists(reviewed_path(date)):
        raise SystemExit("--go: the clients' runs wait until the smoke results were checked and read (`smoke-reviewed`)")
    stopped = [n for n in names if os.path.lexists(stop_path(date, n))]
    if stopped:
        raise SystemExit(f"--go: {', '.join(stopped)} stopped for {date} (`stop`): nothing more starts that night")
    taken = [n for n in names if os.path.lexists(lock_path(date, n))]
    if taken:
        raise SystemExit(f"--go: {', '.join(taken)} launched already for {date} (`status`, `stop`); a second start is "
                         f"refused (its lock: <client-home>/night-{date}/launch/)")


def write_lock(date, name, lock):
    tmp = lock_path(date, name) + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(lock, f)
    os.replace(tmp, lock_path(date, name))


def private_log(path):
    """A console log, mode 600 (appended to; made 600 if it existed), never through a link."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
    os.fchmod(fd, 0o600)
    return os.fdopen(fd, "a")


def stop_path(date, client):
    return os.path.join(night_dir(date), "launch", client + ".stop")


def launch(name, date, popen=None, out=print, killpg=None):
    """One client's runs, each its own background process. The lock file is created exclusively, with the launcher's
    own pid, before the first run starts, and rewritten with each run's pid as soon as that run is started. The
    client's stop mark is looked for before each start, and again right after it (the run's pid recorded): a stop
    written while a run was being started stops that run (its process group signalled) and the launch ends there."""
    popen, killpg = popen or subprocess.Popen, killpg or os.killpg
    d = make_night_dir(date)
    launch_dir = os.path.join(d, "launch")
    if not os.path.isdir(launch_dir):
        os.mkdir(launch_dir, 0o700)
    C.check_private("<client-home>/night-<date>/launch", launch_dir)
    launch_id = f"{date}-{name}-{uuid.uuid4().hex[:12]}"
    try:
        fd = os.open(lock_path(date, name), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError:
        raise SystemExit(f"--go {name}: launched already for {date}: a second start is refused") from None
    lock = {"client": name, "date": date, "launch_id": launch_id, "launcher_pid": os.getpid(),
            "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "runs": {}}
    with os.fdopen(fd, "w") as f:
        json.dump(lock, f)
    logs = os.path.join(ROOT, folders(date)["own"], "logs")
    os.makedirs(logs, exist_ok=True)
    for i, step in enumerate(PARTS[name]):
        if os.path.lexists(stop_path(date, name)):
            raise SystemExit(f"--go {name}: stopped (`stop`) after {len(lock['runs'])} of {len(PARTS[name])} runs: "
                             "nothing more starts")
        delay = delay_of(step, i)
        argv = command(step, date, launch_id=launch_id, delay=delay)
        with private_log(os.path.join(logs, step["id"] + ".log")) as log:
            p = popen(["caffeinate", "-i", *argv], cwd=ROOT, env=clean_env(), stdout=log,
                      stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        lock["runs"][step["id"]] = {"pid": p.pid, "delay_s": delay}
        write_lock(date, name, lock)  # at once: an interrupted launch leaves every started run recorded
        if os.path.lexists(stop_path(date, name)):
            # `stop` came while this run was being started: the run just started is stopped too, and nothing more.
            try:
                killpg(p.pid, signal.SIGTERM)  # its own session: its process group is its pid
            except ProcessLookupError:
                pass
            raise SystemExit(f"--go {name}: stopped (`stop`) while starting {step['id']}: it was signalled at once; "
                             f"{len(lock['runs']) - 1} of {len(PARTS[name])} runs had started before it")
        out(f"{step['id']} pid {p.pid}, begins {delay} s after the go ({step['model']})")
    return lock


def go_clients(names, date, popen=None, out=print, killpg=None):
    names = list(CLIENT_PARTS) if names == ["all"] else names
    guard(names, date)
    locks = [launch(n, date, popen=popen, out=out, killpg=killpg) for n in names]
    out(f"started: {', '.join(names)}; the terminal may be closed. `python3 harness/night.py --date {date} status` "
        "shows which runs are alive.")
    return locks


def process_command(pid):
    """The command line of a process ('' when there is none)."""
    p = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else ""


def process_table():
    """(pid, process group, command line) of every process."""
    p = subprocess.run(["ps", "-ax", "-o", "pid=,pgid=,command="], capture_output=True, text=True)
    rows = []
    for line in p.stdout.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            rows.append((int(parts[0]), int(parts[1]), parts[2]))
    return rows


def alive(run_id, info, launch_id, ps=None):
    """The run's process is alive and is that run: its command line carries `--label <id>` and this launch's id."""
    pid = info.get("pid")
    if not isinstance(pid, int) or pid <= 1:
        return False
    seen = " " + (ps or process_command)(pid) + " "
    return f" --label {run_id} " in seen and f" --launch-id {launch_id} " in seen


def launch_mark(date, name, lock=None):
    """What every worker of this night and client carries on its command line: the night's launch-id prefix for the
    client (`--launch-id <date>-<client>-`), whatever the lock says or whether there is one yet (a launch id is
    `<date>-<client>-<12 hex>`, and there is one launch per client and night)."""
    return f" --launch-id {date}-{name}-"


def workers(date, name, lock, table=None):
    """{process group: run label} of every process whose command line carries this night's launch id for the client:
    the workers of an interrupted launch, or of a launch whose lock was not there yet, included."""
    mark, found = launch_mark(date, name, lock), {}
    for pid, pgid, cmd in (table or process_table)():
        seen = " " + cmd + " "
        if mark in seen and pgid > 1 and pid != os.getpid():
            label = seen.split(" --label ", 1)[1].split()[0] if " --label " in seen else "?"
            found.setdefault(pgid, label)
    return found


def read_lock_any(date, name):
    """The lock (a dict), {} when it exists but cannot be read (an interrupted launch), None when there is none."""
    path = lock_path(date, name)
    if not os.path.lexists(path):
        return None
    try:
        return read_lock(date, name) or {}
    except ValueError:
        return {}


def status(date, ps=None, out=print, table=None):
    """Which runs are alive, by their processes (never by their progress files); a worker carrying the launch's id but
    missing from the lock (an interrupted launch) is listed too."""
    counts = {}
    for name in CLIENT_PARTS:
        lock = read_lock_any(date, name)
        if lock is None:
            out(f"{name}: not launched")
            continue
        out(f"{name}: launched {lock.get('started', '(its lock is incomplete: an interrupted launch)')}")
        recorded = set()
        for rid, info in lock.get("runs", {}).items():
            st = "alive" if lock.get("launch_id") and alive(rid, info, lock["launch_id"], ps) else "ended"
            counts[st] = counts.get(st, 0) + 1
            recorded.add(info.get("pid"))
            out(f"  {rid:6} {st}  pid {info.get('pid')}")
        for pgid, label in workers(date, name, lock, table).items():
            if pgid not in recorded:
                counts["alive, not in the lock"] = counts.get("alive, not in the lock", 0) + 1
                out(f"  {label:6} alive, not in the lock (an interrupted launch)  process group {pgid}")
    out(", ".join(f"{v} {k}" for k, v in counts.items()) or "nothing launched")
    out("Liveness only: how each run ended is in its results file.")
    return counts


def launcher_alive(pid, date, ps=None):
    """The launcher of this night is still running in process `pid` (never this very process): its command line is
    harness/night.py's, with this night's date and --go."""
    if not isinstance(pid, int) or pid <= 1 or pid == os.getpid():
        return False
    seen = " " + (ps or process_command)(pid) + " "
    return "night.py" in seen and f" --date {date} " in seen and " --go " in seen


def parent_table():
    """(pid, parent pid, command line) of every process."""
    p = subprocess.run(["ps", "-ax", "-o", "pid=,ppid=,command="], capture_output=True, text=True)
    rows = []
    for line in p.stdout.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            rows.append((int(parts[0]), int(parts[1]), parts[2]))
    return rows


def launchers(date, table=None):
    """The pids of every launcher of this night that may be running: a process whose command line names
    harness/night.py, carries --go (or its abbreviation --g) and this night's date, in any form. Never this process nor
    one of its ancestors (the shell that runs `stop`)."""
    rows = (table or parent_table)()
    parent = {pid: ppid for pid, ppid, _ in rows}
    mine, p = {os.getpid()}, os.getpid()
    while p in parent and parent[p] not in mine and parent[p] > 1:
        p = parent[p]
        mine.add(p)
    mine.add(os.getppid())
    found = []
    for pid, _, cmd in rows:
        words = cmd.split()
        if pid in mine or pid <= 1:
            continue
        if any(w.endswith("night.py") for w in words) and any(w in ("--go", "--g") for w in words) and date in cmd:
            found.append(pid)
    return sorted(found)


def stop(target, date, ps=None, killpg=None, kill=None, out=print, dry=False, table=None, wait=10.0, sleep=None,
         launcher_table=None):
    """Stops the named client(s) for this night, in this order:
      1. the stop mark of every named client, before anything is looked up: a launcher that has not yet started a run
         starts none, and one that is starting a run stops it as soon as it is started (launch);
      2. a wait until every launcher of this night has ended (each ends by itself once it sees the mark), at most
         `wait` seconds; one still running then is signalled (SIGTERM) and waited for again;
      3. the process group of every run of the client that is alive: those the lock records (pid and command line
         checked), and every process carrying this night's launch id for the client on its command line, whether or
         not a lock was there when `stop` began; looked for twice, a moment apart, so that a run whose process was
         still starting is found too. A group that ended meanwhile is passed over; the others are still signalled.
    Without GROUNDTRUTH_CLIENT_HOME it refuses (the mark cannot be written): set it as for the night."""
    refuse_other_clients("stop", [target])
    names = list(CLIENT_PARTS) if target == "all" else [target]
    if any(n not in CLIENT_PARTS for n in names):
        raise SystemExit(f"stop: one of {', '.join(CLIENT_PARTS)}, or all")
    killpg, kill, sleep = killpg or os.killpg, kill or os.kill, sleep or time.sleep
    if dry:
        for name in names:
            out(f"{name}: would write its stop mark <client-home>/night-{date}/launch/{name}.stop, wait for this "
                "night's launcher to end, then signal its runs. Dry run: nothing written.")
            for pgid, rid in sorted(groups_of(date, name, ps, table).items()):
                out(f"{rid}: would signal process group {pgid}. Dry run: nothing sent.")
        return []
    # 1. The marks, first.
    # Made when missing (mode 700), never refused over a folder's mode: a stop always gets its mark written.
    need_client_home("stop")
    os.makedirs(os.path.join(night_dir(date), "launch"), mode=0o700, exist_ok=True)
    for name in names:
        if not os.path.lexists(stop_path(date, name)):
            C.write_private(stop_path(date, name), time.strftime("%Y-%m-%dT%H:%M:%SZ\n", time.gmtime()))
        out(f"{name}: stop mark written: nothing more of it starts this night")
    # 2. The launchers: they end by themselves on the mark; one that does not is signalled.
    def wait_launchers():
        waited = 0.0
        while waited < wait:
            if not launchers(date, launcher_table):
                return []
            sleep(0.1)
            waited += 0.1
        return launchers(date, launcher_table)
    left = wait_launchers()
    if left:
        for pid in left:
            try:
                kill(pid, signal.SIGTERM)
                out(f"a launcher of this night (pid {pid}) still ran after {wait:g} s: signalled")
            except ProcessLookupError:
                pass
        left = wait_launchers()
        for pid in left:
            out(f"a launcher of this night (pid {pid}) still runs: run `stop` again, then `status`")
    # 3. The runs, by the lock and by the launch id on the process table; looked for again a moment later.
    signalled, tried = [], set()
    for attempt in range(2):
        if attempt:
            sleep(0.3)
        for name in names:
            for pgid, rid in groups_of(date, name, ps, table).items():
                if pgid in tried:
                    continue
                tried.add(pgid)
                try:
                    killpg(pgid, signal.SIGTERM)
                except ProcessLookupError:
                    out(f"{rid}: process group {pgid} had ended")
                    continue
                signalled.append(pgid)
                out(f"{rid}: process group {pgid} stopped")
    if not signalled:
        out("no run alive: nothing signalled" + ("" if not left else " (but a launcher still runs: see above)"))
    return signalled


def groups_of(date, name, ps=None, table=None):
    """{process group: run id} of the client's runs that are alive: those the lock records (pid alive and its command
    line that run's, of this launch), and every process carrying this night's launch id for the client."""
    groups = {}
    lock = read_lock_any(date, name)
    if lock:
        for rid, info in lock.get("runs", {}).items():
            if lock.get("launch_id") and alive(rid, info, lock["launch_id"], ps):
                groups[info["pid"]] = rid
    for pgid, label in workers(date, name, lock, table).items():
        groups.setdefault(pgid, label)
    return groups


def dry_run_go(names, date, out=print):
    names = list(CLIENT_PARTS) if names == ["all"] else names
    out(f"`--go {' '.join(names)}`: checks (step 1's snapshot, the smoke results marked, no launch yet and no stop "
        f"mark of the client(s) for this night), then creates <client-home>/night-{date}/launch/<client>.json "
        "exclusively with the launcher's pid, starts each run as its own background process (caffeinate -i, a session "
        "of its own), looking for the stop mark before each start, and returns:")
    for n in names:
        out(f"  {n}: " + ", ".join(f"{s['id']} (+{delay_of(s, i)} s)" for i, s in enumerate(PARTS[n])))
    for n in names:
        dry_run(PARTS[n], date, out=out)
    total = sum(len(PARTS[n]) for n in names)
    out(f"Dry run of `--go {' '.join(names)}`: {total} runs; nothing run, nothing sent, nothing written.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="The first night of docs/own-clients.md: the own clients' cache runs")
    ap.add_argument("--date", required=True, help="the night's date, YYYY-MM-DD: names the results folders")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="say what the command would do; do nothing")
    mode.add_argument("--go", action="store_true", help="run them")
    ap.add_argument("what", nargs="+", help="smoke | codex | devin | all; or: untouched, login codex|devin, "
                                             "smoke-reviewed, status, stop codex|devin|all")
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)
    head, dry = a.what[0], a.dry_run
    if head == "status":
        status(a.date)  # reads only
        return
    if head == "untouched":
        m = "save" if a.save else "report" if a.report else None
        if not m:
            raise SystemExit("untouched: --save (step 1, before the logins) or --report (any time after)")
        untouched(a.date, m, dry=dry)
        return
    if head == "login":
        if len(a.what) < 2:
            raise SystemExit("login codex|devin")
        login(a.what[1], a.date, dry=dry)
        return
    if head == "smoke-reviewed":
        smoke_reviewed(a.date, dry=dry)
        return
    if head == "stop":
        if len(a.what) < 2:
            raise SystemExit("stop <client>, or stop all")
        stop(a.what[1], a.date, dry=dry)
        return
    if a.what == ["smoke"]:
        if dry:
            dry_run(PARTS["smoke"], a.date)
            print(f"Dry run of the smoke runs: {len(PARTS['smoke'])} runs, in the foreground; nothing run, nothing sent.")
        elif a.go:
            go_smoke(a.date)
        else:
            for s in PARTS["smoke"]:
                print(f"{s['id']}: {shown(command(s, a.date))}")
        return
    names = a.what
    refuse_other_clients("--go" if a.go else "night.py", names)
    if dry:
        if names == ["all"] or all(n in CLIENT_PARTS for n in names):
            dry_run_go(names, a.date)
        else:
            steps = select(names)
            dry_run(steps, a.date)
            print(f"Dry run of {len(steps)} runs: nothing run, nothing sent.")
    elif a.go:
        go_clients(names, a.date)
    else:
        for s in select(names):
            print(f"{s['id']}: {shown(command(s, a.date))}")
        print("Listed only: --dry-run runs each run's dry run, --go starts them.")


if __name__ == "__main__":
    main()
