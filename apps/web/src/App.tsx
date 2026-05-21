import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import MapView from "./MapView";
import { fetchAois, fetchGraph, fetchRoute, type RouteResult } from "./api";

const DEFAULT_AOI = import.meta.env.VITE_DEFAULT_AOI || "demo";

function toLocalDatetimeValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function App() {
  const [aoiId, setAoiId] = useState(DEFAULT_AOI);
  const [origin, setOrigin] = useState<[number, number] | null>([11.578, 48.1365]);
  const [destination, setDestination] = useState<[number, number] | null>([11.582, 48.139]);
  const [pickMode, setPickMode] = useState<"origin" | "destination">("origin");
  const [datetime, setDatetime] = useState(toLocalDatetimeValue(new Date()));
  const [alpha, setAlpha] = useState(0.35);
  const [routes, setRoutes] = useState<RouteResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { data: aoisData } = useQuery({
    queryKey: ["aois"],
    queryFn: fetchAois,
  });

  const { data: graph } = useQuery({
    queryKey: ["graph", aoiId],
    queryFn: () => fetchGraph(aoiId),
    retry: false,
  });

  const datetimeIso = useMemo(() => {
    const d = new Date(datetime);
    return d.toISOString();
  }, [datetime]);

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
        <p className="subtitle">Shadow-oriented pedestrian navigation</p>

        <div className="field">
          <label>Area (AOI)</label>
          <select value={aoiId} onChange={(e) => setAoiId(e.target.value)}>
            <option value={DEFAULT_AOI}>{DEFAULT_AOI}</option>
            {aoisData?.aois
              ?.filter((a) => a.aoi_id !== DEFAULT_AOI)
              .map((a) => (
                <option key={a.aoi_id} value={a.aoi_id}>
                  {a.aoi_id}
                </option>
              ))}
          </select>
        </div>

        <div className="field">
          <label>Set point</label>
          <select value={pickMode} onChange={(e) => setPickMode(e.target.value as "origin" | "destination")}>
            <option value="origin">Origin</option>
            <option value="destination">Destination</option>
          </select>
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
          Bootstrap: <code>python scripts/bootstrap_aoi.py --name demo --bbox …</code>
          <br />
          Cache: <code>python scripts/seed_demo_cache.py --aoi demo</code>
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
        />
      </main>
    </div>
  );
}
