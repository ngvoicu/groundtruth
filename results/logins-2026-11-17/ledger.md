# Ledger, 2026-11-17

Price: $0 per token on every row: all requests went to subscription logins through CLIProxyAPI (plan quota, no
per-token charge; the OpenAI and Claude API keys of the proxy served none of them, see README). Written by
`ledger.py` from the raw files.

## Window requests (one row per request)

| Login | Model | N | Status | Input tokens (reply) | Output tokens (reply) | Price | Running input total of the login |
|---|---|---|---|---|---|---|---|
| Claude login A | `probe/claude-fable-5-2` | 500,500 | 400 | – | – | $0 | 0 |
| Codex login | `probe/gpt-6.1-sol` | 922,289 | 400 | – | – | $0 | 0 |
| Codex login | `probe/gpt-6.1-sol` | 921,489 | 200 | 921500 | 5 | $0 | 921,500 |
| Codex login | `probe/gpt-6-astra` | 922,289 | 400 | – | – | $0 | 921,500 |
| Codex login | `probe/gpt-6-astra` | 921,489 | 200 | 921500 | 5 | $0 | 1,843,000 |
| Codex login | `probe/gpt-6-luna` | 922,289 | 400 | – | – | $0 | 1,843,000 |
| Codex login | `probe/gpt-6-luna` | 921,489 | 200 | 921500 | 5 | $0 | 2,764,500 |
| Devin login | `devin/deepseek-v4-1-flash-1017` | 1,048,463 | 400 | – | – | $0 | 0 |
| Devin login | `devin/deepseek-v4-1-flash-1017` | 1,047,663 | 200 | 1048076 | 16 | $0 | 1,048,076 |
| Devin login | `devin/glm-5-3` | 1,048,482 | 400 | – | – | $0 | 1,048,076 |
| Devin login | `devin/glm-5-3` | 1,047,682 | 502 | – | – | $0 | 1,048,076 |
| Devin login | `devin/gpt-6-luna` | 921,910 | 400 | – | – | $0 | 1,048,076 |
| Devin login | `devin/gpt-6-luna` | 921,110 | 200 | 921500 | 16 | $0 | 1,969,576 |
| Devin login | `devin/claude-haiku-5-5` | 499,864 | 400 | – | – | $0 | 1,969,576 |
| Devin login | `devin/claude-haiku-5-5` | 499,464 | 200 | 999500 | 4 | $0 | 2,969,076 |
| Devin login | `devin/deepseek-v4-pro` | 1,048,410 | 400 | – | – | $0 | 2,969,076 |
| Devin login | `devin/deepseek-v4-pro` | 1,047,610 | 200 | 1048076 | 16 | $0 | 4,017,152 |
| Devin login | `devin/gpt-6-1-terra` | 921,910 | 400 | – | – | $0 | 4,017,152 |
| Devin login | `devin/gpt-6-1-terra` | 921,110 | 200 | 921500 | 5 | $0 | 4,938,652 |
| Devin login | `devin/gemini-4-argon` | 1,048,462 | 400 | – | – | $0 | 4,938,652 |
| Devin login | `devin/gemini-4-argon` | 1,047,662 | 200 | 1048076 | 16 | $0 | 5,986,728 |
| Devin login | `devin/gpt-6-1-sol` | 921,910 | 400 | – | – | $0 | 5,986,728 |
| Devin login | `devin/gpt-6-1-sol` | 921,110 | 200 | 921500 | 5 | $0 | 6,908,228 |
| Devin login | `devin/claude-sonnet-5-5` | 499,864 | 400 | – | – | $0 | 6,908,228 |
| Devin login | `devin/claude-sonnet-5-5` | 499,464 | 200 | 999500 | 4 | $0 | 7,907,728 |
| Devin login | `devin/claude-opus-5-5` | 499,864 | 400 | – | – | $0 | 7,907,728 |
| Devin login | `devin/claude-opus-5-5` | 499,464 | 200 | 999500 | 4 | $0 | 8,907,228 |
| Devin login | `devin/gpt-6-astra` | 921,910 | 400 | – | – | $0 | 8,907,228 |
| Devin login | `devin/gpt-6-astra` | 921,110 | 200 | 921500 | 5 | $0 | 9,828,728 |

