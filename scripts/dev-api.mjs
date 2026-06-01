// Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.

import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import { join } from "node:path";

const isWindows = process.platform === "win32";
const python = join(
  process.cwd(),
  ".venv",
  isWindows ? "Scripts/python.exe" : "bin/python"
);

if (!existsSync(python)) {
  console.error("Missing .venv. Run the setup steps first, then retry npm run dev:api.");
  process.exit(1);
}

const host = process.env.API_HOST || "127.0.0.1";
const port = process.env.API_PORT || "8000";
const env = {
  ...process.env,
  ROUTING_WARM_ON_STARTUP: process.env.ROUTING_WARM_ON_STARTUP || "0",
};

const child = spawn(
  python,
  [
    "-m",
    "uvicorn",
    "umbrastride_api.main:app",
    "--reload",
    "--host",
    host,
    "--port",
    port,
  ],
  {
    cwd: process.cwd(),
    env,
    stdio: "inherit",
  }
);

child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  process.exit(code ?? 0);
});
