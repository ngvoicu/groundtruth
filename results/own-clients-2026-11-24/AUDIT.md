# Own-client night audit: passed

The 2026-11-24 re-run ended at 22:41:38 EET. An independent reviewer audited the measurements on the same computer after all 13 runs had ended. Eleven runs finished and two stopped at their controls.

## Measurements

Warm counts cover on-time timed checks. The 30-second controls are counted separately. Ages are measured from the start of priming. Each tested age had three planned samples.

| Run | Verdict | Warm / usable | Observed cache lifetime and qualifications |
|---|---|---:|---|
| CX1 | With notes | 27/51 | All three were warm at 2.5m. All three were cold at 75m, one was warm at 90m, and all were cold from 2h through 12h. |
| CX3 | With notes | 25/40 | Eleven of 51 timed checks were late. Only one counted at each of 2.5m, 5m and 7.5m, all warm. The 5m sample measured 323s start to start, including about 318s in the prime. The two usage records were only 12s apart. Two of three were warm at 4h and all three were cold at both 8h and 12h. |
| CX6 | With notes | 22/51 | All three were warm at 2.5m. The last hits were two of three at 50m. All were cold from 60m through 12h. |
| DV1 | Ready | 5/42 | Three of three were warm at 2.5m and two of three at 5m. All were cold from 7.5m through 2h. |
| DV2 | Ready | 6/42 | All three were warm through 5m and all were cold from 7.5m through 2h. |
| DV3 | Ready | 6/42 | All three were warm through 5m and all were cold from 7.5m through 2h. |
| DV9d | With notes | 24/42 | Daemon and keepalive defaults. All three were warm through 10m. Hits were mixed at later ages, with three of three warm at 50m and all cold from 60m through 2h. Two 5m primings were retried with fresh prefixes. All timed primings started below their warm threshold. Report this configuration separately from the first night's in-process DV9. |
| DV10 | With notes | 11/51 | One of three was warm at 2.5m. All were cold at 5m, all were warm at 30m, and two were warm at 60m. All were cold from 75m through 12h. |
| DV13 | With notes | 9/42 | The second control was warm. All three were warm through 5m. All were cold at 7.5m, followed by individual hits at 10m, 25m and 40m. All were cold from 50m through 2h. |
| DV16 | With notes | 16/42 | The second control was warm. Two of three were warm at 2.5m, all were cold at 5m, and all were warm at 40m. The last hit was one of three at 90m. All were cold at 2h. |
| DV18 | With notes | 9/42 | One of three was warm at 2.5m. All were cold at 5m, followed by intermittent hits through 60m. All were cold from 75m through 2h. |

## Excluded runs

- DV7 stopped after two fresh 30-second controls. Both read zero cached tokens against minimums of 11,616 and 11,623. All five responses, including the baseline and both primings, reported zero. There were no timed checks.
- DV12 used the corrected high-effort model. Its two fresh 30-second controls read 2,304 and 13,056 cached tokens against minimums of 17,385 and 17,335. Both missed and the run stopped before timed checks.

Both stops recorded the harness reason `no-observable-cache`. The three smoke runs were reviewed separately. S2 and S3 had warm controls. S3b recorded the expected two cold controls.

## Checklist

- A. Checked every line of the 13 evaluation files and three smoke files, 1,249 rows in all. All public fields matched the plan and allowlist. Every one of the 519 checks recorded one call and the requested model. Every Codex check had evidence from its own turn and every final model scan was clear. Wall and monotonic ages agreed to the recorded second on 518 checks and differed by one second on one. All 11 late checks exceeded their age window and were excluded. The only retries were two successful fresh primings in DV9d. No check was invalid or failed.
- B. Matched every Codex baseline and priming to its complete measurement prompt, and each check to its resume in that session. The three evaluations accounted for 315 measurement rows in 159 distinct files. S2 added three rows in two files. All files matched uniquely, were readable, named only the requested model and contained zero reroutes.
- C. Read all 13 private console logs and matched every public event to its evaluation file. The logs are ignored by Git and have mode 600. All 13 evaluation versions matched their private records. The three smoke records were also private. No client version, session handle, private diagnostic or account identifier appeared in the public results. Git showed only the two known untracked night folders.
- D. Both read-only secret scans returned `CLEAN`. The post-run everyday report showed 4,000 filesystem metadata differences and 16 Keychain item differences. One unrelated item was added and 15 items changed. None named Codex or Devin. The changed everyday paths included ordinary tool activity and earlier review records. No measured session identifier appeared there. Nothing in the report pointed to the re-run.
