#!/usr/bin/env python3
"""Check a results folder for credentials before it is committed. Exits 1 when anything is found.

    python3 harness/scan_secrets.py results/<run folder> && git add results/<run folder>

It collects every secret-looking value this machine uses for the measurements (the client's key file, the
management key file, key and token fields of the CLIProxyAPI config, every string in the login files, and the value
of CACHE_PROBE_KEY when it is set: a contributor's own key) and looks for them in the folder, plus the usual token
shapes, any e-mail address but office@providers.dev, home folder paths, pi session files
(a session file stores pi's whole system prompt, with the names and paths of the owner's skills; they stay local), and
an own client's state folder and session files (Claude Code, Codex CLI, Devin CLI, Muse Code: harness/clients.py; a
state folder holds the client's login, every one of its sessions and its settings). Values are never printed: a
finding names the file and the field the value came from, so it can be judged.

Model names are not secrets: model lists and the names in a login's `model_aliases` are skipped, because a run that
measured `devin/some-model` necessarily contains that name.

A `logs` folder is mostly local (a run's console output, never committed), but a campaign may force-add its usage
logs. So in a `logs` folder the files git tracks are scanned (staged ones included) and the others skipped; in a
folder that is not in a git work tree (the tree the pre-commit hook and CI export from the index, where every file is
about to be published) every file of it is scanned.
"""
import glob
import json
import os
import re
import subprocess
import sys

HOME = os.path.expanduser("~")
CLIENT_KEYS = os.environ.get("SCAN_CLIENT_KEYS", HOME + "/.pi/agent/cliproxyapi.json")
KEYS_FILE = os.environ.get("SCAN_KEYS_FILE", HOME + "/.cli-proxy-api/keys.txt")
CONFIG = os.environ.get("SCAN_CONFIG", "/opt/homebrew/etc/cliproxyapi.conf")
LOGINS = os.environ.get("SCAN_LOGINS", HOME + "/.cli-proxy-api/*.json")
# Anchored on the left, so "sk-" or "eyJ" in the middle of a long base64 blob (encrypted reasoning in session
# files) doesn't count.
TOKEN_SHAPES = re.compile(r"(?<![A-Za-z0-9_+/=-])(sk-[A-Za-z0-9_-]{20,}|Bearer [A-Za-z0-9._-]{20,}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,})")
HOME_PATH = re.compile(r"/(Users|home)/[A-Za-z0-9._-]+/")  # a personal folder path names the account and the folder layout
# Any e-mail address, except the project's own public one.
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PUBLIC_EMAILS = {"office@providers.dev"}
# A contributor's own key, read from the environment variable the probe reads it from (never printed).
KEY_ENVS = ("CACHE_PROBE_KEY", "META_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")
# An own client's state folder (<client-home>/<client id>, harness/clients.py) or the probe's temporary folders.
STATE_FOLDERS = {"claude-code", "codex-cli", "devin-cli", "muse-code", "antigravity-cli"}
# A client's own files: its login and its session records.
CLIENT_FILES = {".claude.json": "Claude Code's settings file", ".credentials.json": "a client's login file",
                "auth.json": "a client's login file (Codex CLI, Muse Code)", "history.jsonl": "a client's history"}
CLIENT_FILE_SHAPES = [
    (re.compile(r"^rollout-.*\.jsonl$"), "a Codex CLI session file"),
    (re.compile(r"^export-[0-9a-f]+\.json$"), "a Devin CLI export"),
]
CLIENT_CONTENT = [
    (re.compile(r'"schema_version"\s*:\s*"ATIF'), "a session export (ATIF: the whole conversation)"),
    (re.compile(r'"parentUuid"\s*:.*"sessionId"\s*:|"sessionId"\s*:.*"parentUuid"\s*:'), "a Claude Code session file"),
    (re.compile(r'"type"\s*:\s*"session_meta"'), "a Codex CLI session file"),
]


def client_findings(path, text):
    """Why a file is an own client's state or session file, or []."""
    parts = path.split(os.sep)
    found = []
    folders = sorted(STATE_FOLDERS.intersection(parts[:-1]))
    if folders:
        found.append(f"inside a client's state folder ({folders[0]}): never committed")
    if any(p.startswith("groundtruth-") for p in parts[:-1]):
        found.append("inside a probe's temporary folder")
    name = parts[-1]
    if name in CLIENT_FILES:
        found.append(CLIENT_FILES[name])
    for shape, what in CLIENT_FILE_SHAPES:
        if shape.match(name):
            found.append(what)
    for shape, what in CLIENT_CONTENT:
        if shape.search(text):
            found.append(what)
    return found


