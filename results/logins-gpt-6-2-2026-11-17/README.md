# GPT-6.2 Sol and Astra on the Codex login, 2026-11-17: the cache lifetime, and the window from a refusal

OpenAI released GPT-6.2 Sol and GPT-6.2 Astra on 2026-11-17. Requests through the owner's local CLIProxyAPI (his
build `ngvoicu-local-4c071f30`, process of 18:38:51 local, configuration of 20:50 with `oauth.excluded-models`), on
the plan of the Codex login (ChatGPT plan). No money was spent; `ledger.md` has what each run used.

**Findings.**

- **GPT-6.2 Sol: warm at 2.5 minutes in 2 of 3, cold from 5 minutes** (0 of 3 at 5 and 7.5 min; the run stopped there).
- **GPT-6.2 Astra: warm in every check from 5 to 30 minutes, misses from 40 minutes, cold from 75 minutes** (2 of 3
  at 2.5 min, 3 of 3 at 5 – 30 min, 2, 2, 1 of 3 at 40, 50 and 60 min, 0 of 3 at 75 and 90 min).
- **Both missed one of three checks at 2.5 minutes, as LC1 and LC3 did this afternoon**, although this time no large
  request went to the login before or during the runs, the two models were not primed at the same moment, and nothing
  else used the login (below). Early misses thus also occurred without a large request before the priming and
  without two models priming at once. That does not rule out every kind of load, and it says nothing certain about
  the misses of LC1 and LC3; the cause is not established.
- **Window: both refused 930,000 tokens** with "Your input exceeds the context window of this model. Please adjust your
  input and try again.", which names no limit. No accepted request was sent, so there is no limits row.

## How the requests reached one account

`gpt-6.2-sol` and `gpt-6.2-astra` are served by the Codex login (`oauth`, priority −17) and by an OpenAI API key
(`apikey`, −25). Every request here used a temporary alias on the Codex login only, `probe/gpt-6.2-sol` and
`probe/gpt-6.2-astra`, set at 23:26:31 local through CLIProxyAPI's management API (`PATCH
/v8/management/credentials/fields`, `model_aliases` with `fork: true`) after a backup of the configuration and the
login folder; `/v1/models?include=accounts` listed only the Codex login for each, and every answer of both runs said
`X-CPA-AUTH-KIND: oauth` (53 and 83, `spent.replyHeaders` in the run files). The aliases were removed at 01:04:50 local
on 2026-11-18, after the window requests; `/v1/models` was then identical to the list saved before them (500 ids, no
`probe/` id), and the backup was deleted at 01:04:56.

**What else used the login.** Its request counter (management API, per login) was 72 at 23:26:50, just before the
first run, 181 at 23:40:53, 193 at 00:05:59 and 208 at 01:04:36 after both runs: +136, exactly the 53 + 83 answered
requests of GS1 and GA1. Nothing else was answered by the login meanwhile, and the OpenAI API key's counter stayed at
0. The two window requests then added 2 failed requests and nothing else.

## Cache lifetime (GS1, GA1)

Made as LC1 and LC3 (`../logins-2026-11-17`): the plain probe (0.3.3 here, 0.3.1 there; the request is the same),
Responses format with a per-sample `prompt_cache_key`, a 2,500-token prefix, the standard schedule (2.5 minutes to
2 hours, stopping after two fully cold ages), 3 samples per age, a control first, 2 primes at a time with no pause,
`--stop-on-refusal`, nothing asked about caching. Two differences on purpose: no large request before or during the
runs (LC1 – LC4 followed three 921,500-token window requests by one to two minutes), and Astra started only after Sol
had logged `priming done` (sequence.py; Sol primed 23:26:57 – 23:27:48, Astra 23:28:00 – 23:29:15), where LC1 – LC4
primed side by side.

| Run | Model | Control | Warm / checks per age (2.5, 5, 7.5, 10, 15, 20, 25, 30, 40, 50 min, 1 h, 75, 90 min, 2 h) | Warm through | First miss | First all cold |
|---|---|---|---|---|---|---|
| GS1 | `gpt-6.2-sol` | hit (2,432 / 2,694) | 2, 0, 0 (stopped) | – | 2.5 min | 5 min |
| GA1 | `gpt-6.2-astra` | hit (2,688 / 2,750) | 2, 3, 3, 3, 3, 3, 3, 3, 2, 2, 1, 0, 0 (stopped) | – | 2.5 min | 75 min |
| LC1 (this afternoon) | `gpt-6.1-sol` | hit (2,432 / 2,642) | 2, 3, 1, 2, 2, 2, 3, 3, 2, 2, 0, 1, 2, 2 | – | 2.5 min | 1 h |
| LC3 (this afternoon) | `gpt-6-astra` | hit (2,560 / 2,711) | 2, 3, 2, 2, 3, 2, 3, 1, 2, 2, 1, 3, 3, 1 | – | 2.5 min | – |

"Warm through" is the oldest age through which every check hit; a miss at 2.5 minutes makes it none for all four.
GA1 is warm in all 21 checks from 5 to 30 minutes and then fades; GS1 is gone by 5 minutes. A miss is total: every
cold check read 0 tokens from cache. The latest check ran 6.4 s after its age; none was late or failed.

## Window (`window.py`, `limits-codex.jsonl`)

One request per model, after both runs had ended (01:04 local, 2026-11-18): the request of
`../logins-2026-11-17/window_walk.py` ("Reply with just OK." + " hello" × N, Responses, low effort, a 16-token
reply) at N = 929,989, 930,000 tokens with the login's 11-token overhead, clearly above the 922,300 tokens at which
GPT-6.1 Sol, GPT-6 Astra and GPT-6 Luna were refused this afternoon (921,500 accepted). Both answered 400 in under
3 seconds: "Your input exceeds the context window of this model. Please adjust your input and try again." It names no
limit. No smaller request was sent. A limits row needs an accepted size beside a refused one, so the two rows are in
`excluded` with this reason; they show only that the window is below 930,000 tokens. models.dev's `openai` entries
give both models a 922,000-token input (1,050,000 context).

## Where the rows land

The manifest names the models `gpt-6.2-sol` and `gpt-6.2-astra` on route `codex-subscription` (provider
`openai-codex` on providers.dev), `base_model` `openai/gpt-6.2-sol` / `openai/gpt-6.2-astra`. models.dev
(experimental v2 API, what the site imports; read 2026-11-17 23:29 local) lists only `gpt-6.1-sol` and
`gpt-6.1-terra` under `openai-codex`, and both new models under `openai`. The site adds an entry for a model
measured on a mapped route that models.dev does not list (`site/src/core/resolve.ts`, "Models that exist only
because we measured them"), filled from the `base_model`, as it did for `openai-codex/gpt-6-astra` and `gpt-6-luna`,
so the rows make the entries `openai-codex/gpt-6.2-sol` and `openai-codex/gpt-6.2-astra`.

## Files

- `GS1-…json` / `.md`, `GA1-…json` / `.md`: the runs (probe 0.3.3; `spent.replyHeaders` has the `X-CPA-AUTH-KIND` of
  every answer).
- `limits-codex.jsonl` (`window.py`): the two window requests.
- `manifest-entries.json` (`make_entries.py`, `excluded-window.json`): 2 runs, 1 excluded entry.
- `ledger.md`, `run.sh`, `sequence.py` (one run priming at a time), `status.py` (`logs/status.md`); `logs/` stays local.
