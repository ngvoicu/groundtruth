# Measuring through the own clients: the steps

The first night of [`own-clients.md`](own-clients.md), section 4, cut down to **the own clients' cache runs only**
(the chief's decision of 2026-11-22): Claude Code, Codex CLI, Devin CLI and Muse Code, each through its own
subscription login. There is no pi run and no Provimux in it (the parity pairs come in a later night), no OpenRouter
run and no window request, no input-limit walk and no Antigravity run. `harness/night.py` holds every command. Every
command takes `--dry-run`, which says what it would do and does nothing else; nothing is sent without `--go`.

There are three parts. **Only the first needs the owner**: his logins and one key, about 15 minutes, once. Anyone can
do the night and the morning from the repository's root on the `own-clients` branch, with no login and no key.

## You, once (about 15 minutes)

These are the only steps that need the owner. Do them in this order, in one terminal, from the repository's root.

**What the night does to keep apart from your own use of the computer**, and what it does not:

- Every client process it starts gets its own folders under `$G`: its state folder (`$G/claude-code` and so on) and
  a throwaway home folder (`HOME=$G/home/<client>`), and its own temporary folder (`TMPDIR=$G/tmp/<client>`). It gets
  only `PATH`, `USER`, `LANG` and `TERM` from your shell, never its `TMPDIR`, a key, a proxy or a base URL.
- On a Mac, every client process runs under `sandbox-exec` with a profile that refuses any file write under your
  home folder except in that client's state folder, its throwaway home and its temporary folder. That covers files
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

So you can use your computer and your tools as usual during the night, Claude Code, Codex, the Devin CLI and Muse
Code included.

**What it costs the accounts.** The night uses the Claude subscription, the ChatGPT plan used with Codex, the Devin
subscription and the Muse Code subscription, each through its own client. A login's quota is the account's own:
start when the plans' meters are low.

**Claude in paid overage.** When the Claude account has used its plan's included usage and paid overage is on, every
further Claude request is billed as paid usage, and Claude Code then writes the 5-minute cache. The night refuses that:
the smoke run S1, and every Claude run, stops at its first cache write if that write is the 5-minute tier, and
`--go claude` (or `--go all`) starts no Claude run after S1 showed it. The 5-minute runs CC5 – CC8 cannot see overage
in their own writes, so they do not start when one of CC1 – CC4 stopped for it. Only `--allow-overage` (on `--go smoke`
and `--go claude`/`--go all`) runs Claude in overage anyway, and then **the runs use paid usage**: up to about 500 Claude
requests over the night.

**Devin's account history.** About 820 Devin sessions from the night will appear in the owner's Devin account
history. Each one's first line is `groundtruth cache measurement <salt> (an automated test, not a task).` (the Devin
CLI cannot name a session). Nothing deletes them.

**1. The folders and the snapshot, before any login** (1 minute). `$G` must be a local folder, outside the
repository, any Git checkout, every client's own folders and every synced folder.

```bash
export GROUNDTRUTH_CLIENT_HOME="$HOME/groundtruth-clients"
export N=<YYYY-MM-DD>                                   # the night's date
G="$GROUNDTRUTH_CLIENT_HOME"
mkdir -m 700 "$G" "$G/claude-code" "$G/codex-cli" "$G/devin-cli" "$G/muse-code"
python3 harness/night.py --date $N untouched --save
```

It checks the folders (local, mode 700, no link that leaves them), makes each client's throwaway home
(`$G/home/claude-code` and so on, mode 700), and records the snapshot described above in
`$G/night-$N/everyday-before.json` (mode 600).

**2. The three logins** (about 2 minutes each; a browser window opens for each), after step 1. Each runs the
client's own login command with exactly the folders, the throwaway home, the temporary folder and the sandbox its runs
will have. It says `done` only when the client's login file is in its state folder (non-empty; then set to mode 600)
and the client's own status command, in the same folders, shows the subscription login; otherwise it says what is
missing, and the login is not done.

```bash
python3 harness/night.py --date $N login claude     # the Claude subscription's account, not the Console
python3 harness/night.py --date $N login codex      # the ChatGPT plan's account
python3 harness/night.py --date $N login devin      # the Devin account
```

Claude Code finds no Keychain under its throwaway home, and keeps this login in the file
`$G/claude-code/.credentials.json`. Codex is told to keep its login in a file (`$G/codex-cli/auth.json`) and to use
its built-in ChatGPT provider (`model_provider="openai"`); every Codex run says the same on its command line, and a
`$G/codex-cli/config.toml` that selects another provider, a profile or another base URL is refused. Before every run
the night checks each login's status, with the same folders, and refuses an API key or the Console; a Claude run is
refused too when `$G/claude-code/.credentials.json` is missing or empty. Never run
`claude setup-token` or `devin auth logout`, and never copy an everyday login file.

**3. Muse Code's key** (1 minute). Type it at `security`'s prompt, so that it never lands in the shell's history.

```bash
security add-generic-password -a "$USER" -s "groundtruth META_API_KEY" -w        # the Muse Code subscription key
```

It is read only when the Muse runs start, straight into them, and never printed or written.

**4. A look at the report** (1 minute).

```bash
python3 harness/night.py --date $N untouched --report
```

