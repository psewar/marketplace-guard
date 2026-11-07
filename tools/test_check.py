"""Tests for tools/check.py (standard library only; run by `python3 tools/check.py --all`)."""
import os
import tempfile
import unittest

import check


def adr(status="accepted", date="2026-01-01", title="A decision", makers="maintainer"):
    return f"---\nstatus: {status}\ndate: {date}\ndecision-makers: {makers}\n---\n\n# {title}\n\nText.\n"


def index(*rows):
    head = "# ADRs\n\n| No. | Title | Status | Date |\n|-----|-------|--------|------|\n"
    return head + "".join(f"| [{n}]({f}) | {t} | {s} | {d} |\n" for n, f, t, s, d in rows)


class TestAdrIndex(unittest.TestCase):
    def setUp(self):
        self.adrs = {"0001-first.md": adr(title="First"), "0002-second.md": adr("proposed", title="Second")}
        self.rows = [("0001", "0001-first.md", "First", "accepted", "2026-01-01"),
                     ("0002", "0002-second.md", "Second", "proposed", "2026-01-01")]

    def test_consistent_index_passes(self):
        self.assertEqual(check.adr_index_problems(self.adrs, index(*self.rows)), [])

    def test_status_differs(self):
        self.rows[1] = ("0002", "0002-second.md", "Second", "accepted", "2026-01-01")
        problems = check.adr_index_problems(self.adrs, index(*self.rows))
        self.assertEqual(len(problems), 1)
        self.assertIn("status 'accepted' differs", problems[0])

    def test_file_not_listed(self):
        problems = check.adr_index_problems(self.adrs, index(self.rows[0]))
        self.assertEqual(problems, ["docs/adr/README.md: 0002-second.md is not in the index"])

    def test_listed_file_missing(self):
        rows = self.rows + [("0003", "0003-third.md", "Third", "accepted", "2026-01-01")]
        problems = check.adr_index_problems(self.adrs, index(*rows))
        self.assertTrue(any("0003-third.md does not exist" in p for p in problems), problems)

    def test_gap_in_numbers(self):
        self.adrs["0004-fourth.md"] = adr(title="Fourth")
        rows = self.rows + [("0004", "0004-fourth.md", "Fourth", "accepted", "2026-01-01")]
        problems = check.adr_index_problems(self.adrs, index(*rows))
        self.assertEqual(problems, ["docs/adr: numbers missing (no gaps allowed): 0003"])

    def test_unknown_status_and_dangling_supersede(self):
        self.adrs["0001-first.md"] = adr("superseded by ADR-0009", title="First")
        self.adrs["0002-second.md"] = adr("maybe", title="Second")
        self.rows = [("0001", "0001-first.md", "First", "superseded by ADR-0009", "2026-01-01"),
                     ("0002", "0002-second.md", "Second", "maybe", "2026-01-01")]
        problems = check.adr_index_problems(self.adrs, index(*self.rows))
        self.assertTrue(any("ADR-0009, which does not exist" in p for p in problems), problems)
        self.assertTrue(any("status 'maybe' is not" in p for p in problems), problems)

    def test_badly_named_file_and_missing_front_matter(self):
        self.adrs["notes.md"] = "# Notes\n"
        self.adrs["0002-second.md"] = "# Second\n"
        problems = check.adr_index_problems(self.adrs, index(*self.rows))
        self.assertIn("docs/adr/notes.md: not named NNNN-title-in-kebab-case.md", problems)
        self.assertIn("docs/adr/0002-second.md: front matter has no status", problems)


