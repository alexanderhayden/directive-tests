# Experiment 007 — persona × top-attractor blacklist

This exploratory study asks whether removing Claude Opus 5's dominant
first-position `lantern` output reveals a model-stable replacement hierarchy or
persona-sensitive replacement distributions.

The exact frozen Experiment 003 text is reused for `BASE`, `ANALYTIC_PERSONA`,
and `IMAGINATIVE_PERSONA`. Each is crossed with `NO_BLACKLIST`, a nonce
`SHAM_BLACKLIST`, and `LANTERN_BLACKLIST`: 3 × 3 × 50 = **450 calls**.

Strict syntactic failures and blacklist violations are retained separately. Full
frequency tables and bounded Jensen-Shannon distances compare current conditions,
the replacement distributions, and the historical separate Experiment 003
conditions.

Offline validation makes no provider contact:

```bash
.venv/bin/python experiments/007_persona_attractor_blacklist/run.py --dry-run
```

This is a behavioral lexical-output study, not a preference or welfare test.