It lists what changed since step 1, folder by folder, and the Keychain's items by name; every line is in the file it
names, under `$G/night-$N/` (mode 600). The `groundtruth META_API_KEY` item appears as added. Changes your own tools
made meanwhile may appear too, and that is expected. One thing should not appear: an item `Claude
Code-credentials-…` added or changed after step 2. It would mean Claude Code's login reached your Keychain; then stop
and hand the report to whoever maintains `harness/clients.py`.

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
| 2 | `python3 harness/night.py --date $N --go smoke` | about 10 min, in the foreground |
| 3 | The smoke review (below), then `python3 harness/night.py --date $N smoke-reviewed` | 10 min |
| 4 | `python3 harness/night.py --date $N --go all` (or one client at a time: `--go claude`, `--go codex`, `--go devin`, `--go muse`) | returns at once; the runs take about 12 h 30 |

- **`--go <client>`** starts each of that client's runs as its own background process and returns; closing the
  terminal ends none of them. The starts are staggered (15 s apart, Devin's 20 s); CC5 – CC8 begin 2 h 30 min after
  the go, when CC1 – CC4 are over. Each client's launch is written once, in `$G/night-$N/launch/<client>.json`; a
  second go of the same client for the same night is refused. `--go all` starts the four, and refuses if any of them
  was started already.
- **Watching**: `python3 harness/night.py --date $N status` lists each run as `alive` or `ended`, from its process:
  its pid is alive and that process is that run of this launch. How a run ended is in its results file
  (`results/own-clients-$N/<id>.jsonl`), and its console output in `results/own-clients-$N/logs/<id>.log`.
- **Stopping**: `python3 harness/night.py --date $N stop <client>` (or `stop all`) signals exactly that client's runs
  that are alive: those its launch file records, and any process carrying its launch's id (a run left by an
  interrupted `--go`). `--dry-run stop all` names them and signals nothing. A run also stops by itself on a quota
  refusal, a missed or late control, or (Claude) paid overage or a change of cache lifetime.

### The smoke review (step 3)

`--go smoke` runs S1 (Claude), S2 (Codex), S3 and S3b (Devin) and S4 (Muse), one after the other, then checks them;
`smoke-reviewed` checks them again and refuses to mark them while a check fails. The automatic checks, for each run:
a first line with the client's version and the isolation; exactly one check, the control, made in time (not late) and
of a single model request; no failed, invalid, refused or retried request; the last line `done` with the control warm.
S3b asks whether Devin still reports no cached token for `gpt-6-1-terra`: a cold control there, ending
`stop`/`no-observable-cache`, is the expected answer and is noted, not refused. A late control is refused everywhere.
S1 ending `stop`/`overage` is noted, not refused: the account is in paid overage, and the Claude runs then wait for
`--allow-overage` (see "Claude in paid overage").

Then read, by hand. The results are in `results/own-clients-$N/smoke/`; each invocation's raw output, redacted, is in
`$G/night-$N/raw/<id>/` (mode 700, files 600), never in the repository. If an item fails, do not run
`smoke-reviewed`: hand the run's file and its raw folder to whoever maintains `harness/clients.py`.

- [ ] `--go smoke` ended with "the smoke results pass the automatic checks".
- [ ] Each file's first line shows `"confinement": "sandbox-exec: …"`.
- [ ] `S1.jsonl`'s first line shows `"CLAUDE_CODE_MAX_RETRIES": "0"` under `"client_settings"`.
- [ ] `S2.jsonl`'s first line shows `model_provider="openai"` in both commands, and its check's `"usage"` has a
      `"model"`.
- [ ] `S3.jsonl`'s first line shows `"process_model": "in-process"` and `"keepalive_max_pings": 0` under `"devin"`.
- [ ] `ls -A "$G"/home/*` shows what each client wrote in its throwaway home. Note anything there for the
      maintainer; it needs no action.
- [ ] `git status --short` lists nothing outside `results/own-clients-$N/`, and both scans end with `CLEAN`:
      `python3 harness/scan_secrets.py --own-clients --git .` and
      `python3 harness/scan_secrets.py --own-clients results/own-clients-$N`. With `--own-clients` the scan opens no
      proxy or pi file (the night uses neither). It reads the files a commit could take (the first) and the night's
      results with every console log under `logs/` (the second), and looks in them for the key variables of the shell,
      for Muse Code's key by the fingerprint the night recorded when it read the Keychain item `groundtruth
      META_API_KEY` (in `~/.groundtruth/fingerprints.json`: a hash, a length and the first six characters, never the
      key), and for token shapes, e-mail addresses, home-folder and state-folder paths, and the clients' login and
      session files by name.
- [ ] `python3 harness/night.py --date $N untouched --report` lists no Keychain item `Claude Code-credentials-…` as
      added or changed since the logins.

## The morning

1. `python3 harness/night.py --date $N status`: no run is `alive`. Wait if one is: the longest Codex and Devin runs
   end about 12 h 30 after the go.
2. The morning report: `python3 harness/night.py --date $N untouched --report` writes
   `$G/night-$N/everyday-report-<time>.txt` and summarises it. A file your tools remove while it walks is named in
   the report, not an error. A person reads it. Changes from the owner's own use (Codex refreshing
   `~/.codex/auth.json`, his agents' sessions) are expected. A `Claude Code-credentials-…` Keychain item, or a change
   in a folder none of his tools used, is a question for whoever maintains `harness/clients.py`, with the report.
3. The build (whoever maintains the results):
   - give the new folder under `results/` its README;
   - put the runs in `observed/manifest.json`, with the runs that ended early or measured nothing under `excluded`
     with the reason;
   - run `python3 scripts/build_observed.py`, then `python3 scripts/build_observed.py --check`.
