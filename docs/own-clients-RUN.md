# Measuring through the own clients: the steps

The first night of [`own-clients.md`](own-clients.md), section 4, cut down to **the cache runs of Codex CLI and Devin
CLI only** (the owner's decision of 2026-11-22: the two logins where differences were seen), each through its own
subscription login. Claude Code and Muse Code wait for a later night: no night command runs, logs in or reads a key
for either. There is no Pi run and no Provimux in it, no OpenRouter run and no window request, no input-limit walk and
no Antigravity run. `harness/night.py` holds every command. Every command takes `--dry-run`, which says what it would
do and does nothing else; nothing is sent without `--go`.

There are three parts. **Only the first needs the owner**: his two logins, about 7 minutes, once. Anyone can do the
night and the morning from the repository's root on `main`, with no login and no key.

## You, once (about 7 minutes)

These are the only steps that need the owner. Do them in this order, in one terminal, from the repository's root.

**What the night does to keep apart from your own use of the computer**, and what it does not:

- Every client process it starts gets its own folders under `$G`: its state folder (`$G/codex-cli`, `$G/devin-cli`),
  a throwaway home folder (`HOME=$G/home/<client>`), and its own temporary folder (`TMPDIR=$G/tmp/<client>`). It gets
  only `PATH`, `USER`, `LANG` and `TERM` from your shell, never its `TMPDIR`, a key, a proxy or a base URL.
- On a Mac, every client process runs under `sandbox-exec` with a profile that refuses any file write under your
  home folder except in that client's state folder, its throwaway home and its temporary folders. That covers files
  only. It does not stop a client from reading your files, and it does not cover what a client asks of macOS's own
  services: the Keychain, in particular, is reached through such a service.
- Step 1 records the names, sizes and dates of the files in your everyday client folders (`~/.claude`,
  `~/.claude.json`, `~/.codex`, `~/.devin`, Devin's and Muse Code's folders under `~/.config` and `~/.local/share`,
  `~/.muse`, `~/.pi`) and the names and dates of your Keychain's items, never a content or a secret. The morning
  report lists what changed since, for you to read. It sees a file or an item added, changed or removed; it cannot
  see a read, and it cannot tell your own tools' changes from the night's: a line in it is something to look at, not
  proof of either. If the Keychain cannot be listed (at step 1 or in the morning), the report says the items were not
  compared; it never says "nothing changed" for them. Nothing in it stops the night.
- The night's folders must be yours alone (exactly mode 700) and on this computer: a `$G` under iCloud Drive
  (`~/Library/Mobile Documents`), `~/Library/CloudStorage`, Dropbox, Google Drive or OneDrive is refused, and so is a
  login file whose mode is not exactly 600.
- What the night publishes (`results/own-clients-$N/*.jsonl`) holds no client error text at all: a failed request is
  recorded by its kind only (`timeout`, `exit-nonzero`, `quota`, …). The client's own words, redacted, stay in the
  run's console log (`results/own-clients-$N/logs/`, mode 600, never committed).

So you can use your computer and your tools as usual during the night, Codex and the Devin CLI included.

**What it costs the accounts.** The night uses the ChatGPT plan used with Codex (about 630 requests) and the Devin
subscription (about 1,710 requests), each through its own client. A login's quota is the account's own: start when
the plans' meters are low.

**Devin's account history.** Up to about 870 Devin sessions from the night (863 if every run goes to its end, 4 in
the smoke runs) will appear in the owner's Devin account history: fewer if a control misses (that run ends after its
control), and up to one extra session per priming retry. Each one's first line is `groundtruth cache
measurement <salt> (an automated test, not a task).` (the Devin CLI cannot name a session). Nothing deletes them.

**1. The folders and the snapshot, before any login** (1 minute). `$G` must be a local folder, outside the
repository, any Git checkout, every client's own folders and every synced folder.

```bash
export GROUNDTRUTH_CLIENT_HOME="$HOME/groundtruth-clients"
export N=<YYYY-MM-DD>                                   # the night's date
G="$GROUNDTRUTH_CLIENT_HOME"
mkdir -m 700 "$G" "$G/codex-cli" "$G/devin-cli"
python3 harness/night.py --date $N untouched --save
```

It checks the folders (local, mode 700, no link that leaves them), makes each client's throwaway home and temporary
folder (`$G/home/codex-cli`, `$G/tmp/codex-cli` and so on, mode 700), and records the snapshot described above in
`$G/night-$N/everyday-before.json` (mode 600).

**2. The two logins** (about 2 minutes each; a browser window opens for each), after step 1. Each runs the client's
own login command with exactly the folders, the throwaway home, the temporary folder and the sandbox its runs will
have. It says `done` only when the client's login file is in its state folder (non-empty; then set to mode 600) and
the client's own status command, in the same folders, shows the subscription login; otherwise it says what is
missing, and the login is not done.

```bash
python3 harness/night.py --date $N login codex      # the ChatGPT plan's account
python3 harness/night.py --date $N login devin      # the Devin account
```

Codex is told to keep its login in a file (`$G/codex-cli/auth.json`) and to use its built-in ChatGPT provider
(`model_provider="openai"`); every Codex run says the same on its command line, and a `$G/codex-cli/config.toml`
that selects another provider, a profile or another base URL is refused. Before every run the night checks each
login's status, with the same folders, and refuses an API key; a status that does not positively say it is logged in
(Codex: `Logged in using ChatGPT`; Devin: only the whole lines `Logged in`, `Logged in.`, `Logged in as <one word>`,
`Logged in (via browser)`, `(via web)` or `(via oauth)`, and no mention of an API, a token, a key, a PAT or a personal
access) is refused too, whatever its exit code, and the reply is shown: bring it to whoever maintains
`harness/clients.py`. Never
run `devin auth logout`, and never copy an everyday login file. Neither login asks you to put anything in the Keychain,
and Codex is told to keep its login in a file.

**3. A look at the report** (1 minute).

```bash
python3 harness/night.py --date $N untouched --report
```

It lists what changed since step 1, folder by folder, and the Keychain's items by name; every line is in the file it
names, under `$G/night-$N/` (mode 600). Changes your own tools made meanwhile may appear, and that is expected.

What the Keychain part shows, and what it cannot: it compares the items' names and modification dates at step 1 with
those now, so it shows an item **added, removed or changed between those two moments** that it could list both times,
whoever did it. It cannot prove that no key was written: an item written and removed again between the two moments,
an item a listing does not show, or a secret read, leaves no line in it; and if the Keychain could not be listed, it
says so instead. An item added or changed by Codex or Devin after step 2 is a question for whoever maintains
`harness/clients.py`, with the report.

The owner's part ends here.

## The night

Anyone can do this, from the repository's root, with these set in the shell:

```bash
export GROUNDTRUTH_CLIENT_HOME="$HOME/groundtruth-clients" N=<YYYY-MM-DD>
git config core.hooksPath scripts      # once per clone: each worktree runs its own scripts/pre-commit
```

`--go` refuses to start unless `git config core.hooksPath` is exactly `scripts` in the checkout it runs from, and
the hook Git really selects there (`git rev-parse --git-path hooks/pre-commit`) exists, is executable and is that
checkout's own `scripts/pre-commit` (the same file); a refusal gives the exact command that fixes it. The path is
relative, so Git runs the commit hook of the worktree being committed, never an older one linked under the main
checkout's `.git/hooks` (which every linked worktree would share), and a spelling such as `scripts ` (a trailing
blank), which names a missing hook, is refused. `--dry-run all` says whether it is set.

Every folder the night writes (`$G`, its `night-$N` and `launch` folders, the state folders' throwaway homes, the
raw output, a run's working folder) is checked before anything is made in it: it may not be an everyday folder
(`~/.codex`, `~/.devin`, `~/.claude`, `~/.pi`, `~/.config`, …) or lie in one, compared as real folders (device and
inode, each existing folder above it included), so neither a link nor a spelling such as `~/.CODEX` on a
case-insensitive disk passes.

Keep the computer on power and on the network. Each run keeps it awake (`caffeinate -i -w <its pid>`); a check made too late after
its priming is left out, so a sleeping computer loses checks, not truth.

| # | Command | Time |
|---|---|---|
| 1 | `python3 harness/night.py --date $N --dry-run all` (add `--at HH:MM` for clock times) | 1 min, does nothing; ends with the plan: each run's planned start and expected end, each client's requests and its most in any 60 s and 15 minutes |
| 2 | `python3 harness/night.py --date $N --go smoke` | about 5 min, in the foreground |
| 3 | The smoke review (below), then `python3 harness/night.py --date $N smoke-reviewed` | 10 min |
| 4 | `python3 harness/night.py --date $N --go all` (or one client at a time: `--go codex`, `--go devin`) | returns at once; the runs take about 12 h 30 |

- **`--go <client>`** starts each of that client's runs as its own background process and returns; closing the
  terminal ends none of them. The starts are planned before the go: Codex's 15 s apart; Devin's at least 20 s apart
  and later where needed, so that Devin's whole schedule keeps under 36 requests in any 60 s and 270 in any 15
  minutes (`--limit devin=N60/N900` changes them); `--go` refuses a schedule over them. Nothing paces a run while it
  runs. **The plan's peaks are an estimate, not a bound**: real request times differ from the simulated ones, and
  the real peaks can be somewhat higher (the second review replayed the planned starts and found up to 49 in 60 s and 271
  in 15 minutes; see `own-clients.md`, section 1, rule 6). The safety comes from the margin to Devin's observed
  limit (it refused only after about 430 requests in 15 minutes; windows of 79 in 60 s passed) and from the
  rate-limit handling below, not from the planned numbers. Before anything starts, every run's model id is looked up in `harness/model-ids.json`, the checked list, and
  a run whose id is not there is refused by name. Each client's launch is written
  once, in `$G/night-$N/launch/<client>.json`, with the launcher's own pid before any run starts and each run's pid
  as it starts; a second go of the same client for the same night is refused. `--go all` starts both, and refuses if
  either was started already.
- **Watching**: `python3 harness/night.py --date $N status` lists each run as `alive` or `ended`, from its process:
  its pid is alive and that process is that run of this launch. It reads `ps` in the C locale and compares start
  times as times, so it gives the same answer from any shell, whatever its language, and for a launch file written
  from a shell in another language (`Mon 23 Nov 13:02:41 2026` and `Mon Nov 23 13:02:41 2026` are one start). How a run ended is in its results file
  (`results/own-clients-$N/<id>.jsonl`), and its console output in `results/own-clients-$N/logs/<id>.log`.
- **Stopping**: `python3 harness/night.py --date $N stop <client>` (or `stop all`) first sets the client's stop mark
  (`$G/night-$N/launch/<client>.stop`). **The mark is the authority**: a launcher starts no run after it, and every
  run looks for it immediately before each client invocation (its status, its version, each priming and check) and
  exits without calling the client once it is there. Before its first client call a run also waits up to 5 seconds
  for its own pid to be in the launch file, and exits if it is not (a launcher stopped between starting it and
  recording it). **Signals are only the fast path**: `stop` then signals the pids the launch file records, each
  checked first: the launcher (its start time and command line as it recorded them) and each recorded run that is
  alive and is that run (its recorded start time, its command line with its label and the launch file's launch id).
  Only those pids, never a process group, and never a process the launch file does not record, so nothing of another
  night, another `$G` or another program is touched. A signalled run ends the client invocation it has under way. It
  says, per client: `stop mark set; <n> recorded processes signalled; a run not yet recorded stops before its next
  client call` (or `not launched` when there is no launch file). It needs `GROUNDTRUTH_CLIENT_HOME` set as for the
  night (it refuses without it), and it refuses, writing nothing, when the marks' folder would be an everyday client
  folder (`~/.codex`, …), a synced folder, the repository or a checkout. Nothing more of that client starts that
  night. `--dry-run stop all` names them and does nothing. A run also stops by itself on a quota refusal (a plan's
  limit, or three of Devin's rate-limit refusals in a row), on five failed requests in a row of any kind (`failing`),
  on two missed controls (a cold control gets one more, in a fresh session) or on a control that would be late (it
  is not sent: `control-late`). A check that fails is lost and its session never resumed; a priming that
  fails is tried again in a new session (a `retry` line).

### The smoke review (step 3)

`--go smoke` runs S2 (Codex), S3 and S3b (Devin), one after the other, then checks them; `smoke-reviewed` checks them
again and refuses to mark them while a check fails. The automatic checks, for each run: a first line with the
isolation and no client version (a public result never carries one: it is in the console log and in
`$G/private-runs/`); exactly one check, the control (two when the first was cold: its second chance, in a fresh
session, noted), made in time (not late), of a single model request and naming the model that answered; no failed,
invalid, refused or retried request; the last line `done` with the last control warm. S3b asks whether Devin still reports no cached token for `gpt-6-1-terra`: a cold control there, ending
`stop`/`no-observable-cache`, is the expected answer and is noted, not refused. A late control is refused everywhere,
and so is a check whose answering model is not certain (`check-invalid`, `no-model`, `ambiguous-model` or
`other-model`). For Codex a check counts only when its session file shows exactly one new turn for that invocation,
with a model record carrying that turn's id, naming the requested model, and no other model record since the
invocation began. If S2 shows `no-model` or `ambiguous-model`, the Codex runs would measure nothing: hand it to whoever
maintains `harness/clients.py`. Codex runs also read each session's whole file after every check and at the end
(`model-scan` lines): any model but the requested one anywhere stops the run (`stop`, `other-model`) and excludes it.

Then read, by hand. The results are in `results/own-clients-$N/smoke/`; each invocation's raw output, redacted, is in
`$G/night-$N/raw/<id>/` (mode 700, files 600), never in the repository. If an item fails, do not run
`smoke-reviewed`: hand the run's file and its raw folder to whoever maintains `harness/clients.py`.

- [ ] `--go smoke` ended with "the smoke results pass the automatic checks".
- [ ] Each file's first line shows `"confinement": "sandbox-exec: …"`.
- [ ] `S2.jsonl`'s first line shows `model_provider="openai"` in both commands and no `"client_version"`; its check's
      `"usage"` has `"model_matches": true` and `"model_evidence": "own-turn"`; its last `model-scan` line has
      `"final": true`, `"other_models": 0` and `"unreadable": false`.
- [ ] `S3.jsonl`'s first line shows `"process_model": "in-process"` and `"keepalive_max_pings": 0` under `"devin"`.
- [ ] `ls -A "$G"/home/*` shows what each client wrote in its throwaway home. Note anything there for the
      maintainer; it needs no action.
- [ ] `git status --short` lists nothing outside `results/own-clients-$N/`, and both scans end with `CLEAN`:
      `python3 harness/scan_secrets.py --own-clients --git .` and
      `python3 harness/scan_secrets.py --own-clients results/own-clients-$N`. With `--own-clients` the scan opens no
      proxy or Pi file (the night uses neither). It reads the files a commit could take (the first) and the night's
      results with every console log under `logs/` (the second), and looks in them for the key variables of the shell,
      for any value whose fingerprint `~/.groundtruth/fingerprints.json` holds (a hash, a length and the first six
      characters, never the value; the first night records none of its own), and for token shapes, e-mail addresses,
      home-folder and state-folder paths, and the clients' login and session files by name.
- [ ] `python3 harness/night.py --date $N untouched --report` lists no Keychain item added or changed by Codex or
      Devin since the logins.

## Re-running some runs

Runs that stopped early (a rate limit taken for quota, one cold control, an unknown model id: the first night's 17)
are run again by their ids, on a **new date folder**, with nothing else changed: the same logins in `$G`, the same
isolation and sandbox, the same smoke rules. The new date is a new night: its own snapshot, smoke runs and review,
then the go with the list. Start it once the night before has ended (`status` of that night shows no run `alive`):
the schedule is planned for the runs of one night only.

```bash
export GROUNDTRUTH_CLIENT_HOME="$HOME/groundtruth-clients" N=<the new YYYY-MM-DD>
python3 harness/night.py --date $N untouched --save              # step 1 of that date; no new login
python3 harness/night.py --date $N --dry-run CX1,CX3,DV1          # the plan: checks, ids, each run's end, requests
python3 harness/night.py --date $N --go smoke                     # then the smoke review and `smoke-reviewed`
python3 harness/night.py --date $N --go CX1,CX3,DV1               # those runs only, in the background
```

- The list is comma-separated run ids of the clients' runs (`CX1` – `CX6`, `DV1` – `DV18`, `DV9d`); a client's name
  takes all its runs (`--go devin,CX1`). Smoke ids are refused: the smoke runs go with `--go smoke`.
- Each client of the list gets its launch file, `$G/night-$N/launch/<client>.json`, recording only the listed runs;
  `status` and `stop` work on them as on a whole night. A client already launched that date is refused, as always.
- A run that has results on that date already (`results/own-clients-$N/<id>.jsonl`) is refused: a re-run never
  appends to an earlier file.
- The runs start in the list's order at their planned offsets (Codex 15 s apart; Devin at least 20 s apart, under
  its limits), as `--dry-run` shows them.

## The morning

1. `python3 harness/night.py --date $N status`: no run is `alive`. Wait if one is: the longest Codex and Devin runs
   end about 12 h 30 after the go.
2. The morning report: `python3 harness/night.py --date $N untouched --report` writes
   `$G/night-$N/everyday-report-<time>.txt` and summarises it. A file your tools remove while it walks is named in
   the report, not an error. A person reads it. Changes from the owner's own use (Codex refreshing
   `~/.codex/auth.json`, his agents' sessions) are expected. A change in a folder none of his tools used is a question
   for whoever maintains `harness/clients.py`, with the report.
3. **The audit, before anything is built.** Nothing of the night enters `observed.json` until a person has audited
   its raw results by hand. The code's checks are a first filter; the audit is what decides publication. The builder
   refuses every run of the night until `results/own-clients-$N/AUDIT.md` exists and its first line is exactly
   `# Own-client night audit: passed`; nothing of the night's folder can be committed before it either (the commit
   hook and CI refuse any file under `results/own-clients-*` without it, and any symbolic link there), and not even
   an `excluded` entry of the night is published without it. Write that line only when every item below is checked
   for every run; list in it the runs that fail an item, and put them under `excluded` with the reason. If anything
   private reached a `*.jsonl` file, write no `AUDIT.md`: nothing of the night is committed.
4. The build (whoever maintains the results), after the audit:
   - give the new folder under `results/` its README;
   - put the runs in `observed/manifest.json`, with the runs that ended early, measured nothing or failed an audit
     item under `excluded` with the reason;
   - run `python3 scripts/build_observed.py`, then `python3 scripts/build_observed.py --check`. The builder refuses a
     check that was not one explicit model request, or whose own turn did not name the requested model
     (`model_matches` not true), or whose line still carries a model's text, or a run whose model is not the
     manifest's, or (Codex) whose model is not bound to its own turn (`model_evidence` `own-turn`), and a Codex
     run whose session files named another model anywhere (`model-scan`), and the whole of a run with samples but no
     valid warm control (warm, not late, not `check-invalid`), naming why; it publishes no client version for an own
     client, and nothing of a night without its `AUDIT.md`.

### The audit checklist

The auditor reads, on this computer, from the repository's root with `G` and `N` set as for the night. The session
files and console logs stay where they are: nothing of them is copied into the repository or quoted in `AUDIT.md`.

**A. The raw results** (`results/own-clients-$N/*.jsonl` and `smoke/*.jsonl`, the files that would be committed).
- [ ] Every run has a file, and `python3 harness/night.py --date $N status` shows no run `alive`.
- [ ] Read every line of every file. Nothing in them but the harness's own fields: no client version, no folder or
      home path, no e-mail address, account, organisation or workspace name, no key or token, no client text in an
      error event (an error is only a kind: `timeout`, `exit-nonzero`, …).
- [ ] Every public line was written by one allowlist (`probe.Public`): numbers, booleans, and strings only of a fixed
      set (event names, reasons, error kinds) or of the run's plan (its start line, its age labels). No model name a
      client reported, no session id, no free text: a session is named by its number (`"session": 3`), a reported
      model only by `model_matches`. Every `check`'s `usage` has `"model_matches": true` (the client reported the
      run's model: Devin's model id, or it with its effort or date suffix; Codex's exactly) and no `"model"`; every
      Codex `check` has `"model_evidence": "own-turn"`. What was left out is in the console log
      (`detail: … kept private`).
- [ ] Every Codex run ends with a `model-scan` line with `"final": true`, `"other_models": 0` and
      `"unreadable": false`, and no line of it is `stop` with `other-model` or `unreadable-session`. (A `model-scan`
      line carries no text from any session file: only `final`, the count `other_models` and `unreadable`. The names
      themselves are in the run's console log only, on a `detail: model-scan:` line, for this audit.)
- [ ] The `check-invalid`, `check-failed`, `retry` and `stop` lines are understood, and every `check` whose `realAgeSec` and
      `monoAgeSec` differ by more than 5 is `late`; a run whose checks are mostly
      invalid goes under `excluded` with the reason.

**B. Codex's session files, for reroutes** (`$G/codex-cli/sessions/`, private: read here, never copied).
- [ ] For each Codex run, take its session ids from its console log (`detail: session <n>: <id>`, one line per
      session, the baseline's first; the public lines name them by `<n>` alone), find each file
      (`ls "$G"/codex-cli/sessions/*/*/*/rollout-*-<id>.jsonl`), and list every model it names:
      `grep -hoE '"(model|to_model|from_model)": ?"[^"]*"' <files> | sort | uniq -c`. Only the run's model may appear.
- [ ] `grep -l model_reroute <files>` finds nothing. A run with any reroute, or any other model, is excluded whole.
- [ ] A Codex run whose files cannot all be found is excluded.

**C. The console logs and private records, for anything private** (`results/own-clients-$N/logs/*.log`, mode 600,
and `$G/private-runs/*.json`, mode 600: never committed).
- [ ] `git check-ignore -q results/own-clients-$N/logs/x.log` succeeds (the logs cannot be committed), and
      `git status --short` lists nothing but the night's `*.jsonl` files and the files you write.
- [ ] Read every log. Note anything private (paths outside `<folder>`/`<home>`, account or workspace names, e-mail
      addresses, keys, tokens). The logs stay private either way; anything private there that also appears in a
      `*.jsonl` file fails item A.
- [ ] Each run's client version is in its log (`detail: client version: …`) and its private record. If the README
      names a version, write only the version number, by hand.

**D. The scans and the everyday report.**
- [ ] `python3 harness/scan_secrets.py --own-clients --git .` and
      `python3 harness/scan_secrets.py --own-clients results/own-clients-$N` both end with `CLEAN`.
- [ ] The morning report (step 2) is read, and nothing in it points at the night.

**E. The file.** `results/own-clients-$N/AUDIT.md`: the first line exactly `# Own-client night audit: passed`, then the
date, who audited, the runs excluded and why, and one line per item A to D saying it was checked. No path, name or
client text in it.
