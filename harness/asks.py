#!/usr/bin/env python3
"""Asking the owner (Provimux's design `model-lists.md`, section 9.5; docs/weekly-night.md, "When the night asks").

Each case stops its own part only; the rest of the night goes on. An ask is:
- at once, a macOS notification with its first line;
- in full, `$G/asks/open/<id>.md` (what happened, the exact command, what was not done), with `<id>.json` beside it;
- until it is solved, at the top of the night's report and of every later report.

The check that failed closes it when it passes again (`passed`): nobody closes an ask by hand. A closed ask moves to
`$G/asks/closed/`. Asks hold model ids, routes, counts, dollars and commands only: they go into the public report,
so never a client's or a vendor's text, a path under the home folder, an account or a key. Commands name the night's
folder as `$G` (GROUNDTRUTH_CLIENT_HOME).

    python3 harness/asks.py                    # the open asks, as the report shows them
"""
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NIGHT = "python3 harness/weekly.py"
GITHUB_URL = "https://github.com/ngvoicu/groundtruth.git"
G_NOTE = "From the repository's root, with `export GROUNDTRUTH_CLIENT_HOME=$G` set as for the night."


def _money(x):
    return f"${x:.2f}" if isinstance(x, (int, float)) else "?"


# kind -> (what it stops, a function of the facts giving (first line, what happened, command, what was not done)).
def _login_expired(f):
    return (f"Log in again to {f['part']}: its login in the night's folder is not accepted",
            f"The client's own status command refused the {f['part']} login ({f.get('when', 'before the runs')}).",
            f"python3 harness/night.py --date {f['date']} login {f['part']}   # 2 minutes, a browser opens",
            f"No run of {f['part']} started after the refusal; its planned runs are first next Monday.")


def _key_refused(f):
    return (f"The {f['route']} key was refused ({f.get('status', 'no key')})",
            f"The free request that checks the {f['route']} key answered {f.get('status', 'nothing: no key in the file')}"
            f" ({f.get('when', 'before the runs')}). The key is `{f['variable']}` in `$G/keys.env` (mode 600).",
            f"{NIGHT} --go check keys   # sends the free request again for every key",
            f"No run on {f['route']} started after the refusal.")


def _plan_limit(f):
    return (f"{f['part']}: the plan's limit was reached after {f['ran']} of {f['planned']} runs",
            f"A run of {f['part']} was refused for quota; the part stopped there ({f['ran']} of the {f['planned']} "
            "planned runs had started). The runs left are first next Monday.",
            f"{NIGHT} --date <today> --go night --only {f['part']}   # runs them sooner, once the plan's meter is low",
            f"{f['planned'] - f['ran']} planned runs of {f['part']} did not start.")


def _provider_billing(f):
    return (f"{f['route']} refused for billing ({f['status']}): the account needs credit or a higher limit",
            f"The provider answered {f['status']} on {f['route']}: payment required (no credit left, or a spending "
            "limit set on the account). The route stopped; its runs still alive got their stop mark. This is the "
            "provider's own limit, not one of ours: the night has no cap on money.",
            f"{NIGHT} --date <today> --go night --only keys   # after the account has credit again",
            f"No further run on {f['route']} started that night; its values are planned again next Monday.")


def _vendor_refuses(f):
    return (f"{f['route']} refused twice in a row ({f['refusal']}): the account needs a look",
            f"Two runs in a row on {f['route']} ended refused ({f['refusal']}): neither quota nor login. The route's "
            "part stopped.",
            f"{NIGHT} --date <today> --go night --only {f['part']}   # after a look at the account",
            f"No further run on {f['route']} started that night.")


def _window_answered(f):
    return (f"A window request on {f['route']} was answered instead of refused ({f['model']}, about "
            f"{_money(f['usd'])})",
            f"The window request for {f['model']} on {f['route']} was answered and billed for about {f['words']:,} "
            f"tokens ({_money(f['usd'])}). The window list ended there.",
            f"{NIGHT} check windows   # after a look: the next night's window requests close this ask",
            "The rest of the window list was not sent that night.")


def _discovery_stale(f):
    return (f"Discovery has no fresh list for {f['provider']}: {f['days']} days old",
            f"The list of {f['provider']} in listed.json is {f['days']} days old (more than 3).",
            "Look at the login's line on Provimux's status page; then `python3 harness/discover.py`",
            "Nothing stopped: the plan used the last list.")


