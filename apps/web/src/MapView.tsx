import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import type { RouteResult } from "./api";
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
};

export default function MapView({
  graph,
  routes,
  origin,
  destination,
  onPickPoint,
  pickMode,
  datetime,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapInstance, setMapInstance] = useState<maplibregl.Map | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap",
          },
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
      },
      center: [11.58, 48.137],
      zoom: 15,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-left");

    map.on("click", (e) => {
      onPickPoint(pickMode, e.lngLat.lng, e.lngLat.lat);
    });

    mapRef.current = map;
    setMapInstance(map);
    return () => {
      map.remove();
      mapRef.current = null;
      setMapInstance(null);
    };
  }, [onPickPoint, pickMode]);

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
      <div className="map-overlay">
        Click map to set {pickMode === "origin" ? "origin" : "destination"}
        {import.meta.env.VITE_SHADEMAP_API_KEY ? " · ShadeMap on" : ""}
      </div>
    </div>
  );
}
