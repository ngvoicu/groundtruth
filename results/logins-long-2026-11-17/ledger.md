# Ledger, 2026-11-17 (logins-long)

Price: $0 per token on every row (subscription logins through CLIProxyAPI: plan quota, no per-token charge;
every answer's `X-CPA-AUTH-KIND` was `oauth`). Written by `ledger.py` from the raw files. CL1, CL3, ML1 and
ML3 were cut off by the Mac's restart at 10:16 local on 2026-11-18: their rows are their progress files.

## Field tests (one row per request)

| Login | Model | Sent | Status | Answered by | Input tokens (reply) | of them cached | Output tokens | Price | Running input total of the login |
|---|---|---|---|---|---|---|---|---|---|
| Codex login | `probe/gpt-6.1-sol` | `{}` | 200 | oauth | 309 | 0 | 5 | $0 | 309 |
| Codex login | `probe/gpt-6.1-sol` | `{"prompt_cache_retention":"24h"}` | 200 | oauth | 309 | 0 | 5 | $0 | 618 |
| Codex login | `probe/gpt-6.1-sol` | `{"prompt_cache_retention":"bogus-retention"}` | 200 | oauth | 309 | 0 | 5 | $0 | 927 |
| Codex login | `probe/gpt-6.1-sol` | `{"prompt_cache_options":{"ttl":"12h"}}` | 200 | oauth | 309 | 0 | 5 | $0 | 1,236 |
| Codex login | `probe/gpt-6.1-sol` | `{"prompt_cache_options":{"ttl":"bogus-ttl"}}` | 200 | oauth | 309 | 0 | 5 | $0 | 1,545 |
| Codex login | `probe/gpt-6.1-sol` | `{"unknown_field_xyz":"1"}` | 400 | oauth | 0 | 0 | – | $0 | 1,545 |
| Codex login | `probe/gpt-6.1-sol` | `{"__filler":2400,"__filler_salt":"a21706","prompt_cache_retention":…` | 200 | oauth | 3,018 | 0 | 5 | $0 | 4,563 |
| Codex login | `probe/gpt-6.1-sol` | `{"__filler":2400,"__filler_salt":"a21706","prompt_cache_retention":…` | 200 | oauth | 3,018 | 2,816 | 5 | $0 | 7,581 |
| Codex login | `probe/gpt-6.1-sol` | `{"__filler":2400,"__filler_salt":"b21706","prompt_cache_options":{"…` | 200 | oauth | 3,004 | 0 | 5 | $0 | 10,585 |
| Codex login | `probe/gpt-6.1-sol` | `{"__filler":2400,"__filler_salt":"b21706","prompt_cache_options":{"…` | 200 | oauth | 3,004 | 2,816 | 5 | $0 | 13,589 |
| Devin login | `devin/swe-2` | `{}` | 200 | oauth | 471 | 448 | 16 | $0 | 471 |
| Devin login | `devin/swe-2` | `{"prompt_cache_retention":"24h"}` | 200 | oauth | 471 | 448 | 16 | $0 | 942 |
| Devin login | `devin/swe-2` | `{"prompt_cache_retention":"bogus-retention"}` | 200 | oauth | 471 | 0 | 16 | $0 | 1,413 |
| Devin login | `devin/swe-2` | `{"prompt_cache_options":{"ttl":"bogus-ttl"}}` | 200 | oauth | 471 | 64 | 16 | $0 | 1,884 |
| Devin login | `devin/swe-2` | `{"unknown_field_xyz":"1"}` | 200 | oauth | 471 | 448 | 16 | $0 | 2,355 |
| Devin login | `devin/claude-haiku-5-5` | `{"__ttl":"1h"}` | 200 | oauth | 574 | 0 | 4 | $0 | 2,929 |
| Devin login | `devin/claude-haiku-5-5` | `{"__ttl":"bogus-ttl"}` | 200 | oauth | 574 | 570 | 4 | $0 | 3,503 |

## Lifetime runs (one row per run)

| Login | Run | Model | Status | Requests answered | Answered by | Input tokens | of them cached | Output tokens | Price | Running input total of the login |
|---|---|---|---|---|---|---|---|---|---|---|
| Antigravity login | AG1 | `gemini-3.1-flash-lite` | no-observable-cache | 3 | oauth ×3 | 14,010 | 4,062 | 3 | $0 | 14,010 |
| Antigravity login | AG2 | `gemini-3.5-flash-lite` | no-observable-cache | 3 | oauth ×3 | 14,094 | 4,062 | 3 | $0 | 28,104 |
| Antigravity login | AG3 | `gemini-3-flash` | no-observable-cache | 3 | oauth ×3 | 13,911 | 4,062 | 3 | $0 | 42,015 |
| Antigravity login | AG5 | `gpt-oss-120b-medium` | no-observable-cache | 3 | oauth ×3 | 14,340 | 201 | 111 | $0 | 56,355 |
| Codex login | CL1 | `probe/gpt-6.1-sol` | running (progress file: cut off by the restart of 2026-11-18 10:16 local) | 98 | oauth ×98 | 263,558 | 71,040 | 490 | $0 | 277,147 |
| Codex login | CL2 | `probe/gpt-6.1-terra` | stopped-early | 71 | oauth ×71 | 190,895 | 10,240 | 355 | $0 | 468,042 |
| Codex login | CL3 | `probe/gpt-6-astra` | running (progress file: cut off by the restart of 2026-11-18 10:16 local) | 98 | oauth ×98 | 263,335 | 78,464 | 490 | $0 | 731,377 |
| Codex login | CL4 | `probe/gpt-6-luna` | no-observable-cache | 3 | oauth ×3 | 7,977 | 0 | 15 | $0 | 739,354 |
| Meta login | ML1 | `muse-ember-1.0` | running (progress file: cut off by the restart of 2026-11-18 10:16 local) | 38 | oauth ×38 | 100,000 | 25,480 | 608 | $0 | 100,000 |
| Meta login | ML3 | `muse-wonder-1.0` | running (progress file: cut off by the restart of 2026-11-18 10:16 local) | 38 | oauth ×38 | 100,224 | 33,380 | 607 | $0 | 200,224 |

AG4 (`gemini-3.8-flash-tiered`) left no run file: every request was answered 503 (Google's server capacity)
until it was ended after 10 minutes; nothing was answered.

## Per login

| Login | Input tokens answered |
|---|---|
| Antigravity login | 56,355 |
| Codex login | 739,354 |
| Devin login | 3,503 |
| Meta login | 200,224 |
