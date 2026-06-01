# Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
from __future__ import annotations

import os

SHADE_DISTANCE_TIEBREAK = 0.001
SHADE_BIAS_CURVE = 3.0


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def shade_bias_for_alpha(alpha: float) -> float:
    alpha = max(0.0, min(1.0, alpha))
    curve = max(0.1, _float_env("SHADE_BIAS_CURVE", SHADE_BIAS_CURVE))
    return (1.0 - alpha) ** curve


def edge_weight(
    length_m: float,
    shade_fraction: float,
    alpha: float,
    *,
    beta: float | None = None,
) -> float:
    beta = beta if beta is not None else _float_env("SUN_AVERSION_BETA", 5.0)
    shade_tiebreak = _float_env("SHADE_DISTANCE_TIEBREAK", SHADE_DISTANCE_TIEBREAK)
    alpha = max(0.0, min(1.0, alpha))
    shade_bias = shade_bias_for_alpha(alpha)
    distance_bias = 1.0 - shade_bias
    l_sun = length_m * (1.0 - shade_fraction)
    l_shade = length_m * shade_fraction
    shade_cost = l_sun * beta + l_shade * shade_tiebreak
    return distance_bias * length_m + shade_bias * shade_cost
