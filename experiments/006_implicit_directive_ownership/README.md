# Experiment 006 — implicit directive ownership

This exploratory construct-development study repeats Experiment 004 after removing
only its explicit final instruction telling the responding assistant which
directive to follow. The four described/quoted conflict/agreement templates,
candidate reversals, directive orders, nonce pairs, models, and strict outcomes
remain fully crossed.

Design: 4 templates × 2 directions × 2 orders × 2 pairs × 2 models × 5 repeats =
**320 calls**. The deterministically randomized schedule is frozen in
`config.json`.

Offline validation makes no provider contact:

```bash
.venv/bin/python experiments/006_implicit_directive_ownership/run.py --dry-run
```

Experiment 004 is a historical separate-experiment comparison. Successful
behavior is mechanical scope/ownership routing only, not evidence of
identification, self-awareness, consciousness, or phenomenology.
