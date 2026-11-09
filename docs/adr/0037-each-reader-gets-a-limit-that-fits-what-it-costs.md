---
status: accepted
date: 2026-11-07
decision-makers: maintainer
---

# Each reader gets a limit that fits what it costs

Supersedes [ADR-0027](0027-only-regular-files-are-read-within-a-size-limit.md).

## Context and Problem Statement

ADR-0027 reads files up to 16 MiB and rates a larger Python file `high` (`too-large`), on the assumption that Python
code is never that large. Published integrations do ship larger Python modules of nothing but constants, such as
base64 images. One of 26 MiB makes its integration `high` for that file alone, although Python's tokenizer finds only
one import and 89 constants in all of it.

Measured in the add-on image (amd64, Python 3.13), one file each, peak memory of the process:

| File | Line rules, first 16 MiB | Line rules, whole file | bandit |
|---|---|---|---|
| the 26 MiB data module | 1.5 s, 148 MiB | 2.4 s, 209 MiB | 0.3 s |
| 64 MiB of generated code | 3.7 s, 145 MiB | 14.6 s, 508 MiB | 148 s, 9.9 GB |
| 64 MiB of generated data | 1.4 s, 117 MiB | 5.5 s, 406 MiB | 1.1 s |

bandit on code alone: 1 MiB 192 MiB, 2 MiB 354 MiB, 4 MiB 670 MiB, 8 MiB 1.3 GB. Real code is far smaller: in a survey
of installed components no file of code and no script reached 1 MiB.

So the 16 MiB limit bounds the line rules well and never cuts real code, but it calls data unread code; and bandit,
which reads every file whole, had no limit at all: one component with 64 MiB of code took ten gigabytes, enough to
exhaust the memory of a Home Assistant host.

## Decision Drivers

* A component cannot make its own scan endless or slow, and cannot exhaust the memory of the add-on or the host.
* What is not analysed is reported; a verdict speaks about code, not about images.
* Nothing outside a component is read on its behalf.

## Considered Options

* Keep ADR-0027 as it is.
* Read every file whole.
* Raise the limit.
* Keep the limit for the line rules; read a larger Python file once more with the tokenizer, line by line and up to a
  second limit, to tell data from code; give bandit only files whose analysis fits in bounded memory.

## Decision Outcome

Chosen option: the fourth option.

Unchanged from ADR-0027: only regular files are opened (`open_regular()`, without following links and without
blocking), links and special files are reported by `special_entries()`, every rule stays linear (line numbers by
bisect, repetitions bounded to 500 characters), and state entries carry the hash version.

Changed:

* The line rules read up to `MAX_SCAN_BYTES` (16 MiB), as before.
* A larger Python file is read by `literal_data_only()`: Python's tokenizer, fed line by line, up to
  `DATA_CHECK_MAX_BYTES` (64 MiB), with a plain source encoding. A file of nothing but imports, constants of literals
  (strings, numbers, `True`/`False`/`None`, lists, tuples, dicts of them, with or without a type annotation) and
  docstrings is literal data: the finding is `info` `large-data`. Any other statement, a larger file, an unusual
  encoding or text the tokenizer cannot read keeps `too-large` `high`, naming the reason and the line.
* bandit gets the component's regular Python files up to `BANDIT_MAX_BYTES` (2 MiB), named one by one after `--`,
  instead of the folder. A larger file is `info` `not-analysed` (the line rules read it).
* JavaScript is unchanged: above 16 MiB `too-large` is `medium`.

Keeping ADR-0027 leaves data rated `high` and bandit unbounded. Reading every file whole needs about eight times the
file in memory for the line rules and lets bandit take ten gigabytes. A higher limit is as arbitrary as the old one:
data modules can be of any size, and the memory grows with the limit.

### Consequences

* Good, because a data module is `info`, and the verdict of its integration follows its code.
* Good, because bandit's memory stays bounded (about 350 MiB for a 2 MiB file): the component with 64 MiB of code is
  `high` after 3.7 s with 152 MiB, instead of 148 s and 9.9 GB.
* Good, because bandit is handed regular files only and never follows a link.
* Bad, because Python files between 2 and 16 MiB are not analysed by bandit. The line rules read them, and bandit's
  only `high` findings (shell and code execution) are what the rules look for as well; the gap is reported as `info`.
* Bad, because a data module can hold a payload that another file runs (`exec(module.CONSTANT)`). The `exec` is a
  finding in that file and the line rules still read the first 16 MiB of the data; the same holds for docstrings
  ([ADR-0035](0035-docstrings-are-read-as-text-unless-the-code-reads-them.md)).
* Bad, because a large Python file is read once more, up to 64 MiB (4 s for the 26 MiB module).
* Bad, as before: a rule only matches parts within 500 characters of each other on a line.

### Confirmation

`TestLargeFiles`, `TestBoundedScanning` and `TestBandit` in `marketplace_guard/tests/test_marketplace_guard.py`: data
with imports, annotations, lists and dicts is data; a call, a name, an f-string, an attribute, a subscript or an
augmented assignment is code, with its line; a file beyond the check limit (also one endless line), an unusual encoding
or broken text is not data; the finding for a large file is `info` for data and `high` for code; bandit is handed only
files up to its limit, named after `--`, and a larger one is reported. A 64 MiB file of code and the 26 MiB data module
were scanned in the image with the numbers above.

Accepted by the maintainer on 2026-11-08; implemented in pull request #38.
