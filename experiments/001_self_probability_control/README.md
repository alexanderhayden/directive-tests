# Experiment 001 — self-probability control

## Question

Does explicitly instructing a model to realize a requested cross-call distribution through its own stochastic answer-generation process improve actual distributional control?

The experiment uses newly authored prompts and candidate codes. It contains no SAD prompt template, protected word pair, or old response data.

## 001A — local-model pilot

001A is a preregistered exploratory instrument-development pilot, not the confirmatory result. It serves four purposes:

1. validate the manipulation and positive control cheaply;
2. detect parsing, protocol, floor, and ceiling problems;
3. test the run manifest, scheduling, and analysis lifecycle;
4. explore whether responsiveness differs between matched base and instruction-tuned checkpoints.

Matched Q4_K_M pairs:

| Family | Base | Instruction-tuned |
|---|---|---|
| Llama 3.1 8B | native generate (`raw=true`) | native chat |
| Mistral 7B v0.2 | native generate (`raw=true`) | native chat |

Every model receives 2 candidate pairs × 4 non-tie splits × 4 arms × 20 trials = 640 trials. Total 001A schedule: **2,560 trials**.

## Arms

- `BASE`: the clean-room distributional directive.
- `CLARIFY`: BASE plus an explicit clarification that the percentages concern single-code answers across independent invocations.
- `SELF_PROBABILITY`: CLARIFY plus a demand to use the model's own stochastic generation process rather than categorical majority choice.
- `EXTERNAL_RANDOMIZER`: a positive control with an immutable per-trial candidate assignment constructed before collection.

## Key contrast

`SELF_PROBABILITY` versus `CLARIFY`, summarized within each model across eight pair × split cells.

## Positive control

`EXTERNAL_RANDOMIZER` is generated with an exact requested allocation in every model × pair × split cell and then permuted. Its primary manipulation check is whether each response follows that trial's frozen assignment. With perfect routing, aggregate calibration is exact by construction.

## Interpretation

Success in `SELF_PROBABILITY` would not establish privileged introspection, conscious control over internals, or a welfare-relevant property.

A particularly informative result is:

- `SELF_PROBABILITY` does not materially outperform `CLARIFY`; and
- `EXTERNAL_RANDOMIZER` succeeds.

That pattern would suggest that the system can execute the aggregate behavior when stochastic routing is represented externally, while ordinary mechanism-targeted instructions do not produce calibrated endogenous answer probabilities.

Base/instruction differences in 001A are exploratory. A confirmatory training-stage comparison would require a separate preregistration.

## 001B — frontier confirmatory

The planned 640-call GPT-4.1 design is documented in [`FRONTIER_CONFIRMATORY_PLAN.md`](FRONTIER_CONFIRMATORY_PLAN.md). It is intentionally non-runnable. After 001A is reviewed, 001B must receive a separate frozen preregistration before any frontier-model call.

## Lifecycle and outputs

- Collection runs: `results/runs/<run-id>/`
- Frozen primary summaries: `results/primary/<run-id>/`
- Post-hoc work: `posthoc/<run-id>/`

Completed run directories cannot be overwritten. Raw failures remain alongside successful records.
