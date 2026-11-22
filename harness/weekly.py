#!/usr/bin/env python3
"""The weekly Monday night, unattended (docs/weekly-night.md; Provimux's design `model-lists.md`, sections 9.3 to 9.6,
with the owner's decisions of 2026-11-22 over it), and its Tuesday commands.

    python3 harness/weekly.py --dry-run night                # the night it would run now: every run, inside both caps
    python3 harness/weekly.py --go night                     # the night (launchd, Mondays at 23:00 Europe/Bucharest)
    python3 harness/weekly.py --date 2026-11-30 status       # Tuesday's first question: did the night run?
    python3 harness/weekly.py --date 2026-11-30 audit        # the mechanical audit: $G/night-<date>/audit-draft.md
    python3 harness/weekly.py --date 2026-11-30 manifest     # after AUDIT.md: the manifest entries, generated
    python3 harness/weekly.py check keys|logins|windows      # a check again (closes the asks it answers)

`--date` defaults to the night now running (a Monday from noon, or the Tuesday before noon). Options of `night`:
`--only codex|devin|keys` (repeatable), `--week-cap <dollars>` (default 10), `--run-cap <dollars>` (default 2),
`--value <route>:<model>:<quantity>` (repeatable: only those values), `--site-data <folder>` (a copy of providers.dev's
published data instead of the site).

What a night does, in order (all of it under GROUNDTRUTH_CLIENT_HOME, `$G`, as the first night; nothing is sent
without --go; --dry-run sends nothing to any vendor, login, key or proxy and writes nothing):
1. Its time: after 03:00 on the Tuesday it does not start (its state is written and the owner asked); after 01:00 no
   `long` run starts.
2. One lock per night (`$G/night-<date>/weekly.json`, created exclusively): a second start of the night is refused.
3. The everyday state's snapshot (`night.py untouched --save`).
4. The plan (harness/plan.py), written to results/night-<date>/PLAN.md.
5. The checks before anything is spent: each login's own status command; each key by a request that costs nothing;
   one smoke run per client, judged by the automatic checks. A failure stops that part only, and asks.
6. The runs. A login's part: at most 6 cache runs a night (`long` ones first), each the probe of the first night,
   staggered, under the same lock, stop marks and isolation. The API keys: one pot of $10 a week, $2 a run at most,
   kept by the ledger (harness/ledger.py); window requests first (each should be refused, and costs nothing), then
   cache runs in the plan's order while the money lasts.
7. The end (Tuesday 11:30 at the latest, a run still alive gets its stop mark): `untouched --report`, the mechanical
   audit, REPORT.md (public) and state.json (private), and one notification.

A cap reached, an expired login, a refused key, a vendor refusing twice: that part stops and the owner is asked
(harness/asks.py); the rest goes on.
"""
import sys
sys.dont_write_bytecode = True
import argparse  # noqa: E402
import datetime as dt
import glob
import json
import os
import re
import signal
import subprocess
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import asks as A  # noqa: E402
import clients as C  # noqa: E402
import ledger as L  # noqa: E402
import night as N  # noqa: E402
import plan as P  # noqa: E402

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Bucharest")
except Exception:  # noqa: BLE001 - no tz database: the Mac's local time (the owner's Mac is in Bucharest)
    TZ = None

LOGIN_CAP = 6                      # cache runs per login per night (the owner, 2026-11-22); the smoke run is apart
NO_LONG_AFTER = dt.time(1, 0)      # Tuesday: no `long` run starts after
NO_START_AFTER = dt.time(3, 0)     # Tuesday: the night does not start after
DEADLINE = dt.time(11, 30)         # Tuesday: a run still alive gets its stop mark
API_PARALLEL = 12                  # API-key cache runs under way at once
POLL_S = 60
PARTS = ("codex", "devin", "keys")
PART_ROUTES = {"codex": ("codex-subscription",), "devin": ("devin",), "keys": P.KEY_ROUTES}
ROUTE_PART = {r: p for p, rs in PART_ROUTES.items() for r in rs}
SMOKE_MODEL = {"codex": "gpt-6-luna", "devin": "claude-haiku-5-5-low"}
SPACING = {"codex": 15, "devin": 20, "keys": 15}
KEY_VARS = {"openrouter": "OPENROUTER_API_KEY", "openai-api": "OPENAI_API_KEY", "anthropic-api": "ANTHROPIC_API_KEY"}
API = {"openrouter": {"base": "https://openrouter.ai/api/v1", "format": "responses", "short": "or"},
       "openai-api": {"base": "https://api.openai.com/v1", "format": "responses", "short": "oa"},
       "anthropic-api": {"base": "https://api.anthropic.com/v1", "format": "messages", "short": "an",
                         "extra": ["--concurrency", "2"]}}
# Anthropic's models on OpenRouter cache only marked content: as the 18 November night (results/openrouter-2026-11-18).
OPENROUTER_ANTHROPIC = ["--body-extra", '{"cache_control":{"type":"ephemeral"}}', "--session-id"]
KEY_CHECK = {"openrouter": "https://openrouter.ai/api/v1/key", "openai-api": "https://api.openai.com/v1/models",
             "anthropic-api": "https://api.anthropic.com/v1/models"}
# The first night's effort suffixes of the Devin ids (harness/night.py's DEVIN), where listed.json gives none.
DEVIN_EFFORT = {P.base_id(m): m[len(P.base_id(m)) + 1:] for _, m, _ in N.DEVIN}
EFFORT_PREFERENCE = ("low", "none", "minimal", "medium", "high")


def results_dir(date):
    return os.path.join("results", f"night-{date}")


def now_local(clock=None):
    t = clock() if clock else dt.datetime.now(dt.timezone.utc)
    return t.astimezone(TZ) if TZ else t.astimezone()


def night_date(now):
    """The Monday whose night `now` belongs to: a Monday from noon, or the Tuesday before noon. None otherwise."""
    if now.weekday() == 0 and now.time() >= dt.time(12, 0):
        return now.date().isoformat()
    if now.weekday() == 1 and now.time() < dt.time(12, 0):
        return (now.date() - dt.timedelta(days=1)).isoformat()
    return None


def at(date, days, t):
    day = dt.date.fromisoformat(date) + dt.timedelta(days=days)
    naive = dt.datetime.combine(day, t)
    return naive.replace(tzinfo=TZ) if TZ else naive.astimezone()


def timing(date, now):
    """'too late' (after 03:00 on the Tuesday), 'no long' (after 01:00), else 'ok'."""
    if now >= at(date, 1, NO_START_AFTER):
        return "too late"
    if now >= at(date, 1, NO_LONG_AFTER):
        return "no long"
    return "ok"


def slug(s):
    return re.sub(r"[^A-Za-z0-9.]+", "-", s).strip("-")


def devin_model(model, efforts=None):
    """The Devin id a run asks for: the model with its effort suffix (the lowest the list offers, else the first
    night's, else `low`)."""
    if efforts:
        for e in EFFORT_PREFERENCE:
            if e in efforts:
                return f"{model}-{e}"
        return f"{model}-{efforts[0]}"
    return f"{model}-{DEVIN_EFFORT.get(model, 'low')}"


# --- the selection: the plan, cut by the caps ------------------------------------------------------------------------

