# Contributing a measurement

Anyone can contribute a measurement, providers included. providers.dev takes no payment for listing, correcting or
measuring. A result is published whatever it shows.

A measurement accepted here appears on [providers.dev](https://providers.dev) on the entry it was taken on: the
provider, the way of access (an API key, a subscription) and the model. The site's side of this is at
<https://providers.dev/docs/contributing/>.

## Measure with your own key

You need Node 22.19 or later and Python 3. No proxy is needed: send the requests straight to the provider.

```bash
git clone https://github.com/ngvoicu/groundtruth && cd groundtruth
npm install
git config core.hooksPath scripts                       # the check that blocks credentials, once per clone
export CACHE_PROBE_KEY=...                               # your key: never on the command line, never in a file
```

**How long the prompt cache lives.** Look at the plan and the request body first. The dry run sends nothing:

```bash
node src/cli.ts --base-url https://api.openai.com/v1 --model gpt-6.1-sol --label openai-sol --dry-run
```

Then run it. A run takes about two hours with the default schedule. Keep the computer awake:

```bash
node src/cli.ts --base-url https://api.openai.com/v1 --model gpt-6.1-sol --label openai-sol \
  --out results/openai-api-2026-11-20
```

For Anthropic's API, add `--format messages`. For a setting that changes caching, add it with `--ttl` or
`--body-extra`, and run the default the same day for comparison. The run file records what was sent.

**How much input a request can carry.** A refused request is free. Only accepted ones cost quota:

```bash
python3 harness/limits.py --base-url https://api.openai.com/v1 --model gpt-6.1-sol --format responses \
  --lo 900000 --hi 930000 --out results/openai-api-2026-11-20/limits.jsonl --dry-run
```

Run it again without `--dry-run`. `--hi` must be refused and `--lo` accepted. Each request is written to the
`--out` file, with the provider's own token count for each accepted one.

**Through a subscription's own client** (Claude Code, Codex CLI, Devin CLI, Muse Code): `harness/probe.py --harness
<client>`, with a state folder of the client's own that you logged in once (`--client-home`), never its everyday
folder. `--dry-run` shows the commands and the environment the client gets, and sends nothing. The README, section
"Through a vendor's own client", and [`docs/own-clients.md`](docs/own-clients.md) say how. Never commit the state
folder or a client's session files; the pre-commit check refuses them.

## What a pull request contains

1. **The raw result files** under `results/<folder>/`, for example `results/openai-api-2026-11-20/`: the `.json` and
   `.md` of every run, the `limits.jsonl` of a walk. Include runs that failed or that you leave out.
2. **A short `README.md` in that folder**: what was measured, how (route, client, the commands), on which day, and
   what came out. Say what went wrong, if anything did.
3. **The run in [`observed/manifest.json`](observed/manifest.json)**: route, client, model and options. Nothing
   that is a result: the script computes the results from the raw files. A cache run looks like this:

   ```json
   {
    "id": "openai-api-2026-11-20/openai-sol",
    "file": "results/openai-api-2026-11-20/openai-sol-2026-11-20T09-00-00.json",
    "route": "openai-api",
    "client": "direct",
    "model": "gpt-6.1-sol",
    "models_dev": "openai/gpt-6.1-sol",
    "base_model": "openai/gpt-6.1-sol",
    "options": {}
   }
   ```

   A limits row has the numbers and the raw rows that back them (`evidence`). See the rows already in the manifest,
   and the fields in the README, section "observed.json". A route that is not in the list in
   `scripts/build_observed.py` is added there, in the same pull request.
4. **A run you leave out** goes in `excluded`, with the reason. Nothing is left out silently.
5. **`observed.json` rebuilt**: `python3 scripts/build_observed.py`.

## What is checked

- **The pre-commit check** scans every file to be committed. It refuses a credential (your `CACHE_PROBE_KEY` and
  anything shaped like a token, and the values of `META_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN` when they are set), an
  e-mail address, a home-folder path (`/Users/<name>/`, `/home/<name>/`), a session file of a coding agent and a
  client's state folder. Run it on a results folder before you add it:
  `python3 harness/scan_secrets.py results/<folder>`.
- **CI** runs the tests, the same scan, and rebuilds `observed.json` from the raw files and compares it with the one
  in the pull request. The build refuses a run or a row that contradicts itself or its raw files.

## What makes a run acceptable

- **The control hit.** The prompt sent again at once was served from the cache. Otherwise the run shows nothing
  about the cache's lifetime.
- **Through an own client:** at least one reply reported a cached token (otherwise the run goes in `excluded`), and
  the run file records the client's version and its isolation (`harness/probe.py` writes both).
- **The usual samples.** Three per age, the schedule starting at 2.5 minutes (the default). Fewer only with a reason
  in the README.
- **Nothing excluded silently.** Every run you made is in the folder. A run left out is in `excluded` with its reason.
- **For a limit:** an accepted size and a refused one from the same walk, or a window the provider's own error names.
  A size that was accepted and never refused counts only up to the largest input the reply showed was read to the end
  (a word before the filler and one after it, both returned).

## What a measurement can't tell

- **Small samples.** A few requests at each age or size, on one day.
- **One account.** Another plan, region or account can have another limit or another cache.
- **Dated.** A provider can change a limit or its cache the next day.

## After the pull request

groundtruth has one maintainer. There is no promised response time. A run that meets the checks above is merged, and
providers.dev shows it once it next reads `observed.json`.

A question, a measurement to ask for, or a fault in the tool goes in an
[issue](https://github.com/ngvoicu/groundtruth/issues). For anything that does not fit an issue, write to
office@providers.dev.
