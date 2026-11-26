# The weekly Monday night

Every Monday at 23:00 Europe/Bucharest the owner's Mac measures, unattended, what is new: cache lifetimes through
the vendors' own clients (Codex CLI, Devin CLI) on the two logins, and cache lifetimes and input windows straight with
API keys (OpenRouter, OpenAI, Anthropic). On Tuesday a reviewer audits the raw results, and only then are they
published. The design is section 9 of Provimux's `model-lists.md`; the owner's decisions override it where they differ
(they are marked **owner** below). His rules of 2026-11-26 stand above the older ones: **no cap on money** ("I can pay
money just to have things done": cost is never a reason to cut or skip a measurement, but he is told what a night
may cost before it runs), and **only models released in the last 31 days, and only the values no source gives yet**.

`harness/weekly.py` holds the night and the Tuesday commands, `harness/plan.py` the plan, `harness/ledger.py` the
record of the money, `harness/asks.py` the asks. The runs themselves are the first night's: `harness/probe.py` for
the clients (with
`docs/own-clients-RUN.md`'s isolation, locks and stop marks) and `src/cli.ts` for the keys. Every command takes
`--dry-run`; nothing is sent without `--go`, and the launchd agent is the one caller that passes it.

## What a night measures (harness/plan.py)

A **value** is one quantity of one model on one route: its cache lifetime (the short profile: the night asks for no
lifetime), its input window, its output limit. Methods: cache lifetimes on every route; windows on the API keys (one
request that should be refused); no window through the own clients yet and no output limit anywhere. A value with no
method is named in the plan, never left out without a word.

- **owner** (2026-11-26): only models released in the **31 days before the night** (the night's date is the plan's
  only clock: a model released on the night's date minus 31 days or later is inside). The release date is read, in
  order, from: providers.dev's entry on the route (`release_date`); for a login's own id, the `released` of its row
  in the login's own listing on providers.dev (`/data/listings/<provider>.json`, as `/api/v1/listings/<provider>`;
  "listed release"); the lab's own model's date where exactly one is known. Never a model released earlier.
  - The lab's date: the lab's own entry on providers.dev, else the lab's own listing row (`released`; the listings
    read are those of every lab that is some entry's canonical lab, and of every owner the logins' listings name),
    else any entry naming the same canonical model (many labs' models are on providers.dev only through OpenRouter);
    used only when exactly one date is known. An API key's model takes its entry's date only.
  - **A model whose release date is unknown is not measured**, and the plan (`PLAN.md`), the dry run and the
    morning report (`REPORT.md`) name it under "No release date known: not measured", so that nobody takes it for
    measured. The day a model was first listed or discovered (`plan/values.json`'s `first_seen`) is not a release
    date: it only puts the models first seen since the last night first.
  - A Devin run asks for the base id with the lowest level of `reasoning.levels` (`low`, else `none`, `minimal`,
    `medium`, `high`); a model the list gives no levels is asked for by its base id.
- **owner** (2026-11-26): of those models, only the **values no source gives yet**. A value is given, and never
  measured, when one of these states it, read from providers.dev's published dataset (the entry of the model on the
  route):
  - models.dev, or the provider's own documentation as providers.dev records it: the entry's documented value
    (`cache_lifetime.short.documented_s` for a cache lifetime, `input_window.documented_tokens` for a window,
    `max_output` for an output limit);
  - Pi's catalog, as providers.dev publishes it (`providers_dev.pi.values`: `prompt_cache.short`, `context_window`);
  - our own measurements: a published run that counts for the route (`observed.json`), or a run of a night still
    waiting for its audit or its publication ("waiting").
  A value that no source gives is **new**, and only new values are planned. The older states (in doubt, source moved,
  the re-check of a value that disagrees) are gone: a value we measured is never measured again. Three measurements
  of which no two agree are still an ask ("unsteady"), a decision for the maintainer.
- The order of the new values: the models first seen since the last night first; then the newest release first;
  then logins in the vendor's list order and keys cheapest first; then the id.
- What counts as measured: on a key, direct runs; on a login, direct and own-client runs. A proxy's runs (Provimux)
  are parity checks, never routine. A run an audit excluded does not count; a run of a night still waiting for its
  audit or its publication holds its value ("waiting"), so it is not measured twice.
- `plan/values.json` is written at each publication (`python3 harness/plan.py --date <today> --site-data <copy>
  --write-values`): per value its count, date, last value and what the two sources stated on the day we measured it,
  and per route the day each model was first seen. Its first version (2026-11-22, dataset `0b47455c15b331fa`)
  records that day's sources for every existing value.
- The night runs discovery first (step G1, `harness/discover.py`, [`discovery.md`](discovery.md); without
  `--publish`) and plans from `<client-home>/listed.json` when it exists, else the checkout's `listed.json`. Until
  discovery has written one, a login's offered models are providers.dev's entries of the login.

## The login cap, and the money

- **owner**: at most **6 cache runs per subscription per night**, plus the client's one smoke run (`--login-cap <n>`
  changes it for one start, on the owner's word only). This is a limit on the subscriptions' use, not on money. A
  model still warm at 2 hours gets a `long` run (12 h 10 min); it is one of the six and starts first. After 01:00 no
  `long` run starts (it stays first next Monday).
- **owner** (2026-11-26): **no cap on money**. The caps of $10 a week and $2 a run (2026-11-22) are retired, with the
  list of values "too dear for the caps" (`plan/not-measured.md`, removed) and the options `--week-cap` and
  `--run-cap`. Nothing is skipped, shortened or refused for what it costs; a value with no price known runs all the
  same.
- **Before the night starts**, its estimate is written where the owner sees it: the night's log
  (`$G/weekly-night.log`, or the day's log of a start by hand), `PLAN.md`, the ledger (an `estimate` row), and the
  morning report (`REPORT.md`, "Spent", beside what was spent). The estimate is the API-key cache runs' worst case:
  every request of 3,000 prompt tokens at the higher of the input and the cache-write price, plus 32 output tokens,
  from providers.dev's prices (the night reads OpenRouter's own list again just before each run). Window checks are
  expected to be refused and cost nothing; what they would cost if every one were answered is stated apart. The
  logins cost no dollars (the subscriptions): their count of runs is stated.
- **The ledger** (`$G/ledger/<monday>.jsonl`, mode 600) is a record: each run's worst case when it starts, what it
  cost when it ends (the replies' usage at the prices read before it, and OpenRouter's own `usage.cost`), each with
  its night's date. The morning report gives the night's sum per route and the night's and the week's totals;
  `python3 harness/ledger.py --week <date>` prints the week, night by night, with each night's estimate. A run stopped
  at the deadline is recorded at its worst case.
- **The window checks** go first, one at a time, newest first, each sent whatever its worst case (an answer instead
  of a refusal: every word a token at the input price). A refused check costs $0. An answered one is recorded at what
  it cost (its worst case when the answer gives none), raises an ask and **ends the window list**: a check that
  should have been refused and was answered says the method is wrong for that route, so the next ones would be wrong
  too. Then every cache run, in the plan's order, twelve at a time.
- **The stops that stay**, none of them a cap on money: a provider that refuses for billing (HTTP 402: no credit, a
  limit the owner set on the account) stops that route and asks; a key refused (401/403) stops its route; a vendor
  refusing twice in a row stops its route; a run's probe stops itself on a refusal (`--stop-on-refusal`); every run
  has a fixed schedule (`std` 87 requests, `long` 105; a window check one request) and each value is run once a night;
  at Tuesday 11:30 every run still alive gets its stop mark.
- A night that runs out of candidates ends early; it never fills a login's six with repeats.

## The checkout

The night runs from the workspace's groundtruth checkout (the launchd agent's working folder): its results land
there and Tuesday's audit reads them there. Other people work in this workspace, so before anything else (after the
03:00 check, before the lock) the night looks at it (`check_checkout` in `harness/weekly.py`):

