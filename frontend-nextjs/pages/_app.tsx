import React, { useState, useEffect } from "react";
import { SessionProvider, useSession } from "next-auth/react";
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { AppProps } from "next/app";
import { Toaster } from "sonner";

import { ToastProvider } from "../components/ui/use-toast";
import { GlobalChatWidget } from "../components/GlobalChatWidget";
import "../styles/globals.css";

import Layout from "../components/layout/Layout";
import { useRouter } from "next/router";
import { WakeWordProvider } from "../contexts/WakeWordContext";
import { useCliHandler } from "../hooks/useCliHandler";
import { getCurrentUserId } from "@/lib/identity";
import { checkApiVersion } from "@/lib/apiVersion";

// Dev diagnostics tap: capture load-time errors that kill hydration before
// any component effect can run (the direct-URL freeze on /canvas/[id] left
// no trace in the UI). Module scope so it installs BEFORE React hydrates.
// Read back in the console via window.__atomErrors. Dev only.
if (typeof window !== "undefined" && process.env.NODE_ENV !== "production") {
  const w = window as any;
  if (!w.__atomErrors) {
    w.__atomErrors = [];
    window.addEventListener("error", (e) => {
      const ee = e as ErrorEvent;
      w.__atomErrors.push(
        ee.message
          ? `error: ${ee.message} @ ${ee.filename}:${ee.lineno}`
          : `resource error: ${(e.target as HTMLScriptElement)?.src || (e.target as Element)?.tagName || "unknown"}`
      );
    }, true);  // capture: resource/script load failures don't bubble
    window.addEventListener("unhandledrejection", (e) => {
      w.__atomErrors.push(`rejection: ${String((e as PromiseRejectionEvent).reason).slice(0, 300)}`);
    });
    // React 19 reports hydration/uncaught render failures via console.error
    // (onUncaughtError / onRecoverableError), never reaching window.onerror.
    const origError = console.error.bind(console);
    console.error = (...args: unknown[]) => {
      try {
        w.__atomErrors.push(`console.error: ${args.map(a => (a instanceof Error ? a.stack || a.message : String(a))).join(" ").slice(0, 500)}`);
      } catch { /* never break the caller */ }
      origError(...args);
    };
  }

  // Direct-load route rescue: on direct URL loads the client router can
  // stay un-ready FOREVER — isReady never flips true, React never commits,
  // and the page freezes on its SSR shell (observed live on /canvas/[id]
  // AND /dashboard, Next 16.2.2 dev: zero console errors, zero resource
  // failures, no React keys on #__next — hydration simply never runs).
  // A single router.replace with the REAL location re-parses the route and
  // boots the page (verified live on /canvas/[id]: isReady flips, canvas
  // data loads). Healthy loads flip isReady within the grace period, so
  // the watchdog is a no-op for them; fires at most once per document.
  if (!w.__atomRouteRescue) {
    w.__atomRouteRescue = true;
    const rescue = () => {
      const r = (window as any).next?.router;
      if (!r || r.isReady) return;
      r.replace(window.location.pathname + window.location.search + window.location.hash);
    };
    const arm = () => setTimeout(rescue, 5000);
    if (document.readyState === "complete") arm();
    else window.addEventListener("load", arm, { once: true });
  }
}

const SessionSync: React.FC = () => {
  const { data: session } = useSession();

  useEffect(() => { checkApiVersion(); }, []);
  useEffect(() => {
    if (session && (session as any).backendToken) {
      const token = (session as any).backendToken;
      localStorage.setItem('auth_token', token);
      document.cookie = `auth_token=${token}; path=/; max-age=86400; SameSite=Lax`;
    }
  }, [session]);

  return null;
};

const TauriHooks: React.FC = () => {
  useCliHandler();
  return null;
};

function MyApp({ Component, pageProps: { session, ...pageProps } }: AppProps) {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        retry: false,
      },
    },
  }));

  useEffect(() => {
    setMounted(true);

    // Global Theme Application
    const applyTheme = (theme: string) => {
        const root = document.documentElement;
        if (theme === 'dark') {
            root.classList.add('dark');
        } else if (theme === 'light') {
            root.classList.remove('dark');
        } else {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            if (prefersDark) {
                root.classList.add('dark');
            } else {
                root.classList.remove('dark');
            }
        }
    };

    const loadTheme = async () => {
        try {
            const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
            const headers = {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            };
            const res = await fetch('/api/v1/preferences?user_id=${getCurrentUserId()}&workspace_id=default', { headers });
            if (res.ok) {
                const data = await res.json();
                if (data && data.theme) {
                    applyTheme(data.theme);
                    return;
                }
            }
            applyTheme('system');
        } catch (e) {
            applyTheme('system');
        }
    };

    loadTheme();
  }, []);

  // Default to false during SSR/prerender to avoid router errors
  const isStandalonePage = mounted ? (
    router.pathname.startsWith("/auth") ||
    router.pathname === "/login" ||
    router.pathname === "/register" ||
    router.pathname === "/forgot-password" ||
    router.pathname === "/reset-password"
  ) : false;


  return (
    <SessionProvider session={session} refetchInterval={0} refetchOnWindowFocus={false}>
      <SessionSync />
      <QueryClientProvider client={queryClient}>
        <TauriHooks />
        <ChakraProvider value={defaultSystem}>
          <ToastProvider>
            <WakeWordProvider>
              {/* Sonner toasts (ProjectCommandCenter, PipelineSettingsPanel, ...)
                  call the `toast` helper from "sonner" — without a mounted
                  <Toaster /> every one of those calls silently no-ops. */}
              <Toaster richColors position="top-right" />
              {isStandalonePage ? (
                <Component {...pageProps} />
              ) : (
                <Layout>
                  <Component {...pageProps} />
                </Layout>
              )}
              {mounted && !isStandalonePage && <GlobalChatWidget />}
            </WakeWordProvider>
          </ToastProvider>
        </ChakraProvider>
      </QueryClientProvider>
    </SessionProvider>
  );
}

export default MyApp;

