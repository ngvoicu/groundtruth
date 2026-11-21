# Measuring through the own clients: the owner's steps

What the owner does to run the plan of [`own-clients.md`](own-clients.md), section 4: once, the logins; then, one
night at the owner's go, the commands in order. Everything is run from the repository's root on the `own-clients`
branch. `harness/night.py` holds every command; `--dry-run` shows them and sends nothing:

```bash
python3 harness/night.py --date <YYYY-MM-DD> --dry-run all
```

`<YYYY-MM-DD>` is the night's date; it names `results/own-clients-<date>/` and `results/openrouter-direct-<date>/`.

## Accounts

| Runs | Account | Credential |
|---|---|---|
| OR1 – OR5, OW1 – OW9 | OpenRouter | a key made for this campaign, limit 5 USD; `night.py` starts nothing past 4 USD |
| S1, CC1 – CC8, CL1 – CL4 | the Claude subscription (Pro/Max) | the login in the `claude-code` state folder |
| S2, CX1 – CX6 | the ChatGPT plan used with Codex | the login in the `codex-cli` state folder |
| S3, S3b, DV1 – DV17, DL1 – DL12 | the Devin subscription | the login in the `devin-cli` state folder |
| S4, MC1 – MC3, ML1 – ML3 | the Muse Code subscription | its key, in the Keychain |
| — | Antigravity | none: no own-client run for now (decision 6) |

The quota of a login is the account's: a run and the owner's own work draw on the same allowance. Start the night
when the plans' meters are low; for Claude Code this matters twice, because in overage it writes the 5-minute cache
and the run ends (`tier-changed`).

## Once: a state folder per client, logged in

A folder outside the repository and outside every client's own folders (not `~/.claude`, `~/.codex`, `~/.config`,
`~/.local/share`, `~/.devin`), used for nothing else. The probe refuses anything else, and refuses a folder that is
not logged in.

```bash
export GROUNDTRUTH_CLIENT_HOME="$HOME/groundtruth-clients"
G="$GROUNDTRUTH_CLIENT_HOME"
mkdir -p "$G/claude-code" "$G/codex-cli" "$G/devin-cli" "$G/muse-code"
```

Each login runs with a short environment, as the probe will run the client: no API key, base URL or proxy of the
shell reaches it, so the login is the account's own, and nothing in the everyday folders is used.

