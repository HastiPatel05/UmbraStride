from __future__ import annotations

import os

SHADE_DISTANCE_TIEBREAK = 0.001


def edge_weight(
    length_m: float,
    shade_fraction: float,
    alpha: float,
    *,
    beta: float | None = None,
) -> float:
    beta = beta if beta is not None else float(os.environ.get("SUN_AVERSION_BETA", "5.0"))
    shade_tiebreak = float(os.environ.get("SHADE_DISTANCE_TIEBREAK", str(SHADE_DISTANCE_TIEBREAK)))
    alpha = max(0.0, min(1.0, alpha))
    l_sun = length_m * (1.0 - shade_fraction)
    l_shade = length_m * shade_fraction
    shade_cost = l_sun * beta + l_shade * shade_tiebreak
    return alpha * length_m + (1.0 - alpha) * shade_cost
