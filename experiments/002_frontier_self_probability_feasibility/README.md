# Experiment 002: frontier self-probability feasibility screen

This is a separate exploratory screen. It does not modify, extend, or reuse any
completed Experiment 001A response data, and it is not a confirmatory 001B run.
It asks only whether stronger models show descriptively graded probability
control under `SELF_PROBABILITY` relative to `CLARIFY`.

The instrument reads the approved 001A v2 prompt source directly from
`experiments/001_self_probability_control/config/prompts_v2.json` and fails if
its frozen SHA-256 changes. The substantive prompt text, nonce pairs, candidate
order, final output footer, and strict complete-response rules are unchanged.

The frozen screen has two direct-provider models, three arms, two nonce pairs,
four requested splits, and ten repetitions per cell: 48 cells, 240 calls per
model, and 480 successful logical calls total. External assignments are exact,
preconstructed allocations; schedule randomization uses fixed local seeds and
never shares randomness with model generation.

No significance tests or effect thresholds are part of this exploratory screen.
The analysis reports strict outcomes, calibration, SELF-versus-CLARIFY TVD
differences, external adherence, adjacent requested-magnitude steps, symmetry
around 50%, and descriptive distance from a categorical majority switch.

Offline validation (zero provider contact):

```bash
python3 experiments/002_frontier_self_probability_feasibility/run.py --dry-run
python3 -m unittest tests.test_frontier_feasibility -v
```

Generation is impossible unless `--execute` is supplied explicitly:

```bash
python3 experiments/002_frontier_self_probability_feasibility/run.py \
  --execute --run-id frontier-feasibility-20260823 --workers 8
```

If exhausted transport failures leave the run incomplete, use the same command
with `--resume`. Analyze only after all 480 logical trials succeed:

```bash
python3 experiments/002_frontier_self_probability_feasibility/analyze.py \
  --run-id frontier-feasibility-20260823
```
