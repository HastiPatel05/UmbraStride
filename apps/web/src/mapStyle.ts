import type maplibregl from "maplibre-gl";
import type { StyleSpecification } from "maplibre-gl";

/** OpenFreeMap vector style — base for 3D buildings per MapLibre docs. */
export const OPENFREEMAP_STYLE_URL = "https://tiles.openfreemap.org/styles/bright";

export const OPENFREEMAP_SOURCE_ID = "openfreemap";
export const BUILDINGS_3D_LAYER_ID = "3d-buildings";

/** First symbol layer id — insert 3D buildings below labels (MapLibre example pattern). */
export function findLabelLayerId(map: maplibregl.Map): string | undefined {
  const layers = map.getStyle()?.layers;
  if (!layers) return undefined;
  for (const layer of layers) {
    if (layer.type === "symbol" && layer.layout && "text-field" in layer.layout) {
      return layer.id;
    }
  }
  return undefined;
}

/**
 * Add OpenFreeMap building extrusions (MapLibre “Display buildings in 3D” example).
 * @see https://maplibre.org/maplibre-gl-js/docs/examples/display-buildings-in-3d/
 */
export function add3dBuildingsLayer(map: maplibregl.Map): void {
  if (map.getLayer(BUILDINGS_3D_LAYER_ID)) return;

  if (!map.getSource(OPENFREEMAP_SOURCE_ID)) {
    map.addSource(OPENFREEMAP_SOURCE_ID, {
      type: "vector",
      url: "https://tiles.openfreemap.org/planet",
    });
  }

  const beforeId = findLabelLayerId(map);

  map.addLayer(
    {
      id: BUILDINGS_3D_LAYER_ID,
      source: OPENFREEMAP_SOURCE_ID,
      "source-layer": "building",
      type: "fill-extrusion",
      minzoom: 15,
      filter: ["!=", ["get", "hide_3d"], true],
      paint: {
        "fill-extrusion-color": [
          "interpolate",
          ["linear"],
          ["get", "render_height"],
          0,
          "#c8ccd4",
          80,
          "#a8b0bc",
          200,
          "#8890a0",
        ],
        "fill-extrusion-height": [
          "interpolate",
          ["linear"],
          ["zoom"],
          15,
          0,
          16,
          ["get", "render_height"],
        ],
        "fill-extrusion-base": [
          "case",
          [">=", ["get", "zoom"], 16],
          ["get", "render_min_height"],
          0,
        ],
        "fill-extrusion-opacity": 0.9,
      },
    },
    beforeId
  );
}

export function usesVector3dBuildings(style: string | StyleSpecification): boolean {
  if (typeof style === "string") {
    return style.includes("openfreemap") || style.includes("mapbox.com");
  }
  return false;
}

/** Default map style: OpenFreeMap (3D-ready) unless Mapbox token is set. */
export function getInitialMapStyle(): StyleSpecification | string {
  const token = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;
  if (token) {
    return `https://api.mapbox.com/styles/v1/mapbox/streets-v12?access_token=${token}`;
  }
  return OPENFREEMAP_STYLE_URL;
}
