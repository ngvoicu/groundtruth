"""harness/discover.py and harness/listed_schema.py (step G1, Provimux's model-lists.md 9.1 and 10): discovery of each
login's offered models into listed.json, from a saved Provimux answer or a fake Provimux on a free local port, with a
fake `gh` for GitHub (test/discover_fakes.py). Nothing is sent anywhere else.

    python3 -m unittest discover -s test -p "test_*.py"
"""
import contextlib
import io
import json
import os
import plistlib
import socket
import subprocess
import sys
import tempfile
import unittest

from discover_fakes import (ANSWER, ROOT, TODAY, YESTERDAY, Base, Connections, D, dump, load, provimux, read)
import listed_schema as S  # noqa: E402

KEY = "test-management-key-0123456789"


def changed(edit):
    answer = load(ANSWER)
    edit(answer)
    return answer


class FromTheAnswer(Base):
    def test_two_logins_of_one_type_are_joined_and_named_by_devin_s_own_ids(self):
        code, words = self.from_answer(ANSWER)
        self.assertEqual(code, 0, words)
        devin = self.written()["providers"]["devin"]
        self.assertEqual((devin["date"], devin["client"]), (TODAY, "provimux"))
        # login a: argon, neon, swe-2; login b: opus, argon, swe-2. The union, by Devin's ids (no devin/ prefix).
        self.assertEqual([m["id"] for m in devin["models"]], ["claude-opus-5-5", "gemini-4-argon", "gemini-4-neon", "swe-2"])
        self.assertEqual(devin["models"][1], {"id": "gemini-4-argon", "name": "Gemini 4 Argon", "context_window": 1048576,
                                              "max_output": 65536, "input_modalities": ["text", "image"],
                                              "reasoning": {"levels": ["low", "medium", "high"]}})
        swe = devin["models"][3]
        self.assertNotIn("context_window", swe)  # the two logins state it differently, and nothing was published
        self.assertEqual(swe["reasoning"], {"levels": ["low", "high"]})  # "max-fast" is not a level: dropped
        self.assertIn("disagree on: swe-2 context_window", self.logged())

    def test_only_the_four_listings_are_written(self):
        code, _ = self.from_answer(ANSWER)
        self.assertEqual(code, 0)
        providers = self.written()["providers"]
        # Antigravity, Gemini keys and Vertex are not discovery's; Meta has no held list and was never published.
        self.assertEqual(sorted(providers), ["claude-subscription", "devin", "openai-codex"])
        sol = providers["openai-codex"]["models"][0]
        self.assertNotIn("max_output", sol)  # a list that states no output limit states nothing
        self.assertNotIn("output_modalities", sol)
        self.assertIn("meta-subscription: not published yet, and not a complete day: it waits for one", self.logged())

    def test_a_list_provimux_no_longer_holds_is_not_read(self):
        def expire(a):
            for r in a["logins"]:
                if r["provider"] == "claude":
                    r["live"]["held"], r["live"]["expired"] = False, True
        self.from_answer(changed(expire))
        self.assertNotIn("claude-subscription", self.written()["providers"])

    def test_the_part_s_date_is_the_oldest_of_the_joined_lists_and_never_goes_back(self):
        def older(a):
            for r in a["logins"]:
                if r["auth_index"] == "b39e04c6f1d7a218":
                    r["live"]["fetched_at"] = "2026-11-22T23:59:00Z"
        self.from_answer(changed(older))
        self.assertEqual(self.written()["providers"]["devin"]["date"], "2026-11-22")
        later = load(YESTERDAY)
        later["providers"]["devin"]["date"] = "2026-11-25"
        self.github(later)
        self.from_answer(changed(older))
        self.assertEqual(self.written()["providers"]["devin"]["date"], "2026-11-25")

    def test_an_id_the_site_would_refuse_is_left_out_and_the_rest_is_written(self):
        def big(a):
            r = next(r for r in a["logins"] if r["auth_index"] == "a8d167b7d82c8c15")
            r["live_list"].append({"id": "devin/Big-Model", "display_name": None, "context": None, "output": None,
                                   "input_modalities": [], "output_modalities": [], "reasoning_levels": []})
            r["live"]["listed_models"] += 1
        code, _ = self.from_answer(changed(big))
        self.assertEqual(code, 0)
        self.assertNotIn("Big-Model", read(self.out))
        self.assertIn("left out Big-Model: not a model id", self.logged())

    def test_the_same_answer_twice_publishes_once(self):
        self.github(load(YESTERDAY))
        self.assertEqual(self.from_answer(ANSWER, "--publish")[0], 0)
        code, words = self.from_answer(ANSWER, "--publish")
        self.assertEqual(code, 0, words)
        self.assertIn("(unchanged)", words)
        self.assertEqual(len(self.commits()), 1)


