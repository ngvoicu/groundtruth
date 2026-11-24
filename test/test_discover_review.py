"""The two reviews of discovery (step G1): one class per finding. The first review's cases that still apply, and for
each finding of the second review a `test_second_review_*` showing the case cannot happen with the new approach (no
git; GitHub's contents API through gh; models never removed by discovery; four listings; privacy by allowlist).
Nothing leaves this Mac: fake Provimux servers on free loopback ports and a fake `gh` (test/discover_fakes.py).

    python3 -m unittest discover -s test -p "test_*.py"
"""
import fcntl
import json
import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from discover_fakes import (ANSWER, ROOT, TODAY, YESTERDAY, Base, Connections, D, Server, answer_of, dump, load,
                            provimux, read, row)
import listed_schema as S  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "harness"))
import weekly as W  # noqa: E402
import test_weekly_night as TW  # noqa: E402


def ids(doc, provider):
    return [m["id"] for m in doc["providers"][provider]["models"]]


# --- finding 1: identity ---------------------------------------------------------------------------------------------

class Finding1Identity(Base):
    def test_a_model_whose_name_holds_a_login_s_label_is_dropped_and_the_value_never_logged(self):
        answer = answer_of(row("devin", [{"id": "m-one", "display_name": "One"}], label="Ada"),
                           row("claude", [{"id": "model-team-cedar", "display_name": "Cedar Preview"},
                                          {"id": "claude-plain", "display_name": "Plain"}], label="Cedar"))
        code, words = self.from_answer(answer)
        self.assertEqual(code, 0, words)
        self.assertNotIn("cedar", read(self.out).lower())
        self.assertEqual(ids(self.written(), "claude-subscription"), ["claude-plain"])
        self.assertIn("left out a model whose id or name holds an identity value", self.logged())
        self.assertNotIn("Cedar", self.logged())

    def test_e_mails_file_names_and_auth_index_drop_their_models_without_case(self):
        r = row("codex", [{"id": "gpt-ada-lovelace"}, {"id": "gpt-b", "display_name": "Codex-Team-Acme preview"},
                          {"id": "gpt-c", "display_name": "x 7f21c0d9e8b4a356"}, {"id": "gpt-plain"}],
                email="ada-lovelace" + "@" + "example.org", name="codex-team-acme.json")
        r["auth_index"] = "7F21C0D9E8B4A356"
        code, words = self.from_answer(answer_of(r))
        self.assertEqual(code, 0, words)
        self.assertEqual(ids(self.written(), "openai-codex"), ["gpt-plain"])

    def test_a_label_that_is_a_service_s_name_drops_nothing(self):
        code, words = self.from_answer(answer_of(row("devin", [{"id": "fixture-model", "display_name": "Devin SWE"}],
                                                     label="Devin")))
        self.assertEqual(code, 0, words)
        self.assertEqual(ids(self.written(), "devin"), ["fixture-model"])

    def key_case(self, key, entry):
        server = provimux(answer_of(row("codex", [entry, {"id": "gpt-plain"}])))
        self.addCleanup(server.close)
        code, words = self.run_with(["--base-url", f"http://127.0.0.1:{server.port}", "--date", TODAY])
        self.assertEqual(code, 0, words)
        self.assertEqual(server.requests[0]["auth"], "Bearer " + key)
        self.assertNotIn(key.lower(), read(self.out).lower())
        self.assertNotIn(key, self.logged() + words)
        self.assertEqual(ids(self.written(), "openai-codex"), ["gpt-plain"])

    def test_the_key_from_cpa_mgmt_key_drops_the_model_that_carries_it(self):
        key = "demo-key.unit-only-74"
        os.environ["CPA_MGMT_KEY"] = key
        self.key_case(key, {"id": "demo-model", "display_name": key})

    def test_the_key_from_the_key_file_drops_the_model_that_carries_it(self):
        key = "file-key.unit-only-91"
        os.makedirs(os.path.join(os.environ["HOME"], ".cli-proxy-api"))
        with open(os.path.join(os.environ["HOME"], ".cli-proxy-api", "keys.txt"), "w") as f:
            f.write(f"OTHER=1\nMGMT_KEY={key}\n")
        self.key_case(key, {"id": "model-" + key, "display_name": "A model"})

    def test_second_review_model_ada_from_a_three_letter_label_is_dropped(self):
        # The second review: the site accepted `model-ada` from a login labelled "Ada" (no length exemption now).
        answer = answer_of(row("devin", [{"id": "model-ada"}, {"id": "model-one", "display_name": "Ada"},
                                         {"id": "model-adams"}], label="Ada"))
        code, words = self.from_answer(answer, "--publish")
        self.assertEqual(code, 0, words)
        self.assertEqual(ids(self.github_file(), "devin"), ["model-adams"])  # a whole token only: "adams" stays
        self.assertNotIn(b"ada\"", self.put_bytes()[0].lower())

    def test_second_review_cedar_in_modalities_and_levels_is_dropped(self):
        # The second review: "cedar" (a label) survived in input_modalities and reasoning levels.
        answer = answer_of(row("claude", [{"id": "plain", "input_modalities": ["text", "cedar", "IMAGE"],
                                           "output_modalities": ["cedar"], "reasoning_levels": ["cedar", "high"]}],
                               label="Cedar"))
        code, words = self.from_answer(answer, "--publish")
        self.assertEqual(code, 0, words)
        self.assertEqual(self.github_file()["providers"]["claude-subscription"]["models"],
                         [{"id": "plain", "input_modalities": ["text", "image"], "reasoning": {"levels": ["high"]}}])
        self.assertNotIn(b"cedar", self.put_bytes()[0].lower())

    def test_second_review_an_environment_only_key_never_reaches_the_bytes_sent(self):
        # The second review: with --answer --publish an environment-only key reached the staged file.
        key = "envonly-mgmt-key-5521"
        os.environ["CPA_MGMT_KEY"] = key
        answer = answer_of(row("codex", [{"id": "gpt-plain"}, {"id": "gpt-x", "display_name": f"x {key}"},
                                         {"id": "gpt-" + key}]))
        code, words = self.from_answer(answer, "--publish")
        self.assertEqual(code, 0, words)
        self.assertEqual(ids(self.github_file(), "openai-codex"), ["gpt-plain"])
        self.assertNotIn(key.encode(), b"".join(self.put_bytes()))
        # And if one got past the filter, the check of the exact bytes stops the upload.
        identities = D.Identities(answer, [key])
        with self.assertRaises(D.Failure) as stop:
            D.exact_check(D.text_of({"schema": 1, "repository": S.REPOSITORY, "providers": {"openai-codex": {
                "date": TODAY, "client": "provimux", "models": [{"id": "gpt-plain", "name": f"x {key}"}]}}}).encode(),
                identities, self.home)
        self.assertIn("management key", str(stop.exception))

    def test_second_review_a_published_model_holding_a_new_identity_is_dropped(self):
        # The second review: an earlier part's `team-cedar` stayed after "Cedar" became a login's label.
        published = load(YESTERDAY)
        published["providers"]["devin"]["models"].append({"id": "team-cedar"})
        self.github(published)
        code, words = self.from_answer(answer_of(row("devin", [{"id": "swe-2"}], label="Cedar")), "--publish")
        self.assertEqual(code, 0, words)
        self.assertNotIn("team-cedar", ids(self.github_file(), "devin"))
        self.assertNotIn(b"cedar", self.put_bytes()[0].lower())


