import { defineConfig } from "@tauri-apps/cli";

export default defineConfig({
  build: {
    beforeDevCommand: "npm run dev",
    beforeBuildCommand: "npm run build",
    devPath: "http://localhost:1420",
    distDir: "../dist",
    withGlobalTauri: true,
  },
  package: {
    productName: "ATOM AI Web Studio",
    version: "2.0.0",
  },
  tauri: {
    allowlist: {
      all: false,
      shell: {
        all: false,
        execute: true,
        open: true,
      },
      http: {
        all: true,
        request: true,
      },
      path: {
        all: true,
      },
      fs: {
        all: true,
        readFile: true,
        writeFile: true,
      },
      window: {
        all: true,
        create: true,
        center: true,
        maximize: true,
        minimize: true,
        setAlwaysOnTop: true,
      },
      dialog: {
        all: true,
        open: true,
        save: true,
      },
      notification: {
        all: true,
      },
      os: {
        all: false,
        platform: true,
        version: true,
      },
    },
    bundle: {
      active: true,
      category: "DeveloperTool",
      identifier: "com.atom-ai.web-studio",
      targets: ["deb", "msi", "dmg", "app", "appimage"],
      shortDescription: "AI-powered web development via conversation",
      longDescription:
        "Build modern Next.js applications entirely through conversation. No local development setup required - everything happens in the cloud with real-time preview.",
      icon: [
        "icons/32x32.png",
        "icons/128x128.png",
        "icons/128x128@2x.png",
        "icons/icon.icns",
        "icons/icon.ico",
      ],
      resources: ["resources/*"],
      deb: {
        depends: [],
      },
      macOS: {
        frameworks: [],
        minimumSystemVersion: "10.15",
        useBootstrapper: false,
        exceptionDomain: "localhost",
      },
      windows: {
        certificateThumbprint: null,
        digestAlgorithm: "sha256",
        timestampUrl: "",
      },
    },
    security: {
      csp: "default-src 'self' blob: data: filesystem: ws: wss: ; script-src 'self' 'unsafe-eval' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:",
    },
    updater: {
      active: true,
      endpoints: ["https://release.atomai.com/web-studio/latest.json"],
      dialog: true,
    },
    windows: [
      {
        fullscreen: false,
        resizable: true,
        title: "ATOM AI Web Studio",
        width: 1200,
        height: 800,
        minWidth: 800,
        minHeight: 600,
        center: true,
        transparent: false,
        maximized: true,
      },
    ],
  },
});
