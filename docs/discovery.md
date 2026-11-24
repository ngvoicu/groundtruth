# Daily discovery: `listed.json`

Every day at 22:30 the owner's Mac adds what each of his logins' vendors offers to `listed.json` at the root of this
repository on GitHub, and providers.dev publishes it as the provider's model list (`/api/v1/listings`) at its next
daily sync. The design is section 9.1 (way A) of Provimux's `model-lists.md`; this is step G1 of its section 10.

## What the command does

`python3 harness/discover.py` (its docstring has every rule). `$G` is `GROUNDTRUTH_CLIENT_HOME`, the nights' private
folder; discovery keeps everything there and runs **no git command**: it has no clone and never touches a checkout.

- **One local request**: `GET /v8/management/provimux/model-lists?view=live` to the owner's Provimux on this Mac
  (Provimux 8.1.1-pmx.2 or later). A URL that is not loopback is refused, and the request goes through an opener with
  no proxy and no redirect, so the management key never leaves this Mac. **Nothing is sent to a vendor.**
- **Four listings only**: Claude login → `claude-subscription`, Codex → `openai-codex`, Devin → `devin` (Devin's own
  ids, without Provimux's `devin/`), Meta login → `meta-subscription`. Per login only its `live_list` (the vendor's
  answer as it arrived), and of an entry only its id, name, window, output limit, modalities and reasoning levels.
- **Privacy by allowlist**:
  - modalities only from `text`, `image`, `audio`, `video`, `pdf` (a media type read as its kind) and reasoning
    levels only from `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`: providers.dev's `LISTED_MODALITIES`
    and `LISTED_LEVELS` (`src/core/listings.ts`), the levels being Provimux's `liveModelListLevels`
    (`sdk/cliproxy/live_model_lists.go`). Any other word is dropped;
  - a model whose id or name holds an identity value as a whole word or token sequence, of any length, is dropped:
    a login's label, e-mail and its local part, file name and its stem, `auth_index` (of every row of the answer),
    and the management key from `CPA_MGMT_KEY` and from `~/.cli-proxy-api/keys.txt` (the key also as a plain
    substring). A value made only of service names (`SERVICE_WORDS`: a login labelled "Devin") never counts. The log
    says a model was dropped, never the value. The published models are checked again every day, so a label added
    later removes a model that holds it;
  - before an upload, an identity check and `harness/scan_secrets.py` run on the exact bytes that are sent.
- **Complete lists; discovery never removes a model**:
  - a login's list is complete when Provimux holds it (held, not expired), it is not empty, and it has as many models
    as Provimux says it listed (`live.listed_models`);
  - the logins of each type are remembered, hashed, in `$G/discovery-state.json` (private, never published). A login
    remembered but absent from today's answer counts as incomplete; one removed on purpose is forgotten with
    `--forget-absent`;
  - a provider's new part is the union of the published models and today's complete lists. A field stated today
    replaces the published value (where today's logins state it differently, the published value stays);
  - its date advances, to the oldest of today's lists, only when every enabled login of the type, and every remembered
    one, gave a complete list. A provider not yet published appears on its first complete day;
  - **a retired model is removed only by hand** (an edit of `listed.json` on `main`). So the published file only
    grows, and providers.dev's rule against a file that lost more than 40 % of its models cannot trip from one day to
    the next, whatever day the site last synced.
- **Other providers**: any other provider of the published file is carried forward as it is. Copilot and Antigravity
  rows are left out (below).
- **The base is GitHub's file**, read through `gh` (`GET /repos/ngvoicu/groundtruth/contents/listed.json`, its bytes
  checked against its blob sha). The new file is refused, as providers.dev would refuse it, if it fails the schema
  (`harness/listed_schema.py`), is over 8 MiB, or lost more than 40 % against GitHub's file.
- **`$G/listed.json`**: every run that read Provimux and GitHub writes its result there, published or not. The weekly
  night plans from it.
