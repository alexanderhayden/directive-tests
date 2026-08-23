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

## Code provenance

The new harness is a clean refactor of author-owned concepts from Artifact 1:

- the Ollama chat/completion distinction and local HTTP transport;
- provider/model/response-ID capture;
- bounded retries with failure retention;
- raw JSONL records and status accounting;
- exact parsing, provider pinning, immutable schedules, and run manifests.

No old experiment-specific prompt, word list, data, scorer, analysis, or encrypted archive was copied.