def login_runs(plan, part, late=False, values=None):
    """A login's cache runs of the night: the plan's first LOGIN_CAP cache values of its route (a `long` one dropped
    after 01:00: it stays first next Monday), the `long` ones started first. Returns (runs, left)."""
    route = PART_ROUTES[part][0]
    items = [i for i in plan["planned"] if i["route"] == route and i["quantity"] == "cache"
             and (values is None or i["key"] in values)]
    if late:
        items = [i for i in items if i.get("schedule") != "long"]
    chosen, left = items[:LOGIN_CAP], items[LOGIN_CAP:]
    chosen = [i for i in chosen if i.get("schedule") == "long"] + [i for i in chosen if i.get("schedule") != "long"]
    prefix = {"codex": "cx", "devin": "dv"}[part]
    runs = []
    for i in chosen:
        model = devin_model(i["model"], i.get("efforts")) if part == "devin" else i["model"]
        runs.append({"label": f"{prefix}-{slug(model)}", "part": part, "route": route, "model": i["model"],
                     "ask_model": model, "quantity": "cache", "schedule": i.get("schedule", "std"), "key": i["key"],
                     "state_before": i["state"]})
    return runs, left


def key_items(plan, late=False, values=None, routes=None):
    """The API-key values of the night, in the plan's order: window requests, then cache runs."""
    out = []
    for i in plan["planned"]:
        if i["route"] not in P.KEY_ROUTES or (routes is not None and i["route"] not in routes):
            continue
        if values is not None and i["key"] not in values:
            continue
        if i["quantity"] == "cache" and late and i.get("schedule") == "long":
            continue
        short = API[i["route"]]["short"]
        out.append({"label": f"{short}-{slug(i['model'])}" + ("-window" if i["quantity"] == "window" else ""),
                    "part": "keys", "route": i["route"], "model": i["model"], "quantity": i["quantity"],
                    "schedule": i.get("schedule"), "key": i["key"], "estimate": i.get("estimate_usd"),
                    "words": i.get("words"), "prices": i.get("prices") or {}, "state_before": i["state"]})
    windows = [x for x in out if x["quantity"] == "window"]
    return windows, [x for x in out if x["quantity"] == "cache"]


# --- the night ---------------------------------------------------------------------------------------------------------

