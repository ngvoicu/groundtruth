#!/bin/bash
# Cache lifetimes straight against the OpenAI and the Anthropic API with the owner's keys, no proxy (2026-11-17).
# Usage: results/direct-2026-11-17/run.sh <label>...   (labels below; `--dry-run` as first argument: plan only)
# Every run is a detached probe kept awake by its own `caffeinate -i` (which ends with it); its log, its usage log
# (one line per reply, for ledger.py) and its pid are in logs/. The key is read by key.py straight into the
# environment of the probe and is never printed or written.
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT=results/direct-2026-11-17
mkdir -p $OUT/logs
DRY=""
if [ "${1:-}" = "--dry-run" ]; then DRY=--dry-run; shift; fi

OPENAI="--base-url https://api.openai.com/v1 --format responses"       # standard schedule, 2.5 min to 2 h
ANTHROPIC="--base-url https://api.anthropic.com/v1 --format messages --concurrency 2"
SHORT="--ages 10m,15m"                                                 # with 2.5, 5 and 7.5 min: past 5 minutes
LONG="--ttl 1h --ages 10m,15m,20m,25m,30m,40m,50m,60m,65m,75m"         # as claude-login-2026-11-16: past one hour

args_for() {
  case $1 in
    oa-luna)            echo "openai $OPENAI --model gpt-6-luna" ;;
    oa-terra)           echo "openai $OPENAI --model gpt-6.1-terra" ;;
    oa-sol6)            echo "openai $OPENAI --model gpt-6-sol" ;;
    oa-audio)           echo "openai $OPENAI --model gpt-audio-1.5" ;;
    oa-audio-chat)      echo "openai --base-url https://api.openai.com/v1 --format chat --model gpt-audio-1.5" ;;  # it refuses Responses
    oa-daybreak-blue)   echo "openai $OPENAI --model gpt-daybreak-blue-latest" ;;
    oa-chat-latest)     echo "openai $OPENAI --model chat-latest" ;;
    oa-astra)           echo "openai $OPENAI --model gpt-6-astra" ;;
    oa-daybreak-red)    echo "openai $OPENAI --model gpt-daybreak-red-latest" ;;
    oa-cyber)           echo "openai $OPENAI --model gpt-6-cyber" ;;
    an-haiku-5m)        echo "anthropic $ANTHROPIC --model claude-haiku-5-5 $SHORT" ;;
    an-haiku-1h)        echo "anthropic $ANTHROPIC --model claude-haiku-5-5 $LONG" ;;
    an-haiku-list-5m)   echo "anthropic $ANTHROPIC --model claude-haiku-5-5 --filler list $SHORT" ;;
    an-haiku-list-1h)   echo "anthropic $ANTHROPIC --model claude-haiku-5-5 --filler list $LONG" ;;
    an-sonnet-5m)       echo "anthropic $ANTHROPIC --model claude-sonnet-5-5 $SHORT" ;;
    an-sonnet-1h)       echo "anthropic $ANTHROPIC --model claude-sonnet-5-5 $LONG" ;;
    an-opus-5m)         echo "anthropic $ANTHROPIC --model claude-opus-5-5 $SHORT" ;;
    an-opus-1h)         echo "anthropic $ANTHROPIC --model claude-opus-5-5 $LONG" ;;
    an-fable-5m)        echo "anthropic $ANTHROPIC --model claude-fable-5-2 $SHORT" ;;
    an-fable-1h)        echo "anthropic $ANTHROPIC --model claude-fable-5-2 $LONG" ;;
    *) echo "unknown label $1" >&2; exit 2 ;;
  esac
}

for label in "$@"; do
  spec=$(args_for "$label")
  provider=${spec%% *}
  read -r -a args <<<"${spec#* }"
  if [ -n "$DRY" ]; then
    node src/cli.ts "${args[@]}" --label "$label" --dry-run > $OUT/logs/$label.dry-run.txt
    echo "$label: dry run in $OUT/logs/$label.dry-run.txt"
    continue
  fi
  CACHE_PROBE_KEY="$(python3 $OUT/key.py "$provider")" nohup caffeinate -i node src/cli.ts "${args[@]}" \
    --label "$label" --out $OUT --usage-log $OUT/logs/$label.usage.jsonl > $OUT/logs/$label.log 2>&1 &
  echo $! > $OUT/logs/$label.pid
  echo "$label pid $! started $(date -u +%FT%TZ)" | tee -a $OUT/logs/launches.txt
  sleep 5
done
