export type LngLat = { lng: number; lat: number };

export type RouteRequest = {
  aoi_id: string;
  origin: LngLat;
  destination: LngLat;
  datetime: string;
  alpha: number;
};

export type RouteResult = {
  label: string;
  alpha: number;
  geometry: GeoJSON.LineString | GeoJSON.MultiLineString | null;
  distance_m: number;
  shade_fraction: number;
  detour_ratio: number;
  ts_bucket: string;
};

export type ShadeProfilePoint = {
  lng: number;
  lat: number;
  inShade: boolean;
};

export type ShadeProfileRequest = {
  points: LngLat[];
  datetime: string;
};

export type ShadeProfileResponse = {
  results: ShadeProfilePoint[];
  datetime: string;
};
