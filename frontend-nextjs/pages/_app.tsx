import React from "react";
import { SessionProvider } from "next-auth/react";
import type { AppProps } from "next/app";

import { ToastProvider } from "../components/ui/use-toast";
import { useEffect } from "react";
import { useRouter } from "next/router";
import { GlobalChatWidget } from "../components/GlobalChatWidget";

function MyApp({ Component, pageProps: { session, ...pageProps } }: AppProps) {
  const router = useRouter();

  // Handle authentication redirects
  useEffect(() => {
    const { pathname } = router;

    // If user tries to access protected routes without session, redirect to signin
    const protectedRoutes = [
      "/",
      "/search",
      "/communication",
      "/tasks",
      "/automations",
      "/calendar",
      "/finance",
      "/voice",
    ];

    if (protectedRoutes.includes(pathname) && !session) {
      router.push("/auth/signin");
    }
  }, [router, session]);

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