def _not_started(f):
    return (f"The night of {f['date']} did not start: {f['reason']}",
            f"The night of {f['date']} did not start: {f['reason']}." + (f" The Mac woke at {f['woke']}."
                                                                          if f.get("woke") else ""),
            f"{NIGHT} --date <today> --go night   # the week's night, by hand, now (with the night's own date it "
            "would be refused as too late after 03:00 on the Tuesday; a second start of one date is refused)",
            "Nothing of that night was measured.")


def _checkout_not_ready(f):
    problems = f["problems"]
    return (f"The night of {f['date']} did not start: the checkout is not ready ({problems[0]})",
            "The night runs from the groundtruth checkout, on `main`, with no change to a tracked file, and holding no "
            f"commit GitHub's `main` lacks (it may be behind: it then updates itself). Found: {'; '.join(problems)}. "
            "Untracked and ignored files never count.",
            " && ".join(list(f["fixes"]) + [f"{NIGHT} --date <today> --go night"]) + "   # then the week's night, "
            "by hand, now",
            "Nothing of that night was measured; nothing was sent to any provider.")


def _checkout_not_updated(f):
    return (f"The checkout could not update itself to GitHub's main ({f['behind']} commits behind)",
            f"The night fast-forwards the checkout to GitHub's `main` before it starts; that was refused ({f['why']}), "
            f"and the checkout was left as it was. The night ran from {f['head']}, {f['behind']} commits behind "
            f"GitHub's {f['github']}.",
            f"git pull --ff-only {GITHUB_URL} main   # says what is in the way",
            "The night ran without GitHub's newest commits.")


def _unsteady(f):
    return (f"{f['route']} {f['model']} ({f['quantity']}): three measurements, no two agree",
            f"Our measurements of {f['quantity']} for {f['model']} on {f['route']} are "
            f"{', '.join(str(v) for v in f['values'])}: no two agree. The value is unsteady; no further run.",
            "No command: a decision on how to measure it (for the maintainer, with the chief)",
            "The value is not measured again.")


def _smoke_failed(f):
    return (f"{f['part']}: the smoke run failed its automatic checks",
            f"The smoke run of {f['part']} failed: {'; '.join(f['problems'])}.",
            f"{NIGHT} --date <today> --dry-run night --only {f['part']}   # then hand the smoke results to whoever "
            "maintains harness/clients.py",
            f"No cache run of {f['part']} started.")


def _folders_refused(f):
    return (f"{f['part']}: the night's folders failed their checks",
            f"The everyday snapshot (night.py untouched --save) refused the night's folders, so no run of {f['part']} "
            "started (its state folder must be local, mode 700, with no link out of it, its login file 600).",
            f"python3 harness/night.py --date {f['date']} --dry-run untouched --save   # then without --dry-run: it "
            "says what is wrong",
            f"No run of {f['part']} started.")


KINDS = {
    "login-expired": ("that login's part", _login_expired),
    "key-refused": ("that route's part", _key_refused),
    "plan-limit": ("that login's part", _plan_limit),
    "provider-billing": ("that route's part", _provider_billing),
    "vendor-refuses": ("that route's part", _vendor_refuses),
    "window-answered": ("the window list", _window_answered),
    "discovery-stale": ("nothing", _discovery_stale),
    "night-not-started": ("the night", _not_started),
    "unsteady-value": ("that value", _unsteady),
    "smoke-failed": ("that client's part", _smoke_failed),
    "folders-refused": ("that login's part", _folders_refused),
    "checkout-not-ready": ("the night", _checkout_not_ready),
    "checkout-not-updated": ("nothing", _checkout_not_updated),
}
# The rows of the design's table 9.5 (smoke-failed and folders-refused come from 9.4: the checks before spending).
# provider-billing is the design's money row: since 2026-11-26 the night has no cap on money, so only a provider's own
# billing refusal (HTTP 402) stops a route.
# checkout-not-ready and checkout-not-updated: the night's look at its own checkout before it starts (2026-11-25).
TABLE_ROWS = tuple(k for k in KINDS if k not in ("smoke-failed", "folders-refused", "checkout-not-ready",
                                                 "checkout-not-updated"))


def ask_id(kind, subject):
    return kind + "--" + re.sub(r"[^A-Za-z0-9.]+", "-", str(subject)).strip("-")


