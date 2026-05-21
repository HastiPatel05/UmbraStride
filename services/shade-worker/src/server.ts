import cors from "cors";
import express from "express";
import type { ShadeProfileRequest, ShadeProfileResponse } from "@umbrastride/shared-types";
import { mockShadeProfile } from "./profile.js";

const PORT = Number(process.env.SHADE_WORKER_PORT || 3001);

const app = express();
app.use(cors());
app.use(express.json({ limit: "2mb" }));

app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    mode: process.env.SHADEMAP_API_KEY ? "shademap-ready" : "mock",
  });
});

app.post("/profile", (req, res) => {
  const body = req.body as ShadeProfileRequest;
  if (!body?.points?.length) {
    res.status(400).json({ error: "points required" });
    return;
  }
  const datetime = body.datetime || new Date().toISOString();
  const results = mockShadeProfile(body.points, datetime);
  const response: ShadeProfileResponse = { results, datetime };
  res.json(response);
});

app.listen(PORT, () => {
  console.log(`shade-worker listening on http://127.0.0.1:${PORT}`);
});