# --- finding 2: the key never leaves loopback ------------------------------------------------------------------------

class Finding2Loopback(Base):
    def test_a_redirect_is_refused_and_the_key_goes_nowhere_else(self):
        elsewhere = Server(lambda h: (200, {}, b'{"logins": []}'))
        self.addCleanup(elsewhere.close)
        redirecting = Server(lambda h: (302, {"Location": f"http://127.0.0.1:{elsewhere.port}/stolen"}, b""))
        self.addCleanup(redirecting.close)
        code, words = self.run_with(["--base-url", f"http://127.0.0.1:{redirecting.port}", "--date", TODAY],
                                    key_finder=lambda: "redirect-key-123456")
        self.assertEqual(code, 1)
        self.assertIn("HTTP 302", words)
        self.assertEqual(elsewhere.requests, [])

    def test_no_proxy_is_used_whatever_the_environment_says(self):
        proxy = Server(lambda h: (200, {}, b'{"logins": []}'))
        self.addCleanup(proxy.close)
        target = provimux(load(ANSWER))
        self.addCleanup(target.close)
        os.environ["http_proxy"] = os.environ["HTTP_PROXY"] = f"http://127.0.0.1:{proxy.port}"
        import urllib.request
        urllib.request.install_opener(None)
        self.addCleanup(urllib.request.install_opener, None)
        code, words = self.run_with(["--base-url", f"http://127.0.0.1:{target.port}", "--date", TODAY],
                                    key_finder=lambda: "proxy-key-1234567")
        self.assertEqual(code, 0, words)
        self.assertEqual(proxy.requests, [])
        self.assertEqual(len(target.requests), 1)

    def test_second_review_with_publish_the_only_connection_is_loopback_and_gh_gets_no_key(self):
        key = "loopback-only-key-8812"
        target = provimux(load(ANSWER))
        self.addCleanup(target.close)
        conns = Connections(allowed_port=target.port)
        with conns.watching():
            code, words = self.run_with(["--base-url", f"http://127.0.0.1:{target.port}", "--date", TODAY,
                                         "--publish"], key_finder=lambda: key)
        self.assertEqual(code, 0, words)
        self.assertEqual(conns.seen, [("127.0.0.1", target.port)])
        self.assertNotIn(key, json.dumps(self.calls()))


