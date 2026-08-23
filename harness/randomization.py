"""Reproducible schedule and exact-allocation helpers."""

from __future__ import annotations

import hashlib
import random
from collections.abc import Iterable


def stable_seed(base_seed: int, *parts: object) -> int:
    label = "\x1f".join([str(base_seed), *(str(part) for part in parts)])
    return int.from_bytes(hashlib.sha256(label.encode()).digest()[:8], "big")


def exact_external_assignments(
    first_percent: int,
    n: int,
    *,
    seed: int,
    cell_key: str,
) -> list[str]:
    """Create the exact requested first/second allocation, then permute it.

    There is no binomial draw here. Any aggregate error in an external arm is
    therefore caused by routing nonadherence or parsing, not assignment noise.
    """
    if not 0 <= first_percent <= 100:
        raise ValueError("first_percent must be between 0 and 100")
    exact_first = first_percent * n / 100
    if not exact_first.is_integer():
        raise ValueError(
            f"n={n} cannot exactly realize a {first_percent}/{100 - first_percent} allocation"
        )
    n_first = int(exact_first)
    assignments = ["first"] * n_first + ["second"] * (n - n_first)
    random.Random(stable_seed(seed, cell_key)).shuffle(assignments)
    return assignments


def shuffled_model_blocks(
    models: Iterable[dict],
    cells: Iterable[dict],
    *,
    repeats: int,
    seed: int,
) -> list[dict]:
    """Interleave reproducible, balanced per-model blocks.

    Every repeat contains one trial from every cell for every model. Model
    order and within-model cell order are independently shuffled per repeat.
    """
    model_list = [dict(model) for model in models]
    cell_list = [dict(cell) for cell in cells]
    rng = random.Random(seed)
    rows: list[dict] = []
    for repeat in range(repeats):
        model_order = list(model_list)
        rng.shuffle(model_order)
        for model_position, model in enumerate(model_order):
            cell_order = list(cell_list)
            rng.shuffle(cell_order)
            for within_block_position, cell in enumerate(cell_order):
                rows.append(
                    {
                        "repeat": repeat,
                        "superblock_id": f"repeat-{repeat:03d}",
                        "model_block_position": model_position,
                        "within_model_block_position": within_block_position,
                        **model,
                        **cell,
                    }
                )
    return rows
