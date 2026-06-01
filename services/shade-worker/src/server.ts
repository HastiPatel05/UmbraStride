// Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
import cors from "cors";
import express from "express";
import type { ShadeProfileRequest, ShadeProfileResponse } from "@umbrastride/shared-types";
import { profileShade, resolveProfileMode } from "./profile.js";

const PORT = Number(process.env.SHADE_WORKER_PORT || 3001);
const CONCURRENCY = Math.max(
  1,
  Number(process.env.SHADE_WORKER_CONCURRENCY || "2") || 2
);

const app = express();
app.use(cors());
app.use(express.json({ limit: "4mb" }));

let active = 0;
const queue: Array<() => void> = [];

function runLimited<T>(fn: () => Promise<T>): Promise<T> {
  if (active < CONCURRENCY) {
    active += 1;
    return fn().finally(() => {
      active -= 1;
      const next = queue.shift();
      if (next) next();
    });
  }
  return new Promise((resolve, reject) => {
    queue.push(() => {
      runLimited(fn).then(resolve, reject);
    });
  });
}

app.get("/health", (_req, res) => {
  const mode = resolveProfileMode();
  res.json({
    status: "ok",
    mode,
    concurrency: CONCURRENCY,
    description:
      mode === "building-aware"
        ? "OSM buildings + sun position (Overpass/SunCalc); no ShadeMap API key"
        : "Synthetic shade (no API key); matches seed_demo_cache style",
  });
});

app.post("/profile", async (req, res) => {
  const body = req.body as ShadeProfileRequest;
  if (!body?.points?.length) {
    res.status(400).json({ error: "points required" });
    return;
  }
  const datetime = body.datetime || new Date().toISOString();

  try {
    const { results, mode } = await runLimited(() =>
      profileShade(body.points, datetime)
    );
    const response: ShadeProfileResponse & { mode: string } = {
      results,
      datetime,
      mode,
    };
    res.json(response);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("profile error:", msg);
    res.status(502).json({ error: msg });
  }
});

app.listen(PORT, () => {
  console.log(
    `shade-worker on http://127.0.0.1:${PORT} mode=${resolveProfileMode()} concurrency=${CONCURRENCY}`
  );
});
