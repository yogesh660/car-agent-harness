# 0004 - How the agent is evaluated

Status: accepted (2026-10)

## Context

"The answers look fine" doesn't survive a prompt change. We need numbers that move when the
agent gets better or worse, are cheap enough to run on every relevant PR, and catch the worst
failure for a marketplace: confidently stating a price or listing that doesn't exist.

## Decision

Three layers, from cheapest to most expensive:

1. **Tool-call scoring** (`evals/scoring.py`), every case. Did the agent call the expected tools
   with the expected arguments? Deterministic, so it is the main pass/fail signal. Defaults,
   make aliases and German city names count as matches; extra arguments are fine.
2. **Number grounding** (`evals/grounding.py`), every case. Every number in the answer must
   come from a tool result or the question (rounding and differences allowed). No model
   needed. Tracked as `grounded_rate`, gated like the pass rate.
3. **LLM-as-judge** (`evals/judge.py`), opt-in with `--judge`. Checks every other claim
   (verdicts, which car is cheapest, invented features). Judge failures to produce a verdict
   are reported separately, not counted against the agent.

Cases are grouped by category (search, normalisation, price, compare, multi-step, not found,
vague, out of scope), so a regression points at a capability, not just a number. A smoke
subset of about 13 cases runs on PRs that touch the agent; the full set runs nightly.

`evals/baseline.json` holds the accepted scores per suite. The gate fails when `pass_rate` or
`grounded_rate` falls more than 5 points below it. Every run can be logged to MLflow with
hashes of the prompt, the tool schemas and the case file, so runs are comparable.

## Consequences

- Tool-call scoring can fail an answer that is still helpful (a different but valid filter).
  Accepted: it's stable, and failures are easy to read.
- The grounding check is conservative and will flag some legitimate derived numbers. It is a
  rate to watch, not a hard per-case failure.
- Eval cases reference seeded listing ids; `tests/test_harness.py` fails if the data changes
  under them.
- The CI eval uses Ollama on the runner's CPU when no API key is configured. Free, but slow and
  a weaker model than a hosted one, so its baseline is lower; the gate compares like with like.
