#!/usr/bin/env python3
"""Writes manifest-entries.json: what the runs of this folder add to observed/manifest.json (nothing that is a result).

    python3 results/logins-gpt-6-2-2026-11-17/make_entries.py
"""
import json, os

D = os.path.dirname(os.path.abspath(__file__))
F = "results/logins-gpt-6-2-2026-11-17"
NOTE = ("plain probe 0.3.3 through CLIProxyAPI (build ngvoicu-local-4c071f30, process of 18:38:51 local), made as "
        "logins-2026-11-17/{base} (no option, 2,500-token prefix, standard schedule, 3 samples per age, 2 primes at a "
        "time), pinned to the Codex login by a temporary alias probe/{m} on that login only (/v1/models?include=accounts "
        "lists only the Codex login for it; the plain id also has an OpenAI API key); every answer's X-CPA-AUTH-KIND was "
        "oauth. Unlike {base}: no large request went to the login before or during the run, and the two models were not "
        "primed at the same moment (Astra started once Sol had finished priming); the login's request counter rose by "
        "exactly the runs' own requests, so nothing else used it meanwhile, and the OpenAI API key's stayed at 0. "
        "Released by OpenAI on 2026-11-17. "
        # The note on the Codex login's zeros (the same on LC1, LC3, LC4 in ../logins-2026-11-17 and on CL1 - CL4 in
        # ../logins-long-2026-11-17).
        "The published 0 means that there is no tested age through which every check hit, not that this route does "
        "not cache. GS1 and GA1 each missed 1 of 3 at 2.5 minutes (LC1, LC3 and LC4 had missed there too that "
        "afternoon): early misses also occurred without a large request before the priming and without two models "
        "priming at once. That does not rule out every kind of load, and it says nothing certain about the misses of "
        "the earlier models. Their cause is not established.")
runs = []
for label, m, stamp, base in (("GS1", "gpt-6.2-sol", "2026-11-17T21-26-51", "LC1"),
                              ("GA1", "gpt-6.2-astra", "2026-11-17T21-27-51", "LC3")):
    runs.append({"id": f"logins-gpt-6-2-2026-11-17/{label}", "file": f"{F}/{label}-{stamp}.json",
                 "route": "codex-subscription", "client": "cliproxyapi", "model": m, "models_dev": None,
                 "base_model": f"openai/{m}", "options": {}, "note": NOTE.format(base=base, m=m)})
excluded = json.load(open(f"{D}/excluded-window.json")) if os.path.exists(f"{D}/excluded-window.json") else []
out = {"comment": "Entries the runs of results/logins-gpt-6-2-2026-11-17 would add to observed/manifest.json (T-86, branch "
                  "campaign/logins-long). runs: appended to runs; excluded: appended to excluded. Nothing here is a result.",
       "runs": runs, "excluded": excluded}
open(f"{D}/manifest-entries.json", "w").write(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
print(len(runs), "runs,", len(excluded), "excluded")
