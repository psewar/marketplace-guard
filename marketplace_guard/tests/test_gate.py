"""Tests for the gate's own logic (gate/marketplace_guard_gate/gatecore.py), standard library only (ADR-0042)."""
import asyncio
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gate", "marketplace_guard_gate"))
import gatecore  # noqa: E402


class Base:
    async def async_check_written_content(self):
        self.calls.append("base")


class Integration(Base):
    async def async_check_written_content(self):  # overrides without super(), as the Marketplace's classes do
        self.calls.append("integration")


class Template(Base):
    pass


def make_wrapper(original):
    async def checked(self):
        await original(self)
        self.calls.append("gate")
    return checked


class TestWrapping(unittest.TestCase):
    def tearDown(self):
        for cls, name in ((Base, "base"), (Integration, "integration")):
            fn = cls.__dict__["async_check_written_content"]
            if getattr(fn, gatecore.MARK, False):
                self.fail(f"{name} left wrapped")

    def run_check(self, cls):
        obj = cls()
        obj.calls = []
        asyncio.run(obj.async_check_written_content())
        return obj.calls

    def test_every_class_with_its_own_check_is_wrapped_and_unwrapped(self):
        done = gatecore.wrap_check_methods(Base, make_wrapper)
        try:
            self.assertEqual({c.__name__ for c, _ in done}, {"Base", "Integration"})
            self.assertEqual(self.run_check(Integration), ["integration", "gate"])
            self.assertEqual(self.run_check(Template), ["base", "gate"])  # inherits the wrapped one
            self.assertEqual(gatecore.wrap_check_methods(Base, make_wrapper), [])  # never wrapped twice
        finally:
            gatecore.unwrap(done)
        self.assertEqual(self.run_check(Integration), ["integration"])

    def test_another_version_without_the_method_is_left_alone(self):
        class Other:
            def async_check_written_content(self):  # not a coroutine: not the method the gate knows
                pass
        self.assertIsNone(gatecore.wrap_check_methods(Other, make_wrapper))
        self.assertIsNone(gatecore.wrap_check_methods(None, make_wrapper))
        self.assertFalse(getattr(Other.__dict__["async_check_written_content"], gatecore.MARK, False))


class TestExchange(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_request_names_the_content_relative_to_the_configuration_folder(self):
        state, rid, payload = gatecore.build_request(self.config, os.path.join(self.config, "custom_components", "x"),
                                                     "owner/repo", "integration", False)
        self.assertEqual(state, "ok")
        self.assertEqual((payload["path"], payload["repository"], payload["update"]),
                         ("custom_components/x", "owner/repo", False))
        self.assertRegex(rid, r"^[0-9a-f]{16}$")
        for outside in (os.path.join(self.config, ".."), self.config):
            with self.subTest(outside=outside):
                self.assertEqual(gatecore.build_request(self.config, outside, "o/r", "integration", False)[0],
                                 "refused")

    def test_request_and_answer_go_through_files(self):
        state, rid, payload = gatecore.build_request(self.config, os.path.join(self.config, "custom_components", "x"),
                                                     "owner/repo", "integration", True)
        gatecore.write_request(self.config, rid, payload)
        with open(os.path.join(self.config, gatecore.GATE_DIR, "requests", f"{rid}.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), payload)
        self.assertIsNone(gatecore.read_answer(self.config, rid))
        answers = os.path.join(self.config, gatecore.GATE_DIR, "verdicts")
        os.makedirs(answers)
        with open(os.path.join(answers, f"{rid}.json"), "w", encoding="utf-8") as f:
            json.dump({"decision": "allow"}, f)
        self.assertEqual(gatecore.read_answer(self.config, rid), {"decision": "allow"})
        self.assertFalse(os.listdir(answers))  # taken away when read
        with open(os.path.join(answers, f"{rid}.json"), "w", encoding="utf-8") as f:
            f.write("not json")
        self.assertEqual(gatecore.read_answer(self.config, rid)["decision"], "refuse")
        gatecore.withdraw_request(self.config, rid)
        self.assertFalse(os.listdir(os.path.join(self.config, gatecore.GATE_DIR, "requests")))

    def test_the_outcome_follows_the_answer_and_the_setting(self):
        self.assertEqual(gatecore.outcome(None, "refuse")[0], "refuse")
        self.assertEqual(gatecore.outcome(None, "allow")[0], "allow")
        self.assertEqual(gatecore.outcome({"decision": "allow"}, "refuse")[0], "allow")
        decision, message = gatecore.outcome({"decision": "refuse", "verdict": "high", "summary": "s"}, "allow")
        self.assertEqual(decision, "refuse")
        self.assertIn("(HIGH): s", message)


if __name__ == "__main__":
    unittest.main()
