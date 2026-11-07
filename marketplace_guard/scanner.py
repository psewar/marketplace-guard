#!/usr/bin/env python3
"""Marketplace Guard - static security scan of a Home Assistant custom component, frontend plugin or repository.

Standard library only; bandit & pip-audit are invoked as subprocesses when available and degrade
gracefully when missing. Calibrated conservatively: only strong supply-chain / exfiltration signals
become HIGH, so the quarantine gate (default threshold HIGH) does not lock away harmless integrations.
"""
import os, re, io, json, gzip, zlib, stat, bisect, codecs, shutil, subprocess, tempfile, time, tokenize
import http.client, urllib.request

SEV_ORDER = {"clean": 0, "info": 1, "low": 2, "medium": 3, "high": 4, "critical": 5}
SEV_NAMES = {v: k for k, v in SEV_ORDER.items()}

# Folders a component cannot import: version control and bytecode caches. Everything else inside a component,
# test folders and test_*.py files included, can be imported by its code and is scanned (ADR-0014).
SKIP_DIR_PARTS = {".git", ".github", "__pycache__"}

# Files are read up to this size; a larger script is scanned up to it and that is a finding (ADR-0037). The line rules
# need about nine times the file's size in memory, so this bounds them; code of real integrations stays far below it.
MAX_SCAN_BYTES = 16 * 1024 * 1024
# A larger Python file is read once more by Python's tokenizer, line by line and never wholly in memory, up to this size:
# a file of nothing but literal data (images, tables) is not code that went unread (ADR-0037).
DATA_CHECK_MAX_BYTES = 64 * 1024 * 1024
# bandit gets only Python files up to this size: its memory grows about 160-fold with the code (2 MiB took 354 MiB,
# 8 MiB 1.3 GB), and one larger file could exhaust the host's memory. The line rules read larger files (ADR-0037).
BANDIT_MAX_BYTES = 2 * 1024 * 1024
JS_EXTS = (".js", ".mjs", ".cjs")


def _is_regular(path):
    """Whether path itself is a regular file: not a symlink, FIFO, device or socket. Only those are ever opened."""
    try:
        return stat.S_ISREG(os.lstat(path).st_mode)
    except OSError:  # vanished or unreadable: a file system fault
        return False


def open_regular(path):
    """A binary file object for a regular file, or None. A symlink is not followed (O_NOFOLLOW) and opening never
    blocks (O_NONBLOCK), also when the file was swapped for a FIFO after the check (ADR-0027)."""
    if not _is_regular(path):
        return None
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    try:
        return os.fdopen(os.open(path, flags), "rb")
    except OSError:  # vanished, swapped for a symlink, permissions: a file system fault
        return None


def read_bytes(path, limit=None):
    """(the first `limit` bytes (default MAX_SCAN_BYTES) of a regular file, whether it is longer), or (b"", False)
    when it is not a regular file or cannot be read."""
    limit = MAX_SCAN_BYTES if limit is None else limit
    f = open_regular(path)
    if f is None:
        return b"", False
    try:
        with f:
            data = f.read(limit + 1)
    except OSError:  # an I/O fault while reading
        return b"", False
    return data[:limit], len(data) > limit


def _read(path, limit=None):
    return read_bytes(path, limit)[0].decode("utf-8", errors="replace")


def _iter_files(root, exts):
    """Regular files below root whose names end with one of exts; symlinks and special files are reported by
    special_entries() and never read."""
    for dp, _, fns in os.walk(root):
        # Only folders below the scanned root count: a component whose own folder (or a parent folder) is
        # called e.g. "testing" must still be scanned, or its name alone would hide it from the scan.
        rel = os.path.relpath(dp, root)
        parts = [] if rel == "." else rel.replace("\\", "/").split("/")
        if any(p in SKIP_DIR_PARTS for p in parts):
            continue
        for fn in fns:
            if fn.lower().endswith(exts) and _is_regular(os.path.join(dp, fn)):
                yield os.path.join(dp, fn)


SPECIAL_MSG = {
    "symlink-outside": "Symbolic link to a place outside the component: Home Assistant or the browser would load "
                       "content that was not scanned",
    "symlink": "Symbolic link inside the component (not followed; its target is scanned where it lies)",
    "special-file": "FIFO, device or socket: no component needs one, and reading it would block or never end",
}
SPECIAL_SEVERITY = {"symlink-outside": "high", "symlink": "info", "special-file": "high"}


def special_entries(root):
    """What in a component is neither a regular file nor a folder, as sorted (relative path, kind, link target):
    kind "symlink-outside" (the target leaves the component), "symlink" or "special-file". None of it is read
    (ADR-0027)."""
    out = []
    base = os.path.realpath(root)
    for dp, subdirs, fns in os.walk(root):  # followlinks=False: a linked folder is listed, never entered
        subdirs[:] = [s for s in subdirs if s not in (".git", ".github")]
        for name in subdirs + fns:
            p = os.path.join(dp, name)
            rel = os.path.relpath(p, root).replace("\\", "/")
            if os.path.islink(p):
                try:
                    target = os.readlink(p)
                except OSError:  # vanished: a file system fault
                    continue
                real = os.path.realpath(p)
                inside = real == base or real.startswith(base + os.sep)
                out.append((rel, "symlink" if inside else "symlink-outside", target))
            elif name in fns and not _is_regular(p) and os.path.lexists(p):
                out.append((rel, "special-file", ""))
    return sorted(out)


def F(sev, code, msg, file=None, line=None):
    return {"severity": sev, "code": code, "msg": msg, "file": file, "line": line}


# ---------------------------------------------------------------- compiled code (ADR-0015)
NATIVE_SUFFIXES = (".so", ".pyd")
COMPILED_MSG = {
    "native-module": "Native extension module: compiled code that cannot be reviewed (Python loads it even "
                     "before a .py of the same name)",
    "sourceless-bytecode": "Bytecode without source: Python imports it, but there is no code to review",
    "unchecked-bytecode": "Bytecode marked 'unchecked hash': Python runs it instead of the .py next to it",
}


def _pyc_flags(path):
    # PEP 552 header: magic (4 bytes), then flags (4 bytes, little endian): bit 0 hash-based, bit 1 check source
    head = read_bytes(path, 8)[0]
    return int.from_bytes(head[4:8], "little") if len(head) == 8 else None


