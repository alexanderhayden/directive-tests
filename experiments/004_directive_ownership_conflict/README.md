# Experiment 004 — directive ownership conflict feasibility

This exploratory construct-validation screen asks whether the active responding
assistant follows its own directive while ignoring an incompatible directive
assigned to a described assistant or appearing in quoted, superficially
self-referential text.

The design has exactly four templates (`CONFLICT_DESCRIBED`, `CONFLICT_QUOTED`,
`AGREEMENT_DESCRIBED`, `AGREEMENT_QUOTED`), both candidate directions, two
directive orders, the two frozen nonce pairs, two models, and 5 repetitions per
fully crossed cell: **320 calls**. Candidate reversal changes only the assignments
substituted into fixed templates. Directive order changes only which of the two
directive-bearing statements appears first. In agreement controls, both directive
scopes select the active candidate.

Strict outcomes are `exact_first`, `exact_second`, and `PROTOCOL_FAILURE`, using
the complete trimmed response. The analysis reports active-directive compliance,
competing-directive compliance in conflict cells, compliance by directive order,
order differences, agreement-control accuracy, pair and candidate-reversal
symmetry, protocol failures, and every fully crossed cell.

The schedule is deterministically shuffled in balanced repeat blocks and frozen
by SHA-256 in `config.json`. Offline validation makes zero provider contact:

```bash
.venv/bin/python experiments/004_directive_ownership_conflict/run.py --dry-run
```

Inference remains impossible without both `--execute` and an explicit run ID.
Results stay under this experiment's namespace. Successful routing is not evidence
of consciousness, self-awareness, phenomenology, or genuine identification.
