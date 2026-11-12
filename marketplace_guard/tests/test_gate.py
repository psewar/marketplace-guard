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


class TestCopyWatch(unittest.TestCase):
    """The gate notices when the app replaced its folder and has Home Assistant's restart flag set (ADR-0044)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = self.tmp.name
        self.flagged = []  # (hass, domain), as Home Assistant's async_set_home_assistant_restart_required gets them

    def tearDown(self):
        self.tmp.cleanup()

    def put_manifest(self, version):
        with open(os.path.join(self.folder, gatecore.MANIFEST), "w", encoding="utf-8") as f:
            json.dump({"domain": "marketplace_guard_gate", "version": version}, f)

    def watch(self, running):
        def set_restart_required(hass, domain):
            self.flagged.append((hass, domain))
        # wired as in __init__.py: mark_restart calls Home Assistant's flag with the gate's domain
        return gatecore.CopyWatch(self.folder, running,
                                  lambda on_disk: set_restart_required("hass", "marketplace_guard_gate"))

    def test_a_newer_copy_on_disk_sets_the_restart_flag_once(self):
        self.put_manifest("2.4.2")
        watch = self.watch(gatecore.manifest_version(self.folder))  # what the gate read while Python imported it
        self.assertEqual(watch.judge(watch.read()), "current")
        self.put_manifest("2.5.0")  # the app replaced the copy
        self.assertEqual(watch.judge(watch.read()), "replaced")
        self.assertEqual(self.flagged, [("hass", "marketplace_guard_gate")])
        self.put_manifest("2.5.1")
        self.assertEqual(watch.judge(watch.read()), "replaced")  # latched until the restart, as the flag is
        self.assertEqual(len(self.flagged), 1)

    def test_the_same_version_on_disk_does_not_set_the_flag(self):
        self.put_manifest("2.5.0")
        watch = self.watch("2.5.0")
        for _ in range(3):
            self.assertEqual(watch.judge(watch.read()), "current")
        self.assertEqual(self.flagged, [])

    def test_an_older_copy_after_a_rollback_also_needs_the_restart(self):
        self.put_manifest("2.4.2")
        watch = self.watch("2.5.0")
        self.assertEqual(watch.judge(watch.read()), "replaced")
        self.assertEqual(len(self.flagged), 1)

    def test_an_unreadable_version_concludes_nothing(self):
        watch = self.watch("2.5.0")
        self.assertEqual(watch.judge(watch.read()), "unknown")  # no manifest: the app is between removing and renaming
        for text in ("not json", "[]", '{"version": 3}', '{"version": ""}', "{}"):
            with self.subTest(manifest=text):
                with open(os.path.join(self.folder, gatecore.MANIFEST), "w", encoding="utf-8") as f:
                    f.write(text)
                self.assertIsNone(gatecore.manifest_version(self.folder))
                self.assertEqual(watch.judge(watch.read()), "unknown")
        self.put_manifest("2.5.0")
        self.assertEqual(self.watch(None).judge("2.5.0"), "unknown")  # its own version was not read at import
        self.assertEqual(watch.judge(watch.read()), "current")  # and it keeps watching
        self.assertEqual(self.flagged, [])

    def test_the_shipped_gate_can_read_its_own_version(self):
        self.assertRegex(gatecore.manifest_version(os.path.dirname(os.path.abspath(gatecore.__file__))) or "",
                         r"^\d+\.\d+\.\d+$")


class TestFindFunction(unittest.TestCase):
    """Home Assistant's restart flag is looked up before it is used; a version without it gets None, not an error."""

    def test_an_existing_function_is_found(self):
        self.assertIs(gatecore.find_function("json", "loads"), json.loads)
        self.assertIs(gatecore.find_function("os.path", "join"), os.path.join)

    def test_a_missing_module_or_function_gives_none(self):
        self.assertIsNone(gatecore.find_function("json", "no_such_function"))
        self.assertIsNone(gatecore.find_function("json", "__name__"))  # there, but not a function
        self.assertIsNone(gatecore.find_function("json.no_such_module", "x"))
        self.assertIsNone(gatecore.find_function("no_such_package_for_the_gate.helpers.system_state", "x"))


if __name__ == "__main__":
    unittest.main()
