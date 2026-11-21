# Measuring through the own clients: the steps

The first night of [`own-clients.md`](own-clients.md), section 4, narrowed: no input limit through an own client, no
Antigravity run. It includes the pairs of Provimux's `client-parity.md`, section 7: each pair is an own-client run and
a pi-through-Provimux run started beside it. `harness/night.py` holds every command. `--dry-run` shows them and sends
nothing, and nothing is sent without `--go`.

There are three parts. **Only the first needs the owner**: his logins and his keys, about 15 minutes, once. Anyone can
do the night and the morning from the repository's root on the `own-clients` branch, with no login and no key.

## You, once (about 15 minutes)

These are the only steps that need the owner. Do them in this order, in one terminal, from the repository's root.

**From step 1 until the morning, nobody uses Claude Code, Codex, the Devin CLI, Muse Code or pi on this computer**,
and no agent does either. Before every launch the night compares the everyday folders and the Keychain with step 1's
snapshot, and any difference stops it.

**What it costs the accounts.** The night uses the Claude subscription, the ChatGPT plan used with Codex, the Devin
subscription and the Muse Code subscription, directly and through Provimux. It also uses an OpenRouter key made for
the campaign, with a 5 USD limit; the night starts nothing that could take it past 4 USD. A login's quota is the
account's own: start when the plans' meters are low. For Claude this matters twice, because in overage Claude Code
writes the 5-minute cache and the run stops.

**Devin's account history.** About 1,700 Devin sessions from the night will appear in the owner's Devin account
history. Each one's first line is `groundtruth cache measurement <salt> (an automated test, not a task).` (the Devin
CLI cannot name a session). Nothing deletes them.

**1. The folders and the snapshot, before any login** (1 minute). The folders must lie outside the repository, any
Git checkout and every client's own folders.

```bash
export GROUNDTRUTH_CLIENT_HOME="$HOME/groundtruth-clients"
export N=<YYYY-MM-DD>                                   # the night's date
G="$GROUNDTRUTH_CLIENT_HOME"
mkdir -p "$G/claude-code" "$G/codex-cli" "$G/devin-cli" "$G/muse-code" "$G/pi-provimux"
python3 harness/night.py --date $N untouched --save
```

It records the names, sizes and dates of the files in the everyday folders, and the names of the Keychain's items,
never a secret.

**2. The three logins** (about 2 minutes each; a browser window opens for each). Each one writes only into its own
folder, and the everyday logins are not touched.

Claude Code: sign in with the Claude subscription's account, not the Console.

```bash
env -i PATH="$PATH" HOME="$HOME" USER="$USER" LANG="$LANG" TERM="$TERM" TMPDIR="$TMPDIR" \
    CLAUDE_CONFIG_DIR="$G/claude-code" DISABLE_AUTOUPDATER=1 claude auth login --claudeai
```

Codex: sign in with the ChatGPT plan's account.

```bash
env -i PATH="$PATH" HOME="$HOME" USER="$USER" LANG="$LANG" TERM="$TERM" TMPDIR="$TMPDIR" \
    CODEX_HOME="$G/codex-cli" codex login -c cli_auth_credentials_store="file"
```

Devin: sign in with the Devin account.

```bash
D="$G/devin-cli"
env -i PATH="$PATH" HOME="$HOME" USER="$USER" LANG="$LANG" TERM="$TERM" TMPDIR="$TMPDIR" \
    XDG_CONFIG_HOME="$D/config" XDG_DATA_HOME="$D/data" XDG_STATE_HOME="$D/state" XDG_CACHE_HOME="$D/cache" \
    DEVIN_SESSIONS_DIR="$D/sessions" devin auth --process-model in-process login
```

The night checks each login's status before every run and refuses an API key or the Console. Never run
`claude setup-token` or `devin auth logout`, and never copy an everyday login file.

**3. The three keys** (1 minute). Type each at `security`'s prompt, so that none lands in the shell's history.

```bash
security add-generic-password -a "$USER" -s "groundtruth META_API_KEY" -w        # the Muse Code subscription key
security add-generic-password -a "$USER" -s "groundtruth OPENROUTER_API_KEY" -w  # the campaign's OpenRouter key (limit 5 USD)
security add-generic-password -a "$USER" -s "groundtruth PROVIMUX_KEY" -w        # Provimux's key
```

**4. The compare** (1 minute).

```bash
python3 harness/night.py --date $N untouched --compare
```

It should list only Keychain items: Claude Code's entry for its own folder and the three `groundtruth` items. If it
lists anything else, stop: a login wrote outside its folder. If it doesn't, accept those items as the night's own and
compare again; the second compare must print `unchanged`:

```bash
python3 harness/night.py --date $N untouched --accept-keychain-added
python3 harness/night.py --date $N untouched --compare
```

The owner's part ends here. Provimux stays as it is: nothing is switched or restarted.

## The night

Anyone can do this, from the repository's root, with these set in the shell:

```bash
export GROUNDTRUTH_CLIENT_HOME="$HOME/groundtruth-clients" N=<YYYY-MM-DD>
export PI_PROVIMUX_DIR=<the pi-provimux checkout>       # the extension pi loads; its commit goes in each pi run's record
```

