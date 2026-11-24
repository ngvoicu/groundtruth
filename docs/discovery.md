# Daily discovery: `listed.json`

Every day at 22:30 the owner's Mac writes what each of his logins' vendors offers into `listed.json` at the root of
this repository on GitHub, and providers.dev publishes it as the provider's model list (`/api/v1/listings`) at its next
daily sync. The design is section 9.1 (way A) of Provimux's `model-lists.md`; this is step G1 of its section 10.

## What the command does

`python3 harness/discover.py` (its docstring has every rule):

- **One local request**: `GET /v8/management/provimux/model-lists?view=live` to the owner's Provimux on this Mac
  (Provimux 8.1.1-pmx.2 or later). A URL that is not loopback is refused, and the request goes through an opener with
  no proxy and no redirect (a redirect is an error), so the management key never leaves this Mac. The key is found as
  `harness/pool.py` finds it and is never printed or written. **Nothing is sent to a vendor** and nothing is spent.
- **Only the vendor's list**: per login, `live_list` (the vendor's answer as it arrived, unmerged), only while Provimux
  holds it (`live.held`). From an entry only its id, name, window, output limit, modalities and reasoning levels.
- **No identity**: a model whose id or name contains a login's label, e-mail (or its local part), file name (or its
  stem), `auth_index` or the management key, without regard to case, is dropped; the log says a model was dropped,
  never the value. Values of 3 characters or fewer and names of providers and services (`SERVICE_WORDS`: a login
  labelled "Devin") drop nothing.
- **Per listing**: Claude login → `claude-subscription`, Codex → `openai-codex`, Antigravity → `antigravity`, Devin →
  `devin` (Devin's own ids, without Provimux's `devin/`), Meta login → `meta-subscription`.
- **A provider changes only on a complete day**: when every enabled login of its type has a held live list. Their
  lists are joined (the union; a field two logins state differently is left out; the date is the oldest list's).
  Otherwise, and when no login of the type answered, yesterday's part stays as it was, date included, and the log says
  how many logins lacked a list.
- **Refused before it is written, as providers.dev would refuse it**: the schema (`harness/listed_schema.py`, the
  site's `ListedFile` or stricter, with its safe-integer bounds), more than 8 MiB, the key anywhere in the text, or more
  than 40 % of the providers or models lost against the file it replaces (with `--publish`: GitHub's).
- **Ages**: every provider's age goes to `$G/discovery.log`. A provider older than 3 days is an ask: an `ASK:` line in
  the log and in the command's last words.
- **One run at a time**: a lock in `$G` (`discovery.lock`) makes a second run exit at once.

Without `--publish` it writes `--out` (default: `./listed.json`) and commits nothing.

### `--publish`: discovery's own clone, never the main checkout

- Discovery keeps its own clone of groundtruth at `$G/discovery-repo`, made from GitHub (`upstream`) on first use.
- Each run: `git fetch upstream`, `reset --hard upstream/main`, `clean -fdx`; it writes `listed.json` there and stops
  when it equals GitHub's.
- Otherwise `harness/scan_secrets.py` must pass on the file, and `listed.json` alone is committed, as
  `groundtruth discovery <office@providers.dev>` (never the Mac's own Git identity), through the clone's commit hook,
  and pushed with `git push upstream HEAD:main`, never forced.
- A refused push is redone once from a fresh fetch; a second refusal is exit 1. Nothing is left over: the next day
  starts again from GitHub.
- `--out` is refused with `--publish`; the checkout the command runs from is never written.
- **GitHub only.** The NAS copy follows GitHub by itself (`.forgejo/workflows/follow-github.yml`), so discovery
  never pushes to it. providers.dev reads GitHub.

CI checks the committed file (`python3 harness/listed_schema.py listed.json`), and so does the commit hook.

## Login types left out, and why

- **Copilot, for now.** Provimux 8.1.1-pmx.2 puts every model of the account's answer into the status endpoint's
  list, also the ones the account does not offer: `sdk/cliproxy/provimux_live_copilot.go` lines 70–71 append each
  model to `entry.models` before line 72 tests `provimuxCopilotOffered` (disabled by policy, hidden from the picker,
  embedding models, no chat endpoint), and `sdk/cliproxy/provimux_model_list_status.go` lines 91–99 put every one of
  them on the wire; lines 102–110 of the first file also give every model `TEXT` modalities the account did not state.
  models.dev covers Copilot (`github-copilot`). It comes back with one line in `LISTINGS` once Provimux lists only the
  offered models.
- **Kimi** (Provimux does not ask it yet, `model-lists.md` 13.4), **xAI**, **Gemini keys**, **Vertex** and
  **AI Studio**: their listings come from models.dev (`model-lists.md` 4.1).

**Antigravity's caveat.** Provimux keeps one description per model id for all Antigravity logins
(`sdk/auth/provimux_antigravity_models.go` lines 49–60: each answer overwrites the shared map), and the status endpoint
reads that same description for every login (`sdk/cliproxy/provimux_model_list_status.go` lines 109–115). So two
logins that state different windows arrive as one value, the newest answer's: the join cannot see the disagreement,
and the window written is the last login's to answer. The ids are each login's own.

## The Monday night

**Requirement for the weekly night (branch `weekly-night`, not merged): `harness/weekly.py night` must run
`python3 harness/discover.py --publish` as its first step, before planning (design 9.1), and plan from the file it
wrote.** Until then the night plans from the `listed.json` of its checkout. A stale provider is, for now, only the
`ASK:` line in the log and the exit message.

## The file

```json
{
  "schema": 1,
  "repository": "https://github.com/ngvoicu/groundtruth",
  "providers": {
    "devin": {"date": "2026-11-24", "client": "provimux", "models": [
        {"id": "gemini-4-neon", "name": "Gemini 4 Neon", "context_window": 1048576, "max_output": 65536, "input_modalities": ["text", "image"], "reasoning": {"levels": ["low", "medium", "high"]}}
    ]}
  }
}
```

`date` is the day the oldest joined list was read; `client` is `provimux` (providers.dev's measurement labels). A
field the vendor's list does not state is left out, never guessed.

## Once, with the owner's OK

```bash
export GROUNDTRUTH_CLIENT_HOME="$HOME/groundtruth-clients"      # exists, mode 700 (the night's folder)
# 1. a first run by hand: reads his Provimux, writes $G/listed.json only, commits nothing
python3 harness/discover.py --out "$GROUNDTRUTH_CLIENT_HOME/listed.json"
# 2. the first publication by hand: makes $G/discovery-repo from GitHub, pushes listed.json to GitHub's main
python3 harness/discover.py --publish
# 3. the agent, daily at 22:30 (a run missed while the Mac slept runs when it wakes)
scripts/install-discovery.sh --print --publish        # shows the plist; changes nothing
scripts/install-discovery.sh --owner-ok --publish     # writes and loads ~/Library/LaunchAgents/dev.providers.groundtruth.discovery.plist
scripts/install-discovery.sh --uninstall --owner-ok   # removes it
```

The agent's output goes to `$G/discovery.out.log`; the command's own log is `$G/discovery.log`.
