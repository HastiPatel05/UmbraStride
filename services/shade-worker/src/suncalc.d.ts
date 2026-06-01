// Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
declare module "suncalc" {
  export function getPosition(
    date: Date,
    lat: number,
    lng: number
  ): { altitude: number; azimuth: number };
}