Refused requests report no usage (the Fable request above 1,000,000 tokens included). Devin's 502 on `devin/glm-5-3` reported none either; it may still have
counted against the plan (it ran 143 s).

## Lifetime runs (one row per run)

| Login | Run | Model | Status | Requests answered | Input tokens | of them cached | Output tokens | Price | Running input total of the login |
|---|---|---|---|---|---|---|---|---|---|
| Antigravity login | LA1 | `gemini-3.8-flash-high` | stopped-early | 80 | 372,638 | 20,898 | 2,331 | $0 | 372,638 |
| Antigravity login | LA2 | `probe/ag-claude-opus-4-6-thinking` | failed | 15 | 85,987 | 5,740 | 0 | $0 | 458,625 |
| Codex login | LC1 | `probe/gpt-6.1-sol` | completed | 87 | 233,370 | 70,656 | 435 | $0 | 2,997,870 |
| Codex login | LC2 | `probe/gpt-6.1-terra` | stopped-early | 53 | 142,594 | 5,120 | 265 | $0 | 3,140,464 |
| Codex login | LC3 | `probe/gpt-6-astra` | completed | 87 | 233,517 | 78,208 | 435 | $0 | 3,373,981 |
| Codex login | LC4 | `probe/gpt-6-luna` | stopped-early | 81 | 217,709 | 53,504 | 405 | $0 | 3,591,690 |
| Devin login | LD1 | `devin/claude-opus-5-5` | failed | 35 | 170,630 | 23,858 | 140 | $0 | 9,999,358 |
| Devin login | LD2 | `devin/deepseek-v4-pro` | running (ended by hand: its last progress file) | 44 | 130,385 | 12,544 | 704 | $0 | 10,129,743 |
| Devin login | LD3 | `devin/gemini-4-argon` | failed | 7 | 35,961 | 3,046 | 112 | $0 | 10,165,704 |
| Devin login | LD4 | `devin/glm-5-3` | failed | 14 | 42,577 | 6,848 | 80 | $0 | 10,208,281 |
| Devin login | LD5 | `devin/gpt-6-1-sol` | failed | 0 | 0 | 0 | 0 | $0 | 10,208,281 |
| Claude login A | LF1 | `probe/claude-fable-5-2` | completed | 80 | 355,542 | 151,058 | 596 | $0 | 355,542 |
| Claude login A | LF2 | `probe/claude-fable-5-2` | completed | 80 | 355,212 | 150,914 | 500 | $0 | 710,754 |
| Meta login | LM1 | `muse-ember-1.0` | completed | 86 | 226,174 | 109,692 | 1,376 | $0 | 226,174 |
| Meta login | LM2 | `muse-spark-1.3` | stopped-early | 71 | 187,010 | 53,445 | 1,136 | $0 | 413,184 |
| Meta login | LM3 | `muse-wonder-1.0` | completed | 86 | 226,360 | 109,564 | 1,371 | $0 | 639,544 |

LD6 (`devin/grok-4-7`) left no run file: it was ended by hand while priming. The Devin login's request counter
rose by 105 answered requests over the Devin lifetime runs; the files of LD1 to LD5 account for 100, so LD6 had about
5 (its control: 3,860 input tokens per request). Its tokens are not in the totals below.

## Per login

| Login | Input tokens answered (windows and lifetime runs) |
|---|---|
| Antigravity login | 458,625 |
| Claude login A | 710,754 |
| Codex login | 3,591,690 |
| Devin login | 10,208,281 |
| Meta login | 639,544 |
