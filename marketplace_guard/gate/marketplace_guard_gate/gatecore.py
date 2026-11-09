"""The logic of the Marketplace Guard gate (ADR-0042), without Home Assistant imports, so that it is tested with the
standard library. __init__.py wires it into Home Assistant's Marketplace.

The Marketplace writes a repository's content, runs the check of its repository class
(`async_check_written_content`), and only then loads anything: when the check raises, it puts back what was there.
The gate wraps that check: after the Marketplace's own, it asks the Marketplace Guard app for a verdict through two
folders in Home Assistant's configuration folder and refuses what the app would quarantine.
"""
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
