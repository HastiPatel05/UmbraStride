declare module "mapbox-gl-shadow-simulator" {
  import type { Map } from "maplibre-gl";
  export default class ShadeMap {
    constructor(options: Record<string, unknown>);
    addTo(map: Map): this;
    remove(): void;
    setDate(date: Date): void;
  }
}
