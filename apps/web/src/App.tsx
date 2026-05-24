import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import MapView from "./MapView";
import { fetchArizonaRegion, fetchRoute, syncShadeCache, type RouteResult } from "./api";
import { resolveAoiForRoute, resolvePresetForPoint } from "./resolveAoi";

const DEFAULT_AOI = import.meta.env.VITE_DEFAULT_AOI || "az-phoenix";
const PHOENIX_CENTER: [number, number] = [-112.07, 33.48];
const PHOENIX_ZOOM = 16;
const SHADE_AUTO_SYNC_MS = 5 * 60 * 1000;

function toLocalDatetimeValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function App() {
  const [aoiId, setAoiId] = useState(DEFAULT_AOI);
  const [activePresetName, setActivePresetName] = useState<string | null>(null);
  const [mapCenter, setMapCenter] = useState<[number, number]>(PHOENIX_CENTER);
  const [mapZoom, setMapZoom] = useState(PHOENIX_ZOOM);
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
  const hasRoutesRef = useRef(false);
  hasRoutesRef.current = routes.length > 0;

  const {
    data: region,
    isError: regionLoadFailed,
    error: regionLoadError,
    isLoading: regionLoading,
    isFetching: regionFetching,
    refetch: refetchRegion,
  } = useQuery({
    queryKey: ["region", "arizona"],
    queryFn: fetchArizonaRegion,
    retry: 8,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10000),
    refetchOnWindowFocus: true,
    refetchInterval: (query) => (query.state.status === "error" ? 5000 : false),
  });

  const bootstrapped = useMemo(
    () => new Set(region?.bootstrapped_aois ?? []),
    [region?.bootstrapped_aois]
  );

  const activePreset = useMemo(
    () => region?.presets.find((p) => p.aoi_id === aoiId) ?? null,
    [region, aoiId]
  );

  const metroBbox = activePreset?.bbox;

  // Auto-select AOI from map picks (smallest metro containing both points).
  useEffect(() => {
    if (!region || !origin) return;

    let resolved: { aoiId: string; preset: { aoi_id: string; name: string; bbox: number[] } };
    if (destination) {
      resolved = resolveAoiForRoute(origin, destination, region, bootstrapped);
    } else {
      const preset = resolvePresetForPoint(origin[0], origin[1], region, bootstrapped);
      resolved = { aoiId: preset.aoi_id, preset };
    }

    setActivePresetName(resolved.preset.name);
    setAoiId((prev) => {
      if (prev !== resolved.aoiId) {
        const [w, s, e, n] = resolved.preset.bbox;
        setMapCenter([(w + e) / 2, (s + n) / 2]);
        setMapZoom(region.default_zoom ?? 16);
      }
      return resolved.aoiId;
    });
  }, [region, origin, destination, bootstrapped]);

  const datetimeIso = useMemo(() => new Date(datetime).toISOString(), [datetime]);

  const onPickPoint = useCallback(
    (kind: "origin" | "destination", lng: number, lat: number) => {
      if (kind === "origin") setOrigin([lng, lat]);
      else setDestination([lng, lat]);
    },
    []
  );

  const findRoutes = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (!origin || !destination) {
        if (!opts?.silent) setError("Set origin and destination on the map");
        return;
      }

      if (regionLoadFailed) {
        if (!opts?.silent) {
          setError(
            "Cannot reach the API at http://127.0.0.1:8000. Start it in another terminal: " +
              "source .venv/bin/activate && uvicorn umbrastride_api.main:app --reload --port 8000"
          );
        }
        return;
      }

      if (regionLoading) {
        if (!opts?.silent) setError("Loading area data from API…");
        return;
      }

      if (!bootstrapped.has(aoiId)) {
        if (!opts?.silent) {
          setError(
            `No street network for this area (${activePresetName ?? aoiId}). ` +
              `Run: python scripts/bootstrap_arizona.py --preset ${aoiId}`
          );
        }
        return;
      }

      if (!opts?.silent) {
        setLoading(true);
        setError(null);
      }
      try {
        const result = await fetchRoute({
          aoi_id: aoiId,
          origin: { lng: origin[0], lat: origin[1] },
          destination: { lng: destination[0], lat: destination[1] },
          datetime: datetimeIso,
          alpha,
        });
        setRoutes(result.routes);
        if (result.sun_below_horizon) {
          setShadeCacheNote(
            "Sun is below the horizon — coolest and shortest routes use the same distance (full shade)."
          );
        } else if (result.shade_cache_exact === false && result.shade_ts_bucket) {
          setShadeCacheNote(
            `Updating shade for ${result.ts_bucket}… (auto-sync runs every 5 min)`
          );
        } else {
          setShadeCacheNote(null);
        }
        if (result.aoi_id && result.aoi_id !== aoiId) {
          setAoiId(result.aoi_id);
          const p = region?.presets.find((x) => x.aoi_id === result.aoi_id);
          if (p) setActivePresetName(p.name);
        }
      } catch (e) {
        if (!opts?.silent) {
          setError(e instanceof Error ? e.message : "Route failed");
          setRoutes([]);
        }
      } finally {
        if (!opts?.silent) setLoading(false);
      }
    },
    [
      origin,
      destination,
      regionLoadFailed,
      regionLoading,
      bootstrapped,
      aoiId,
      activePresetName,
      datetimeIso,
      alpha,
      region?.presets,
    ]
  );

  // Auto-seed shade for the selected time; refresh every 5 minutes.
  useEffect(() => {
    if (regionLoadFailed || !bootstrapped.has(aoiId)) return;

    const sync = (refreshRoutes: boolean) => {
      // Fire-and-forget — never block routing on shade seed (can take minutes on az-phoenix).
      void syncShadeCache(aoiId, datetimeIso).then(() => {
        if (refreshRoutes && hasRoutesRef.current && origin && destination) {
          void findRoutes({ silent: true });
        }
      });
    };

    const id = window.setInterval(() => sync(true), SHADE_AUTO_SYNC_MS);
    return () => window.clearInterval(id);
  }, [
    aoiId,
    datetimeIso,
    bootstrapped,
    regionLoadFailed,
    origin,
    destination,
    findRoutes,
  ]);

  return (
    <div className="app">
      <aside className="panel">
        <h1>UmbraStride</h1>
        <p className="subtitle">Shadow-oriented walking — area picked from the map</p>

        {regionFetching && !region && (
          <p className="hint">Connecting to API…</p>
        )}

        {regionLoadFailed && !regionFetching && (
          <p className="error">
            API not reachable — start:{" "}
            <code>uvicorn umbrastride_api.main:app --reload --port 8000</code>
            {regionLoadError instanceof Error ? ` (${regionLoadError.message})` : ""}
            <button
              type="button"
              className="btn"
              style={{ marginTop: "0.5rem", width: "100%", background: "#2a3548" }}
              onClick={() => void refetchRegion()}
            >
              Retry connection
            </button>
          </p>
        )}

        {activePresetName && (
          <p className="hint" style={{ marginTop: 0 }}>
            Active area: <strong>{activePresetName}</strong>
            {!regionLoadFailed && !bootstrapped.has(aoiId) ? " (graph not loaded)" : ""}
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
            Select Origin or Destination, then click the map. The nearest metro graph is chosen
            automatically.
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

        <button className="btn" onClick={() => void findRoutes()} disabled={loading}>
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
      </aside>
      <main>
        <MapView
          routes={routes}
          origin={origin}
          destination={destination}
          onPickPoint={onPickPoint}
          pickMode={pickMode}
          datetime={datetimeIso}
          center={mapCenter}
          zoom={mapZoom}
          stateBbox={region?.bbox}
          metroBbox={metroBbox}
        />
      </main>
    </div>
  );
}
