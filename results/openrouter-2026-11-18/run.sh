#!/bin/bash
# Cache lifetimes of OpenRouter's recent chat models, straight to https://openrouter.ai/api/v1 with this campaign's own
# key, no proxy (2026-11-18). Usage: results/openrouter-2026-11-18/run.sh [--dry-run] <label>...  (labels: plan.json)
# Every run: the probe (src/cli.ts 0.3.3), Responses format, a prompt_cache_key per sample, nothing asked about
# caching, the standard schedule (2.5 min to 2 h, stopping after two fully cold ages), 3 samples per age,
# --stop-on-refusal (a rate, credit or key-limit refusal ends the run, never retried), --usage-log (one line per
# reply: usage, upstream, reply id, sample key). Anthropic models add a top-level cache_control and a per-sample
# session_id (plan.json "args"), as openrouter-direct-v0.2/R1b.
# Each run is a detached probe kept awake by its own `caffeinate -i` (which ends with it); its log, usage log and
# pid are in logs/, its start in logs/launches.txt. The key is read by key.py from the Keychain straight into the
# probe's environment and is never printed or written. status.py decides what is launched (the $18 stop).
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT=results/openrouter-2026-11-18
mkdir -p $OUT/logs
DRY=""
if [ "${1:-}" = "--dry-run" ]; then DRY=--dry-run; shift; fi

for label in "$@"; do
  model=$(python3 -c "import json,sys;print(next(r['model'] for r in json.load(open('$OUT/plan.json'))['runs'] if r['label']==sys.argv[1]))" "$label")
  extra=()
  while IFS= read -r a; do [ -n "$a" ] && extra+=("$a"); done < <(python3 -c "import json,sys;[print(a) for a in next(r['args'] for r in json.load(open('$OUT/plan.json'))['runs'] if r['label']==sys.argv[1])]" "$label")
  args=(--base-url https://openrouter.ai/api/v1 --format responses --model "$model" ${extra[@]+"${extra[@]}"} --stop-on-refusal --label "$label")
  if [ -n "$DRY" ]; then
    node src/cli.ts "${args[@]}" --dry-run > $OUT/logs/$label.dry-run.txt
    echo "$label: dry run in $OUT/logs/$label.dry-run.txt"
    continue
  fi
  if [ -e $OUT/logs/$label.pid ] || ls $OUT/$label-2026-* >/dev/null 2>&1; then
    echo "$label: already started once (logs/$label.pid or a result file exists): not started again" >&2; exit 3
  fi
  CACHE_PROBE_KEY="$(python3 $OUT/key.py)" nohup caffeinate -i node src/cli.ts "${args[@]}" \
    --out $OUT --usage-log $OUT/logs/$label.usage.jsonl > $OUT/logs/$label.log 2>&1 < /dev/null &
  echo $! > $OUT/logs/$label.pid
  echo "$label pid $! started $(date -u +%FT%TZ) model $model" | tee -a $OUT/logs/launches.txt
done
