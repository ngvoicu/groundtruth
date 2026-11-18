#!/usr/bin/env python3
"""Writes manifest-entries.json: what the runs of this folder add to observed/manifest.json (nothing that is a result).

    python3 results/logins-long-2026-11-17/make_entries.py

CL1, CL3, ML1 and ML3 were cut off by the Mac's restart at 10:16 local on 2026-11-18, before their 24-hour checks:
their run files are the probes' progress files (`<label>-<start>.partial.json`) as the restart left them, committed
unchanged. Every other run ended by itself (`<label>-<start>.json`).
"""
import json, os

D = os.path.dirname(os.path.abspath(__file__))
F = "results/logins-long-2026-11-17"
B1 = ("build ngvoicu-local-c52243ab (process of 18:09:07 local) until the owner restarted the proxy at 18:38:51 "
      "local, build ngvoicu-local-4c071f30 (the same plus one commit for the WebSocket auth-kind event, nothing in "
      "this request path) after that")
PROOF = ("The probe sent prompt_cache_retention \"24h\" (OpenAI's extended retention, as a client asking for the long "
         "cache sends it); CLIProxyAPI deletes it before the Codex login, so the login received the plain request, "
         "recorded with no option. Proof: the Codex translator deletes prompt_cache_options and prompt_cache_retention "
         "from every OpenAI Responses request (commits 2ab25eae \"strip unsupported prompt_cache_options from OpenAI "
         "Responses requests\", #4915, and 2005788f \"filter out prompt_cache_retention in OpenAI->Codex responses "
         "request conversion\", #5068; codex_executor_request.go: \"OAuth and SIWC credentials reject "
         "prompt_cache_options, so they keep the translator's removal\"), and at 18:23 local the login answered 200 to "
         "prompt_cache_retention \"bogus-retention\" and prompt_cache_options.ttl \"bogus-ttl\" while it refused an "
         "unknown field with 400 \"Unsupported parameter\" (fields-codex.jsonl).")
PIN = ("Pinned to the Codex login by a temporary alias probe/{m} on that login only (/v1/models?include=accounts lists "
       "only the Codex login for it; the plain id also has an OpenAI API key); every answer's X-CPA-AUTH-KIND was "
       "oauth, and the OpenAI API key's counter stayed at 0.")

# The note on the Codex login's zeros (the same on LC1, LC3, LC4 in ../logins-2026-11-17 and on GS1, GA1 in
# ../logins-gpt-6-2-2026-11-17).
ZERO = ("The published 0 means that there is no tested age through which every check hit, not that this route does "
        "not cache. Early misses also occurred without a large request before the priming and without two models "
        "priming at once: GS1 and GA1 (logins-gpt-6-2-2026-11-17, GPT-6.2 Sol and Astra) each missed 1 of 3 at "
        "2.5 minutes. That does not rule out every kind of load, and it says nothing certain about the misses of the "
        "earlier models. Their cause is not established.")
CUT = {"CL1", "CL3", "ML1", "ML3"}  # cut off by the restart: their progress files
CUT_CODEX = (" Cut off: the 4-, 8- and 12-hour checks were refused by CLIProxyAPI itself (HTTP 400 \"unknown provider for "
             "model probe/{m}\"; the owner's configuration of 20:50 local had excluded {m} from the Codex login; nothing "
             "reached OpenAI), and the Mac was restarted at 10:16 local on 2026-11-18, before the 24-hour check, which "
             "ended the run. The run file is the probe's progress file as the restart left it (status \"running\"), "
             "unchanged. A check that errored counts neither warm nor cold, so this run adds data to 2 h only: no data "
             "at 4, 8, 12 or 24 h.")
CUT_META = (" Cut off: all three 8-hour checks failed after their retries (HTTP 504 from CLIProxyAPI between 02:32 and "
            "02:58 local on 2026-11-18: its lookup of Meta's API host timed out), and the Mac was restarted at 10:16 "
            "local on 2026-11-18, before the 24-hour check, which ended the run. The run file is the probe's progress "
            "file as the restart left it (status \"running\"), unchanged. A check that errored counts neither warm nor "
            "cold, so this run has data at 2.5, 5, 7.5 min, 4 h and 12 h, none at 8 h or 24 h.")


def run_file(label, stamp):
    return f"{F}/{label}-{stamp}" + (".partial.json" if label in CUT else ".json")


