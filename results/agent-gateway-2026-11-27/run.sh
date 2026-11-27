#!/bin/bash
# 2026-11-27: the cache lifetime Pi gets through Provimux 8.1.7-pmx.3, with the answering account of every request.
# The gateway's client key is in PROVIMUX_API_KEY (read into the environment, never on a command line or in a file).
# S is a new scratch folder; EXT the pi-provimux package Pi loads; RAW where the unlabelled files go (never committed).
# The runs went in parallel; the two Codex models share the login's lock, so their requests never overlapped.
cd "$(dirname "$0")/../.."
G="python3 harness/agent_gateway.py --scratch $S --extension $EXT --replicas 3"

# F1: Claude Fable 5.2 on a Claude login (documented 5 minutes and 1 hour); 2 hours only after a warm 65-minute check
$G --model claude-fable-5-2 --login claude --ages 4,6,30,55,65 --extend 120 --lazy-extend --words 1200 \
   --outfile $RAW/F1.jsonl --budget 2.9 --price-in 8 --price-cached 0.2 --price-write 16 --price-out 40 &
# S1: GPT-6.2 Sol on the Codex login (documented 30 minutes); 2-hour samples primed up front, checked only after a
# warm 65-minute check
$G --model gpt-6.2-sol --login codex --ages 25,35,55,65 --extend 120 --words 700 \
   --outfile $RAW/S1.jsonl --budget 0.4 --price-in 2 --price-cached 0.1 --price-write 0 --price-out 10 &
# A1: GPT-6.2 Astra, same plan; its control was cold and this version of the tool ended there
$G --model gpt-6.2-astra --login codex --delay 20 --ages 25,35,55,65 --extend 120 --words 700 \
   --outfile $RAW/A1.jsonl --budget 1.3 --price-in 8 --price-cached 0.4 --price-write 0 --price-out 40 &
# H1 (14:45 UTC, before the others): gemini-4-hydrogen-low on the Antigravity login, refused for quota at once
#   $G --model gemini-4-hydrogen-low --login antigravity --ages 1 --replicas 1 --words 1200 --outfile $RAW/H1.jsonl ...
# (F1, S1 and A1 at 14:45 UTC.)

# A2 (14:47 UTC, with a second control in a fresh session, as harness/probe.py): continues A1
$G --model gpt-6.2-astra --login codex --ages 25,35,55,65 --extend 120 --words 700 \
   --outfile $RAW/A2.jsonl --budget 1.24 --price-in 8 --price-cached 0.4 --price-write 0 --price-out 40 &
# S2 (15:12 UTC, once Sol was cold at 25 minutes): continues S1 with the younger ages
$G --model gpt-6.2-sol --login codex --ages 2.5,5,10,15 --words 700 \
   --outfile $RAW/S2.jsonl --budget 0.2 --price-in 2 --price-cached 0.1 --price-write 0 --price-out 10 &
wait

# The published files: account markers replaced by labels, answer ids dropped
python3 harness/agent_gateway.py publish --out results/agent-gateway-2026-11-27 \
   $RAW/F1.jsonl $RAW/A1.jsonl $RAW/A2.jsonl $RAW/S1.jsonl $RAW/S2.jsonl $RAW/H1.jsonl
