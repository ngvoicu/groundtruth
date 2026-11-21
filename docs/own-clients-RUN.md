# Measuring through the own clients: the owner's steps

What the owner does to run the first night of [`own-clients.md`](own-clients.md), section 4, narrowed: no input
limit through an own client, no Antigravity run; with the pairs of Provimux's `client-parity.md`, section 7 (each
pair is an own-client run and a pi-through-Provimux run started beside it). Everything runs from the repository's
root on the `own-clients` branch. `harness/night.py` holds every command; `--dry-run` shows them and sends nothing.
Nothing is sent without `--go`.

## Accounts

| Runs | Account | Credential |
|---|---|---|
| OR1 – OR5, OW1 – OW9 | OpenRouter | a key made for this campaign, limit 5 USD; `night.py` starts nothing that could pass 4 USD |
| S1, CC1 – CC8 | the Claude subscription (Pro/Max) | the login in the `claude-code` state folder |
| S2, CX1 – CX6 | the ChatGPT plan used with Codex | the login in the `codex-cli` state folder |
| S3, S3b, DV1 – DV17, DV9d | the Devin subscription | the login in the `devin-cli` state folder |
| S4, MC1 – MC3 | the Muse Code subscription | its key, in the Keychain |
| SP, P-CC3, P-CC4, P-CX1, P-CX3, P-CX4, P-DV1, P-DV5, P-DV9, P-DV11, P-DV14, P-MC1, P-MC1b | the same logins, through the owner's Provimux | pi in the `pi-provimux` state folder, with Provimux's key |
| CXS-a | the ChatGPT plan, through Provimux | Provimux's key, in the Keychain |
| — | Antigravity | none |

A login's quota is the account's: the night and the owner's own work draw on the same allowance. Start when the
plans' meters are low; for Claude Code this matters twice, because in overage it writes the 5-minute cache and the
run stops (`tier-changed`) and is not published.

**Devin's account history.** The night's Devin sessions will appear in the owner's Devin account history (accepted
by the owner on 2026-11-22): those of the Devin CLI, and possibly those of pi through Provimux, about 1,700 sessions
(about 90 per run). The Devin CLI (3000.14) has no option to set a session's title or name, so every session's first
line is the label: `groundtruth cache measurement <salt> (an automated test, not a task).` It tells them apart from
the owner's work. Nothing here deletes them.

**From step 1 to the end of the night, nobody uses Claude Code, Codex, the Devin CLI, Muse Code or pi on this
computer** (no agent either): the everyday folders and the Keychain are compared with step 1's snapshot before every
`--go` and at the end, and any difference stops the night.

## Once: the state folders, the snapshot, the logins

**1. The folders and the snapshot, before any login.** A folder outside the repository, outside every Git checkout
and outside every client's own folders (not under `~/.claude`, `~/.codex`, `~/.devin`, `~/.pi`, `~/.config`,
`~/.local`, `~/Library`), used for nothing else. The probe refuses anything else, and a state folder with a link
that leaves it.

```bash
export GROUNDTRUTH_CLIENT_HOME="$HOME/groundtruth-clients"
G="$GROUNDTRUTH_CLIENT_HOME"
mkdir -p "$G/claude-code" "$G/codex-cli" "$G/devin-cli" "$G/muse-code" "$G/pi-provimux"
export N=<YYYY-MM-DD>                                   # the night's date: names the results folders
python3 harness/night.py --date $N untouched --save     # before the logins: the everyday folders and the Keychain
```

The snapshot (in `$G/night-$N/`, never in the repository) records the path, size and modification time of every
file under the everyday folders, and the Keychain's items by name and service, never a secret. Seconds.

**2. The logins**, each with a short environment, as the probe runs the client: no API key, base URL or proxy of the
shell reaches it. About 2 minutes each.

