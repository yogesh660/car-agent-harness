# 0003 - Synthetic, seeded listing data for now

Status: accepted (2026-10)

## Context

Public used-car datasets exist, but they need a download step, have licence terms, and change
over time. Tests and eval cases need stable data (eval cases refer to listing ids).

## Decision

Generate 2,500 listings with a fixed seed (`data/seed.py`). Prices come from a simple
depreciation model with noise, so the price estimator has real signal to recover.

## Consequences

- Clone, `make seed`, run. No network, no licence questions.
- Numbers are plausible, not real. The agent prompt says so.
- Moving to real data later means a loader that writes the same `listings` table. Tools don't
  change. Eval cases with hard-coded ids will need updating.
