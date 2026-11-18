#!/usr/bin/env python3
"""Prints the owner's OpenAI API key from CLIProxyAPI's configuration (the entry whose base URL is
https://api.openai.com/v1), for capture into an environment variable (CACHE_PROBE_KEY=$(python3 key.py openai)).
Only reads the file. Never run it where its output is shown or kept. As ../direct-2026-11-17/key.py, OpenAI only."""
import sys

import yaml

conf = yaml.safe_load(open("/opt/homebrew/etc/cliproxyapi.conf"))["api-keys"]
if sys.argv[1:] != ["openai"]:
    raise SystemExit("usage: key.py openai")
entries = [e for e in conf["codex"] if e.get("base-url", "").rstrip("/") == "https://api.openai.com/v1"]
if len(entries) != 1 or len(entries[0]["keys"]) != 1:
    raise SystemExit("expected exactly one openai entry with one key")
print(entries[0]["keys"][0]["api-key"])
