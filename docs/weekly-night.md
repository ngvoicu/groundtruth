# The weekly Monday night

Every Monday at 23:00 Europe/Bucharest the owner's Mac measures, unattended, what is new: cache lifetimes through
the vendors' own clients (Codex CLI, Devin CLI) on the two logins, and cache lifetimes and input windows straight with
API keys (OpenRouter, OpenAI, Anthropic). On Tuesday a reviewer audits the raw results, and only then are they
published. The design is section 9 of Provimux's `model-lists.md`; the owner's decisions of 2026-11-22 override it
where they differ (they are marked **owner** below).

`harness/weekly.py` holds the night and the Tuesday commands, `harness/plan.py` the plan, `harness/ledger.py` the
money, `harness/asks.py` the asks. The runs themselves are the first night's: `harness/probe.py` for the clients (with
`docs/own-clients-RUN.md`'s isolation, locks and stop marks) and `src/cli.ts` for the keys. Every command takes
`--dry-run`; nothing is sent without `--go`, and the launchd agent is the one caller that passes it.

## What a night measures (harness/plan.py)

A **value** is one quantity of one model on one route: its cache lifetime (the short profile: the night asks for no
lifetime), its input window, its output limit. Methods: cache lifetimes on every route; windows on the API keys (one
request that should be refused); no window through the own clients yet and no output limit anywhere. A value with no
method is named in the plan, never left out without a word.

- **owner**: only models released in the **last two months** (calendar months before the night), newest first. A
  login's own id with no release date on its entry takes, in order: the `released` of its row in the login's own
  listing on providers.dev (`/data/listings/<provider>.json`, as `/api/v1/listings/<provider>`; "listed release");
  the lab's own model's date where exactly one is known; else the day it was first listed or discovered
  (`plan/values.json`'s `first_seen`; `listed.json` states no date of any kind). Never a model released earlier,
  whatever its state: the design's 90-day re-check of values only we state is dropped.
  - The lab's date: the lab's own entry on providers.dev, else the lab's own listing row (`released`; the listings
    read are those of every lab that is some entry's canonical lab, and of every owner the logins' listings name),
    else any entry naming the same canonical model (many labs' models are on providers.dev only through OpenRouter);
    used only when exactly one date is known. An API key's model takes its entry's date only.
  - A model `listed.json` lists for the first time is first seen on that night (recorded at its publication). The
    models already listed when discovery began (its first file, 2026-11-25) with no date at all are recorded once
    with `first_seen: null` (`harness/plan.py --record-baseline`): the day they were first listed is unknown, so they
    are too old. Without that, every one of them (Opus 4.6, GPT-5.4, SWE-1.6, ...) would be planned as new.
  - A Devin run asks for the base id with the lowest level of `reasoning.levels` (`low`, else `none`, `minimal`,
    `medium`, `high`); a model the list gives no levels is asked for by its base id.
- Inside the window, the order is the design's: **1 new** (never measured; first the models first seen since the
  last night), **2 in doubt** (measured once and disagreeing with models.dev or pi.dev, or twice with two values that
  disagree with each other), **3 source moved** (a source states another value than on the day we measured). A value
  that agrees is never measured again; one measured twice that still disagrees is settled; one no source states is
  "ours alone" and not measured again; three that never agree are "unsteady" (an ask). Within a state: the newest
  release first, then logins in the vendor's list order and keys cheapest first, then the oldest measurement.
- What counts as measured: on a key, direct runs; on a login, direct and own-client runs. A proxy's runs (Provimux)
  are parity checks, never routine. A run an audit excluded does not count; a run of a night still waiting for its
  audit or its publication holds its value ("waiting"), so it is not measured twice.
- Agreement is providers.dev's verdict, never worked out again here: `documented_status` of the entry's
  `cache_lifetime.short` and `input_window`, and pi.dev's `standing` (`prompt_cache.short`, `context_window`). The
  output limit has none before providers.dev 1.4.0: "agreement not available", ordered as new only.
- `plan/values.json` is written at each publication (`python3 harness/plan.py --date <today> --site-data <copy>
  --write-values`): per value its count, date, last value and what the two sources stated on the day we measured it.
  Its first version (2026-11-22, dataset `0b47455c15b331fa`) records that day's sources for every existing value.
- The night runs discovery first (step G1, `harness/discover.py`, [`discovery.md`](discovery.md); without
  `--publish`) and plans from `<client-home>/listed.json` when it exists, else the checkout's `listed.json`. Until
  discovery has written one, a login's offered models are providers.dev's entries of the login.

## The caps

