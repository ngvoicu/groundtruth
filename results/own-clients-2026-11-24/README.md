# Codex CLI and Devin CLI on their own logins: the re-run of 2026-11-24

The 13 runs of [`../own-clients-2026-11-23`](../own-clients-2026-11-23/README.md) that stopped early and were to be run
again, on a new date folder with nothing else changed: the same logins, isolation and sandbox, the same smoke rules,
and the harness as corrected after the first night (a cold control gets one more in a fresh session; only Devin's own
rate-limit text is a rate limit; a check whose wall-clock and monotonic ages disagree is late). Steps as in
[`docs/own-clients-RUN.md`](../../docs/own-clients-RUN.md), "Re-running some runs": a new snapshot, the smoke runs and
their review, then
`python3 harness/night.py --date 2026-11-24 --go CX1,CX3,CX6,DV1,DV2,DV3,DV7,DV9d,DV10,DV12,DV13,DV16,DV18`, launched at
07:00:48 UTC from commit `cbd3ef9`. The last run ended at 20:41:38 UTC.

Method as the first night: route `codex-subscription` with client `codex-cli`, route `devin` with client `devin-cli`,
each through `harness/probe.py` on the owner's subscription login in a dedicated state folder; a ~3,000-word block of
random filler per sample, primed in a new session and resumed once at its age; the 30-second control first; 3 samples
per age in three waves at least five minutes apart; effort `low` (DV12: `high`, the model has no `low` on Devin).
Devin runs in-process with its cache keepalive off, except DV9d, which runs with the client's defaults (its background
daemon and keepalive). A check counts only when it is one model request, on time and answered by the requested model.

**Audited** ([`AUDIT.md`](AUDIT.md)): an independent reviewer read every line of the 13 run files and 3 smoke files
(1,249 rows), the Codex session files and the 13 console logs. Nothing private reached a `*.jsonl` file. Wall-clock and
monotonic ages agreed to the second on 518 of 519 checks and by one second on the last.

## What came out

13 runs: 11 finished and are published, 2 stopped at their controls and are under `excluded`.

| Run | Model | Control | Warm / usable | All warm through | Last warm | First all cold | Note |
|---|---|---:|---:|---:|---:|---:|---|
| CX1 | `gpt-6.2-sol` | 1/1 | 27/51 | 2.5 min | 90 min | 75 min | 0 of 3 at 75 min, 1 of 3 at 90 min |
| CX3 | `gpt-6.1-sol` | 1/1 | 25/40 | 7.5 min | 4 h | 8 h | 11 late checks not counted (10 of them warm); one on-time sample each at 2.5, 5 and 7.5 min; see below |
| CX6 | `gpt-6-luna` | 1/1 | 22/51 | 2.5 min | 50 min | 60 min | last hits 2 of 3 at 50 min |
| DV1 | `claude-opus-5-5-low` | 1/1 | 5/42 | 2.5 min | 5 min | 7.5 min | |
| DV2 | `claude-sonnet-5-5-low` | 1/1 | 6/42 | 5 min | 5 min | 7.5 min | |
| DV3 | `claude-haiku-5-5-low` | 1/1 | 6/42 | 5 min | 5 min | 7.5 min | |
| DV9d | `glm-5-3-low` | 1/1 | 24/42 | 10 min | 50 min | 60 min | daemon and keepalive defaults; two 5-minute primings retried with fresh prefixes |
| DV10 | `kimi-k3-1-pro-low` | 1/1 | 11/51 | — | 60 min | 5 min | intermittent |
| DV13 | `gemini-4-argon-low` | 1/2 | 9/42 | 5 min | 40 min | 7.5 min | first control cold, second warm |
| DV16 | `muse-wonder-1-0-low` | 1/2 | 16/42 | — | 90 min | 5 min | first control cold, second warm; intermittent |
| DV18 | `gemini-4-neon-low` | 1/1 | 9/42 | — | 60 min | 5 min | intermittent |

"All warm through" counts the timed ages only, as `observed.json`'s `all_warm_through_s` does; the control is beside
it. "First all cold" can come before a later hit.

Checks warm of those made, by age (late checks left out):

