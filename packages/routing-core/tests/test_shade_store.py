# Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
from datetime import datetime, timezone

from umbrastride_routing.shade_store import ShadeStore, floor_ts_bucket


def test_resolve_bucket_nearest(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    store = ShadeStore("test-aoi")
    store.set_fraction("e1", "2026-05-22T12:00", 0.8, 5)
    store.set_fraction("e2", "2026-05-22T12:00", 0.2, 5)

    resolved, data, exact = store.resolve_bucket("2026-05-21T12:00")
    assert exact is False
    assert resolved == "2026-05-22T12:00"
    assert data["e1"] == 0.8


def test_resolve_bucket_exact(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    store = ShadeStore("test-aoi")
    tb = floor_ts_bucket(datetime(2026, 5, 22, 12, 7, tzinfo=timezone.utc))
    store.set_fraction("e1", tb, 0.6, 5)
    resolved, data, exact = store.resolve_bucket(tb)
    assert exact is True
    assert data["e1"] == 0.6
