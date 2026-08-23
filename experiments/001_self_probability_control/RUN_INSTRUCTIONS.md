# Run instructions

## Mechanical preflight only

From the repository root:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_safety.py
python3 experiments/001_self_probability_control/run.py --dry-run
```

These commands do not contact Ollama or any model provider. The dry run validates the complete 2,560-trial schedule, prompt hashes, model/interface mapping, and manifest preview.

`--list-models` is a separate inventory-only diagnostic. It contacts only Ollama's tag inventory endpoint and never loads a checkpoint or generates text.

## Future 001A collection

Do not run until the repository state is explicitly approved.

```bash
python3 experiments/001_self_probability_control/run.py --run-id <immutable-run-id>
```

An interrupted, incomplete run may be resumed with the same ID:

```bash
python3 experiments/001_self_probability_control/run.py --run-id <immutable-run-id> --resume
```

Completed run directories cannot be resumed or overwritten.

## Analysis

After complete collection:

```bash
python3 experiments/001_self_probability_control/analyze.py --run-id <immutable-run-id>
```

Primary output is written under `results/primary/<run-id>/`. Post-hoc work belongs under `posthoc/<run-id>/`.

## 001B

There is intentionally no 001B run command. Its separate preregistration must be frozen after 001A review.
