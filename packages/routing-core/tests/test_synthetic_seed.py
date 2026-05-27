from datetime import datetime, timezone

from umbrastride_routing.synthetic_seed import ensure_synthetic_shade_bucket

from test_routing_graph import _synthetic_graph


def test_ensure_synthetic_shade_bucket_seeds_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _synthetic_graph(tmp_path, monkeypatch)
    dt = datetime(2026, 5, 24, 14, 30, tzinfo=timezone.utc)

    first = ensure_synthetic_shade_bucket("test", dt)
    assert first["seeded"] is True
    assert first["ts_bucket"] == "2026-05-24T14:30"

    second = ensure_synthetic_shade_bucket("test", dt)
    assert second["seeded"] is False
    assert second["coverage"] >= 0.9
