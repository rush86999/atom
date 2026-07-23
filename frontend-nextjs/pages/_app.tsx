import React, { useState, useEffect } from "react";
import { SessionProvider, useSession } from "next-auth/react";
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { AppProps } from "next/app";

import { ToastProvider } from "../components/ui/use-toast";
import { GlobalChatWidget } from "../components/GlobalChatWidget";
import "../styles/globals.css";

import Layout from "../components/layout/Layout";
import { useRouter } from "next/router";
import { WakeWordProvider } from "../contexts/WakeWordContext";
import { useCliHandler } from "../hooks/useCliHandler";

const SessionSync: React.FC = () => {
  const { data: session } = useSession();

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
            const res = await fetch('/api/v1/preferences?user_id=default_user&workspace_id=default', { headers });
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
  const isStandalonePage = mounted ? (router.pathname.startsWith("/auth")) : false;


  return (
    <SessionProvider session={session}>
      <SessionSync />
      <QueryClientProvider client={queryClient}>
        <TauriHooks />
        <ChakraProvider value={defaultSystem}>
          <ToastProvider>
            <WakeWordProvider>
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

