import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_API_BASE_URL || "http://127.0.0.1:8050";
  const apiKey = env.MEMORY_API_KEY || "";

  return {
    plugins: [react()],
    server: {
      proxy: {
        "/brain-api": {
          target,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/brain-api/, ""),
          configure: (proxy) => {
            proxy.on("proxyReq", (proxyReq) => {
              if (apiKey) {
                proxyReq.setHeader("X-API-Key", apiKey);
              }
            });
          },
        },
      },
    },
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts",
      include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
      exclude: ["e2e/**", "playwright.config.ts"],
    },
  };
});
