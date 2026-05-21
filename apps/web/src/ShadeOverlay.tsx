/**
 * Optional live shadow layer via ShadeMap (mapbox-gl-shadow-simulator).
 * Set VITE_SHADEMAP_API_KEY in .env to enable.
 */
import { useEffect, useRef } from "react";
import type maplibregl from "maplibre-gl";

type Props = {
  map: maplibregl.Map | null;
  datetime: string;
};

export default function ShadeOverlay({ map, datetime }: Props) {
  const layerRef = useRef<{ remove: () => void } | null>(null);
  const apiKey = import.meta.env.VITE_SHADEMAP_API_KEY;

  useEffect(() => {
    if (!map || !apiKey) return;

    let cancelled = false;

    (async () => {
      try {
        const mod = await import("mapbox-gl-shadow-simulator");
        const ShadeMap = mod.default;
        if (cancelled) return;

        layerRef.current?.remove();
        const shadeMap = new ShadeMap({
          apiKey,
          date: new Date(datetime),
          color: "#01112f",
          opacity: 0.45,
          terrainSource: {
            tileSize: 256,
            maxZoom: 15,
            getSourceUrl: ({ x, y, z }: { x: number; y: number; z: number }) =>
              `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/${z}/${x}/${y}.png`,
            getElevation: ({ r, g, b }: { r: number; g: number; b: number }) =>
              (r * 256 + g + b / 256) - 32768,
          },
        });
        shadeMap.addTo(map);
        layerRef.current = shadeMap;
      } catch {
        // ShadeMap optional — routing still works via server cache
      }
    })();

    return () => {
      cancelled = true;
      layerRef.current?.remove();
      layerRef.current = null;
    };
  }, [map, datetime, apiKey]);

  if (!apiKey) return null;
  return null;
}
