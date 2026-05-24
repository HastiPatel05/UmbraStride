const API_BASE = import.meta.env.VITE_API_URL || "/api";

export type LngLat = { lng: number; lat: number };

export type SnappedPoint = LngLat & { distance_m: number };

export type RouteResult = {
  label: string;
  alpha: number;
  geometry: GeoJSON.LineString | null;
  distance_m: number;
  shade_fraction: number;
  detour_ratio: number;
  ts_bucket: string;
};

export type ArizonaPreset = {
  aoi_id: string;
  name: string;
  bbox: number[];
  description?: string;
};

export type ArizonaRegion = {
  region_id: string;
  name: string;
  bbox: number[];
  default_aoi: string;
  default_center: [number, number];
  default_zoom: number;
  presets: ArizonaPreset[];
  tile_count?: number;
  bootstrapped_aois?: string[];
};

export async function fetchArizonaRegion(): Promise<ArizonaRegion> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/v1/regions/arizona`);
  } catch {
    throw new Error("Cannot reach API — start uvicorn on port 8000, then retry");
  }
  if (!res.ok) {
    throw new Error(`Failed to load Arizona region (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchRoute(params: {
  aoi_id?: string;
  origin: LngLat;
  destination: LngLat;
  datetime: string;
  alpha?: number;
}): Promise<{
  routes: RouteResult[];
  ts_bucket: string;
  shade_ts_bucket?: string;
  shade_cache_exact?: boolean;
  sun_below_horizon?: boolean;
  aoi_id?: string;
  origin_snapped?: SnappedPoint;
  destination_snapped?: SnappedPoint;
}> {
  const res = await fetch(`${API_BASE}/v1/route`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || res.statusText);
  }
  return res.json();
}

export async function syncShadeCache(
  aoiId: string,
  datetime: string,
  force = false
): Promise<{ status: string; seeded: boolean; ts_bucket: string }> {
  const res = await fetch(`${API_BASE}/v1/aoi/${aoiId}/shade/sync`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ datetime, force }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || res.statusText);
  }
  return res.json();
}

export async function fetchGraph(aoiId: string): Promise<GeoJSON.FeatureCollection> {
  const res = await fetch(`${API_BASE}/v1/aoi/${aoiId}/graph`);
  if (!res.ok) throw new Error("Failed to load graph");
  return res.json();
}

export async function fetchAois(): Promise<{ aois: { aoi_id: string; bbox?: number[] }[] }> {
  const res = await fetch(`${API_BASE}/v1/aoi`);
  if (!res.ok) return { aois: [] };
  return res.json();
}
