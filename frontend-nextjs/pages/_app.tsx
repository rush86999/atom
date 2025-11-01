import React from "react";
import { SessionProvider } from "next-auth/react";
import type { AppProps } from "next/app";
import { ChakraProvider } from "@chakra-ui/react";
import { useEffect } from "react";
import { useRouter } from "next/router";

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
      <ChakraProvider>
        <Component {...pageProps} />
      </ChakraProvider>
    </SessionProvider>
  );
}

export default MyApp;