| Age | CX1 | CX3 | CX6 | DV1 | DV2 | DV3 | DV9d | DV10 | DV13 | DV16 | DV18 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2.5 min | 3/3 | 1/1 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 1/3 | 3/3 | 2/3 | 1/3 |
| 5 min | 2/3 | 1/1 | 2/3 | 2/3 | 3/3 | 3/3 | 3/3 | 0/3 | 3/3 | 0/3 | 0/3 |
| 7.5 min | 2/3 | 1/1 | 1/3 | 0/3 | 0/3 | 0/3 | 3/3 | 1/3 | 0/3 | 2/3 | 0/3 |
| 10 min | 3/3 | 1/3 | 3/3 | 0/3 | 0/3 | 0/3 | 3/3 | 1/3 | 1/3 | 1/3 | 2/3 |
| 15 min | 2/3 | 1/1 | 2/3 | 0/3 | 0/3 | 0/3 | 1/3 | 0/3 | 0/3 | 1/3 | 0/3 |
| 20 min | 2/3 | 2/2 | 3/3 | 0/3 | 0/3 | 0/3 | 1/3 | 1/3 | 0/3 | 0/3 | 1/3 |
| 25 min | 2/3 | 1/2 | 1/3 | 0/3 | 0/3 | 0/3 | 2/3 | 0/3 | 1/3 | 2/3 | 1/3 |
| 30 min | 3/3 | 2/2 | 2/3 | 0/3 | 0/3 | 0/3 | 3/3 | 3/3 | 0/3 | 1/3 | 0/3 |
| 40 min | 3/3 | 2/3 | 3/3 | 0/3 | 0/3 | 0/3 | 2/3 | 1/3 | 1/3 | 3/3 | 2/3 |
| 50 min | 3/3 | 2/3 | 2/3 | 0/3 | 0/3 | 0/3 | 3/3 | 1/3 | 0/3 | 0/3 | 1/3 |
| 60 min | 1/3 | 2/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 2/3 | 0/3 | 2/3 | 1/3 |
| 75 min | 0/3 | 2/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 1/3 | 0/3 |
| 90 min | 1/3 | 3/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 1/3 | 0/3 |
| 2 h | 0/3 | 2/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 |
| 4 h | 0/3 | 2/3 | 0/3 | — | — | — | — | 0/3 | — | — | — |
| 8 h | 0/3 | 0/3 | 0/3 | — | — | — | — | 0/3 | — | — | — |
| 12 h | 0/3 | 0/3 | 0/3 | — | — | — | — | 0/3 | — | — | — |

## Notes on single runs

- **CX3.** 11 of its 51 timed checks were late (past 1.1 times the age plus 90 seconds) and are not counted, although
  10 of them read warm: its count is 25 of 40, not 35 of 51. Only one on-time sample counts at each of 2.5, 5 and 7.5
  minutes. The 5-minute sample measured 323 seconds start to start, about 318 of them inside the priming turn, so its
  idle time was far shorter than 5 minutes. Its 7.5 minutes through which every check hit rests on those single
  samples.
- **DV9d and DV9.** The same model, `glm-5-3-low`, in two settings: DV9 (first night) in-process with the keepalive
  off, warm in every check to 2 hours; DV9d (this night) with the client's daemon and keepalive defaults, warm through
  10 minutes and cold from 60. They differ in date too, so the difference cannot be put on the daemon alone. In
  `observed/manifest.json` DV9d's `options` carry
  `"devin": {"process_model": "client default (daemon)", "keepalive_max_pings": "client default"}` (as its start line
  records them), so the two are separate entries and each is `latest`.
- **DV13 and DV16.** The first 30-second control was cold and the second, in a fresh session, warm; the control is
  published as 1 of 2.
- **DV9d.** Two 5-minute primings returned an empty response and were primed again with fresh prefixes. Every timed
  priming of the night started below its warm threshold.

## What is left out

- DV7 (`gpt-6-luna-low`): both 30-second controls read zero cached tokens (minimums 11,616 and 11,623); all five
  responses, the baseline and both primings included, reported zero (`no-observable-cache`). No timed check.
- DV12 (`deepseek-v4-pro-high`, the corrected id): both 30-second controls read below the warm threshold (2,304 and
  13,056 cached tokens against minimums of 17,385 and 17,335; `no-observable-cache`). No timed check.
- The smoke runs in `smoke/` establish the controls only: S2 (Codex CLI, `gpt-6-luna`) and S3 (Devin CLI,
  `claude-haiku-5-5-low`) had warm controls; S3b (Devin CLI, `gpt-6-1-terra-low`) had the two cold controls expected
  for that model, so DV5 of the first night is not run again.

All are under `excluded` in `observed/manifest.json` with their reasons.

## Files

- `CX*.jsonl`, `DV*.jsonl`: one file per run, written through `harness/probe.py`'s public allowlist (no client
  version, no client text, a session by its number, a reported model only as `model_matches`).
- `smoke/S2.jsonl`, `smoke/S3.jsonl`, `smoke/S3b.jsonl`: the smoke runs.
- `AUDIT.md`: the night's audit.
- Not in the repository: `logs/` (console logs, with client versions and session handles), the private run records
  and the clients' state folders.
