#!/usr/bin/env python3
"""Repository checks for Marketplace Guard, with one exit code.

    python3 tools/check.py          ADR index, Markdown links, add-on configuration
    python3 tools/check.py --all    the same, plus the unit tests and tools/check_neutral.py: the gate before a push

What each check looks at:
- adr-index: docs/adr/README.md lists every docs/adr/NNNN-*.md once, with the title (its "# " heading), status and
  date of the ADR; the numbers run from 0001 without gaps; every listed file exists; every status is one of the
  values the ADR rules allow, and "superseded by ADR-NNNN" names an ADR that exists.
- links: every relative Markdown link in AGENTS.md, README.md, PUBLISHING.md, marketplace_guard/*.md and docs/adr/*.md
  resolves to a file or folder inside the repository, and every repository path AGENTS.md names in backticks exists.
- addon-config: in marketplace_guard/config.yaml the options are a subset of the schema; every schema option has a name and
  a description in every translation (en and de at least), and no translation names an option the schema lacks;
  every schema option is in DEFAULTS in guard.py, with the same value where options sets a default; the gate
  integration's manifest.json carries the version of config.yaml. It reads YAML with
  PyYAML; without PyYAML this check does not run and says how to install it.
- unit-tests (--all): the add-on's tests in marketplace_guard/tests and the tests of these tools (tools/test_*.py).
- site-neutral (--all): tools/check_neutral.py (ADR-0011).

Exit 0: every check ran and passed. 1: a check found problems. 2: nothing failed, but a check could not run; the
output names its missing precondition and the next step.
"""
import ast
import collections
import glob
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = "marketplace_guard"
REQUIRED_TRANSLATIONS = ("en", "de")

# state: "ok" | "fail" | "not-run"; summary: one line; details: lines shown below it
Result = collections.namedtuple("Result", "name state summary details")


