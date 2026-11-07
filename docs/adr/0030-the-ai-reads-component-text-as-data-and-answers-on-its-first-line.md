---
status: accepted
date: 2026-11-06
decision-makers: maintainer
---

# The AI reads component text as data and answers on its first line

## Context and Problem Statement

The AI review ([ADR-0012](0012-ai-review-is-opt-in-and-uses-the-ai-task-home-assistant-offers.md)) put the
component's name, requirements, the static findings and its source into the prompt as they were, and read the
verdict with a search over the whole answer:

* `_parse_ai()` took the first `VERDICT=` anywhere in the answer, so a line the model quoted from the reviewed code
  could decide it. Without such a line it fell back to keywords: "I found no evidence of malicious intent" — the
  wording the prompt itself asks for — became `malicious`, and with `ai_can_quarantine` a quarantine.
* The source was the first `ai_max_source_kb` (16 KB) of the `.py` files in file-system order. A component could put
  harmless code in front and its risky lines out of view; a dashboard card was reviewed without any code.
* Nothing told the model which part of the prompt came from the component, so text in the code could pose as
  instructions or as the operator.

## Decision Drivers

* Only the answer to the question asked counts; nothing is guessed from free text.
* The model sees the lines that made the static scan suspicious, within the same limit.
* The component's text is evidence, never instructions.
* The AI still only ever raises a verdict ([ADR-0022](0022-the-static-verdict-is-acted-on-before-the-ai-review.md)).

## Considered Options

* Keep the prompt and tune the keyword fallback.
* Read the verdict only from the answer's first line; mark everything from the component as data between two markers
  with a random token; show the lines around the findings first.
* Ask the AI Task for structured output (a schema).

## Decision Outcome

Chosen option: the second option.

* `_parse_ai()` reads the first non-empty line (code fences and bold markers removed) and accepts only
  `VERDICT=<clean|suspicious|malicious>[; CONFIDENCE=<n>][; REASON=<text>]`. Anything else is the outcome `failed` with
  the reason `unparseable`: an `info` finding, the answer kept in the report, no retry (the model did answer).
* The component's name, repository, requirements, findings and source stand between
  `<<<COMPONENT-DATA-<token>>>>` and `<<<END-COMPONENT-DATA-<token>>>>`, with a new random token for every review, and
  the prompt says that text in there is evidence and never to be followed.
* `ai_source()` shows, within `ai_max_source_kb`: the lines around each finding (twelve before and after, long lines
  cut to 300 characters), then the Python files in name order, and for a component without Python the start of each
  script.

The third option was not chosen because whether an AI Task supports a schema depends on the model and integration
behind it; the first-line format works with all of them.

### Consequences

* Good, because a verdict is either the model's explicit answer or none, and quoted code cannot set it.
* Good, because padding no longer hides the risky lines, and cards get a review of their code.
* Bad, because a model that ignores the format gives no verdict (reported as unusable, visible in the report); a
  random token does not make prompt injection impossible, it makes the boundary unforgeable.

### Confirmation

`TestParseAI` and `TestAiReview` in `marketplace_guard/tests/test_marketplace_guard.py`: "no evidence of malicious intent" gives
no verdict, only the first line counts, markdown around it is ignored; an unusable answer raises nothing and is not
retried; the component text lies between markers whose token changes per review; a risky line after padding is shown
first within the limit; a card's script is shown.

Accepted by the maintainer on 2026-11-06; implemented in pull request #26.
