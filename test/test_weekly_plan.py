"""harness/plan.py (step G2): every value in exactly one state, the order, the window of 31 days, only the values no
source gives, plan/values.json. Nothing is sent: fixtures only. The plan's only clock is the night's date given to it
(DATE here, and others below): no test reads today's date.

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
            entry("openrouter", "a/documented", cache_doc=300, cache_status="not_contradicted"),
            entry("openrouter", "a/doc-zero", cache_doc=0),
            entry("openrouter", "a/pi", cache_pi=300, pi_standing="only"),
            entry("openrouter", "a/measured"),
            entry("openrouter", "a/unsteady"),
            entry("openrouter", "a/old", release="2026-10-29"),
            entry("openrouter", "a/undated", release=None),
        )
        o = observed([
            cache_row("openrouter", "a/measured", "direct", 900),
            cache_row("openrouter", "a/unsteady", "direct", 150, "2026-11-01"),
            cache_row("openrouter", "a/unsteady", "direct", 300, "2026-11-02"),
            cache_row("openrouter", "a/unsteady", "direct", 600, "2026-11-03"),
        ])
        plan = build(s, o)
        want = {"a/new": P.NEW, "a/documented": P.GIVEN, "a/doc-zero": P.GIVEN, "a/pi": P.GIVEN,
                "a/measured": P.MEASURED, "a/unsteady": P.UNSTEADY, "a/old": P.TOO_OLD, "a/undated": P.UNDATED}
        for model, state in want.items():
            self.assertEqual(item(plan, "openrouter", model)["state"], state, model)
        self.assertEqual(item(plan, "openrouter", "a/new", "output")["state"], P.NO_METHOD_STATE)
        self.assertEqual(item(plan, "openrouter", "a/new", "window")["state"], P.NEW)
        self.assertEqual(item(plan, "openrouter", "a/pi")["why"], "Pi's catalog: 300")
        self.assertEqual([i["model"] for i in plan["planned"] if i["quantity"] == "cache"], ["a/new"])

    def test_every_value_is_in_exactly_one_state_and_only_new_ones_are_planned(self):
        s = site(entry("openrouter", "a/x"), entry("devin", "m-1"), entry("openai-codex", "gpt-x"),
                 entry("openrouter", "a/agree", cache_doc=300, cache_status="not_contradicted"))
        o = observed([cache_row("openrouter", "a/agree", "direct", 300)])
        plan = build(s, o)
        keys = [i["key"] for i in plan["items"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(keys), 4 * 3)
        for i in plan["items"]:
            self.assertIn(i["state"], P.STATES)
        self.assertEqual(P.PLANNED, (P.NEW,))
        self.assertTrue(all(i["state"] == P.NEW for i in plan["planned"]))
        self.assertNotIn("openrouter|a/agree|cache", [i["key"] for i in plan["planned"]])

    def test_a_value_a_source_gives_is_never_measured_even_when_we_disagree_with_it(self):
        # The owner, 2026-11-26: only values nobody else gives. The old "in doubt" and "source moved" are gone.
        s = site(entry("openrouter", "a/x", cache_doc=300, cache_status="contradicted"),
                 entry("openrouter", "a/y", cache_pi=300, pi_standing="differs"))
        o = observed([cache_row("openrouter", "a/x", "direct", 150, "2026-11-01"),
                      cache_row("openrouter", "a/x", "direct", 600, "2026-11-02"),
                      cache_row("openrouter", "a/y", "direct", 600)])
        moved = {"values": {"openrouter|a/x|cache": {"stated": {"models_dev": 600, "pi": None}}}}
        plan = build(s, o, moved)
        self.assertEqual(item(plan, "openrouter", "a/x")["state"], P.MEASURED)
        self.assertEqual(item(plan, "openrouter", "a/y")["state"], P.MEASURED)
        self.assertEqual(build(site(entry("openrouter", "a/x", cache_doc=300)), observed())["planned"][0]["key"],
                         "openrouter|a/x|window")  # its cache lifetime is documented: only the window is new

    def test_a_window_models_dev_states_is_given(self):
        s = site(entry("openrouter", "a/x", win_doc=200000), entry("openrouter", "a/y"))
        plan = build(s, observed())
        self.assertEqual(item(plan, "openrouter", "a/x", "window")["state"], P.GIVEN)
        self.assertEqual(item(plan, "openrouter", "a/x", "window")["why"], "documented: 200000")
        self.assertEqual(item(plan, "openrouter", "a/y", "window")["state"], P.NEW)

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

    def test_the_sources_read(self):
        e = entry("openrouter", "a/x", cache_doc=0, cache_pi=300, win_doc=1000)
        self.assertEqual(P.given_by(e, "cache"), ["documented: 0", "Pi's catalog: 300"])
        self.assertEqual(P.given_by(e, "window"), ["documented: 1000"])
        self.assertEqual(P.given_by(None, "cache"), [])
        self.assertEqual(P.verdict(e, "output"), "unavailable")
        self.assertEqual(P.state_of("output", [], [], []), P.NEW)
        self.assertEqual(P.state_of("output", [{"value": 1}], [], []), P.MEASURED)

    def test_a_proxy_s_runs_do_not_make_a_login_value_measured(self):
        s = site(entry("devin", "m-1"))
        o = observed([cache_row("devin", "m-1", "cliproxyapi", 300), cache_row("devin", "m-1", "pi+cliproxyapi", 300)])
        self.assertEqual(item(build(s, o), "devin", "m-1")["state"], P.NEW)
        o2 = observed([cache_row("devin", "m-1", "devin-cli", 300)])
        self.assertEqual(item(build(s, o2), "devin", "m-1")["state"], P.MEASURED)

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

    def test_cost_never_keeps_a_value_out(self):
        s = site(entry("openai", "dear", price_in=500.0, price_out=2000.0))
        plan = build(s, observed())
        self.assertEqual(item(plan, "openai-api", "dear")["state"], P.NEW)
        self.assertGreater(item(plan, "openai-api", "dear")["estimate_usd"], 100)
        self.assertEqual([i["quantity"] for i in plan["planned"]], ["cache", "window"])
        self.assertIn("Estimate: API keys $", P.render(plan))


class Window(unittest.TestCase):
    """The window is the 31 days before the night's own date: the plan's clock is the date it is given."""

    def test_thirty_one_days(self):
        self.assertEqual(P.window_start(P.parse_day("2026-11-30")).isoformat(), "2026-10-30")
        self.assertEqual(P.window_start(P.parse_day("2027-03-01")).isoformat(), "2027-01-29")
        s = site(entry("openrouter", "a/in", release="2026-10-30"), entry("openrouter", "a/out", release="2026-10-29"))
        plan = build(s, observed())
        self.assertEqual(plan["window_since"], "2026-10-30")
        self.assertEqual(item(plan, "openrouter", "a/in")["state"], P.NEW)
        self.assertEqual(item(plan, "openrouter", "a/out")["state"], P.TOO_OLD)

    def test_the_night_s_date_is_the_only_clock(self):
        # The same files planned for nights years apart: only the date given moves the window, never today's.
        s = site(entry("openrouter", "a/x", release="2031-05-20"), entry("openrouter", "a/y", release="2026-11-20"))
        with tempfile.TemporaryDirectory() as t:
            later = P.build("2031-06-02", observed(), s, root=t)
            now = P.build(DATE, observed(), s, root=t)
            early = P.build("2020-01-06", observed(), s, root=t)
        self.assertEqual((item(later, "openrouter", "a/x")["state"], item(later, "openrouter", "a/y")["state"]),
                         (P.NEW, P.TOO_OLD))
        self.assertEqual((item(now, "openrouter", "a/x")["state"], item(now, "openrouter", "a/y")["state"]),
                         (P.NEW, P.NEW))  # a release after the night counts as inside
        self.assertEqual(early["window_since"], "2019-12-06")

    def test_never_a_model_released_before_the_window_whatever_its_state(self):
        s = site(entry("openrouter", "a/old", release="2026-06-01", cache_doc=300, cache_status="contradicted"))
        o = observed([cache_row("openrouter", "a/old", "direct", 150)])
        plan = build(s, o)
        self.assertEqual(item(plan, "openrouter", "a/old")["state"], P.TOO_OLD)
        self.assertEqual(plan["planned"], [])

    def test_a_login_s_own_id_dates_from_the_lab_and_never_from_when_it_was_first_seen(self):
        s = site(entry("anthropic", "claude-old-4-6", release="2026-02-01", canonical="anthropic/claude-old-4-6"))
        listed = {"providers": {"devin": {"date": DATE, "models": [
            {"id": "claude-old-4-6"}, {"id": "swe-9"}, {"id": "swe-8"}]}}}
        plan = build(s, observed(), {"first_seen": {"devin": {"swe-8": "2026-11-20"}}}, listed=listed)
        old = item(plan, "devin", "claude-old-4-6")
        self.assertEqual((old["state"], old["release_basis"]), (P.TOO_OLD, "lab release"))
        new = item(plan, "devin", "swe-9")  # first seen tonight, no release date: not measured, named
        self.assertEqual((new["state"], new["release_basis"], new["release"]), (P.UNDATED, P.NO_DATE, None))
        self.assertEqual(plan["newly_seen"]["devin"], {"claude-old-4-6": DATE, "swe-9": DATE})
        self.assertEqual(item(plan, "devin", "swe-8")["state"], P.UNDATED)
        self.assertEqual(plan["undated"], [("devin", "swe-9"), ("devin", "swe-8")])
        self.assertEqual(plan["planned"], [])
        text = P.render(plan)
        self.assertIn("## No release date known: not measured", text)
        self.assertIn("- devin (2): `swe-9`, `swe-8`", text)


def listing(provider, *rows):
    """A provider's listing as providers.dev serves it (/data/listings/<provider>.json, /api/v1/listings/<provider>):
    only the fields the plan reads, with others beside them."""
    return {"meta": {"dataset_version": "fixture"}, "data": {"provider": provider, "basis": "listed", "models": [
        {"id": i, "name": i, "owner": owner, "canonical": canonical, "released": released, "context_window": None,
         "sources": {"released": "models.dev" if released else None}} for i, released, owner, canonical in rows]}}


class ListingDates(unittest.TestCase):
    """A login model's release date: the route's entry, else its row in the login's listing (`released`), else the
    lab's own entry, else the lab's listing row (exactly one date known), else none: not measured."""

    def plan(self, s, listings, models, seen=None):
        s = dict(s, listings={p: P.listing_rows(doc) for p, doc in listings.items()})
        listed = {"providers": {"devin": {"date": DATE, "models": [{"id": m} for m in models]}}}
        return build(s, observed(), {"first_seen": {"devin": seen or {m: None for m in models}}}, listed)

    def test_the_order_entry_then_listing_row_then_lab_entry_then_lab_listing(self):
        s = site(entry("devin", "with-entry", release="2026-11-01"),
                 entry("google", "lab-entry", release="2026-11-03", canonical="google/lab-entry"))
        listings = {
            "devin": listing("devin", ("with-entry", "2026-01-01", None, None), ("row-only", "2026-11-02", None, None),
                             ("lab-entry", None, "google", None), ("lab-row", None, None, None),
                             ("nothing", None, None, None)),
            "google": listing("google", ("lab-entry", "2026-01-03", "google", None),
                              ("lab-row", "2026-11-04", "google", None))}
        plan = self.plan(s, listings, ["with-entry", "row-only", "lab-entry", "lab-row", "nothing"])
        got = {m: (item(plan, "devin", m)["release"], item(plan, "devin", m)["release_basis"])
               for m in ("with-entry", "row-only", "lab-entry", "lab-row", "nothing")}
        self.assertEqual(got, {"with-entry": ("2026-11-01", "release"), "row-only": ("2026-11-02", "listed release"),
                               "lab-entry": ("2026-11-03", "lab release"), "lab-row": ("2026-11-04", "lab release"),
                               "nothing": (None, P.NO_DATE)})
        self.assertEqual(item(plan, "devin", "row-only")["state"], P.NEW)
        self.assertEqual(item(plan, "devin", "nothing")["state"], P.UNDATED)

    def test_a_listing_date_moves_a_model_out_of_the_window_or_into_it(self):
        listings = {"devin": listing("devin", ("old-one", "2026-06-01", None, None),
                                     ("new-one", "2026-11-20", None, None))}
        plan = self.plan(site(), listings, ["old-one", "new-one"], seen={"old-one": DATE, "new-one": None})
        self.assertEqual(item(plan, "devin", "old-one")["state"], P.TOO_OLD)  # first seen today, released in June
        self.assertEqual(item(plan, "devin", "new-one")["state"], P.NEW)  # listed before discovery, dated now

    def test_a_lab_listing_with_two_dates_for_a_model_gives_none(self):
        listings = {"devin": listing("devin", ("twice", None, None, None)),
                    "google": listing("google", ("twice", "2026-11-01", None, None),
                                      ("x", "2026-11-05", None, "google/twice"))}
        plan = self.plan(site(), listings, ["twice"])
        self.assertEqual(item(plan, "devin", "twice")["release_basis"], P.NO_DATE)

    def test_a_reseller_s_row_of_a_lab_s_model_is_not_the_lab_s_date(self):
        listings = {"devin": listing("devin", ("claude-x", None, None, None)),
                    "anthropic": listing("anthropic", ("claude-x", "2026-11-01", None, None)),
                    "vivgrid": listing("vivgrid", ("claude-x", "2026-11-02", "anthropic", None),
                                       ("claude-x-2", "2026-11-03", None, "anthropic/claude-x"))}
        plan = self.plan(site(), listings, ["claude-x"])
        self.assertEqual(item(plan, "devin", "claude-x")["release"], "2026-11-01")

    def test_the_lab_s_own_entry_comes_before_its_listing_row(self):
        s = site(entry("openai", "gpt-x", release="2026-11-06", canonical="openai/gpt-x"))
        listings = {"openai": listing("openai", ("gpt-x", "2026-07-01", "openai", "openai/gpt-x"))}
        plan = self.plan(s, listings, ["gpt-x"])
        self.assertEqual(item(plan, "devin", "gpt-x")["release"], "2026-11-06")

    def test_an_api_key_route_reads_no_listing(self):
        s = site(entry("openrouter", "a/x", release=None))
        s["listings"] = {"openrouter": P.listing_rows(listing("openrouter", ("a/x", "2026-11-20", None, None)))}
        plan = build(s, observed(), {"first_seen": {"openrouter": {"a/x": None}}})
        self.assertEqual(item(plan, "openrouter", "a/x")["state"], P.UNDATED)

    def test_the_listing_s_shape(self):
        rows = P.listing_rows(listing("devin", ("a", "2026-11-02", "openai", "openai/a"), ("b", "2026-11", None, None),
                                      ("c", None, None, None)))
        self.assertEqual(rows, [{"id": "a", "released": "2026-11-02", "canonical": "openai/a", "owner": "openai"},
                                {"id": "b", "released": None, "canonical": None, "owner": None},
                                {"id": "c", "released": None, "canonical": None, "owner": None}])
        self.assertEqual(P.listing_rows({"data": {"provider": "x", "models": None}}), [])
        self.assertEqual(P.listing_rows(None), [])

    def test_a_copy_of_the_site_reads_the_listings_of_the_logins_and_the_labs(self):
        with tempfile.TemporaryDirectory() as folder:
            index = {"dataset_version": "fixture", "providers": [{"id": p} for p in ("devin", "openai", "mistral")],
                     "entries": [{"provider": "openrouter", "model": "openai/gpt-x", "canonical_id": "openai/gpt-x",
                                  "release_date": None, "type": "chat"}]}
            os.makedirs(os.path.join(folder, "listings"))
            with open(os.path.join(folder, "index.json"), "w") as f:
                json.dump(index, f)
            for p, rows in (("devin", [("swe-9", None, "openai", None)]), ("openai", [("swe-9", "2026-11-21", None,
                                                                                    None)]),
                            ("mistral", [("m", "2026-11-01", None, None)])):
                with open(os.path.join(folder, "listings", f"{p}.json"), "w") as f:
                    json.dump(listing(p, *rows), f)
            s = P.load_site(folder)
            self.assertEqual(sorted(s["listings"]), ["devin", "openai"])  # mistral is no entry's lab, no owner
            listed = {"providers": {"devin": {"date": DATE, "models": [{"id": "swe-9"}]}}}
            plan = build(s, observed(), {"first_seen": {"devin": {"swe-9": None}}}, listed)
            self.assertEqual((item(plan, "devin", "swe-9")["release"], item(plan, "devin", "swe-9")["state"]),
                             ("2026-11-21", P.NEW))


class Order(unittest.TestCase):
    def test_the_order(self):
        s = site(
            entry("openrouter", "a/new-old", release="2026-11-01", price_in=0.1),
            entry("openrouter", "a/new-recent", release="2026-11-20", price_in=5.0),
            entry("openrouter", "a/new-recent-cheap", release="2026-11-20", price_in=0.2),
            entry("openrouter", "a/new-fresh", release="2026-11-02", price_in=0.3),
        )
        values = {"first_seen": {"openrouter": {m: "2026-11-01" for m in ("a/new-old", "a/new-recent",
                                                                          "a/new-recent-cheap")}}}
        plan = build(s, observed(), values, last_night="2026-11-23")
        caches = [i["model"] for i in plan["planned"] if i["quantity"] == "cache"]
        self.assertEqual(caches, ["a/new-fresh", "a/new-recent-cheap", "a/new-recent", "a/new-old"])

    def test_logins_keep_the_vendor_s_own_order_within_a_state(self):
        listed = {"providers": {"devin": {"date": DATE, "models": [{"id": "z-1"}, {"id": "a-1"}]}}}
        s = dict(site(), listings={"devin": P.listing_rows(listing("devin", ("z-1", "2026-11-10", None, None),
                                                                   ("a-1", "2026-11-10", None, None)))})
        plan = build(s, observed(), {"first_seen": {"devin": {"z-1": "2026-11-01", "a-1": "2026-11-01"}}},
                     listed)
        self.assertEqual([i["model"] for i in plan["planned"]], ["z-1", "a-1"])

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
