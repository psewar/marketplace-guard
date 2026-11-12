"""The logic of the Marketplace Guard gate (ADR-0042), without Home Assistant imports, so that it is tested with the
standard library. __init__.py wires it into Home Assistant's Marketplace.

The Marketplace writes a repository's content, runs the check of its repository class
(`async_check_written_content`), and only then loads anything: when the check raises, it puts back what was there.
The gate wraps that check: after the Marketplace's own, it asks the Marketplace Guard app for a verdict through two
folders in Home Assistant's configuration folder and refuses what the app would quarantine.

The app replaces the gate's own folder when it brings a new version; Home Assistant runs the new code only after a
restart. CopyWatch notices that, so that Home Assistant's restart flag gets set (ADR-0044).
"""
import importlib
import importlib.util
import inspect
import json
import os
import secrets
import time

GATE_DIR = os.path.join("marketplace_guard", "gate")  # in Home Assistant's configuration folder
CATEGORIES = ("integration", "plugin")  # what Marketplace Guard scans: code that runs
METHOD = "async_check_written_content"
MAX_ANSWER = 64 * 1024
MARK = "_marketplace_guard_gate"
MANIFEST = "manifest.json"
MAX_MANIFEST = 16 * 1024
COPY_CHECK_SECONDS = 60
# Home Assistant's latched "restart required" flag (since 2026.11.0, the first version with the Marketplace)
RESTART_FLAG = ("homeassistant.helpers.system_state", "async_set_home_assistant_restart_required")


def wrap_check_methods(root, make_wrapper):
    """Wrap METHOD of root and of every subclass that defines its own (the Marketplace's repository classes override it
    without calling super()). Returns [(class, original)] to undo it, or None when root has no such coroutine method:
    another Home Assistant version, and nothing is changed."""
    if root is None or not inspect.iscoroutinefunction(getattr(root, METHOD, None)):
        return None
    classes, todo = [], [root]
    while todo:
        cls = todo.pop()
        if cls not in classes:
            classes.append(cls)
            todo.extend(cls.__subclasses__())
    done = []
    for cls in classes:
        original = cls.__dict__.get(METHOD)
        if original is None or getattr(original, MARK, False):
            continue
        wrapped = make_wrapper(original)
        setattr(wrapped, MARK, True)
        setattr(cls, METHOD, wrapped)
        done.append((cls, original))
    return done


def unwrap(done):
    for cls, original in done:
        setattr(cls, METHOD, original)


def build_request(config_dir, local_path, repository, category, update):
    """The request for one written content: ("ok", id, payload), or ("refused", None, reason) when the content is not
    inside the configuration folder (the app could not find it)."""
    rel = os.path.relpath(os.path.realpath(local_path), os.path.realpath(config_dir))
    if rel == os.curdir or rel.startswith(os.pardir) or os.path.isabs(rel):
        return "refused", None, f"{local_path} is not inside the configuration folder"
    rid = secrets.token_hex(8)
    return "ok", rid, {"id": rid, "path": rel.replace(os.sep, "/"), "repository": str(repository),
                       "category": str(category), "update": bool(update), "ts": round(time.time())}


def _folder(config_dir, kind):
    return os.path.join(config_dir, GATE_DIR, kind)


def write_request(config_dir, rid, payload):
    """Put the request where the app watches (written under a temporary name, then renamed: the app never reads half
    of it)."""
    d = _folder(config_dir, "requests")
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, f".{rid}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    os.replace(tmp, os.path.join(d, f"{rid}.json"))


def read_answer(config_dir, rid):
    """The app's answer to a request, taken away when read: a dict, or None while there is none yet."""
    path = os.path.join(_folder(config_dir, "verdicts"), f"{rid}.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        text = f.read(MAX_ANSWER)
    os.remove(path)
    try:  # written by the app, still parsed as untrusted text: only parsing tells whether it is valid
        answer = json.loads(text)
    except ValueError:
        answer = None
    return answer if isinstance(answer, dict) else {"decision": "refuse",
                                                   "summary": "the answer of Marketplace Guard could not be read"}


def withdraw_request(config_dir, rid):
    """After waiting in vain: take the request back, so the app does not answer a question nobody waits for."""
    path = os.path.join(_folder(config_dir, "requests"), f"{rid}.json")
    if os.path.isfile(path):
        os.remove(path)


def outcome(answer, on_no_answer):
    """What the gate does, as a fact: ("allow" | "refuse", message for the log and the install dialog)."""
    if answer is None:
        if on_no_answer == "allow":
            return "allow", "Marketplace Guard did not answer in time; allowed, as the gate's options say"
        return "refuse", ("Marketplace Guard did not answer in time (is the app running?), so nothing was installed. "
                          "Install it again once the app runs")
    if answer.get("decision") == "allow":
        return "allow", str(answer.get("summary") or "")
    verdict = str(answer.get("verdict") or "?").upper()
    return "refuse", (f"Marketplace Guard refused it before it could load ({verdict}): "
                      f"{answer.get('summary') or 'see its report'}")


def find_function(module, name):
    """module.name when this Python has that module and it has such a function, else None (another Home Assistant
    version). Checks each package level with find_spec before importing anything."""
    parts = module.split(".")
    for depth in range(1, len(parts) + 1):
        if importlib.util.find_spec(".".join(parts[:depth])) is None:
            return None
    function = getattr(importlib.import_module(module), name, None)
    return function if callable(function) else None


def manifest_version(folder):
    """The version in folder/manifest.json as a fact: a non-empty string, or None when there is none to read (missing,
    not JSON, no version)."""
    path = os.path.join(folder, MANIFEST)
    if not os.path.isfile(path):
        return None
    try:  # the app replaces the folder as a whole: the file can go between the check above and the read
        with open(path, encoding="utf-8") as f:
            text = f.read(MAX_MANIFEST)
    except OSError:
        return None
    try:  # only parsing tells whether it is valid JSON
        manifest = json.loads(text)
    except ValueError:
        return None
    version = manifest.get("version") if isinstance(manifest, dict) else None
    return version if isinstance(version, str) and version else None


class CopyWatch:
    """Whether the gate's folder still holds the code that runs (ADR-0044). running is the version read while Python
    imported the gate. Another version on disk (newer, or older after a rollback) runs only after a restart: the first
    time judge() sees one, it calls mark_restart(version on disk), once, since Home Assistant's flag latches until the
    restart."""

    def __init__(self, folder, running, mark_restart):
        self.folder = folder
        self.running = running
        self.mark_restart = mark_restart
        self.state = None  # not judged yet

    def read(self):
        """The version on disk now. File I/O: Home Assistant runs this in an executor."""
        return manifest_version(self.folder)

    def judge(self, on_disk):
        """Take the version read from disk; returns the state as a fact: "current" (the code on disk runs) |
        "replaced" (another version waits for a restart; latched) | "unknown" (a version could not be read, nothing is
        concluded)."""
        if self.state == "replaced":
            return self.state
        if self.running is None or on_disk is None:
            self.state = "unknown"
        elif on_disk == self.running:
            self.state = "current"
        else:
            self.state = "replaced"
            self.mark_restart(on_disk)
        return self.state
