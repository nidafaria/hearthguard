import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";

// Serves ../eval/results at /results/<name>.json. A missing file is a real 404, so the page can
// show NOT COMPUTED instead of the dev server's index.html fallback. Read-only; no key, no database.
const RESULTS = path.resolve(__dirname, "../eval/results");

function results(): Plugin {
  return {
    name: "serve-eval-results",
    configureServer(server) {
      server.middlewares.use("/results", (req, res) => {
        const name = decodeURIComponent((req.url ?? "").split("?")[0]).replace(/^\/+/, "");
        const file = path.resolve(RESULTS, name);
        const ok = /^[A-Za-z0-9_.-]+\.(json|md)$/.test(name) && file.startsWith(RESULTS + path.sep);
        if (!ok || !fs.existsSync(file)) {
          res.statusCode = 404;
          res.end("not found");
          return;
        }
        res.setHeader("Content-Type", name.endsWith(".json") ? "application/json" : "text/plain");
        res.end(fs.readFileSync(file));
      });
    },
  };
}

export default defineConfig({ plugins: [react(), results()], server: { port: 5173 } });
