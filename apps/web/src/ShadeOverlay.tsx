/**
 * Live building shadows on the map — no ShadeMap API.
 * Sun position: SunCalc (browser). Routing uses Python `astral` (same astronomy).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type maplibregl from "maplibre-gl";
import { buildingShadowsGeoJSON } from "./buildingShadows";
import {
  type BuildingFeature,
  fetchBuildingsForMap,
  parseHeightMeters,
  SHADE_MIN_ZOOM,
  waitForMapLoaded,
  waitForMapStyleReady,
} from "./buildings";
import { BUILDINGS_3D_LAYER_ID } from "./mapStyle";
import { getSunPosition } from "./sun";

type Props = {
  map: maplibregl.Map | null;
  datetime: string;
  opacity?: number;
};

const SHADOW_SOURCE_ID = "building-shadows";
const SHADOW_LAYER_ID = "building-shadows-fill";
const REFRESH_DEBOUNCE_MS = 800;

function placeShadowLayersBelowBuildings(map: maplibregl.Map): void {
  if (!map.getLayer(BUILDINGS_3D_LAYER_ID)) return;
  if (map.getLayer(SHADOW_LAYER_ID)) {
    map.moveLayer(SHADOW_LAYER_ID, BUILDINGS_3D_LAYER_ID);
  }
}

function ensureShadowLayer(map: maplibregl.Map, opacity: number): void {
  const empty: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

  if (!map.getSource(SHADOW_SOURCE_ID)) {
    map.addSource(SHADOW_SOURCE_ID, { type: "geojson", data: empty });
  }

  const beforeId = map.getLayer(BUILDINGS_3D_LAYER_ID)
    ? BUILDINGS_3D_LAYER_ID
    : undefined;

  if (!map.getLayer(SHADOW_LAYER_ID)) {
    map.addLayer(
      {
        id: SHADOW_LAYER_ID,
        type: "fill",
        source: SHADOW_SOURCE_ID,
        paint: {
          "fill-color": "#030711",
          "fill-opacity": opacity,
          "fill-antialias": true,
        },
      },
      beforeId
    );
  } else {
    map.setPaintProperty(SHADOW_LAYER_ID, "fill-opacity", opacity);
  }

  placeShadowLayersBelowBuildings(map);
}

function clearShadowLayer(map: maplibregl.Map): void {
  const src = map.getSource(SHADOW_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
  src?.setData({ type: "FeatureCollection", features: [] });
}

function removeShadowLayer(map: maplibregl.Map): void {
  if (map.getLayer(SHADOW_LAYER_ID)) map.removeLayer(SHADOW_LAYER_ID);
  if (map.getSource(SHADOW_SOURCE_ID)) map.removeSource(SHADOW_SOURCE_ID);
}

function shadowBudgetForZoom(zoom: number): number {
  if (zoom < 16) return 120;
  if (zoom < 17) return 180;
  return 260;
}

function mapViewCacheKey(map: maplibregl.Map): string {
  const b = map.getBounds();
  const round = (n: number) => n.toFixed(4);
  return [
    Math.floor(map.getZoom() * 2) / 2,
    round(b.getWest()),
    round(b.getSouth()),
    round(b.getEast()),
    round(b.getNorth()),
  ].join("|");
}

export default function ShadeOverlay({ map, datetime, opacity = 0.46 }: Props) {
  const mapboxToken = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;
  const datetimeRef = useRef(datetime);
  datetimeRef.current = datetime;

  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const refreshGenRef = useRef(0);
  const buildingCacheRef = useRef<{
    key: string;
    buildings: BuildingFeature[];
  } | null>(null);

  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [zoomOk, setZoomOk] = useState(true);
  const [buildingCount, setBuildingCount] = useState(0);
  const [shadowCount, setShadowCount] = useState(0);
  const [nightMode, setNightMode] = useState(false);
  const [sunLabel, setSunLabel] = useState("");
  const [hint, setHint] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const refreshShadows = useCallback(async () => {
    if (!map) return;

    const zoom = map.getZoom();
    const center = map.getCenter();
    const sun = getSunPosition(datetimeRef.current, center.lat, center.lng);
    setNightMode(sun.belowHorizon);
    setSunLabel(
      sun.belowHorizon
        ? "Sun below horizon"
        : `Sun ${sun.altitudeDeg.toFixed(0)}° alt`
    );

    if (sun.belowHorizon) {
      clearShadowLayer(map);
      setBuildingCount(0);
      setShadowCount(0);
      setHint(null);
      setStatus("ready");
      return;
    }

    const ok = zoom >= SHADE_MIN_ZOOM;
    setZoomOk(ok);

    if (!ok) {
      clearShadowLayer(map);
      setBuildingCount(0);
      setShadowCount(0);
      setNightMode(false);
      setHint(`Zoom in to level ${SHADE_MIN_ZOOM}+ (current ${zoom.toFixed(1)})`);
      setStatus("ready");
      return;
    }

    const gen = ++refreshGenRef.current;

    try {
      await waitForMapLoaded(map);
      if (gen !== refreshGenRef.current) return;

      ensureShadowLayer(map, opacity);

      const cacheKey = mapViewCacheKey(map);
      let buildings = buildingCacheRef.current?.key === cacheKey
        ? buildingCacheRef.current.buildings
        : null;
      if (!buildings) {
        buildings = await fetchBuildingsForMap(map, mapboxToken);
        buildingCacheRef.current = { key: cacheKey, buildings };
      }
      if (gen !== refreshGenRef.current) return;

      setBuildingCount(buildings.length);

      let byHeight = [...buildings].sort(
        (a, b) =>
          parseHeightMeters((b.properties ?? {}) as Record<string, unknown>) -
          parseHeightMeters((a.properties ?? {}) as Record<string, unknown>)
      );
      const shadowBudget = shadowBudgetForZoom(zoom);
      let fc = buildingShadowsGeoJSON(byHeight.slice(0, shadowBudget), sun);
      let nShadowBuildings = fc.features.length;
      let usedOverpassFallback = false;

      if (nShadowBuildings === 0 && buildings.length > 0 && sun.altitudeDeg <= 55) {
        const fallbackBuildings = await fetchBuildingsForMap(map, mapboxToken, {
          includeOverpass: true,
        });
        if (gen !== refreshGenRef.current) return;
        usedOverpassFallback = true;
        if (fallbackBuildings.length > 0) {
          buildings = fallbackBuildings;
          buildingCacheRef.current = { key: cacheKey, buildings };
          setBuildingCount(buildings.length);
          byHeight = [...buildings].sort(
            (a, b) =>
              parseHeightMeters((b.properties ?? {}) as Record<string, unknown>) -
              parseHeightMeters((a.properties ?? {}) as Record<string, unknown>)
          );
          fc = buildingShadowsGeoJSON(byHeight.slice(0, shadowBudget), sun);
          nShadowBuildings = fc.features.length;
        }
      }
      setShadowCount(nShadowBuildings);

      const src = map.getSource(SHADOW_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
      src?.setData(fc);
      map.triggerRepaint();

      if (buildings.length === 0) {
        setHint("No usable building footprints loaded here — zoom in, wait for tiles, or pan slightly");
      } else if (nShadowBuildings === 0) {
        setHint(
          sun.altitudeDeg > 55
            ? "Sun is high — shadows are very short; try morning or late afternoon"
            : usedOverpassFallback
              ? "No usable shadow geometry from local or Overpass footprints — try panning slightly"
              : "No usable shadow geometry from map tile buildings — try panning slightly"
        );
      } else if (sun.altitudeDeg > 50) {
        setHint("Tip: lower sun (morning/evening) casts longer, clearer shadows");
      } else {
        setHint(null);
      }

      setStatus("ready");
      setErrorMsg(null);
    } catch (e) {
      if (gen !== refreshGenRef.current) return;
      const msg = e instanceof Error ? e.message : "Shadow update failed";
      setStatus("error");
      setNightMode(false);
      setErrorMsg(msg);
      setHint(null);
      console.warn("Shadow refresh:", e);
    }
  }, [map, mapboxToken, opacity]);

  const scheduleRefresh = useCallback(() => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    refreshTimerRef.current = setTimeout(() => {
      void refreshShadows();
    }, REFRESH_DEBOUNCE_MS);
  }, [refreshShadows]);

  useEffect(() => {
    if (!map) {
      setStatus("loading");
      return;
    }

    let cancelled = false;

    const init = async () => {
      try {
        await waitForMapStyleReady(map);
        if (cancelled) return;
        await refreshShadows();
      } catch (e) {
        if (!cancelled) {
          setStatus("error");
          setErrorMsg(e instanceof Error ? e.message : "Shadow init failed");
        }
      }
    };

    const onMapChange = () => scheduleRefresh();
    const onStyleData = () => {
      if (map.isStyleLoaded() && map.getLayer(BUILDINGS_3D_LAYER_ID)) {
        buildingCacheRef.current = null;
        scheduleRefresh();
      }
    };

    void init();
    map.on("moveend", onMapChange);
    map.on("zoomend", onMapChange);
    map.on("styledata", onStyleData);

    return () => {
      cancelled = true;
      refreshGenRef.current += 1;
      buildingCacheRef.current = null;
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
      map.off("moveend", onMapChange);
      map.off("zoomend", onMapChange);
      map.off("styledata", onStyleData);
      removeShadowLayer(map);
    };
  }, [map, scheduleRefresh, refreshShadows]);

  useEffect(() => {
    if (!map) return;
    void refreshShadows();
  }, [datetime, map, refreshShadows]);

  return (
    <>
      {status === "loading" && <div className="shade-banner">Computing shadows…</div>}
      {status === "error" && (
        <div className="shade-banner shade-banner-warn">{errorMsg}</div>
      )}
      {status === "ready" && nightMode && <div className="night-shade-wash" />}
      {status === "ready" && nightMode && (
        <div className="shade-banner shade-banner-ok">
          Night shade · {sunLabel} · {new Date(datetime).toLocaleString()}
        </div>
      )}
      {status === "ready" && hint && (
        <div className="shade-banner shade-banner-warn">{hint}</div>
      )}
      {status === "ready" && !nightMode && !hint && zoomOk && shadowCount > 0 && (
        <div className="shade-banner shade-banner-ok">
          Geometric shadows · {shadowCount}/{buildingCount} buildings · {sunLabel} ·{" "}
          {new Date(datetime).toLocaleString()}
        </div>
      )}
    </>
  );
}
