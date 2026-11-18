#!/usr/bin/env python3
"""Reads what OpenRouter reports for this campaign's key (GET https://openrouter.ai/api/v1/key: limit, usage, limit
remaining) and appends it to key-readings.jsonl with the time and a note. Never prints or writes the key.
    python3 results/openrouter-2026-11-18/key_usage.py "before the first run"
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
key = subprocess.run([sys.executable, os.path.join(HERE, "key.py")], check=True, capture_output=True, text=True).stdout.strip()
req = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": "Bearer " + key})
data = json.load(urllib.request.urlopen(req, timeout=30)).get("data") or {}
row = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "note": " ".join(sys.argv[1:]) or None}
for field in ("limit", "usage", "limit_remaining", "usage_daily", "is_free_tier", "rate_limit"):
    if field in data:
        row[field] = data[field]
open(os.path.join(HERE, "key-readings.jsonl"), "a").write(json.dumps(row) + "\n")
print(json.dumps(row))
