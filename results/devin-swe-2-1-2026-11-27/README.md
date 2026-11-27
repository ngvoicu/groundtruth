# SWE-2.1 on a Devin login, through Pi and Provimux, with the account that answered: 2026-11-27

The cache lifetime the Pi coding agent gets for Cognition's SWE-2.1 (Devin's id `swe-2-1`, released 2026-11-24)
through Provimux 8.1.7-pmx.4 (a distribution of CLIProxyAPI) on a Devin subscription login, and the model's input
window through the same gateway. Made with `harness/agent_gateway.py` (client `pi+cliproxyapi`, shown on providers.dev
as `agent+cliproxyapi`) and `results/limits-2026-11-16/devin_walk.py` (client `cliproxyapi`), between 18:28 and 19:33
UTC. The login's weekly quota had been used up earlier that day (other Devin models were refused); SWE-2.1 was
answered every time.

- **How**: as [`../agent-gateway-2026-11-27/`](../agent-gateway-2026-11-27/README.md). Pi 1.6.0 with pi-provimux
  105.0.7, over SSE, cache warming off, reasoning low, only the pi-provimux extension, in a scratch folder of its own.
  Each sample is a new Pi session whose first message carries a block of 700 random words no other sample has (about
  3,400 tokens with Pi's own prompt); after its age the session is resumed once with "Reply with OK only". A check is
  warm when the cache read covers Pi's own prompt (the baseline, 1,464 tokens, measured once without a block) and at
  least half of the block. Every sample is primed once and checked once.
- **Which account answered**: the gateway serves the model as `devin/swe-2-1`, and its model list names one account
  for it, the Devin login. A loopback relay between Pi and the gateway recorded every request's
  `X-Provimux-Account`: all 33 requests of the cache run were answered by `devin-login-1`, a login (`oauth`), and every
  answer names the model `devin/swe-2-1`. No API key answered anything. All 15 checks and the control counted.
- **The labels**: `devin-login-1` stands for the gateway's account marker (an opaque hash). Nothing that names an
  account of the gateway is published; the `accounts` list at the start of the file gives the label's provider, kind
  and priority.
- **Ages**: a control at 30 seconds, then 2.5, 5, 10, 30 and 60 minutes, three samples each; 2 hours only if all three
  60-minute checks were warm (none was, so the 2-hour samples were never primed).

| Age | SWE-2.1 (W1) |
|---|---|
| control (30 s) | 1/1 |
| 2.5 min | 1/3 |
| 5 min | 1/3 |
| 10 min | 0/3 |
| 30 min | 0/3 |
| 60 min | 0/3 |

- **SWE-2.1**: no dependable lifetime. The control read 3,360 of 3,458 tokens from the cache; at 2.5 and 5 minutes one
  check of three read the cache (3,360 and 3,328 tokens) and the other two read nothing; cold in all nine checks from
  10 minutes on. The same pattern as `swe-2` through Pi on 2026-11-08 (control warm, cold from 5 minutes).

## The input window: no edge, read to the end at 282,338 tokens

Devin lists a 262,144-token window. `devin_walk.py` (as on 2026-11-16, unchanged) sent one request about 20,000 tokens
above it, `"Reply with just OK." + " hello" × 282,144`: it was accepted (282,220 tokens as the provider counted them),
so the walk ends there and no larger request is sent. The same filler with a code word before it and one after it
(`--recall`, Responses format, low effort, 256 output tokens) came back as "APRICOT WALNUT" at 282,338 tokens: the
model read the input to the end. That is the row in `observed.json`: `input_accepted` and `input_read` 282,338, no
`input_refused`, the note saying that no edge was found. Rows: `swe-2-1-limits.jsonl`. This script does not record
the answering account; the gateway's model list named only the Devin login for `devin/swe-2-1`, read just before.

**Removed before publication** (`harness/agent_gateway.py publish`): every account marker, replaced by its label. The
files never held a request header's value, a key, a path or a session file: the relay records header names, the
values of limit headers only, and a hash and size of each request body; session ids are `gt-<random>-<age>-<n>`.

Used: 35 answered model requests, none refused. The cache run: 33 requests, 111,972 input tokens (10,048 read from
cache), 1,010 output tokens. The window: 2 requests, 564,558 input tokens. Paid by the subscription, not by the token; no
list price is given for SWE-2.1, and the login's used-up weekly quota did not stop it.

Files: `W1.jsonl` (one Pi invocation or decision per line), `swe-2-1-limits.jsonl`, `run.sh`.