- **owner**: at most **6 cache runs per subscription per night**, plus the client's one smoke run (`--login-cap <n>`
  changes it for one start, on the owner's word only). A model still warm
  at 2 hours gets a `long` run (12 h 10 min); it is one of the six and starts first. After 01:00 no `long` run starts
  (it stays first next Monday).
- **owner**: the API keys share one pot of **$10 a week** with a ceiling of **$2 a run**, kept by the ledger
  (`$G/ledger/<monday>.jsonl`): each run's worst case (every request of 3,000 prompt tokens at the higher of the input
  and the cache-write price, plus 32 output tokens) is reserved before it starts, from the prices read just before
  (OpenRouter's own list; providers.dev's elsewhere); a cache run starts only when it is at most $2 and fits what is
  left; when it ends its real cost (the replies' usage at those prices, and OpenRouter's own `usage.cost`) replaces
  the reservation. The part stops when either figure reaches the cap.
- **owner** (2026-11-22, "A"): a **window check** is **not** held to the $2 a run. The checks go first, one at a
  time, newest first. Before each, its worst case (the vendor answers instead of refusing: every word a token at the
  input price) must fit in $10 minus what the week has been charged minus the cache runs reserved; one that does not
  (every one above $10 among them) is not sent and is an ask, and the list goes on. A refused check is charged $0 and
  its reservation released before the next is considered. An answered one is charged what it cost (its worst case
  when the answer gives none), raises an ask and ends the window list. So the week never passes $10, even when a
  check is answered.
- Then the cache runs, in the plan's order, each held to the $2 a run and reserving its worst case when it starts,
  from what is left.
- Reaching a cap stops that part and asks. A night that runs out of candidates ends early; it never fills a cap with
  repeats.
- **owner** (2026-11-25): a value too dear for the caps is **decided once**, not asked every week:
  [`plan/not-measured.md`](../plan/not-measured.md) holds one row per such value (the value as `--value` takes it,
  the day, who decided, why). The plan names a recorded value whose worst case is still above the caps (a cache run
  above $2 a run, a window check above the week's $10) as "not measured: above the caps (decided <date>)": it is
  not sent and raises no ask, and an ask still open for it closes. When its worst case falls under the caps (a price
  drops; or caps given by hand, `--run-cap`, `--week-cap`), the row no longer applies: the value is planned again
  and `PLAN.md` lists the row as one that can go. A new value above the caps raises its ask once, which gives the
  row to add. A row that does not parse stops the night before it starts (the checkout's ask, below). The four of
  2026-11-25: OpenAI `gpt-6-cyber`'s window check ($23.12) and cache run ($5.50), OpenRouter
  `openai/gpt-6.2-astra` and `openai/gpt-6.2-astra-pro`'s cache runs ($2.72 each).

## The checkout

The night runs from the workspace's groundtruth checkout (the launchd agent's working folder): its results land
there and Tuesday's audit reads them there. Other people work in this workspace, so before anything else (after the
03:00 check, before the lock) the night looks at it (`check_checkout` in `harness/weekly.py`):

- HEAD on the branch **`main`**;
- **no change to a tracked file**, staged or not (untracked and ignored files, the private `results/…/logs/`
  among them, never count);
- **`main` on GitHub's `main` history**: it may be behind; it must not hold a commit GitHub lacks. GitHub's `main`
  is fetched from `https://github.com/ngvoicu/groundtruth.git` into `refs/night/github-main` (never the NAS); when
  GitHub cannot be reached, the one fetched last stands in, and the report says so;
- `plan/not-measured.md` readable.

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
| Mon 23:00 | the checkout's look (above; a fast-forward and a restart when behind); the lock (`$G/night-<date>/weekly.json`, exclusive: a second start of the night is refused); the everyday snapshot; the plan, `results/night-<date>/PLAN.md` |
| | the checks before anything is spent: each login's status, each key's free request, one smoke run per client. A failure: that part does not start, and an ask |
| Mon ~23:15 | the runs: each login's six, each started as the first night's launcher plans it (`night.plan`: Devin's whole schedule under 36 requests in any 60 s and 270 in any 15 minutes; the dry run shows each start and end); the money's pass; the window checks one by one; the key runs, twelve at a time |
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
(`$G/night-<today>/weekly.json`), discovery, the snapshot, the plan from today's date (its two months end today), the
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
| the week's money spent (or the provider's 402) | the API keys | the same with `--only keys --week-cap <dollars>` |
| a cache run over $2 | that one | the same with `--value <route>:<model>:cache --run-cap <dollars>`; or the row it gives, added to `plan/not-measured.md` |
| a window check whose worst case does not fit the week | that one | the same with `--value <route>:<model>:window --week-cap <dollars>`; above $10, or the row it gives |
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
