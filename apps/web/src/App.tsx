import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import MapView from "./MapView";
import {
  fetchArizonaRegion,
  fetchAois,
  fetchGraph,
  fetchRoute,
  type RouteResult,
} from "./api";

const DEFAULT_AOI = import.meta.env.VITE_DEFAULT_AOI || "az-phoenix-core";
const PHOENIX_CENTER: [number, number] = [-112.07404, 33.44838];

function pointInBbox(lng: number, lat: number, bbox: number[]): boolean {
  const [west, south, east, north] = bbox;
  return lng >= west && lng <= east && lat >= south && lat <= north;
}

function toLocalDatetimeValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function App() {
  const [aoiId, setAoiId] = useState(DEFAULT_AOI);
  const [mapCenter, setMapCenter] = useState<[number, number]>(PHOENIX_CENTER);
  const [mapZoom, setMapZoom] = useState(16);
  const [origin, setOrigin] = useState<[number, number] | null>([
    PHOENIX_CENTER[0] - 0.003,
    PHOENIX_CENTER[1] - 0.002,
  ]);
  const [destination, setDestination] = useState<[number, number] | null>([
    PHOENIX_CENTER[0] + 0.004,
    PHOENIX_CENTER[1] + 0.003,
  ]);
  const [pickMode, setPickMode] = useState<"origin" | "destination">("origin");
  const [datetime, setDatetime] = useState(toLocalDatetimeValue(new Date()));
  const [alpha, setAlpha] = useState(0.35);
  const [routes, setRoutes] = useState<RouteResult[]>([]);
  const [shadeCacheNote, setShadeCacheNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { data: region } = useQuery({
    queryKey: ["region", "arizona"],
    queryFn: fetchArizonaRegion,
  });

  const { data: aoisData } = useQuery({
    queryKey: ["aois"],
    queryFn: fetchAois,
  });

  const bootstrapped = useMemo(
    () => new Set(aoisData?.aois?.map((a) => a.aoi_id) ?? []),
    [aoisData]
  );

  const { data: graph, error: graphError } = useQuery({
    queryKey: ["graph", aoiId],
    queryFn: () => fetchGraph(aoiId),
    retry: false,
  });

  useEffect(() => {
    if (!region) return;
    const preset = region.presets.find((p) => p.aoi_id === aoiId);
    if (preset) {
      const [w, s, e, n] = preset.bbox;
      setMapCenter([(w + e) / 2, (s + n) / 2]);
      setMapZoom(region.default_zoom ?? 16);
    }
  }, [aoiId, region]);

  const datetimeIso = useMemo(() => new Date(datetime).toISOString(), [datetime]);

  const presetOptions = region?.presets ?? [];
  const activePreset = presetOptions.find((p) => p.aoi_id === aoiId);

  const onPickPoint = useCallback(
    (kind: "origin" | "destination", lng: number, lat: number) => {
      if (kind === "origin") setOrigin([lng, lat]);
      else setDestination([lng, lat]);
    },
    []
  );

  const findRoutes = async () => {
    if (!origin || !destination) {
      setError("Set origin and destination on the map");
      return;
    }
    const preset = presetOptions.find((p) => p.aoi_id === aoiId);
    if (preset) {
      const inOrigin = pointInBbox(origin[0], origin[1], preset.bbox);
      const inDest = pointInBbox(destination[0], destination[1], preset.bbox);
      if (!inOrigin || !inDest) {
        setError(
          `Origin or destination is outside "${preset.name}". Move both points inside that metro ` +
            `(blue outline on map) or pick another metro from the list.`
        );
        return;
      }
    }

    if (aoiId === "demo") {
      setError(
        'AOI "demo" is the old Munich sample and does not cover Arizona. Select "Phoenix downtown (fast)" or run bootstrap_arizona.'
      );
      return;
    }

    if (!bootstrapped.has(aoiId)) {
      setError(`Graph not loaded for ${aoiId}. Run: python scripts/bootstrap_arizona.py --preset ${aoiId}`);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await fetchRoute({
        aoi_id: aoiId,
        origin: { lng: origin[0], lat: origin[1] },
        destination: { lng: destination[0], lat: destination[1] },
        datetime: datetimeIso,
        alpha,
      });
      setRoutes(result.routes);
      if (result.shade_cache_exact === false && result.shade_ts_bucket) {
        setShadeCacheNote(
          `Shade data from nearest cached hour (${result.shade_ts_bucket}). ` +
            `Run seed_demo_cache.py for your selected time, or match the datetime picker.`
        );
      } else {
        setShadeCacheNote(null);
      }
      if (result.aoi_id && result.aoi_id !== aoiId) {
        setAoiId(result.aoi_id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Route failed");
      setRoutes([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <aside className="panel">
        <h1>UmbraStride</h1>
        <p className="subtitle">Arizona · shadow-oriented walking</p>

        <div className="field">
          <label>Metro / AOI (Arizona)</label>
          <select value={aoiId} onChange={(e) => setAoiId(e.target.value)}>
            {presetOptions.map((p) => (
              <option key={p.aoi_id} value={p.aoi_id}>
                {p.name}
                {!bootstrapped.has(p.aoi_id) ? " (not bootstrapped)" : ""}
              </option>
            ))}
            {aoisData?.aois
              ?.filter((a) => !presetOptions.some((p) => p.aoi_id === a.aoi_id))
              .map((a) => (
                <option key={a.aoi_id} value={a.aoi_id}>
                  {a.aoi_id}
                </option>
              ))}
          </select>
        </div>

        {graphError && (
          <p className="error">
            No graph for {aoiId}. Run:{" "}
            <code>python scripts/bootstrap_arizona.py --preset {aoiId}</code>
          </p>
        )}

        <div className="field">
          <label>Click map to set</label>
          <div className="pick-toggle">
            <button
              type="button"
              data-mode="origin"
              className={pickMode === "origin" ? "active" : ""}
              onClick={() => setPickMode("origin")}
            >
              Origin
            </button>
            <button
              type="button"
              data-mode="destination"
              className={pickMode === "destination" ? "active" : ""}
              onClick={() => setPickMode("destination")}
            >
              Destination
            </button>
          </div>
          <p className="pick-hint" style={{ marginTop: "0.35rem" }}>
            Select Origin or Destination, then click anywhere on the map.
          </p>
        </div>

        <div className="field">
          <label>Date & time (local)</label>
          <input
            type="datetime-local"
            value={datetime}
            onChange={(e) => setDatetime(e.target.value)}
          />
        </div>

        <div className="field">
          <label>Preference: cooler ← → shorter</label>
          <div className="alpha-row">
            <span>Shade</span>
            <span>{Math.round((1 - alpha) * 100)}% shade bias</span>
            <span>Short</span>
          </div>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={alpha}
            onChange={(e) => setAlpha(Number(e.target.value))}
          />
        </div>

        <button className="btn" onClick={findRoutes} disabled={loading}>
          {loading ? "Routing…" : "Find routes"}
        </button>

        {error && <p className="error">{error}</p>}
        {shadeCacheNote && <p className="hint">{shadeCacheNote}</p>}

        <div className="routes-list">
          {routes.map((r) => (
            <div key={`${r.label}-${r.alpha}`} className={`route-card ${r.label}`}>
              <h3>
                {r.label === "shortest"
                  ? "Shortest"
                  : r.label === "coolest"
                    ? "Coolest"
                    : `Your route (α=${r.alpha})`}
              </h3>
              <p>
                {r.distance_m} m · {Math.round(r.shade_fraction * 100)}% shade · detour{" "}
                {Math.round((r.detour_ratio - 1) * 100)}%
              </p>
            </div>
          ))}
        </div>

        <p className="hint">
          Full state: <code>python scripts/bootstrap_arizona.py --preset all</code>
          <br />
          One metro: <code>python scripts/bootstrap_arizona.py --preset az-phoenix</code>
          <br />
          Grid tiles: <code>python scripts/bootstrap_arizona.py --list-tiles</code>
        </p>
      </aside>
      <main>
        <MapView
          graph={graph ?? null}
          routes={routes}
          origin={origin}
          destination={destination}
          onPickPoint={onPickPoint}
          pickMode={pickMode}
          datetime={datetimeIso}
          center={mapCenter}
          zoom={mapZoom}
          stateBbox={region?.bbox}
          metroBbox={activePreset?.bbox}
        />
      </main>
    </div>
  );
}
