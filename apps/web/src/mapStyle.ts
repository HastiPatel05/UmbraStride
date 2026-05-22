import type maplibregl from "maplibre-gl";
import type { StyleSpecification } from "maplibre-gl";

const OSM_RASTER_STYLE: StyleSpecification = {
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
};

/** ShadeMap global building footprints (same tiles as shademap.app). */
const SHADEMAP_BUILDINGS_SOURCE = {
  buildings: {
    type: "vector" as const,
    encoding: "mlt" as const,
    tiles: ["https://cfw.shademap.app/buildings/{z}/{x}/{y}.mlt"],
    minzoom: 14,
    maxzoom: 14,
    attribution: "© ShadeMap / OpenStreetMap",
  },
};

function buildingHeightExpression(): maplibregl.ExpressionSpecification {
  // Heights in ShadeMap tiles are decimeters; divide by 10 for meters.
  return ["max", 3, ["/", ["coalesce", ["get", "height"], 31], 10]];
}

/**
 * OSM basemap + ShadeMap building vector tiles for 2.5D extrusions and shadows.
 * Used when VITE_SHADEMAP_API_KEY is set (see ShadeOverlay).
 */
export function getShadeMapStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {
      osm: OSM_RASTER_STYLE.sources!.osm,
      ...SHADEMAP_BUILDINGS_SOURCE,
    },
    layers: [
      { id: "osm", type: "raster", source: "osm" },
      {
        id: "buildings-footprint",
        type: "fill",
        source: "buildings",
        "source-layer": "building",
        minzoom: 14,
        paint: {
          "fill-color": "#c8ccd4",
          "fill-opacity": 0.35,
        },
      },
      {
        id: "buildings-3d",
        type: "fill-extrusion",
        source: "buildings",
        "source-layer": "building",
        minzoom: 14,
        paint: {
          "fill-extrusion-color": "#b8bcc6",
          "fill-extrusion-height": buildingHeightExpression(),
          "fill-extrusion-base": 0,
          "fill-extrusion-opacity": 0.88,
        },
      },
    ],
  };
}

/** Mapbox Streets includes vector building layer for ShadeMap heights. */
export function getInitialMapStyle(): StyleSpecification | string {
  const shadeKey = import.meta.env.VITE_SHADEMAP_API_KEY;
  if (shadeKey) {
    return getShadeMapStyle();
  }
  const token = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;
  if (token) {
    return `https://api.mapbox.com/styles/v1/mapbox/streets-v12?access_token=${token}`;
  }
  return OSM_RASTER_STYLE;
}
