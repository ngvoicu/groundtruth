# Codex CLI and Devin CLI on their own logins: cache lifetimes, the first own-client night, 2026-11-23

The first night of [`docs/own-clients.md`](../../docs/own-clients.md): the cache runs of Codex CLI (route
`codex-subscription`, client `codex-cli`) and the Devin CLI (route `devin`, client `devin-cli`), each driven by
`harness/probe.py` through the vendor's own client on the owner's subscription login, in a dedicated state folder of
its own, a throwaway `HOME` and an empty temporary working folder, each client process under `sandbox-exec`. Steps as
in [`docs/own-clients-RUN.md`](../../docs/own-clients-RUN.md): the smoke runs, their review, then
`python3 harness/night.py --date 2026-11-23 --go all`. The last run ended at 23:16:38 UTC.

Method: a ~3,000-word block of random filler per sample, primed in a new session and resumed once at its age; the
control (the prompt sent again at 30 seconds) first; 3 samples per age, primed in three waves at least five minutes
apart; effort `low` (Nemotron 3.5 Super: `none`). Codex: `codex exec` with the built-in ChatGPT provider; a check
counts only when its own new turn in the session file names the requested model, and each run's session files are
read whole at the end (`model-scan`). Devin: `--process-model in-process` with `DEVIN_CACHE_KEEPALIVE_MAX_PINGS=0`,
except DV9d (the client's defaults). A check is warm when the cached tokens cover the client's own prompt and at least
half of the block. Ages are measured from the start of the priming. This night's harness recorded wall-clock ages
only (no monotonic age); no check was flagged late, and the offsets from target were 0 to +94 s.

**Audited** ([`AUDIT.md`](AUDIT.md)): an independent reviewer who did not write the harness read every line of the 25
run files and 3 smoke files, the Codex session files and the console logs. Nothing private reached a `*.jsonl` file.

## What came out

25 runs: 8 finished and are published, 17 stopped early and are under `excluded`.

| Run | Model | Warm / usable | All warm through | Last warm | First all cold | Note |
|---|---|---:|---:|---:|---:|---|
| CX2 | `gpt-6.2-astra` | 37/51 | 20 min | 2 h | 4 h | 2 of 3 at 25 min, 3 of 3 at 2 h |
| CX4 | `gpt-6.1-terra` | 38/51 | 25 min | 2 h | 4 h | first mixed at 30 min, 1 of 3 at 2 h |
| CX5 | `gpt-6-astra` | 38/51 | 5 min | 4 h | 8 h | first mixed at 7.5 min, 3 of 3 at 4 h |
| DV8 | `deepseek-v4-1-flash-1017-low` | 27/51 | — | 4 h | 7.5 min | intermittent from 2.5 min (1 of 3); no single expiry time |
| DV9 | `glm-5-3-low` | 41/41 | 2 h | 2 h | — | in-process, keepalive off; 2 h is the end of its ladder, a lower bound; 36/36 without five checks whose retried priming already read warm; one sample lost |
| DV11 | `nemotron-3-5-super-none` | 51/51 | 12 h | 12 h | — | 12 h is the oldest age tested, a lower bound |
| DV14 | `grok-4-7-low` | 11/41 | 2.5 min | 15 min | 20 min | one 40-minute check made two model calls: check-invalid, not counted |
| DV15 | `kimi-k3-low` | 37/42 | 50 min | 90 min | 2 h | 2 of 3 at 60 and 75 min, 3 of 3 at 90 min |

Checks warm of those made, by age (the control first):

| Age | CX2 | CX4 | CX5 | DV8 | DV9 | DV11 | DV14 | DV15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| control | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| 2.5 min | 3/3 | 3/3 | 3/3 | 1/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| 5 min | 3/3 | 3/3 | 3/3 | 2/3 | 3/3 | 3/3 | 1/3 | 3/3 |
| 7.5 min | 3/3 | 3/3 | 2/3 | 0/3 | 2/2 | 3/3 | 3/3 | 3/3 |
| 10 min | 3/3 | 3/3 | 3/3 | 1/3 | 3/3 | 3/3 | 2/3 | 3/3 |
| 15 min | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 2/3 | 3/3 |
| 20 min | 3/3 | 3/3 | 3/3 | 1/3 | 3/3 | 3/3 | 0/3 | 3/3 |
| 25 min | 2/3 | 3/3 | 2/3 | 3/3 | 3/3 | 3/3 | 0/3 | 3/3 |
| 30 min | 3/3 | 2/3 | 2/3 | 2/3 | 3/3 | 3/3 | 0/3 | 3/3 |
| 40 min | 2/3 | 3/3 | 1/3 | 2/3 | 3/3 | 3/3 | 0/2 | 3/3 |
| 50 min | 2/3 | 3/3 | 2/3 | 2/3 | 3/3 | 3/3 | 0/3 | 3/3 |
| 60 min | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 0/3 | 2/3 |
| 75 min | 3/3 | 3/3 | 2/3 | 2/3 | 3/3 | 3/3 | 0/3 | 2/3 |
| 90 min | 1/3 | 2/3 | 3/3 | 1/3 | 3/3 | 3/3 | 0/3 | 3/3 |
| 2 h | 3/3 | 1/3 | 3/3 | 2/3 | 3/3 | 3/3 | 0/3 | 0/3 |
| 4 h | 0/3 | 0/3 | 3/3 | 2/3 | — | 3/3 | — | — |
| 8 h | 0/3 | 0/3 | 0/3 | 0/3 | — | 3/3 | — | — |
| 12 h | 0/3 | 0/3 | 0/3 | 0/3 | — | 3/3 | — | — |

## What went wrong, and what is left out

The night's rules exclude a run that ended early: none of the 17 runs' samples are published. Each is under
`excluded` in `observed/manifest.json` with its reason.

- CX1, CX3, CX6: the 30-second control was cold (`no-observable-cache`), and this night's harness stopped after one
  cold control. Rerun on 2026-11-24.
- DV1, DV2, DV3, DV13, DV16, DV18: one Devin rate-limit refusal during a priming, between 11:14:14 and 11:14:23 UTC,
  recorded as `quota`. The refusals named the same 11:15 UTC reset, and none showed the plan's quota running out.
  Rerun on 2026-11-24.
- DV9d: eight empty-response priming errors, then the same rate-limit refusal (`quota`); its control was warm. Rerun
  on 2026-11-24 with its daemon defaults, kept separate from DV9.
- DV7: the control was cold and every read was zero (`no-observable-cache`). Rerun on 2026-11-24 with the two-control
  policy.
- DV10: the control was cold (`no-observable-cache`), although the same model had a warm control earlier. Rerun on
  2026-11-24.
- DV12: three baseline attempts rejected the model id `deepseek-v4-pro-low`, so there is no control
  (`baseline-failed`). Rerun on 2026-11-24 as `deepseek-v4-pro-high`.
- DV4 (`gpt-6-1-sol-low`), DV6 (`gpt-6-astra-low`): the baseline, the priming and the control all reported zero cached
  tokens, as earlier observations of the same models did. Not rerun.
- DV5 (`gpt-6-1-terra-low`): every read was zero, as in smoke S3b and an earlier run. Not rerun.
- DV17 (`swe-2-medium`): the control read fell below the warm threshold, as in an earlier run. Not rerun.

The three smoke runs in `smoke/` establish the controls only and are under `excluded`: S2 (Codex CLI, `gpt-6-luna`)
and S3 (Devin CLI, `claude-haiku-5-5-low`) had warm controls; S3b (Devin CLI, `gpt-6-1-terra-low`) read zero
everywhere, the expected answer for that model.

Since this night the harness gives a cold control a second chance in a fresh session, treats only Devin's own
rate-limit text as a rate limit (three in a row end a run as `quota`), and records the monotonic age of every check
(`docs/own-clients.md`, the opening section).

## Files

- `CX*.jsonl`, `DV*.jsonl`: one file per run, the events `harness/probe.py` wrote through its public allowlist
  (numbers, booleans and fixed strings; a session by its number, a reported model only as `model_matches`; no client
  version and no client text).
- `smoke/S2.jsonl`, `smoke/S3.jsonl`, `smoke/S3b.jsonl`: the smoke runs.
- `AUDIT.md`: the night's audit.
- Not in the repository: `logs/` (each run's console log, with the client's version and session handles), the
  private run records and the clients' state folders.