# --- findings 3, 4 and 5: publishing ---------------------------------------------------------------------------------

class Finding3PublishScope(Base):
    def test_second_review_git_identity_and_push_urls_cannot_reach_the_commit(self):
        # The second review: Git resolved private author.email/committer.email and a different pushurl. No git now:
        # the commit's identity is in the PUT's body, the path is fixed, and nothing reads Git's configuration.
        author, committer = "private-author" + "@" + "example.invalid", "private-committer" + "@" + "example.invalid"
        with open(os.path.join(os.environ["HOME"], ".gitconfig"), "w") as f:
            f.write(f"[user]\n\temail = {author}\n[author]\n\temail = {author}\n[committer]\n\temail = {committer}\n"
                    "[remote \"upstream\"]\n\tpushurl = /elsewhere.git\n")
        os.environ.update(GIT_AUTHOR_EMAIL=author, GIT_COMMITTER_EMAIL=committer, GH_REPO="someone/else")
        self.github(load(YESTERDAY))
        with mock.patch.object(subprocess, "run", wraps=subprocess.run) as spy:
            code, words = self.from_answer(ANSWER, "--publish")
        self.assertEqual(code, 0, words)
        self.assertEqual(self.commits(), [{"message": "discovery: listed.json", "branch": "main",
                                           "author": D.IDENTITY, "committer": D.IDENTITY,
                                           "sha": D.blob_sha(D.text_of(load(YESTERDAY)).encode())}])
        self.assertEqual(D.IDENTITY, {"name": "groundtruth discovery", "email": "office@providers.dev"})
        programs = {os.path.basename(c.args[0][0]) for c in spy.call_args_list}
        self.assertNotIn("git", programs)
        paths = {next(a for a in c["argv"] if a.startswith("repos/")) for c in self.calls()}
        self.assertEqual(paths, {"repos/ngvoicu/groundtruth/contents/listed.json?ref=main",
                                 "repos/ngvoicu/groundtruth/contents/listed.json"})
        self.assertNotIn("example.invalid", json.dumps(self.calls()))

    def test_the_put_replaces_exactly_the_file_it_read(self):
        self.github(load(YESTERDAY))
        sha = D.blob_sha(D.text_of(load(YESTERDAY)).encode())
        self.from_answer(ANSWER, "--publish")
        self.assertEqual(self.puts()[0]["sha"], sha)
        self.assertEqual(self.put_bytes()[0], read(self.out).encode())