def compiled_code(root):
    """Compiled Python a component can import but nobody can review, as sorted (relative path, kind):
    native extension modules; bytecode beside the code with no .py of the same name (imported in place of a
    source); __pycache__ bytecode marked "unchecked hash" (run without looking at the source). Bytecode that
    Python writes itself (timestamp or checked hash) is a cache and not listed."""
    out = []
    for dp, subdirs, fns in os.walk(root):
        subdirs[:] = [s for s in subdirs if s not in (".git", ".github")]
        in_cache = os.path.basename(dp) == "__pycache__"
        stems = {fn.split(".")[0] for fn in fns if fn.lower().endswith(".py")}
        for fn in fns:
            low = fn.lower()
            rel = os.path.relpath(os.path.join(dp, fn), root).replace("\\", "/")
            if low.endswith(NATIVE_SUFFIXES):
                out.append((rel, "native-module"))
            elif low.endswith(".pyc") and not in_cache and fn.split(".")[0] not in stems:
                out.append((rel, "sourceless-bytecode"))
            elif low.endswith(".pyc") and in_cache and _pyc_flags(os.path.join(dp, fn)) == 0b01:
                out.append((rel, "unchecked-bytecode"))
    return sorted(out)


# ---------------------------------------------------------------- Python heuristics
# Only clearly suspicious patterns are HIGH. Normal integrations talk to their vendor cloud
# (outbound URLs) -> that is INFO, never a quarantine reason.
# Repetitions inside a rule are bounded ({0,500} instead of *): an unbounded one is retried from every start on a
# long line and makes the scan quadratic, which a component could use to delay its own quarantine (ADR-0027).
PY_HIGH = [
    ("secret-store-access",
     re.compile(r"\.storage/(core\.config_entries|auth|application_credentials)|/config/\.storage|/homeassistant/\.storage|(/config/|/homeassistant/)secrets\.yaml|open\s*\([^)]{0,500}secrets\.yaml"),
     "Reads HA secret store / secrets.yaml"),
    ("shell-exec",
     re.compile(r"os\.system\s*\(|subprocess\.[A-Za-z_]+\([^)]{0,500}shell\s*=\s*True|(^|[^.\w])Popen\s*\(|pty\.spawn|os\.popen\s*\("),
     "Shell / process execution"),
    ("runtime-fetch-exec",
     re.compile(r"urllib\.request\.urlretrieve|(^|[^\w])(wget|curl)\s+http|pip\s+install\s|os\.chmod\([^)]{0,500}0o?[75]|subprocess[^\n]{0,500}(curl|wget)"),
     "Downloads or installs additional code at runtime"),
]
PY_MEDIUM = [
    ("dynamic-exec", re.compile(r"(^|[^.\w])(eval|exec)\s*\("), "Dynamic code execution (eval/exec)"),
    ("unsafe-deser", re.compile(r"pickle\.loads|yaml\.load\s*\((?![^)]{0,500}Loader)"), "Unsafe deserialization (pickle / yaml.load without Loader)"),
]
IP_URL = re.compile(r"https?://(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")
ANY_URL = re.compile(r"https?://([A-Za-z0-9._\-]+)")
# Hosts not listed as outbound hosts. Hosts that serve anyone's files (raw.githubusercontent.com, gists, release
# downloads) are listed: they are where payloads are usually kept.
ALLOW_HOSTS = ("github.com", "pypi.org", "files.pythonhosted.org", "home-assistant.io", "hacs.xyz",
               "localhost", "127.0.0.1")
SHARED_HOSTS = ("gist.github.com", "gist.githubusercontent.com", "raw.githubusercontent.com",
                "objects.githubusercontent.com", "codeload.github.com")
B64_BLOB = re.compile(r"['\"][A-Za-z0-9+/]{220,}={0,2}['\"]")
# The danger is not the blob alone, but decode + execution within the same file:
DECODE_RE = re.compile(r"base64\.b64decode|codecs\.decode\s*\(|marshal\.loads|(^|[^.\w])compile\s*\(")
EXEC_RE = re.compile(r"(^|[^.\w])(eval|exec)\s*\(")


# ---------------------------------------------------------------- Unicode that hides code (ADR-0018)
# Trojan Source (CVE-2021-42574): bidirectional controls (LRE, RLE, PDF, LRO, RLO, LRI, RLI, FSI, PDI) make code
# display in another order than it runs. Written as escapes, so this file holds none of them.
BIDI_CONTROLS = re.compile("[\u202a-\u202e\u2066-\u2069]")
# Invisible characters: zero width space, non-joiner and joiner, word joiner, and U+FEFF after the start of a file.
INVISIBLE = re.compile("[\u200b-\u200d\u2060\ufeff]")


def unicode_findings(text, rel, kind):
    """Characters that make code read differently than it runs (pure). kind: "py", "js" or "json".
    - Bidirectional controls: high in every kind, on every line, comments included: a comment is where Trojan
      Source hides the reordering (ADR-0006 does not apply to this check).
    - Invisible characters next to ASCII text, where identifiers, keywords, hosts and paths are: medium in Python,
      info in JavaScript (bundles carry them for emoji and scripts), not in JSON (translations use them for Persian,
      Indic scripts and emoji); comment lines are skipped like in the other heuristics (ADR-0006)."""
    out = []
    for no, line in enumerate(text.split("\n"), 1):
        bidi = sorted({f"U+{ord(c):04X}" for c in BIDI_CONTROLS.findall(line)})
        if bidi:
            out.append(F("high", "bidi-control",
                         f"Bidirectional control character {', '.join(bidi)} (Trojan Source, CVE-2021-42574): "
                         "the code may display in another order than it runs", rel, no))
        stripped = line.lstrip()
        if kind == "json" or stripped.startswith("#") or stripped.startswith("//"):
            continue
        hidden = set()
        for m in INVISIBLE.finditer(line):
            if no == 1 and m.start() == 0 and m.group() == "\ufeff":
                continue  # a byte order mark at the start of the file
            before = line[m.start() - 1] if m.start() else " "
            after = line[m.end()] if m.end() < len(line) else " "
            if before.isascii() or after.isascii():
                hidden.add(f"U+{ord(m.group()):04X}")
        if hidden:
            out.append(F("info" if kind == "js" else "medium", "invisible-char",
                         f"Invisible character {', '.join(sorted(hidden))} next to code text: a name, string or "
                         "host may not be what it looks like", rel, no))
    return out