# ---------------------------------------------------------------- ADR index
ADR_FILE = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
ADR_STATUS = re.compile(r"^(proposed|accepted|rejected|deprecated|superseded by ADR-(\d{4}))$")
INDEX_ROW = re.compile(r"^\|\s*\[(\d{4})\]\(([^)\s]+)\)\s*\|(.*)\|(.*)\|(.*)\|\s*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def front_matter(text):
    """The "key: value" lines between the leading "---" lines, as a dict; {} without front matter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return {}  # no closing "---": not front matter


def heading(text):
    """The first "# " heading, or None."""
    return next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), None)


def adr_index_problems(adrs, readme):
    """adrs: {file name: text} of every *.md in docs/adr except README.md; readme: the text of docs/adr/README.md.
    Returns the problems as lines (empty when the index and the ADRs agree)."""
    problems = []
    facts = {}  # number -> (file name, title, status, date)
    for name in sorted(adrs):
        m = ADR_FILE.match(name)
        if not m:
            problems.append(f"docs/adr/{name}: not named NNNN-title-in-kebab-case.md")
            continue
        fm = front_matter(adrs[name])
        for key in ("status", "date", "decision-makers"):
            if not fm.get(key):
                problems.append(f"docs/adr/{name}: front matter has no {key}")
        status, date = fm.get("status", ""), fm.get("date", "")
        if status and not ADR_STATUS.match(status):
            problems.append(f"docs/adr/{name}: status {status!r} is not proposed, accepted, rejected, deprecated or "
                            f"superseded by ADR-NNNN")
        if date and not DATE.match(date):
            problems.append(f"docs/adr/{name}: date {date!r} is not YYYY-MM-DD")
        title = heading(adrs[name])
        if not title:
            problems.append(f"docs/adr/{name}: no '# ' title")
        number = int(m.group(1))
        if number in facts:
            problems.append(f"docs/adr/{name}: number {m.group(1)} also used by {facts[number][0]}")
            continue
        facts[number] = (name, title, status, date)
    numbers = sorted(facts)
    missing = [n for n in range(1, (numbers[-1] if numbers else 0) + 1) if n not in facts]
    if missing:
        problems.append("docs/adr: numbers missing (no gaps allowed): " + ", ".join(f"{n:04d}" for n in missing))
    for number, (name, _, status, _) in sorted(facts.items()):
        sup = ADR_STATUS.match(status)
        if sup and sup.group(2) and int(sup.group(2)) not in facts:
            problems.append(f"docs/adr/{name}: superseded by ADR-{sup.group(2)}, which does not exist")

    listed = {}
    for no, line in enumerate(readme.splitlines(), 1):
        row = INDEX_ROW.match(line)
        if not row:
            continue
        num, target = row.group(1), row.group(2)
        title, status, date = (c.strip() for c in row.group(3, 4, 5))
        where = f"docs/adr/README.md:{no}"
        if target in listed:
            problems.append(f"{where}: {target} is listed twice")
            continue
        listed[target] = no
        if target not in adrs:
            problems.append(f"{where}: {target} does not exist")
            continue
        m = ADR_FILE.match(target)
        if not m or int(m.group(1)) not in facts or facts[int(m.group(1))][0] != target:
            continue  # the file itself is reported above
        _, f_title, f_status, f_date = facts[int(m.group(1))]
        if num != m.group(1):
            problems.append(f"{where}: number {num} links to {target}")
        for what, in_index, in_file in (("title", title, f_title), ("status", status, f_status),
                                        ("date", date, f_date)):
            if in_index != in_file:
                problems.append(f"{where}: {what} {in_index!r} differs from {target}: {in_file!r}")
    for name, _, _, _ in facts.values():
        if name not in listed:
            problems.append(f"docs/adr/README.md: {name} is not in the index")
    return problems


def check_adr_index(root):
    adr_dir = os.path.join(root, "docs", "adr")
    readme = os.path.join(adr_dir, "README.md")
    if not os.path.isfile(readme):
        return Result("adr-index", "fail", "docs/adr/README.md missing", [])
    adrs = {os.path.basename(p): _read(p) for p in glob.glob(os.path.join(adr_dir, "*.md"))
            if os.path.basename(p) != "README.md"}
    problems = adr_index_problems(adrs, _read(readme))
    if problems:
        return Result("adr-index", "fail", f"{len(problems)} problem(s)", problems)
    return Result("adr-index", "ok", f"{len(adrs)} ADRs, index complete", [])


# ---------------------------------------------------------------- Markdown links
LINK = re.compile(r"\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REF_DEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)")
CODE_SPAN = re.compile(r"`+[^`]*`+")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
# Repository paths AGENTS.md names in backticks; "NNNN", "*" and "<...>" mark a naming pattern, not a file.
AGENTS_PATH = re.compile(r"`((?:marketplace_guard|docs|tools)/[^`\s]+|[A-Z][A-Z_]*\.md|repository\.yaml)`")


def markdown_files(root):
    """The Markdown files whose links are checked, relative to root. The three top-level files must exist."""
    names = ["AGENTS.md", "README.md", "PUBLISHING.md"]
    names += sorted(os.path.relpath(p, root).replace("\\", "/") for pattern in ("marketplace_guard/*.md", "docs/adr/*.md")
                    for p in glob.glob(os.path.join(root, *pattern.split("/"))))
    return names


def link_targets(text):
    """(line number, target) of every Markdown link outside code blocks and code spans."""
    found, fence = [], None
    for no, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        marker = stripped[:3]
        if marker in ("```", "~~~"):
            fence = None if fence == marker else (fence or marker)
            continue
        if fence:
            continue
        plain = CODE_SPAN.sub("", line)
        found += [(no, m.group(1)) for m in LINK.finditer(plain)]
        ref = REF_DEF.match(plain)
        if ref:
            found.append((no, ref.group(1)))
    return found


def link_problems(root, names):
    """Problems of the relative links in the given Markdown files (paths relative to root); also the count checked."""
    problems, checked = [], 0
    base = os.path.abspath(root)
    for rel in names:
        path = os.path.join(root, *rel.split("/"))
        if not os.path.isfile(path):
            problems.append(f"{rel}: missing")
            continue
        for no, target in link_targets(_read(path)):
            if SCHEME.match(target) or target.startswith(("#", "/")):
                continue  # a URL, an anchor in the same file, or an absolute path: not a relative link
            file_part = urllib.parse.unquote(re.split(r"[#?]", target, maxsplit=1)[0])
            if not file_part:
                continue
            checked += 1
            resolved = os.path.abspath(os.path.join(os.path.dirname(path), *file_part.split("/")))
            if not (resolved == base or resolved.startswith(base + os.sep)):
                problems.append(f"{rel}:{no}: link {target} points outside the repository")
            elif not os.path.exists(resolved):
                problems.append(f"{rel}:{no}: link {target} does not resolve")
    return problems, checked


def agents_path_problems(root):
    """Repository paths named in backticks in AGENTS.md that do not exist; also the count checked."""
    path = os.path.join(root, "AGENTS.md")
    if not os.path.isfile(path):
        return [], 0  # reported by link_problems
    problems, checked = [], 0
    for no, line in enumerate(_read(path).splitlines(), 1):
        for m in AGENTS_PATH.finditer(line):
            p = m.group(1)
            if "NNNN" in p or "*" in p or "<" in p:
                continue
            checked += 1
            if not os.path.exists(os.path.join(root, *p.rstrip("/").split("/"))):
                problems.append(f"AGENTS.md:{no}: path {p} does not exist")
    return problems, checked


def check_links(root):
    problems, links = link_problems(root, markdown_files(root))
    path_problems, paths = agents_path_problems(root)
    problems += path_problems
    if problems:
        return Result("links", "fail", f"{len(problems)} problem(s)", problems)
    return Result("links", "ok", f"{links} relative links, {paths} paths in AGENTS.md", [])


# ---------------------------------------------------------------- add-on configuration
def same_value(a, b):
    """Equal including the type (True is not 1)."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def addon_config_problems(config, translations, defaults):
    """config: marketplace_guard/config.yaml; translations: {language: parsed translations/<language>.yaml};
    defaults: DEFAULTS from guard.py. Returns the problems as lines."""
    problems = []
    options = config.get("options") if isinstance(config, dict) else None
    schema = config.get("schema") if isinstance(config, dict) else None
    if not isinstance(options, dict) or not isinstance(schema, dict):
        return ["config.yaml: options and schema must both be mappings"]
    for key in sorted(set(options) - set(schema)):
        problems.append(f"config.yaml: option {key} has no schema entry")
    for lang in REQUIRED_TRANSLATIONS:
        if lang not in translations:
            problems.append(f"translations/{lang}.yaml missing")
    for lang, data in sorted(translations.items()):
        texts = data.get("configuration") if isinstance(data, dict) else None
        if not isinstance(texts, dict):
            problems.append(f"translations/{lang}.yaml: no configuration mapping")
            continue
        for key in sorted(schema):
            entry = texts.get(key)
            for field in ("name", "description"):
                value = entry.get(field) if isinstance(entry, dict) else None
                if not isinstance(value, str) or not value.strip():
                    problems.append(f"translations/{lang}.yaml: option {key} has no {field}")
        for key in sorted(set(texts) - set(schema)):
            problems.append(f"translations/{lang}.yaml: text for unknown option {key}")
    for key in sorted(schema):
        if key not in defaults:
            problems.append(f"guard.py: DEFAULTS lacks schema option {key}")
        elif key in options and not same_value(options[key], defaults[key]):
            problems.append(f"default of {key} differs: config.yaml {options[key]!r}, guard.py {defaults[key]!r}")
    return problems


def guard_defaults(source):
    """The literal DEFAULTS dict of guard.py's source, read without importing it; None if there is none."""
    for node in ast.parse(source).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "DEFAULTS" and isinstance(node.value, ast.Dict)):
            return ast.literal_eval(node.value)
    return None


