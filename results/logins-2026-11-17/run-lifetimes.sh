#!/bin/bash
# Cache lifetimes, 2026-11-17: plain probe (0.3.1) through the local CLIProxyAPI, Responses format with a per-sample
# prompt_cache_key as the earlier runs of these routes, standard schedule (2.5 min to 2 h, stops after two cold
# ages), 3 samples per age, a control first, --stop-on-refusal. One supervisor per login (supervise.py) starts that
# login's runs side by side and ends them all at the login's first quota or rate refusal.
#   ./run-lifetimes.sh codex|meta|antigravity|devin
# GPT ids are temporary aliases probe/<model> on the Codex login only (an OpenAI API key also serves the plain ids);
# muse-*, gemini-3.8-flash-high and devin/* ids are served by one login each. Gemini 4 Argon and Gemini 3.8 Flash use
# a 5,000-token prefix, as their earlier runs (D5, A3).
cd "$(dirname "$0")/../.."
R=results/logins-2026-11-17
mkdir -p $R/logs
export CACHE_PROBE_KEY=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.pi/agent/cliproxyapi.json')))['apiKey'])")
case "$1" in
  codex) SPECS="LC1=probe/gpt-6.1-sol LC2=probe/gpt-6.1-terra LC3=probe/gpt-6-astra LC4=probe/gpt-6-luna" ;;
  meta) SPECS="LM1=muse-ember-1.0 LM2=muse-spark-1.3 LM3=muse-wonder-1.0" ;;
  antigravity) SPECS="LA1=gemini-3.8-flash-high@--prefix-tokens@5000" ;;
  devin) SPECS="LD1=devin/claude-opus-5-5 LD2=devin/deepseek-v4-pro LD3=devin/gemini-4-argon@--prefix-tokens@5000
                LD4=devin/glm-5-3 LD5=devin/gpt-6-1-sol LD6=devin/grok-4-7 LD7=devin/kimi-k3 LD8=devin/swe-2" ;;
  *) echo "usage: $0 codex|meta|antigravity|devin"; exit 2 ;;
esac
nohup caffeinate -i python3 -u $R/supervise.py "$1" $SPECS > $R/logs/supervise-$1.out 2>&1 &
echo "$1 supervisor (caffeinate) pid $!"
