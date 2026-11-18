# Ledger, 2026-11-17/18 (logins-gpt-6-2)

Price: $0 per token (the Codex login, a ChatGPT plan: plan quota, no per-token charge); every answer's
`X-CPA-AUTH-KIND` was `oauth` and the OpenAI API key's counter stayed at 0. From the run files' `spent` and
`limits-codex.jsonl`.

| Login | What | Model | Requests answered | Input tokens (replies) | of them cached | Output tokens | Price | Running input total |
|---|---|---|---|---|---|---|---|---|
| Codex login | GS1 | `probe/gpt-6.2-sol` | 53 | 142,293 | 7,552 | 265 | $0 | 142,293 |
| Codex login | GA1 | `probe/gpt-6.2-astra` | 83 | 223,250 | 75,648 | 415 | $0 | 365,543 |
| Codex login | window | `probe/gpt-6.2-sol` | 0 (refused, 400) | – | – | – | $0 | 365,543 |
| Codex login | window | `probe/gpt-6.2-astra` | 0 (refused, 400) | – | – | – | $0 | 365,543 |

A refused window request reports no usage; whether the plan counts a refusal is not shown.