- HEAD on the branch **`main`**;
- **no change to a tracked file**, staged or not (untracked and ignored files, the private `results/…/logs/`
  among them, never count);
- **`main` on GitHub's `main` history**: it may be behind; it must not hold a commit GitHub lacks. GitHub's `main`
  is fetched from `https://github.com/ngvoicu/groundtruth.git` into `refs/night/github-main` (never the NAS); when
  GitHub cannot be reached, the one fetched last stands in, and the report says so.

A condition not met: the night does **not start**. It writes its state (`started: false`, `reason: checkout not
ready`), raises the ask `checkout-not-ready`, which says exactly what is wrong and gives the commands that fix it
followed by the night by hand (`git stash push -m "kept before the weekly night"`, `git switch main`, `git branch
kept-<sha> main && git reset --keep <github sha>`; nothing is thrown away), and notifies. Nothing is sent to any
provider. A night already started (its lock) is never overwritten.

All met and behind: the night **updates itself**. It fast-forwards `main` to the GitHub commit it fetched (`git
merge --ff-only`: git checks the whole update before it writes a file, and refuses, writing nothing, when an
untracked file is in the way), checks the result (HEAD at that commit, no tracked change), then starts itself again
(`execve`, the same command) so the night runs the new code, not the code it was started with; it updates once. A
fix pushed to GitHub on Monday afternoon therefore counts. An update refused with the checkout left as it was: the
night runs on the old commit (it is on GitHub's history) and asks (`checkout-not-updated`, stops nothing). An
update that left anything else (it cannot in practice: a crash or a full disk mid-write) is a condition not met:
the night does not start, and the ask's command completes the update (`git reset --hard <sha>`: the checkout was
clean before it).