def gate_version_problems(version, manifest_path):
    """The gate integration the add-on installs carries the add-on's version, so the add-on can tell an older copy in
    custom_components from its own (ADR-0042)."""
    if not os.path.isfile(manifest_path):
        return ["gate/marketplace_guard_gate/manifest.json missing"]
    try:  # parsing is the only way to know whether the file is valid JSON
        manifest = json.loads(_read(manifest_path))
    except ValueError:
        return ["gate manifest.json: not valid JSON"]
    if manifest.get("version") != version:
        return [f"gate manifest.json has version {manifest.get('version')!r}, config.yaml {version!r}: set both"]
    return []


def check_addon_config(root):
    if importlib.util.find_spec("yaml") is None:
        return Result("addon-config", "not-run", "PyYAML is not installed", [
            f"next step: {sys.executable} -m pip install pyyaml, then run this check again"])
    import yaml

    addon = os.path.join(root, ADDON)
    docs = {"config.yaml": os.path.join(addon, "config.yaml")}
    docs.update({f"translations/{os.path.basename(p)}": p
                 for p in sorted(glob.glob(os.path.join(addon, "translations", "*.yaml")))})
    parsed, problems = {}, []
    for label, path in docs.items():
        if not os.path.isfile(path):
            problems.append(f"{label} missing")
            continue
        try:
            parsed[label] = yaml.safe_load(_read(path))
        except yaml.YAMLError as e:  # parsing is the only way to know whether the file is valid YAML
            problems.append(f"{label}: not valid YAML ({type(e).__name__})")
    guard_path = os.path.join(addon, "guard.py")
    defaults = guard_defaults(_read(guard_path)) if os.path.isfile(guard_path) else None
    if defaults is None:
        problems.append("guard.py: no literal DEFAULTS dict")
    if problems:
        return Result("addon-config", "fail", f"{len(problems)} problem(s)", problems)
    translations = {label[len("translations/"):-len(".yaml")]: data
                    for label, data in parsed.items() if label.startswith("translations/")}
    problems = addon_config_problems(parsed["config.yaml"], translations, defaults)
    problems += gate_version_problems(parsed["config.yaml"].get("version"),
                                      os.path.join(addon, "gate", "marketplace_guard_gate", "manifest.json"))
    if problems:
        return Result("addon-config", "fail", f"{len(problems)} problem(s)", problems)
    schema = parsed["config.yaml"]["schema"]
    return Result("addon-config", "ok", f"{len(schema)} options, translated in {', '.join(sorted(translations))}", [])


