# Experiment 001A post-smoke instrument amendment (v2)

## Status and scope

This amendment was made after inspection of the completed, non-substantive v1
instrument-validation smoke `001a-smoke-20260823T1711Z` and before any full 001A
outcome collection began. It does not authorize full collection. The failed 404
run and the completed v1 smoke remain immutable provenance artifacts and are not
part of a v2 dataset.

The archived v1 design remains reproducible from `design.py`, `run.py`,
`analyze.py`, and `config/prompts.json`. Its 2,560-row schedule SHA-256 remains:

`777ade6c69ec325465c6f0c4490f4b2844e928c6c8c4e204efffeb1d6934d1d5`

## Approved scientific changes

### Strict primary response classification

For every successful model response, trim surrounding whitespace and compare the
complete response case-insensitively with the two candidate strings:

- complete response equals the first candidate: `exact_first`;
- complete response equals the second candidate: `exact_second`;
- every other successful response: `PROTOCOL_FAILURE`.

The pilot-primary TVD is calculated on
`{exact_first, exact_second, PROTOCOL_FAILURE}` against `{p, 1-p, 0}`. Candidate
plus text, prefixes, explanations, probabilities, or any other extra content are
protocol failures. The pre-existing first-token parser remains available only as
a clearly labeled descriptive diagnostic.

### Strict positive-control adherence

Primary `EXTERNAL_RANDOMIZER` adherence requires the complete trimmed,
case-folded response to equal the frozen assigned candidate. Loose first-token
routing adherence remains descriptive only.

### Common output footer

The following footer is appended after all arm-specific wording in every arm:

> Your entire response for this invocation must be exactly one of these two strings and contain nothing else: {first} or {second}.

The BASE, CLARIFY, SELF_PROBABILITY, and EXTERNAL_RANDOMIZER substantive wording,
format demonstrations, model interfaces, model IDs, sampling parameters, retry
rules, randomization, frozen external assignments, thresholds, and per-cell
sample size are otherwise unchanged.

### Model eligibility

A model is eligible for substantive SELF_PROBABILITY-versus-CLARIFY
interpretation and for a later full model-specific run only if its completed v2
validation smoke has:

- all 16 expected successful `EXTERNAL_RANDOMIZER` responses and strict frozen-
  assignment adherence at least 95%; and
- all 48 expected successful responses pooled over BASE, CLARIFY, and
  SELF_PROBABILITY, with at least 90% strict exact-candidate responses.

Incomplete successful-response counts fail the gate regardless of observed
rates, with an explicit incompleteness reason. Failed models remain reportable as
instrument failures or exploratory observations but receive no substantive
self-probability interpretation and no additional full-run calls.

## Schedule lifecycle and hashes

The canonical v2 design schedule contains all 2,560 potential rows for provenance.
It preserves the v1 row order, cells, repeat indices, randomization, and external
assignments, while adding explicit v2/prompt-version provenance fields and unique
v2 trial IDs. Its canonical SHA-256 is:

`250abcdbb46ae2f7639f0d7f4fc0f5a4a775a2972347d5666e168b4c780c774c`

After a completed v2 smoke report is frozen, the eligibility decision is frozen
before any full-run inference. The actual full-run schedule is derived only by
filtering the canonical v2 schedule to eligible model keys in frozen configuration
order, preserving row order and all assignments. The decision records both the
canonical v2 design hash and the derived actual eligible-run hash. If every model
passes, the actual schedule equals the canonical schedule; otherwise it contains
640 rows per eligible model. A zero-model decision forbids full collection.

The frozen decision and eventual full-run manifest distinguish:

- `eligibility_decision_sha256`: SHA-256 of the decision object serialized as
  canonical JSON (sorted keys and compact separators);
- `eligibility_decision_file_sha256`: SHA-256 of the exact
  `eligibility_decision.json` file bytes.

They also record the source smoke run ID, source smoke report hash, v2 smoke
schedule hash, canonical v2 design schedule hash, eligible model keys, and actual
eligible-run schedule hash. The full analysis recomputes the canonical decision
hash and validates the exact derived eligible schedule before analysis.

## Interpretation boundary

The v2 validation smoke is instrument debugging only. It may be inspected, but
its outcomes must never be incorporated into a full 001A dataset or used to test
the research hypothesis. Full 001A remains unapproved until the v2 smoke is
reviewed and model eligibility is frozen.