class Night:
    """One night. `w` is its contact with the world (World; a fake in the tests)."""

    def __init__(self, date, w, home, dry=False, only=None, week_cap=L.WEEK_CAP, run_cap=L.RUN_CAP, values=None,
                 out=print, root=ROOT):
        self.date, self.w, self.home, self.dry, self.out, self.root = date, w, home, dry, out, root
        self.only = tuple(only) if only else PARTS
        self.values = set(values) if values else None
        self.private = os.path.join(home, f"night-{date}")
        self.public = os.path.join(root, results_dir(date))
        self.notes = []  # new asks' first lines, shown together (flush): one notification per burst
        self.asks = A.Asks(os.path.join(home, "asks"), notify=self.notes.append, today=date, dry=dry)
        self.ledger = L.Ledger(os.path.join(home, "ledger"), date, week_cap, run_cap, dry=dry)
        self.parts = {p: {"status": "not planned", "planned": 0, "started": 0, "runs": []} for p in self.only}
        self.routes_stopped = {}
        self.refusals = {}
        self.started_runs = []
        self.left = {}
        self.windows = []
        self.state = {"date": date, "dry_run": dry, "parts": self.parts}

    # -- bookkeeping
    def say(self, text):
        self.out(text)

    def flush(self):
        """The new asks, at once: one notification with the first line, or with how many and the first."""
        if self.notes:
            self.w.notify(self.notes[0] if len(self.notes) == 1 else
                          f"{len(self.notes)} new asks; the first: {self.notes[0]} (all in the night's report)")
            self.notes.clear()

    def stop_part(self, part, why):
        p = self.parts.get(part)
        if p is not None and not p["status"].startswith(("stopped", "not started")):
            p["status"] = f"stopped: {why}" if p["started"] else f"not started: {why}"

    def stop_route(self, route, why):
        self.routes_stopped.setdefault(route, why)
        if ROUTE_PART[route] != "keys":
            self.stop_part(ROUTE_PART[route], why)

    # -- the steps
    def run(self):
        now = self.w.now()
        when = timing(self.date, now)
        if when == "too late":
            self.say(f"the night of {self.date}: it is {now:%a %H:%M}: after 03:00 on the Tuesday the night does not "
                     "start")
            if not self.dry:
                os.makedirs(self.private, mode=0o700, exist_ok=True)
                self.asks.open("night-not-started", self.date, date=self.date,
                               reason="the Mac woke (or the job ran) after 03:00 on the Tuesday",
                               woke=f"{now:%a %Y-%m-%d %H:%M}")
                self.state.update(started=False, reason="too late", at=now.isoformat())
                self.write_state()
                self.flush()
            return self.state
        self.take_lock(now)
        self.asks.passed("night-not-started", self.date)
        self.snapshot()
        site = self.w.site()
        observed = _load(os.path.join(self.root, "observed.json"), {})
        values = _load(os.path.join(self.root, "plan", "values.json"), {})
        listed = _load(os.path.join(self.root, "listed.json"))
        plan = P.build(self.date, observed, site, values, listed, root=self.root)
        self.plan = plan
        self.plan_asks(plan, listed)
        self.write_public("PLAN.md", P.render(plan))
        late = when == "no long"
        if late:
            self.say("after 01:00: no `long` run starts tonight; those stay first next Monday")
        login = {}
        for part in ("codex", "devin"):
            if part in self.only:
                runs, left = login_runs(plan, part, late, self.values)
                login[part], self.left[part] = runs, left
                self.parts[part]["planned"] = len(runs)
        windows, caches = key_items(plan, late, self.values) if "keys" in self.only else ([], [])
        if "keys" in self.only:
            self.parts["keys"]["planned"] = len(windows) + len(caches)
        self.checks(login, windows + caches)
        self.flush()
        if self.dry:
            return self.dry_report(login, windows, caches)
        self.go(login, windows, caches)
        return self.finish()

    def take_lock(self, now):
        if self.dry:
            return
        os.makedirs(self.private, mode=0o700, exist_ok=True)
        path = os.path.join(self.private, "weekly.json")
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError:
            raise SystemExit(f"night {self.date}: started already (its lock <client-home>/night-{self.date}/"
                             "weekly.json): a second start of the same night is refused") from None
        with os.fdopen(fd, "w") as f:
            json.dump({"date": self.date, "pid": os.getpid(), "started": now.isoformat(), "only": list(self.only)}, f)
        self.state.update(started=True, at=now.isoformat())
        self.w.keep_awake()

    def snapshot(self):
        if self.dry:
            self.say("would take the everyday state's snapshot (night.py untouched --save)")
            return
        why = self.w.untouched(self.date, "save")
        self.state["snapshot"] = "taken" if not why else "not taken"
        if why:
            for part in ("codex", "devin"):
                if part in self.parts:
                    self.asks.open("folders-refused", part, part=part, date=self.date)
                    self.stop_part(part, "the night's folders failed their checks")
        else:
            for part in ("codex", "devin"):
                self.asks.passed("folders-refused", part)

    def plan_asks(self, plan, listed):
        unsteady = set()
        for a in plan["asks"]:
            subject = f"{a['route']}|{a['model']}|{a['quantity']}"
            unsteady.add(subject)
            self.asks.open("unsteady-value", subject, **{k: v for k, v in a.items() if k != "kind"})
        for subject in self.asks.subjects("unsteady-value") - unsteady:
            self.asks.passed("unsteady-value", subject)
        day = dt.date.fromisoformat(self.date)
        for provider, lp in ((listed or {}).get("providers") or {}).items():
            got = P.parse_day(lp.get("date"))
            days = (day - got).days if got else None
            if days is None or days > 3:
                self.asks.open("discovery-stale", provider, provider=provider, days=days if days is not None else "?")
            else:
                self.asks.passed("discovery-stale", provider)

    def checks(self, login, key_values):
        """Before anything is spent: each login's status, each key's free request, one smoke run per client."""
        for part, runs in login.items():
            if not runs:
                self.parts[part]["status"] = "nothing to measure"
                continue
            if self.parts[part]["status"].startswith("not started"):
                continue
            if self.dry:
                self.parts[part]["status"] = "would check its login, then its smoke run"
                continue
            why = self.w.login_status(part)
            if why:
                self.asks.open("login-expired", part, part=part, date=self.date, when="before the runs")
                self.stop_part(part, "login expired")
                continue
            self.asks.passed("login-expired", part)
            problems = self.w.smoke(part, self.date)
            if problems:
                self.asks.open("smoke-failed", part, part=part, problems=problems)
                self.stop_part(part, "smoke failed")
                continue
            self.asks.passed("smoke-failed", part)
            self.parts[part]["status"] = "checked"
        if "keys" not in self.parts:
            return
        routes = sorted({v["route"] for v in key_values})
        if not routes:
            self.parts["keys"]["status"] = "nothing to measure"
            return
        if self.dry:
            self.parts["keys"]["status"] = "would check each key with a request that costs nothing"
            return
        keys = self.w.read_keys()
        for route in routes:
            if not keys.get(route):
                self.asks.open("key-refused", route, route=route, variable=KEY_VARS[route], status="no key in the file")
                self.stop_route(route, "no key")
                continue
            status = self.w.key_check(route, keys[route])
            if status in (401, 403):
                self.asks.open("key-refused", route, route=route, variable=KEY_VARS[route], status=f"HTTP {status}")
                self.stop_route(route, "key refused")
            elif status != 200:
                self.stop_route(route, f"its key check answered {status}")
            else:
                self.asks.passed("key-refused", route)
        self.keys = keys
        if self.ledger.exhausted():
            self.money_spent(len(key_values))
        else:
            self.asks.passed("money-spent", self.ledger.week)
        self.parts["keys"]["status"] = "checked" if any(r not in self.routes_stopped for r in routes) else \
            "not started: every key refused"

    def money_spent(self, left_unmeasured):
        self.asks.open("money-spent", self.ledger.week, spent=self.ledger.used() + self.ledger.reserved(),
                       cap=self.ledger.week_cap, left_unmeasured=left_unmeasured)
        self.stop_part("keys", "the week's money is spent")

    # -- the dry run
    def dry_report(self, login, windows, caches):
        lines = [f"# Dry run of the night of {self.date}", "",
                 f"providers.dev dataset `{self.plan['dataset']}`. Nothing was sent to any vendor, login, key or proxy;"
                 " nothing was written.", ""]
        lines += A.render_top(self.asks.open_of())
        for part in ("codex", "devin"):
            if part not in login:
                continue
            runs = login[part]
            lines += [f"## {part}: {len(runs)} of at most {LOGIN_CAP} cache runs", ""]
            lines += [f"{n}. `{r['ask_model']}` ({r['schedule']}, {r['state_before']}) as {r['label']}"
                      for n, r in enumerate(runs, 1)] or ["nothing to measure"]
            if self.left.get(part):
                lines += ["", f"Left for later Mondays by the cap: " +
                          ", ".join(f"`{i['model']}`" for i in self.left[part])]
            lines.append("")
        if "keys" in self.parts:
            lines += [f"## API keys: ${self.ledger.week_cap:.2f} a week, ${self.ledger.run_cap:.2f} a run "
                      f"(left this week ${self.ledger.left():.2f})", ""]
            sent, refused_runs, stopped = [], [], None
            for v in windows + caches:
                if stopped:
                    break
                verdict = self.ledger.admit(v["label"], v["route"], v["model"], v["estimate"])
                if verdict == "ok":
                    if v["quantity"] == "window":
                        self.ledger.release(v["label"])  # a refusal costs nothing: the reservation comes back
                    sent.append(v)
                elif verdict == "over-week":
                    stopped = v
                else:
                    refused_runs.append((v, verdict))
            lines += ["| # | Route | Model | Value | Run | Worst case |", "|---|---|---|---|---|---|"]
            lines += [f"| {n} | {v['route']} | `{v['model']}` | {v['quantity']} | "
                      f"{'window request' if v['quantity'] == 'window' else v['schedule']} | "
                      f"${v['estimate']:.2f} |" for n, v in enumerate(sent, 1)] or ["| | | nothing | | | |"]
            spend = sum(v["estimate"] for v in sent if v["quantity"] == "cache")
            lines += ["", f"{sum(1 for v in sent if v['quantity'] == 'window')} window requests (each should be "
                      f"refused: nothing billed), {sum(1 for v in sent if v['quantity'] == 'cache')} cache runs, "
                      f"worst case ${spend:.2f} in all."]
            if refused_runs:
                lines += ["", "Not started, each an ask:"]
                lines += [f"- {v['route']} `{v['model']}` {v['quantity']}: "
                          + ("worst case ${:.2f}, above the run ceiling".format(v["estimate"]) if why == "over-run-cap"
                             else "no price on providers.dev: no worst case") for v, why in refused_runs]
            if stopped:
                rest = (windows + caches)[(windows + caches).index(stopped):]
                lines += ["", f"The week's money ends at {stopped['route']} `{stopped['model']}` (worst case "
                          f"${stopped['estimate']:.2f}): {len(rest)} values left for later, an ask."]
            lines.append("")
        lines += ["## The plan", "", f"{len(self.plan['planned'])} values planned (results/night-{self.date}/PLAN.md "
                  "on the night)."]
        text = "\n".join(lines) + "\n"
        self.say(text)
        self.state["dry_report"] = text
        return self.state

    # -- the runs
    def go(self, login, windows, caches):
        for part, runs in login.items():
            if self.parts[part]["status"] == "checked":
                self.start_login_part(part, runs)
        pending = []
        if "keys" in self.parts and self.parts["keys"]["status"] == "checked":
            self.run_windows(windows)
            self.flush()
            pending = [c for c in caches if c["route"] not in self.routes_stopped]
        self.supervise(pending)

    def start_login_part(self, part, runs):
        launch_id = f"{self.date}-{part}-{uuid.uuid4().hex[:12]}"
        lock = self.w.lock_part(self.date, part, launch_id)
        if lock is None:
            self.stop_part(part, "launched already for this night")
            return
        self.parts[part]["status"] = "running"
        for i, run in enumerate(runs):
            if i and self.w.login_status(part):  # between two starts
                self.asks.open("login-expired", part, part=part, date=self.date, when="between two runs")
                self.stop_part(part, "login expired")
                break
            if self.parts[part]["status"].startswith("stopped"):
                break
            run["delay"], run["date"] = i * SPACING[part], self.date
            run["handle"] = self.w.start(run, self.date, launch_id, lock)
            run["file"] = f"{results_dir(self.date)}/{run['label']}.jsonl"
            self.parts[part]["started"] += 1
            self.parts[part]["runs"].append(run)
            self.started_runs.append(run)

    def run_windows(self, windows):
        """One request per value, one after the other, before the cache runs: each should be refused (not billed). An
        answered one was billed: the window list ends, and an ask."""
        for v in windows:
            if v["route"] in self.routes_stopped or self.parts["keys"]["status"].startswith("stopped"):
                continue
            verdict = self.ledger.admit(v["label"], v["route"], v["model"], self.priced(v))
            if verdict == "over-run-cap":
                self.asks.open("run-over-cap", v["key"], route=v["route"], model=v["model"], quantity="window",
                               estimate=v["estimate"], cap=self.ledger.run_cap)
                continue
            if verdict == "no-price":
                v["outcome"] = "no price"
                self.windows.append(v)
                continue
            if verdict == "over-week":
                self.money_spent(len(windows))
                return
            self.asks.passed("run-over-cap", v["key"])
            v["date"] = self.date
            res = self.w.window(v, self.keys[v["route"]], self.date)
            v["outcome"], v["status"] = res["outcome"], res.get("status")
            v["file"] = f"{results_dir(self.date)}/windows.jsonl"
            self.windows.append(v)
            self.parts["keys"]["started"] += 1
            if res["outcome"] == "answered":
                self.ledger.settle(v["label"], v["route"], v["model"], res.get("usd") or v["estimate"],
                                   res.get("reported"))
                self.asks.open("window-answered", v["key"], route=v["route"], model=v["model"], words=v["words"],
                               usd=res.get("usd") or v["estimate"])
                self.windows_ended = True
                return
            self.ledger.release(v["label"])
            if res["outcome"] == "key":
                self.asks.open("key-refused", v["route"], route=v["route"], variable=KEY_VARS[v["route"]],
                               status=f"HTTP {res.get('status')}", when="on a window request")
                self.stop_route(v["route"], "key refused")
            # Any other answer ("error": a model the route does not serve, a format it refuses) is recorded in
            # windows.jsonl and the report; it never stops the route's cache runs.
        if windows and not any(v.get("outcome") == "answered" for v in self.windows):
            for subject in self.asks.subjects("window-answered"):
                self.asks.passed("window-answered", subject)

    def priced(self, v):
        """The worst case again, from the prices read just before the run (OpenRouter's own list); the plan's
        (providers.dev's) when none can be read."""
        prices = self.w.price(v)
        if prices and prices.get("in") is not None:
            v["prices"] = prices
            e = {"price_in": prices["in"], "price_out": prices.get("out"), "price_write": prices.get("write")}
            v["estimate"] = P.estimate_usd(e, v["schedule"]) if v["quantity"] == "cache" else \
                P.window_usd(e, v["words"])
        return v["estimate"]

    def refused(self, route, part, kind):
        """A refusal that is neither quota nor login: twice in a row on one route stops it, and asks."""
        self.refusals[route] = self.refusals.get(route, 0) + 1
        if self.refusals[route] >= 2 and route not in self.routes_stopped:
            self.asks.open("vendor-refuses", route, route=route, part=part, refusal=kind)
            self.stop_route(route, "the vendor refused twice in a row")
            if part != "keys":
                self.w.stop_part(self.date, part)

    def start_key_run(self, v):
        verdict = self.ledger.admit(v["label"], v["route"], v["model"], self.priced(v))
        if verdict == "over-run-cap":
            self.asks.open("run-over-cap", v["key"], route=v["route"], model=v["model"], quantity="cache",
                           estimate=v["estimate"], cap=self.ledger.run_cap)
            v["outcome"] = "not started: over the run ceiling"
            return "skip"
        if verdict == "no-price":
            v["outcome"] = "not started: no price"
            return "skip"
        if verdict == "over-week":
            return "stop"
        self.asks.passed("run-over-cap", v["key"])
        v["date"] = self.date
        v["handle"] = self.w.start(v, self.date, None, None, key=self.keys[v["route"]])
        v["started_at"] = self.w.now().isoformat()
        self.parts["keys"]["started"] += 1
        self.parts["keys"]["runs"].append(v)
        self.started_runs.append(v)
        return "ok"

    def supervise(self, queue):
        """Polls the runs under way; starts API-key runs while the money and the slots last; acts on each outcome;
        stops everything still alive at the deadline."""
        deadline = at(self.date, 1, DEADLINE)
        queue = list(queue)
        if queue and self.parts["keys"]["status"] == "checked":
            self.parts["keys"]["status"] = "running"
        while True:
            # Start API-key runs.
            while queue and self.parts["keys"]["status"] == "running" and \
                    sum(1 for r in self.started_runs if r["part"] == "keys" and "outcome" not in r) < API_PARALLEL:
                v = queue[0]
                if v["route"] in self.routes_stopped:
                    queue.pop(0)
                    continue
                verdict = self.start_key_run(v)
                if verdict == "stop":
                    self.money_spent(len(queue))
                    queue = []
                    break
                queue.pop(0)
            alive = [r for r in self.started_runs if "outcome" not in r]
            if not alive and not (queue and self.parts.get("keys", {}).get("status") == "running"):
                break
            if self.w.now() >= deadline:
                for r in alive:
                    self.w.stop(r, self.date)
                    r["outcome"] = "stopped at the deadline"
                break
            for r in alive:
                res = self.w.poll(r)
                if res is not None:
                    self.ended(r, res)
            if self.ledger.exhausted() and "keys" in self.parts and self.parts["keys"]["status"] == "running":
                for r in self.started_runs:
                    if r["part"] == "keys" and "outcome" not in r:
                        self.w.stop(r, self.date)
                        r["outcome"] = "stopped: the week's money is spent"
                self.money_spent(len(queue))
                queue = []
            self.flush()
            if any("outcome" not in r for r in self.started_runs) or queue:
                self.w.sleep(POLL_S)
        for part, p in self.parts.items():
            if p["status"] in ("running", "checked"):
                p["status"] = "done"
        # The checks that passed again tonight close their asks: a login's part that ran to its end without a quota
        # refusal; a route that ran without being stopped.
        for part in ("codex", "devin"):
            if self.parts.get(part, {}).get("status") == "done" and self.parts[part]["started"]:
                self.asks.passed("plan-limit", part)
        for route in {r["route"] for r in self.started_runs} - set(self.routes_stopped):
            if any(r["route"] == route and r.get("outcome") == "done" for r in self.started_runs):
                self.asks.passed("vendor-refuses", route)

    def ended(self, r, res):
        r["outcome"] = res["outcome"]
        part, route = r["part"], r["route"]
        if part == "keys":
            self.ledger.settle(r["label"], route, r["model"], res.get("usd", 0.0), res.get("reported"))
        if res["outcome"] == "done":
            self.refusals[route] = 0
            return
        if res["outcome"] == "quota" and part != "keys":
            p = self.parts[part]
            self.asks.open("plan-limit", part, part=part, ran=p["started"], planned=p["planned"])
            self.stop_part(part, "the plan's limit")
            self.w.stop_part(self.date, part)
        elif res["outcome"] == "login":
            self.asks.open("login-expired", part, part=part, date=self.date, when="during a run")
            self.stop_part(part, "login expired")
            self.w.stop_part(self.date, part)
        elif res["outcome"] == "key":
            self.asks.open("key-refused", route, route=route, variable=KEY_VARS[route],
                           status=f"HTTP {res.get('status')}", when="during a run")
            self.stop_route(route, "key refused")
            for o in self.started_runs:
                if o["route"] == route and "outcome" not in o:
                    self.w.stop(o, self.date)
                    o["outcome"] = "stopped: key refused"
        elif res["outcome"] == "money":  # the provider's own limit (HTTP 402): the API-key part stops
            for o in self.started_runs:
                if o["part"] == "keys" and "outcome" not in o:
                    self.w.stop(o, self.date)
                    o["outcome"] = "stopped: the provider's limit"
            self.money_spent(0)
        elif res["outcome"] == "refused":
            self.refused(route, part, res.get("kind", "refused"))

    # -- the end
    def finish(self):
        self.w.untouched(self.date, "report")
        draft = self.w.audit(self.date)
        self.state["audit_draft"] = bool(draft)
        self.state["ended"] = self.w.now().isoformat()
        self.write_runs()
        report = self.report()
        self.write_public("REPORT.md", report)
        self.write_state()
        self.flush()
        opened = len(self.asks.opened_now)
        done = sum(1 for r in self.started_runs if r.get("outcome") == "done")
        stopped = [p for p, v in self.parts.items() if v["status"].startswith(("stopped", "not started"))]
        self.w.notify(f"Night {self.date}: {done} runs done" + (f", stopped: {', '.join(stopped)}" if stopped else "")
                      + f"; {len(self.asks.open_of())} asks open ({opened} new)")
        return self.state

    def write_public(self, name, text):
        if self.dry:
            return
        os.makedirs(self.public, exist_ok=True)
        with open(os.path.join(self.public, name), "w") as f:
            f.write(text)

    def write_runs(self):
        """results/night-<date>/runs.json: every run started, public (route, model, label, file, options). What
        the next plan counts as waiting for the audit, and what `manifest` generates the entries from."""
        runs = []
        for r in self.started_runs:
            f = r.get("file") or self.w.result_file(r, self.date)
            runs.append({"label": r["label"], "route": r["route"], "model": r["model"], "quantity": r["quantity"],
                         "client": P.ROUTES[r["route"]]["client"], "schedule": r.get("schedule"), "file": f,
                         "options": r.get("options") or {}, "outcome": r.get("outcome")})
        for v in self.windows:
            runs.append({"label": v["label"], "route": v["route"], "model": v["model"], "quantity": "window",
                         "client": "direct", "file": v.get("file"), "outcome": v.get("outcome"),
                         "status": v.get("status")})
        self.write_public("runs.json", json.dumps({"date": self.date, "runs": runs}, indent=1) + "\n")

    def write_state(self):
        if self.dry:
            return
        os.makedirs(self.private, mode=0o700, exist_ok=True)
        state = json.loads(json.dumps(self.state, default=lambda o: None))
        A._write(os.path.join(self.private, "state.json"), json.dumps(state, indent=1) + "\n")

    def report(self):
        lines = [f"# The night of {self.date}", ""]
        lines += A.render_top(self.asks.open_of())
        lines += ["## Parts", "", "| Part | Status | Planned | Started | Done |", "|---|---|---|---|---|"]
        for part, p in self.parts.items():
            runs = [r for r in self.started_runs if r["part"] == part] + \
                (self.windows if part == "keys" else [])
            done = sum(1 for r in runs if r.get("outcome") in ("done", "refused as expected"))
            lines.append(f"| {part} | {p['status']} | {p['planned']} | {p['started']} | {done} |")
        lines += ["", "Runs excluded: decided by the audit (AUDIT.md).", "", "## Values measured", "",
                  "| Route | Model | Value | State before | Outcome | New value |", "|---|---|---|---|---|---|"]
        for r in self.started_runs + self.windows:
            lines.append(f"| {r['route']} | `{r['model']}` | {r['quantity']} | {r['state_before']} | "
                         f"{r.get('outcome')} | {self.w.new_value(r)} |")
        if not self.started_runs and not self.windows:
            lines.append("| | nothing measured | | | | |")
        lines += ["", "The state of each value now: after the audit and the publication (plan/values.json).", "",
                  "## Not measured", ""]
        started = {r["key"] for r in self.started_runs + self.windows}
        left = [i for i in self.plan["planned"] if i["key"] not in started and i["route"] in
                [r for p in self.only for r in PART_ROUTES[p]]]
        lines += [f"{len(left)} planned values were left for next week, in order:", ""]
        lines += [f"{n}. {i['route']} `{i['model']}` {i['quantity']} ({i['state']})" for n, i in enumerate(left, 1)]
        since = self.plan["window_since"]
        nm = [i for i in self.plan["items"] if i["state"] == P.NO_METHOD_STATE and (i["release"] or "") >= since]
        lines += ["", f"No method yet (inside the window): {len(nm)} values: " +
                  (", ".join(f"{i['route']} `{i['model']}` {i['quantity']}" for i in nm) or "none"), "",
                  "## Spent", ""]
        for part in ("codex", "devin"):
            if part in self.parts:
                lines.append(f"- {part}: {sum(self.w.requests(r) for r in self.started_runs if r['part'] == part)} "
                             "requests")
        if "keys" in self.parts:
            by_route = self.ledger.by_route()
            for route in P.KEY_ROUTES:
                lines.append(f"- {route}: ${by_route.get(route, 0.0):.4f}")
            lines.append(f"- the week ({self.ledger.week}): ${self.ledger.used():.4f} of ${self.ledger.week_cap:.2f}")
        return "\n".join(lines) + "\n"


