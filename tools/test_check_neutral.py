"""Tests for tools/check_neutral.py: where it finds the site term list, and its generic rules (standard library only)."""
import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

import check_neutral


class TestSiteTermList(unittest.TestCase):
    """The list lives outside the repository; the tool says where, and names a list left under the former name."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        self.env = mock.patch.dict(os.environ, {"HOME": self.home, "USERPROFILE": self.home}, clear=False)
        self.env.start()
        os.environ.pop("MARKETPLACE_GUARD_SITE_TERMS", None)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def write(self, *parts, text="example-host\n"):
        path = os.path.join(self.home, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def refusal(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as ctx:
            check_neutral.load_terms()
        return ctx.exception.code, err.getvalue()

    def test_the_list_under_the_current_name_is_read(self):
        self.write(".config", "marketplace-guard", "site-terms.txt")
        terms, why = check_neutral.load_terms()
        self.assertIsNone(why)
        self.assertEqual(len(terms), 1)

    def test_no_list_refuses_with_the_next_step(self):
        code, msg = self.refusal()
        self.assertEqual(code, 2)
        self.assertIn("marketplace-guard", msg)
        self.assertIn("Next step", msg)

    def test_a_list_under_the_former_name_is_named_not_read(self):
        self.write(".config", "hacs-guard", "site-terms.txt")
        code, msg = self.refusal()
        self.assertEqual(code, 2)
        self.assertIn("former name", msg)
        self.assertIn("hacs-guard", msg.replace("\\", "/"))
        self.assertIn("mv ", msg)

    def test_an_explicit_path_is_not_redirected_to_the_former_list(self):
        self.write(".config", "hacs-guard", "site-terms.txt")
        os.environ["MARKETPLACE_GUARD_SITE_TERMS"] = os.path.join(self.home, "missing.txt")
        code, msg = self.refusal()
        self.assertEqual(code, 2)
        self.assertNotIn("former name", msg)

    def test_generic_rules_only_with_a_reason(self):
        os.environ["MARKETPLACE_GUARD_SITE_TERMS"] = "none: a fresh checkout"
        self.assertEqual(check_neutral.load_terms(), (None, "a fresh checkout"))


class TestRegionalSpelling(unittest.TestCase):
    """German written with ss for ß is a place hint; standard German and English words pass. The words are put
    together here, so that this file does not trip the check itself."""

    SS = "s" + "s"

    def hits(self, line):
        return [h for h in check_neutral.generic(line) if h.startswith("regional spelling")]

    def test_regional_forms_are_found(self):
        for word in ("au" + self.SS + "er", "Au" + self.SS + "erhalb", "grö" + self.SS + "ere", "gemä" + self.SS,
                     "regelmä" + self.SS + "ig", "schlie" + self.SS + "lich", "Stra" + self.SS + "e", "hei" + self.SS + "t"):
            with self.subTest(word=word):
                self.assertEqual(len(self.hits(f"Ein Satz mit {word} darin.")), 1)

    def test_standard_german_and_english_pass(self):
        for line in ("außer, größere, gemäß, regelmäßig, schließlich, Straße, heißt",
                     "dass, muss, müssen, Schloss, Klasse, Prozess, Adresse, besser",
                     "a gross error, a fuss, the mass, reissue, classes, assessment, grosses"):
            with self.subTest(line=line):
                self.assertEqual(self.hits(line), [])


if __name__ == "__main__":
    unittest.main()
