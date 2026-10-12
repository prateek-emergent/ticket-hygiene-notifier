import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev` serves the UI on :5173 and forwards /api to the Python server (python -m dashboard, :8090).
// `npm run build` writes the static UI into ../static, which the Python server serves.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../static", emptyOutDir: true, sourcemap: false },
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8090", changeOrigin: false } },
  },
});
