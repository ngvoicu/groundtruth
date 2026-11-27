# A real coding agent through Provimux, with the account that answered: 2026-11-27

The cache lifetime the Pi coding agent gets through Provimux 8.1.7-pmx.3 (a distribution of CLIProxyAPI) on two
subscription logins, for the models released in the 31 days before: Claude Fable 5.2 on a Claude login, GPT-6.2 Astra
and GPT-6.2 Sol on a Codex login. Made with `harness/agent_gateway.py` (client `pi+cliproxyapi`, shown on providers.dev
as `agent+cliproxyapi`), between 14:45 and 16:50 UTC.

- **How**: Pi 1.6.0 with pi-provimux 105.0.7, over SSE (not the WebSocket Pi can use for Codex: the relay reads each
  answer's headers), cache warming off, reasoning low, only the pi-provimux extension, in a scratch folder of its own.
  Each sample is a new Pi session whose first message carries a block of random words no other sample has (1,200
  words for Claude, 700 for Codex); after its age the session is resumed once with "Reply with OK only". A check is
  warm when the cache read covers Pi's own prompt (the baseline, measured once per run without a block) and at least
  half of the block. Every sample is primed once and checked once.
- **Which account answered**: a loopback relay between Pi and the gateway recorded every request's
  `X-Provimux-Account`, the model the provider's answer names and the usage as reported. A check counts only when
  its priming and itself were each one model request, answered by the same login of the intended kind and by the
  requested model. All 59 checks and controls here counted: every Claude request was answered by `claude-login-1`,
  every Codex request by `codex-login-1`. No API key answered anything.
- **The labels**: `claude-login-1`, `codex-login-1`, `codex-apikey-1` and the others stand for the gateway's account
  markers (an opaque hash per account). Nothing that names an account of the gateway is published; the `accounts`
  list at the start of each file gives each label's provider, kind and priority, so a reader can see what else could
  have answered.
- **Ages**: planned around the documented lifetimes instead of from 2.5 minutes (`first_ages` in the manifest).
  Claude Fable 5.2: 4, 6, 30, 55 and 65 minutes (documented 5 minutes and 1 hour); 2 hours only if a 65-minute check
  read the cache, and none did. GPT-6.2: 25, 35, 55, 65 minutes and 2 hours (documented 30 minutes; the 12-hour
  retention was not tested). Sol was cold at 25 minutes, so S2 added 2.5, 5, 10 and 15 minutes. Three samples per age.

| Age | Fable 5.2 (F1) | Astra (A1 + A2) | Sol (S1 + S2) |
|---|---|---|---|
| control (30 s) | 1/1 | 1/2 | 2/2 |
| 2.5 min | | | 2/3 |
| 4 min | 3/3 | | |
| 5 min | | | 1/3 |
| 6 min | 3/3 | | |
| 10 min | | | 0/3 |
| 15 min | | | 0/3 |
| 25 min | | 3/3 | 0/3 |
| 30 min | 3/3 | | |
| 35 min | | 1/3 | 0/3 |
| 55 min | 3/3 | 3/3 | 0/3 |
| 65 min | 0/3 | 1/3 | 0/3 |
| 2 h | | 2/3 | |

- **Claude Fable 5.2**: about one hour: every check warm through 55 minutes, none at 65. Every cache write was a
  1-hour one (`ephemeral_1h_input_tokens`): Provimux asks Anthropic for it on Claude logins.
- **GPT-6.2 Astra**: warm 3 of 3 at 25 minutes, then at random (1/3, 3/3, 1/3, 2/3 up to 2 hours). **A1 is kept and
  marked**: its control was cold at 30 seconds and the tool then ended the run; A2 continues it in fresh sessions with
  a control that hit. The chain's control is 1 of 2, so providers.dev's strict reading gives this client 0 for Astra.
- **GPT-6.2 Sol**: no dependable lifetime: 2 of 3 at 2.5 minutes, 1 of 3 at 5, cold from 10 minutes on (21 of 21).
  The 2-hour samples were primed and not checked.
- **Gemini 4 Hydrogen** (H1, the Antigravity login): the first request was refused with HTTP 429
  `RESOURCE_EXHAUSTED` (a quota); the run stopped at once and nothing was measured. It is in `excluded`.

**Removed before publication** (`harness/agent_gateway.py publish`): every account marker, replaced by its label, and
the `attribution` part of the Codex usage (per-message token counts keyed by the ids the provider gives its answers).
The files never held a request header's value, a key, a path or a session file: the relay records header names, the
values of limit headers only, and a hash and size of each request body; session ids are `gt-<random>-<age>-<n>`.

Used: 126 answered model requests and 1 refused; 490,096 input tokens (151,181 read from cache, 120,502 written),
597 output tokens; at list prices about 2.84 US dollars, paid by subscriptions, not by the token.

Files: `F1`, `A1`, `A2`, `S1`, `S2`, `H1` (`.jsonl`, one Pi invocation or decision per line), `run.sh`.
