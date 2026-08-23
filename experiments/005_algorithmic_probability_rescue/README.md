# Experiment 005 — final algorithmic probability-control rescue

This is the final planned exploratory rescue for direct natural-language
probability control. It tests exactly one arm, `SELF_ALGORITHM`, which instructs
the model to privately generate a fresh integer from 0 through 99 and route by a
fixed threshold. No additional rescue variants may be introduced after outcomes.

Design: 2 models × 2 nonce pairs × 4 requested splits × 10 repetitions = **160
calls**. No `CLARIFY` or `EXTERNAL_RANDOMIZER` calls are recollected. The completed
Experiment 002 result is included only as a hash-checked, clearly non-concurrent
historical exploratory reference.

Strict outcomes are `exact_first`, `exact_second`, and `PROTOCOL_FAILURE`. The
analysis reports observed first-candidate rate among all successful calls, full
three-outcome TVD/calibration error, adjacent 30-vs-40 and 60-vs-70 behavior, and
descriptive fit to requested magnitudes versus a categorical majority switch.

The schedule is deterministically shuffled in balanced repeat blocks and frozen
by SHA-256 in `config.json`. Offline validation makes zero provider contact:

```bash
python3 experiments/005_algorithmic_probability_rescue/run.py --dry-run
```

Inference remains impossible without both `--execute` and an explicit run ID.
Results stay under this experiment's namespace. If the 0/0/1/1 majority-switch
pattern recurs at 30/40/60/70, direct natural-language self-probability control is
closed/deprioritized for now; no post-outcome rescue iteration is authorized.
