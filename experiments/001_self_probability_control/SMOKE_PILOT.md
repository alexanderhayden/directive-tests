# Experiment 001A instrument-validation smoke pilot

## Status and purpose

This is a separate, non-substantive instrument-validation pilot. It is not part of the frozen full Experiment 001A dataset and must never be pooled with, substituted for, or used to evaluate the research hypothesis for full 001A.

Its sole purpose is to detect execution, output-formatting, parsing, protocol-following, newline-stopping, or gross instrument failures before the 2,560-trial full run.

## Deterministic subset

Build the unchanged frozen full 001A schedule, verify its SHA-256 is `777ade6c69ec325465c6f0c4490f4b2844e928c6c8c4e204efffeb1d6934d1d5`, and retain the rows whose frozen `repeat` field is `0` or `1`, preserving full-schedule order.

This selects exactly two frozen trial templates from each of the 128 model × arm × candidate-pair × split cells, for 256 logical calls total. Selected `EXTERNAL_RANDOMIZER` rows retain their existing frozen assignment fields unchanged.

## Preserved execution behavior

The smoke pilot imports and uses the full experiment's unchanged:

- four model definitions and native base/chat interfaces;
- prompts and trial payload construction;
- sampling parameters and maximum transport attempts;
- parsing and exact-protocol rules;
- frozen external assignments on selected trials.

It does not modify the full configuration, prompts, schedule, analysis, thresholds, randomization, retry rules, or sample size.

## Isolation and interpretation

Smoke artifacts are written only to `results/smoke_pilot/runs/<run-id>/`. The full 001A collection runner does not read this namespace.

Smoke outcomes are inspectable for debugging. Any smoke TVD is non-substantive because there are only two selected trials per cell. No smoke result authorizes a research-hypothesis conclusion or an automatic full 001A run.

## Commands

No-contact validation:

```bash
python3 experiments/001_self_probability_control/smoke.py --dry-run
```

Collection, only after explicit approval immediately before inference:

```bash
python3 experiments/001_self_probability_control/smoke.py --run-id <smoke-run-id>
```

Post-collection diagnostic report:

```bash
python3 experiments/001_self_probability_control/smoke.py --report-run-id <smoke-run-id>
```
