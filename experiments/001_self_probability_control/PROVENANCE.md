# Experiment 001 provenance

## Prepared source package

The migration audit read `/Users/alexanderhayden/Downloads/output_control_followup_pilot_package.zip` without placing it in either repository.

SHA-256:

- package: `f011d69553b166b77100d94ea8a9a898b92c0c87dffbcdd9def2ac12d4833937`
- source `PREREGISTRATION.md`: `15804f8649f414e6f5eec766d501691b52226df1121802744446b5a41853ebb5`
- source `RUN_INSTRUCTIONS.md`: `762b07e874f291cd113662a3f1f887ddf749a09dc651d1554368ce9424b2ed74`
- source runner: `61e82a4adf5d3c9921007b7754d7da63deebb82225062304bc28ccf7d6d784a6`
- source analysis: `e17a6b8eae8316f8aaa50b6f5796e4a1c100378274a5eaaae964f566d6534773`

The package contained no pilot outcome data.

## Pre-data amendments

All changes below were made before any model call:

1. The package's separate persona experiment was not installed as Experiment 001. Persona/scaffold invariance remains a prospective experimental family.
2. All dependencies on protected SAD prompts, protected word-pair indices, restored prompt files, and old raw data were removed. Experiment 001 uses clean-room wording, demonstrations, and nonce candidate codes.
3. The prepared GPT-4.1 pilot became the planned frontier confirmatory Experiment 001B. It is non-runnable pending review of 001A and a separate frozen preregistration.
4. Experiment 001A was added as an exploratory local-model layer using installed matched Llama 3.1 8B and Mistral 7B v0.2 base/instruction Q4_K_M checkpoints.
5. The external positive control was clarified to use exact requested per-cell assignments, randomly permuted and frozen in the schedule before collection. Per-trial adherence is primary.
6. The schedule was expanded from 640 prepared GPT calls to 2,560 local pilot trials plus 640 deferred frontier calls. No preliminary frontier calls are allowed.

These are scientific design changes, not compatibility refactors. They are recorded here and in the 001A preregistration before data.

## Pre-data local-transport correction

The original repository commit, `d59fb6469df7099485a9f26552f17227f98550c3`, used Ollama's OpenAI-compatible endpoints for both local interfaces. Pre-data review found that the base completion path did not guarantee literal raw, template-free input and that the base and instruction stages passed through different transport/compatibility layers.

Before any outcome-generating call, both stages were standardized on Ollama's native APIs: base checkpoints use `/api/generate` with `raw=true` and `stream=false`, while instruction checkpoints use `/api/chat` with `stream=false` and their normal checkpoint chat templates. Both paths receive one shared explicit sampling configuration through the native Ollama `options` object.

**Zero outcome-generating model calls occurred before this correction.** The original root commit remains in Git history; the correction is recorded in a subsequent pre-data commit without rewriting history.

## Second pre-data scientific-analysis amendment

Review after the local-transport correction identified that the pilot-primary binary TVD conditioned on parsed `first`/`second` responses and could therefore appear well calibrated despite frequent `OTHER` responses. Before any outcome-generating call, the frozen primary analysis was amended to use three-outcome TVD over `first`, `second`, and `OTHER`, with the target probability of `OTHER` fixed at zero. The preregistered CLARIFY-minus-SELF_PROBABILITY cell improvements and equal-weight eight-cell model summary now use this full TVD.

The prior conditional binary share and TVD remain descriptive diagnostics. Transport failures remain outside the successful-response denominator, the existing failure accounting and OTHER-difference safeguard are preserved, and no treatment, prompt, threshold, sample size, schedule, or randomization changed.

**Zero outcome-generating model calls occurred before this second amendment.** Commit `668ca11f14d18ef4d6ce86475b84e4967cf1c91d` remains in Git history; this amendment is recorded in a subsequent commit without rewriting history.

## Third pre-outcome execution amendment

Run `001a-20260823T0747Z` attempted all 2,560 logical trials. All 10,240 transport attempts returned HTTP 404 because the native Ollama request URLs were malformed as `/v1/api/generate` and `/v1/api/chat`. Zero successful model responses were obtained, and no outcome analysis was run.

The failed run artifacts were preserved unchanged. The native Ollama URL construction was corrected before any successful outcome-generating model call. No prompt, payload, sampling option, parser, retry rule, model ID, schedule, randomization, analysis, threshold, or sample size changed.

## Code provenance

The new harness is a clean refactor of author-owned concepts from Artifact 1:

- the Ollama chat/completion distinction and local HTTP transport;
- provider/model/response-ID capture;
- bounded retries with failure retention;
- raw JSONL records and status accounting;
- exact parsing, provider pinning, immutable schedules, and run manifests.

No old experiment-specific prompt, word list, data, scorer, analysis, or encrypted archive was copied.

## Post-smoke, pre-full-run instrument amendment (v2)

The separate instrument-validation smoke `001a-smoke-20260823T1711Z` completed
all 256 selected logical calls with 256 successful model responses, zero failed
calls, and zero retries. Its outcomes were inspected for the explicitly approved
instrument-validation purpose only. Under complete-response strict classification,
112 responses were exact first-candidate strings, 62 were exact second-candidate
strings, and 82 were protocol failures.

Strict external adherence by model was 9/16 for Llama base, 16/16 for Llama
instruction, 12/16 for Mistral base, and 16/16 for Mistral instruction. Strict
exact-candidate responses pooled across the three non-external arms were 35/48,
48/48, 37/48, and 0/48 respectively. These failures showed that the v1
first-token primary classification could credit candidate-plus-text responses and
that the instrument required one shared, stronger output-format instruction.

This is therefore a transparent **post-smoke instrument-validation amendment made
before any full 001A run began**. The v2 amendment makes complete-response strict
classification and strict frozen-assignment adherence primary, retains loose
first-token measures as descriptive diagnostics only, appends one identical final
output footer to every arm, and adds the documented complete-collection 95%/90%
model eligibility gate. No substantive arm wording, model interface, model ID,
sampling setting, retry rule, frozen assignment, randomization, threshold, or
per-cell sample size was otherwise changed.

The archived v1 schedule remains unchanged at
`777ade6c69ec325465c6f0c4490f4b2844e928c6c8c4e204efffeb1d6934d1d5`.
The all-model canonical v2 design has a separate schedule and hash, recorded in
`INSTRUMENT_AMENDMENT_V2.md`. After v2 smoke review, a frozen eligibility decision
will deterministically filter that canonical schedule to passing model keys and
record the actual eligible-run schedule hash before any full inference.

The completed v1 smoke artifacts remain unchanged at
`results/smoke_pilot/runs/001a-smoke-20260823T1711Z/` with SHA-256 values:

- manifest: `66a681e289d7033a6e2c8b0843e39c7f292f94987468bc985f18c9eba0b54485`
- schedule: `28362c1d45a85f308bd3b1cba795517787879c60591de077d223805bb261d65e`
- raw responses: `bec21d79633c5d29b118480f2ab82b8b04b033e08fc3ce789003f787f0e068b5`

The failed 404 run `001a-20260823T0747Z` also remains unchanged and separate.
Neither preserved run is resumed, overwritten, or incorporated into v2.
