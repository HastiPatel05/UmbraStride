import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import type { RouteResult, SnappedPoint } from "./api";
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

const CONNECTOR_MIN_DISTANCE_M = 0.5;
const CONNECTOR_LINE_SOURCE_ID = "pedestrian-connectors";
const CONNECTOR_DOTS_SOURCE_ID = "pedestrian-connector-dots";
const CONNECTOR_CASE_LAYER_ID = "pedestrian-connectors-case";
const CONNECTOR_LINE_LAYER_ID = "pedestrian-connectors-line";
const CONNECTOR_DOTS_LAYER_ID = "pedestrian-connectors-dots";

const CONNECTOR_COLOR_EXPR: maplibregl.ExpressionSpecification = [
  "match",
  ["get", "role"],
  "destination",
  "#fca5a5",
  "#10b981",
];

const CONNECTOR_LINE_COLOR_EXPR: maplibregl.ExpressionSpecification = [
  "match",
  ["get", "role"],
  "destination",
  "#ef4444",
  "#10b981",
];

function sameCoord(a: [number, number], b: [number, number]): boolean {
  return Math.abs(a[0] - b[0]) < 1e-9 && Math.abs(a[1] - b[1]) < 1e-9;
}

function snappedCoord(point?: SnappedPoint | null): [number, number] | null {
  if (!point) return null;
  return [point.lng, point.lat];
}

function routeEndpoint(routes: RouteResult[], end: "start" | "end"): [number, number] | null {
  for (const route of routes) {
    const coordinates = route.geometry?.coordinates as [number, number][] | undefined;
    if (!coordinates?.length) continue;
    return end === "start" ? coordinates[0] : coordinates[coordinates.length - 1];
  }
  return null;
}

function shouldShowConnector(
  exact: [number, number] | null,
  snapped: [number, number] | null,
  distanceM?: number
): exact is [number, number] {
  if (!exact || !snapped || sameCoord(exact, snapped)) return false;
  return distanceM === undefined || distanceM >= CONNECTOR_MIN_DISTANCE_M;
}

function approximateDistanceM(a: [number, number], b: [number, number]): number {
  const lat = ((a[1] + b[1]) / 2) * (Math.PI / 180);
  const dx = (b[0] - a[0]) * 111_320 * Math.cos(lat);
  const dy = (b[1] - a[1]) * 110_540;
  return Math.sqrt(dx * dx + dy * dy);
}

function connectorDotFeatures(
  lines: GeoJSON.Feature<GeoJSON.LineString>[]
): GeoJSON.Feature<GeoJSON.Point>[] {
  const dots: GeoJSON.Feature<GeoJSON.Point>[] = [];
  for (const line of lines) {
    const [start, end] = line.geometry.coordinates as [number, number][];
    if (!start || !end) continue;

    const distanceM = approximateDistanceM(start, end);
    const segments = Math.max(3, Math.min(28, Math.round(distanceM / 6)));
    for (let i = 1; i < segments; i += 1) {
      const t = i / segments;
      dots.push({
        type: "Feature",
        properties: line.properties,
        geometry: {
          type: "Point",
          coordinates: [
            start[0] + (end[0] - start[0]) * t,
            start[1] + (end[1] - start[1]) * t,
          ],
        },
      });
    }
  }
  return dots;
}

function connectorFeatures(
  routes: RouteResult[],
  origin: [number, number] | null,
  destination: [number, number] | null,
  originSnapped?: SnappedPoint | null,
  destinationSnapped?: SnappedPoint | null
): GeoJSON.Feature<GeoJSON.LineString>[] {
  const features: GeoJSON.Feature<GeoJSON.LineString>[] = [];
  const originTarget = snappedCoord(originSnapped) ?? routeEndpoint(routes, "start");
  const destinationTarget = snappedCoord(destinationSnapped) ?? routeEndpoint(routes, "end");

  if (originTarget && shouldShowConnector(origin, originTarget, originSnapped?.distance_m)) {
    features.push({
      type: "Feature",
      properties: { role: "origin" },
      geometry: { type: "LineString", coordinates: [origin, originTarget] },
    });
  }

  if (
    destinationTarget &&
    shouldShowConnector(destination, destinationTarget, destinationSnapped?.distance_m)
  ) {
    features.push({
      type: "Feature",
      properties: { role: "destination" },
      geometry: { type: "LineString", coordinates: [destinationTarget, destination] },
    });
  }

  return features;
}

