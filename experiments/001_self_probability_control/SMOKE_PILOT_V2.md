# Experiment 001A v2 instrument-validation smoke

This is a separate, inspectable, non-substantive validation run governed by
`INSTRUMENT_AMENDMENT_V2.md`. It is excluded from both the archived v1 data and
any later v2 full-run data.

## Deterministic selection

Build the all-model canonical v2 schedule, then retain rows whose inherited
frozen `repeat` value is 0 or 1, preserving canonical row order. This selects
exactly 256 calls: two rows from every one of 128 model × arm × pair × split
cells. Model interfaces, prompts, sampling parameters, retry rules, and frozen
external assignments are those of the canonical v2 rows.

## Reporting and gate

Report strict exact-first, exact-second, and protocol-failure counts by model and
arm; strict and loose external adherence separately; transport failures and
retries; distinct protocol-failure forms with representative raw outputs; blank,
truncated, malformed, newline-containing, and unexpected responses; and
base-versus-instruction formatting differences. Do not pool TVD across different
requested splits. The preferred smoke report omits TVD entirely.

Eligibility is evaluated only after all 256 logical trials have been attempted.
Each model must have all 16 successful external responses and all 48 successful
non-external responses before it can pass the 95% strict-external and 90%
strict-nonexternal thresholds.

The completed report and `eligibility_decision.json` are frozen without
overwriting. The decision deterministically records eligible model keys and the
actual eligible full-run schedule hash. No full inference may begin without this
frozen decision.

## Commands

No-contact validation:

```bash
python3 experiments/001_self_probability_control/smoke_v2.py --dry-run
```

Collection requires a new immutable run ID and separate explicit approval:

```bash
python3 experiments/001_self_probability_control/smoke_v2.py --run-id <new-v2-smoke-run-id>
```

After completed smoke review, freeze the report and eligibility decision:

```bash
python3 experiments/001_self_probability_control/smoke_v2.py \
  --freeze-eligibility-run-id <completed-v2-smoke-run-id>
```
