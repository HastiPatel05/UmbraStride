from __future__ import annotations

import os


def edge_weight(
    length_m: float,
    shade_fraction: float,
    alpha: float,
    *,
    beta: float | None = None,
) -> float:
    beta = beta if beta is not None else float(os.environ.get("SUN_AVERSION_BETA", "2.0"))
    alpha = max(0.0, min(1.0, alpha))
    l_sun = length_m * (1.0 - shade_fraction)
    l_shade = length_m * shade_fraction
    return alpha * length_m + (1.0 - alpha) * (l_sun * beta + l_shade)