class Finding4Recovery(Base):
    def test_second_review_an_interrupted_write_leaves_nothing_the_next_run_depends_on(self):
        # The second review: after an interrupted write the clone's checkout aborted run after run. Now the base is
        # GitHub's file; $G holds only discovery's own output, rewritten whole.
        self.github(load(YESTERDAY))
        with open(self.out, "w") as f:
            f.write('{"schema": 1, "providers": {"devin": ')  # half a file
        with open(os.path.join(self.home, ".discovery-abc123.tmp"), "w") as f:
            f.write("left over\n")
        code, words = self.from_answer(ANSWER, "--publish")
        self.assertEqual(code, 0, words)
        self.assertEqual(self.github_file(), self.written())

    def test_second_review_a_same_day_change_on_github_is_merged_never_overwritten(self):
        # The second review: a retry overwrote GitHub's three models with its own two. Now a 409 re-reads and rebuilds.
        self.github(answer_doc := {"schema": 1, "repository": S.REPOSITORY, "providers": {"devin": {
            "date": TODAY, "client": "provimux", "models": [{"id": "one"}]}}})
        meanwhile = json.loads(json.dumps(answer_doc))
        meanwhile["providers"]["devin"]["models"] = [{"id": "one"}, {"id": "three"}, {"id": "two"}]
        with open(os.path.join(self.fake, "before-put"), "w") as f:
            f.write(D.text_of(meanwhile))
        code, words = self.from_answer(answer_of(row("devin", [{"id": "one"}, {"id": "two"}])), "--publish")
        self.assertEqual(code, 0, words)
        self.assertIn("changed meanwhile (HTTP 409/422): reading it again and rebuilding once", self.logged())
        # Rebuilt from GitHub's three: the union is what GitHub has already, so nothing more is sent.
        self.assertEqual(ids(self.github_file(), "devin"), ["one", "three", "two"])
        self.assertEqual(len(self.puts()), 1)
        self.assertIn("listed.json equals GitHub's: nothing to publish", self.logged())
        self.assertEqual(ids(self.written(), "devin"), ["one", "three", "two"])

    def test_two_conflicts_are_exit_1_and_an_ask(self):
        self.github(load(YESTERDAY))
        with open(os.path.join(self.fake, "put-statuses"), "w") as f:
            f.write("409\n422\n")
        code, words = self.from_answer(ANSWER, "--publish")
        self.assertEqual(code, 1)
        self.assertIn("changed twice", words)
        self.assertIn("ASK: discovery could not publish listed.json", words)
        self.assertEqual(self.github_file(), load(YESTERDAY))
        self.assertEqual(self.commits(), [])


