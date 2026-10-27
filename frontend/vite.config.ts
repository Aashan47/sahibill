import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built into ../web/dist and served by FastAPI; in development the API is proxied to the local server.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../web/dist", emptyOutDir: true, sourcemap: false },
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8770" } },
});
