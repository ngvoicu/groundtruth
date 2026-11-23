#!/usr/bin/env python3
"""The model ids a client knows, read without sending a prompt, and the night's check of its run table against them
(docs/own-clients.md, "Model ids"). On 2026-11-23 DV12 asked Devin for `deepseek-v4-pro-low`, an id Devin does not
have ("Unknown model"), three times, and nothing had checked it before the go.

- Codex CLI: `codex debug models --bundled` prints the catalog shipped with the binary, offline (no login, no
  refresh). `--go` runs it in a throwaway CODEX_HOME and HOME, under sandbox-exec with the network denied: nothing is
  sent, nothing of the owner's is read or written.
- Devin CLI: `devin models list --format json` lists "the models available to your account": it needs the login and
  asks Devin's server (no prompt, no model request, no session). `--go` runs it in the client's state folder and
  sandbox, as every run of the night is run.
- `--dry-run` runs no client at all: it reads the checked list in the repository (harness/model-ids.json), and so
  does `--go` when a client's own list cannot be read (it says so).

harness/model-ids.json is the checked list: each id with how it was checked.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKED = os.path.join(HERE, "model-ids.json")
ID = re.compile(r"[a-z0-9][a-z0-9._-]{1,80}")
LEVELS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")


class ListError(Exception):
    pass


def checked(client, path=CHECKED):
    """The ids of the checked list of `client` (a set)."""
    with open(path) as f:
        return set(json.load(f)[client]["ids"])


def ids_in(data):
    """Every model id a client's JSON list names: each id-shaped string, and each id-shaped string followed by a
    reasoning level named in the same object (a list that gives a model's levels apart from its id)."""
    found = set()

    def strings(x):
        if isinstance(x, str):
            return [x]
        if isinstance(x, list):
            return [s for v in x for s in strings(v)]
        return []

    def walk(x):
        if isinstance(x, dict):
            own = [s for v in x.values() for s in strings(v)]
            levels = [s for s in own if s in LEVELS]
            for s in own:
                if ID.fullmatch(s):
                    found.add(s)
                    found.update(f"{s}-{lv}" for lv in levels)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                if isinstance(v, str) and ID.fullmatch(v):
                    found.add(v)
                walk(v)
    walk(data)
    return found


def no_network(argv, writable):
    """`argv` under sandbox-exec: no network at all, and no file write under the home folder but in `writable` (macOS,
    clients.sandbox_profile); as it is elsewhere."""
    import clients as C
    if not C.CONFINED:
        return list(argv)
    return [C.SANDBOX_EXEC, "-p", C.sandbox_profile(writable) + "(deny network*)", *argv]


def codex_listed(run=None):
    """The slugs of Codex's bundled catalog (`codex debug models --bundled`), offline: a throwaway CODEX_HOME and HOME,
    network denied. ListError when it cannot be read."""
    if not shutil.which("codex"):
        raise ListError("the codex command is not on PATH")
    tmp = tempfile.mkdtemp(prefix="groundtruth-models-")
    try:
        env = {"PATH": os.environ.get("PATH", ""), "HOME": tmp, "CODEX_HOME": os.path.join(tmp, "codex"),
               "TMPDIR": tmp}
        os.makedirs(env["CODEX_HOME"])
        argv = no_network(["codex", "debug", "models", "--bundled"], [tmp])
        try:
            p = (run or subprocess.run)(argv, env=env, cwd=tmp, capture_output=True, text=True, timeout=60,
                                        stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ListError(f"codex debug models --bundled could not be run ({type(e).__name__})") from None
        if p.returncode:
            raise ListError(f"codex debug models --bundled exited {p.returncode}")
        try:
            models = json.loads(p.stdout)["models"]
            slugs = {m["slug"] for m in models if isinstance(m, dict) and isinstance(m.get("slug"), str)}
        except (ValueError, KeyError, TypeError):
            raise ListError("codex debug models --bundled printed no catalog") from None
        if not slugs:
            raise ListError("codex debug models --bundled listed no model")
        return slugs
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def devin_listed(client_home, run=None):
    """The ids Devin lists for the account (`devin models list --format json`), in the client's state folder, its
    throwaway HOME and its sandbox, after the same checks as a run's (clients.state_folder): no prompt is sent.
    ListError when it cannot be read."""
    import clients as C
    client = C.CLIENTS["devin"]("m")
    root = os.path.dirname(HERE)
    try:
        state = C.state_folder(client, client_home, root, check_login=False)
    except SystemExit as e:
        raise ListError(f"the Devin state folder: {e}") from None
    if not client.login_evidence(state):
        raise ListError("no Devin login in its state folder")  # never the client without its login: nothing to list
    env = client.environment(state)
    argv = C.confine(["devin", "--process-model", "in-process", "models", "list", "--format", "json"], env,
                     [state, env["HOME"], env["TMPDIR"]])
    try:
        code, out, err = (run or C._run)(argv, env=env, cwd=None, stdin=None, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ListError(f"devin models list could not be run ({type(e).__name__})") from None
    if code:
        raise ListError(f"devin models list exited {code}")
    try:
        found = ids_in(json.loads(out))
    except ValueError:
        raise ListError("devin models list printed no JSON") from None
    if not found:
        raise ListError("devin models list named no model")
    return found


def known_ids(client, live=False, client_home=None, lister=None):
    """(ids, where they come from, whether that is the client's own list) for `client`. A dry run (`live` False) runs
    no client: the checked list. --go (`live`): Codex its bundled catalog (offline), Devin the account's list (no
    prompt); the checked list when that cannot be read. `lister(client)` replaces the client's own listing (tests)."""
    if lister:
        return lister(client), f"{client}: its own list", True
    if not live or os.environ.get("GROUNDTRUTH_MODEL_LIST") == "checked":
        return checked(client), "harness/model-ids.json, the checked list (--go reads the client's own)", False
    try:
        if client == "codex":
            return codex_listed(), "codex debug models --bundled (offline)", True
        if client == "devin":
            return devin_listed(client_home), "devin models list (the account's list; no prompt)", True
    except ListError as e:
        return checked(client), f"harness/model-ids.json, the checked list: the client's own could not be read ({e})", \
            False
    return checked(client), "harness/model-ids.json, the checked list", False


def unknown(steps, live=False, client_home=None, lister=None):
    """([`id (model)` of each step whose model id its client does not list], {client: where its list came from})."""
    bad, lists = [], {}
    for s in steps:
        c = s["harness"]
        if c not in lists:
            lists[c] = known_ids(c, live, client_home, lister)
        if s["model"] not in lists[c][0]:
            bad.append(f"{s['id']} ({s['model']})")
    return bad, {c: (src, own) for c, (_, src, own) in lists.items()}
