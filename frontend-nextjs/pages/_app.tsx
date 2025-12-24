import React from "react";
import { SessionProvider } from "next-auth/react";
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import type { AppProps } from "next/app";

import { ToastProvider } from "../components/ui/use-toast";
import { GlobalChatWidget } from "../components/GlobalChatWidget";
import "../styles/globals.css";

import Layout from "../components/layout/Layout";
import { useRouter } from "next/router";

function MyApp({ Component, pageProps: { session, ...pageProps } }: AppProps) {
  const router = useRouter();
  const isAuthPage = router.pathname.startsWith("/auth");

  return (
    <SessionProvider session={session}>
      <ChakraProvider value={defaultSystem}>
        <ToastProvider>
          {isAuthPage ? (
            <Component {...pageProps} />
          ) : (
            <Layout>
              <Component {...pageProps} />
            </Layout>
          )}
          {!isAuthPage && <GlobalChatWidget />}
        </ToastProvider>
      </ChakraProvider>
    </SessionProvider>
  );
}

export default MyApp;