def collect():
    """value -> where it was found (a file kind and a field path, never the value)."""
    secrets = {}
    where = [""]

    def add(value, path=""):
        if isinstance(value, str) and len(value) >= 16 and " " not in value and not value.startswith(("http", "/", "~")) \
                and not value.endswith(".json") and not re.fullmatch(r"[\w.+-]+@[\w.-]+", value) \
                and not re.fullmatch(r"\d{4}-\d\d-\d\dT[\d:.+Z-]+", value):
            secrets.setdefault(value, where[0] + path)

    def walk(node, path=""):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for value in node:
                walk(value, path + "[]")
        elif not re.search(r"model_aliases\[\]\.(name|alias)$|excluded_models\[\]$|(^|\.)models?(\[\])?(\.(id|name|alias|slug))?$|model_ids\[\]$", path):
            add(node, path)

    if os.path.exists(CLIENT_KEYS):
        where[0] = "client key file"
        walk(json.load(open(CLIENT_KEYS)))
    if os.path.exists(KEYS_FILE):
        where[0] = "management key file"
        for line in open(KEYS_FILE):
            if "=" in line:
                add(line.split("=", 1)[1].strip(), " " + line.split("=", 1)[0].strip())
    if os.path.exists(CONFIG):
        # key, token, secret and password fields, without needing a YAML parser
        where[0] = "config"
        for m in re.finditer(r"^\s*-?\s*([\w-]*(?:key|token|secret|password)[\w-]*):\s*[\"']?([^\"'\s#]+)", open(CONFIG).read(), re.I | re.M):
            add(m.group(2), " " + m.group(1))
    for name in KEY_ENVS:
        where[0] = f"environment variable {name}"
        add(os.environ.get(name))
    for path in glob.glob(LOGINS):
        try:
            where[0] = "login file (" + os.path.basename(path).split("-")[0] + ")"
            walk(json.load(open(path)))
        except (ValueError, OSError):
            pass
    return secrets


def tracked(folder):
    """The files under `folder` that git tracks (relative paths), or None when `folder` is in no git work tree."""
    # Without the GIT_* variables a hook runs with (GIT_DIR, GIT_INDEX_FILE…): they would answer for the repository
    # being committed to, not for the folder (the hook scans an exported tree outside it).
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

    def git(*args):
        return subprocess.run(["git", "-C", folder, *args], capture_output=True, text=True, env=env)
    if git("rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
        return None
    out = git("ls-files", "-z", "--", ".")
    if out.returncode:
        sys.exit(f"{folder}: git ls-files failed: {out.stderr.strip()}")
    return {os.path.normpath(p) for p in out.stdout.split("\0") if p}


def files_in(target):
    """Every file to scan under `target`: `logs` folders only for what git tracks (or all of it outside git)."""
    if os.path.isfile(target):
        # a single file is scanned too (os.walk yields nothing for one, which would pass it unread)
        yield target
        return
    for root, dirs, names in os.walk(target):
        logs = [d for d in dirs if d == "logs"]
        dirs[:] = [d for d in dirs if d not in ("logs", ".git", "node_modules") and not d.startswith("work-")]  # never committed
        for name in names:
            yield os.path.join(root, name)
        for d in logs:
            folder = os.path.join(root, d)
            keep = tracked(folder)
            for sub, subdirs, subnames in os.walk(folder):
                subdirs[:] = [s for s in subdirs if s not in (".git", "node_modules")]
                for name in subnames:
                    path = os.path.join(sub, name)
                    if keep is None or os.path.normpath(os.path.relpath(path, folder)) in keep:
                        yield path


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    secrets = collect()
    hits = files = 0
    for target in sys.argv[1:]:
        if not os.path.exists(target):
            sys.exit(f"{target}: no such file or folder")
        for path in files_in(target):
            files += 1
            text = open(path, errors="ignore").read()
            found = []
            origins = sorted({origin for value, origin in secrets.items() if value in text})
            if origins:
                found.append("a value from " + "; ".join(origins[:4]))
            if TOKEN_SHAPES.search(text):
                found.append("something shaped like a token")
            if any(m.group(0).lower() not in PUBLIC_EMAILS for m in EMAIL.finditer(text)):
                found.append("an e-mail address")
            if HOME_PATH.search(text):
                found.append("a home folder path")
            if "pi-sessions" in path.split(os.sep):
                found.append("a pi session file (holds the whole system prompt: skill names, folder paths)")
            found += client_findings(os.path.relpath(path, target) if os.path.isdir(target) else os.path.basename(path), text)
            if found:
                hits += 1
                print(f"{path}: {', '.join(found)}")
    if not files:
        sys.exit("nothing was scanned")
    print(f"{files} files scanned against {len(secrets)} credentials: {'CLEAN' if not hits else str(hits) + ' file(s) with findings'}")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
