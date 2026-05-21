import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { sampleEdge, aggregateShadeFraction, sampleCountForLength } from "./sampling.js";

describe("sampling", () => {
  it("sampleCountForLength", () => {
    assert.equal(sampleCountForLength(25), 5);
    assert.equal(sampleCountForLength(100), 10);
  });

  it("sampleEdge returns points along line", () => {
    const pts = sampleEdge("0|1|0", [
      [11.58, 48.13],
      [11.581, 48.131],
    ], 50);
    assert.ok(pts.length >= 5);
    assert.equal(pts[0].edgeKey, "0|1|0");
  });

  it("aggregateShadeFraction", () => {
    const f = aggregateShadeFraction(
      [
        { index: 0, inShade: true },
        { index: 1, inShade: false },
      ],
      2
    );
    assert.equal(f, 0.5);
  });
});