# ---------------------------------------------------------------- unit tests and the site-neutral check
def _run(cmd, cwd):
    proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


def check_unit_tests(root):
    unittest = [sys.executable, "-B", "-W", "error::DeprecationWarning", "-m", "unittest", "discover"]
    runs = (("marketplace_guard/tests", unittest + ["-s", "tests"], os.path.join(root, ADDON)),
            ("tools", unittest + ["-s", "tools", "-p", "test_*.py"], root))
    summary, details, failed = [], [], False
    for label, cmd, cwd in runs:
        code, out = _run(cmd, cwd)
        ran = next((line for line in out.splitlines() if line.startswith("Ran ")), "no tests ran")
        summary.append(f"{label}: {ran}")
        if code != 0:
            failed = True
            details += [f"{label}: exit {code}"] + ["  " + line for line in out.splitlines()[-40:]]
    return Result("unit-tests", "fail" if failed else "ok", "; ".join(summary), details)


def check_site_neutral(root):
    code, out = _run([sys.executable, "-I", os.path.join(root, "tools", "check_neutral.py")], root)
    lines = [line for line in out.splitlines() if line.strip()]
    # check_neutral.py: exit 0 clean, 1 hits, 2 no site term list (it says how to go on)
    state = {0: "ok", 2: "not-run"}.get(code, "fail")
    if state == "ok":
        return Result("site-neutral", "ok", lines[-1] if lines else "clean", [])
    return Result("site-neutral", state, f"check_neutral.py exit {code}", lines)


# ---------------------------------------------------------------- main
def overall_exit(results):
    """0 every check ran and passed, 1 a check found problems, 2 none failed but a check could not run."""
    states = {r.state for r in results}
    return 1 if "fail" in states else 2 if "not-run" in states else 0


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def main(argv):
    if any(a != "--all" for a in argv):
        print("usage: python3 tools/check.py [--all]   (--all adds the unit tests and tools/check_neutral.py)",
              file=sys.stderr)
        return 2
    checks = [check_adr_index, check_links, check_addon_config]
    if "--all" in argv:
        checks += [check_unit_tests, check_site_neutral]
    results = [check(ROOT) for check in checks]
    for r in results:
        print(f"{r.name:<13} {r.state.upper() if r.state != 'ok' else 'ok':<8} {r.summary}")
        for line in r.details:
            print(f"    {line}")
    code = overall_exit(results)
    print({0: f"check: all {len(results)} checks passed",
           1: "check: problems found (see above)",
           2: "check: no problems found, but a check could not run (see its next step above)"}[code])
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