`--dry-run` reads GitHub's `main` with `git ls-remote` (it fetches nothing and moves nothing), reports the same check
under "The checkout", shows the ask a failure would raise, and goes on.

## The owner, once

```bash
export GROUNDTRUTH_CLIENT_HOME="$HOME/groundtruth-clients"; G="$GROUNDTRUTH_CLIENT_HOME"
sudo pmset repeat wakeorpoweron M 23:01:00            # the Mac wakes on Mondays at 23:01 (below)
# the logins stay in the night's own folder between weeks (the first night's, docs/own-clients-RUN.md, step 2)
umask 077; printf 'OPENROUTER_API_KEY=%s\nOPENAI_API_KEY=%s\nANTHROPIC_API_KEY=%s\n' \
  "<a key made for the night, with its own limit>" "<…>" "<…>" > "$G/keys.env"; chmod 600 "$G/keys.env"
```

The lid stays open and the Mac on power on Monday nights, the owner logged in (the screen may be locked): the agent
lives in the owner's session, so a Mac that is shut down, or at the login window, runs no night. The wake is just
after 23:00 on purpose: launchd starts a calendar job missed while the Mac slept as soon as it wakes, so the night
starts at the wake itself, and its `caffeinate` holds the Mac awake from then on. A wake before 23:00 would need the
Mac to stay awake, idle, until 23:00, which nothing holds. `pmset repeat` keeps one repeating wake: it replaces any
other (`pmset -g sched` shows it); `sudo pmset repeat cancel` removes it.

## Staff, once, with the owner's OK

```bash
scripts/install-weekly-night.sh --owner-ok --dry-run-nights   # step G6: a dry-run Monday first
scripts/install-weekly-night.sh --owner-ok                    # then the real nights (it replaces the agent)
scripts/install-weekly-night.sh --print                       # writes nothing: the plist it would install
```

It fills `scripts/launchd/dev.providers.groundtruth.weekly-night.plist` in (this checkout, `$G`, this shell's
`python3` and `PATH`), writes it to `~/Library/LaunchAgents/` and loads it. Its log is `$G/weekly-night.log`. A job
missed while the Mac slept runs when it wakes; `--uninstall --owner-ok` removes it.

## The night, as it runs

