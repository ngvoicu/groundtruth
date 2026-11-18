#!/bin/bash
# GPT-6.2 Sol and GPT-6.2 Astra straight against the OpenAI API with the owner's key, no proxy (2026-11-17), as
# ../direct-2026-11-17 measured gpt-6-sol, gpt-6-astra, gpt-6-luna and gpt-6.1-terra.
# Usage: results/gpt-6-2-2026-11-17/run.sh <label>...   (labels below; `--dry-run` as first argument: plan only)
# Every run is a detached probe kept awake by its own `caffeinate -i` (which ends with it); its log, its usage log
# (one line per reply, for ledger.py) and its pid are in logs/. The key is read by key.py straight into the
# environment of the probe and is never printed or written.
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT=results/gpt-6-2-2026-11-17
mkdir -p $OUT/logs
DRY=""
if [ "${1:-}" = "--dry-run" ]; then DRY=--dry-run; shift; fi

OPENAI="--base-url https://api.openai.com/v1 --format responses"       # standard schedule, 2.5 min to 2 h

args_for() {
  case $1 in
    oa-sol62)   echo "openai $OPENAI --model gpt-6.2-sol" ;;
    oa-astra62) echo "openai $OPENAI --model gpt-6.2-astra" ;;
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
