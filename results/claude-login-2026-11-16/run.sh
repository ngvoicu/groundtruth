#!/bin/bash
# Claude login, cache lifetime: three models, two settings each, one detached probe per run, all through the local
# CLIProxyAPI. Every model id is a temporary alias (probe/<model>) on one Claude login only (harness/pool.py), so no
# other login and no API key can serve it.
cd "$(dirname "$0")/../.."
export CACHE_PROBE_KEY=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.pi/agent/cliproxyapi.json')))['apiKey'])")
OUT=results/claude-login-2026-11-16
mkdir -p $OUT/logs
AGES=10m,15m,20m,25m,30m,40m,50m,60m,65m,75m
run() { # label model extra...
  local label=$1 model=$2; shift 2
  nohup caffeinate -i node src/cli.ts --base-url http://127.0.0.1:8317/v1 --format messages --model "probe/$model" \
    --label "$label" --ages $AGES --replicas 3 --concurrency 2 --out $OUT "$@" > $OUT/logs/$label.log 2>&1 &
  echo "$label $!"
  sleep 20
}
run CS1 claude-opus-5-5
run CS2 claude-opus-5-5 --ttl 1h
run CS3 claude-sonnet-5-5
run CS4 claude-sonnet-5-5 --ttl 1h
run CS5 claude-haiku-5-5
run CS6 claude-haiku-5-5 --ttl 1h
