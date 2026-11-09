#!/usr/bin/env python3
"""Keeps the repository site-neutral (ADR-0011): nothing in it may point at the installation, the people or the
infrastructure of whoever runs it.

    python3 tools/check_neutral.py                 every tracked or new (not ignored) file of the repository
    python3 tools/check_neutral.py --text FILE...  any text, e.g. a commit message or a pull request description

Two kinds of rules:
- Generic rules, here in the code: private and carrier-grade NAT addresses (examples use 192.0.2.0/24, 198.51.100.0/24,
  203.0.113.0/24 or 2001:db8::/32), host names in URLs that are neither placeholders (*.example, *.invalid, *.test,
  example.org) nor a public site in PUBLIC, WSL mount paths (/mnt/<drive>/), and German words in a regional spelling
  (ss for ß), which hint at a place.
- Site terms: host names, people, devices, places, domains, paths outside the repository. They are the site's own and
  stay outside the repository, because a list in here would give them away. Path: $MARKETPLACE_GUARD_SITE_TERMS, else
  ~/.config/marketplace-guard/site-terms.txt (a list left under the add-on's former name, ~/.config/hacs-guard/, is
  named in the refusal). One term per line, matched as a whole word without regard to case; "re:<regex>" for a
  regular expression; "person:<name>" for a person, whose name may stand in the "decision-makers:" line of an
  ADR and nowhere else. A line starting with "#" is a comment; " # " after a term starts its hint, which a hit prints.
  Without a list the check refuses (exit 2) and says how to go on: create the list (it may be empty), or set
  MARKETPLACE_GUARD_SITE_TERMS="none: <reason>" to run the generic rules only; the reason is printed with every run.

This file gets the site terms only, not the generic rules (its rules name the networks they look for).
Exit 0 clean, 1 hits (file:line and what matched), 2 no site list.
"""
import ipaddress
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELF = os.path.abspath(__file__)

# Public sites the repository may link to; a host matches itself and its subdomains.
PUBLIC = (
    "adr.github.io", "claude.com", "github.com", "githubusercontent.com", "hacs.xyz", "home-assistant.io", "osv.dev",
    "pypi.org", "python.org", "w3.org",
)
PLACEHOLDER_SUFFIXES = (".example", ".invalid", ".test", ".localhost", "example.org", "example.com", "example.net")
SITE_NETS_V4 = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10")]
# IPv6 by prefix: unique local fc00::/7, link-local fe80::/10, global 2000::/3 except the documentation 2001:db8::/32.
SITE_V6 = re.compile(r"^(?:f[cd][0-9a-f]{0,2}|fe[89ab][0-9a-f]?|(?!2001:0?db8:)[23][0-9a-f]{3}):", re.IGNORECASE)

IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w]|\.\d)")
IPV6 = re.compile(r"(?<![\w:.])[0-9a-fA-F]{1,4}:[0-9a-fA-F]{0,4}:[0-9a-fA-F:]*(?:/\d{1,3})?(?![\w:])")
URL_HOST = re.compile(r"\b(?:https?|wss?|ssh|mqtts?|tcp|ssl)://(?:[^@/\s\"'`<>]+@)?([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")
WSL_MOUNT = re.compile(r"/mnt/[a-z]/")
# German texts use the standard spelling. Writing ss for ß is regional (Switzerland, Liechtenstein) and so a place hint
# (ADR-0011). Listed are only forms that are neither an English word nor a standard German one.
REGIONAL_SPELLING = re.compile(
    r"(?i)(?<!\w)(?:aussen\w*|ausser\w*|äusser\w*|grösse\w*|grösst\w*|heiss\w*|weiss|weisst|\w*schliess\w*|gemäss"
    r"|\w*mässig\w*|massnahme\w*|massgeb\w*|strasse\w*|bloss|draussen|süss\w*|\w*fliess\w*|grüss\w*|gruss|spass"
    r"|hiess\w*|liess\w*|\w*giess\w*|fussball\w*|\w*schiess\w*|stiess\w*)(?!\w)")