Claude Code (a browser window opens; sign in with the Claude subscription's account, not the Console). Another
`CLAUDE_CONFIG_DIR` is another Keychain entry: the everyday login is not touched. Never `claude setup-token`: no
long-lived token is stored.

```bash
env -i PATH="$PATH" HOME="$HOME" USER="$USER" LANG="$LANG" TERM="$TERM" TMPDIR="$TMPDIR" \
    CLAUDE_CONFIG_DIR="$G/claude-code" DISABLE_AUTOUPDATER=1 claude auth login --claudeai
env -i PATH="$PATH" HOME="$HOME" USER="$USER" CLAUDE_CONFIG_DIR="$G/claude-code" claude auth status --json
```

The status must show `"authMethod": "claude.ai"` (or `oauth`); the probe refuses an API key or the Console.

Codex CLI (sign in with the ChatGPT plan's account; never `--with-api-key`). The login becomes a file in the state
folder; never copy the everyday `auth.json`.

```bash
env -i PATH="$PATH" HOME="$HOME" USER="$USER" LANG="$LANG" TERM="$TERM" TMPDIR="$TMPDIR" \
    CODEX_HOME="$G/codex-cli" codex login -c cli_auth_credentials_store="file"
env -i PATH="$PATH" HOME="$HOME" USER="$USER" CODEX_HOME="$G/codex-cli" \
    codex login status -c cli_auth_credentials_store="file"
```

The status must say `Logged in using ChatGPT`; the probe refuses an API key.

Devin CLI (sign in with the Devin account). Never `devin auth logout`, in any environment.

```bash
D="$G/devin-cli"
env -i PATH="$PATH" HOME="$HOME" USER="$USER" LANG="$LANG" TERM="$TERM" TMPDIR="$TMPDIR" \
    XDG_CONFIG_HOME="$D/config" XDG_DATA_HOME="$D/data" XDG_STATE_HOME="$D/state" XDG_CACHE_HOME="$D/cache" \
    DEVIN_SESSIONS_DIR="$D/sessions" devin auth --process-model in-process login
env -i PATH="$PATH" HOME="$HOME" USER="$USER" XDG_CONFIG_HOME="$D/config" XDG_DATA_HOME="$D/data" \
    XDG_STATE_HOME="$D/state" XDG_CACHE_HOME="$D/cache" DEVIN_SESSIONS_DIR="$D/sessions" \
    devin auth --process-model in-process status
```

pi, in its own folder: set it up with pi's own commands as the everyday pi is set up (the pi-provimux extension and
Provimux's key), with `PI_CODING_AGENT_DIR="$G/pi-provimux"` in front of each; never copy `~/.pi`. Then write
`$G/pi-provimux/payload-rules.json`: the payload rules of Provimux's configuration that touch these requests, as a
JSON list (`[]` for none); for the first part of the night, the Meta 24 h rule switched off (step 8). And name the
pi-provimux checkout pi loads, for the run's record:

```bash
export PI_PROVIMUX_DIR=<the pi-provimux checkout>
```

Keys, each typed at `security`'s prompt (in no shell history); the night reads them only into the one process
that needs them:

```bash
security add-generic-password -a "$USER" -s "groundtruth META_API_KEY" -w        # the Muse Code subscription key
security add-generic-password -a "$USER" -s "groundtruth OPENROUTER_API_KEY" -w  # the campaign's OpenRouter key (limit 5 USD)
security add-generic-password -a "$USER" -s "groundtruth PROVIMUX_KEY" -w        # Provimux's key, for CXS-a
```

**3. After the logins.**

```bash
python3 harness/night.py --date $N untouched --compare
```

It should list only Keychain items that the logins added (Claude Code's entry for its state folder, the three
groundtruth items). If it lists anything else, stop: a login wrote outside its state folder. If not, accept them
as the night's own and compare again; it must print `unchanged`:

```bash
python3 harness/night.py --date $N untouched --accept-keychain-added
python3 harness/night.py --date $N untouched --compare
```

## The night, in order

Every command starts from the repository's root, with `GROUNDTRUTH_CLIENT_HOME`, `N` and `PI_PROVIMUX_DIR` exported.
Keep the computer on power and on the network. A check made more than `age × 1.1 + 90 s` after its priming is left
out, so a sleeping computer loses checks, not truth. Logs and pids are in `results/<folder>/logs/` (never
committed). Each `--go` first compares the everyday folders and the Keychain with the snapshot and stops on any
difference; a step already done or running is skipped, so a `--go` can be repeated.

| # | Command | Account | Wall time |
|---|---|---|---|
| 4 | `python3 harness/night.py --date $N --dry-run all` | none: sends nothing | 1 min |
| 5 | `python3 harness/night.py --date $N --go smoke` | Claude, ChatGPT, Devin, Muse, and pi through Provimux | about 2 min per run, one after the other: about 12 min, in the foreground |
| 6 | Read the smoke results (below); then `python3 harness/night.py --date $N smoke-reviewed` | none | 10 – 20 min |
| 7 | `python3 harness/night.py --date $N --go openrouter` then `--go windows` | OpenRouter key | 2 h 15 in the background (about 1.60 USD); the windows about 10 min in the foreground (refused, not billed) |
| 8 | With Provimux's Meta 24 h rule switched off and `payload-rules.json` saying so: `python3 harness/night.py --date $N --go claude codex codex-plain devin muse` (add `devin-terra-pi` only if S3b showed cached tokens) | Claude, ChatGPT, Devin, Muse, Provimux | about 13 min of launches (15 s apart, Devin 20 s); then in the background: Claude 2 h 20, Codex 12 h 20, CXS-a 35 min, Devin 2 h 20 (std) and 12 h 20 (DV8, DV10, DV11), Muse 2 h 20 (minutes where a control misses) |
| 9 | When CC1 – CC4 have ended (about 2 h 20 after step 8): `python3 harness/night.py --date $N --go claude-5m` | Claude | 35 min |
| 10 | When MC1 and P-MC1 have ended: switch the Meta 24 h rule back on, write it into `payload-rules.json`, then `python3 harness/night.py --date $N --go muse-rule` | Muse, through Provimux | 2 h 20 |
| 11 | When everything has ended: `python3 harness/night.py --date $N untouched --compare` | none | seconds |

A run has ended when the last line of its `.jsonl` is `{"event": "done", …}` or `{"event": "stop", …}` (for
OR1 – OR5 and CXS-a: its `.json` result file exists). The cache runs end about 12 h 30 after step 8.

**Step 6, the smoke results.** `results/own-clients-$N/smoke/` holds S1, S2, S3, S3b, S4 and SP (`.jsonl`); the
redacted raw output of every invocation is in `$G/night-$N/raw/<id>/` (never in the repository):

- each run ends with `{"event": "done"}` after one warm `check` of the control with `"calls": 1`; the launcher
  stops by itself when one does not, and says which;
- S3b (Devin, gpt-6-1-terra): whether its replies report any cached token; if not, DV5 measures nothing and is
  excluded, and `devin-terra-pi` is not run;
- SP: its start event shows `pi` with the Provimux build, pi's version, pi-provimux's commit and the payload rules;
- if a client printed something other than the fixtures under `test/fixtures/clients/` expect, the fixtures and
  `harness/clients.py` are corrected from the raw output before step 8.

**Stopping.** A run stops itself on a quota refusal, on a missed or late control, or (Claude) on a change of
lifetime. To stop one by hand: `python3 harness/night.py --date $N stop <id>` (it finds the run's pid file in its
own folder and signals the process group only if it is that run).

**After the night** (not the owner's): each folder gets its README, its runs go in `observed/manifest.json` (runs
that ended early or measured nothing in `excluded`, with the reason), and `observed.json` is rebuilt. The pairs are
read by the rule of `client-parity.md`, section 6, decided before the runs.