runs = []
codex = [("CL1", "gpt-6.1-sol", "2026-11-17T16-27-48", "LC1", ""),
         ("CL2", "gpt-6.1-terra", "2026-11-17T16-28-58", "LC2", ""),
         ("CL3", "gpt-6-astra", "2026-11-17T16-30-03", "LC3", ""),
         ("CL4", "gpt-6-luna", "2026-11-17T16-31-23", "LC4",
          " Its control missed completely (0 of 2,659 tokens read from cache, at 3 s and again at 10 s), so it ended "
          "there with no check: it continues LC4 with that missed control only, by the chief's decision, and Luna "
          "was not started again.")]
for label, m, stamp, base, extra in codex:
    runs.append({
        "id": f"logins-long-2026-11-17/{label}", "file": run_file(label, stamp),
        "route": "codex-subscription", "client": "cliproxyapi", "model": m, "models_dev": None,
        "base_model": f"openai/{m}", "options": {}, "removed_by_proxy": {"prompt_cache_retention": "24h"},
        "continues": f"logins-2026-11-17/{base}",
        "note": (f"probe 0.3.3 through CLIProxyAPI, the request of {base} with ages out to 24 h (the long schedule plus "
                 f"24 h). {PROOF} {PIN.format(m=m)} Served by {B1}.{extra}"
                 + (CUT_CODEX.format(m=m) if label in CUT else "") + f" {ZERO}")})

meta = [("ML1", "muse-ember-1.0", "2026-11-17T16-31-20", "LM1"), ("ML3", "muse-wonder-1.0", "2026-11-17T16-31-45", "LM3")]
for label, m, stamp, base in meta:
    runs.append({
        "id": f"logins-long-2026-11-17/{label}", "file": run_file(label, stamp),
        "route": "meta-subscription", "client": "cliproxyapi", "model": m, "models_dev": None,
        "base_model": f"meta/{m}", "options": {"prompt_cache_retention": "24h"},
        "continues": f"logins-2026-11-17/{base}",
        "note": (f"continues {base} (warm in all its checks to 2 h), planned at 4, 8, 12 and 24 h, made as it was: the plain "
                 "probe, no body extra; CLIProxyAPI's payload rule for muse-* adds prompt_cache_retention \"24h\" to "
                 "every request to the Meta login. muse-* ids have one account, the Meta login "
                 "(/v1/models?include=accounts); every answer's X-CPA-AUTH-KIND was oauth. The probe also checks at "
                 f"2.5, 5 and 7.5 min (always), which adds samples to those ages of {base}. Served by {B1}.{CUT_META} "
                 f"{base} and this run are published together, as one evaluation, whatever they show (decided on "
                 "2026-11-17, before any of this run's later checks).")})

# AG1 - AG3, AG5: no timed check, a control under the probe's criterion. Inconclusive about the lifetime, so excluded
# (the chief's decision after the review of round two); the raw files stay.
INCONCLUSIVE = ("Lifetime inconclusive: the control did not establish observable caching under this probe's criterion "
                "(warm = at least half of the prompt and at least 500 tokens read from cache), and the run has no timed "
                "check, so it ended at the control. It does not show a cache that expired, and it does not show that "
                "there is none: it is not a measured lifetime of 0. ")
AGN = ("Responses format with a per-sample prompt_cache_key and a 5,000-token prefix as A3 and LA1, probe 0.3.3 "
       "through CLIProxyAPI; the id is served by the Antigravity login only, every answer's X-CPA-AUTH-KIND was oauth. "
       "On the same login that day gemini-3.8-flash-high's control read 2,647 of 4,686 (logins-2026-11-17/LA1, a hit).")
ag = [("AG1", "gemini-3.1-flash-lite", "2026-11-17T16-27-48",
       "the prime read 0 of 4,670 prompt tokens from cache, the immediate re-send 2,031 of 4,670"),
      ("AG2", "gemini-3.5-flash-lite", "2026-11-17T16-28-08",
       "the prime read 0 of 4,698 prompt tokens from cache, the immediate re-send 2,031 of 4,698"),
      ("AG3", "gemini-3-flash", "2026-11-17T16-28-28",
       "the prime read 0 of 4,637 prompt tokens from cache, the immediate re-send 2,031 of 4,637"),
      ("AG5", "gpt-oss-120b-medium", "2026-11-17T16-38-49",
       "the prime and the immediate re-send each read 67 of 4,780 prompt tokens from cache")]