type Props = {
  routes: RouteResult[];
  origin: [number, number] | null;
  destination: [number, number] | null;
  originSnapped?: SnappedPoint | null;
  destinationSnapped?: SnappedPoint | null;
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
  originSnapped,
  destinationSnapped,
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

      const setConnectorLines = (lineFeatures: GeoJSON.Feature<GeoJSON.LineString>[]) => {
        const dotFeatures = connectorDotFeatures(lineFeatures);
        const lineData: GeoJSON.FeatureCollection<GeoJSON.LineString> = {
          type: "FeatureCollection",
          features: lineFeatures,
        };
        const dotData: GeoJSON.FeatureCollection<GeoJSON.Point> = {
          type: "FeatureCollection",
          features: dotFeatures,
        };

        if (lineFeatures.length === 0) {
          if (map.getLayer(CONNECTOR_DOTS_LAYER_ID)) map.removeLayer(CONNECTOR_DOTS_LAYER_ID);
          if (map.getLayer(CONNECTOR_LINE_LAYER_ID)) map.removeLayer(CONNECTOR_LINE_LAYER_ID);
          if (map.getLayer(CONNECTOR_CASE_LAYER_ID)) map.removeLayer(CONNECTOR_CASE_LAYER_ID);
          if (map.getSource(CONNECTOR_DOTS_SOURCE_ID)) map.removeSource(CONNECTOR_DOTS_SOURCE_ID);
          if (map.getSource(CONNECTOR_LINE_SOURCE_ID)) map.removeSource(CONNECTOR_LINE_SOURCE_ID);
          return;
        }

        if (map.getLayer(CONNECTOR_DOTS_LAYER_ID)) {
          map.removeLayer(CONNECTOR_DOTS_LAYER_ID);
        }

        if (map.getSource(CONNECTOR_LINE_SOURCE_ID)) {
          (map.getSource(CONNECTOR_LINE_SOURCE_ID) as maplibregl.GeoJSONSource).setData(lineData);
        } else {
          map.addSource(CONNECTOR_LINE_SOURCE_ID, { type: "geojson", data: lineData });
          map.addLayer({
            id: CONNECTOR_CASE_LAYER_ID,
            type: "line",
            source: CONNECTOR_LINE_SOURCE_ID,
            layout: { "line-cap": "round", "line-join": "round" },
            paint: {
              "line-color": "#ffffff",
              "line-opacity": 0.7,
              "line-width": ["interpolate", ["linear"], ["zoom"], 12, 5, 18, 7],
              "line-dasharray": [0.1, 1.4],
            },
          });
          map.addLayer({
            id: CONNECTOR_LINE_LAYER_ID,
            type: "line",
            source: CONNECTOR_LINE_SOURCE_ID,
            layout: { "line-cap": "round", "line-join": "round" },
            paint: {
              "line-color": CONNECTOR_LINE_COLOR_EXPR,
              "line-opacity": 0.3,
              "line-width": ["interpolate", ["linear"], ["zoom"], 12, 3, 18, 5],
              "line-dasharray": [0.1, 1.4],
            },
          });
        }

        if (map.getSource(CONNECTOR_DOTS_SOURCE_ID)) {
          (map.getSource(CONNECTOR_DOTS_SOURCE_ID) as maplibregl.GeoJSONSource).setData(dotData);
        } else {
          map.addSource(CONNECTOR_DOTS_SOURCE_ID, { type: "geojson", data: dotData });
        }
        map.addLayer({
          id: CONNECTOR_DOTS_LAYER_ID,
          type: "circle",
          source: CONNECTOR_DOTS_SOURCE_ID,
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 12, 3, 18, 5],
            "circle-color": CONNECTOR_COLOR_EXPR,
            "circle-opacity": 0.98,
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
          },
        });
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

      setConnectorLines(
        connectorFeatures(routes, origin, destination, originSnapped, destinationSnapped)
      );

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

      // Colored outer ring expression (matches previous single-circle colors).
      const outlineColorExpr: maplibregl.ExpressionSpecification = [
        "match",
        ["get", "role"],
        "origin",
        "#22c55e",
        "dest",
        "#ef4444",
        "#fff",
      ];

      if (map.getSource("markers")) {
        (map.getSource("markers") as maplibregl.GeoJSONSource).setData(markerFc);
        if (map.getLayer("markers-circle-outline")) {
          map.setPaintProperty("markers-circle-outline", "circle-color", outlineColorExpr);
          map.setPaintProperty("markers-circle-outline", "circle-radius", 9);
          map.setPaintProperty("markers-circle-outline", "circle-stroke-width", 2);
          map.setPaintProperty("markers-circle-outline", "circle-stroke-color", "#0f1419");
        }
        if (map.getLayer("markers-circle-inner")) {
          map.setPaintProperty("markers-circle-inner", "circle-color", "#ffffff");
          map.setPaintProperty("markers-circle-inner", "circle-radius", 5);
        }
      } else {
        map.addSource("markers", { type: "geojson", data: markerFc });
        // Outer colored ring
        map.addLayer({
          id: "markers-circle-outline",
          type: "circle",
          source: "markers",
          paint: {
            "circle-radius": 9,
            "circle-color": outlineColorExpr,
            "circle-stroke-width": 2,
            "circle-stroke-color": "#0f1419",
          },
        });
        // Inner light/white dot
        map.addLayer({
          id: "markers-circle-inner",
          type: "circle",
          source: "markers",
          paint: {
            "circle-radius": 5,
            "circle-color": "#ffffff",
            "circle-stroke-width": 0,
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
  }, [routes, origin, destination, originSnapped, destinationSnapped]);

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