def _plain_string(tok):
    """A string literal token that runs nothing: not an f-string (or t-string), whose braces hold code."""
    if tok.type != tokenize.STRING:
        return False
    prefix = tok.string[:len(tok.string) - len(tok.string.lstrip("rRbBuUfFtT"))].lower()
    return "f" not in prefix and "t" not in prefix


def python_text_lines(text):
    """The lines Python never runs, from its own tokenizer (pure): (comment_lines, string_lines), or None when the text
    does not tokenize (then no line is skipped).
    - comment_lines hold nothing but a comment. A '#' inside a string is not a comment, and '//' never starts one in
      Python: a continued expression line can begin with the '//' operator (ADR-0026).
    - string_lines belong to a statement made of nothing but string literals: a docstring, or a string standing alone.
      Python evaluates such a statement to nothing; a docstring only becomes __doc__. Not one: an f-string (it runs
      the code in its braces) and a statement with anything else in it, such as '; os.system(...)' (ADR-0035)."""
    comments, code, strings = set(), set(), set()
    layout = (tokenize.NL, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER, tokenize.ENCODING)
    statement = []  # the tokens of the current logical line, without layout and comments
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                comments.add(tok.start[0])
            elif tok.type == tokenize.NEWLINE:  # the end of a logical line; tokenize adds one at the end of the text
                if statement and all(_plain_string(t) for t in statement):
                    strings.update(range(statement[0].start[0], statement[-1].end[0] + 1))
                statement = []
            elif tok.type not in layout:
                code.update(range(tok.start[0], tok.end[0] + 1))
                statement.append(tok)
    except (tokenize.TokenError, SyntaxError):  # tokenizing is the only check; such code fails to import anyway
        return None
    return comments - code, strings


def python_comment_lines(text):
    """The numbers of the lines that hold nothing but a comment (pure), or None when the text does not tokenize."""
    lines = python_text_lines(text)
    return None if lines is None else lines[0]


LITERAL_PUNCTUATION = {"(", ")", "[", "]", "{", "}", ",", ":", "-", "+"}
LITERAL_NAMES = {"True", "False", "None"}
_LAYOUT = (tokenize.NL, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING, tokenize.ENDMARKER)


def _literal_statement(stmt):
    """Whether one logical line is literal data: an import; NAME [: annotation] = a value of literals (plain strings,
    numbers, True/False/None, lists, tuples, dicts, sets of them); or plain strings standing alone (a docstring)."""
    if stmt[0].string in ("import", "from"):
        return all(t.type == tokenize.NAME or t.string in (".", ",", "(", ")", "*") for t in stmt)
    if all(_plain_string(t) for t in stmt):
        return True
    if stmt[0].type != tokenize.NAME or len(stmt) < 3:
        return False
    if stmt[1].string == "=":
        value = stmt[2:]
    elif stmt[1].string == ":":
        eq = next((i for i, t in enumerate(stmt) if t.string == "="), None)
        if eq is None or not all(t.type == tokenize.NAME or t.string in (".", "[", "]", ",") for t in stmt[2:eq]):
            return False
        value = stmt[eq + 1:]
    else:
        return False
    return bool(value) and all(_plain_string(t) or t.type == tokenize.NUMBER or t.string in LITERAL_PUNCTUATION
                               or (t.type == tokenize.NAME and t.string in LITERAL_NAMES) for t in value)


def literal_data_only(path, limit=None):
    """Whether a Python file holds nothing but literal data, read once by Python's tokenizer, line by line and never
    wholly in memory, up to `limit` bytes (default DATA_CHECK_MAX_BYTES). A fact, as a dict: data (bool), statements
    read, and for a file that is not data the reason ("code", "too-large", "unusual-encoding", "untokenizable",
    "unreadable") and the line where it stopped (ADR-0037)."""
    limit = DATA_CHECK_MAX_BYTES if limit is None else limit
    facts = {"data": False, "statements": 0, "reason": None, "line": None}
    f = open_regular(path)
    if f is None:
        facts["reason"] = "unreadable"
        return facts
    read = 0

    def readline():
        nonlocal read
        if read > limit:
            return b""
        line = f.readline(limit - read + 1)  # also a single endless line is read only up to the limit
        read += len(line)
        return b"" if read > limit else line  # past the limit the tokenizer sees the end; checked below

    stmt = []
    try:
        with f:
            for tok in tokenize.tokenize(readline):
                if tok.type == tokenize.ENCODING:
                    if codecs.lookup(tok.string).name not in PLAIN_ENCODINGS:
                        facts["reason"] = "unusual-encoding"
                        return facts
                    continue
                if tok.type in _LAYOUT:
                    continue
                if tok.type != tokenize.NEWLINE:
                    stmt.append(tok)
                    continue
                if stmt:
                    facts["statements"] += 1
                    if not _literal_statement(stmt):
                        facts.update(reason="code", line=stmt[0].start[0])
                        return facts
                stmt = []
    except (tokenize.TokenError, SyntaxError, LookupError):  # tokenizing is the only check; such code fails to import
        facts["reason"] = "too-large" if read > limit else "untokenizable"  # cut at the limit inside a statement
        return facts
    except OSError:  # an I/O fault while reading
        facts["reason"] = "unreadable"
        return facts
    if read > limit:
        facts["reason"] = "too-large"
        return facts
    facts["data"] = True
    return facts


# Code that reads docstrings can run what they hold, so they are scanned as code then (ADR-0035).
DOCSTRING_READ = re.compile(r"__doc__|getdoc|get_docstring")


def js_comment_lines(text):
    """Lines whose first non-blank characters are '//' (ADR-0006). '#' starts a private class field in JavaScript,
    not a comment."""
    return {i for i, line in enumerate(text.split("\n"), 1) if line.lstrip().startswith("//")}


