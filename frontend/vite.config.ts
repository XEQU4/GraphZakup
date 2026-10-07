import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === "build" ? "/static/frontend/" : "/",
  build: {
    outDir: "../static/frontend",
    emptyOutDir: true,
    manifest: "vite-manifest.json",
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (
            id.includes("node_modules") &&
            /react-dom|react-router|\/react\//.test(id)
          )
            return "vendor";
          if (id.includes("node_modules") && /motion|framer/.test(id))
            return "motion";
        },
      },
    },
  },
  server: {
    host: "127.0.0.1",
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        configure(proxy) {
          proxy.on("proxyReq", (request, incoming) => {
            if (incoming.headers.origin === "http://127.0.0.1:5173") {
              request.setHeader("Origin", "http://127.0.0.1:8000");
            }
          });
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
  },
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
}));
