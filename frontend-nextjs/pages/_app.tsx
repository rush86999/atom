import React from "react";
import { SessionProvider } from "next-auth/react";
import type { AppProps } from "next/app";

import { ToastProvider } from "../components/ui/use-toast";
import { GlobalChatWidget } from "../components/GlobalChatWidget";
import "../styles/globals.css";

function MyApp({ Component, pageProps: { session, ...pageProps } }: AppProps) {
  return (
    <SessionProvider session={session}>
      <ToastProvider>
        <Component {...pageProps} />
        <GlobalChatWidget />
      </ToastProvider>
    </SessionProvider>
  );
}

export default MyApp;

