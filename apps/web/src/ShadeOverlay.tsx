/**
 * Live 2.5D building shadows via ShadeMap (mapbox-gl-shadow-simulator).
 * Requires VITE_SHADEMAP_API_KEY — https://shademap.app/about/
 */
import { useEffect, useRef, useState } from "react";
import type maplibregl from "maplibre-gl";
import { fetchBuildingsForMap, SHADE_MIN_ZOOM } from "./buildings";

type ShadeMapInstance = {
  addTo: (map: maplibregl.Map) => ShadeMapInstance;
  remove: () => void;
  setDate: (date: Date) => void;
  setOpacity: (opacity: number) => void;
};

type Props = {
  map: maplibregl.Map | null;
  datetime: string;
  opacity?: number;
};

const TERRAIN_SOURCE = {
  tileSize: 256,
  maxZoom: 15,
  getSourceUrl: ({ x, y, z }: { x: number; y: number; z: number }) =>
    `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/${z}/${x}/${y}.png`,
  getElevation: ({ r, g, b }: { r: number; g: number; b: number }) =>
    (r * 256 + g + b / 256) - 32768,
};

export default function ShadeOverlay({ map, datetime, opacity = 0.5 }: Props) {
  const apiKey = import.meta.env.VITE_SHADEMAP_API_KEY;
  const mapboxToken = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;

  const shadeRef = useRef<ShadeMapInstance | null>(null);
  const datetimeRef = useRef(datetime);
  datetimeRef.current = datetime;

  const [status, setStatus] = useState<"off" | "loading" | "ready" | "error">(
    apiKey ? "loading" : "off"
  );
  const [zoomOk, setZoomOk] = useState(true);
  const [buildingCount, setBuildingCount] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!map || !apiKey) {
      setStatus("off");
      return;
    }

    let cancelled = false;
    setStatus("loading");
    setErrorMsg(null);

    const getFeatures = async () => {
      if (!map || map.getZoom() < SHADE_MIN_ZOOM) return [];
      try {
        const features = await fetchBuildingsForMap(map, mapboxToken);
        if (!cancelled) setBuildingCount(features.length);
        return features;
      } catch (e) {
        console.warn("Building fetch failed:", e);
        if (!cancelled) setBuildingCount(0);
        return [];
      }
    };

    const updateZoomState = () => {
      const ok = map.getZoom() >= SHADE_MIN_ZOOM;
      setZoomOk(ok);
      return ok;
    };

    const refreshShadows = () => {
      if (shadeRef.current && updateZoomState()) {
        shadeRef.current.setDate(new Date(datetimeRef.current));
      }
    };

    const onMapChange = () => {
      updateZoomState();
      refreshShadows();
    };

    (async () => {
      try {
        const mod = await import("mapbox-gl-shadow-simulator");
        const ShadeMap = mod.default as new (
          opts: import("mapbox-gl-shadow-simulator").ShadeMapOptions
        ) => ShadeMapInstance;
        if (cancelled) return;

        shadeRef.current?.remove();
        const shadeMap = new ShadeMap({
          apiKey,
          date: new Date(datetimeRef.current),
          color: "#0a1628",
          opacity,
          terrainSource: TERRAIN_SOURCE,
          getFeatures,
        });

        shadeMap.addTo(map);
        shadeRef.current = shadeMap;
        setStatus("ready");
        updateZoomState();

        map.on("moveend", onMapChange);
        map.on("zoomend", onMapChange);
      } catch (e) {
        if (!cancelled) {
          setStatus("error");
          setErrorMsg(e instanceof Error ? e.message : "ShadeMap failed to load");
        }
      }
    })();

    return () => {
      cancelled = true;
      map.off("moveend", onMapChange);
      map.off("zoomend", onMapChange);
      shadeRef.current?.remove();
      shadeRef.current = null;
    };
  }, [map, apiKey, mapboxToken, opacity]);

  useEffect(() => {
    if (status !== "ready" || !shadeRef.current || !map) return;
    if (map.getZoom() >= SHADE_MIN_ZOOM) {
      shadeRef.current.setDate(new Date(datetime));
    }
  }, [datetime, status, map]);

  if (!apiKey) {
    return (
      <div className="shade-banner shade-banner-warn">
        Add <code>VITE_SHADEMAP_API_KEY</code> in <code>apps/web/.env</code> for building shadows
      </div>
    );
  }

  return (
    <>
      {status === "loading" && <div className="shade-banner">Loading ShadeMap…</div>}
      {status === "error" && (
        <div className="shade-banner shade-banner-warn">{errorMsg}</div>
      )}
      {status === "ready" && !zoomOk && (
        <div className="shade-banner shade-banner-warn">
          Zoom in to level {SHADE_MIN_ZOOM}+ to see building shadows
        </div>
      )}
      {status === "ready" && zoomOk && (
        <div className="shade-banner shade-banner-ok">
          Shadows · {buildingCount} buildings · {new Date(datetime).toLocaleString()}
        </div>
      )}
    </>
  );
}
