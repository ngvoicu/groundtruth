#!/usr/bin/env python3
"""The results of this folder's runs, from their files: results.md (one row per run: control, warm checks per age,
warm through, first all cold, the upstreams that answered, samples whose check was answered by another upstream than
their priming, cost, and what providers.dev documented for the entry on 2026-11-18), results.json (the same, as data),
manifest-entries.json (the entries a finished run adds to observed/manifest.json; a run that failed goes to
`excluded` with its reason), and manifest-entries-upstream-changed.json (runs in which the upstream changed between a
sample's priming and its check, and runs pinned to one upstream: the entry each would have, and the checks that
crossed upstreams with their outcome, for the reviewer), and manifest-entries-cold-control.json (first runs whose
control read 0 cached tokens, each with its ~8,000-token run). A run still
running is listed and gets nothing in manifest-entries.json.
    python3 results/openrouter-2026-11-18/summary.py
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FOLDER = os.path.basename(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_observed as B  # noqa: E402
import ledger as L  # noqa: E402
import status as S  # noqa: E402

site = {e["model"]: e for e in json.load(open(os.path.join(HERE, "sources", "providers-dev-entries.json")))["entries"]}
led = L.compute()
windows = {}
if os.path.exists(os.path.join(HERE, "windows.jsonl")):
    for x in open(os.path.join(HERE, "windows.jsonl")):
        if x.strip():
            w = json.loads(x)
            windows[w["model"]] = w


def fmt_s(s):
    if s is None:
        return "–"
    return B.age_label(s)


def verdict(doc, through, first_cold, checks):
    """The site's documented lifetime against the run, in the site's sense (the reviewer's ruling 4, m-10767): holds
    when every check up to it was warm; contradicted only when at an age at or below it fewer than half the checks hit
    (by how much: the first such age); otherwise the misses are told as they are (n of m at an age, warm through)."""
    if doc is None:
        return "none documented"
    under = [a for a, v in sorted(checks.items()) if a <= doc and sum(v) * 2 < len(v)]
    if under:
        return f"{fmt_s(doc)} documented: contradicted, fewer than half the checks hit at {fmt_s(under[0])}"
    if through is not None and through >= doc:
        return f"{fmt_s(doc)} documented: holds (warm through {fmt_s(through)})"
    missed = [(a, v) for a, v in sorted(checks.items()) if a <= doc and not all(v)]
    if missed:
        a, v = missed[0]
        return (f"{fmt_s(doc)} documented: {sum(v)} of {len(v)} at {fmt_s(a)}; all warm through "
                f"{fmt_s(through) if through is not None else 'no age'}")
    return f"{fmt_s(doc)} documented: not reached by the run"


def upstream_answer(error):
    """'HTTP 504 "The operation was aborted", after Google AI Studio's 429 "…rate-limited upstream…"' from a probe error."""
    import re
    code = re.search(r"HTTP (\d+)", error)
    msgs = re.findall(r'"message":"([^"]+)"', error)
    raw = re.search(r'"raw":"([^"]{0,90})', error)
    prev = re.search(r'"previous_errors":\[\{"code":(\d+),"message":"[^"]*","provider_name":"([^"]+)"', error)
    out = f"HTTP {code.group(1) if code else '?'} \"{msgs[0] if msgs else ''}\""
    if prev:
        out += f", after a {prev.group(1)} of {prev.group(2)}"
    if raw:
        out += f" (\"{raw.group(1)}…\")"
    return out


rows, entries, excluded, separate = [], [], [], []
for r in S.runs:
    st = S.state(r)
    if st["state"] in ("not started",):
        continue
    e = site.get(r["model"], {})
    doc = (e.get("cache_lifetime_short") or {}).get("documented_s")
    row = {"label": r["label"], "model": r["model"], "state": st["state"], "status": st.get("status"),
           "usd": round(led["per_run"].get(r["label"], {}).get("usd", 0.0), 4), "site_documented_s": doc,
           "error": st.get("error")}
    if st["state"] == "left out":
        row["reason"] = S.dec["left_out"].get(r["label"])
        rows.append(row)
        continue
    ups, changed, unknown = S.upstreams(r["label"], st.get("salt"))
    row.update(upstreams=ups, upstream_changed=changed, upstream_unknown=unknown)
    if st.get("file") and st["state"] == "finished":
        path = f"results/{FOLDER}/{st['file']}"
        data = B.read_plain(path)
        j = json.load(open(os.path.join(ROOT, path)))
        summ = B.summarize(data["checks"])
        row.update(file=st["file"], control=("warm" if data["control"] == [True] else "cold") if data["control"] else "none",
                   control_tokens=(j.get("control") or {}).get("check"),
                   checks={B.age_label(a): f"{sum(v)}/{len(v)}" for a, v in sorted(data["checks"].items())},
                   late=data["late"], **summ, probe_version=j.get("probeVersion"),
                   verdict=verdict(doc, summ["all_warm_through_s"], summ["first_all_cold_s"], data["checks"]))
        rid = f"{FOLDER}/{r['label']}"
        ctl = (j.get("control") or {}).get("check") or {}
        if unknown and st["status"] != "failed":
            # OpenRouter's generation record of a reply comes some minutes late: the run waits for the next batch.
            row["pending"] = f"{unknown} reply(ies) whose upstream OpenRouter has not recorded yet: no entry until known"
        elif st["status"] == "failed" and not (
                "quota or rate refusal" in (st.get("error") or "") and data["control"] == [True] and data["checks"]
                and min(data["checks"]) == 150):
            reason = f"failed: {(st.get('error') or '')[:300]}"
            if "quota or rate refusal" in (st.get("error") or "") and data["checks"]:
                reason += (f" (its answered checks begin at {B.age_label(min(data['checks']))}, not 2.5 minutes, so the "
                           "build's rule for an evaluation leaves it out)")
            excluded.append({"id": rid, "reason": reason})
        elif st["status"] == "no-observable-cache" and (ctl.get("cachedTokens") or 0) > 0:
            # As main's AG1 - AG3 (round two): a control cached in part, under the probe's criterion, with no timed
            # check, is neither an expired cache nor none.
            excluded.append({"id": rid, "reason": f"lifetime inconclusive: the control was cached in part ({ctl.get('cachedTokens')} of "
                             f"{ctl.get('promptTokens')} tokens, under the probe's criterion of half), so the run ended with no timed check"})
        else:
            ent = {"id": rid, "file": path, "route": "openrouter", "client": "direct", "model": r["model"],
                   "models_dev": e.get("ref"), "base_model": e.get("canonical_id"), "options": r["options"]}
            if r["group"] == "free":
                ent["note"] = "paced: --concurrency 1 --prime-pause 3500 (OpenRouter's limit on free requests per minute)"
            if st["status"] == "failed":
                # The chief's ruling (m-10781), as round two's cut-off runs: the answered checks stand.
                last = max(data["checks"])
                ent["note"] = ((ent.get("note") + "; ") if ent.get("note") else "") + (
                    f"the run ended after its {B.age_label(last)} checks, at the next check, on an upstream's answer "
                    f"({upstream_answer(st.get('error') or '')}), which the probe's --stop-on-refusal "
                    "read as a rate refusal and did not retry; the checks answered before it stand, later ages untested")
            outcome = {c["sampleId"]: c for c in j.get("checks", [])}
            crossings, control_crossed = [], False
            for c in changed:
                if c["sample"] == "control":
                    control_crossed = True
                    res = "warm" if (j.get("control") or {}).get("warm") else "cold"
                    ct = (j.get("control") or {}).get("check") or {}
                else:
                    ck = outcome.get(c["sample"]) or {}
                    res = "warm" if ck.get("warm") else ("cold" if ck else "not checked (run stopped first)")
                    ct = ck
                crossings.append(f"{c['sample']}: primed on {c['upstreams'][0]}, answered by {c['upstreams'][-1]}"
                                 + (f" (replies {' → '.join(map(str, c['upstreams']))})" if len(c["upstreams"]) > 2 else "")
                                 + f": {res}" + (f" ({ct.get('cachedTokens')}/{ct.get('promptTokens')} cached)" if ct.get("promptTokens") else ""))
            row["crossings"] = crossings
            # The reviewer's rulings (m-10767): a pinned run is never a manifest run (excluded, its provider option
            # stated); a crossing in a control that missed, with no timed checks, is excluded; a run with crossings in
            # its timed checks is published as what the default route gives, the crossings told in its note.
            if r.get("separate"):
                excluded.append({"id": rid, "reason": "supplemental evidence, not a manifest run (the reviewer's ruling, "
                                 "m-10767): pinned to one upstream, options.provider = " + json.dumps(r["options"].get("provider"))
                                 + f"; {('crossings: ' + '; '.join(crossings)) if crossings else 'no check crossed upstreams'}"})
            elif control_crossed and data["control"] == [False] and not data["checks"]:
                excluded.append({"id": rid, "reason": "the control's re-send was answered by another upstream than the one "
                                 "primed, the control missed and there is no timed check: no lifetime measured (" + "; ".join(crossings) + ")"})
            else:
                if crossings:
                    ent["note"] = ((ent.get("note") + "; ") if ent.get("note") else "") + (
                        f"OpenRouter's default route: {len(crossings)} check(s) were answered by another upstream than the "
                        "one their sample was primed on (" + "; ".join(crossings) + "). Such a miss shows failed reuse "
                        "through the default route, not expiry at the upstream")
                entries.append(ent)
    elif st["state"] == "cut off":
        excluded.append({"id": f"{FOLDER}/{r['label']}", "reason": "cut off before its end (the process ended without a result file); the partial file is kept"})
    if r["model"] in windows:
        row["window"] = windows[r["model"]]
    rows.append(row)

json.dump(rows, open(os.path.join(HERE, "results.json"), "w"), indent=1)
# Window refusals that name a figure: one limits row each (the window named, no accepted size: no request near a
# limit was sent), backed by the raw row's message, as logins-2026-11-17's Fable row.
import re  # noqa: E402
limits = []
for model, w in windows.items():
    m = re.search(r"maximum context length is (\d+) tokens", w.get("message") or "")
    if w.get("status") and 400 <= w["status"] < 500 and m:
        e = site.get(model, {})
        plan_row = next(r for r in S.runs if r["model"] == model)
        limits.append({
            "route": "openrouter", "client": "direct", "model": model, "models_dev": e.get("ref"),
            "base_model": e.get("canonical_id"), "context": int(m.group(1)),
            "note": (f"OpenRouter's own refusal of a request of about 1.2 million tokens names the endpoint's window "
                     f"(\"maximum context length is {m.group(1)} tokens\"); OpenRouter lists context_length "
                     f"{plan_row['context_length']:,} and top_provider.context_length {plan_row['top_provider_context_length']:,}. "
                     "The refusal came from OpenRouter before any upstream; no large request was accepted (none was sent "
                     "near a limit), so no accepted size; the output limit was not tested"),
            "file": f"results/{FOLDER}/windows.jsonl",
            "evidence": [{"row_model": model, "message_has": f"maximum context length is {m.group(1)} tokens"}]})

json.dump({"comment": f"Empty since the reviewer's rulings on batch 1 (m-10767): runs with crossings in their timed "
           "checks are in manifest-entries.json with the crossings in their note; a pinned run and a control crossing "
           "with no timed check are in its excluded. Kept so that the earlier commits (f1cca4d, 6abf96d) read the same.",
           "runs": separate}, open(os.path.join(HERE, "manifest-entries-upstream-changed.json"), "w"), indent=1)
# The reviewer's ruling 5 (m-10767): a first run and its larger-prompt run that both read 0 with a valid control and
# known upstream are both published, with that said in their notes.
ent_by_id = {e["id"]: e for e in entries}

# The chief's ruling (m-10781): where the ~2,500-token run read 0 and the ~8,000-token run's control hit, only the
# larger-prompt run is a manifest run; the small one goes under excluded, and the large one's note says so.
for r in S.runs:
    if not r.get("larger_prompt_of"):
        continue
    fid, bid = f"{FOLDER}/{r['larger_prompt_of']}", f"{FOLDER}/{r['label']}"
    fx = next((x for x in rows if x["label"] == r["larger_prompt_of"]), {})
    bx = next((x for x in rows if x["label"] == r["label"]), {})
    small_zero = fx.get("status") == "no-observable-cache" and not (fx.get("control_tokens") or {}).get("cachedTokens")
    if small_zero and bx.get("control") == "warm" and bid in ent_by_id:
        big = ent_by_id[bid]
        big["note"] = ((big["note"] + "; ") if big.get("note") else "") + (
            f"the same request with a ~2,500-token prompt ({fid}) read no cached token at its control: that prompt was "
            "under the smallest cacheable size; this run with ~8,000 tokens is the measurement")
        if fid in ent_by_id:
            entries.remove(ent_by_id.pop(fid))
            excluded.append({"id": fid, "reason": "no cache read at about 2,500 tokens (the control read 0 cached "
                             f"tokens); the 8,000-token run ({bid}) shows the prompt was under the smallest cacheable size"})


def zero(x):
    return x.get("status") == "no-observable-cache" and not (x.get("control_tokens") or {}).get("cachedTokens") \
        and not x.get("upstream_unknown") and not x.get("upstream_changed")


for r in S.runs:
    if not r.get("larger_prompt_of"):
        continue
    first, big = ent_by_id.get(f"{FOLDER}/{r['larger_prompt_of']}"), ent_by_id.get(f"{FOLDER}/{r['label']}")
    fx = next((x for x in rows if x["label"] == r["larger_prompt_of"]), {})
    bx = next((x for x in rows if x["label"] == r["label"]), {})
    if first and big and zero(fx) and zero(bx):
        for ent, other in ((first, r["label"]), (big, r["larger_prompt_of"])):
            ent["note"] = ((ent["note"] + "; ") if ent.get("note") else "") + (
                f"no cache read observed with about 2,500- and 8,000-token prompts (this run and {FOLDER}/{other}: "
                "neither control read a cached token)")

json.dump({"comment": f"Entries for observed/manifest.json from results/{FOLDER} (branch campaign/openrouter): add runs "
           "to runs, excluded to excluded and limits to limits. Finished runs only; not applied here; a later task "
           "assembles the manifest.",
           "runs": entries, "excluded": excluded, "limits": limits}, open(os.path.join(HERE, "manifest-entries.json"), "w"), indent=1)

# The chief's decision (m-10759): first runs whose control read 0 cached tokens at the default ~2,500 tokens, each
# with its run of about 8,000 tokens once that exists (the assembler holds the cold rows out until then).
by_label = {x["label"]: x for x in rows}
all_entries = {e["id"]: e for e in entries} | {x["entry"]["id"]: x["entry"] for x in separate}
cold = []
for r in S.runs:
    x = by_label.get(r["label"])
    if r.get("larger_prompt_of") or not x or x.get("status") != "no-observable-cache" or (x.get("control_tokens") or {}).get("cachedTokens"):
        continue
    big = next((q for q in S.runs if q.get("larger_prompt_of") == r["label"]), None)
    bx = by_label.get(big["label"]) if big else None
    item = {"run": all_entries.get(f"{FOLDER}/{r['label']}") or {"id": f"{FOLDER}/{r['label']}"},
            "control": f"0 of {(x.get('control_tokens') or {}).get('promptTokens')} tokens cached"}
    if not big:
        item["larger_prompt_run"] = None
        item["state"] = "larger-prompt run not planned yet"
    elif not bx or bx["state"] != "finished":
        item["larger_prompt_run"] = {"label": big["label"], "state": bx["state"] if bx else "not started"}
        item["state"] = "larger-prompt run not finished"
    else:
        ct = bx.get("control_tokens") or {}
        item["larger_prompt_run"] = {"entry": all_entries.get(f"{FOLDER}/{big['label']}") or {"id": f"{FOLDER}/{big['label']}", "excluded": True},
                                     "status": bx.get("status"), "control": f"{ct.get('cachedTokens')} of {ct.get('promptTokens')} tokens cached",
                                     "all_warm_through_s": bx.get("all_warm_through_s"), "first_all_cold_s": bx.get("first_all_cold_s")}
        item["state"] = (f"the larger-prompt run failed: {(bx.get('error') or '')[:160]}" if bx.get("status") == "failed" else
                         "the larger prompt read 0 again: two runs say no observable cache"
                         if bx.get("status") == "no-observable-cache" and not ct.get("cachedTokens") else
                         "the larger prompt was cached: see its run" if bx.get("control") == "warm" else "see the larger-prompt run")
    cold.append(item)
json.dump({"comment": f"First runs of results/{FOLDER} whose control read 0 cached tokens at the default ~2,500-token "
           "prompt (no observable cache), each with its run of its own with a ~8,000-token prompt (as "
           "cpa-latest-2026-11-06/L1b) once that exists (the chief's decision, m-10759). The first runs stay in "
           "manifest-entries.json as summary.py builds it; the assembler holds them out until their larger-prompt run "
           "exists.", "runs": cold}, open(os.path.join(HERE, "manifest-entries-cold-control.json"), "w"), indent=1)
with open(os.path.join(HERE, "results.md"), "w") as md:
    md.write("# Results, run by run\n\nWritten by `summary.py` from the run files, `logs/*.usage.jsonl`, `upstreams.jsonl` "
             "and `sources/providers-dev-entries.json`. Checks: warm of total per age. Upstream: the providers that "
             "answered the run's replies (OpenRouter's generation records).\n\n")
    md.write("| Run | Model | Status | Control | Checks (warm/total per age) | Warm through | First all cold | Upstreams | Upstream changed | USD | providers.dev 2026-11-18 |\n")
    md.write("|---|---|---|---|---|---|---|---|---|---|---|\n")
    for x in rows:
        if x["state"] == "left out":
            md.write(f"| `{x['label']}` | `{x['model']}` | left out | | {x.get('reason') or ''} | | | | | {x['usd']:.4f} | |\n")
            continue
        checks = ", ".join(f"{a} {v}" for a, v in (x.get("checks") or {}).items())
        ct = x.get("control_tokens") or {}
        ctrl = f"{x.get('control', '')} ({ct.get('cachedTokens')}/{ct.get('promptTokens')})" if ct else x.get("control", "")
        chg = "; ".join(f"{c['sample']}: {' → '.join(map(str, c['upstreams']))}" for c in x.get("upstream_changed") or []) or "none"
        status = x.get("status") or x["state"]
        if x.get("error") and status == "failed":
            status += ": " + x["error"][:140].replace("|", "/")
        if x.get("pending"):
            status += f" (entry pending: {x['pending']})"
        md.write(f"| `{x['label']}` | `{x['model']}` | {status} | {ctrl} | {checks} | {fmt_s(x.get('all_warm_through_s'))} | "
                 f"{fmt_s(x.get('first_all_cold_s'))} | {', '.join(map(str, x.get('upstreams') or []))} | {chg} | {x['usd']:.4f} | "
                 f"{x.get('verdict', '')} |\n")
print(f"{len(rows)} runs listed, {len(entries)} manifest entries, {len(separate)} apart (upstream changed or pinned), {len(excluded)} excluded")
