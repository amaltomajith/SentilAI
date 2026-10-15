import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// Dev: the SPA talks to the Sentinel backend through same-origin proxies (no CORS, no secrets in the bundle).
const backend = process.env.VITE_BACKEND_PROXY ?? "http://127.0.0.1:8000";

export default defineConfig({
  server: {
    host: "::",
    port: 5173,           // fixed: the stored admin token is per-origin, so the port must not drift
    strictPort: true,
    hmr: { overlay: false },
    watch: { ignored: ['**/backend/**', '**/whatsapp-bridge/**', '**/docs/**'] },   // never watch DBs, media or node_modules of the other services
    proxy: {
      "/api": { target: backend, changeOrigin: false },
      "/r": { target: backend, changeOrigin: false },
    },
  },
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
});