# Encodings that read ASCII as ASCII: a cookie naming one of them cannot hide code (codecs.lookup() names)
PLAIN_ENCODINGS = {"utf-8", "utf-8-sig", "ascii", "iso8859-1", "iso8859-15", "cp1252"}


def python_source(raw):
    """Python source bytes as Python reads them (pure): (text, codec, problem). A PEP 263 cookie in the first two
    lines names the codec Python decodes the file with; a codec that does not read ASCII as ASCII (utf-7,
    unicode_escape, ...) shows the scanner other code than Python runs, so the text is decoded with it and problem
    is "unusual"; "unknown" when Python could not decode the file at all (ADR-0026)."""
    try:
        codec = codecs.lookup(tokenize.detect_encoding(io.BytesIO(raw).readline)[0]).name
    except (SyntaxError, LookupError):  # the cookie rules and the codec registry offer no check without trying
        return raw.decode("utf-8", "replace"), None, "unknown"
    try:
        text = raw.decode(codec, "replace")
    except (TypeError, LookupError, UnicodeError):  # not a text codec (rot13, zlib): Python refuses the file too
        return raw.decode("utf-8", "replace"), codec, "unknown"
    return text, codec, (None if codec in PLAIN_ENCODINGS else "unusual")


def _line_numbers(text):
    """pos -> line number in linear time overall (bisect over the newline positions)."""
    newlines = [m.start() for m in re.finditer("\n", text)]
    return lambda pos: bisect.bisect_right(newlines, pos - 1) + 1


def scan_text(txt, rel, kind, high_rules, med_rules, skip_lines=()):
    """The heuristic findings of one script's text (pure). kind: "py" or "js"; skip_lines: lines that are never run
    (comments, and in Python docstrings unless the code reads them)."""
    is_js = kind == "js"
    out = unicode_findings(txt, rel, kind)
    for i, line in enumerate(txt.splitlines(), 1):
        if i in skip_lines:
            # Comments and docstrings are never executed; they often *document* or *deny-list* scary patterns
            # (e.g. a path-traversal guard mentioning ".storage"/"secrets.yaml", or "a runtime pip install"). Skip them.
            continue
        for code, rx, msg in high_rules:
            if rx.search(line):
                out.append(F("high", code, msg, rel, i))
        for code, rx, msg in med_rules:
            if rx.search(line):
                # JS is usually minified -> heuristic hits are INFO only (otherwise constant false positives)
                out.append(F("info" if is_js else "medium", code, msg, rel, i))
    # Raw-IP URLs (vendor APIs use domains; raw IPs are unusual)
    line_of = _line_numbers(txt)
    for m in IP_URL.finditer(txt):
        out.append(F("medium", "ip-url", f"URL to raw IP {m.group(1)}", rel, line_of(m.start())))
    # Decode + dynamic execution in the same file = real payload pattern -> HIGH
    if DECODE_RE.search(txt) and EXEC_RE.search(txt):
        out.append(F("high", "decode-exec", "Decode + dynamic execution in the same file (obfuscation/payload pattern)", rel, None))
    # base64 blob on its own: JS -> INFO (minified assets), Python -> MEDIUM (rarely legitimate)
    if B64_BLOB.search(txt):
        out.append(F("info" if is_js else "medium", "embedded-blob",
                     "Long base64 blob in code" + (" (minified - usually an asset)" if is_js else ""), rel, None))
    # Outbound hosts -> INFO only (documented in the report), not a score driver
    hosts = set()
    for m in ANY_URL.finditer(txt):
        h = m.group(1).lower()
        if h in SHARED_HOSTS or not any(h == a or h.endswith("." + a) for a in ALLOW_HOSTS):
            hosts.add(h)
    for h in sorted(hosts)[:15]:
        out.append(F("info", "outbound-host", f"Outbound host: {h}", rel, None))
    # Deduplicate identical findings (minified JS lines would otherwise create hundreds of duplicates).
    # The msg is part of the key so that distinct hosts/messages on the same (codeless) line are kept.
    seen, dd = set(), []
    for f in out:
        k = (f["severity"], f["code"], f["line"], f["msg"])
        if k in seen:
            continue
        seen.add(k)
        dd.append(f)
    return dd


def _too_large(rel, kind):
    return F("high" if kind == "py" else "medium", "too-large",
             f"Larger than {MAX_SCAN_BYTES // (1024 * 1024)} MiB: only the start was scanned", rel)


def large_python_finding(path, rel):
    """The finding for a Python file larger than MAX_SCAN_BYTES: info when the tokenizer read all of it and found only
    literal data, high otherwise - code that went unread, or a file too large or too odd to tell (ADR-0037)."""
    mib = MAX_SCAN_BYTES // (1024 * 1024)
    facts = literal_data_only(path)
    if facts["data"]:
        return F("info", "large-data", f"Larger than {mib} MiB, but only literal data ({facts['statements']} imports "
                                       "and constants, read whole by Python's tokenizer); the line rules read the "
                                       f"first {mib} MiB", rel)
    why = {"code": f"code from line {facts['line']} on",
           "too-large": f"larger than {DATA_CHECK_MAX_BYTES // (1024 * 1024)} MiB",
           "unusual-encoding": "an unusual source encoding",
           "untokenizable": "text Python's tokenizer cannot read",
           "unreadable": "not readable"}[facts["reason"]]
    return F("high", "too-large", f"Larger than {mib} MiB and not only data ({why}): only the start was scanned", rel)


def bandit_files(pyfiles, rootlen):
    """The Python files bandit gets (up to BANDIT_MAX_BYTES), and an info finding for each larger one (ADR-0037)."""
    small, out = [], []
    mib = BANDIT_MAX_BYTES // (1024 * 1024)
    for pf in pyfiles:
        try:
            size = os.lstat(pf).st_size
        except OSError:  # vanished since it was listed: a race with the file system, nothing to analyse
            continue
        if size <= BANDIT_MAX_BYTES:
            small.append(pf)
        else:
            out.append(F("info", "not-analysed", f"Larger than {mib} MiB: not given to bandit, whose memory grows about "
                                                 "160-fold with the code; the line rules read it", pf[rootlen:].lstrip("/\\")))
    return small, out


