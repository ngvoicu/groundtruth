# Daily discovery: `listed.json`

Every day at 22:30 the owner's Mac writes what each of his logins' vendors offers into [`listed.json`](../listed.json),
and providers.dev publishes it as the provider's model list (`/api/v1/listings`) at its next daily sync. The design is
section 9.1 (way A) of Provimux's `model-lists.md`; this is step G1 of its section 10.

## What the command does

`python3 harness/discover.py` (see its docstring for every rule):

- **One local request**: `GET /v8/management/provimux/model-lists?view=live` to the owner's Provimux on this Mac
  (Provimux 8.1.1-pmx.2 or later). Any host that is not this Mac is refused. The management key is found as
  `harness/pool.py` finds it and is never printed or written. **Nothing is sent to a vendor** and nothing is spent:
  Provimux has asked the vendors already; groundtruth reads no token.
- **Only the vendor's list**: per login, `live_list` (the vendor's answer as it arrived, unmerged), only while Provimux
  holds it (`live.held`). The file takes from each entry its id, name, window, output limit, modalities and reasoning
  levels, and nothing of the row: no `auth_index`, login name, e-mail, label, count or failure.
- **Per listing**, the logins of one type joined: Claude login → `claude-subscription`, Codex → `openai-codex`,
  Copilot → `github-copilot`, Antigravity → `antigravity`, Devin → `devin` (Devin's own ids, without Provimux's
  `devin/`), Meta login → `meta-subscription`. A field two logins state differently is left out. Kimi, xAI, Gemini
  keys, Vertex and AI Studio are not written: their listings come from models.dev (`model-lists.md` 4.1; Kimi's
  lists are not asked yet, 13.4).
- **A provider with no live list today keeps yesterday's part and date.** A provider older than 3 days is an ask: an
  `ASK:` line in `$G/discovery.log` and in the command's last words (the weekly night raises the same ask from the
  file, `harness/weekly.py`).
- **Checked before it is written**: the schema (`harness/listed_schema.py`, providers.dev's `ListedFile` or stricter),
  no identity value of the answer anywhere, and not a file providers.dev would refuse as shrunk (more than 40 % of its
  providers or models lost).
- **`--publish`** (off by default): when the file changed, `harness/scan_secrets.py` must pass on it; then it alone is
  committed on `main` and pushed to `upstream` and `origin`.

CI checks the committed file (`python3 harness/listed_schema.py listed.json`), and so does the commit hook.

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

A first run by hand, reading his Provimux, writing nothing but `listed.json` in this checkout:

```bash
python3 harness/discover.py
```

Then the agent (daily at 22:30; a run missed while the Mac slept runs when it wakes):

```bash
scripts/install-discovery.sh --owner-ok --publish     # writes and loads ~/Library/LaunchAgents/dev.providers.groundtruth.discovery.plist
scripts/install-discovery.sh --print --publish        # shows the plist first, writes nothing
scripts/install-discovery.sh --uninstall --owner-ok   # removes it
```

Its output goes to `$G/discovery.out.log`; the command's own log is `$G/discovery.log`.
