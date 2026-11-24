# Own-client night audit: passed

Night: 2026-11-23 (the first own-clients night: Codex CLI and Devin CLI only). The last run ended at 2026-11-23T23:16:38Z.
Audited: 2026-11-24, after every run had ended, on the computer that ran the night.
Who audited: an independent reviewer who did not write the harness read the raw results, the Codex session files and the console logs by hand. A second reviewer generated and read the post-run everyday report, repeated the scans and wrote this file from the first reviewer's verdicts.

## The runs

25 runs. 8 finished and 17 stopped early. Nothing private reached a `*.jsonl` file.

Finished runs (each keeps its 2026-11-23 data):

- DV11: ready on the data. 51/51 timed checks were warm, so the observed lower bound is 12h, the oldest age tested.
- DV15: ready on the data. 37/42 timed checks were warm. All three checks were warm through 50m, and all three were cold at 2h.
- CX2: publishable with a note. 37/51 timed checks were warm. All were warm through 20m. The last warm check was at 2h, and all three were cold from 4h.
- CX4: publishable with a note. 38/51 timed checks were warm. All were warm through 25m. The last warm check was at 2h, and all three were cold from 4h.
- CX5: publishable with a note. 38/51 timed checks were warm. All were warm through 5m. The last warm check was at 4h, and all three were cold from 8h.
- DV8: publishable with a note. 27/51 timed checks were warm. The results are mixed from 2.5m, the last warm check was at 4h, and all three were cold from 8h. The samples do not support a single expiry time.
- DV9: publishable with a note. Publish a 2h lower bound, the end of its configured ladder, with both denominators. Five retry primings already read warm, because the first night's harness retried an empty-response priming in a new session with the same text. The ordinary count is 41/41 warm. Without those five it is 36/36 fresh timed checks warm.
- DV14: publishable with a note. 11/41 timed checks were warm. All were warm through 2.5m, the last warm check was at 15m, and all three were cold from 20m. One 40m check was invalid because it made two model calls, and it is not counted.

Excluded: these 17 runs stopped early, so none of their samples are published. The night's rules exclude a run that ended early.

- CX1, CX3, CX6: the 30s control was cold (`no-observable-cache`). The first night's harness stopped after one cold control. Rerun on 2026-11-24.
- DV1, DV2, DV3, DV13, DV16, DV18: one Devin rate-limit refusal during a priming, between 11:14:14 and 11:14:23 UTC, which was recorded as `quota`. The refusals named the same 11:15 UTC reset, and none showed the plan's quota running out. Rerun on 2026-11-24.
- DV9d: eight empty-response priming errors were followed by the same rate-limit refusal (`quota`). Its control was warm. Rerun on 2026-11-24 with its daemon defaults, kept separate from DV9.
- DV7: the control was cold, and every read was zero (`no-observable-cache`). There is only one observation for this model. Rerun once on 2026-11-24 with the two-control policy.
- DV10: the control was cold (`no-observable-cache`), although the same model had a warm control earlier. Rerun on 2026-11-24.
- DV12: three baseline attempts rejected the low-effort model id, so there is no control (`baseline-failed`). Rerun on 2026-11-24 with the corrected high-effort id.
- DV4, DV6: the baseline, the priming and the control all reported zero cached tokens (`no-observable-cache`), as earlier observations of the same model did. Dropped from 2026-11-24.
- DV5: every read was zero (`no-observable-cache`), as in smoke S3b and an earlier run. Dropped from 2026-11-24 unless the new S3b smoke comes back warm.
- DV17: the control read fell below the warm threshold (`no-observable-cache`), as it did in an earlier run. Dropped from 2026-11-24.

13 runs are rerun on 2026-11-24 in a new date folder: CX1, CX3, CX6, DV1, DV2, DV3, DV7, DV9d, DV10, DV12, DV13, DV16 and DV18.

## The checklist

- A. Raw results: checked. Every run has a file, and `status` shows no run alive. Every line of the 25 run files and 3 smoke files was read, and they hold only the allowlist's fields. Every counted `check` has `model_matches: true`, and every Codex check has `model_evidence: own-turn`. Each finished Codex run ends with a final `model-scan` line showing 0 other models and no unreadable session. The `check-invalid`, `check-failed`, `retry` and `stop` lines are understood. Note: the first night's harness recorded wall-clock time only (no `monoAgeSec`), so these rows cannot show wall-clock and monotonic age agreeing within 5s. No check was flagged late, and the offsets from target were 0 to +94s.
- B. Codex session files: checked by a lookup with the measurement's prompt salt, because the console logs masked the session handles. All 324 public measurement rows across CX1 to CX6 matched exactly one session file each: 165 distinct files, 0 ambiguous, 0 missing. Every file could be read in full and named only the run's model. None had a reroute.
- C. Console logs and private records: checked. The logs are ignored by Git and are mode 600, like the private records. `git status` lists nothing but this night's folder. The public events in the logs match the `*.jsonl` files exactly. Each run's client version is in its log and its private record, and in no public file.
- D. Scans and everyday report: checked. Both own-client scans end with `CLEAN`. The post-run everyday report was generated after the last run ended and was read. Its changes come from the owner's own use of his tools: Claude Code, Codex and pi sessions, a few Devin CLI logs and transcripts, and Keychain items of other applications. No Keychain item was added. No Codex or Devin Keychain item was added or changed. None of the changes points at the night: the night's own Codex and Devin sessions are in its dedicated state folders.