def reads_docstrings(path):
    """Whether a Python file's text mentions reading docstrings (__doc__, getdoc, get_docstring) anywhere."""
    raw, _ = read_bytes(path)
    return DOCSTRING_READ.search(python_source(raw)[0]) is not None


def scan_python_file(path, rootlen, docstrings_are_code=False):
    """The heuristic findings of one Python file. docstrings_are_code: another file of the component reads docstrings,
    so they are scanned here too; the file's own text is checked for that as well (ADR-0035)."""
    raw, longer = read_bytes(path)
    rel = path[rootlen:].lstrip("/\\")
    txt, codec, problem = python_source(raw)
    out = []
    read = DOCSTRING_READ.search(txt)
    if read:
        out.append(F("info", "docstring-read", "Mentions reading docstrings (__doc__, getdoc, get_docstring): the "
                                               "component's docstrings are scanned as code", rel,
                     _line_numbers(txt)(read.start())))
    if problem == "unusual":
        out.append(F("high", "source-encoding", f"Declared source encoding {codec}: Python decodes this file so that "
                                                "it can run other code than it shows", rel, None))
    elif problem == "unknown":
        out.append(F("info", "source-encoding", "Source encoding Python cannot decode: scanned as UTF-8", rel, None))
    if longer:
        out.append(large_python_finding(path, rel))
    lines = python_text_lines(txt)
    if lines is None:
        skip = ()
    elif docstrings_are_code or read:
        skip = lines[0]
    else:
        skip = lines[0] | lines[1]
    return out + scan_text(txt, rel, "py", PY_HIGH, PY_MEDIUM, skip)


JS_MED = [
    ("js-eval", re.compile(r"(^|[^.\w])eval\s*\(|new\s+Function\s*\("), "JS eval / Function()"),
    ("js-deobf", re.compile(r"atob\s*\(|fromCharCode|unescape\s*\(|\\x[0-9a-fA-F]{2}\\x"), "JS deobfuscation"),
]


def scan_js_text(txt, rel):
    return scan_text(txt, rel, "js", [], JS_MED, js_comment_lines(txt))


def scan_js_file(path, rootlen):
    raw, longer = read_bytes(path)
    rel = path[rootlen:].lstrip("/\\")
    return ([_too_large(rel, "js")] if longer else []) + scan_js_text(raw.decode("utf-8", "replace"), rel)


# ---------------------------------------------------------------- precompressed scripts (ADR-0028)
GZ_SUFFIXES = tuple(e + ".gz" for e in JS_EXTS)
BR_SUFFIXES = tuple(e + ".br" for e in JS_EXTS)


def precompressed_findings(root):
    """Compressed copies of scripts. Home Assistant's web server (aiohttp) sends x.js.br or x.js.gz instead of x.js to
    a browser that accepts it, so the browser runs what the copy holds. A .gz is decompressed (up to MAX_SCAN_BYTES);
    when it is not the script next to it, that is high and its content is scanned as JavaScript. A .br cannot be read
    with the standard library and the Marketplace never writes one: high."""
    rootlen, out = len(root), []
    for fp in _iter_files(root, GZ_SUFFIXES):
        rel = fp[rootlen:].lstrip("/\\")
        raw, _ = read_bytes(fp)
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as g:
                data = g.read(MAX_SCAN_BYTES + 1)
        except (OSError, EOFError, zlib.error):  # decompressing is the only check of a gzip stream
            out.append(F("info", "precompressed-unreadable", "Compressed copy that does not decompress: a browser "
                                                             "cannot use it either", rel))
            continue
        if len(data) > MAX_SCAN_BYTES:
            out.append(_too_large(rel, "js"))
        script = fp[:-3]
        same = _is_regular(script) and read_bytes(script, MAX_SCAN_BYTES + 1)[0] == data
        if not same:
            if _is_regular(script):
                out.append(F("high", "precompressed-differs", f"Compressed copy differs from {rel[:-3]}: the browser "
                                                              "gets this content instead of the script", rel))
            out += scan_js_text(data[:MAX_SCAN_BYTES].decode("utf-8", "replace"), rel)
    for fp in _iter_files(root, BR_SUFFIXES):
        out.append(F("high", "precompressed-unreviewable", "Brotli copy of a script: the browser gets it instead of "
                                                           "the script, and it cannot be reviewed", fp[rootlen:].lstrip("/\\")))
    return out


# ---------------------------------------------------------------- external tools
def tool_env():
    """The environment for the scanners run as programs: without the Supervisor token, which they do not need."""
    return {k: v for k, v in os.environ.items() if k not in ("SUPERVISOR_TOKEN", "HASSIO_TOKEN")}


# Bandit reads an ini file and '# nosec' markers from the code it scans: a component could switch checks off or, with
# two .bandit files, make bandit stop without a report. Bandit gets its own empty ini and ignores nosec (ADR-0026).
BANDIT_CMD = ["bandit", "-r", "-f", "json", "-q", "--ignore-nosec"]
# Only genuine shell/code execution is HIGH (B307 eval / B301 pickle etc. -> low, otherwise noisy)
BANDIT_SHELL_EXEC = {"B102", "B602", "B604", "B605", "B609"}


def bandit_findings(returncode, stdout, root):
    """Findings from one bandit run (pure), decided by exit code and JSON fields: bandit exits 0 (nothing found) or 1
    (issues found) with a report; anything else means bandit did not analyse the code."""
    try:
        data = json.loads(stdout or "")
    except ValueError:  # parsing is the only check for a JSON report; no report is a fact in itself
        data = None
    results = data.get("results") if isinstance(data, dict) else None
    if returncode not in (0, 1) or not isinstance(results, list):
        return [F("info", "tool-error", f"bandit failed (exit {returncode}, no report): the Python code was not "
                                        "analysed by bandit")]
    out = []
    for r in results:
        if not isinstance(r, dict):
            continue
        tid = r.get("test_id", "")
        bsev = (r.get("issue_severity") or "LOW").lower()
        # Only genuine shell/code execution is a malware signal -> high. Everything else bandit
        # reports (weak hash, asserts, hardcoded test strings, ...) is code hygiene -> low, so it
        # never drives the verdict on its own.
        sev = "high" if (tid in BANDIT_SHELL_EXEC and bsev in ("high", "medium")) else "low"
        out.append(F(sev, f"bandit:{tid}", str(r.get("issue_text") or "")[:140],
                     os.path.relpath(str(r.get("filename") or root), root), r.get("line_number")))
    for e in data.get("errors") or []:
        if isinstance(e, dict):
            out.append(F("info", "not-analysed", f"bandit could not analyse this file: {str(e.get('reason'))[:120]}",
                         os.path.relpath(str(e.get("filename") or root), root)))
    return out


