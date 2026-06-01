// Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
/** 15-minute UTC bucket key (matches Python floor_ts_bucket). */
export function floorTsBucket(iso: string, minutes = 15): string {
  const d = new Date(iso);
  const utc = new Date(
    Date.UTC(
      d.getUTCFullYear(),
      d.getUTCMonth(),
      d.getUTCDate(),
      d.getUTCHours(),
      Math.floor(d.getUTCMinutes() / minutes) * minutes,
      0,
      0
    )
  );
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${utc.getUTCFullYear()}-${pad(utc.getUTCMonth() + 1)}-${pad(utc.getUTCDate())}T${pad(utc.getUTCHours())}:${pad(utc.getUTCMinutes())}`;
}

export function edgeCacheKey(aoiId: string, edgeKey: string, tsBucket: string): string {
  return `${aoiId}::${edgeKey}::${tsBucket}`;
}
