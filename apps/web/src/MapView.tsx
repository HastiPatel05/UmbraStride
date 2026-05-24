import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import type { RouteResult } from "./api";
import { add3dBuildingsLayer, getInitialMapStyle, usesVector3dBuildings } from "./mapStyle";
import ShadeOverlay from "./ShadeOverlay";

const ROUTE_COLORS: Record<string, string> = {
  shortest: "#f97316",
  coolest: "#10b981",
  custom: "#a78bfa",
};

/** Bottom → top: shortest, custom, coolest (coolest on top). */
const ROUTE_DRAW_ORDER = ["shortest", "custom", "coolest"] as const;

const ROUTE_LINE_WIDTH: Record<string, number> = {
  shortest: 6,
  custom: 5,
  coolest: 7,
};

const ROUTE_LINE_OFFSET: Record<string, number> = {
  shortest: -5,
  custom: 0,
  coolest: 5,
};

type Props = {
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

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const style = getInitialMapStyle();
    const enable3d = usesVector3dBuildings(style);
    const map = new maplibregl.Map({
      container: containerRef.current,
      style,
      center,
      zoom,
      pitch: enable3d ? 45 : 0,
      bearing: enable3d ? -17.6 : 0,
      minZoom: 8,
      maxZoom: 20,
      antialias: true,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-left");

    map.on("click", (e) => {
      onPickPointRef.current(pickModeRef.current, e.lngLat.lng, e.lngLat.lat);
    });

    mapRef.current = map;

    const onMapReady = () => {
      if (enable3d) {
        try {
          add3dBuildingsLayer(map);
        } catch (e) {
          console.warn("3D buildings layer:", e);
        }
      }
      setMapInstance(map);
    };

    if (map.isStyleLoaded()) onMapReady();
    else map.once("load", onMapReady);

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
      const removeRouteLayer = (label: string) => {
        const layerId = `route-${label}-line`;
        const sourceId = `route-${label}`;
        if (map.getLayer(layerId)) map.removeLayer(layerId);
        if (map.getSource(sourceId)) map.removeSource(sourceId);
      };

      const setRouteLine = (
        label: string,
        data: GeoJSON.FeatureCollection,
        color: string,
        width: number,
        lineOffset: number
      ) => {
        const sourceId = `route-${label}`;
        const layerId = `${sourceId}-line`;
        if (map.getSource(sourceId)) {
          (map.getSource(sourceId) as maplibregl.GeoJSONSource).setData(data);
          if (map.getLayer(layerId)) {
            map.setPaintProperty(layerId, "line-color", color);
            map.setPaintProperty(layerId, "line-width", width);
            map.setPaintProperty(layerId, "line-offset", lineOffset);
          }
        } else {
          map.addSource(sourceId, { type: "geojson", data });
          map.addLayer({
            id: layerId,
            type: "line",
            source: sourceId,
            paint: {
              "line-color": color,
              "line-width": width,
              "line-opacity": 1,
              "line-offset": lineOffset,
            },
          });
        }
      };

      // Remove legacy layers (indexed routes, full graph, custom route).
      const style = map.getStyle();
      if (style?.layers) {
        for (const layer of style.layers) {
          const id = layer.id;
          if (
            id === "graph-line" ||
            id.match(/^route-\d+-line$/) ||
            id === "route-custom-line"
          ) {
            const sourceId = id.replace(/-line$/, "");
            if (map.getLayer(id)) map.removeLayer(id);
            if (map.getSource(sourceId)) map.removeSource(sourceId);
          }
        }
      }
      removeRouteLayer("custom");

      const activeLabels = new Set(
        routes.filter((r) => r.geometry).map((r) => r.label)
      );
      for (const label of ROUTE_DRAW_ORDER) {
        if (!activeLabels.has(label)) removeRouteLayer(label);
      }

      const byLabel = new Map(routes.map((r) => [r.label, r]));
      for (const label of ROUTE_DRAW_ORDER) {
        const r = byLabel.get(label);
        if (!r?.geometry) continue;
        const fc: GeoJSON.FeatureCollection = {
          type: "FeatureCollection",
          features: [{ type: "Feature", properties: {}, geometry: r.geometry }],
        };
        setRouteLine(
          label,
          fc,
          ROUTE_COLORS[label],
          ROUTE_LINE_WIDTH[label],
          ROUTE_LINE_OFFSET[label]
        );
      }

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
            "circle-radius": 9,
            "circle-color": [
              "match",
              ["get", "role"],
              "origin",
              "#22c55e",
              "dest",
              "#ef4444",
              "#fff",
            ],
            "circle-stroke-width": 2,
            "circle-stroke-color": "#0f1419",
          },
        });
      }

      // Fit map to routes when available.
      if (routes.length > 0) {
        const bounds = new maplibregl.LngLatBounds();
        let hasCoord = false;
        for (const r of routes) {
          if (!r.geometry?.coordinates) continue;
          for (const c of r.geometry.coordinates) {
            bounds.extend(c as [number, number]);
            hasCoord = true;
          }
        }
        if (origin) {
          bounds.extend(origin);
          hasCoord = true;
        }
        if (destination) {
          bounds.extend(destination);
          hasCoord = true;
        }
        if (hasCoord) {
          map.fitBounds(bounds, { padding: 80, maxZoom: 17, duration: 600 });
          map.once("moveend", () => {
            if (map.getZoom() < 16) map.setZoom(16);
          });
        }
      }
    };

    if (map.isStyleLoaded()) applyLayers();
    else map.once("load", applyLayers);
  }, [routes, origin, destination]);

  return (
    <div className="map-wrap" style={{ height: "100%" }}>
      <div ref={containerRef} id="map" />
      <ShadeOverlay map={mapInstance} datetime={datetime} />
      <div className="map-overlay map-hud" aria-hidden="true">
        <span className={pickMode === "origin" ? "pick-mode-active" : "pick-hint"}>
          ● Green dot = origin
        </span>
        <span className={pickMode === "destination" ? "pick-mode-active" : "pick-hint"}>
          ● Red dot = destination
        </span>
        {routes.length > 0 && (
          <span className="pick-hint route-legend">
            <span className="legend-swatch legend-shortest">orange</span> shortest ·{" "}
            <span className="legend-swatch legend-coolest">green</span> coolest ·{" "}
            <span className="legend-swatch legend-custom">purple</span> your route
          </span>
        )}
        <span className="pick-hint">
          Click the <strong>map</strong> to place the active point (use sidebar buttons to switch).
          Shadows use local SunCalc (no API key).
        </span>
      </div>
    </div>
  );
}