**Claude Code** (a browser window opens; sign in with the Claude subscription's account). Another
`CLAUDE_CONFIG_DIR` is another Keychain entry: the everyday login is not touched. About 2 minutes.

```bash
env -i PATH="$PATH" HOME="$HOME" USER="$USER" LANG="$LANG" TERM="$TERM" TMPDIR="$TMPDIR" \
    CLAUDE_CONFIG_DIR="$G/claude-code" DISABLE_AUTOUPDATER=1 claude auth login
env -i PATH="$PATH" HOME="$HOME" USER="$USER" CLAUDE_CONFIG_DIR="$G/claude-code" claude auth status
```

Never `claude setup-token`: no long-lived token is stored (decision 5).

**Codex CLI** (sign in with the ChatGPT plan's account). The login becomes a file in the state folder. Never copy the
everyday `auth.json`: both copies would refresh one token, and one of them would be logged out. About 2 minutes.

```bash
env -i PATH="$PATH" HOME="$HOME" USER="$USER" LANG="$LANG" TERM="$TERM" TMPDIR="$TMPDIR" \
    CODEX_HOME="$G/codex-cli" codex login -c cli_auth_credentials_store="file"
env -i PATH="$PATH" HOME="$HOME" USER="$USER" CODEX_HOME="$G/codex-cli" \
    codex login status -c cli_auth_credentials_store="file"
```

**Devin CLI** (sign in with the Devin account). Never `devin auth logout`, in any environment, until it is known that
the two logins are apart. About 2 minutes.

```bash
D="$G/devin-cli"
env -i PATH="$PATH" HOME="$HOME" USER="$USER" LANG="$LANG" TERM="$TERM" TMPDIR="$TMPDIR" \
    XDG_CONFIG_HOME="$D/config" XDG_DATA_HOME="$D/data" XDG_STATE_HOME="$D/state" XDG_CACHE_HOME="$D/cache" \
    DEVIN_SESSIONS_DIR="$D/sessions" devin auth --process-model in-process login
env -i PATH="$PATH" HOME="$HOME" USER="$USER" XDG_CONFIG_HOME="$D/config" XDG_DATA_HOME="$D/data" \
    XDG_STATE_HOME="$D/state" XDG_CACHE_HOME="$D/cache" DEVIN_SESSIONS_DIR="$D/sessions" \
    devin auth --process-model in-process status
```

**Muse Code**: no login in its folder (the folder holds its settings and sessions). Its subscription key goes in a
Keychain item of groundtruth's; `security` asks for the value, so it is in no shell history. The night reads it into
Muse Code's environment only.

```bash
security add-generic-password -a "$USER" -s "groundtruth META_API_KEY" -w
```

**OpenRouter**: make a key for this campaign with a limit of 5 USD, then:

```bash
security add-generic-password -a "$USER" -s "groundtruth OPENROUTER_API_KEY" -w
```

## The night, in order

Every command starts from the repository's root, with `GROUNDTRUTH_CLIENT_HOME` exported as above and the night's
date in `N` (`export N=<YYYY-MM-DD>`). Keep the computer on power and on the network; the cache runs keep it awake
themselves (`caffeinate -i`). A check made more than `age × 1.1 + 90 s` after its priming is left out, so a sleeping
computer loses checks, not truth. Logs and pids are in `results/<folder>/logs/` (never committed); `tail -f` a `.log`
to follow a run.

| # | Command | Account | Wall time |
|---|---|---|---|
| 0 | `python3 harness/night.py --date $N --dry-run all` | none: sends nothing | 1 min |
| 1 | `python3 harness/night.py --date $N untouched --save` | none | seconds |
| 2 | `python3 harness/night.py --date $N --go smoke` | Claude, ChatGPT, Devin, Muse | about 5 min per client, side by side: about 10 min |
| 3 | `python3 harness/night.py --date $N untouched --compare` | none | seconds |
| 4 | Read the smoke results (below); stop here if one is wrong | none | 10 – 20 min |
| 5 | `python3 harness/night.py --date $N --go openrouter` | OpenRouter key | 2 h 15, in the background; about 1.60 USD |
| 6 | `python3 harness/night.py --date $N --go windows` | OpenRouter key | about 10 min, in the foreground; 0 USD (refused, not billed) |
| 7 | `python3 harness/night.py --date $N --go claude codex devin muse` | Claude, ChatGPT, Devin, Muse | about 8 min of launches (15 s apart, Devin 20 s); then in the background: Claude 2 h 10, Codex 12 h 10, Devin 2 h 10 (13 runs) and 12 h 10 (DV8 – DV11), Muse 2 h 10 (minutes where a control misses) |
| 8 | When CC1 – CC4 have ended (about 2 h 10 after step 7): `python3 harness/night.py --date $N --go claude-5m` | Claude | 25 min |
| 9 | When CC5 – CC8 have ended: `python3 harness/night.py --date $N --go limits` | Claude | 10 – 20 min per model, one after the other: 40 – 80 min; 4 to 12 million tokens of the Claude allowance |
| 10 | Only if S3 showed Devin's provider refusing: `python3 harness/night.py --date $N --go limits-devin` | Devin | 12 models one after the other, 2 – 4 h; 12 to 36 million tokens of the allowance |
| 11 | Only if S4 showed Meta's own refusal: `python3 harness/night.py --date $N --go limits-muse` | Muse | 30 – 60 min |

A run has ended when the last line of its `.jsonl` is `{"event": "done", …}` or `{"event": "stop", …}`. The cache
runs end about 12 h 30 after step 7 (the `long` runs of Codex and Devin). Steps 10 and 11 may wait for another day:
each uses a large part of a plan's allowance.

**Step 4, the smoke results.** `results/own-clients-$N/smoke/` holds S1, S2, S3, S3b, S4 (`.jsonl`) and
`refusals.jsonl`:

- each run ends with `{"event": "done"}` after one `check` of the control that is warm, with `"calls": 1`; a `stop`
  (`no-observable-cache`, `quota`, `control-failed`) or a `check-invalid` is read before going on;
- S3b (Devin, gpt-6-1-terra): whether its replies report any cached token; if not, DV5 will be excluded (decision 1);
- `refusals.jsonl`: Claude, Devin and Muse should each show the provider's refusal (a `message` that names the size,
  as `prompt is too long: N tokens > M maximum`); Codex writes no row (its own cap ends the walk; the log says so);
- step 3 prints `unchanged: every everyday folder`. If it prints `CHANGED`, stop: a client wrote outside its state
  folder.

These files answer every *(open)* of [`own-clients.md`](own-clients.md), section 1. If a client printed something
other than expected, `harness/clients.py` and `test/fixtures/clients/` are corrected from them before step 5.

**Stopping.** A run stops itself on a quota refusal, on a missed control, or (Claude) on a change of lifetime. To stop
one by hand: `kill -- -$(cat results/own-clients-$N/logs/<id>.pid)` (the run's process group: caffeinate and the
probe under it). `night.py` never starts again a run that has a pid file or a raw file.

**After the night** (not the owner's): each folder gets its README, its runs go in `observed/manifest.json` (runs that
ended early or measured nothing in `excluded`, with the reason), and `observed.json` is rebuilt.
