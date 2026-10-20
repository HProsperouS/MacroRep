/// <reference types="vitest/config" />
import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import { VitePWA } from "vite-plugin-pwa"

const backendTarget = process.env.VITE_DEV_PROXY_TARGET ?? "http://127.0.0.1:8000"

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["apple-touch-icon.png"],
      manifest: {
        name: "MacroRep",
        short_name: "MacroRep",
        description: "Adaptive nutrition and workout tracking",
        theme_color: "#0e1012",
        background_color: "#0e1012",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "pwa-192x192.png", sizes: "192x192", type: "image/png" },
          { src: "pwa-512x512.png", sizes: "512x512", type: "image/png" },
          { src: "pwa-maskable-512x512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      // Precache the build output only. API responses are private per-user data, so they are never cached.
      workbox: { navigateFallbackDenylist: [/^\/api\//, /^\/health\//] },
    }),
  ],
  server: {
    proxy: {
      "/api": backendTarget,
      "/health": backendTarget,
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    restoreMocks: true,
    coverage: {
      provider: "v8",
      // Every source file counts, including ones no test loads.
      include: ["src/**/*.{ts,tsx}"],
      // Generated shadcn primitives, the entry point, test helpers and type-only files.
      exclude: ["src/components/ui/**", "src/main.tsx", "src/test/**", "src/types/**", "src/**/*.d.ts", "src/**/*.test.{ts,tsx}"],
      reporter: ["text-summary", "json-summary", "html"],
      // A floor that catches a drop, not a target: lines were 88% and branches 78% when it was set.
      thresholds: { lines: 85, branches: 75 },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
})
