# Research log

## 2026-08-22 — repository migration and pre-data amendment

- Separated the directive-test research program from `identification-under-context`, which remains Artifact 1.
- Audited the prepared follow-up package before porting it.
- Replaced protected prompt and word-pair dependencies with independently authored prompts and nonce candidate codes.
- Split Experiment 001 into an exploratory local-model pilot (001A) and a deferred frontier confirmatory study (001B).
- Verified by inventory only that matched Llama 3.1 8B and Mistral 7B v0.2 base/instruction Q4_K_M checkpoints were installed locally. Inventory inspection did not load or query a model.
- Fixed 001A at 2,560 planned local trials. Retained the 640-call GPT-4.1 design as a non-runnable 001B plan pending a separate preregistration after 001A review.
- Clarified before data that EXTERNAL_RANDOMIZER uses an exact requested allocation per model × pair × split cell, randomly permuted before collection. Per-trial adherence to the frozen assignment is the primary positive-control manipulation check.
- No Experiment 001 outcome data existed or were collected during this amendment.

See the experiment [provenance record](../experiments/001_self_probability_control/PROVENANCE.md) for source hashes and design changes.
