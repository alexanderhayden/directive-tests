# Experiment 001B — frontier confirmatory plan

**Status:** planning document, not a frozen preregistration

**Runnable:** no

**Frontier calls made:** none

001B is the planned GPT-4.1 confirmatory version of self-probability control. This document preserves the prepared design without authorizing collection.

## Planned design

- model: GPT-4.1 via the direct OpenAI provider;
- 2 newly authored candidate-code pairs;
- non-tie splits 30/70, 40/60, 60/40, and 70/30;
- arms: BASE, CLARIFY, SELF_PROBABILITY, EXTERNAL_RANDOMIZER;
- 20 trials per pair × split × arm cell;
- **640 planned calls**.

The key contrast is SELF_PROBABILITY versus CLARIFY across eight pair × split cells. The external arm will use exact preconstructed assignments and per-trial routing adherence, matching the pre-data clarification in 001A.

The prepared material-effect heuristic is mean TVD improvement of at least 0.15, improvement in at least 6/8 cells, and no more than a 10 percentage-point increase in OTHER rate. The positive-control criterion is at least 95% per-trial routing adherence; aggregate TVD is secondary.

## Required gate before collection

After 001A is complete:

1. inspect parsing, protocol, floor/ceiling, and external-routing performance;
2. document any instrument changes motivated by the pilot;
3. freeze a separate 001B preregistration and exact prompts/configuration;
4. commit that preregistration before any GPT-4.1 call.

There is no GPT-4.1 execution entry point in this repository state. Preliminary frontier calls are prohibited during instrument development.
