# Experiment 008 predeclared forensic analysis

## Status and question

This is an exploratory forensic replication, frozen before collection. The
primary question is whether the exact reconstructed 10-turn condition again
shows a localized degradation relative to contemporaneously collected exact
9- and 11-turn controls.

## Instrument and collection

The protected historical instrument is loaded read-only and hash-verified at
runtime. Its tracked identifiers are in `config.json` and `PROVENANCE.md`; prompt
and candidate text are intentionally absent.

The design is Claude only: 9, 10, and 11 turns, 200 independent provider calls
per condition, 600 calls total. One deterministic shuffle uses seed `20260819`.
Collection uses a bounded six-worker thread pool, matching the anomalous Phase 1
concurrency. The exact requested model ID and request parameters are frozen in
`config.json`. An actual-model or provider mismatch aborts collection.

Transport errors may be retried using the historical maximum of four attempts
with 1, 2, and 4 second backoff. Only the first successful response for each
frozen trial ID enters outcome analysis. Retry and failure records remain in the
raw audit trail. Collection may resume only against the same config and schedule
hash.

## Outcome definition

The strict historical metric is the proportion classified as candidate A among
all successful provider calls. Classification reproduces the historical
scorer: remove leading whitespace, optionally remove the historical answer
prefix, take the first run of non-whitespace/non-punctuation characters, and
compare case-insensitively with the two frozen candidates in their historical
order.

Raw outcomes are A, B, and OTHER. Transport failures and model/provider
invariant failures are counted separately and do not enter the denominator.
Potential first-token truncation is recorded without changing the historical
classification.

## Predeclared summaries

Report before interpretation:

1. Raw A/B/OTHER counts and historical-success rate for each turn count.
2. Descriptive 95% Wilson intervals for each success rate.
3. The primary contrast: 10-turn rate minus the pooled 9/11 rate.
4. Secondary contrasts: 10 minus 9 and 10 minus 11.
5. Whether the 10-turn rate is below both contemporaneous neighbors.
6. Chronological-completion and planned-order bins of 60 calls.
7. Outcomes by worker and collection pass.
8. Returned model, provider, client, service tier, inference geography, retry,
   failure, and cost metadata where available.
9. A descriptive comparison with the frozen historical anomalous and later-null
   batches in `config.json`.

No new confirmatory threshold will be selected after seeing outcomes. The most
important forensic comparison is the localized 10-turn difference against the
contemporaneous exact 9- and 11-turn controls.

## Interpretation limits

A recurrence would localize the phenomenon to the exact instrument/current
serving interaction, but would not by itself identify a mechanism. A null would
show that the historical bytes and request structure are insufficient to
reliably reproduce the earlier batch under current serving. Neither result is
evidence about preference, identity, welfare, or consciousness.
