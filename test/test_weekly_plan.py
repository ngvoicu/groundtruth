"""harness/plan.py (step G2): every value in exactly one state, the order, the window of two months, plan/values.json.
Nothing is sent: fixtures only.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
import plan as P  # noqa: E402

DATE = "2026-11-30"
KINDS = {"direct": "direct", "codex-cli": "own_client", "devin-cli": "own_client", "cliproxyapi": "proxy",
         "pi+cliproxyapi": "proxy"}


def entry(provider, model, release="2026-11-10", cache_doc=None, cache_status=None, cache_pi=None, pi_standing=None,
          win_doc=None, win_status=None, price_in=1.0, price_out=4.0, canonical=None, typ="chat"):
    return {"provider": provider, "model": model, "type": typ, "release_date": release, "canonical_id": canonical,
            "price_in": price_in, "price_out": price_out, "price_write": None, "context": win_doc, "input": None,
            "cache": {"documented": cache_doc, "status": cache_status, "pi": cache_pi, "pi_standing": pi_standing},
            "window": {"documented": win_doc, "status": win_status, "pi": None, "pi_standing": None},
            "output": {"documented": None, "status": None, "pi": None, "pi_standing": None, "unavailable": True}}


def site(*entries):
    return {"dataset": "fixture", "entries": {f"{e['provider']}/{e['model']}": e for e in entries}}


def cache_row(route, model, client, through, date="2026-11-10", rid=None):
    return {"id": rid or f"x/{route}/{model}/{client}/{date}/{through}", "route": route, "model": model,
            "client": client, "date": date, "all_warm_through_s": through, "source": f"results/x/{model}-{date}.json"}


def observed(cache=(), limits=(), excluded=()):
    return {"client_kinds": KINDS, "cache": list(cache), "limits": list(limits), "excluded": list(excluded)}


def build(s, o, values=None, listed=None, root=None, last_night=None):
    with tempfile.TemporaryDirectory() as t:
        return P.build(DATE, o, s, values, listed, root=root or t, last_night=last_night)


def item(plan, route, model, q="cache"):
    return next(i for i in plan["items"] if i["key"] == f"{route}|{model}|{q}")


class States(unittest.TestCase):
    def test_one_fixture_per_state(self):
        s = site(
            entry("openrouter", "a/new"),
            entry("openrouter", "a/doubt", cache_doc=300, cache_status="contradicted"),
            entry("openrouter", "a/moved", cache_doc=600, cache_status="not_contradicted"),
            entry("openrouter", "a/agree", cache_doc=300, cache_status="not_contradicted"),
            entry("openrouter", "a/settled", cache_doc=300, cache_status="contradicted"),
            entry("openrouter", "a/ours"),
            entry("openrouter", "a/unsteady"),
            entry("openrouter", "a/old", release="2026-09-29"),
        )
        o = observed([
            cache_row("openrouter", "a/doubt", "direct", 150),
            cache_row("openrouter", "a/moved", "direct", 600),
            cache_row("openrouter", "a/agree", "direct", 300),
            cache_row("openrouter", "a/settled", "direct", 150, "2026-11-01"),
            cache_row("openrouter", "a/settled", "direct", 150, "2026-11-08"),
            cache_row("openrouter", "a/ours", "direct", 900),
            cache_row("openrouter", "a/unsteady", "direct", 150, "2026-11-01"),
            cache_row("openrouter", "a/unsteady", "direct", 300, "2026-11-02"),
            cache_row("openrouter", "a/unsteady", "direct", 600, "2026-11-03"),
        ])
        values = {"values": {"openrouter|a/moved|cache": {"stated": {"models_dev": 300, "pi": None}}}}
        plan = build(s, o, values)
        want = {"a/new": P.NEW, "a/doubt": P.DOUBT, "a/moved": P.MOVED, "a/agree": P.AGREEING,
                "a/settled": P.SETTLED, "a/ours": P.OURS, "a/unsteady": P.UNSTEADY, "a/old": P.TOO_OLD}
        for model, state in want.items():
            self.assertEqual(item(plan, "openrouter", model)["state"], state, model)
        self.assertEqual(item(plan, "openrouter", "a/new", "output")["state"], P.NO_METHOD_STATE)
        self.assertEqual(item(plan, "openrouter", "a/new", "window")["state"], P.NEW)

    def test_every_value_is_in_exactly_one_state_and_only_states_1_to_3_are_planned(self):
        s = site(entry("openrouter", "a/x"), entry("devin", "m-1"), entry("openai-codex", "gpt-x"),
                 entry("openrouter", "a/agree", cache_doc=300, cache_status="not_contradicted"))
        o = observed([cache_row("openrouter", "a/agree", "direct", 300)])
        plan = build(s, o)
        keys = [i["key"] for i in plan["items"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(keys), 4 * 3)
        for i in plan["items"]:
            self.assertIn(i["state"], P.STATES)
        self.assertTrue(all(i["state"] in P.PLANNED for i in plan["planned"]))
        self.assertNotIn("openrouter|a/agree|cache", [i["key"] for i in plan["planned"]])

    def test_two_measurements_that_disagree_are_in_doubt_and_a_third_decides(self):
        s = site(entry("openrouter", "a/x", cache_doc=300, cache_status="contradicted"))
        two = observed([cache_row("openrouter", "a/x", "direct", 150, "2026-11-01"),
                        cache_row("openrouter", "a/x", "direct", 600, "2026-11-02")])
        self.assertEqual(item(build(s, two), "openrouter", "a/x")["state"], P.DOUBT)
        three = observed(two["cache"] + [cache_row("openrouter", "a/x", "direct", 600, "2026-11-03")])
        self.assertEqual(item(build(s, three), "openrouter", "a/x")["state"], P.SETTLED)

    def test_three_of_which_no_two_agree_are_unsteady_and_an_ask(self):
        s = site(entry("devin", "m-1"))
        o = observed([cache_row("devin", "m-1", "devin-cli", v, f"2026-11-0{n}") for n, v in
                      enumerate((150, 300, 600), 1)])
        plan = build(s, o)
        self.assertEqual(item(plan, "devin", "m-1")["state"], P.UNSTEADY)
        self.assertEqual(plan["asks"], [{"kind": "unsteady-value", "route": "devin", "model": "m-1",
                                         "quantity": "cache", "values": [150, 300, 600]}])
        self.assertNotIn("devin|m-1|cache", [i["key"] for i in plan["planned"]])

    def test_a_value_whose_only_run_an_audit_excluded_counts_as_never_measured(self):
        with tempfile.TemporaryDirectory() as root:
            night = os.path.join(root, "results", "night-2026-11-23")
            os.makedirs(night)
            with open(os.path.join(night, "or-a-x.json"), "w") as f:
                f.write("{}")
            with open(os.path.join(night, "runs.json"), "w") as f:
                json.dump({"runs": [{"label": "or-a-x", "route": "openrouter", "model": "a/x", "quantity": "cache",
                                     "file": "results/night-2026-11-23/or-a-x.json"}]}, f)
            s = site(entry("openrouter", "a/x"))
            waiting = build(s, observed(), root=root)
            self.assertEqual(item(waiting, "openrouter", "a/x")["state"], P.WAITING)
            excluded = build(s, observed(excluded=[{"id": "night-2026-11-23/or-a-x", "reason": "x"}]), root=root)
            self.assertEqual(item(excluded, "openrouter", "a/x")["state"], P.NEW)

    def test_a_night_waiting_for_its_audit_holds_its_values_the_first_night_too(self):
        with tempfile.TemporaryDirectory() as root:
            night = os.path.join(root, "results", "own-clients-2026-11-23")
            os.makedirs(night)
            with open(os.path.join(night, "DV1.jsonl"), "w") as f:
                f.write(json.dumps({"event": "start", "harness": "devin", "model": "m-1-low"}) + "\n")
            plan = build(site(entry("devin", "m-1")), observed(), root=root)
            self.assertEqual(item(plan, "devin", "m-1")["state"], P.WAITING)
            self.assertEqual(item(plan, "devin", "m-1")["pending"], ["own-clients-2026-11-23"])

    def test_a_source_that_moved_brings_back_an_agreeing_or_settled_value(self):
        s = site(entry("openrouter", "a/x", cache_doc=600, cache_status="not_contradicted"))
        o = observed([cache_row("openrouter", "a/x", "direct", 600)])
        same = {"values": {"openrouter|a/x|cache": {"stated": {"models_dev": 600, "pi": None}}}}
        moved = {"values": {"openrouter|a/x|cache": {"stated": {"models_dev": 300, "pi": None}}}}
        self.assertEqual(item(build(s, o, same), "openrouter", "a/x")["state"], P.AGREEING)
        self.assertEqual(item(build(s, o, moved), "openrouter", "a/x")["state"], P.MOVED)
        self.assertEqual(item(build(s, o), "openrouter", "a/x")["state"], P.AGREEING)  # no record: not moved

    def test_agreement_not_available(self):
        e = entry("openrouter", "a/x")
        self.assertEqual(P.verdict(e, "output"), "unavailable")
        self.assertEqual(P.state_of("output", [], [], "unavailable", None, {}), P.NEW)
        self.assertEqual(P.state_of("output", [{"value": 1}], [], "unavailable", None, {}), P.OURS)

    def test_pi_disagreeing_is_a_disagreement(self):
        s = site(entry("openrouter", "a/x", cache_pi=300, pi_standing="differs"))
        o = observed([cache_row("openrouter", "a/x", "direct", 600)])
        self.assertEqual(item(build(s, o), "openrouter", "a/x")["state"], P.DOUBT)

    def test_a_proxy_s_runs_do_not_make_a_login_value_measured(self):
        s = site(entry("devin", "m-1"))
        o = observed([cache_row("devin", "m-1", "cliproxyapi", 300), cache_row("devin", "m-1", "pi+cliproxyapi", 300)])
        self.assertEqual(item(build(s, o), "devin", "m-1")["state"], P.NEW)
        o2 = observed([cache_row("devin", "m-1", "devin-cli", 300)])
        self.assertEqual(item(build(s, o2), "devin", "m-1")["state"], P.OURS)

    def test_a_run_that_asked_for_a_long_lifetime_is_another_value(self):
        s = site(entry("anthropic", "c-1"))
        long_run = dict(cache_row("anthropic-api", "c-1", "direct", 3600), options={"ttl": "1h"})
        short_run = dict(cache_row("anthropic-api", "c-1", "direct", 300, rid="s"), options={"ttl": "5m"})
        plan = build(s, observed([long_run, short_run]))
        self.assertEqual(item(plan, "anthropic-api", "c-1")["values"], [300])
        self.assertEqual(item(build(s, observed([long_run])), "anthropic-api", "c-1")["state"], P.NEW)
        self.assertFalse(P.short_profile({"prompt_cache_retention": "24h"}))
        self.assertFalse(P.short_profile({"prompt_cache_retention": "in_memory"}))
        self.assertTrue(P.short_profile({"reasoning": "low"}))

    def test_on_an_api_key_only_direct_runs_count(self):
        s = site(entry("openrouter", "a/x"))
        o = observed([cache_row("openrouter", "a/x", "cliproxyapi", 300)])
        self.assertEqual(item(build(s, o), "openrouter", "a/x")["state"], P.NEW)

    def test_no_method_is_named(self):
        s = site(entry("devin", "m-1"))
        plan = build(s, observed())
        self.assertEqual(item(plan, "devin", "m-1", "window")["state"], P.NO_METHOD_STATE)
        text = P.render(plan)
        self.assertIn("devin `m-1` window: no method yet", text)
        self.assertIn("devin `m-1` output: no method yet", text)


class Window(unittest.TestCase):
    def test_two_calendar_months(self):
        self.assertEqual(P.months_before(P.parse_day("2026-11-30"), 2).isoformat(), "2026-09-30")
        self.assertEqual(P.months_before(P.parse_day("2026-12-31"), 2).isoformat(), "2026-10-31")
        self.assertEqual(P.months_before(P.parse_day("2026-04-30"), 2).isoformat(), "2026-02-28")
        s = site(entry("openrouter", "a/in", release="2026-09-30"), entry("openrouter", "a/out", release="2026-09-29"))
        plan = build(s, observed())
        self.assertEqual(item(plan, "openrouter", "a/in")["state"], P.NEW)
        self.assertEqual(item(plan, "openrouter", "a/out")["state"], P.TOO_OLD)

    def test_never_a_model_released_more_than_two_months_ago_whatever_its_state(self):
        s = site(entry("openrouter", "a/old", release="2026-06-01", cache_doc=300, cache_status="contradicted"))
        o = observed([cache_row("openrouter", "a/old", "direct", 150)])
        moved = {"values": {"openrouter|a/old|cache": {"stated": {"models_dev": 600, "pi": None}}}}
        plan = build(s, o, moved)
        self.assertEqual(item(plan, "openrouter", "a/old")["state"], P.TOO_OLD)
        self.assertEqual(plan["planned"], [])

    def test_a_login_s_own_id_dates_from_the_lab_else_from_when_it_was_first_seen(self):
        s = site(entry("anthropic", "claude-old-4-6", release="2026-02-01", canonical="anthropic/claude-old-4-6"))
        listed = {"providers": {"devin": {"date": DATE, "models": [
            {"id": "claude-old-4-6"}, {"id": "swe-9"}, {"id": "swe-8", "first_seen": "2026-08-01"}]}}}
        plan = build(s, observed(), listed=listed)
        old = item(plan, "devin", "claude-old-4-6")
        self.assertEqual((old["state"], old["release_basis"]), (P.TOO_OLD, "lab release"))
        new = item(plan, "devin", "swe-9")
        self.assertEqual((new["state"], new["release_basis"], new["release"]), (P.NEW, "first seen", DATE))
        self.assertEqual(plan["newly_seen"]["devin"], {"claude-old-4-6": DATE, "swe-9": DATE})
        self.assertEqual(item(plan, "devin", "swe-8")["state"], P.TOO_OLD)
        seen = {"first_seen": {"devin": {"swe-9": "2026-09-01"}}}
        self.assertEqual(item(build(s, observed(), seen, listed), "devin", "swe-9")["state"], P.TOO_OLD)


class Order(unittest.TestCase):
    def test_the_order(self):
        s = site(
            entry("openrouter", "a/doubt", release="2026-11-20", cache_doc=300, cache_status="contradicted"),
            entry("openrouter", "a/moved", release="2026-11-21", cache_doc=600, cache_status="not_contradicted"),
            entry("openrouter", "a/new-old", release="2026-10-01", price_in=0.1),
            entry("openrouter", "a/new-recent", release="2026-11-20", price_in=5.0),
            entry("openrouter", "a/new-recent-cheap", release="2026-11-20", price_in=0.2),
            entry("openrouter", "a/new-fresh", release="2026-10-02", price_in=0.3),
        )
        o = observed([cache_row("openrouter", "a/doubt", "direct", 150),
                      cache_row("openrouter", "a/moved", "direct", 600)])
        values = {"values": {"openrouter|a/moved|cache": {"stated": {"models_dev": 300, "pi": None}}},
                  "first_seen": {"openrouter": {m: "2026-11-01" for m in ("a/doubt", "a/moved", "a/new-old",
                                                                          "a/new-recent", "a/new-recent-cheap")}}}
        plan = build(s, o, values, last_night="2026-11-23")
        caches = [i["model"] for i in plan["planned"] if i["quantity"] == "cache"]
        self.assertEqual(caches, ["a/new-fresh", "a/new-recent-cheap", "a/new-recent", "a/new-old", "a/doubt",
                                  "a/moved"])

    def test_logins_keep_the_vendor_s_own_order_within_a_state(self):
        listed = {"providers": {"devin": {"date": DATE, "models": [{"id": "z-1", "release_date": "2026-11-01"},
                                                                    {"id": "a-1", "release_date": "2026-11-01"}]}}}
        plan = build(site(), observed(), {"first_seen": {"devin": {"z-1": "2026-11-01", "a-1": "2026-11-01"}}},
                     listed)
        self.assertEqual([i["model"] for i in plan["planned"]], ["z-1", "a-1"])

    def test_ties_the_oldest_measurement_first(self):
        s = site(*(entry("openrouter", m, release="2026-11-01", cache_doc=300, cache_status="contradicted")
                   for m in ("a/b", "a/z")))
        o = observed([cache_row("openrouter", "a/b", "direct", 150, "2026-11-10"),
                      cache_row("openrouter", "a/z", "direct", 150, "2026-11-02")])
        plan = build(s, o)
        self.assertEqual([i["model"] for i in plan["planned"] if i["quantity"] == "cache"], ["a/z", "a/b"])

    def test_the_same_inputs_give_the_same_plan(self):
        s = site(*(entry("openrouter", f"a/{n}", release=f"2026-11-{10 + n % 5}", price_in=n % 3) for n in range(20)))
        a, b = build(s, observed()), build(s, observed())
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual(P.render(a), P.render(b))

    def test_a_model_warm_at_two_hours_gets_a_long_run(self):
        s = site(entry("devin", "m-1"))
        o = observed([cache_row("devin", "m-1", "cliproxyapi", 7200)])
        self.assertEqual(item(build(s, o), "devin", "m-1")["schedule"], "long")


class Values(unittest.TestCase):
    def test_first_time_then_kept_then_renewed(self):
        s1 = site(entry("openrouter", "a/x", cache_doc=300, cache_status="not_contradicted"))
        o = observed([cache_row("openrouter", "a/x", "direct", 300)])
        first = P.values_file(o, s1, None, today="2026-11-22")
        rec = first["values"]["openrouter|a/x|cache"]
        self.assertEqual((rec["count"], rec["stated"], rec["stated_date"]),
                         (1, {"models_dev": 300, "pi": None}, "2026-11-22"))
        s2 = site(entry("openrouter", "a/x", cache_doc=600, cache_status="not_contradicted"))
        kept = P.values_file(o, s2, first, today="2026-12-01")
        self.assertEqual(kept["values"]["openrouter|a/x|cache"]["stated"], {"models_dev": 300, "pi": None})
        self.assertEqual(item(build(s2, o, kept), "openrouter", "a/x")["state"], P.MOVED)
        o2 = observed(o["cache"] + [cache_row("openrouter", "a/x", "direct", 600, "2026-11-30")])
        renewed = P.values_file(o2, s2, kept, today="2026-12-01")
        self.assertEqual(renewed["values"]["openrouter|a/x|cache"]["stated"], {"models_dev": 600, "pi": None})

    def test_first_seen_is_kept(self):
        f = P.values_file(observed(), site(), {"first_seen": {"devin": {"a": "2026-10-01"}}},
                          first_seen={"devin": {"a": "2026-11-30", "b": "2026-11-30"}})
        self.assertEqual(f["first_seen"], {"devin": {"a": "2026-10-01", "b": "2026-11-30"}})

    def test_the_committed_file_is_the_first_time_record(self):
        path = os.path.join(HERE, "..", "plan", "values.json")
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data["schema"], 1)
        self.assertTrue(data["values"])
        for key, rec in data["values"].items():
            self.assertEqual(len(key.split("|")), 3, key)
            self.assertIn("stated", rec)


if __name__ == "__main__":
    unittest.main()