def _load(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


# --- the world: what the night touches (real here; a fake in the tests) ----------------------------------------------

class World:
    """The real contact with the world. Every method that sends a request or starts a process is called only by a
    night with --go."""

    def __init__(self, home, root=ROOT, site_data=None):
        self.home, self.root, self.site_data = home, root, site_data
        self._prices = None

    def now(self):
        return now_local()

    def sleep(self, s):
        time.sleep(s)

    def notify(self, text):
        A.notify_mac(text)

    def keep_awake(self):
        if sys.platform == "darwin":
            subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    def site(self):
        if self.site_data:
            return P.load_site(self.site_data)
        import urllib.request

        def get(path):
            req = urllib.request.Request("https://providers.dev" + path, headers={"User-Agent": "groundtruth"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if data[:2] == b"\x1f\x8b":
                import gzip
                data = gzip.decompress(data)
            return json.loads(data)
        index = get("/data/index.json")
        return P.site_from(index, lambda provider, shard: get(f"/data/entries/{provider}/{shard}.json"))

    def untouched(self, date, mode):
        try:
            N.untouched(date, mode, out=lambda text: None)
            return None
        except SystemExit as e:
            return str(e)

    def login_status(self, part):
        client = C.CLIENTS[part]("m")
        state = os.path.join(self.home, client.client_id)
        if not os.path.isdir(state):
            return "no state folder"
        return C.login_status(client, state, client.environment(state))

    def read_keys(self):
        """The night's keys, from `$G/keys.env` (mode 600 exactly, `NAME=value` lines): never printed or written."""
        path = os.path.join(self.home, "keys.env")
        try:
            C.check_private("the keys file", path, 0o600)
        except (SystemExit, OSError):
            return {}
        values = {}
        with open(path) as f:
            for line in f:
                k, _, v = line.strip().partition("=")
                values[k] = v.strip().strip('"')
        return {route: values.get(var) or None for route, var in KEY_VARS.items()}

    def key_check(self, route, key):
        import urllib.error
        import urllib.request
        headers = {"Authorization": "Bearer " + key, "x-api-key": key, "anthropic-version": "2023-06-01",
                   "User-Agent": "groundtruth"}
        try:
            with urllib.request.urlopen(urllib.request.Request(KEY_CHECK[route], headers=headers), timeout=60) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
        except OSError:
            return 0

    def smoke(self, part, date):
        sid = f"smoke-{part}"
        step = N.smoke(sid, part, SMOKE_MODEL[part])
        out = os.path.join(results_dir(date), "smoke")
        argv = [sys.executable, "harness/probe.py", *step["args"], "--out", out,
                "--keep-raw", os.path.join(N.night_dir(date), "raw", sid)]
        os.makedirs(os.path.join(self.root, out, "logs"), exist_ok=True)
        with N.private_log(os.path.join(self.root, out, "logs", sid + ".log")) as log:
            subprocess.run(["caffeinate", "-i", *argv], cwd=self.root, env=N.clean_env(), stdout=log,
                           stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        problems, _ = N.smoke_problems(sid, N.read_events(os.path.join(self.root, out, sid + ".jsonl")))
        return problems

    def lock_part(self, date, part, launch_id):
        """The part's launch lock, as the first night's (night.py status and stop read it)."""
        d = N.make_night_dir(date)
        os.makedirs(os.path.join(d, "launch"), mode=0o700, exist_ok=True)
        lock = {"client": part, "date": date, "launch_id": launch_id, "launcher_pid": os.getpid(),
                "launcher_started": N.process_started(os.getpid()), "launcher_command": N.process_command(os.getpid()),
                "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "runs": {}}
        try:
            fd = os.open(N.lock_path(date, part), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                         0o600)
        except FileExistsError:
            return None
        with os.fdopen(fd, "w") as f:
            json.dump(lock, f)
        return lock

    def start(self, run, date, launch_id, lock, key=None):
        logs = os.path.join(self.root, results_dir(date), "logs")
        os.makedirs(logs, exist_ok=True)
        if run["part"] == "keys":
            cfg = API[run["route"]]
            usage = os.path.join(self.home, f"night-{date}", "usage")
            os.makedirs(usage, mode=0o700, exist_ok=True)
            argv = ["caffeinate", "-i", "node", "src/cli.ts", "--base-url", cfg["base"], "--format", cfg["format"],
                    "--model", run["model"], "--schedule", run["schedule"], "--stop-on-refusal", "--label",
                    run["label"], "--out", results_dir(date), "--usage-log",
                    os.path.join(usage, run["label"] + ".usage.jsonl"), *cfg.get("extra", [])]
            if run["route"] == "openrouter" and run["model"].startswith("anthropic/"):
                argv += OPENROUTER_ANTHROPIC
                run["options"] = {"cache_control": {"type": "ephemeral"}, "session_id": True}
            env = N.clean_env({"CACHE_PROBE_KEY": key})
            with N.private_log(os.path.join(logs, run["label"] + ".log")) as log:
                p = subprocess.Popen(argv, cwd=self.root, env=env, stdout=log, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, start_new_session=True)
            return p
        step = N.probe(run["label"], run["part"], run["ask_model"], schedule=run["schedule"])
        argv = [sys.executable, "harness/probe.py", *step["args"], "--out", results_dir(date),
                "--delay", str(run.get("delay", 0)), "--launch-id", launch_id]
        with N.private_log(os.path.join(logs, run["label"] + ".log")) as log:
            p = subprocess.Popen(argv, cwd=self.root, env=N.clean_env(), stdout=log, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, start_new_session=True)
        lock["runs"][run["label"]] = {"pid": p.pid, "started": N.process_started(p.pid), "delay_s": run.get("delay", 0)}
        N.write_lock(date, run["part"], lock)
        return p

    def poll(self, run):
        p = run["handle"]
        if p.poll() is None:
            return None
        if run["part"] == "keys":
            return self.key_outcome(run)
        return login_outcome(N.read_events(os.path.join(self.root, run["file"])))

    def key_outcome(self, run):
        usage = os.path.join(self.home, f"night-{run['date']}", "usage", run["label"] + ".usage.jsonl")
        statuses = []
        try:
            with open(usage) as f:
                statuses = [json.loads(x).get("status") for x in f if x.strip()]
        except (OSError, ValueError):
            pass
        usd, rep, _ = L.usage_cost(usage, run.get("prices") or {})
        run["file"] = self.result_file(run, run["date"])
        result = _load(os.path.join(self.root, run["file"] or "-"), {}) or {}
        out = {"usd": usd, "reported": rep}
        if any(s in (401, 403) for s in statuses):
            return dict(out, outcome="key", status=next(s for s in statuses if s in (401, 403)))
        if 402 in statuses:
            return dict(out, outcome="money", status=402)
        if result.get("status") in ("completed", "no-observable-cache"):
            return dict(out, outcome="done")
        bad = [s for s in statuses if isinstance(s, int) and s >= 400]
        return dict(out, outcome="refused" if bad else "failed", kind=f"HTTP {bad[-1]}" if bad else "no result")

    def price(self, v):
        """USD per million tokens of a model, read just before its run: OpenRouter's own model list (read once a
        night); None elsewhere (the plan's, providers.dev's, stand)."""
        if v["route"] != "openrouter":
            return None
        if self._prices is None:
            import urllib.request
            try:
                req = urllib.request.Request("https://openrouter.ai/api/v1/models", headers={"User-Agent": "groundtruth"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    self._prices = {m["id"]: m.get("pricing") or {} for m in json.load(r).get("data") or []}
            except (OSError, ValueError):
                self._prices = {}
        p = self._prices.get(v["model"])
        if not p:
            return None

        def per_m(k):
            return float(p[k]) * 1e6 if p.get(k) not in (None, "") else None
        return {"in": per_m("prompt"), "out": per_m("completion"), "write": per_m("input_cache_write"),
                "read": per_m("input_cache_read")}

    def result_file(self, run, date):
        if run["part"] != "keys":
            return f"{results_dir(date)}/{run['label']}.jsonl"
        found = sorted(f for f in glob.glob(os.path.join(self.root, results_dir(date), run["label"] + "-*.json"))
                       if not f.endswith(".partial.json"))
        return os.path.relpath(found[-1], self.root) if found else None

    def stop(self, run, date):
        if run["part"] == "keys":
            try:
                os.killpg(run["handle"].pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        else:
            self.stop_part(date, run["part"])

    def stop_part(self, date, part):
        N.stop(part, date, out=lambda text: None)

    def window(self, v, key, date):
        import limits as LM
        cfg = API[v["route"]]
        LM.BASE, LM.KEY = cfg["base"], key
        fmt = "chat" if v["route"] == "openrouter" else cfg["format"]
        path, body = LM.build(fmt, v["model"], v["words"])
        if v["route"] == "openrouter":
            body["transforms"] = []
        code, data, secs = LM.post(path, body, timeout=600)
        named = LM.named_limit(LM.message(data)) if code != 200 else None
        row = {"route": v["route"], "model": v["model"], "n": v["words"], "status": code, "named_limit": named,
               "prompt_tokens": LM.prompt_tokens(fmt, data) if code == 200 else None,
               "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        os.makedirs(os.path.join(self.root, results_dir(date)), exist_ok=True)
        with open(os.path.join(self.root, results_dir(date), "windows.jsonl"), "a") as f:
            f.write(json.dumps(row) + "\n")
        if code == 200:
            usd = L.cost(v.get("prices") or {}, L.tokens(data.get("usage") or {}))
            return {"outcome": "answered", "status": code, "usd": usd, "reported": (data.get("usage") or {}).get("cost")}
        if code in (401, 403):
            return {"outcome": "key", "status": code}
        if named or C.INPUT_TOO_LONG.search(LM.message(data) or ""):
            return {"outcome": "refused as expected", "status": code}
        return {"outcome": "error", "status": code}

    def audit(self, date):
        try:
            return audit(date, self.home, self.root)
        except SystemExit:
            return None

    def new_value(self, run):
        return new_value(run, self.root)

    def requests(self, run):
        ev = N.read_events(os.path.join(self.root, run.get("file") or "-")) or []
        return sum((e.get("usage") or {}).get("calls", 0) + (e.get("prime") or {}).get("calls", 0) for e in ev)


def login_outcome(ev):
    """A probe run's outcome from its public lines: done, quota, login, refused (neither: the vendor) or failed."""
    if not ev:
        return {"outcome": "failed", "kind": "no result"}
    last = ev[-1]
    kinds = {e.get("kind") or e.get("error_kind") for e in ev} - {None}
    if last.get("event") == "stop" and last.get("reason") == "quota" or "quota" in kinds:
        return {"outcome": "quota"}
    if "login" in kinds:
        return {"outcome": "login"}
    if last.get("event") == "done" or (last.get("event") == "stop" and last.get("reason") == "no-observable-cache"):
        return {"outcome": "done"}
    if last.get("event") == "stop" and last.get("reason") in ("baseline-failed", "control-failed"):
        return {"outcome": "refused", "kind": ", ".join(sorted(kinds)) or last.get("reason")}
    return {"outcome": "failed", "kind": last.get("reason") or last.get("event")}


def new_value(run, root=ROOT):
    """The cache lifetime a run measured (all warm through, in seconds), as the builder will sum it; or why not."""
    if run.get("quantity") == "window":
        return {"refused as expected": "refused (see windows.jsonl)", "answered": "answered"}.get(run.get("outcome"),
                                                                                              "-")
    path = run.get("file")
    if not path or not os.path.exists(os.path.join(root, path)):
        return "no result"
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_observed", os.path.join(ROOT, "scripts", "build_observed.py"))
    bo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bo)
    bo.ROOT = root
    try:
        data = bo.read_harness(path) if path.endswith(".jsonl") else bo.read_plain(path)
    except (SystemExit, Exception):  # noqa: BLE001 - the audit says why
        return "not readable as a measurement (the audit says why)"
    s = bo.summarize(data["checks"])
    return f"warm through {s['all_warm_through_s']} s" if s["all_warm_through_s"] is not None else "no age all warm"


# --- Tuesday: the mechanical audit, the manifest, the status ---------------------------------------------------------

SESSION_LINE = re.compile(r"detail: session (\d+): ([0-9a-f-]{8,})")
MODEL_NAMES = re.compile(r'"(?:model|to_model|from_model)": ?"([^"]*)"')


def public_line_problems(rec, start):
    """What is wrong with one public line of a probe run against its schema (harness/probe.py, FIELDS): a key not
    listed, a value of another type or outside its fixed set. The start line is the run's plan: no client version."""
    import probe as PR
    if rec.get("event") == "start":
        return ["a start line with a client version"] if "client_version" in rec else []
    pub = PR.Public(os.devnull, start)
    problems = []

    def walk(d, schema, where):
        for k, v in d.items():
            if k == "at" and schema is PR.FIELDS:
                continue
            spec = schema.get(k)
            if isinstance(spec, dict) and isinstance(v, dict):
                walk(v, spec, f"{where}.{k}")
            elif spec is None or not pub.keep(spec, v):
                problems.append(f"{where}.{k} outside the schema")
    walk(rec, PR.FIELDS, rec.get("event", "?"))
    return problems


def audit(date, home, root=ROOT, run=None, out=print):
    """The mechanical items of the audit checklist over results/night-<date>/, written to
    $G/night-<date>/audit-draft.md: per item passed or failed, with counts, never a private text. A person reads every
    public line and writes AUDIT.md (docs/weekly-night.md, "Tuesday")."""
    run = run or subprocess.run
    folder = os.path.join(root, results_dir(date))
    if not os.path.isdir(folder):
        raise SystemExit(f"audit: no results/night-{date}/ folder")
    items = []

    def item(name, ok, detail):
        items.append((name, ok, detail))
    files = sorted(glob.glob(os.path.join(folder, "*.jsonl")) + glob.glob(os.path.join(folder, "smoke", "*.jsonl")))
    files = [f for f in files if os.path.basename(f) != "windows.jsonl"]
    schema_bad, checks_bad, own_turn_bad, scan_bad, codex_runs = 0, 0, 0, 0, []
    for f in files:
        ev = N.read_events(f) or []
        if not ev:
            schema_bad += 1
            continue
        start = ev[0]
        for rec in ev:
            schema_bad += bool(public_line_problems(rec, start))
        for c in (e for e in ev if e.get("event") == "check"):
            u = c.get("usage") or {}
            checks_bad += u.get("model_matches") is not True
            if start.get("harness") == "codex":
                own_turn_bad += u.get("model_evidence") != "own-turn"
        if start.get("harness") == "codex" and os.path.dirname(f) == folder:
            codex_runs.append(os.path.basename(f)[:-len(".jsonl")])
            scans = [e for e in ev if e.get("event") == "model-scan"]
            last = scans[-1] if scans else {}
            if not (last.get("final") is True and last.get("other_models") == 0 and last.get("unreadable") is False):
                scan_bad += 1
    item("A. every public line against its schema", schema_bad == 0,
         f"{len(files)} files; {schema_bad} lines outside the schema")
    item("A. every check names the run's model (model_matches)", checks_bad == 0, f"{checks_bad} checks without it")
    item("A. every Codex check is bound to its own turn (own-turn)", own_turn_bad == 0,
         f"{own_turn_bad} Codex checks without it")
    item("A. every Codex run's last model-scan is final, 0 other models, readable", scan_bad == 0,
         f"{len(codex_runs)} Codex runs; {scan_bad} without such a last line")
    # B. Codex's session files: every model named, and any reroute (two greps by hand on the first night).
    other, reroutes, missing = 0, 0, 0
    sessions = os.path.join(home, "codex-cli", "sessions")
    for label in codex_runs:
        model = (N.read_events(os.path.join(folder, label + ".jsonl")) or [{}])[0].get("model")
        try:
            with open(os.path.join(folder, "logs", label + ".log"), errors="replace") as f:
                ids = [m.group(2) for m in SESSION_LINE.finditer(f.read())]
        except OSError:
            ids = []
        if not ids:
            missing += 1
        for sid in ids:
            found = glob.glob(os.path.join(sessions, "*", "*", "*", f"rollout-*-{sid}.jsonl"))
            if not found:
                missing += 1
                continue
            for path in found:
                with open(path, errors="replace") as f:
                    text = f.read()
                other += sum(1 for name in MODEL_NAMES.findall(text) if name != model)
                reroutes += text.count("model_reroute")
    item("B. Codex session files name only the run's model", other == 0 and missing == 0,
         f"{other} other model names; {missing} session files not found")
    item("B. no reroute in Codex session files", reroutes == 0, f"{reroutes} reroutes")
    # C. git status: nothing outside the night's folder.
    st = run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root, capture_output=True, text=True)
    outside = [line for line in st.stdout.splitlines() if f"results/night-{date}/" not in line]
    item("C. git status lists nothing outside the night's folder", not outside, f"{len(outside)} paths outside it")
    # D. both scans.
    for label, args in (("D. the scan of what a commit could take", ["--own-clients", "--git", "."]),
                        ("D. the scan of the night's folder and its logs", ["--own-clients", results_dir(date)])):
        r = run([sys.executable, "-B", "harness/scan_secrets.py", *args], cwd=root, capture_output=True, text=True)
        lines = r.stdout.strip().splitlines()
        item(label, r.returncode == 0, f"{max(0, len(lines) - 1)} files with findings" if r.returncode else "CLEAN")
    text = [f"# Audit draft of the night of {date}", "", "The mechanical items only; counts, never a private text. "
            "The reviewer reads every public line, judges the `check-invalid`, `retry` and `stop` lines, reads the "
            "console logs and the everyday report, looks at each failed item, and writes "
            f"results/night-{date}/AUDIT.md (docs/weekly-night.md, \"Tuesday\").", ""]
    text += [f"- [{'x' if ok else ' '}] {'passed' if ok else 'FAILED'}: {name}: {detail}" for name, ok, detail in items]
    path = os.path.join(home, f"night-{date}", "audit-draft.md")
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    A._write(path, "\n".join(text) + "\n")
    out(f"audit draft: {sum(ok for _, ok, _ in items)} of {len(items)} items passed; <client-home>/night-{date}/"
        "audit-draft.md")
    return items


EXCLUDED_LINE = re.compile(r"^- `?([A-Za-z0-9._-]+)`?: (.+)$")


def manifest(date, root=ROOT, out=print, dry=False):
    """observed/manifest.json's entries of the night, generated from results/night-<date>/runs.json and AUDIT.md's
    `## Excluded` list (`- <label>: <reason>`), never typed by hand. Refused before the audit is passed."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_observed", os.path.join(ROOT, "scripts", "build_observed.py"))
    bo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bo)
    why = bo.audit_problem(root, f"night-{date}")
    if why:
        raise SystemExit(f"manifest: {why}")
    folder = os.path.join(root, results_dir(date))
    runs = (_load(os.path.join(folder, "runs.json"), {}) or {}).get("runs") or []
    excluded, section = {}, False
    with open(os.path.join(folder, "AUDIT.md")) as f:
        for line in f:
            if line.startswith("## "):
                section = line.strip().lower() == "## excluded"
                continue
            m = EXCLUDED_LINE.match(line.strip()) if section else None
            if m:
                excluded[m.group(1)] = m.group(2)
    path = os.path.join(root, "observed", "manifest.json")
    with open(path) as f:
        man = json.load(f)
    have = {r["id"] for r in man["runs"]} | {e.get("id") for e in man["excluded"]}
    added_runs, added_excluded, windows = [], [], []
    for r in runs:
        rid = f"night-{date}/{r['label']}"
        if r.get("quantity") == "window":
            windows.append(r)
            continue
        if rid in have or not r.get("file"):
            continue
        if r["label"] in excluded or r.get("outcome") != "done":
            reason = excluded.get(r["label"]) or f"the run ended {r.get('outcome')}"
            added_excluded.append({"id": rid, "file": r["file"], "reason": reason})
            continue
        entry = {"id": rid, "file": r["file"], "route": r["route"], "model": r["model"], "client": r["client"]}
        if r.get("options"):
            entry["options"] = r["options"]
        added_runs.append(entry)
    out(f"manifest: {len(added_runs)} runs and {len(added_excluded)} excluded entries of night-{date}"
        + (f"; {len(windows)} window requests are in windows.jsonl for the limits file, by the maintainer"
           if windows else ""))
    if dry:
        return added_runs, added_excluded
    man["runs"] += added_runs
    man["excluded"] += added_excluded
    with open(path, "w") as f:
        f.write(json.dumps(man, indent=1, ensure_ascii=False) + "\n")
    return added_runs, added_excluded


def status(date, home, out=print):
    """Tuesday's first question: did the night run? Its state, its draft, its open asks."""
    state = _load(os.path.join(home, f"night-{date}", "state.json"))
    if state is None:
        out(f"no state file for the night of {date}: the night did not start. Report it with the launchd agent's log "
            "($G/weekly-night.log) and the Mac's wake log (`pmset -g log | grep -E 'Wake|Sleep' | tail -40`).")
        return None
    out(f"the night of {date}: " + ("started " + state.get("at", "?") if state.get("started") else
                                    f"did not start ({state.get('reason')})"))
    for part, p in (state.get("parts") or {}).items():
        out(f"  {part}: {p.get('status')}, {p.get('started')} of {p.get('planned')} started")
    draft = os.path.exists(os.path.join(home, f"night-{date}", "audit-draft.md"))
    out(f"  audit draft: {'there' if draft else 'missing'}; open asks: "
        f"{len(A.Asks(os.path.join(home, 'asks')).open_of())}")
    return state


def check(what, home, w, out=print):
    """A check again, outside a night: it closes the asks it answers."""
    asks = A.Asks(os.path.join(home, "asks"), notify=w.notify, today=time.strftime("%Y-%m-%d"))
    if what == "keys":
        keys = w.read_keys()
        for route in P.KEY_ROUTES:
            if not keys.get(route):
                out(f"{route}: no key in $G/keys.env")
                continue
            code = w.key_check(route, keys[route])
            out(f"{route}: HTTP {code}")
            if code == 200:
                asks.passed("key-refused", route)
    elif what == "logins":
        for part in ("codex", "devin"):
            why = w.login_status(part)
            out(f"{part}: {'logged in' if not why else 'refused'}")
            if not why:
                asks.passed("login-expired", part)
    elif what == "windows":
        out("windows: the next night's window requests close the window ask (one answered request is a look first)")
    else:
        raise SystemExit("check keys|logins|windows")


def main(argv=None):
    ap = argparse.ArgumentParser(description="The weekly Monday night")
    ap.add_argument("--date", help="the night's Monday (default: the night now running)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--go", action="store_true")
    ap.add_argument("what", nargs="+", help="night | status | audit | manifest | check keys|logins|windows")
    ap.add_argument("--only", action="append", choices=PARTS)
    ap.add_argument("--week-cap", type=float, default=L.WEEK_CAP)
    ap.add_argument("--run-cap", type=float, default=L.RUN_CAP)
    ap.add_argument("--value", action="append", help="<route>:<model>:<quantity>, only these values")
    ap.add_argument("--site-data", help="a copy of providers.dev's published data folder")
    a = ap.parse_args(argv)
    date = a.date or night_date(now_local())
    head = a.what[0]
    home = os.environ.get("GROUNDTRUTH_CLIENT_HOME")
    if head == "night":
        if not date:
            raise SystemExit("night: it is not a Monday night (Monday from noon to Tuesday noon): give --date")
        if not (a.dry_run or a.go):
            raise SystemExit("night: --dry-run (says what it would do) or --go (does it)")
        if not home:
            raise SystemExit("night: GROUNDTRUTH_CLIENT_HOME is not set")
        if a.go:
            N.need_hook("--go night")
        values = None
        if a.value:
            values = set()
            for v in a.value:
                route, _, rest = v.partition(":")
                model, _, q = rest.rpartition(":")
                values.add(f"{route}|{model}|{q}")
        Night(date, World(home, ROOT, a.site_data), home, dry=a.dry_run, only=a.only, week_cap=a.week_cap,
              run_cap=a.run_cap, values=values).run()
        return
    if not home and head in ("status", "audit", "check"):
        raise SystemExit(f"{head}: GROUNDTRUTH_CLIENT_HOME is not set")
    if head == "status":
        status(date, home)
    elif head == "audit":
        if a.dry_run:
            print(f"audit: would check results/night-{date}/ and write <client-home>/night-{date}/audit-draft.md")
            return
        audit(date, home)
    elif head == "manifest":
        manifest(date, dry=a.dry_run)
    elif head == "check":
        check(a.what[1] if len(a.what) > 1 else "", home, World(home))
    else:
        raise SystemExit("night | status | audit | manifest | check")


if __name__ == "__main__":
    main()