class Union(Base):
    def test_the_published_models_stay_and_today_s_are_added_with_today_s_values(self):
        published = load(YESTERDAY)
        published["providers"]["devin"]["models"] = [{"id": "devin-retired", "name": "Retired"},
                                                     {"id": "gemini-4-argon", "context_window": 5}]
        self.github(published)
        code, words = self.from_answer(ANSWER, "--publish")
        self.assertEqual(code, 0, words)
        devin = self.github_file()["providers"]["devin"]
        self.assertEqual([m["id"] for m in devin["models"]],
                         ["claude-opus-5-5", "devin-retired", "gemini-4-argon", "gemini-4-neon", "swe-2"])
        self.assertEqual(devin["date"], TODAY)  # both enabled logins gave a complete list
        argon = next(m for m in devin["models"] if m["id"] == "gemini-4-argon")
        self.assertEqual(argon["context_window"], 1048576)  # today's value replaces the published one
        # Meta: its only login has no list today: the published part and date stay.
        self.assertEqual(self.github_file()["providers"]["meta-subscription"],
                         load(YESTERDAY)["providers"]["meta-subscription"])

    def test_a_published_value_stays_where_today_s_logins_disagree(self):
        published = load(YESTERDAY)
        published["providers"]["devin"]["models"] = [{"id": "swe-2", "context_window": 131072}]
        self.github(published)
        self.from_answer(ANSWER)
        swe = next(m for m in self.written()["providers"]["devin"]["models"] if m["id"] == "swe-2")
        self.assertEqual(swe["context_window"], 131072)


class Ages(Base):
    def test_age_comes_from_github_s_file_one_ask_and_one_notification_per_stale_part(self):
        published = load(YESTERDAY)
        published["providers"]["meta-subscription"]["date"] = "2026-11-19"
        self.github(published)
        code, words = self.from_answer(ANSWER)
        self.assertEqual(code, 0, words)
        ask = "ASK: discovery has no fresh list for meta-subscription: 5 days old on GitHub (more than 3)"
        self.assertIn(ask, words)
        self.assertIn(ask, self.logged())
        self.assertRegex(self.logged(), r"age: devin 1 day \(published 2026-11-23\)")  # GitHub's, not today's
        self.assertEqual(len(self.notifications()), 1)
        self.assertIn("meta-subscription", self.notifications()[0][-1])
        code, words = self.from_answer(ANSWER)  # the next run: the ask again, no second notification
        self.assertIn(ask, words)
        self.assertEqual(len(self.notifications()), 1)

    def test_three_days_is_not_yet_an_ask(self):
        self.github(load(YESTERDAY))
        _, words = self.from_answer(ANSWER, date="2026-11-26")
        self.assertNotIn("ASK", words)
        self.assertEqual(self.notifications(), [])

    def test_provimux_unreachable_reports_the_ages_last_seen_on_github(self):
        published = load(YESTERDAY)
        published["providers"]["meta-subscription"]["date"] = "2026-11-19"
        self.github(published)
        self.from_answer(ANSWER)
        before = read(self.out)
        with socket.socket() as s:  # a free port nobody listens on
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        with Connections(allowed_port=port).watching():
            code, words = self.run_with(["--base-url", f"http://127.0.0.1:{port}", "--date", TODAY],
                                        key_finder=lambda: KEY)
        self.assertEqual(code, 1)
        self.assertIn("Provimux could not be reached", words)
        self.assertIn("ASK: discovery has no fresh list for meta-subscription", words)
        self.assertEqual(read(self.out), before)


