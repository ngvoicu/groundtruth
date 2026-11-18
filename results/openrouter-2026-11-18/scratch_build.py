#!/usr/bin/env python3
"""The proof of manifest-entries.json, outside the commit: a copy of `main`'s tree as last fetched (git archive
origin/main: its manifest, its raw files and its build_observed.py) with this folder as it is now, this folder's runs
and excluded added to main's observed/manifest.json, then `python3 scripts/build_observed.py` in that copy. Reports whether it passes, how many cache rows it adds
to `main`'s observed.json, and the profile each new row lands in on providers.dev (site/src/core/cache.ts
lifetimeAsked: a non-empty string at options.ttl, options.prompt_cache_retention or options.prompt_cache_options.ttl
asks a lifetime; none asked is the short profile). With --separate, the runs of manifest-entries-upstream-changed.json
are added too (only to show they would build). Nothing in the worktree is changed.
    python3 results/openrouter-2026-11-18/scratch_build.py [--separate]
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FOLDER = os.path.basename(HERE)


def asked(options):
    for path in (["ttl"], ["prompt_cache_retention"], ["prompt_cache_options", "ttl"]):
        v = options
        for k in path:
            v = v.get(k) if isinstance(v, dict) else None
        if isinstance(v, str) and v:
            return v
    return None


tmp = tempfile.mkdtemp(prefix="or-scratch-")
try:
    subprocess.run(f"git archive origin/main | tar -x -C {tmp}", shell=True, cwd=ROOT, check=True)
    shutil.rmtree(os.path.join(tmp, "results", FOLDER), ignore_errors=True)
    shutil.copytree(HERE, os.path.join(tmp, "results", FOLDER))
    main_manifest = json.load(open(os.path.join(tmp, "observed", "manifest.json")))
    print("main at", subprocess.run(["git", "rev-parse", "--short", "origin/main"], cwd=ROOT, capture_output=True, text=True).stdout.strip())
    main_observed = json.loads(subprocess.run(["git", "show", "origin/main:observed.json"], cwd=ROOT, check=True,
                                              capture_output=True, text=True).stdout)
    add = json.load(open(os.path.join(HERE, "manifest-entries.json")))
    runs = list(add["runs"])
    if "--separate" in sys.argv:
        runs += [x["entry"] for x in json.load(open(os.path.join(HERE, "manifest-entries-upstream-changed.json")))["runs"]]
    main_manifest["runs"] += runs
    main_manifest["excluded"] += add["excluded"]
    json.dump(main_manifest, open(os.path.join(tmp, "observed", "manifest.json"), "w"), indent=1)
    out = subprocess.run([sys.executable, "scripts/build_observed.py"], cwd=tmp, capture_output=True, text=True)
    print(out.stdout.strip(), out.stderr.strip())
    if out.returncode:
        print(f"BUILD FAILED (exit {out.returncode})")
        sys.exit(1)
    built = json.load(open(os.path.join(tmp, "observed.json")))
    before = {e["id"] for e in main_observed["cache"]}
    new = [e for e in built["cache"] if e["id"] not in before]
    print(f"build passes: {len(built['cache'])} cache rows ({len(main_observed['cache'])} on main), {len(new)} added, "
          f"{len(built.get('excluded', []))} excluded ({len(main_observed.get('excluded', []))} on main)")
    for e in new:
        print(f"  {e['id']}: control {e['control']['warm']}/{e['control']['total']}, through {e['all_warm_through_s']}, "
              f"first cold {e['first_all_cold_s']}, options {json.dumps(e['options'])}, profile "
              f"{'long (asks ' + asked(e['options']) + ')' if asked(e['options']) else 'short'}")
    r1b = next(e for e in built["cache"] if e["id"] == "openrouter-direct-v0.2/R1b")
    print(f"  for comparison openrouter-direct-v0.2/R1b: options {json.dumps(r1b['options'])}, profile "
          f"{'long' if asked(r1b['options']) else 'short'}")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
