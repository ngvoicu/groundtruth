# Measuring through the own clients: the steps

The first night of [`own-clients.md`](own-clients.md), section 4, cut down to **the cache runs of Codex CLI and Devin
CLI only** (the owner's decision of 2026-11-22: the two logins where differences were seen), each through its own
subscription login. Claude Code and Muse Code wait for a later night: no night command runs, logs in or reads a key
for either. There is no pi run and no Provimux in it, no OpenRouter run and no window request, no input-limit walk and
no Antigravity run. `harness/night.py` holds every command. Every command takes `--dry-run`, which says what it would
do and does nothing else; nothing is sent without `--go`.

There are three parts. **Only the first needs the owner**: his two logins, about 7 minutes, once. Anyone can do the
night and the morning from the repository's root on the `own-clients` branch, with no login and no key.

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
subscription (about 1,620 requests), each through its own client. A login's quota is the account's own: start when
the plans' meters are low.

**Devin's account history.** Up to about 820 Devin sessions from the night (819 if every run goes to its end, 4 in
the smoke runs) will appear in the owner's Devin account history: fewer if a control misses (that run ends after its
control), one more for each priming that is tried again. Each one's first line is `groundtruth cache
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
(Codex: `Logged in using ChatGPT`; Devin: `Logged in`, `Logged in as …`) is refused too, whatever its exit code. Never
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
```

Keep the computer on power and on the network. Each run keeps it awake (`caffeinate -i`); a check made too late after
its priming is left out, so a sleeping computer loses checks, not truth.

| # | Command | Time |
|---|---|---|
| 1 | `python3 harness/night.py --date $N --dry-run all` | 1 min, does nothing |
| 2 | `python3 harness/night.py --date $N --go smoke` | about 5 min, in the foreground |
| 3 | The smoke review (below), then `python3 harness/night.py --date $N smoke-reviewed` | 10 min |
| 4 | `python3 harness/night.py --date $N --go all` (or one client at a time: `--go codex`, `--go devin`) | returns at once; the runs take about 12 h 30 |

- **`--go <client>`** starts each of that client's runs as its own background process and returns; closing the
  terminal ends none of them. The starts are staggered (15 s apart, Devin's 20 s). Each client's launch is written
  once, in `$G/night-$N/launch/<client>.json`, with the launcher's own pid before any run starts and each run's pid
  as it starts; a second go of the same client for the same night is refused. `--go all` starts both, and refuses if
  either was started already.
- **Watching**: `python3 harness/night.py --date $N status` lists each run as `alive` or `ended`, from its process:
  its pid is alive and that process is that run of this launch. How a run ended is in its results file
  (`results/own-clients-$N/<id>.jsonl`), and its console output in `results/own-clients-$N/logs/<id>.log`.
- **Stopping**: `python3 harness/night.py --date $N stop <client>` (or `stop all`) first writes the client's stop mark
  (`$G/night-$N/launch/<client>.stop`), before it looks anything up: a launcher starts no run after it, and stops at
  once a run it was just starting. Then it waits (a few seconds at most) for the night's launcher to end, signalling it
  if it does not, and then signals exactly that client's runs that are alive: those its launch file records, and any
  process carrying the night's launch id for that client, launch file or not. It needs `GROUNDTRUTH_CLIENT_HOME` set
  as for the night (it refuses without it). Nothing more of that client starts that night. `--dry-run stop all` names them and does nothing. A
  run also stops by itself on a quota refusal or a missed or late control.

### The smoke review (step 3)

`--go smoke` runs S2 (Codex), S3 and S3b (Devin), one after the other, then checks them; `smoke-reviewed` checks them
again and refuses to mark them while a check fails. The automatic checks, for each run: a first line with the client's
version and the isolation; exactly one check, the control, made in time (not late), of a single model request and
naming the model that answered; no failed, invalid, refused or retried request; the last line `done` with the control
warm. S3b asks whether Devin still reports no cached token for `gpt-6-1-terra`: a cold control there, ending
`stop`/`no-observable-cache`, is the expected answer and is noted, not refused. A late control is refused everywhere,
and so is a check whose answering model is not certain (`check-invalid`, `no-model`, `ambiguous-model` or
`other-model`). For Codex a check counts only when its session file shows exactly one new turn for that invocation,
with a model record carrying that turn's id, naming the requested model, and no other model record since the
invocation began. If S2 shows `no-model` or `ambiguous-model`, the Codex runs would measure nothing: hand it to whoever
maintains `harness/clients.py`.

Then read, by hand. The results are in `results/own-clients-$N/smoke/`; each invocation's raw output, redacted, is in
`$G/night-$N/raw/<id>/` (mode 700, files 600), never in the repository. If an item fails, do not run
`smoke-reviewed`: hand the run's file and its raw folder to whoever maintains `harness/clients.py`.

- [ ] `--go smoke` ended with "the smoke results pass the automatic checks".
- [ ] Each file's first line shows `"confinement": "sandbox-exec: …"`.
- [ ] `S2.jsonl`'s first line shows `model_provider="openai"` in both commands and a `"client_version"` that is a
      version number (`unknown` means the client's `--version` printed something else: note it), and its check's
      `"usage"` has `"model": "gpt-6-luna"` and `"model_evidence": "own-turn"`.
- [ ] `S3.jsonl`'s first line shows `"process_model": "in-process"` and `"keepalive_max_pings": 0` under `"devin"`.
- [ ] `ls -A "$G"/home/*` shows what each client wrote in its throwaway home. Note anything there for the
      maintainer; it needs no action.
- [ ] `git status --short` lists nothing outside `results/own-clients-$N/`, and both scans end with `CLEAN`:
      `python3 harness/scan_secrets.py --own-clients --git .` and
      `python3 harness/scan_secrets.py --own-clients results/own-clients-$N`. With `--own-clients` the scan opens no
      proxy or pi file (the night uses neither). It reads the files a commit could take (the first) and the night's
      results with every console log under `logs/` (the second), and looks in them for the key variables of the shell,
      for any value whose fingerprint `~/.groundtruth/fingerprints.json` holds (a hash, a length and the first six
      characters, never the value; the first night records none of its own), and for token shapes, e-mail addresses,
      home-folder and state-folder paths, and the clients' login and session files by name.
- [ ] `python3 harness/night.py --date $N untouched --report` lists no Keychain item added or changed by Codex or
      Devin since the logins.

## The morning

1. `python3 harness/night.py --date $N status`: no run is `alive`. Wait if one is: the longest Codex and Devin runs
   end about 12 h 30 after the go.
2. The morning report: `python3 harness/night.py --date $N untouched --report` writes
   `$G/night-$N/everyday-report-<time>.txt` and summarises it. A file your tools remove while it walks is named in
   the report, not an error. A person reads it. Changes from the owner's own use (Codex refreshing
   `~/.codex/auth.json`, his agents' sessions) are expected. A change in a folder none of his tools used is a question
   for whoever maintains `harness/clients.py`, with the report.
3. The build (whoever maintains the results):
   - give the new folder under `results/` its README;
   - put the runs in `observed/manifest.json`, with the runs that ended early or measured nothing under `excluded`
     with the reason;
   - run `python3 scripts/build_observed.py`, then `python3 scripts/build_observed.py --check`. The builder refuses a
     check that was not one explicit model request, or that names no model of its own turn, or another model than
     the manifest's, or (Codex) whose model is not bound to its own turn (`model_evidence` `own-turn`); a client
     version is published only as a version number, anything else as `unknown`.