| When (Bucharest) | What |
|---|---|
| Mon 23:00 | the checkout's look (above; a fast-forward and a restart when behind); the lock (`$G/night-<date>/weekly.json`, exclusive: a second start of the night is refused); the everyday snapshot; the plan, `results/night-<date>/PLAN.md`; the estimate, in the log and the ledger |
| | the checks before anything is spent: each login's status, each key's free request, one smoke run per client. A failure: that part does not start, and an ask |
| Mon ~23:15 | the runs: each login's six, each started as the first night's launcher plans it (`night.plan`: Devin's whole schedule under 36 requests in any 60 s and 270 in any 15 minutes; the dry run shows each start and end); the window checks one by one; the key runs, twelve at a time |
| Tue ~01:30 | the `std` runs have ended |
| Tue 11:30 at the latest | a run still alive gets its stop mark; `untouched --report`; the audit draft; `REPORT.md`, `runs.json` (public); `state.json` (private); one notification |

A late start: after 01:00 no `long` run; after 03:00 the night does not start, writes its state and asks (also when
the Mac slept through and launchd runs the missed job later in the week: it is last Monday's night). A night already
started is never overwritten. The ask's command runs the week's night by hand under today's date (same week, same
ledger); that start closes the ask.

`python3 harness/night.py --date <date> status` and `stop codex|devin|all` work on a weekly night's logins as on the
first night.

## One login by day

The night's own command runs one login's part alone on any day, without waiting for Monday: `--only devin` (or
`codex`), with `--date <today>`. It is a night like any other: the checkout's look, the lock
(`$G/night-<today>/weekly.json`), discovery, the snapshot, the plan from today's date (its 31 days end today), the
login's status and its smoke run, the runs, and `results/night-<today>/` with `PLAN.md`, `runs.json` and `REPORT.md`.
So the audit, the manifest and the publication treat it as any night, and until it is published the next Monday's
plan holds its values as "waiting for its audit" (never measured twice). With `--only devin` the night reads no key
file and starts nothing on the Codex login (the snapshot lists the everyday folders' names and dates, as every
night). `--value devin:<model>:cache` (repeatable) names the runs exactly; `--login-cap <n>` lets more than six start
(the owner's word). It ends when its last run ends, not at a set hour; Tuesday's 03:00 and 11:30 limits count from
`--date`, so a start by day is never late. Its audit and publication are Tuesday's steps with `--date <that day>`;
best before the next Monday night, whose audit draft would otherwise count the unpublished folder as a path outside
its own night (item C). `stop` ends the night's own process too (the lock names it as the launcher): the runs stop,
but `runs.json`, `REPORT.md` and the audit draft are not written; until they are, the next plan still holds the
stopped runs' values as waiting (it reads the folder's `*.jsonl`).

```bash
cd ~/Projects/ngvoicu/providers.dev/groundtruth
export GROUNDTRUTH_CLIENT_HOME="$HOME/groundtruth-clients"
python3 harness/weekly.py --go check logins --only devin                          # Devin's own status command only
python3 harness/weekly.py --date "$(date +%F)" --dry-run night --only devin       # what it would run: nothing sent
nohup caffeinate -i python3 -B harness/weekly.py --date "$(date +%F)" --go night --only devin \
  >> "$GROUNDTRUTH_CLIENT_HOME/day-$(date +%F).log" 2>&1 &                          # the run; the terminal may close
python3 harness/night.py --date "$(date +%F)" status                               # its runs, alive or ended
python3 harness/night.py --date "$(date +%F)" stop devin                           # stops it
```

## When the night asks (harness/asks.py)

Each case stops its own part only. The owner gets a macOS notification at once (one for a burst), the ask in full in
`$G/asks/open/<id>.md` with the exact command, and every open ask at the top of every report until the check that
failed passes again; nobody closes one by hand. `python3 harness/asks.py` lists them; `python3 harness/weekly.py
--go check keys|logins` runs a check again (it sends: without `--go` it only says what it would send; `check logins
--only devin` runs that login's alone).

| Case | Stops | The command in the ask |
|---|---|---|
| a login expired (status before or between runs, or a run's login error) | that login's part | `python3 harness/night.py --date <date> login <client>` |
| a key refused (401/403) or missing | that route | `python3 harness/weekly.py --go check keys` |
| a plan's limit (quota) | that login's part | `python3 harness/weekly.py --date <today> --go night --only <client>` |
| a provider refusing for billing (HTTP 402) | that route | the same with `--only keys`, once the account has credit |
| a vendor refusing twice in a row | that route | the same with `--only <part>`, after a look at the account |
| a window request answered | the window list | none: a look first; the next night's requests close it |
| discovery stale (over 3 days) | nothing | Provimux's status page, then discovery |
| the night did not start (after 03:00) | the night | `python3 harness/weekly.py --date <today> --go night` |
| the checkout not ready (not `main`, a tracked change, a commit GitHub lacks) | the night | the fixing commands, then the same |
| the checkout could not update itself | nothing | `git pull --ff-only https://github.com/ngvoicu/groundtruth.git main` (says what is in the way) |
| an unsteady value | that value | none: a decision |
| a smoke run failed, the night's folders refused | that client's part | the smoke results to the maintainer; `night.py untouched --save` |

## Tuesday

1. **Did the night run?** `python3 harness/weekly.py --date <date> status`. No state file: the night did not start;
   report it with `$G/weekly-night.log` and `pmset -g log | grep -E 'Wake|Sleep' | tail -40`.
2. **The draft**, written by the night (or `python3 harness/night.py --date <date> audit`):
   `$G/night-<date>/audit-draft.md`, the mechanical items with counts and no private text: every public line against
   its schema; every check's model (`model_matches`), Codex's `own-turn`, the last `model-scan`; Codex's session
   files listed for any other model and any reroute; `git status`; both scans.
3. **The reviewer** (not who wrote the code the night ran that week), on the owner's Mac, reading only: reads every
   public line of `results/night-<date>/`; judges the `check-invalid`, `retry` and `stop` lines; reads the console
   logs (`results/night-<date>/logs/`) and the everyday report for anything private; looks at each failed item of
   the draft; writes `results/night-<date>/AUDIT.md`: the first line exactly `# Night audit: passed`, the date, the
   role that audited, a section `## Excluded` with one line `- <label>: <reason>` per run left out, and one line per
   item. Not the reviewer's alone, and nothing committed: something private in a public file, a Keychain item a
   client added or changed, an unsteady value. Each goes to the chief.
4. **The publication**, after the audit: `python3 harness/night.py --date <date> manifest` adds the night's entries to
   `observed/manifest.json` (generated from `runs.json` and `AUDIT.md`, never typed); the window requests are in
   `windows.jsonl` for the maintainer's limits file. Then `python3 scripts/build_observed.py` and its `--check`,
   `plan/values.json` (`harness/plan.py --write-values`), the commit and the push. The builder, the commit hook and
   CI refuse anything under `results/night-*` without its `AUDIT.md`.