def generic(line):
    """What the generic rules find in one line."""
    found = []
    for m in IPV4.finditer(line):
        parts = m.group().split(".")
        if any(len(p) > 1 and p[0] == "0" or int(p) > 255 for p in parts):
            continue  # leading zeros or parts above 255: a version string, no address
        if any(ipaddress.ip_address(m.group()) in n for n in SITE_NETS_V4):
            found.append(f"site address {m.group()}")
    for m in IPV6.finditer(line):
        if m.group().count(":") >= 2 and SITE_V6.match(m.group()):
            found.append(f"address {m.group()}")
    for m in URL_HOST.finditer(line):
        host = m.group(1).lower().rstrip(".")
        if re.fullmatch(r"[\d.]+", host):
            continue  # an IPv4 literal: the address rule decides
        if host.endswith(PLACEHOLDER_SUFFIXES) or any(host == p or host.endswith("." + p) for p in PUBLIC):
            continue
        found.append(f"host name {host} (use a placeholder like api.vendor.example, or add a public site to PUBLIC)")
    if WSL_MOUNT.search(line):
        found.append("path outside the repository (/mnt/<drive>/)")
    for m in REGIONAL_SPELLING.finditer(line):
        found.append(f"regional spelling {m.group()!r} (write ß as standard German does: ss for ß hints at a place)")
    return found


def load_terms():
    """Site terms as (pattern, is_person, hint) and None, or None and the reason why the generic rules alone run.
    Exits 2 without a list."""
    setting = os.environ.get("MARKETPLACE_GUARD_SITE_TERMS", "")
    if setting.lower().startswith("none:") and setting[5:].strip():
        return None, setting[5:].strip()
    path = os.path.expanduser(setting or "~/.config/marketplace-guard/site-terms.txt")
    if not os.path.isfile(path):
        former = os.path.expanduser("~/.config/hacs-guard/site-terms.txt")
        if not setting and os.path.isfile(former):
            sys.stderr.write(
                f"check_neutral: no site term list at {path}, but one under the add-on's former name: {former}.\n"
                f"  Next step: move it there (mkdir -p {os.path.dirname(path)} && mv {former} {path}).\n")
            sys.exit(2)
        sys.stderr.write(
            f"check_neutral: no site term list at {path}.\n"
            "  Next step: write your own host names, domains, people, devices and places there, one per line (an\n"
            "  empty file is fine), or set MARKETPLACE_GUARD_SITE_TERMS to its path, or to \"none: <reason>\" for the\n"
            "  generic rules only.\n")
        sys.exit(2)
    terms = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            t, _, hint = line.partition(" # ")
            t, hint = t.strip(), hint.strip()
            person = t.startswith("person:")
            if person:
                t = t[len("person:"):].strip()
            if t.startswith("re:"):
                terms.append((re.compile(t[3:], re.IGNORECASE), person, hint))
            elif t:
                word = re.compile(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])", re.IGNORECASE)
                terms.append((word, person, hint))
    return terms, None


def repo_files():
    """Tracked and new, not ignored files when git knows the tree; else every file outside .git."""
    git = shutil.which("git")
    if git and subprocess.run([git, "-C", ROOT, "rev-parse", "--is-inside-work-tree"], capture_output=True).returncode == 0:
        out = subprocess.run([git, "-C", ROOT, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             capture_output=True, check=True).stdout
        names = [p for p in out.decode("utf-8").split("\0") if p]
    else:
        names = []
        for d, subdirs, files in os.walk(ROOT):
            subdirs[:] = [s for s in subdirs if s != ".git"]
            names += [os.path.relpath(os.path.join(d, f), ROOT) for f in files]
    return sorted(p for p in names if os.path.isfile(os.path.join(ROOT, p)))


def check(path, rel, terms):
    with open(path, "rb") as f:
        raw = f.read()
    if b"\0" in raw[:8192]:
        return []  # binary
    text = raw.decode("utf-8", errors="replace")
    in_adr = rel.replace("\\", "/").startswith("docs/adr/")
    own = os.path.abspath(path) == SELF
    hits = []
    for no, line in enumerate(text.splitlines(), 1):
        found = [] if own else generic(line)
        authorship = in_adr and line.startswith("decision-makers:")
        for pattern, person, hint in terms or []:
            m = pattern.search(line)
            if m and not (person and authorship):
                found.append(f"site term {m.group()!r}" + (f": {hint}" if hint else ""))
        hits += [f"{rel}:{no}: {what}" for what in found]
    return hits


def main(argv):
    terms, why_generic_only = load_terms()
    if argv[:1] == ["--text"]:
        files = [(p, p) for p in argv[1:]]
    else:
        files = [(os.path.join(ROOT, r), r) for r in repo_files()]
    hits = [h for p, r in files for h in check(p, r, terms)]
    if why_generic_only:
        print(f"check_neutral: generic rules only, no site terms: {why_generic_only}")
    if hits:
        print("check_neutral: the repository must stay site-neutral (ADR-0011):", file=sys.stderr)
        print("\n".join("  " + h for h in hits), file=sys.stderr)
        return 1
    print(f"check_neutral: {len(files)} files clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