def run_bandit(root, files=None):
    """bandit on the given Python files of the component under root (default: its regular Python files up to
    BANDIT_MAX_BYTES). The files are named one by one instead of handing bandit the folder: it reads no link and no
    file too large for its memory (ADR-0037)."""
    if files is None:
        files = bandit_files(list(_iter_files(root, (".py",))), len(root))[0]
    if not files:
        return []
    if shutil.which("bandit") is None:
        return [F("info", "tool-missing", "bandit not installed - Python code scan skipped")]
    ini = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False) as f:
            f.write("[bandit]\n")
            ini = f.name
        p = subprocess.run(BANDIT_CMD + ["--ini", ini, "--"] + files, capture_output=True, text=True, timeout=240,
                           env=tool_env())
        return bandit_findings(p.returncode, p.stdout, root)
    except subprocess.TimeoutExpired:  # a real fault of the child process
        return [F("info", "tool-timeout", "bandit timed out")]
    except OSError as e:  # writing the ini file or starting the program failed: file system or OS fault
        return [F("info", "tool-error", f"bandit could not run ({type(e).__name__})")]
    finally:
        if ini and os.path.exists(ini):
            os.unlink(ini)


SAFE_REQ = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?(?:\[[A-Za-z0-9,._-]+\])?\s*(?:(?:==|>=|<=|~=|!=|<|>)\s*[A-Za-z0-9][A-Za-z0-9._*+!-]*\s*)*$")


def _sanitize_reqs(requirements):
    """Keep only simple PyPI specs; drop URL/VCS/editable/index entries so pip-audit cannot be
    tricked into fetching an attacker-controlled location while scanning a hostile manifest."""
    safe, dropped = [], []
    for r in requirements or []:
        if not isinstance(r, str):
            continue
        s = r.split(";")[0].strip()  # drop environment markers
        if not s:
            continue
        if s.startswith("-") or any(t in s for t in ("@", "://", "git+", "hg+", "svn+", "bzr+")) or not SAFE_REQ.match(s):
            dropped.append(r.strip())
        else:
            safe.append(s)
    return safe, dropped


# A requirement pip-audit can audit without resolving or installing anything (ADR-0021): exactly one "==" clause
# with a plain PEP 440 version, no wildcard. pip-audit's --disable-pip refuses anything else, so it is reported.
PINNED_REQ = re.compile(
    r"^(?P<name>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)(?:\[[A-Za-z0-9,._-]+\])?\s*==\s*"
    r"(?P<version>(?:\d+!)?\d+(?:\.\d+)*(?:(?:a|b|rc)\d+)?(?:\.post\d+)?(?:\.dev\d+)?(?:\+[a-z0-9]+(?:\.[a-z0-9]+)*)?)"
    r"\s*$", re.IGNORECASE)
PIP_AUDIT_CMD = ["pip-audit", "--no-deps", "--disable-pip", "--format", "json", "--progress-spinner", "off", "-r"]