def notify_mac(text, run=None):
    """A macOS notification (osascript), never a stop when it cannot be shown."""
    text = text.replace("\\", "").replace('"', "'")[:220]
    try:
        (run or subprocess.run)(["osascript", "-e", f'display notification "{text}" with title "groundtruth night"'],
                                capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        pass


class Asks:
    """The open asks of `$G/asks`. `notify(text)` is called once, when an ask is first opened."""

    def __init__(self, folder, notify=None, today=None, dry=False):
        self.folder, self.notify, self.dry = folder, notify or (lambda text: None), dry
        self.today = today or time.strftime("%Y-%m-%d")
        self.opened_now, self.closed_now = [], []
        self._dry_open = {}

    def _dir(self, which):
        return os.path.join(self.folder, which)

    def _path(self, which, aid, ext):
        return os.path.join(self._dir(which), aid + ext)

    def get(self, aid):
        if aid in self._dry_open:
            return self._dry_open[aid]
        try:
            with open(self._path("open", aid, ".json")) as f:
                return json.load(f)
        except FileNotFoundError:
            return None

    def open(self, kind, subject, **facts):
        """Opens the ask (or updates an open one, keeping when it was first opened); notifies only when it is new."""
        if kind not in KINDS:
            raise ValueError(kind)
        aid = ask_id(kind, subject)
        stops, text = KINDS[kind]
        first, happened, command, not_done = text(facts)
        old = self.get(aid)
        ask = {"id": aid, "kind": kind, "subject": str(subject), "stops": stops, "first_line": first,
               "happened": happened, "command": command, "not_done": not_done, "facts": facts,
               "opened": (old or {}).get("opened", self.today),
               "nights": sorted(set((old or {}).get("nights", [])) | {self.today})}
        if self.dry:
            self._dry_open[aid] = ask
        else:
            os.makedirs(self._dir("open"), mode=0o700, exist_ok=True)
            _write(self._path("open", aid, ".json"), json.dumps(ask, indent=1, sort_keys=True) + "\n")
            _write(self._path("open", aid, ".md"), render_one(ask))
        if old is None:
            self.opened_now.append(aid)
            if not self.dry:
                self.notify(first)
        return ask

    def passed(self, kind, subject):
        """The check of `kind` for `subject` passed: its ask, if open, is closed (moved to closed/)."""
        aid = ask_id(kind, subject)
        if self.dry:
            return self._dry_open.pop(aid, None) is not None
        src = self._path("open", aid, ".json")
        if not os.path.exists(src):
            return False
        os.makedirs(self._dir("closed"), mode=0o700, exist_ok=True)
        with open(src) as f:
            ask = json.load(f)
        ask["closed"] = self.today
        _write(self._path("closed", f"{aid}--{self.today}", ".json"), json.dumps(ask, indent=1, sort_keys=True) + "\n")
        os.remove(src)
        md = self._path("open", aid, ".md")
        if os.path.exists(md):
            os.remove(md)
        self.closed_now.append(aid)
        return True

    def open_of(self, kind=None):
        out = list(self._dry_open.values())
        d = self._dir("open")
        if os.path.isdir(d):
            for name in sorted(os.listdir(d)):
                if name.endswith(".json") and name[:-5] not in self._dry_open:
                    with open(os.path.join(d, name)) as f:
                        out.append(json.load(f))
        return sorted((a for a in out if kind is None or a["kind"] == kind), key=lambda a: (a["opened"], a["id"]))

    def subjects(self, kind):
        return {a["subject"] for a in self.open_of(kind)}


def _write(path, text):
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(path + ".tmp", path)


def render_one(ask):
    return (f"# {ask['first_line']}\n\nOpened {ask['opened']}; open on the nights of {', '.join(ask['nights'])}. "
            f"Stops: {ask['stops']}.\n\n{ask['happened']}\n\n{G_NOTE}\n\n```bash\n{ask['command']}\n```\n\n"
            f"Not done: {ask['not_done']}\n\nThis ask closes by itself when its check passes again.\n")


def render_top(asks):
    """The open asks, as every report begins: each with its first line, what it stops and its exact command."""
    lines = ["## Open asks", ""]
    if not asks:
        return lines + ["None.", ""]
    for a in asks:
        lines += [f"- **{a['first_line']}** (open since {a['opened']}; stops {a['stops']})", f"  {a['happened']}",
                  f"  `{a['command']}`", f"  Not done: {a['not_done']}"]
    return lines + ["", G_NOTE, ""]


def main():
    home = os.environ.get("GROUNDTRUTH_CLIENT_HOME")
    if not home:
        raise SystemExit("asks: GROUNDTRUTH_CLIENT_HOME is not set")
    print("\n".join(render_top(Asks(os.path.join(home, "asks")).open_of())))


if __name__ == "__main__":
    main()