class Schema(unittest.TestCase):
    def good(self):
        return load(YESTERDAY)

    def test_the_fixtures_and_a_written_file_pass(self):
        self.assertEqual(S.validate(self.good()), [])

    def test_a_field_outside_the_schema_is_refused_at_every_level(self):
        cases = [
            lambda d: d.__setitem__("generated_by", "x"),
            lambda d: d["providers"]["devin"].__setitem__("logins", 2),
            lambda d: d["providers"]["devin"]["models"][0].__setitem__("first_seen", "2026-11-20"),
            lambda d: d["providers"]["devin"]["models"][0].__setitem__("reasoning", {"levels": ["low"], "effort": "x"}),
        ]
        for change in cases:
            doc = self.good()
            change(doc)
            self.assertTrue(any("is not in the schema" in e for e in S.validate(doc)))

    def test_identity_shapes_are_refused_wherever_they_are(self):
        for change in (
            lambda d: d["providers"]["devin"]["models"][0].__setitem__("email", "office@providers.dev"),
            lambda d: d["providers"]["devin"]["models"][0].__setitem__("name", "office@providers.dev"),
            lambda d: d["providers"]["devin"]["models"][0].__setitem__("id", "devin-login-b.json"),
            lambda d: d["providers"]["devin"]["models"][0].__setitem__("description", "token sk-abcdefabcdefabcdef"),
            lambda d: d["providers"]["devin"].__setitem__("client", "a8d167b7d82c8c15a8d167b7d82c8c15"),
        ):
            doc = self.good()
            change(doc)
            self.assertNotEqual(S.validate(doc), [])

    def test_other_shapes_are_refused(self):
        for change in (
            lambda d: d.__setitem__("schema", 2),
            lambda d: d["providers"]["devin"].__setitem__("models", []),
            lambda d: d["providers"]["devin"].__setitem__("date", "24.11.2026"),
            lambda d: d["providers"]["devin"]["models"].append({"id": "swe-2"}),
            lambda d: d["providers"]["devin"]["models"][0].__setitem__("context_window", 0),
            lambda d: d["providers"]["devin"]["models"][0].__setitem__("hidden", "no"),
            lambda d: d["providers"].__setitem__("Devin Login", d["providers"]["devin"]),
        ):
            doc = self.good()
            change(doc)
            self.assertNotEqual(S.validate(doc), [], doc)

    def test_the_command_ci_runs_refuses_a_bad_file_and_passes_a_good_or_absent_one(self):
        cmd = [sys.executable, os.path.join(ROOT, "harness", "listed_schema.py")]
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, "listed.json")
            self.assertEqual(subprocess.run(cmd + [path], capture_output=True).returncode, 0)  # absent
            dump(self.good(), path)
            self.assertEqual(subprocess.run(cmd + [path], capture_output=True).returncode, 0)
            doc = self.good()
            doc["providers"]["devin"]["models"][0]["account"] = "login-b"
            dump(doc, path)
            r = subprocess.run(cmd + [path], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("field 'account' is not in the schema", r.stdout)

    def test_ci_and_the_commit_hook_run_it(self):
        self.assertIn("python3 harness/listed_schema.py listed.json",
                      read(os.path.join(ROOT, ".github", "workflows", "ci.yml")))
        self.assertIn('(cd "$tmp" && python3 harness/listed_schema.py listed.json)',
                      read(os.path.join(ROOT, "scripts", "pre-commit")))


class GithubFile(Base):
    def test_a_github_file_that_fails_its_schema_stops_everything(self):
        doc = load(YESTERDAY)
        doc["providers"]["devin"]["models"][0]["first_seen"] = "2026-11-20"
        self.github(json.dumps(doc))
        code, words = self.from_answer(ANSWER, "--publish")
        self.assertEqual(code, 1)
        self.assertIn("does not pass its schema", words)
        self.assertEqual(self.puts(), [])
        self.assertFalse(os.path.exists(self.out))

    def test_a_large_file_is_read_by_its_blob_and_checked_against_its_sha(self):
        self.github(load(YESTERDAY))
        open(os.path.join(self.fake, "large"), "w").close()
        code, words = self.from_answer(ANSWER)
        self.assertEqual(code, 0, words)
        self.assertIn("antigravity: in GitHub's file, not listed by discovery: left out", self.logged())
        self.assertTrue(any("git/blobs/" in " ".join(c["argv"]) for c in self.calls()))

    def test_without_publish_github_is_only_read(self):
        self.github(load(YESTERDAY))
        code, words = self.from_answer(ANSWER)
        self.assertEqual(code, 0, words)
        self.assertEqual(self.puts(), [])
        self.assertTrue(all(c["argv"][c["argv"].index("--method") + 1] == "GET" for c in self.calls()))
        self.assertEqual(self.github_file(), load(YESTERDAY))


class Identity(Base):
    def identity_values(self):
        values = set()
        for row in load(ANSWER)["logins"]:
            values.add(row["auth_index"])
            values.update(v for v in row["login"].values() if v)
        return values

    def test_no_identity_field_of_the_answer_is_ever_written(self):
        self.github(load(YESTERDAY))
        self.from_answer(ANSWER, "--publish")
        text = self.put_bytes()[0].decode()
        for value in self.identity_values():
            self.assertNotIn(value, text)
        for word in ("auth_index", "login", "email", "label", "registered_models", "learned_models", "fetched_at",
                     "last_failure", "disabled", "source"):
            self.assertNotIn(f'"{word}"', text)

    def test_identity_smuggled_into_a_vendor_s_entry_is_not_written(self):
        def smuggle(a):
            r = next(r for r in a["logins"] if r["provider"] == "claude")
            r["live_list"][0].update({"email": "office@providers.dev", "account_id": "acct-123456", "owner": "login-b"})
            r["live_list"][1]["display_name"] = "office@providers.dev"
            r["live_list"][2]["input_modalities"] = ["text", "devin-login-b.json"]
        code, _ = self.from_answer(changed(smuggle))
        self.assertEqual(code, 0)
        text = read(self.out)
        for value in ("office@providers.dev", "acct-123456", "login-b", "devin-login-b.json", "account_id"):
            self.assertNotIn(value, text)
        ids = [m["id"] for m in self.written()["providers"]["claude-subscription"]["models"]]
        self.assertEqual(ids, ["claude-haiku-5-5", "claude-sonnet-5-5"])

    def test_a_label_found_in_a_model_s_name_drops_that_model_only(self):
        def label(a):
            next(r for r in a["logins"] if r["provider"] == "claude")["login"]["label"] = "Opus 5.5"
        code, words = self.from_answer(changed(label))
        self.assertEqual(code, 0, words)
        ids = [m["id"] for m in self.written()["providers"]["claude-subscription"]["models"]]
        self.assertEqual(ids, ["claude-haiku-5-5", "claude-sonnet-5-5"])
        self.assertIn("left out a model whose id or name holds an identity value (not shown)", self.logged())
        self.assertNotIn("Opus 5.5", self.logged())

    def test_the_management_key_is_never_printed_or_logged(self):
        server = provimux(load(ANSWER))
        self.addCleanup(server.close)
        out = io.StringIO()
        with Connections(server.port).watching(), contextlib.redirect_stdout(out):
            code, words = self.run_with(["--base-url", f"http://127.0.0.1:{server.port}", "--date", TODAY,
                                         "--publish"], key_finder=lambda: KEY)
        self.assertEqual(code, 0, words)
        for text in (out.getvalue(), self.err, words, self.logged(), read(self.out),
                     json.dumps(self.calls()), read(os.path.join(self.home, D.STATE))):
            self.assertNotIn(KEY, text)

    def test_the_state_file_holds_no_identity(self):
        self.from_answer(ANSWER)
        state = read(os.path.join(self.home, D.STATE))
        for value in self.identity_values():
            self.assertNotIn(value, state)


class NothingSentAnywhereElse(Base):
    def test_one_local_request_to_provimux_and_no_other_connection(self):
        server = provimux(load(ANSWER))
        self.addCleanup(server.close)
        conns = Connections(allowed_port=server.port)
        with conns.watching():
            code, words = self.run_with(["--base-url", f"http://127.0.0.1:{server.port}", "--date", TODAY],
                                        key_finder=lambda: KEY)
        self.assertEqual(code, 0, words)
        self.assertEqual(conns.seen, [("127.0.0.1", server.port)])
        self.assertEqual(server.requests, [{"path": "/v8/management/provimux/model-lists?view=live",
                                            "auth": "Bearer " + KEY}])

    def test_a_host_that_is_not_this_mac_is_refused_before_any_connection(self):
        for base in ("https://api.x.ai", "http://192.168.1.10:8317", "http://provimux.example:8317",
                     "file:///etc/hosts"):
            conns = Connections()
            with conns.watching():
                code, _ = self.run_with(["--base-url", base, "--date", TODAY], key_finder=lambda: KEY)
            self.assertEqual(code, 1, base)
            self.assertEqual(conns.seen, [], base)

    def test_a_saved_answer_opens_no_connection_and_sends_no_key(self):
        def no_key():
            raise AssertionError("a saved answer sends no key")
        conns = Connections()
        with conns.watching():
            code, _ = self.from_answer(ANSWER, key_finder=no_key)
        self.assertEqual((code, conns.seen), (0, []))

    def test_an_error_answer_is_reported_by_its_status_only(self):
        server = provimux({"error": "secret-looking text office@providers.dev"}, status=401)
        self.addCleanup(server.close)
        with Connections(server.port).watching():
            code, words = self.run_with(["--base-url", f"http://127.0.0.1:{server.port}", "--date", TODAY],
                                        key_finder=lambda: KEY)
        self.assertEqual(code, 1)
        self.assertIn("HTTP 401", words)
        self.assertNotIn("secret-looking", words + self.logged())

    def test_an_answer_without_view_live_is_refused(self):
        def strip(a):
            for r in a["logins"]:
                r.pop("live_list")
        code, words = self.from_answer(changed(strip))
        self.assertEqual(code, 1)
        self.assertIn("view=live", words)

    def test_the_command_has_no_vendor_address_and_no_git(self):
        source = read(os.path.join(ROOT, "harness", "discover.py"))
        for host in ("anthropic.com", "openai.com", "chatgpt.com", "codeium.com", "githubcopilot", "googleapis",
                     "meta.ai", "x.ai", "kimi.com", "providers.dev/api", "api.github.com"):
            self.assertNotIn(host, source)
        self.assertNotIn('"git"', source)
        self.assertNotIn("discovery-repo", source)

    def test_without_its_folder_it_does_nothing(self):
        os.environ.pop("GROUNDTRUTH_CLIENT_HOME")
        code, words = self.from_answer(ANSWER)
        self.assertEqual(code, 1)
        self.assertIn("GROUNDTRUTH_CLIENT_HOME", words)
        self.assertEqual(self.calls(), [])


class Scan(Base):
    def test_the_real_scan_runs_on_the_bytes_sent_and_passes(self):
        self.github(load(YESTERDAY))
        code, words = self.from_answer(ANSWER, "--publish")
        self.assertEqual(code, 0, words)
        self.assertIn("checks of the exact bytes: 1 files scanned", self.logged())
        self.assertIn("CLEAN", self.logged())
        self.assertEqual([f for f in os.listdir(self.home) if f.startswith(".listed-upload-")], [])


class Agent(unittest.TestCase):
    LABEL = "dev.providers.groundtruth.discovery"
    PLIST = os.path.join(ROOT, "scripts", "launchd", LABEL + ".plist")
    INSTALL = os.path.join(ROOT, "scripts", "install-discovery.sh")

    def test_the_template_runs_the_installed_copy_daily_at_22_30(self):
        with open(self.PLIST, "rb") as f:
            p = plistlib.load(f)
        self.assertEqual(p["Label"], self.LABEL)
        self.assertEqual(p["StartCalendarInterval"], {"Hour": 22, "Minute": 30})
        self.assertEqual(p["ProgramArguments"][1:], ["-B", "__CLIENT_HOME__/bin/discover.py", "__ARG1__"])
        self.assertEqual(p["WorkingDirectory"], "__CLIENT_HOME__")
        self.assertFalse(p["RunAtLoad"])
        self.assertNotIn("CPA_MGMT_KEY", json.dumps(p["EnvironmentVariables"]))

    def test_the_installer_refuses_without_the_owner_s_ok_and_fills_the_template_in(self):
        with tempfile.TemporaryDirectory() as t:
            home = os.path.join(t, "G")
            os.mkdir(home, 0o700)
            target = os.path.join(t, "agents")
            env = dict(os.environ, GROUNDTRUTH_CLIENT_HOME=home)
            r = subprocess.run([self.INSTALL, "--target", target], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("owner's OK", r.stderr)
            self.assertFalse(os.path.exists(target))
            self.assertFalse(os.path.exists(os.path.join(home, "bin")))
            r = subprocess.run([self.INSTALL, "--print"], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(plistlib.loads(r.stdout.encode())["ProgramArguments"][2:],
                             [os.path.join(home, "bin", "discover.py")])
            self.assertFalse(os.path.exists(os.path.join(home, "bin")))
            r = subprocess.run([self.INSTALL, "--owner-ok", "--publish", "--target", target], env=env,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(os.path.join(target, self.LABEL + ".plist"), "rb") as f:
                p = plistlib.load(f)
            self.assertEqual(p["ProgramArguments"][2:], [os.path.join(home, "bin", "discover.py"), "--publish"])
            self.assertEqual(p["WorkingDirectory"], home)
            self.assertEqual(p["EnvironmentVariables"]["GROUNDTRUTH_CLIENT_HOME"], home)
            self.assertEqual(p["StandardOutPath"], os.path.join(home, "discovery.out.log"))
            for name in ("discover.py", "listed_schema.py", "scan_secrets.py"):
                self.assertEqual(read(os.path.join(home, "bin", name)), read(os.path.join(ROOT, "harness", name)))


if __name__ == "__main__":
    unittest.main()
