#!/bin/bash
# 2026-11-27: the cache lifetime Pi gets for SWE-2.1 on a Devin login through Provimux 8.1.7-pmx.4, with the answering
# account of every request, and the model's input window through the same gateway.
# The gateway's client key is in PROVIMUX_API_KEY and CACHE_PROBE_KEY (read into the environment, never on a command
# line or in a file). S is a new scratch folder; EXT the pi-provimux package Pi loads; RAW where the unlabelled files
# go (never committed).
cd "$(dirname "$0")/../.."

# W1 (18:28 UTC): the gateway serves the model as devin/swe-2-1, on the Devin login only. A control, then 2.5, 5, 10,
# 30 and 60 minutes, three samples each; 2 hours only after a warm 60-minute check (none was). The model is free on the
# login, so the list prices are zero and the budget does not stop the run; it made 33 model requests.
python3 harness/agent_gateway.py --model devin/swe-2-1 --login devin --ages 2.5,5,10,30,60 --extend 120 --lazy-extend \
   --replicas 3 --words 700 --scratch $S --extension $EXT --outfile $RAW/W1.jsonl \
   --budget 0 --price-in 0 --price-cached 0 --price-write 0 --price-out 0

# The input window (19:32 UTC, after W1 had ended): one request above Devin's listed 262,144 tokens (accepted, so the
# walk stops there), then the same filler with a code word before it and one after it, which must both come back.
python3 results/limits-2026-11-16/devin_walk.py $RAW/swe-2-1-limits.jsonl devin/swe-2-1:262144
python3 results/limits-2026-11-16/devin_walk.py $RAW/swe-2-1-limits.jsonl --recall devin/swe-2-1 282144 256
cp $RAW/swe-2-1-limits.jsonl results/devin-swe-2-1-2026-11-27/

# The published file: account markers replaced by labels
python3 harness/agent_gateway.py publish --out results/devin-swe-2-1-2026-11-27 $RAW/W1.jsonl
