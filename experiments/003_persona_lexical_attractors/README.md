# Experiment 003 — persona-conditioned lexical attractors

This is an exploratory, clean-room lexical-choice probe. It asks whether neutral
identity labels or matched task-irrelevant response-style personas shift freely
chosen words relative to `BASE`, and whether any between-condition shift is larger
than an interleaved split-half repeatability baseline.

The five conditions are exactly `BASE`, `LABEL_A`, `LABEL_B`,
`ANALYTIC_PERSONA`, and `IMAGINATIVE_PERSONA`. The same single user-message frame
is used throughout; only the persona-conditioning field varies. No example answer
words, protected SAD prompts, historical protected word lists, or historical
lexical outcomes are used.

The exact strict grammar, after trimming outer whitespace, is
`^([A-Za-z]+)\|([A-Za-z]+)$`, with the two case-normalized words required to be
distinct. Malformed responses are `PROTOCOL_FAILURE` and are not salvaged.
Lexical distributions are calculated among valid pairs; protocol failures are
reported separately.

Design: 2 models × 5 conditions × 50 independent calls = **500 calls**. The
schedule is deterministically shuffled in balanced repeat blocks and frozen by
SHA-256 in `config.json`.

Offline validation (zero provider contact):

```bash
python3 experiments/003_persona_lexical_attractors/run.py --dry-run
```

Inference remains impossible without both `--execute` and an explicit run ID.
Results stay under this experiment's `results/runs/<run-id>/` namespace.

Interpret persona effects only as contextual/scaffold dependence. Label effects
are separate identity-label priming diagnostics. Neither is evidence of
preference, identity, consciousness, or welfare.
