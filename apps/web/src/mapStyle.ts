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

/** Mapbox Streets includes vector building layer for ShadeMap heights. */
export function getInitialMapStyle(): StyleSpecification | string {
  const token = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;
  if (token) {
    return `https://api.mapbox.com/styles/v1/mapbox/streets-v12?access_token=${token}`;
  }
  return OSM_RASTER_STYLE;
}
