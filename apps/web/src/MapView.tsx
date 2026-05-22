import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import type { RouteResult } from "./api";
import { getInitialMapStyle } from "./mapStyle";
import ShadeOverlay from "./ShadeOverlay";

const ROUTE_COLORS: Record<string, string> = {
  shortest: "#f97316",
  coolest: "#2dd4bf",
  custom: "#a78bfa",
};

type Props = {
  graph: GeoJSON.FeatureCollection | null;
  routes: RouteResult[];
  origin: [number, number] | null;
  destination: [number, number] | null;
  onPickPoint: (kind: "origin" | "destination", lng: number, lat: number) => void;
  pickMode: "origin" | "destination";
  datetime: string;
  center?: [number, number];
  zoom?: number;
  stateBbox?: number[];
  metroBbox?: number[];
};

export default function MapView({
  graph,
  routes,
  origin,
  destination,
  onPickPoint,
  pickMode,
  datetime,
  center = [-112.07404, 33.44838],
  zoom = 16,
  stateBbox,
  metroBbox,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const pickModeRef = useRef(pickMode);
  const onPickPointRef = useRef(onPickPoint);
  pickModeRef.current = pickMode;
  onPickPointRef.current = onPickPoint;

  const [mapInstance, setMapInstance] = useState<maplibregl.Map | null>(null);

  // Initialize map once — do NOT depend on pickMode (would destroy/recreate map + ShadeMap).
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const shadeEnabled = Boolean(import.meta.env.VITE_SHADEMAP_API_KEY);
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: getInitialMapStyle(),
      center,
      zoom,
      pitch: shadeEnabled ? 52 : 0,
      bearing: shadeEnabled ? -24 : 0,
      minZoom: 8,
      maxZoom: 20,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-left");

    map.on("click", (e) => {
      onPickPointRef.current(pickModeRef.current, e.lngLat.lng, e.lngLat.lat);
    });

    mapRef.current = map;
    setMapInstance(map);
    return () => {
      map.remove();
      mapRef.current = null;
      setMapInstance(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- center/zoom applied via flyTo effect
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.flyTo({ center, zoom, duration: 800 });
  }, [center, zoom]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !stateBbox) return;
    const applyState = () => {
      const [west, south, east, north] = stateBbox;
      const fc: GeoJSON.FeatureCollection = {
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            properties: {},
            geometry: {
              type: "LineString",
              coordinates: [
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],
              ],
            },
          },
        ],
      };
      if (map.getSource("az-state")) {
        (map.getSource("az-state") as maplibregl.GeoJSONSource).setData(fc);
      } else {
        map.addSource("az-state", { type: "geojson", data: fc });
        map.addLayer({
          id: "az-state-line",
          type: "line",
          source: "az-state",
          paint: { "line-color": "#3d9be9", "line-width": 2, "line-opacity": 0.35 },
        });
      }
    };
    if (map.isStyleLoaded()) applyState();
    else map.once("load", applyState);
  }, [stateBbox]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !metroBbox) return;
    const applyMetro = () => {
      const [west, south, east, north] = metroBbox;
      const fc: GeoJSON.FeatureCollection = {
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            properties: {},
            geometry: {
              type: "LineString",
              coordinates: [
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],
              ],
            },
          },
        ],
      };
      if (map.getSource("metro-bbox")) {
        (map.getSource("metro-bbox") as maplibregl.GeoJSONSource).setData(fc);
      } else {
        map.addSource("metro-bbox", { type: "geojson", data: fc });
        map.addLayer({
          id: "metro-bbox-fill",
          type: "fill",
          source: "metro-bbox",
          paint: { "fill-color": "#3d9be9", "fill-opacity": 0.06 },
        });
        map.addLayer({
          id: "metro-bbox-line",
          type: "line",
          source: "metro-bbox",
          paint: { "line-color": "#3d9be9", "line-width": 2, "line-opacity": 0.55 },
        });
      }
    };
    if (map.isStyleLoaded()) applyMetro();
    else map.once("load", applyMetro);
  }, [metroBbox]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const applyLayers = () => {
    const setGeo = (id: string, data: GeoJSON.FeatureCollection, color: string, width: number) => {
      if (map.getSource(id)) {
        (map.getSource(id) as maplibregl.GeoJSONSource).setData(data);
      } else {
        map.addSource(id, { type: "geojson", data });
        map.addLayer({
          id: `${id}-line`,
          type: "line",
          source: id,
          paint: { "line-color": color, "line-width": width, "line-opacity": 0.85 },
        });
      }
    };

    if (graph?.features?.length) {
      setGeo("graph", graph, "#4b5563", 1.5);
    }

    routes.forEach((r, i) => {
      if (!r.geometry) return;
      const fc: GeoJSON.FeatureCollection = {
        type: "FeatureCollection",
        features: [{ type: "Feature", properties: {}, geometry: r.geometry }],
      };
      setGeo(`route-${i}`, fc, ROUTE_COLORS[r.label] || "#a78bfa", r.label === "custom" ? 5 : 4);
    });

    const markers: GeoJSON.Feature[] = [];
    if (origin) {
      markers.push({
        type: "Feature",
        properties: { role: "origin" },
        geometry: { type: "Point", coordinates: origin },
      });
    }
    if (destination) {
      markers.push({
        type: "Feature",
        properties: { role: "dest" },
        geometry: { type: "Point", coordinates: destination },
      });
    }
    const markerFc: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: markers,
    };
    if (map.getSource("markers")) {
      (map.getSource("markers") as maplibregl.GeoJSONSource).setData(markerFc);
    } else {
      map.addSource("markers", { type: "geojson", data: markerFc });
      map.addLayer({
        id: "markers-circle",
        type: "circle",
        source: "markers",
        paint: {
          "circle-radius": 8,
          "circle-color": [
            "match",
            ["get", "role"],
            "origin",
            "#22c55e",
            "dest",
            "#ef4444",
            "#fff",
          ],
        },
      });
    }
    };

    if (map.isStyleLoaded()) applyLayers();
    else map.once("load", applyLayers);
  }, [graph, routes, origin, destination]);

  return (
    <div className="map-wrap" style={{ height: "100%" }}>
      <div ref={containerRef} id="map" />
      <ShadeOverlay map={mapInstance} datetime={datetime} />
      <div className="map-overlay map-hud" aria-hidden="true">
        <span className={pickMode === "origin" ? "pick-mode-active" : "pick-hint"}>
          ● Green = origin
        </span>
        <span className={pickMode === "destination" ? "pick-mode-active" : "pick-hint"}>
          ● Red = destination
        </span>
        <span className="pick-hint">
          Click the <strong>map</strong> to place the active point (use sidebar buttons to switch).
          {import.meta.env.VITE_SHADEMAP_API_KEY ? " Shadows on." : ""}
        </span>
      </div>
    </div>
  );
}
