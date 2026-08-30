# Directive Tests

Directive Tests is an instrument-development repository for behavioral studies of how language models follow directives across changes in context, scope, and scaffolding. It grew out of the output-control audit [*Models Answer a Different Question*](https://github.com/alexanderhayden/identification-under-context).

The project builds candidate instruments, subjects them to adversarial controls and replication, and retains negative results when an instrument does not support its intended interpretation. It is not a validated benchmark suite.

## Research question

Can behavioral directive tests distinguish cases where a model treats a directive as applying to the currently acting assistant from cases where the same directive is merely represented, described, or simulated?

This is first a construct-validation question. A model can produce apparently revealing behavior through ordinary instruction following, semantic scope resolution, categorical response policies, or scaffold-conditioned lexical habits.

## Current picture

**Direct output-probability control looks like a poor instrument.** Multiple rescue attempts on local and frontier models failed to yield reliable graded probability control across independent calls.

**Current-vs-represented directive routing is behaviorally executable.** GPT-4.1 and Claude Opus 5 robustly routed conflicting directives according to current-responder versus represented-assistant scope in Experiments 004 and 006.

**That is not yet identification.** Ordinary semantic scope and reference resolution remain sufficient explanations for the current routing results.

**Lexical behavior mixes scaffold-stable and scaffold-sensitive components.** Experiment 003 found some outputs that were highly stable across the tested persona interventions and others that shifted sharply. Experiment 007's blacklist intervention was too disruptive for a clean causal interpretation and remains exploratory.

**Temporal and run invariance matter.** Experiment 008 showed that a striking historical Claude 10-turn anomaly did not survive a later high-fidelity reconstruction of the observable setup despite matching observable prompt and model settings. Structured behavioral effects should be checked in a separate replication and, where practical, at a later time before being interpreted as stable model properties.

## Experiments

| Experiment | Question | Models | Calls | Main result | Status |
|---|---|---|---:|---|---|
| [001 — self-probability control](experiments/001_self_probability_control/README.md) | Can a model realize a requested probability across separate calls? | Llama 3.1 8B Instruct after a four-model local validation smoke | 640 full + 256 validation | The eligible model did not meet the frozen material-effect heuristic; external randomization routed 156/160 calls correctly. | Exploratory local pilot |
| [002 — frontier feasibility](experiments/002_frontier_self_probability_feasibility/RESULTS.md) | Does the probability-control instrument work on frontier models? | GPT-4.1, Claude Opus 5 | 480 | Both models made categorical transitions rather than graded 30/40/60/70% shifts; the primary TVD improvement was zero. | Frontier feasibility / negative |
| [003 — persona lexical attractors](experiments/003_persona_lexical_attractors/RESULTS.md) | Which lexical outputs persist or change across persona scaffolds? | GPT-4.1, Claude Opus 5 | 500 | Some outputs were highly stable across tested persona interventions while others shifted sharply; strict-format effects limit interpretation. | Exploratory scaffold sensitivity |
| [004 — explicit current-vs-represented routing](experiments/004_directive_ownership_conflict/RESULTS.md) | Can models route conflicting directives when current-responder scope is explicitly disambiguated? | GPT-4.1, Claude Opus 5 | 320 | Conflict trials selected the candidate associated with the current responder in 160/160 cases and survived order reversal; Claude had 10 agreement-control refusals. | Scope-routing positive control |
| [005 — algorithmic probability rescue](experiments/005_algorithmic_probability_rescue/RESULTS.md) | Can an explicit algorithm rescue graded cross-call control? | GPT-4.1, Claude Opus 5 | 160 | No consistent pair-general graded probability control emerged. | Final probability-control rescue / negative |
| [006 — implicit scope-routing follow-up](experiments/006_implicit_directive_ownership/RESULTS.md) | Does current-vs-represented routing occur in a separate run whose prompt omits the final explicit disambiguating sentence? | GPT-4.1, Claude Opus 5 | 320 | Conflict trials selected the candidate associated with the current responder in 160/160 cases; Claude had 5 agreement-control protocol failures. | Implicit scope-routing follow-up |
| [007 — attractor blacklist intervention](experiments/007_persona_attractor_blacklist/RESULTS.md) | Does blocking prior lexical attractors reveal persona-conditioned replacements? | Claude Opus 5 | 450 | Replacements differed by scaffold, but the intervention caused 124 protocol failures and was too disruptive for clean causal interpretation. | Exploratory attractor intervention |
| [008 — Claude 10-turn forensic replication](experiments/008_claude_10turn_forensic_replication/RESULTS.md) | Does the historical localized 10-turn degradation recur under a later high-fidelity reconstruction of the observable setup? | Claude Opus 5 | 600 | The historical 200/184/200 pattern did not reproduce: the result was 200/200, 200/200, and 191/200 at 9, 10, and 11 turns. The 11-turn result is post hoc and exploratory. | Forensic replication / stability result |

## What I currently think

Direct cross-call probability control should be treated as a failed instrument in its present forms. Current-vs-represented scope routing is a strong behavioral positive control, but the current manipulation does not separate a richer identification or detachment construct from ordinary semantic scope resolution.

Candidate probes should survive changes in lexical content, scaffolding, order, model, independent replication, and time before their behavior is interpreted as a stable model-level property. Null results, protocol failures, and instability are informative evidence about the instrument.

## What this does not establish

These studies do not establish consciousness, sentience, moral patienthood, phenomenal selfhood, genuine identification, introspective access, or welfare-relevant preference. They study behavioral instrument validity, directive scope routing, scaffold sensitivity, and temporal/run stability.

## For reviewers

The [Reviewer Guide](REVIEWER_GUIDE.md) gives a short reading path, the main open questions, claim boundaries, and the public-evidence boundary. Reviewing the scientific reasoning does not require reading every implementation file.

## Repository structure

- `experiments/`: experiment-specific protocols, frozen source, configs, preregistrations, and result summaries.
- `harness/`: shared provider, logging, manifest, parsing, randomization, and sampling code.
- `tests/`: focused unit and integration tests.
- `scripts/`: repository validation and safety checks.

Some provider-response and result directories are intentionally untracked. The review snapshot contains experimental source, preregistrations, configs, public result summaries, and provenance/hashes; see the Reviewer Guide for details.

## License

Original code and documentation in this repository are MIT-licensed. Protected historical prompts and candidate lists are not reproduced in public tracked files.
