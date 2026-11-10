"""Small stdlib statistics helpers shared by the evaluations (no numpy: the production image stays unchanged)."""
from __future__ import annotations

import random
from typing import Callable, Sequence


def bootstrap_ci(items: Sequence, stat: Callable[[Sequence], float | None], n: int = 1000, seed: int = 0,
                 alpha: float = 0.05) -> tuple[float | None, float | None]:
    """Percentile bootstrap over items (records or seeds). Returns (low, high); None if the statistic is undefined."""
    if not items:
        return None, None
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        v = stat([items[rng.randrange(len(items))] for _ in range(len(items))])
        if v is not None:
            vals.append(v)
    if not vals:
        return None, None
    vals.sort()
    return vals[int(alpha / 2 * (len(vals) - 1))], vals[int((1 - alpha / 2) * (len(vals) - 1))]


def ratio(a: float, b: float) -> float | None:
    return a / b if b else None


def fmt(x: float | None, pct: bool = True) -> str:
    if x is None:
        return "n/a"
    return f"{100 * x:.1f}%" if pct else f"{x:.3f}"
