#!/bin/bash
# The runs of this folder: probe 0.3.3 through the local CLIProxyAPI, one supervisor per login (sequence.py), which
# starts that login's runs one after another (the next once the one before has logged `priming done`) and ends them
# all at the login's first quota or rate refusal. Each supervisor runs under its own `caffeinate -i`, which keeps
# the Mac awake exactly as long as the supervisor (and so its runs) lives.
#   ./run.sh codex|antigravity|meta
# Responses format with a per-sample prompt_cache_key, 3 samples per age, a control first, as the earlier runs of
# these routes.
# - codex: the long setting as a client sends it, prompt_cache_retention "24h" (what pi's OpenAI client sends with
#   PI_CACHE_RETENTION=long); the ages of the long schedule plus 24 h (given as --ages: --ages replaces the
#   schedule, so `--schedule long --ages 24h` would check only at 2.5, 5, 7.5 min and 24 h). Ids are temporary
#   aliases probe/<model> on the Codex login only (an OpenAI API key also serves the plain ids).
# - antigravity: the login's chat models not yet measured, the standard schedule, a 5,000-token prefix as A3 and
#   LA1, one request at a time while priming; a run not primed after 10 minutes is ended. Each id is served by the
#   Antigravity login only (/v1/models?include=accounts), so the plain ids are used.
# - devin: see the README (the chief's decision).
cd "$(dirname "$0")/../.."
R=results/logins-long-2026-11-17
mkdir -p $R/logs
export CACHE_PROBE_KEY=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.pi/agent/cliproxyapi.json')))['apiKey'])")
LONG="10m,15m,20m,25m,30m,40m,50m,60m,75m,90m,120m,4h,8h,12h,24h"
case "$1" in
  codex) X="@--ages@$LONG@--concurrency@2@--body-extra@{\"prompt_cache_retention\":\"24h\"}"
         ARGS="CL1=probe/gpt-6.1-sol$X CL2=probe/gpt-6.1-terra$X CL3=probe/gpt-6-astra$X CL4=probe/gpt-6-luna$X" ;;
  antigravity) X="@--schedule@std@--prefix-tokens@5000@--concurrency@1@--prime-pause@1000"
         ARGS="--prime-timeout 600 AG1=gemini-3.1-flash-lite$X AG2=gemini-3.5-flash-lite$X AG3=gemini-3-flash$X
               AG4=gemini-3.8-flash-tiered$X AG5=gpt-oss-120b-medium$X" ;;
  # Added on the chief's note of 2026-11-17: Muse Ember and Wonder on the Meta login, continuing LM1 and LM3 of
  # ../logins-2026-11-17 at 4, 8, 12 and 24 h, made as they were (plain probe, no body extra: the proxy's payload
  # rule adds prompt_cache_retention "24h" to every muse-* request; 2 primes at a time). muse-* ids have one account.
  meta) X="@--ages@4h,8h,12h,24h@--concurrency@2"
         ARGS="ML1=muse-ember-1.0$X ML3=muse-wonder-1.0$X" ;;
  *) echo "usage: $0 codex|antigravity|meta"; exit 2 ;;
esac
nohup caffeinate -i python3 -u $R/sequence.py "$1" $ARGS > $R/logs/sequence-$1.out 2>&1 &
echo "$1 supervisor under caffeinate: pid $!"
