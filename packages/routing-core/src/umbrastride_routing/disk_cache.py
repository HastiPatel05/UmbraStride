from __future__ import annotations

import hashlib
import os
import pickle
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

from umbrastride_geo.aoi import resolve_data_dir, routing_cache_dir
from umbrastride_routing.graph_build import alpha_weight_key

ROUTING_CACHE_VERSION = 3


@dataclass(frozen=True)
class RoutingCacheKey:
    aoi_id: str
    graph_mtime: float
    shade_mtime: float
    resolved_bucket: str
    alphas: tuple[float, ...]
    uniform_full_shade: bool = False

    def digest(self) -> str:
        raw = (
            f"v{ROUTING_CACHE_VERSION}|{self.graph_mtime}|{self.shade_mtime}|"
            f"{self.resolved_bucket}|{self.uniform_full_shade}|"
            f"{','.join(str(a) for a in self.alphas)}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:20]

    def path(self, data_dir: Path | None = None) -> Path:
        data_dir = data_dir or resolve_data_dir()
        return routing_cache_dir(data_dir, self.aoi_id) / f"{self.digest()}.routing.pkl"


def routing_cache_enabled() -> bool:
    return os.environ.get("ROUTING_DISK_CACHE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def load_routing_digraph(key: RoutingCacheKey) -> nx.DiGraph | None:
    if not routing_cache_enabled():
        return None
    path = key.path()
    if not path.exists():
        return None
    try:
        with path.open("rb") as fh:
            payload = pickle.load(fh)
    except (OSError, pickle.UnpicklingError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("version") != ROUTING_CACHE_VERSION:
        return None
    if payload.get("cache_key") != key.digest():
        return None
    digraph = payload.get("digraph")
    if not isinstance(digraph, nx.DiGraph):
        return None
    return digraph


def save_routing_digraph(key: RoutingCacheKey, digraph: nx.DiGraph) -> Path | None:
    if not routing_cache_enabled():
        return None
    path = key.path()
    payload = {
        "version": ROUTING_CACHE_VERSION,
        "cache_key": key.digest(),
        "aoi_id": key.aoi_id,
        "resolved_bucket": key.resolved_bucket,
        "alphas": key.alphas,
        "digraph": digraph,
    }
    tmp = path.with_suffix(".tmp")
    with tmp.open("wb") as fh:
        pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)
    return path
