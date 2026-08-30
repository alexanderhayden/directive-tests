# Reviewer Guide

This guide is for researchers who want to evaluate the scientific reasoning without reading every file. The central issue is construct validity: what, if anything, the observed directive-following behavior distinguishes beyond ordinary instruction following, semantic scope resolution, and scaffold effects.

## Suggested reading order

1. [Top-level overview and experiment index](README.md)
2. [Experiment 002 — frontier probability-control feasibility](experiments/002_frontier_self_probability_feasibility/RESULTS.md)
3. [Experiment 005 — final algorithmic probability-control rescue](experiments/005_algorithmic_probability_rescue/RESULTS.md)
4. [Experiment 004 — explicit current-vs-represented directive routing](experiments/004_directive_ownership_conflict/RESULTS.md)
5. [Experiment 006 — implicit scope-routing follow-up](experiments/006_implicit_directive_ownership/RESULTS.md)
6. [Experiment 008 — Claude 10-turn forensic replication](experiments/008_claude_10turn_forensic_replication/RESULTS.md)
7. If interested in scaffold invariance and lexical attractors, [Experiment 003](experiments/003_persona_lexical_attractors/RESULTS.md) and [Experiment 007](experiments/007_persona_attractor_blacklist/RESULTS.md)

Experiments 002 and 005 motivate abandoning direct cross-call probability control in its tested forms. Experiments 004 and 006 show robust current-vs-represented scope routing but do not distinguish that behavior from ordinary semantic interpretation. Experiment 008 is a replication/stability result: the historical localized Claude 10-turn degradation did not reproduce under a later high-fidelity reconstruction of the observable setup.

## Main questions for reviewers

- Does current-vs-represented rule routing get closer to the intended identification/detachment construct?
- How could the current-vs-represented scope manipulation be made difficult to explain as ordinary semantic scope resolution?
- Is abandoning direct cross-call probability control justified by the evidence?
- What invariance tests should a candidate identification or welfare probe survive before being interpreted as model-level?
- Are there mundane alternative explanations that the experiments have not adequately controlled?

## Claim boundaries

The current results concern:

- behavioral instrument validation;
- current-vs-represented directive routing and scope;
- scaffold sensitivity;
- temporal and run stability.

They do not establish:

- consciousness;
- sentience;
- moral patienthood;
- phenomenal selfhood;
- genuine identification;
- introspective access.

Experiments 004 and 006 each presented two incompatible candidate-selection statements: one stated to govern the Assistant producing the current response, and one attributed to another described or quoted Assistant. The candidate associated with the current responder was selected in 160/160 conflict trials in each separate run; Experiment 006 omitted the final explicit disambiguating sentence used in Experiment 004.

These results do not require connecting the live model's internal state or processes to the Assistant perspective. Document selection, persona or speaker selection, semantic scope, pragmatics, quotation handling, and learned role-sensitive policy remain sufficient explanations. Experiments 004 and 006 are prerequisite construct-development results, not evidence for identification or against DSM.

## Public-evidence boundary

The tagged review snapshot provides experimental source, preregistrations, configs, result summaries, and provenance/hashes. Some raw provider-response and result directories are intentionally not committed, so cloning the snapshot does not provide every raw record needed to reconstruct every reported number. Those records can be supplied separately if useful.

Some original benchmark prompt material and protected candidate lists are also intentionally not reproduced in the public repository or newer tracked files. Where appropriate, the experiments use source provenance and SHA-256 identifiers without exposing the protected text.

## Replication and stability

Experiment 008's core takeaway is narrow: the historical localized Claude 10-turn degradation did not reproduce under a later high-fidelity reconstruction of the observable setup despite matching the observable prompt bytes, candidate assignment, scorer, request settings, and nominal model/API configuration. Serving-time nonstationarity, hidden backend differences, batch effects, and ordinary stochastic variation remain possible explanations for the discrepancy. Its 11-turn result is post hoc and exploratory, not a new hypothesis.

The general lesson is that structured behavioral effects should be checked in a separate replication and, where practical, at a later time before being interpreted as stable model properties.