- **Ages, from the last published file**: every provider's age goes to `$G/discovery.log`. A provider older than 3 days
  on GitHub is an `ASK:` line, and one macOS notification per stale part. A failed `--publish` is an `ASK:` line too.
- **One run at a time**: a lock in `$G` (`discovery.lock`) makes a second run exit at once.

### `--publish`: GitHub's contents API, never git

- When the new file differs from GitHub's, `PUT /repos/ngvoicu/groundtruth/contents/listed.json` through `gh api`, with
  the exact bytes checked, GitHub's `sha` of the file it read, `branch: main`, the message `discovery: listed.json`,
  and author and committer `groundtruth discovery <office@providers.dev>`. Nothing of the Mac's Git configuration is
  read: there is no Git.
- A `409` or `422` (the file changed meanwhile): it reads the file again and rebuilds once, from what GitHub now has; a
  second one is exit 1, and the next run starts again from GitHub.
- **GitHub only.** The NAS copy follows GitHub by itself (`.forgejo/workflows/follow-github.yml`).

CI checks the committed file (`python3 harness/listed_schema.py listed.json`), and so does the commit hook.

## Login types left out, and why

- **Copilot.** Provimux 8.1.1-pmx.2 puts every model of the account's answer into the status endpoint's list, also the
  ones the account does not offer: `sdk/cliproxy/provimux_live_copilot.go` lines 70–71 append each model to
  `entry.models` before line 72 tests `provimuxCopilotOffered` (disabled by policy, hidden from the picker, embedding
  models, no chat endpoint), and `sdk/cliproxy/provimux_model_list_status.go` lines 91–99 put every one of them on the
  wire. models.dev covers Copilot (`github-copilot`).
- **Antigravity.** Provimux keeps one description per model id for all Antigravity logins
  (`sdk/auth/provimux_antigravity_models.go` lines 49–60: each answer overwrites the shared map), and the status
  endpoint reads that same description for every login (`sdk/cliproxy/provimux_model_list_status.go` lines 109–115).
  Two logins that state different windows would arrive as one value, the newest answer's.
- **Kimi** (Provimux does not ask it yet, `model-lists.md` 13.4), **xAI**, **Gemini keys**, **Vertex** and
  **AI Studio**: their listings come from models.dev (`model-lists.md` 4.1).

An earlier file's Copilot or Antigravity rows are left out at the next publication. GitHub has no `listed.json` yet,
so there are none.

## The Monday night

`harness/weekly.py night` runs discovery first (the copy in `$G/bin` when installed, else the checkout's), without
`--publish`: it refreshes `$G/listed.json`, and the night plans from `$G/listed.json` when it exists, else from the
checkout's `listed.json`. A failed discovery is a line in the night's output; the night plans from the last file.

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

`date` is the day of the oldest list of the last complete day; `client` is `provimux` (providers.dev's measurement
labels). A field the vendor's list does not state is left out, never guessed.

## Once, with the owner's OK

```bash
export GROUNDTRUTH_CLIENT_HOME="$HOME/groundtruth-clients"      # exists, mode 700 (the night's folder)
# 1. a first run by hand, reading only: Provimux and GitHub's file; writes $G/listed.json; publishes nothing
python3 harness/discover.py
# 2. the first publication by hand: puts listed.json on GitHub's main (gh must be logged in)
python3 harness/discover.py --publish
# 3. the agent, daily at 22:30 (a run missed while the Mac slept runs when it wakes)
scripts/install-discovery.sh --print --publish        # shows what it would copy and the plist; changes nothing
scripts/install-discovery.sh --owner-ok --publish     # copies discover.py into $G/bin, writes and loads the agent
scripts/install-discovery.sh --uninstall --owner-ok   # removes the agent
```

The agent runs `$G/bin/discover.py`, the copy made at install, never a checkout's file: to update it, install again.
Its output goes to `$G/discovery.out.log`; the command's own log is `$G/discovery.log`.
