declare module "mapbox-gl-shadow-simulator" {
  import type { Map } from "maplibre-gl";

  export interface ShadeMapTerrainSource {
    tileSize: number;
    maxZoom: number;
    getSourceUrl: (params: { x: number; y: number; z: number }) => string;
    getElevation: (params: { r: number; g: number; b: number; a?: number }) => number;
  }

  export interface ShadeMapOptions {
    apiKey: string;
    date?: Date;
    color?: string;
    opacity?: number;
    terrainSource?: ShadeMapTerrainSource;
    getFeatures?: () => Promise<GeoJSON.Feature[]>;
  }

  export default class ShadeMap {
    constructor(options: ShadeMapOptions);
    addTo(map: Map): this;
    remove(): void;
    setDate(date: Date): this;
    setOpacity(opacity: number): this;
  }
}