class Finding5Isolation(Base):
    def test_second_review_a_link_in_g_never_writes_into_a_checkout(self):
        # The second review: a discovery-repo symlink to the measuring checkout passed, and clean would have removed
        # an in-flight result. No clone now; a link in $G is replaced, never followed.
        checkout = os.path.join(self.dir, "checkout")
        os.makedirs(os.path.join(checkout, "results"))
        with open(os.path.join(checkout, "listed.json"), "w") as f:
            f.write("the checkout's own\n")
        with open(os.path.join(checkout, "results", "in-flight.jsonl"), "w") as f:
            f.write("{}\n")
        os.symlink(os.path.join(checkout, "listed.json"), self.out)
        os.symlink(checkout, os.path.join(self.home, "discovery-repo"))
        code, words = self.from_answer(ANSWER, "--publish")
        self.assertEqual(code, 0, words)
        self.assertEqual(read(os.path.join(checkout, "listed.json")), "the checkout's own\n")
        self.assertTrue(os.path.exists(os.path.join(checkout, "results", "in-flight.jsonl")))
        self.assertFalse(os.path.islink(self.out))

    def test_second_review_the_agent_runs_its_own_copy_whatever_the_checkout_holds(self):
        # The second review: switching the installing checkout to a commit without discover.py broke the agent.
        target = os.path.join(self.dir, "agents")
        r = subprocess.run([os.path.join(ROOT, "scripts", "install-discovery.sh"), "--owner-ok", "--target", target],
                           env=os.environ, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(target, "dev.providers.groundtruth.discovery.plist"), "rb") as f:
            p = plistlib.load(f)
        self.assertEqual(p["ProgramArguments"][2:], [os.path.join(self.home, "bin", "discover.py")])
        self.assertEqual(p["WorkingDirectory"], self.home)
        # The copy runs on its own, from a folder with no checkout in it.
        run = subprocess.run([sys.executable, "-B", *p["ProgramArguments"][2:], "--answer", ANSWER, "--date", TODAY],
                             cwd=self.dir, env=os.environ, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(sorted(self.written()["providers"]), ["claude-subscription", "devin", "openai-codex"])

    def test_a_second_run_exits_at_once_while_the_first_holds_the_lock(self):
        with open(os.path.join(self.home, "discovery.lock"), "a+") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            code, words = self.from_answer(ANSWER, "--publish")
        self.assertEqual(code, 1)
        self.assertIn("another discovery run", words)
        self.assertEqual(self.calls(), [])

    def test_each_write_uses_a_temporary_file_of_its_own(self):
        seen = []
        real = os.replace

        def replace(src, dst):
            seen.append(src)
            return real(src, dst)
        with mock.patch.object(D.os, "replace", replace):
            D.write(self.out, "alpha\n")
            D.write(self.out, "bravo\n")
        self.assertEqual(len(set(seen)), 2)
        self.assertEqual(read(self.out), "bravo\n")


# --- finding 6: a partial day changes nothing ------------------------------------------------------------------------

class Finding6PartialDay(Base):
    def setUp(self):
        super().setUp()
        self.github(load(YESTERDAY))
        self.from_answer(ANSWER, "--publish")  # remembers the logins; devin published today with four models
        self.devin = self.github_file()["providers"]["devin"]

    def next_day(self, edit):
        answer = load(ANSWER)
        devin = [r for r in answer["logins"] if r["provider"] == "devin"]
        edit(answer, devin)
        for r in answer["logins"]:
            if r["live"].get("fetched_at"):
                r["live"]["fetched_at"] = "2026-11-25T12:00:00Z"
        return self.from_answer(answer, "--publish", date="2026-11-25")

    def kept(self):
        """Devin's published date and ids: the date does not advance, no model goes (a value stated today updates)."""
        part = self.github_file()["providers"]["devin"]
        return part["date"], [m["id"] for m in part["models"]]

    def test_an_enabled_login_without_a_held_list_keeps_the_part_and_its_date(self):
        def lose(answer, devin):
            devin[1].update(live_list=None)
            devin[1]["live"].update(held=False, fetched_at=None, listed_models=None)
        self.next_day(lose)
        self.assertEqual(self.kept(), (TODAY, [m["id"] for m in self.devin["models"]]))
        self.assertIn("devin: 1 enabled login(s): no held list: not a complete day", self.logged())

    def test_second_review_a_login_absent_from_the_answer_is_an_incomplete_day(self):
        # The second review: the row absent entirely advanced the date and wrote three models of four.
        code, words = self.next_day(lambda answer, devin: answer["logins"].remove(devin[1]))
        self.assertEqual(code, 0, words)
        part = self.github_file()["providers"]["devin"]
        self.assertEqual(part["date"], TODAY)
        self.assertEqual([m["id"] for m in part["models"]], [m["id"] for m in self.devin["models"]])
        self.assertIn("devin: 1 login(s) seen before, absent from Provimux's answer", self.logged())
        # Removed on purpose: the owner says so once, and the day is complete again.
        answer = load(ANSWER)
        answer["logins"] = [r for r in answer["logins"] if r["auth_index"] != "b39e04c6f1d7a218"]
        self.from_answer(answer, "--publish", "--forget-absent", date="2026-11-25")
        self.assertEqual(self.github_file()["providers"]["devin"]["date"], TODAY)  # lists still read 11-24
        self.assertEqual(len(self.github_file()["providers"]["devin"]["models"]), 4)  # never removed

    def test_second_review_a_held_list_shorter_than_its_count_is_an_incomplete_day(self):
        # The second review: a held row advertising four models and holding three passed.
        def short(answer, devin):
            devin[0]["live"]["listed_models"] = 4
        code, words = self.next_day(short)
        self.assertEqual(code, 0, words)
        self.assertEqual(self.kept(), (TODAY, [m["id"] for m in self.devin["models"]]))
        self.assertIn("a list with fewer or more models than it says it listed", self.logged())


# --- finding 7: refuse what the site refuses -------------------------------------------------------------------------

class Finding7SiteLimits(Base):
    def test_a_number_beyond_the_safe_integers_is_not_written(self):
        code, words = self.from_answer(answer_of(row("devin", [{"id": "fixture-model", "context": 2 ** 53}])))
        self.assertEqual(code, 0, words)
        self.assertNotIn("context_window", self.written()["providers"]["devin"]["models"][0])
        doc = load(YESTERDAY)
        doc["providers"]["devin"]["models"][0]["context_window"] = 2 ** 53
        self.assertTrue(any("2^53" in e for e in S.validate(doc)))

    def test_a_file_over_the_site_s_size_limit_is_not_written(self):
        self.github(load(YESTERDAY))
        with mock.patch.object(S, "MAX_BYTES", 2000):
            code, words = self.from_answer(ANSWER, "--publish")
        self.assertEqual(code, 1)
        self.assertIn("more than 8 MiB", words)
        self.assertEqual(self.puts(), [])

    def test_the_schema_command_refuses_an_oversized_file_and_an_empty_one(self):
        doc = load(YESTERDAY)
        doc["providers"]["devin"]["models"] = [{"id": f"m-{i}", "name": "A model name " * 4} for i in range(200000)]
        path = os.path.join(self.dir, "big.json")
        dump(doc, path)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "harness", "listed_schema.py"), path],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("more than 8 MiB", r.stdout)
        self.assertNotEqual(S.validate({"schema": 1, "providers": {}}), [])

    def test_second_review_shrinking_lists_never_shrink_the_published_file(self):
        # The second review: 10, then 6, then 4 models were each accepted against the day before, and the site
        # refused 4 against its last good 10. Now the published file only grows: the site's last good is a subset.
        counts = []
        for day, n in (("2026-11-24", 10), ("2026-11-25", 6), ("2026-11-26", 4)):
            r = row("devin", [{"id": f"model-{i}"} for i in range(n)])
            r["live"]["fetched_at"] = f"{day}T12:00:00Z"
            code, words = self.from_answer(answer_of(r), "--publish", date=day)
            self.assertEqual(code, 0, words)
            counts.append((len(ids(self.github_file(), "devin")), self.github_file()["providers"]["devin"]["date"]))
        self.assertEqual(counts, [(10, "2026-11-24"), (10, "2026-11-25"), (10, "2026-11-26")])

    def test_the_shrink_guard_compares_with_github_s_file(self):
        big = load(YESTERDAY)
        big["providers"]["antigravity"]["models"] = [{"id": f"m-{n}"} for n in range(40)]
        self.github(big)
        code, words = self.from_answer(ANSWER, "--publish")
        self.assertEqual(code, 1)
        self.assertIn("lost more than 40 %", words)
        self.assertEqual(self.puts(), [])


