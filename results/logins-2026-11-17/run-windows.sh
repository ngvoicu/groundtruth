#!/bin/bash
# Input windows, 2026-11-17: the Codex login (each id a temporary alias probe/<model> on that login only) and Devin
# (devin/<model> ids, served by the Devin login only), side by side, each walk in its own file. See window_walk.py.
cd "$(dirname "$0")/../.."
R=results/logins-2026-11-17
mkdir -p $R/logs
CODEX="probe/gpt-6.1-sol:responses:1:11:922000:915011:922511:3 probe/gpt-6-astra:responses:1:11:922000:915011:922511:3
       probe/gpt-6-luna:responses:1:11:922000:915011:922511:3"
# Devin, cheapest first (OpenRouter's input price per 1M tokens on 2026-11-17, as providers.dev lists it)
DEVIN="devin/deepseek-v4-1-flash-1017:chat:1:413:1048576:1047489:1052864:2 devin/glm-5-3:chat:1:394:1048576:1047470:1052845:2
       devin/gpt-6-luna:chat:1:390:922000:911390:923890:2 devin/claude-haiku-5-5:chat:2:572:1000000:999072:1004446:2
       devin/deepseek-v4-pro:chat:1:466:1048576:1047542:1052917:2 devin/gpt-6-1-terra:chat:1:390:922000:911390:923890:2
       devin/gemini-4-argon:chat:1:414:1048576:1047490:1052865:2 devin/gpt-6-1-sol:chat:1:390:922000:915390:925390:2
       devin/claude-sonnet-5-5:chat:2:572:1000000:999072:1004446:2 devin/claude-opus-5-5:chat:2:572:1000000:999072:1004446:2
       devin/gpt-6-astra:chat:1:390:922000:911390:923890:2"
nohup caffeinate -i python3 -u $R/window_walk.py $R/limits-codex.jsonl $CODEX > $R/logs/windows-codex.log 2>&1 &
echo "codex $!"
nohup caffeinate -i python3 -u $R/window_walk.py $R/limits-devin.jsonl $DEVIN > $R/logs/windows-devin.log 2>&1 &
echo "devin $!"

# 14:30: the first Devin walk stopped at GLM-5.3's 502 (an empty completion; see window_walk.py). The models it had not
# reached were walked again in the same order, by this command (GLM-5.3 not again: no retry):
#   nohup caffeinate -i python3 -u $R/window_walk.py $R/limits-devin.jsonl <the DEVIN specs from devin/gpt-6-luna on> \
#     > $R/logs/windows-devin-2.log 2>&1 &
