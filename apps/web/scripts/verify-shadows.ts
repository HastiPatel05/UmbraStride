/**
 * Quick sanity check for wall-quad shadow union (run: npx tsx scripts/verify-shadows.ts)
 */
import { getSunPosition } from "../src/sun.js";
import { shadowMultiPolygonForRing } from "../src/buildingShadows.js";

const sun = getSunPosition("2024-06-21T19:00:00Z", 33.4484, -112.074);

// 20 m × 10 m rectangle centered near Phoenix (~0.00018° lng × 0.00009° lat)
const ring = [
  [-112.0741, 33.4483],
  [-112.0739, 33.4483],
  [-112.0739, 33.4484],
  [-112.0741, 33.4484],
  [-112.0741, 33.4483],
];

const mp = shadowMultiPolygonForRing(ring, 15, 33.44835, sun);
if (!mp || mp.length === 0) {
  console.error("FAIL: no shadow polygon");
  process.exit(1);
}

const outer = mp[0][0];
console.log("shadow vertices:", outer.length - 1);
console.log("sample ring:", outer.slice(0, 4).map((p) => p.map((v) => v.toFixed(6))));
console.log("OK");
