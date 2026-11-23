#!/usr/bin/env python3
"""The model ids the night accepts: the checked list in the repository, harness/model-ids.json, and nothing else
(docs/own-clients.md, section 1, rule 7). No client is run and nothing is asked of a vendor to list models: an id is
added to the list only with how it was checked. On 2026-11-23 DV12 asked Devin for `deepseek-v4-pro-low`, an id Devin
does not have ("Unknown model"); `--dry-run` and `--go` now refuse a run whose id is not in the list, by name. An id
that is listed but wrong still fails at its baseline, after three requests, as DV12 did.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKED = os.path.join(HERE, "model-ids.json")


def checked(client, path=CHECKED):
    """The ids of the checked list of `client` (a set)."""
    with open(path) as f:
        return set(json.load(f)[client]["ids"])


def unknown(steps, path=CHECKED):
    """`id (model)` of each step whose model id is not in its client's checked list."""
    lists = {}
    bad = []
    for s in steps:
        c = s["harness"]
        if c not in lists:
            lists[c] = checked(c, path)
        if s["model"] not in lists[c]:
            bad.append(f"{s['id']} ({s['model']})")
    return bad
