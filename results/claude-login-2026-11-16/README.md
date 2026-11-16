# Claude login: cache lifetime of Opus, Sonnet and Haiku 5.5, 2026-11-16

Plain probe (`src/cli.ts`, 0.2.0) through a local CLIProxyAPI, Anthropic Messages format, the way the Claude API key
(K1) and OpenRouter (P1, P2) runs were made. The CLIProxyAPI has no plugin, no pools and no aliases; two Claude logins
and two Claude API keys serve the same Claude ids. Every request here went to **Claude login A** (one of the two
logins; the other is not used): each model got a temporary alias on that login only (`probe/<model>`, made with
`harness/pool.py`, removed afterwards). No other login and no API key serves such an id: the API keys serve only the
names they list, and they list none. During the runs the request counters of both Claude API keys stayed at 0 and
those of the other Claude login did not move.

Ages: the control, 2.5, 5 and 7.5 minutes, then 10, 15, 20, 25, 30, 40, 50, 60, 65 and 75 minutes, 3 samples each,
about 4,460-token prompts. `run.sh` started the six runs side by side; `run-haiku-list.sh` started CS7 and CS8 after
them.

| Run | Model | Request | Control | Warm at each age | Lifetime |
|---|---|---|---|---|---|
| CS1 | `claude-opus-5-5` | one `cache_control` marker, no ttl | warm | 3/3 from 2.5 min to 1 h; 0/3 at 65 and 75 min | **1 h – 65 min** (all warm through 1 h) |
| CS2 | `claude-opus-5-5` | the marker with `ttl: "1h"` | warm | the same | **1 h – 65 min** |
| CS3 | `claude-sonnet-5-5` | no ttl | warm | the same | **1 h – 65 min** |
| CS4 | `claude-sonnet-5-5` | `ttl: "1h"` | warm | the same | **1 h – 65 min** |
| CS5, CS6 | `claude-haiku-5-5` | no ttl / `ttl: "1h"` | refused | – | no result (the filler was refused) |
| CS7 | `claude-haiku-5-5` | no ttl, `--filler list` | warm | 3/3 from 2.5 min to 1 h; 0/3 at 65 and 75 min | **1 h – 65 min** |
| CS8 | `claude-haiku-5-5` | `ttl: "1h"`, `--filler list` | warm | the same | **1 h – 65 min** |

Every check ran within 4 s of its age (one at 18 s), none late. The 1-hour checks ran at 3,600.0 – 3,601.9 s and all hit;
every 65-minute check missed completely.

**Without a ttl the login gets the 1-hour cache.** CLIProxyAPI asks Anthropic for it on Claude logins, and the
measurement shows it: a request that only marks the prompt lives exactly as long as one that asks for an hour.
`tier.jsonl` shows the same from the other side: one request per model and setting (a plain numbered list of about
7,650 tokens, `tier_check.py`), and Anthropic's usage puts every written token under `ephemeral_1h_input_tokens`, with
or without `ttl: "1h"`, for Opus, Sonnet and Haiku alike.

**Claude Haiku 5.5 refuses the probe's default filler, so it was measured with another one.** Every prompt with the
default filler (sentences of random words) was answered with a refusal (`stop_details` category `bio`), which
CLIProxyAPI returns as HTTP 400 `claude refusal (bio)`: the controls of CS5 and CS6, a second CS5 with a new salt, and
by hand a third salt and prefixes of 3,000 and 5,000 tokens. Short prompts and the numbered list of `tier.jsonl` were
answered normally. CS7 and CS8 therefore use the probe's `--filler list` (plain numbered sentences about shop opening
hours, added for this; the default filler is unchanged, so earlier runs stay comparable). The filler changes only the
words of the prompt, not how it is cached, so it is not among the run's options in `observed.json`; the result files
name it (`"filler": "list"`). CS5 and CS6 are kept as files (both CS5 attempts) and are not in `observed.json`.
