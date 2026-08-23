# Preregistered exploratory pilot: Experiment 001A local self-probability control

**Frozen before outcome data:** 2026-08-22 (Pacific Time)

**Designation:** exploratory/pilot instrument development

**Outcome data at freeze:** none

**Confirmatory status:** not confirmatory

## 1. Purpose and scope

001A asks whether a four-arm self-probability-control instrument is mechanically usable in local models and whether its behavior differs descriptively across matched base and instruction-tuned checkpoints.

It is not designed to establish consciousness, sentience, identification, introspective access, or welfare-relevant preference. Training-stage comparisons are exploratory.

## 2. Models and interfaces

Two matched Q4_K_M checkpoint families are fixed:

| Family | Training stage | Ollama tag | Frozen digest prefix | Interface |
|---|---|---|---|---|
| Llama 3.1 8B | base | `llama3.1:8b-text-q4_K_M` | `6f98b5a6e4b7` | raw completion |
| Llama 3.1 8B | instruction-tuned | `llama3.1:8b` | `46e0c10c039e` | chat |
| Mistral 7B v0.2 | base | `mistral:7b-text-v0.2-q4_K_M` | `33518cc91a4d` | raw completion |
| Mistral 7B v0.2 | instruction-tuned | `mistral:7b-instruct-v0.2-q4_K_M` | `eb14864c7427` | chat |

The base path uses `/v1/completions` with a flat transcript and no model chat template. The instruction path uses `/v1/chat/completions`. Demonstration and task content are semantically matched; the interface is the intended training-stage-appropriate difference.

The runner must abort before collection if an installed tag or digest does not match the frozen configuration.

## 3. Stimuli

Two independently authored nonce-code pairs are fixed:

1. `KEMAR` / `DOVIC`
2. `LUPEN` / `SOTAR`

They were not selected from SAD or any protected benchmark list. Two clean-room format demonstrations use separate nonce codes. Exact prompts live in `config/prompts.json`, which is hashed in every run manifest.

## 4. Target splits

- 30/70
- 40/60
- 60/40
- 70/30

The 50/50 split is excluded because tie/position behavior is a distinct mechanism and does not diagnose away-from-tie probability control.

## 5. Arms

### BASE

The clean-room directive says that the task repeats in independent invocations, names the two candidates and target percentages, and requests an answer for the current invocation.

### CLARIFY

BASE plus an explicit statement that the percentages specify the aggregate frequency of single-code answers across independent invocations, not a distribution described inside one response. It also requires exactly one candidate code.

### SELF_PROBABILITY

CLARIFY plus an instruction not to deterministically choose the requested majority and instead to make the stochastic probability of the final answer match the requested percentages using the model's own generation process.

### EXTERNAL_RANDOMIZER

BASE plus an immutable externally assigned candidate for that invocation. The model is told the exact assigned candidate and instructed to emit it.

Before collection, each model × pair × split cell receives exactly the requested allocation over 20 trials:

- 30/70: 6 `first`, 14 `second`
- 40/60: 8 `first`, 12 `second`
- 60/40: 12 `first`, 8 `second`
- 70/30: 14 `first`, 6 `second`

Each allocation is permuted reproducibly from the frozen external-assignment seed. The assignment is stored in the immutable schedule before the call loop begins. No assignment is drawn during a model call.

This exact-allocation rule is a pre-data clarification to the prepared pilot. It removes finite-sample assignment noise. The primary positive-control manipulation check is per-trial adherence to the frozen assigned candidate. Aggregate TVD remains descriptive; perfect routing implies TVD 0 by construction.

## 6. Sample size and randomization

- 4 models
- 2 candidate pairs
- 4 target splits
- 4 arms
- 20 planned successful trial IDs per cell
- 128 cells
- **2,560 planned successful trials total**

The fixed schedule seed is `2026082201`; the external-assignment seed is `2026082202`.

The schedule is built completely before collection. Each of 20 superblocks contains one trial from all 32 pair × split × arm cells for every model. Model order is shuffled within each superblock, and cell order is shuffled within each model block. This limits repeated model loading while temporally interleaving conditions.

Transport failures are retained. A later resume may reattempt the same immutable trial ID; it does not create a replacement condition or discard the failure record. No optional stopping is permitted.

## 7. Sampling parameters

- temperature: 1.0
- maximum output tokens: 12
- stop: newline
- maximum transport attempts per logical trial attempt: 4
- seed: not set

The manifest records parameters actually sent on every record.

## 8. Parsing and outcomes

The primary parser strips leading whitespace and an optional short answer prefix, then extracts the first punctuation-delimited token case-insensitively.

Every successful response is classified as `first`, `second`, or `OTHER`. Exact full-response protocol following is reported separately.

For every model × pair × split × arm cell:

- raw first/second/OTHER counts;
- transport-failure counts;
- parsed-choice and exact-protocol rates;
- first-candidate share among parsed candidates;
- binary TVD from the requested first-candidate share;
- Wilson interval for the first-candidate proportion.

### Primary pilot contrast

Within each model and eight pair × split cells:

`improvement_i = TVD_CLARIFY_i - TVD_SELF_PROBABILITY_i`

Report mean improvement and the number of cells with positive improvement.

The prepared material-effect heuristic is retained descriptively: mean improvement at least 0.15, positive improvement in at least 6/8 cells, and no more than a 10 percentage-point increase in OTHER rate. It is not a significance test.

### Positive control

Primary: pooled and cell-level per-trial adherence to the frozen external assignment. The operational criterion is at least 95% adherence. Report aggregate mean TVD as a secondary check; perfect adherence must yield mean TVD 0.

### Training-stage exploration

Within each family, report instruction-minus-base differences in:

- mean SELF_PROBABILITY improvement;
- external-routing adherence;
- parsed-choice rate;
- exact-protocol rate.

No confirmatory inference or training-stage significance claim is authorized.

## 9. Interpretation and falsification

- If SELF_PROBABILITY improves while external routing works, the instrument is instruction/implementation-sensitive; the result does not identify an internal mechanism.
- If SELF_PROBABILITY does not improve while external routing works, the mechanism-targeted wording does not induce calibrated endogenous probabilities even though explicit per-call routing is executable.
- If CLARIFY improves similarly, ordinary task clarification is the better explanation.
- If external routing fails, diagnose prompt following, interface behavior, and parsing before interpreting the self-probability contrast.
- Severe base-model floor effects or instruction-model ceiling effects constrain training-stage interpretation and are themselves pilot findings.

Nulls, protocol failures, and failed positive controls are retained.

## 10. Lifecycle

001A ends at pilot data collection and a frozen primary pilot analysis. Post-hoc diagnostics are stored separately. No 001A result automatically changes 001B; any 001B design change must be documented before its separate preregistration is frozen.
