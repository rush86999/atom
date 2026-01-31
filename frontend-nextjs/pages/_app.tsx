import React, { useState, useEffect } from "react";
import { SessionProvider } from "next-auth/react";
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import type { AppProps } from "next/app";

import { ToastProvider } from "../components/ui/use-toast";
import { GlobalChatWidget } from "../components/GlobalChatWidget";
import "../styles/globals.css";

import Layout from "../components/layout/Layout";
import { useRouter } from "next/router";
import { WakeWordProvider } from "../contexts/WakeWordContext";
import { useCliHandler } from "../hooks/useCliHandler";

function MyApp({ Component, pageProps: { session, ...pageProps } }: AppProps) {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  useCliHandler();

  useEffect(() => {
    setMounted(true);
  }, []);

  // Default to false during SSR/prerender to avoid router errors
  const isAuthPage = mounted ? router.pathname.startsWith("/auth") : false;


  return (
    <SessionProvider session={session}>
      <ChakraProvider value={defaultSystem}>
        <ToastProvider>
          <WakeWordProvider>
            {isAuthPage ? (
              <Component {...pageProps} />
            ) : (
              <Layout>
                <Component {...pageProps} />
              </Layout>
            )}
            {mounted && !isAuthPage && <GlobalChatWidget />}
          </WakeWordProvider>
        </ToastProvider>
      </ChakraProvider>
    </SessionProvider>
  );
}

export default MyApp;