def _canonical(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def split_pinned(requirements):
    """Sanitized requirement specs -> (pinned specs, names of the others) (pure). A spec is pinned when PINNED_REQ
    matches; the first pin of a package counts, a second pin of it with another version is listed as not pinned
    (pip-audit would refuse the whole file)."""
    pinned, versions, unpinned = [], {}, []
    for spec in requirements:
        m = PINNED_REQ.match(spec)
        name = m.group("name") if m else re.match(r"[A-Za-z0-9._-]+", spec).group()
        key = _canonical(name)
        if m and versions.get(key, m.group("version")) == m.group("version"):
            if key not in versions:
                versions[key] = m.group("version")
                pinned.append(spec)
        elif name not in unpinned:
            unpinned.append(name)
    return pinned, unpinned


def pip_audit_findings(returncode, stdout, audited):
    """Findings from one pip-audit run (pure), decided by exit code and JSON fields, never by its log text.
    pip-audit prints its JSON report and exits 0 (no vulnerability) or 1 (vulnerabilities found); any other outcome
    (exit 1 without a report: an error; another code) means nothing was audited. audited: the names passed in."""
    try:
        data = json.loads(stdout or "")
    except ValueError:  # parsing is the only check for a JSON report; no report is a fact in itself
        data = None
    deps = data.get("dependencies") if isinstance(data, dict) else None
    if returncode not in (0, 1) or not isinstance(deps, list):
        return [F("info", "tool-error", f"pip-audit failed (exit {returncode}, no report); not audited: "
                                        f"{', '.join(audited)}")]
    out, seen = [], set()
    for dep in deps:
        if not isinstance(dep, dict):
            continue
        name = f"{dep.get('name')} {dep.get('version') or ''}".strip()
        if dep.get("skip_reason"):
            out.append(F("info", "not-audited", f"Not audited by pip-audit: {name}: {str(dep['skip_reason'])[:120]}"))
        for v in dep.get("vulns") or []:
            if (name, v.get("id")) in seen:
                continue  # the vulnerability service can list the same advisory twice
            seen.add((name, v.get("id")))
            fix = ",".join(v.get("fix_versions") or []) or "no fix"
            out.append(F("high", "cve", f"{name}: {v.get('id')} (fix: {fix})"))
    return out


def run_pip_audit(requirements):
    """Audit the manifest's requirements for known vulnerabilities without installing anything (ADR-0007,
    ADR-0021): only specs pinned to an exact version go to pip-audit, with --no-deps --disable-pip, which queries
    the vulnerability service for name and version only. The others are reported as not audited."""
    out = []
    safe, dropped = _sanitize_reqs(requirements)
    for d in dropped:
        out.append(F("medium", "suspicious-requirement", f"Non-PyPI / unsafe requirement (not audited): {d[:120]}"))
    pinned, unpinned = split_pinned(safe)
    if unpinned:
        out.append(F("info", "not-audited", "Not audited by pip-audit: not pinned to an exact version: "
                                            + ", ".join(unpinned)[:200]))
    if not pinned:
        return out
    if shutil.which("pip-audit") is None:
        out.append(F("info", "tool-missing", "pip-audit not installed - dependency CVE scan skipped"))
        return out
    names = [PINNED_REQ.match(s).group("name") for s in pinned]
    req = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("\n".join(pinned) + "\n")
            req = f.name
        p = subprocess.run(PIP_AUDIT_CMD + [req], capture_output=True, text=True, timeout=240, env=tool_env())
        out += pip_audit_findings(p.returncode, p.stdout, names)
    except subprocess.TimeoutExpired:  # a real fault of the child process (network, service)
        out.append(F("info", "tool-timeout", f"pip-audit timed out; not audited: {', '.join(names)}"))
    except OSError as e:  # writing the temporary file or starting the program failed: file system or OS fault
        out.append(F("info", "tool-error", f"pip-audit could not run ({type(e).__name__}); not audited: "
                                           f"{', '.join(names)}"))
    finally:
        if req and os.path.exists(req):
            os.unlink(req)
    return out


# ---------------------------------------------------------------- Home Assistant's records and the catalog's lists
# Home Assistant's own records of the installed community repositories: the Marketplace's files (Home Assistant
# 2026.11 and later) first, then those of the HACS integration it replaced. The Marketplace takes the HACS files over
# and deletes them (ADR-0024).
REPOSITORY_RECORDS = ("marketplace.repositories", "hacs.repositories")
CRITICAL_RECORDS = ("marketplace.critical", "hacs.critical")
# The catalog's lists: repositories marked critical (the Marketplace uninstalls them) and repositories removed from it
CATALOG_LISTS = (("https://data-v2.hacs.xyz/critical/data.json", "marked critical in the catalog"),
                 ("https://data-v2.hacs.xyz/removed/data.json", "removed from the catalog"))
CATALOG_TTL = 6 * 60 * 60  # the Marketplace reads them every six hours as well
CATALOG_RETRY = 10 * 60  # after a failed fetch: try again, but not for every component
CATALOG_MAX_BYTES = 8 * 1024 * 1024
_CATALOG = {"at": None, "repos": {}, "unavailable": []}


def _storage_data(ha_storage, key):
    """The "data" of a Home Assistant storage file, or None when the file does not exist or cannot be read."""
    p = os.path.join(ha_storage, key)
    if not os.path.isfile(p):
        return None
    try:
        d = json.loads(_read(p))
    except ValueError:  # parsing is the only check for valid JSON
        return None
    return d.get("data") if isinstance(d, dict) and "data" in d else d


def installed_repositories(ha_storage="/homeassistant/.storage"):
    """The repository each installed folder came from, from Home Assistant's own records:
    {"integration": {domain: full_name}, "plugin": {folder under www/community: full_name}}. The first record file
    that exists counts."""
    out = {"integration": {}, "plugin": {}}
    for key in REPOSITORY_RECORDS:
        data = _storage_data(ha_storage, key)
        if data is None:
            continue
        entries = data.values() if isinstance(data, dict) else data if isinstance(data, list) else []
        for e in entries:
            if not (isinstance(e, dict) and isinstance(e.get("full_name"), str) and "/" in e["full_name"]):
                continue
            fn, category = e["full_name"], e.get("category")
            if e.get("domain") and category in (None, "", "integration"):
                out["integration"][str(e["domain"]).lower()] = fn
            elif category == "plugin":
                out["plugin"][str(e.get("directory") or fn.rsplit("/", 1)[-1]).lower()] = fn
        return out
    return out


def domain_to_fullname(ha_storage="/homeassistant/.storage"):
    return installed_repositories(ha_storage)["integration"]


def _fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "marketplace-guard"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read(CATALOG_MAX_BYTES).decode("utf-8", "replace"))


def _list_entries(d):
    return [it for it in (d if isinstance(d, list) else list(d.values()) if isinstance(d, dict) else [])
            if isinstance(it, dict)]


def _catalog(now):
    """The catalog's critical and removed lists, read at most every CATALOG_TTL seconds (CATALOG_RETRY after a
    failure). Keeps the lists that could not be read as a fact."""
    at = _CATALOG["at"]
    if at is not None and now - at < (CATALOG_RETRY if _CATALOG["unavailable"] else CATALOG_TTL):
        return _CATALOG
    repos, unavailable = {}, []
    for url, why in CATALOG_LISTS:
        try:
            entries = _list_entries(_fetch_json(url))
        except (OSError, ValueError, http.client.HTTPException):  # network boundary or a damaged answer: a real fault
            unavailable.append(url)
            continue
        for it in entries:
            fn = str(it.get("repository") or it.get("full_name") or "").lower()
            if fn:
                repos.setdefault(fn, f"{why}: {it.get('reason') or it.get('removal_type') or 'no reason given'}")
    _CATALOG.update(at=now, repos=repos, unavailable=unavailable)
    return _CATALOG


def load_critical(ha_storage="/homeassistant/.storage", fetch=True, now=None):
    """Repositories known to be critical or removed, as ({full_name lower: reason}, [lists that could not be read]):
    Home Assistant's own record of critical repositories, then the catalog's lists."""
    repos = {}
    for key in CRITICAL_RECORDS:
        data = _storage_data(ha_storage, key)
        if data is None:
            continue
        for it in _list_entries(data):
            fn = str(it.get("repository") or it.get("full_name") or "").lower()
            if fn:
                repos[fn] = f"marked critical in Home Assistant: {it.get('reason') or 'no reason given'}"
        break
    unavailable = []
    if fetch:
        cat = _catalog(time.time() if now is None else now)
        for fn, why in cat["repos"].items():
            repos.setdefault(fn, why)
        unavailable = list(cat["unavailable"])
    return repos, unavailable


GH_RE = re.compile(r"github\.com[:/]+([A-Za-z0-9._\-]+)/([A-Za-z0-9._\-]+)")