class TestLinks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        os.makedirs(os.path.join(self.root, "docs", "adr"))
        self.write("docs/adr/README.md", "# ADRs\n")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        with open(os.path.join(self.root, *rel.split("/")), "w", encoding="utf-8") as f:
            f.write(text)

    def test_resolving_links_and_ignored_forms_pass(self):
        self.write("README.md", "[adr](docs/adr/README.md#index) [web](https://example.org/x) [here](#top)\n"
                                "```\n[not a link](missing.md)\n```\n`[code](missing.md)`\n[ref]: docs/adr/\n")
        self.assertEqual(check.link_problems(self.root, ["README.md"]), ([], 2))

    def test_broken_and_escaping_links_are_problems(self):
        self.write("README.md", "intro\n[gone](docs/adr/0001-gone.md)\n[out](../outside.md)\n")
        problems, _ = check.link_problems(self.root, ["README.md"])
        self.assertEqual(problems, ["README.md:2: link docs/adr/0001-gone.md does not resolve",
                                    "README.md:3: link ../outside.md points outside the repository"])

    def test_link_relative_to_the_file(self):
        self.write("docs/adr/0001-a.md", "[index](README.md) [up](../../README.md)\n")
        problems, _ = check.link_problems(self.root, ["docs/adr/0001-a.md"])
        self.assertEqual(problems, ["docs/adr/0001-a.md:1: link ../../README.md does not resolve"])

    def test_agents_paths(self):
        self.write("AGENTS.md", "`docs/adr/README.md` `docs/adr/NNNN-title.md` `tools/missing.py` `~/.config/x`\n")
        problems, checked = check.agents_path_problems(self.root)
        self.assertEqual((problems, checked), (["AGENTS.md:1: path tools/missing.py does not exist"], 2))


class TestAddonConfig(unittest.TestCase):
    def setUp(self):
        self.config = {"options": {"a": True, "b": [1]}, "schema": {"a": "bool", "b": ["int"], "c": "str?"}}
        text = {"name": "N", "description": "D"}
        self.translations = {"en": {"configuration": {"a": text, "b": text, "c": text}},
                             "de": {"configuration": {"a": text, "b": text, "c": text}}}
        self.defaults = {"a": True, "b": [1], "c": "", "internal": 5}

    def problems(self):
        return check.addon_config_problems(self.config, self.translations, self.defaults)

    def test_consistent_configuration_passes(self):
        self.assertEqual(self.problems(), [])

    def test_option_without_schema(self):
        self.config["options"]["d"] = 1
        self.assertEqual(self.problems(), ["config.yaml: option d has no schema entry"])

    def test_missing_and_unknown_translation(self):
        del self.translations["de"]["configuration"]["c"]
        self.translations["en"]["configuration"]["old"] = {"name": "N", "description": "D"}
        self.assertEqual(self.problems(), ["translations/de.yaml: option c has no name",
                                           "translations/de.yaml: option c has no description",
                                           "translations/en.yaml: text for unknown option old"])

    def test_required_language_missing(self):
        del self.translations["de"]
        self.assertEqual(self.problems(), ["translations/de.yaml missing"])

    def test_defaults_missing_or_different(self):
        del self.defaults["c"]
        self.defaults["a"] = 1  # equal to True in Python, but not the same default
        self.assertEqual(self.problems(), ["default of a differs: config.yaml True, guard.py 1",
                                           "guard.py: DEFAULTS lacks schema option c"])

    def test_guard_defaults_read_without_import(self):
        source = "import os\nX = 1\nDEFAULTS = {\"a\": True, \"b\": [1]}\nos.exit(1)\n"
        self.assertEqual(check.guard_defaults(source), {"a": True, "b": [1]})
        self.assertIsNone(check.guard_defaults("DEFAULTS = dict(a=1)\n"))


class TestOverallExit(unittest.TestCase):
    def result(self, state):
        return check.Result("x", state, "", [])

    def test_codes(self):
        self.assertEqual(check.overall_exit([self.result("ok")]), 0)
        self.assertEqual(check.overall_exit([self.result("ok"), self.result("not-run")]), 2)
        self.assertEqual(check.overall_exit([self.result("not-run"), self.result("fail")]), 1)


if __name__ == "__main__":
    unittest.main()