ag_excluded = []
for label, m, stamp, figures in ag:
    same = (" The same 2,031 tokens on AG1 - AG3 suggests a fixed block read from cache; the records do not show what "
            "it is.") if label != "AG5" else ""
    ag_excluded.append({
        "id": f"logins-long-2026-11-17/{label}",
        "reason": (f"{m} on the Antigravity login (antigravity / cliproxyapi, prefix_tokens 5000): {figures}. "
                   f"{INCONCLUSIVE}{AGN}{same} Raw file: {F}/{label}-{stamp}.json (and .md).")})

excluded = ag_excluded + [
    {"id": "logins-long-2026-11-17/AG4",
     "reason": "gemini-3.8-flash-tiered on the Antigravity login: its control was answered (warm, 2,620 of 4,659 "
               "tokens read from cache, 18:30:48 local) after five retries of Google's 503 \"No capacity available "
               "for model ... on the server\" and CLIProxyAPI's auth_unavailable; the priming of its 42 samples then "
               "did not complete (the same 503s, one TLS handshake timeout answered 500 by the proxy), and the run was "
               "ended by the chief's 10-minute rule at 18:38:48 local. No timed evidence and no run file; its log is "
               "AG4-2026-11-17T16-28-48.not-primed.log. Google's server capacity, not the account: no 429, no "
               "refusal of the login."},
    {"id": "logins-long-2026-11-17/codex-subscription long setting (gpt-6.1-sol, gpt-6.1-terra, gpt-6-astra, gpt-6-luna)",
     "reason": "Not measured because it does not exist on this route through CLIProxyAPI: the proxy deletes both "
               "prompt_cache_retention and prompt_cache_options from every Codex request to the login (commits "
               "2ab25eae and 2005788f; codex_executor_request.go: \"OAuth and SIWC credentials reject "
               "prompt_cache_options, so they keep the translator's removal\"; only an OpenAI API key gets a "
               "client's prompt_cache_options.ttl back, PR #7609), and on 2026-11-17 18:23 local (build "
               "ngvoicu-local-c52243ab) the login answered 200 to prompt_cache_retention \"24h\" and "
               "\"bogus-retention\", prompt_cache_options.ttl \"12h\" and \"bogus-ttl\", while it refused an unknown "
               "field with 400 \"Unsupported parameter\" (fields-codex.jsonl). A client that asks gets the plain cache: "
               "CL1 - CL4 are recorded as plain runs (removed_by_proxy)."},
    {"id": "logins-long-2026-11-17/devin long setting (all 17 models of the devin provider)",
     "reason": "Not measured because it does not exist on this route: CLIProxyAPI rebuilds every Devin request as "
               "Devin's protobuf (internal/runtime/executor/helps/devin_wire.go, BuildDevinGetChatMessageRequest, "
               "build ngvoicu-local-c52243ab): system prompt, messages, tools, max tokens, temperature, session id, "
               "the cascade id (the cache key) and the model; no field for a cache lifetime, and cache_control markers "
               "are skipped when the content is read. On 2026-11-17 18:24 local devin/swe-2 (Responses format) answered "
               "200 with the same 471 input tokens to no field, prompt_cache_retention \"24h\" and \"bogus-retention\", "
               "prompt_cache_options.ttl \"bogus-ttl\" and an unknown top-level field; devin/claude-haiku-5-5 (Claude's "
               "format) answered 200 to a cache marker with ttl \"1h\" and with ttl \"bogus-ttl\" (Anthropic refuses "
               "an invalid ttl with 400) (fields-devin.jsonl). A long run would send Devin exactly what a short run "
               "sends, so by the chief's decision none was made."},
]
out = {"comment": "Entries the runs of results/logins-long-2026-11-17 would add to observed/manifest.json (T-75, branch "
                  "campaign/logins-long). runs: appended to runs; excluded: appended to excluded. Nothing here is a "
                  "result. The runs that continue logins-2026-11-17/LC1 - LC4 and LM1, LM3 need those as runs: LC1 - LC4 "
                  "are runs in that part's entries, LM1 and LM3 are in its excluded and must move to runs (they were "
                  "held back to be published with ML1 and ML3, as one evaluation each, whatever those show). CL1, CL3, "
                  "ML1 and ML3 were cut off by a restart of the Mac: their files are the probes' progress files.",
       "runs": runs, "excluded": excluded}
open(f"{D}/manifest-entries.json", "w").write(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
print(len(runs), "runs,", len(excluded), "excluded")
