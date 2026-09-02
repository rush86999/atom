const path = require('path');
const fs = require('fs');

// API base resolution (fail-fast): NEXT_PUBLIC_API_URL from the real env
// wins; .env.local is a dev convenience fallback; a localhost default is
// ONLY applied in `next dev`. Production builds REFUSE to bake loopback
// into the client bundle — serving such a build from any non-local
// hostname breaks every API call (gap #2 in the UI gap analysis).
const isDev = process.env.NODE_ENV === 'development';
let nextPublicApiUrl = process.env.NEXT_PUBLIC_API_URL || "";
if (!nextPublicApiUrl) {
  try {
    const envLocalPath = path.resolve(__dirname, '.env.local');
    if (fs.existsSync(envLocalPath)) {
      const envLocal = fs.readFileSync(envLocalPath, 'utf8');
      const match = envLocal.match(/NEXT_PUBLIC_API_URL=(.+)/);
      if (match && match[1]) {
        nextPublicApiUrl = match[1].trim();
      }
    }
  } catch (e) {
    // Ignore
  }
}
if (!nextPublicApiUrl && isDev) {
  nextPublicApiUrl = "http://localhost:8001";
}
// Explicit opt-in for same-machine deployments (docker compose on one
// host, where the browser genuinely talks to localhost). Never silent.
const allowLoopback = process.env.NEXT_PUBLIC_ALLOW_LOOPBACK === "1";
if (!nextPublicApiUrl || (/localhost|127\.0\.0\.1/.test(nextPublicApiUrl) && !isDev && !allowLoopback)) {
  throw new Error(
    "[next.config.js] NEXT_PUBLIC_API_URL must be set to the public API origin " +
    "for non-dev builds (got: " + (nextPublicApiUrl || 'unset') + "). " +
    "Refusing to bake a loopback URL into a production client bundle."
  );
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    PYTHON_API_SERVICE_BASE_URL: nextPublicApiUrl,
    NEXT_PUBLIC_API_BASE_URL: nextPublicApiUrl,
    PYTHON_BACKEND_URL: nextPublicApiUrl,
  },
  // #11 fix: re-enable compression (the zlib issue was from an old Next.js
  // version — 14+ handles this correctly). Keep TS/ESLint ignores for now
  // (the codebase has ~100 type errors that would block CI) but flag them
  // as a known tech-debt item.
  compress: true,
  reactStrictMode: true,
  eslint: {
    // TODO: fix existing ESLint errors then set to false
    ignoreDuringBuilds: true,
  },
  typescript: {
    // TODO: fix existing type errors then set to false
    ignoreBuildErrors: true,
  },
  output: 'standalone',
  // The Next.js 16 dev-tools floating button (rendered as <nextjs-portal> in
  // the bottom-right corner) intercepts pointer events over the chat input's
  // send button in dev, which breaks both real users and E2E tests. Disabled
  // in dev; the production build has no dev indicators anyway.
  devIndicators: false,
  images: {
    unoptimized: true,
  },
  transpilePackages: ["@chakra-ui/react", "@chakra-ui/icons", "@ark-ui/react"],
  outputFileTracingRoot: process.cwd(),

  // #11 fix: source maps and minification were disabled as a workaround for
  // an old SWC bug. Modern Next.js handles both correctly. Re-enable for
  // production performance and security (unminified bundles expose logic).
  productionBrowserSourceMaps: false,

  experimental: {
    externalDir: true,
  },

  // Re-enable minification (was disabled via a workaround for an old SWC bug).
  webpack: (config, { isServer }) => {
    return config;
  },

  // Silence Turbopack + webpack config conflict
  turbopack: {},
  async rewrites() {
    // Single source of truth for the backend the UI talks to:
    // NEXT_PUBLIC_API_URL in frontend-nextjs/.env.local (default
    // http://localhost:8001). The destinations below are written with a
    // "127.0.0.1:8000" PLACEHOLDER that gets replaced with backendUrl at the
    // end of this function — the 8000s here are NOT the real target. Don't
    // "fix" them; change .env.local (or start the backend with
    // scripts/start-backend.sh, which reads it) instead.
    const backendUrl = (process.env.NEXT_PUBLIC_API_URL || nextPublicApiUrl || "http://127.0.0.1:8000").replace(/\/$/, "");
    const rawRewrites = [
      {
        source: "/api/sales/:path*",
        destination: "http://127.0.0.1:8000/api/sales/:path*",
      },
      {
        source: "/api/accounting/:path*",
        destination: "http://127.0.0.1:8000/api/accounting/:path*",
      },
      {
        source: "/api/integrations/:path*",
        destination: "http://127.0.0.1:8000/api/integrations/:path*",
      },
      // Data-ingestion + memory endpoints (sync status, ingestion progress,
      // memory records) — previously only reachable via NEXT_PUBLIC_API_URL.
      {
        source: "/api/data-ingestion/:path*",
        destination: "http://127.0.0.1:8000/api/data-ingestion/:path*",
      },
      {
        source: "/api/memory/:path*",
        destination: "http://127.0.0.1:8000/api/memory/:path*",
      },
      // Round 80b: journey pages (dropbox/telegram/gitlab/xero/monday/whatsapp)
      // call these bare prefixes; the backend boot-mounts the real routers at
      // these exact paths (main_api_app.py "FORCED JOURNEY ROUTER REGISTRATION").
      {
        source: "/api/dropbox/:path*",
        destination: "http://127.0.0.1:8000/api/dropbox/:path*",
      },
      {
        source: "/api/gitlab/:path*",
        destination: "http://127.0.0.1:8000/api/gitlab/:path*",
      },
      {
        source: "/api/monday/:path*",
        destination: "http://127.0.0.1:8000/api/monday/:path*",
      },
      {
        source: "/api/telegram/:path*",
        destination: "http://127.0.0.1:8000/api/telegram/:path*",
      },
      {
        source: "/api/whatsapp/:path*",
        destination: "http://127.0.0.1:8000/api/whatsapp/:path*",
      },
      {
        source: "/api/xero/:path*",
        destination: "http://127.0.0.1:8000/api/xero/:path*",
      },
      {
        source: "/api/chat/:path*",
        destination: "http://127.0.0.1:8000/api/chat/:path*",
      },
      {
        source: "/api/zoho-workdrive/:path*",
        destination: "http://127.0.0.1:8000/api/zoho-workdrive/:path*",
      },
      // Round 83: OneDrive/GDrive integration panels call these bare
      // prefixes; the backend boot-mounts the real journey routers at these
      // exact paths (main_api_app.py "Round 83 journey route repair").
      {
        source: "/api/onedrive/:path*",
        destination: "http://127.0.0.1:8000/api/onedrive/:path*",
      },
      {
        source: "/api/gdrive/:path*",
        destination: "http://127.0.0.1:8000/api/gdrive/:path*",
      },
      {
        source: "/api/ingest-gdrive-document",
        destination: "http://127.0.0.1:8000/api/ingest-gdrive-document",
      },
      {
        source: "/api/v1/:path*",
        destination: "http://127.0.0.1:8000/api/v1/:path*",
      },
      // NOTE: Do NOT add a broad /api/auth/:path* → backend proxy here.
      // NextAuth's own internal routes — /api/auth/session, /api/auth/csrf,
      // /api/auth/providers, /api/auth/signout — are served by the Next.js
      // [...nextauth].ts handler and must NOT be forwarded to the Python backend.
      // Specific backend auth routes are enumerated individually below.
      {
        source: "/api/shopify/:path*",
        destination: "http://127.0.0.1:8000/api/shopify/:path*",
      },
      {
        source: "/api/workflows/:path*",
        destination: "http://127.0.0.1:8000/api/v1/workflow-ui/:path*",
      },
      {
        source: "/api/ai/:path*",
        destination: "http://127.0.0.1:8000/api/ai/:path*",
      },
      {
        source: "/api/system/:path*",
        destination: "http://127.0.0.1:8000/api/v1/system/:path*",
      },
      {
        source: "/api/analytics/:path*",
        destination: "http://127.0.0.1:8000/api/v1/analytics/:path*",
      },
      {
        source: "/api/workflow-templates",
        destination: "http://127.0.0.1:8000/api/workflow-templates/",
      },
      {
        source: "/api/workflow-templates/:path*",
        destination: "http://127.0.0.1:8000/api/workflow-templates/:path*",
      },
      {
        source: "/api/workflow-agent/:path*",
        destination: "http://127.0.0.1:8000/api/workflow-agent/:path*",
      },
      {
        source: "/api/v1/employee/:path*",
        destination: "http://127.0.0.1:8000/api/v1/employee/:path*",
      },
      {
        source: "/api/atom-agent/:path*",
        destination: "http://127.0.0.1:8000/api/atom-agent/:path*",
      },
      {
        source: "/api/intelligence/:path*",
        destination: "http://127.0.0.1:8000/api/intelligence/:path*",
      },
      {
        source: "/api/time-travel/:path*",
        destination: "http://127.0.0.1:8000/api/time-travel/:path*",
      },
      // Chat Rewrite
      {
        source: "/api/chat/:path*",
        destination: "http://127.0.0.1:8000/api/chat/:path*",
      },
      // Admin Rewrite
      {
        source: "/api/admin/:path*",
        destination: "http://127.0.0.1:8000/api/admin/:path*",
      },
      {
        source: "/api/admin",
        destination: "http://127.0.0.1:8000/api/admin",
      },
      // Marketing Rewrite
      {
        source: "/api/marketing/:path*",
        destination: "http://127.0.0.1:8000/api/marketing/:path*",
      },
      {
        source: "/api/marketing",
        destination: "http://127.0.0.1:8000/api/marketing",
      },
      // Documents Rewrite
      {
        source: "/api/documents/:path*",
        destination: "http://127.0.0.1:8000/api/documents/:path*",
      },
      {
        source: "/api/documents",
        destination: "http://127.0.0.1:8000/api/documents",
      },
      // Boards Rewrite
      {
        source: "/api/boards/:path*",
        destination: "http://127.0.0.1:8000/api/boards/:path*",
      },
      {
        source: "/api/onboarding/:path*",
        destination: "http://127.0.0.1:8000/api/onboarding/:path*",
      },
      {
        source: "/api/users/:path*",
        destination: "http://127.0.0.1:8000/api/users/:path*",
      },
      // Integration API rewrites (Outlook, etc.)
      {
        source: "/api/integrations/:path*",
        destination: "http://127.0.0.1:8000/api/integrations/:path*",
      },
      // Add general API rewrite for other endpoints
      {
        source: "/api/v1/:path*",
        destination: "http://127.0.0.1:8000/api/v1/:path*",
      },
      // Specific Auth Rewrites (Delegate only these to Python Backend)
      {
        source: "/api/auth/:service/authorize",
        destination: "http://127.0.0.1:8000/api/auth/:service/authorize",
      },
      {
        source: "/api/auth/:service/initiate",
        destination: "http://127.0.0.1:8000/api/auth/:service/initiate",
      },
      {
        source: "/api/auth/:service/status",
        destination: "http://127.0.0.1:8000/api/auth/:service/status",
      },
      {
        source: "/api/auth/:service/disconnect",
        destination: "http://127.0.0.1:8000/api/auth/:service/disconnect",
      },
      {
        source: "/api/v1/auth/oauth/:path*",
        destination: "http://127.0.0.1:8000/api/v1/auth/oauth/:path*",
      },
      {
        source: "/api/auth/login",
        destination: "http://127.0.0.1:8000/api/auth/login",
      },
      {
        source: "/api/auth/register",
        destination: "http://127.0.0.1:8000/api/auth/register",
      },
      {
        source: "/api/auth/profile",
        destination: "http://127.0.0.1:8000/api/auth/profile",
      },
      {
        source: "/api/auth/me",
        destination: "http://127.0.0.1:8000/api/auth/me",
      },
      {
        source: "/api/auth/accounts",
        destination: "http://127.0.0.1:8000/api/auth/accounts",
      },
      {
        source: "/api/auth/logout",
        destination: "http://127.0.0.1:8000/api/auth/logout",
      },
      {
        source: "/api/auth/refresh",
        destination: "http://127.0.0.1:8000/api/auth/refresh",
      },
      {
        source: "/api/auth/forgot-password",
        destination: "http://127.0.0.1:8000/api/auth/forgot-password",
      },
      {
        source: "/api/auth/reset-password",
        destination: "http://127.0.0.1:8000/api/auth/reset-password",
      },
      {
        source: "/api/auth/verify-token",
        destination: "http://127.0.0.1:8000/api/auth/verify-token",
      },
      {
        source: "/api/auth/change-password",
        destination: "http://127.0.0.1:8000/api/auth/change-password",
      },
      {
        source: "/api/atom/:path*",
        destination: "http://127.0.0.1:8000/api/atom/:path*",
      },
      {
        source: "/api/agents",
        destination: "http://127.0.0.1:8000/api/agents/",
      },
      {
        source: "/api/agents/",
        destination: "http://127.0.0.1:8000/api/agents/",
      },
      {
        source: "/api/agents/:path*",
        destination: "http://127.0.0.1:8000/api/agents/:path*",
      },
      // R82: episodic-memory surfaces (MemoryRecallFeed trajectory feed)
      {
        source: "/api/episodes",
        destination: "http://127.0.0.1:8000/api/episodes",
      },
      {
        source: "/api/episodes/:path*",
        destination: "http://127.0.0.1:8000/api/episodes/:path*",
      },
      // R82: agent maturity/training surfaces (Approvals page training proposals)
      {
        source: "/api/maturity",
        destination: "http://127.0.0.1:8000/api/maturity",
      },
      {
        source: "/api/maturity/:path*",
        destination: "http://127.0.0.1:8000/api/maturity/:path*",
      },
      // WebSocket Proxy - REMOVED to prevent ECONNRESET crashes
      // Frontend now connects directly to port 8000 (see hooks/useWebSocket.ts)
      /*
      {
        source: "/ws",
        destination: "http://127.0.0.1:8000/ws",
      },
      {
        source: "/ws/:path*",
        destination: "http://127.0.0.1:8000/ws/:path*",
      }
      */
    ];
    return rawRewrites.map(rewrite => ({
      ...rewrite,
      destination: rewrite.destination.replace("http://127.0.0.1:8000", backendUrl)
    }));
  },
};

const withBundleAnalyzer = require('@next/bundle-analyzer')({
  enabled: process.env.ANALYZE === 'true',
});

module.exports = withBundleAnalyzer(nextConfig);
