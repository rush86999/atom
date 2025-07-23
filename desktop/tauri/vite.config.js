import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
  },
  resolve: {
    alias: {
      "@tauri-apps/api/tauri": "./src-tauri/bindings/tauri-apps-api.js",
      "@tauri-apps/api/window": "./src-tauri/bindings/tauri-apps-api.js",
      "@tauri-apps/api/fs": "./src-tauri/bindings/tauri-apps-api.js",
      "@tauri-apps/api": "./src-tauri/bindings/tauri-apps-api.js",
    },
  },
});
