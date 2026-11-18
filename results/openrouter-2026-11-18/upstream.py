#!/usr/bin/env python3
"""Which upstream answered each reply. OpenRouter's Responses replies do not name it, so every reply id in
logs/*.usage.jsonl is looked up once in GET https://openrouter.ai/api/v1/generation?id=… (free) and appended to
upstreams.jsonl: the upstream that answered (`provider_name`), every attempt OpenRouter made (provider and status:
a fallback shows here), the model version, the session id OpenRouter used for the request and its token counts.
Nothing else of the record is kept (no account or workspace id). Ids not yet known to OpenRouter are tried on a later
pass.
    python3 results/openrouter-2026-11-18/upstream.py [--max 400]
"""
import glob
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "upstreams.jsonl")


def known():
    return {json.loads(x)["id"] for x in open(OUT) if x.strip()} if os.path.exists(OUT) else set()


def main():
    limit = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 400
    have = known()
    todo = []
    for path in sorted(glob.glob(os.path.join(HERE, "logs", "*.usage.jsonl"))):
        for line in open(path):
            if line.strip():
                r = json.loads(line)
                if r.get("reply_id") and r["reply_id"] not in have:
                    todo.append((r["label"], r["reply_id"]))
    if not todo:
        print("upstreams: nothing to look up")
        return
    key = subprocess.run([sys.executable, os.path.join(HERE, "key.py")], check=True, capture_output=True, text=True).stdout.strip()
    done = missing = 0
    with open(OUT, "a") as f:
        for label, gid in todo[:limit]:
            req = urllib.request.Request(f"https://openrouter.ai/api/v1/generation?id={gid}", headers={"Authorization": "Bearer " + key})
            try:
                d = json.load(urllib.request.urlopen(req, timeout=30))["data"]
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    missing += 1
                    continue
                if e.code == 429:
                    print("upstreams: 429 on the lookup, stopping this pass")
                    break
                raise
            f.write(json.dumps({
                "id": gid, "run": label, "created_at": d.get("created_at"), "model": d.get("model"),
                "upstream": d.get("provider_name"),
                "attempts": [{"provider": p.get("provider_name"), "status": p.get("status")} for p in d.get("provider_responses") or []],
                "session_id": d.get("session_id"), "native_tokens_prompt": d.get("native_tokens_prompt"),
                "native_tokens_cached": d.get("native_tokens_cached"), "native_tokens_completion": d.get("native_tokens_completion"),
                "native_tokens_reasoning": d.get("native_tokens_reasoning"), "total_cost": d.get("total_cost"),
                "finish_reason": d.get("finish_reason")}) + "\n")
            f.flush()
            done += 1
            time.sleep(0.15)
    print(f"upstreams: {done} looked up, {missing} not yet known, {max(0, len(todo) - limit)} left for the next pass")


if __name__ == "__main__":
    main()