def github_repo_name(m):
    """(owner, repo) from a match of owner and repository name, or None (pure). Only a trailing ".git" is dropped
    (a repository may be called "foo.gitlab"), and "." and ".." are no names."""
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo or {owner, repo} & {".", ".."}:
        return None
    return owner, repo


def github_repo(text):
    """(owner, repo) of the first github.com URL in text, or None (pure)."""
    return github_repo_name(GH_RE.search(text or ""))


def _fullname_from_manifest(manifest):
    if not isinstance(manifest, dict):
        return None
    for k in ("issue_tracker", "documentation"):
        v = manifest.get(k)
        repo = github_repo(v) if isinstance(v, str) else None
        if repo:
            return "/".join(repo)
    return None


# Where a repository name may come from to count as the component's own (ADR-0031): Home Assistant's records, or
# given by the caller (the operator's pre-check request). A manifest is written by the component's author.
TRUSTED_NAME_SOURCES = ("records", "given")


def _label_key(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


# ---------------------------------------------------------------- main entry point
def scan_component(path, full_name=None, ha_storage="/homeassistant/.storage",
                   do_python=True, do_js=True, do_bandit=True, do_pip_audit=True, fetch_critical=True):
    findings = []
    rootlen = len(path)
    pyfiles = list(_iter_files(path, (".py",)))
    jsfiles = list(_iter_files(path, JS_EXTS))
    for rel, kind, target in special_entries(path):
        findings.append(F(SPECIAL_SEVERITY[kind], kind, SPECIAL_MSG[kind] + (f" ({target})" if target else ""), rel))

    manifest = None
    for mf in _iter_files(path, ("manifest.json",)):
        try:
            manifest = json.loads(_read(mf))
            break
        except Exception:
            pass

    # Where the repository name comes from is kept as a fact: Home Assistant's records are trustworthy, a manifest is
    # written by the component's author (ADR-0007).
    full_name_source = "given" if full_name else None
    if not full_name:
        base = os.path.basename(path.rstrip("/\\")).lower()
        recs = installed_repositories(ha_storage)
        kinds = ("plugin", "integration") if os.path.basename(os.path.dirname(path.rstrip("/\\"))) == "community" \
            else ("integration", "plugin")
        full_name = next((recs[k][base] for k in kinds if base in recs[k]), None)
        full_name_source = "records" if full_name else None
        if not full_name:
            full_name = _fullname_from_manifest(manifest)
            full_name_source = "manifest" if full_name else None

    crit, unavailable = load_critical(ha_storage, fetch=fetch_critical)
    if full_name and full_name.lower() in crit:
        findings.append(F("critical", "hacs-critical",
                          f"Repository {full_name} is {crit[full_name.lower()]}"))
    for url in unavailable:
        findings.append(F("info", "catalog-unavailable", f"Could not read the catalog list {url}; not checked against it"))

    if do_python:
        # One file can run another file's docstring (exec(other.__doc__)): if any file reads docstrings, every file's
        # docstrings are scanned as code (ADR-0035).
        docstrings_are_code = any(reads_docstrings(pf) for pf in pyfiles)
        for pf in pyfiles:
            findings += scan_python_file(pf, rootlen, docstrings_are_code)
        for rel, kind in compiled_code(path):
            findings.append(F("high", kind, COMPILED_MSG[kind], rel))
    if do_bandit and pyfiles:
        small, skipped = bandit_files(pyfiles, rootlen)
        findings += skipped + run_bandit(path, small)
    if do_pip_audit and manifest:
        findings += run_pip_audit(manifest.get("requirements"))
    if do_js:
        for jf in jsfiles:
            findings += scan_js_file(jf, rootlen)
        findings += precompressed_findings(path)
    if do_python or do_js:
        # JSON is data, but a manifest or a translation can hide what it says the same way (ADR-0018)
        for jf in _iter_files(path, (".json",)):
            findings += unicode_findings(_read(jf), jf[rootlen:].lstrip("/\\"), "json")

    # Re-label outbound hosts that have the repository owner as one of their labels -> the component's own backend
    # (ADR-0005). Only with a name from Home Assistant's records or the pre-check, and only a whole label: a short or
    # chosen owner name must not turn every host into "own backend" (ADR-0031).
    owner_key = _label_key((full_name or "").split("/")[0]) if full_name_source in TRUSTED_NAME_SOURCES else ""
    if owner_key:
        for f in findings:
            if f.get("code") == "outbound-host":
                host = f["msg"].rsplit(": ", 1)[-1].strip().lower()
                if owner_key in {_label_key(label) for label in host.split(".")}:
                    f["code"] = "vendor-host"
                    f["msg"] = f"Outbound host matches repo owner (own backend): {host}"

    sev = max([SEV_ORDER[f["severity"]] for f in findings], default=0)
    counts = {}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    return {
        "path": path, "name": os.path.basename(path.rstrip("/")),
        "full_name": full_name, "full_name_source": full_name_source, "verdict": SEV_NAMES[sev],
        "counts": counts, "py": len(pyfiles), "js": len(jsfiles),
        "requirements": (manifest or {}).get("requirements") or [],
        "findings": findings,
    }


def render_report(res):
    lines = []
    lines.append(f"Marketplace Guard report: {res['name']}")
    if res.get("full_name"):
        lines.append(f"Repository: {res['full_name']}")
    lines.append(f"Verdict: {res['verdict'].upper()}   (py={res['py']} js={res['js']})")
    if res.get("requirements"):
        lines.append(f"Requirements: {', '.join(res['requirements'])}")
    c = res.get("counts", {})
    if c:
        lines.append("Findings: " + ", ".join(f"{k}={v}" for k, v in sorted(c.items(), key=lambda x: -SEV_ORDER[x[0]])))
    lines.append("-" * 60)
    order = sorted(res["findings"], key=lambda f: -SEV_ORDER[f["severity"]])
    for f in order[:80]:
        loc = f.get("file") or ""
        if f.get("line"):
            loc += f":{f['line']}"
        lines.append(f"[{f['severity'].upper():8}] {f['code']:18} {f['msg']}  {loc}")
    if len(order) > 80:
        lines.append(f"... (+{len(order) - 80} more)")
    if res.get("ai_detail"):
        lines.append("")
        lines.append("AI assessment:")
        lines.append(res["ai_detail"])
    return "\n".join(lines)
