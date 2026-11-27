# groundtruth

The measuring tool behind [providers.dev](https://providers.dev): how long an LLM prompt cache really lives, and how
large the limits really are, per endpoint, model and route. It was called `cache-ttl-probe` until November 2026.

Providers rarely publish how long a cached prompt prefix survives, and when they do it's a range ("5 to 10 minutes
of inactivity") or it only holds on their own API, not through a proxy, a reseller or a subscription backend. Agents
that keep caches warm (or that decide when a pause will cost a full re-write) need a number. This tool measures it.

- Chat Completions, Responses and Anthropic Messages formats
- Optional explicit Anthropic `cache_control` ttl (`5m` / `1h`), extra headers and body fields
- Works against any base URL: vendor APIs, OpenRouter, or a local proxy such as Provimux (a distribution of CLIProxyAPI)
- No runtime dependencies, Node ≥ 22.19, MIT (TypeScript is a build-time dependency only)

## Quick start

```bash
# run straight from GitHub (or: git clone, npm install, node src/cli.ts …)
export CACHE_PROBE_KEY=sk-...           # never passed on the command line, never printed

# OpenAI-style Responses endpoint, default schedule (2.5 min → 2 h)
npx github:ngvoicu/groundtruth --base-url https://api.openai.com/v1 --model gpt-6.1-sol

# Anthropic, explicit 1-hour cache: the first ages of every run, then 30 and 65 minutes
npx github:ngvoicu/groundtruth --base-url https://api.anthropic.com/v1 --format messages --model claude-opus-5-5 \
  --ttl 1h --ages 30m,65m

# Through a local proxy, long schedule (adds 4 h, 8 h, 12 h)
npx github:ngvoicu/groundtruth --base-url http://127.0.0.1:8317/v1 --model gpt-6.1-sol --schedule long

# Show the plan and the request body without sending anything
npx github:ngvoicu/groundtruth --base-url http://127.0.0.1:8317/v1 --model m --dry-run
```

Each run writes `results/<label>-<timestamp>.json` (every check) and `.md` (survival table), and keeps a
`.partial.json` up to date while it runs.

From version 0.3.0 both files also say what was sent (`request` in the `.json`): the path, `--body-extra` as given,
the prefix size, max output, streaming, the cache key and session id settings, every header by name, and the body of
one request with the prefix as a placeholder. The format and ttl are at the top of the file, and the filler when it
is not the default. A header's value is written only for `content-type`, `anthropic-version` and `anthropic-beta`;
the key and any other header are named, never written. `--dry-run` prints the same record.
`scripts/build_observed.py` refuses a run whose recorded extra body fields are not in its options in the manifest.
Older files have no `request`.

```
**Lifetime: 5m – 10m**

| Age | Warm | Checks |
|---|---|---|
| 2.5m | 3 | 3 |
| 5m | 3 | 3 |
| 7.5m | 1 | 3 |
| 10m | 0 | 3 |
```

`5m – 10m` reads "every replica was warm at 5 minutes, none at 10". Schedule warming against the lower bound.

## Method

1. **Control round.** Prime a fresh prefix and re-send it immediately. If the re-send isn't served from cache, the
   endpoint has no observable cache for this request shape and the run stops (`no-observable-cache`).
2. **Prime every sample once.** One sample per (age, replica), each with its own prefix, all primed up front.
3. **Check each sample exactly once**, when it reaches its age. Never poll one prefix: most caches restart their timer
   on every hit, so polling measures how long your own polling keeps the entry alive.
   From 0.3.5 a check, and the control's re-send, is sent once: a failed one is recorded as an error and never
   sent again, because a first try that reached the model would make the second read what it wrote. A priming may
   still be retried.
4. **Warm** = at least half of the prompt and at least 500 tokens reported as cached.
5. **Stop** after two consecutive ages where every replica is cold.

Ages are measured from the *start* of the priming request (Anthropic counts the lifetime from the start of the request
that wrote the entry). Each result records the actual age of every check, so late checks (sleeping laptop, retries)
are visible.

**Every evaluation starts the same way.** The prompt is sent again at once (the control: it shows that the prompt was
cached at all and that the route reports cache hits), then checked at 2.5, 5 and 7.5 minutes, and on from there:

| Schedule | Ages |
|---|---|
| `std` (default) | 2.5, 5, 7.5, 10, 15, 20, 25, 30, 40, 50 min, 1 h, 1 h 15, 1 h 30, 2 h |
| `long` | `std`, then 4 h, 8 h, 12 h |
| `quick` | 2.5, 5, 7.5, 10 min |

`--ages` adds ages to that start, it does not replace it: `--ages 30m,65m` checks at 2.5, 5, 7.5, 30 and 65 minutes.
A cache that is gone inside five minutes only shows in the first ages, and two results can only be compared when they
share them. `harness/probe.py` (the same evaluation through a real coding tool) has the same schedules, and
`scripts/build_observed.py` refuses a run dated 14 November 2026 or later that has no control or does not start at
2.5 minutes. A run whose every control missed has no ages by the method and is accepted as it is; the rule reads the
run's own control, so a run with a mixed control (one re-send hit, another missed) showed the cache and must go on to
its ages like one whose control hit. A run that continues another is not held to the rule. Runs before that date keep
the ages they were made with. A run of `harness/agent_gateway.py` (below) may instead have ages planned around the
lifetimes the provider documents; its manifest entry says so in `first_ages`, and its youngest age is published as it
is (providers.dev shows it as `tested_from_s`).

Options: `--schedule std|long|quick`, `--ages 30m,65m`, `--replicas 3`, `--prefix-tokens 2500`, `--filler words|list`, `--max-output 16`,
`--stream`, `--ttl`, `--beta`, `--header k:v`, `--body-extra '<json>'`, `--label`, `--salt`, `--out`,
`--stop-on-refusal`, `--prime-pause <ms>`, `--usage-log <file>` (one JSON line per reply with the usage as reported,
for a cost ledger; from 0.3.4 also the upstream an aggregator such as OpenRouter names in its reply (`reply_provider`),
the reply's id and the sample's cache key or session id (`sample`), so that a check can be paired with its priming),
`--record-header <name>`. See `--help`.

`--stop-on-refusal` (from 0.3.1) ends a run at the first quota or rate refusal (HTTP 429, from 0.3.4 also HTTP 402,
OpenRouter's answer when the credit or a key's limit is used up, or an answer that names a quota, usage, credit or key
limit) instead of retrying it: for a subscription whose quota must not be pressed again. From 0.3.1
every run file also sums what its answered requests used (`spent`: requests, prompt, cached and output tokens as the
replies report them). `--prime-pause` (from 0.3.2) waits after each priming request, for a request-rate limit; with
`--concurrency 1` the priming then sends one request at a time, and the log says when it is done (`priming done`).
From 0.3.3 every run file records, for every answered request, the value of CLIProxyAPI's reply header
`X-CPA-AUTH-KIND` (`oauth` for a login, `apikey` for an API key: the kind of credential that answered): per check
(`replyHeaders`), for the control, and counted over the run (`spent.replyHeaders`; a reply without it counts as
`(absent)`). `--record-header <name>` records other reply headers instead; one that can carry a credential is refused.

### Through a vendor's own client

A login (a Claude, ChatGPT, Devin or Muse Code subscription) is measured first through the client its vendor ships,
driven as its user drives it; a proxy only where no own client can be scripted. The design is
[`docs/own-clients.md`](docs/own-clients.md). `harness/probe.py` runs the same evaluation through Claude Code
(`--harness claude`), Codex CLI (`codex`), Devin CLI (`devin`) and Muse Code (`muse`); `harness/clients.py` says how
each is driven and where its output shows cache reads, cache writes, the number of model requests and a refusal.
Each sample is a new session whose first message carries a block no other sample has; after its age the session is
resumed once with a short message. A check is warm when the cache covers the client's own prompt and at least half of
the block. Four rules hold for every client:

1. **One model request per check.** A turn that made two (a tool call, then the answer) is `check-invalid` and left
   out: the second request reads what the first wrote.
2. **A check is never sent twice.** One that fails is `check-failed`; its sample is lost.
3. **The control first.** It is checked at 30 seconds before any other sample is primed; a miss ends the run.
4. **A quota refusal ends the run**, never retried.

A run is kept apart from the owner's everyday use: each client has a **state folder** of its own
(`--client-home`, one subfolder per client id, logged in once there; the probe refuses the client's everyday folder),
works in a **new empty folder** under the system's temporary folder, and gets a **short environment** (`PATH`, `HOME`,
`USER`, `LANG`, `TERM`, `TMPDIR`, its folder's variables, and what the run sets with `--client-env`): no API key, base
URL, proxy or cache switch of the caller's shell reaches it. The run file records the client's version and
`isolation`, never a path. `--dry-run` prints the commands and sends nothing.

On macOS each client process runs under `sandbox-exec`: no file write under the home folder outside its state folder,
its throwaway home and its temporary folder. An age's samples are primed in three waves, two replicas of an age at
least five minutes apart; the Devin CLI runs in-process with its cache keepalive
off; Claude Code's own retries are switched off. Every new session's first line names the measurement.

`harness/client_limits.py` walks an input size through the same clients. It is **not yet trusted**: no own-client
input limit is published, and a login's input limits stay the proxy's. `harness/night.py` holds the run plan of
[`docs/own-clients.md`](docs/own-clients.md), section 4, as commands; `--dry-run` prints each one with its tool's own
dry run and sends nothing, and nothing is sent without `--go`. The first night is the cache runs of Codex CLI and Devin
CLI only; after the smoke runs, `--go <client>` (or `--go all`) starts a client's runs in the background under one
lock per client (`status`, `stop <client>|all`). [`docs/own-clients-RUN.md`](docs/own-clients-RUN.md) has the steps: the
owner's one-time setup, the night, the morning.

### A real coding agent through a gateway

What a coding agent gets through a gateway is often not what the provider's own client gets: the gateway adds its
own prompt, asks for its own cache lifetime, and may hand a conversation to another account when one is overloaded.
`harness/agent_gateway.py` measures that lifetime the way a real agent meets it, Pi through Provimux, and proves for
every request **which account answered**: Provimux names it in a reply header (`X-Provimux-Account`, an opaque
marker), and a sample counts only when one login of the intended kind answered both its priming and its check. Every
other sample is kept in the file and marked, never dropped. It replaced the Pi client that `harness/probe.py` had
until 22 November 2026, with the same method (a new session per sample, resumed once after its age).

```bash
export PROVIMUX_API_KEY=...       # the gateway's client key: read from the environment, never printed or written
python3 harness/agent_gateway.py --model claude-fable-5-2 --login claude --ages 4,6,30,55,65 \
  --scratch <new folder> --extension <pi-provimux package> --outfile <raw>/F1.jsonl \
  --budget 3 --price-in 8 --price-cached 0.2 --price-write 16 --price-out 40
python3 harness/agent_gateway.py publish --out results/<folder> <raw>/F1.jsonl   # markers become labels
```

A run stops at the first answer from an API key (a paid route), at any quota, limit or overage sign, and at its
list-price budget; two runs on one login never overlap. `publish` replaces each account marker by a neutral label
(`claude-login-1`) in every file it is given, so nothing that names an account of the gateway is published.

Its limits: one gateway, one agent and one account per login, small samples; Pi runs over SSE (the relay reads each
answer's headers), so a Codex model is not measured over the WebSocket Pi can use; and the ages are planned around
the documented lifetimes, not from 2.5 minutes, so a run says nothing about the ages it did not check. The first
runs are in [`results/agent-gateway-2026-11-27/`](results/agent-gateway-2026-11-27/README.md).

## observed.json

Everything measured so far, in one file: [`observed.json`](observed.json). providers.dev reads it once a day and
shows each run on the entry it belongs to. Raw results are in `results/`
(see [`results/SUMMARY.md`](results/SUMMARY.md) for the story of each run).

```bash
curl -s https://raw.githubusercontent.com/ngvoicu/groundtruth/main/observed.json
```

It holds what catalogs such as [models.dev](https://models.dev) can't: values **as measured**, including
subscription routes that have no public API (a ChatGPT plan through Codex, Devin, a Claude login, a Muse Code key).

- **`client_kinds`** and **`route_kinds`**: what each client and route is. A client is `direct` (plain requests to
  the route's own address), `own_client` (a client the route's vendor ships) or `proxy` (anything through a proxy);
  a route is `api_key` or `login`. providers.dev applies the rule: on an `api_key` route only `direct` runs count; on
  a login, for one value, the lowest kind present (`direct`, then `own_client`, then `proxy`). Every other run stays in
  the file and is shown as measured. An own client measures only its vendor's login (`claude-code` only
  `claude-subscription`, and so on); the build refuses anything else.
- **`cache`**: one entry per run. `route` (whose account), `client` (what sent the requests), `model` (the id on that
  route), `options` (anything that changes caching: an explicit ttl, a retention setting, reasoning level) and
  `checks`, the raw counts per age: `{ "age": "30m", "age_s": 1800, "warm": 3, "total": 3 }`. A run of
  `harness/probe.py` adds `written_ttl` (`1h` or `5m`)
  where the client reports the lifetime of its cache writes (Claude Code); a run whose writes are mixed, or whose
  options ask a ttl its writes do not show, is refused. An own-client run in which no reply reported a cached token
  measured nothing: it goes in `excluded`, never in `cache`.
- Three numbers summarise a run, all in seconds, `null` when there is none:
  `all_warm_through_s` (every age up to here was fully warm: **the safe value**), `last_warm_s` (the oldest age with
  any warm check) and `first_all_cold_s` (the youngest age with none). When `last_warm_s` is past
  `first_all_cold_s`, the route misses at random rather than by age.
- `control` is an immediate re-send, counted like a check (`warm` of `total`); `0/1` means that the re-send was not
  served from cache by the probe's rule (at least half of the prompt and 500 tokens), which shows no lifetime: a run
  with nothing else says nothing about how long a cache lives. `late_excluded` counts checks that ran too long after
  their age and were left out.
- `latest` marks the newest run for the same route, client, model and options. Older runs stay in the file.
- `continues` names an earlier run that this one adds checks to: older ages, or more samples of an age (same route,
  client, model and options). Its `checks`, its `control` and its three summary numbers then cover that run too, and
  any run that one continues: every run's own control counted once, outcomes kept as they are (a chain whose first
  control hit and whose second missed has `1/2`); `source` is the file with its own checks.
- `removed_by_proxy` (from 2026-11-17): body fields the client sent (the run file records them) that are shown not
  to reach the provider on that route and build, because the proxy deletes them. `options` hold what the provider
  received, so such a field is not in `options` and asks for nothing; the run's `note` must give the proof (the
  proxy's source, and requests showing it). `build_observed.py` accepts a recorded field only when it is in
  `options` or here with the same value, and refuses this key without a note.
- `answered_by` and `not_counted` (runs of `harness/agent_gateway.py`, from 2026-11-27): the labels of the accounts
  that answered the run's counted checks (`claude-login-1`: a label standing for the gateway's account marker, never
  the marker), and how many checks the run did not count (answered by another account, more than one model request,
  or no answer). `first_ages` says why such a run's ages do not start at 2.5 minutes.
- `requires` / `lacks` name a CLIProxyAPI change the run had or did not have yet (for OpenRouter, the cache markers
  and session id of router-for-me/CLIProxyAPI#7284). A reader on a build with that change should skip `lacks` runs.
- `models_dev` is the matching entry in models.dev (`provider/model`) when that route exists there, and
  `base_model` is the model's id in its `models/` folder; either can be `null`.
- **`limits`**: context and output limits found by sending requests of growing size. One row per route, client and
  model; a new walk replaces the row. Every number is in tokens and is backed by a row of the raw file named in
  `source`:
  - `context`: the window, only where the route's own answer names it (an error message). A window from a vendor's
    model list stays in `note`. `output`: the output cap, likewise.
  - `input_accepted`: the provider's count of the largest request it answered.
  - `input_refused`: the smallest refused request, counted the same way. Where the refusal states a count, that
    count; otherwise the probe's size converted with the tokens per word and the overhead of the accepted requests of
    the same walk (the note says which). A row with `input_refused` always has `input_accepted`, below it.
  - `input_read`: the largest input for which the reply showed it was read to the end (a word before the filler and
    one after it, both returned). Never above `input_accepted`. It gives a value to an accepted size with no
    refusal and no named window.
  - `output_accepted`: the largest output cap a request was answered with.
  - `date`: the day the requests were sent (`YYYY-MM-DD`). `note`: what the numbers do not say.

  No own-client row is published for now; when they are, a row needs `context` or `input_refused` from the
  provider's own refusal, and only rows its own client wrote back it.

  `scripts/build_observed.py` refuses a row that providers.dev would refuse: two rows for one route, client and
  model, a refusal without an accepted size, an accepted size not below the refused one or above the named window,
  `input_read` above `input_accepted`, a count that is not a whole number of 0 or more, a number its raw rows don't
  show, or a conversion that the accepted requests don't fit.
- **`known`**: lifetimes that were **not measured** but follow from how a client or proxy builds its requests
  (for example Provimux asking Anthropic for the 1-hour cache on Claude logins). Each has `ttl_s`, a `basis` in
  words and a `source`; `model` is `*` when it holds for every model of the route, and `when` narrows it to a
  setting.
- **`excluded`**: runs left out, and why.

Small samples (2 to 5 per age), one account per route, dated: treat them as observations, not guarantees.

Before the first commit in a clone, install the check that blocks credentials, home-folder paths and session files:
`git config core.hooksPath scripts` (relative: every worktree of the clone runs its own `scripts/pre-commit`).

To add a run: publish its files under `results/`, add it to [`observed/manifest.json`](observed/manifest.json)
(route, model, options: nothing that is a result), then run `python3 scripts/build_observed.py`. CI fails when
`observed.json` doesn't match the raw files.

## listed.json

What each of the owner's logins offers, read daily from his Provimux (the vendors' own model lists, no account):
`listed.json` at the repository root (once discovery runs), written by `harness/discover.py`. providers.dev publishes it as each provider's model
list. [`docs/discovery.md`](docs/discovery.md) has the rules and the schema.

## Contributing a measurement

Anyone can contribute a measurement, providers included. providers.dev takes no payment for listing, correcting or
measuring: a result is published whatever it shows. An accepted run appears on providers.dev on the entry it was
taken on. [CONTRIBUTING.md](CONTRIBUTING.md) has the commands and the checklist.

- **Measure with your own key**, straight against the provider. No proxy is needed. Run `--dry-run` first: it shows
  the plan and the request and sends nothing. Then run without it, with `--out results/<folder>`. For input limits,
  `python3 harness/limits.py --base-url <url> --model <id> --format <f> --lo <N> --hi <N> --out <file> --dry-run`.
- **A pull request contains** the raw result files under `results/<folder>/` with a short README, the run in
  `observed/manifest.json` (route, client, model and options, nothing that is a result), and `observed.json`
  rebuilt by `python3 scripts/build_observed.py`.
- **What is checked**: the pre-commit scan (no credential, e-mail address, home-folder path or session file), and CI,
  which runs the same scan and rebuilds `observed.json` from the raw files and compares.
- **A run is acceptable** when its control hit, it has the usual samples per age (three, from 2.5 minutes), and
  nothing was left out silently: a run you leave out goes in `excluded` with its reason.
- **A measurement has limits**: small samples, one account, one day.

One maintainer, no promised response time. For anything that does not fit an issue: office@providers.dev.

## Pitfalls

- **Minimum cacheable length.** Below it, nothing is ever cached (OpenAI 1,024 tokens; Anthropic 512–4,096 depending on
  the model). The default 2,500-token prefix plus whatever the proxy adds clears most minimums; raise
  `--prefix-tokens` if the control round fails.
- **A model may refuse the filler.** The default filler is sentences of random words; Anthropic refused it on Claude
  Haiku 5.5 through a Claude login (`stop_details` category `bio`, returned by Provimux as HTTP 400
  `claude refusal (bio)`). `--filler list` uses plain numbered sentences instead. The filler does not change caching,
  and the default stays as it was, so earlier runs remain comparable; a result file names the filler when it is not
  the default.
- **A missing cached-tokens field counts as 0.** Some endpoints omit it instead of reporting 0.
- **Prefixes are salted per run.** Re-running immediately never hits the previous run's cache.
- **Anthropic caches only marked content.** `messages` runs always mark the prefix; proxies that translate other formats
  to Anthropic must add markers themselves (a failing control round tells you they don't).
- **Aggregators can split caches** across upstream providers. Pin the upstream (or a single credential behind a proxy)
  for meaningful results.
- **A lifetime is a curve.** Report the bracket, not a single number; run 3+ replicas.
- **An own client decides things by itself.** Claude Code asks for the 1-hour cache inside a plan's included usage
  and the 5-minute one in overage (a run whose writes change lifetime ends, `tier-changed`); start a Claude run when
  the plan's meter is low. Codex CLI caps a message at 1,048,576 characters. Devin CLI reported no cached token for
  some models whose cache the same account showed through the proxy: such a run measured nothing. Muse Code cached
  only its own system prompt on 7 November: its 0 is what that client gives. A client's quota is the account's,
  shared with its owner's own work.
- **Never an own client's everyday folder.** A state folder holds the client's login and every session; it is never
  committed (the pre-commit scan refuses a state folder and a client's session files), and never the folder the
  owner works in.

## Credits

The single-check-per-prefix method follows the measurement write-up
["How long does a prompt cache live? Measured TTLs for 11 LLM endpoints"](https://gist.github.com/monperrus/9784f52d5144975fd11be7f642c4a8fc).
This is an independent implementation.

## License

MIT
