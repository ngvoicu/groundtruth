#!/usr/bin/env python3
"""Prints one of the owner's API keys from CLIProxyAPI's configuration, for capture into an environment variable
(CACHE_PROBE_KEY=$(python3 key.py openai)). Only reads the file. Never run it where its output is shown or kept."""
import sys

import yaml

conf = yaml.safe_load(open("/opt/homebrew/etc/cliproxyapi.conf"))["api-keys"]
which = sys.argv[1]
if which == "openai":
    entries = [e for e in conf["codex"] if e.get("base-url", "").rstrip("/") == "https://api.openai.com/v1"]
elif which == "anthropic":
    entries = [e for e in conf["claude"] if e.get("name") == "claude-1"]
else:
    raise SystemExit("usage: key.py openai|anthropic")
if len(entries) != 1 or len(entries[0]["keys"]) != 1:
    raise SystemExit(f"expected exactly one {which} entry with one key")
print(entries[0]["keys"][0]["api-key"])
