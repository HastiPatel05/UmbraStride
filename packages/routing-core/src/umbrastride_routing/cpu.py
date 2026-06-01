# Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
"""CPU parallelism helpers — default to all available cores."""

from __future__ import annotations

import os


def available_cores() -> int:
    return os.cpu_count() or 4


def worker_count(
    env_var: str,
    *,
    default: int | None = None,
    cap: int | None = None,
    minimum: int = 1,
) -> int:
    """
    Resolve worker count from environment.

    - Unset or ``0`` → use all CPU cores (``os.cpu_count()``).
    - Positive integer → use that many workers.
    """
    raw = os.environ.get(env_var, "").strip()
    if raw == "" or raw == "0":
        n = default if default is not None else available_cores()
    else:
        n = int(raw)
    if cap is not None:
        n = min(n, cap)
    return max(minimum, n)