# --- finding 8: what discovery lists ---------------------------------------------------------------------------------

class Finding8Provenance(Base):
    def test_copilot_s_and_antigravity_s_lists_are_not_written(self):
        answer = answer_of(row("copilot", [{"id": "gpt-4.1"}, {"id": "disabled-model"}]),
                           row("antigravity", [{"id": "gemini-3.8-flash"}]), row("claude", [{"id": "claude-plain"}]))
        code, words = self.from_answer(answer)
        self.assertEqual(code, 0, words)
        self.assertEqual(sorted(self.written()["providers"]), ["claude-subscription"])

    def test_second_review_an_old_file_s_copilot_and_antigravity_rows_are_dropped_others_carried(self):
        # The second review: a populated schema-1 file carried Copilot's disabled model forward, and Antigravity's
        # shared window was published. GitHub has no listed.json today (checked: HTTP 404), so neither is there.
        old = load(YESTERDAY)
        old["providers"]["copilot"] = {"date": "2026-11-21", "client": "provimux", "models": [{"id": "disabled-model"}]}
        old["providers"]["kimi-subscription"] = {"date": "2026-11-20", "client": "provimux",
                                                 "models": [{"id": "kimi-k3", "plans": ["pro"]}]}
        self.github(old)
        code, words = self.from_answer(ANSWER, "--publish")
        self.assertEqual(code, 0, words)
        published = self.github_file()["providers"]
        self.assertNotIn("copilot", published)
        self.assertNotIn("antigravity", published)
        self.assertEqual(published["kimi-subscription"], old["providers"]["kimi-subscription"])
        self.assertEqual(sorted(D.LISTINGS.values()),
                         ["claude-subscription", "devin", "meta-subscription", "openai-codex"])

    def test_the_reasons_and_the_provimux_lines_are_in_the_doc(self):
        doc = read(os.path.join(ROOT, "docs", "discovery.md"))
        self.assertIn("sdk/cliproxy/provimux_live_copilot.go", doc)
        self.assertIn("sdk/auth/provimux_antigravity_models.go", doc)


# --- finding 9: the Monday handoff and stale data --------------------------------------------------------------------