Keep the computer on power and on the network. A check made too late after its priming is left out, so a sleeping
computer loses checks, not truth.

| # | Command | Time |
|---|---|---|
| 1 | `python3 harness/night.py --date $N pi-setup` | 1 min |
| 2 | `python3 harness/night.py --date $N --dry-run all` | 1 min, sends nothing |
| 3 | `python3 harness/night.py --date $N --go smoke` | about 12 min, in the foreground |
| 4 | The smoke review (below), then `python3 harness/night.py --date $N smoke-reviewed` | 10 – 20 min |
| 5 | `python3 harness/night.py --date $N --go night` | returns at once; the night runs about 12 h 30 |

- **Step 1, pi-setup**, sets up pi's own folder (`$G/pi-provimux`). It uses pi's own `pi install` with the
  pi-provimux checkout, and writes the proxy's address into that folder with no key; the key reaches pi only at the
  go, from the Keychain. It never reads `~/.pi`.
- **Step 5, `--go night`**, checks that the smoke runs were reviewed, that pi's folder is set up and that the everyday
  state is unchanged. Then it starts a supervisor in the background, which keeps running if the terminal is closed.
  The supervisor:
  - launches OpenRouter (OR1 – OR5), Claude (CC1 – CC4), Codex (CX1 – CX6), CX-S, Devin (DV1 – DV17, DV9d) and Muse
    (MC1 – MC3), each with its pi twin, then the OpenRouter window requests;
  - adds DV-6's pi run itself if S3b showed cached tokens;
  - starts CC5 – CC8 by itself once CC1 – CC4 have ended;
  - compares the everyday state again when the last run has ended.

  Before each launch it compares the everyday state, and before each OpenRouter request it checks the money stop. It
  skips what is done, so `--go night` can be repeated safely.
- **Watching**: `python3 harness/night.py --date $N status` lists each run as running, done, failed (with why) or not
  started, with the supervisor's last lines. The full log is `results/own-clients-$N/logs/supervisor.log`.
- **Stopping**: `python3 harness/night.py --date $N stop all` stops the supervisor first, then every run still
  running. `stop <id>` stops a single run. A run also stops by itself on a quota refusal, a missed or late control,
  or (Claude) a change of cache lifetime.

### The smoke review (step 4): a checklist

The smoke results are in `results/own-clients-$N/smoke/`: `S1.jsonl` (Claude), `S2.jsonl` (Codex), `S3.jsonl` and
`S3b.jsonl` (Devin), `S4.jsonl` (Muse) and `SP.jsonl` (pi through Provimux). One JSON event per line. Each
invocation's raw output, redacted, is in `$G/night-$N/raw/<id>/`, never in the repository. Tick every item. If any
item fails, do not run `smoke-reviewed`: hand the run's file and its raw folder to whoever maintains
`harness/clients.py`.

- [ ] `--go smoke` ended without "smoke runs that did not end with `done`".
- [ ] `python3 harness/night.py --date $N status` shows S1, S2, S3, S3b, S4 and SP as `done`.
- [ ] In each of the six files, the last line has `"event": "done"`.
- [ ] Each file has exactly one line with `"event": "check"`, whose `"usage"` shows `"calls": 1` and whose `"warm"` is
      `true`.
- [ ] No file has a line whose `"event"` is `check-invalid`, `check-failed`, `prime-failed`, `prime-refused` or
      `retry`.
- [ ] Each file's first line (`"event": "start"`) has a `"client_version"`.
- [ ] `S1.jsonl`'s first line shows `"CLAUDE_CODE_MAX_RETRIES": "0"` under `"client_settings"`.
- [ ] `S3.jsonl`'s first line shows `"process_model": "in-process"` and `"keepalive_max_pings": 0` under `"devin"`.
- [ ] `SP.jsonl`'s first line has a `"pi"` block with `provimux_build`, `pi_version`, `pi_provimux_commit` and
      `payload_rules`. `payload_rules.section` starts with `payload:` (or is `null` with the note "no payload
      section") and holds no key, password or e-mail.
- [ ] `S3b.jsonl`: note whether any `check` line has `"cached"` above 0. Nothing to do either way: the supervisor reads
      it and runs DV-6's pi run only if so.
- [ ] `git status --short` lists nothing outside `results/own-clients-$N/` and `results/openrouter-direct-$N/`, and
      `python3 harness/scan_secrets.py --git .` ends with `CLEAN`.
- [ ] `python3 harness/night.py --date $N untouched --compare` prints `unchanged`.

## The morning

1. `python3 harness/night.py --date $N status`: the supervisor is not running, and no run is `running`. Wait if one
   is: the longest Codex and Devin runs end about 12 h 30 after the go.
2. The final compare: `python3 harness/night.py --date $N untouched --compare` must print `unchanged`. The supervisor
   made the same compare at the end: see the last lines of `supervisor.log`. If it changed, the comparison says what,
   and the night's results are kept but marked.
3. The build (whoever maintains the results):
   - give each new folder under `results/` its README;
   - put the runs in `observed/manifest.json`, with the runs that ended early or measured nothing under `excluded`
     with the reason;
   - run `python3 scripts/build_observed.py`, then `python3 scripts/build_observed.py --check`.

   The pairs are read by the rule of `client-parity.md`, section 6, decided before the runs.
