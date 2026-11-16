#!/bin/bash
# Claude Haiku 5.5 again (CS7, CS8), as CS5 and CS6 but with the probe's `list` filler: Anthropic refused the default
# filler of random words on this model (category "bio"). Same login, same temporary alias, same ages.
cd "$(dirname "$0")/../.."
export CACHE_PROBE_KEY=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.pi/agent/cliproxyapi.json')))['apiKey'])")
OUT=results/claude-login-2026-11-16
mkdir -p $OUT/logs
AGES=10m,15m,20m,25m,30m,40m,50m,60m,65m,75m
run() { # label extra...
  local label=$1; shift
  nohup caffeinate -i node src/cli.ts --base-url http://127.0.0.1:8317/v1 --format messages --model probe/claude-haiku-5-5 \
    --filler list --label "$label" --ages $AGES --replicas 3 --concurrency 2 --out $OUT "$@" > $OUT/logs/$label.log 2>&1 &
  echo "$label $!"
  sleep 20
}
run CS7
run CS8 --ttl 1h
