const API_BASE = import.meta.env.VITE_API_URL || "/api";

export type LngLat = { lng: number; lat: number };

export type RouteResult = {
  label: string;
  alpha: number;
  geometry: GeoJSON.LineString | null;
  distance_m: number;
  shade_fraction: number;
  detour_ratio: number;
  ts_bucket: string;
};

export async function fetchRoute(params: {
  aoi_id: string;
  origin: LngLat;
  destination: LngLat;
  datetime: string;
  alpha: number;
}): Promise<{ routes: RouteResult[]; ts_bucket: string }> {
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
