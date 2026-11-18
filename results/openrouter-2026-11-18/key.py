#!/usr/bin/env python3
"""Prints the OpenRouter key of this campaign from the macOS Keychain, for capture straight into an environment
variable (CACHE_PROBE_KEY="$(python3 key.py)"). Only reads. Never run it where its output is shown or kept."""
import os
import subprocess

print(subprocess.run(["security", "find-generic-password", "-a", os.environ["USER"], "-s", "providers.dev OPENROUTER_API_KEY",
                      "-w"], check=True, capture_output=True, text=True).stdout.strip())