class Finding9Handoff(Base):
    def test_second_review_a_rejected_publication_asks_with_the_published_ages(self):
        # The second review: a refused scan computed ages from the unpublished candidate and gave no ask.
        old = load(YESTERDAY)
        old["providers"]["devin"]["date"] = "2026-11-19"
        self.github(old)
        code, words = self.from_answer(ANSWER, "--publish",
                                       scan=[sys.executable, "-c", "import sys; print('x: an e-mail'); sys.exit(1)"])
        self.assertEqual(code, 1)
        self.assertIn("ASK: discovery could not publish listed.json (harness/scan_secrets.py found something", words)
        self.assertIn("ASK: discovery has no fresh list for devin: 5 days old on GitHub", words)
        self.assertIn("ASK:", self.logged())
        self.assertEqual(self.puts(), [])
        self.assertEqual(len(self.notifications()), 1)
        self.assertEqual(self.written()["providers"]["devin"]["date"], TODAY)  # $G has the read; GitHub the age

    def test_second_review_the_weekly_night_runs_discovery_first_and_plans_from_g(self):
        # The second review: main's weekly planner read its own checkout's listed.json.
        root = os.path.join(self.dir, "repo")
        os.makedirs(root)
        with open(os.path.join(root, "listed.json"), "w") as f:
            json.dump({"providers": {"devin": {"date": "2026-11-01", "models": ["old"]}}}, f)

        class WithDiscovery(TW.Fake):
            def discover(self):
                self.calls.append(("discover",))
                with open(os.path.join(home, "listed.json"), "w") as f:
                    json.dump({"providers": {"devin": {"date": "2026-11-30", "models": ["m-0"]}}}, f)
        home = self.home
        fake = WithDiscovery(TW.bucharest(0, 23), TW.fixture_site(codex=1, devin=1))
        W.Night(TW.DATE, fake, home, out=lambda line: None, root=root).run()
        self.assertEqual(fake.calls[0:2], [("keep_awake",), ("discover",)])
        self.assertLess(fake.calls.index(("discover",)), fake.calls.index(("site",)))
        import asks as A
        self.assertEqual(A.Asks(os.path.join(home, "asks")).open_of("discovery-stale"), [])  # $G's, not the checkout's

    def test_the_world_runs_the_installed_copy_without_publish(self):
        os.makedirs(os.path.join(self.home, "bin"))
        with open(os.path.join(self.home, "bin", "discover.py"), "w") as f:
            f.write("import os, sys\nopen(os.path.join(os.environ['GROUNDTRUTH_CLIENT_HOME'], 'argv'), 'w')"
                    ".write(' '.join(sys.argv[1:]) + '|' + os.getcwd())\n")
        self.assertIsNone(W.World(self.home, ROOT).discover())
        self.assertEqual(read(os.path.join(self.home, "argv")), "|" + os.path.realpath(self.home))

    def test_a_dry_night_only_says_it_would_run_discovery(self):
        lines = []
        fake = TW.Fake(TW.bucharest(0, 23), TW.fixture_site())
        fake.discover = lambda: self.fail("a dry run runs nothing")
        W.Night(TW.DATE, fake, self.home, dry=True, out=lines.append, root=os.path.join(self.dir)).run()
        self.assertTrue(any("would run discovery first" in line for line in lines))


# --- finding 10: the installer ---------------------------------------------------------------------------------------

class Finding10Installer(unittest.TestCase):
    LABEL = "dev.providers.groundtruth.discovery"
    INSTALL = os.path.join(ROOT, "scripts", "install-discovery.sh")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = os.path.join(self.tmp.name, "G")
        os.mkdir(self.home, 0o700)
        self.target = os.path.join(self.tmp.name, "agents")
        os.mkdir(self.target)
        self.plist = os.path.join(self.target, self.LABEL + ".plist")
        with open(self.plist, "w") as f:
            f.write("an installed agent\n")
        self.env = dict(os.environ, GROUNDTRUTH_CLIENT_HOME=self.home)

    def install(self, *args):
        return subprocess.run([self.INSTALL, "--target", self.target, *args], env=self.env, capture_output=True,
                              text=True)

    def test_second_review_print_changes_nothing_whatever_else_is_given(self):
        for args in (("--print", "--uninstall"), ("--print", "--uninstall", "--owner-ok"),
                     ("--print", "--owner-ok", "--publish")):
            r = self.install(*args)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(read(self.plist), "an installed agent\n", args)
            self.assertFalse(os.path.exists(os.path.join(self.home, "bin")), args)

    def test_uninstall_needs_the_owner_s_ok(self):
        r = self.install("--uninstall")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(os.path.exists(self.plist))
        r = self.install("--uninstall", "--owner-ok")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(self.plist))

    def test_without_publish_the_agent_passes_no_option(self):
        r = self.install("--owner-ok")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.plist, "rb") as f:
            p = plistlib.load(f)
        self.assertEqual(p["ProgramArguments"][2:], [os.path.join(self.home, "bin", "discover.py")])


if __name__ == "__main__":
    unittest.main()
