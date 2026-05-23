from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from umbrastride_geo.aoi import resolve_data_dir


def floor_ts_bucket(dt: datetime, minutes: int = 15) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    minute = (dt.minute // minutes) * minutes
    floored = dt.replace(minute=minute, second=0, microsecond=0)
    return floored.strftime("%Y-%m-%dT%H:%M")


def _parse_bucket(ts_bucket: str) -> datetime:
    """Parse ``YYYY-MM-DDTHH:MM`` bucket to UTC datetime."""
    if len(ts_bucket) == 16:
        return datetime.fromisoformat(f"{ts_bucket}:00+00:00")
    return datetime.fromisoformat(ts_bucket.replace("Z", "+00:00")).astimezone(timezone.utc)


class ShadeStore:
    def __init__(self, aoi_id: str, *, data_dir: Path | None = None):
        data_dir = data_dir or resolve_data_dir()
        cache_dir = data_dir / "shade-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.aoi_id = aoi_id
        self.path = cache_dir / f"{aoi_id}.sqlite"
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS edge_shade (
                    aoi_id TEXT NOT NULL,
                    edge_key TEXT NOT NULL,
                    ts_bucket TEXT NOT NULL,
                    shade_fraction REAL NOT NULL,
                    sample_count INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (aoi_id, edge_key, ts_bucket)
                )
                """
            )
            conn.commit()

    def list_buckets(self) -> list[str]:
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                "SELECT DISTINCT ts_bucket FROM edge_shade WHERE aoi_id = ? ORDER BY ts_bucket",
                (self.aoi_id,),
            ).fetchall()
        return [r[0] for r in rows]

    def resolve_bucket(self, ts_bucket: str) -> tuple[str, dict[str, float], bool]:
        """
        Load shade for ``ts_bucket``, or the nearest cached hour if missing.

        Returns ``(resolved_bucket, shade_map, exact_match)``.
        """
        data = self.load_bucket(ts_bucket)
        if data:
            return ts_bucket, data, True

        buckets = self.list_buckets()
        if not buckets:
            return ts_bucket, {}, False

        target = _parse_bucket(ts_bucket)
        nearest = min(
            buckets,
            key=lambda b: abs((_parse_bucket(b) - target).total_seconds()),
        )
        return nearest, self.load_bucket(nearest), False

    def load_bucket(self, ts_bucket: str) -> dict[str, float]:
        """Load all shade fractions for a time bucket in one query."""
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                """
                SELECT edge_key, shade_fraction FROM edge_shade
                WHERE aoi_id = ? AND ts_bucket = ?
                """,
                (self.aoi_id, ts_bucket),
            ).fetchall()
        return {ek: float(sf) for ek, sf in rows}

    def load_bucket_array(
        self,
        ts_bucket: str,
        n_edges: int,
        key_to_index: dict[str, int],
        default: float = 0.5,
    ) -> np.ndarray:
        """Load shade into a dense float32 array indexed by edge_key order."""
        import numpy as np

        arr = np.full(n_edges, default, dtype=np.float32)
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                """
                SELECT edge_key, shade_fraction FROM edge_shade
                WHERE aoi_id = ? AND ts_bucket = ?
                """,
                (self.aoi_id, ts_bucket),
            ).fetchall()
        for ek, sf in rows:
            idx = key_to_index.get(ek)
            if idx is not None and 0 <= idx < n_edges:
                arr[idx] = float(sf)
        return arr

    def resolve_bucket_array(
        self,
        ts_bucket: str,
        n_edges: int,
        key_to_index: dict[str, int],
        default: float = 0.5,
    ) -> tuple[str, np.ndarray, bool]:
        """
        Load shade array for ``ts_bucket``, or the nearest cached hour if missing.

        Returns ``(resolved_bucket, shade_array, exact_match)``.
        """
        if self.load_bucket(ts_bucket):
            return (
                ts_bucket,
                self.load_bucket_array(ts_bucket, n_edges, key_to_index, default),
                True,
            )

        buckets = self.list_buckets()
        if not buckets:
            return (
                ts_bucket,
                self.load_bucket_array(ts_bucket, n_edges, key_to_index, default),
                False,
            )

        target = _parse_bucket(ts_bucket)
        nearest = min(
            buckets,
            key=lambda b: abs((_parse_bucket(b) - target).total_seconds()),
        )
        return (
            nearest,
            self.load_bucket_array(nearest, n_edges, key_to_index, default),
            False,
        )

    def get_fraction(self, edge_key: str, ts_bucket: str, default: float = 0.5) -> float:
        resolved, data, _ = self.resolve_bucket(ts_bucket)
        return data.get(edge_key, default)

    def set_fraction(
        self, edge_key: str, ts_bucket: str, shade_fraction: float, sample_count: int = 1
    ) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO edge_shade (aoi_id, edge_key, ts_bucket, shade_fraction, sample_count)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(aoi_id, edge_key, ts_bucket) DO UPDATE SET
                    shade_fraction = excluded.shade_fraction,
                    sample_count = excluded.sample_count
                """,
                (self.aoi_id, edge_key, ts_bucket, shade_fraction, sample_count),
            )
            conn.commit()

    def bulk_set(self, rows: list[tuple[str, str, float, int]]) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.executemany(
                """
                INSERT INTO edge_shade (aoi_id, edge_key, ts_bucket, shade_fraction, sample_count)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(aoi_id, edge_key, ts_bucket) DO UPDATE SET
                    shade_fraction = excluded.shade_fraction,
                    sample_count = excluded.sample_count
                """,
                [(self.aoi_id, ek, tb, sf, sc) for ek, tb, sf, sc in rows],
            )
            conn.commit()

    def coverage(self, ts_bucket: str | None = None) -> dict:
        with sqlite3.connect(self.path) as conn:
            if ts_bucket:
                cached = conn.execute(
                    "SELECT COUNT(DISTINCT edge_key) FROM edge_shade WHERE aoi_id = ? AND ts_bucket = ?",
                    (self.aoi_id, ts_bucket),
                ).fetchone()[0]
            else:
                cached = conn.execute(
                    "SELECT COUNT(DISTINCT edge_key) FROM edge_shade WHERE aoi_id = ?",
                    (self.aoi_id,),
                ).fetchone()[0]
            buckets = [
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT ts_bucket FROM edge_shade WHERE aoi_id = ? ORDER BY ts_bucket",
                    (self.aoi_id,),
                ).fetchall()
            ]
        return {"cached_edges": cached, "ts_buckets": buckets}
