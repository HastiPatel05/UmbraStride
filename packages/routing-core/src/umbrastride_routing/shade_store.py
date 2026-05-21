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

    def get_fraction(self, edge_key: str, ts_bucket: str, default: float = 0.5) -> float:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                """
                SELECT shade_fraction FROM edge_shade
                WHERE aoi_id = ? AND edge_key = ? AND ts_bucket = ?
                """,
                (self.aoi_id, edge_key, ts_bucket),
            ).fetchone()
        return float(row[0]) if row else default

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
