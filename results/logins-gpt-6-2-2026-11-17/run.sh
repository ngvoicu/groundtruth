#!/bin/bash
# GPT-6.2 Sol and Astra on the Codex login, 2026-11-17: the plain probe (0.3.3) through the local CLIProxyAPI, made as
# LC1 and LC3 of ../logins-2026-11-17 (Responses format, per-sample prompt_cache_key, 2,500-token prefix, standard
# schedule to 2 h, 3 samples per age, a control first, 2 primes at a time, no pause, --stop-on-refusal, nothing asked
# about caching). Ids are temporary aliases probe/<model> on the Codex login only (the OpenAI API key also serves the
# plain ids). sequence.py starts Astra only after Sol has logged `priming done`, under its own `caffeinate -i`.
cd "$(dirname "$0")/../.."
R=results/logins-gpt-6-2-2026-11-17
mkdir -p $R/logs
export CACHE_PROBE_KEY=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.pi/agent/cliproxyapi.json')))['apiKey'])")
X="@--schedule@std@--concurrency@2"
nohup caffeinate -i python3 -u $R/sequence.py codex GS1=probe/gpt-6.2-sol$X GA1=probe/gpt-6.2-astra$X > $R/logs/sequence-codex.out 2>&1 &
echo "supervisor under caffeinate: pid $!"
