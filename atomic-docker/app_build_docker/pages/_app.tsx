/* eslint-disable */
import "../styles/globals.css";
import "../styles/burger.css";
import "../styles/Calendar.css";
// import '../styles/DatePicker.css'
import "../styles/DateTimePicker.css";
import "../styles/chat-style.css";
import "@fontsource/roboto/300.css";
import "@fontsource/roboto/400.css";
import "@fontsource/roboto/500.css";
import "@fontsource/roboto/700.css";
import "@styles/react-big-calendar.css";
import "@styles/drag-and-drop-big-calendar.css";

// import 'react-big-calendar/lib/css/react-big-calendar.css'
// import 'react-big-calendar/lib/addons/dragAndDrop/styles.css'
import "setimmediate";

import { AppContext } from "@lib/user-context";
import {
  ApolloClient,
  ApolloProvider,
  InMemoryCache,
  NormalizedCacheObject,
} from "@apollo/client";
import { useEffect, useState } from "react";
import makeApolloClient from "@lib/apollo/apollo";
import { AppProps } from "next/app";

import { ChakraProvider } from "@chakra-ui/react";
// import { Spinner } from '@chakra-ui/react' // Spinner seems unused here, consider removing if not needed elsewhere
import SideBarWithHeader from "@layouts/SideBarWithHeader";
import { ThemeProvider as ShopifyThemeProvider } from "@shopify/restyle"; // Aliased to avoid conflict

import {
  theme as shopifyTheme, // Aliased to avoid conflict
} from "@lib/theme/theme";

// import { useRouter } from 'next/router' // useRouter seems unused here
import { ThemeProvider as MUIThemeProvider } from "@mui/material/styles";
import { CacheProvider, EmotionCache } from "@emotion/react";
import MUITheme from "@lib/mui/theme";
import createEmotionCache from "@lib/mui/createEmotionCache";
import Head from "next/head";
import Modal from "react-modal";

import { TooltipProvider as RadixTooltipProvider } from "@components/chat/ui/tooltip"; // Aliased
import { AudioModeProvider } from "@lib/contexts/AudioModeContext";
import { AgentAudioControlProvider } from "contexts/AgentAudioControlContext";
import { WakeWordProvider } from "contexts/WakeWordContext";
import { UserRoleProvider } from "../contexts/userRole/userRoleContext";
import { FinanceProvider } from "../contexts/finance";
import { ThemeProvider as AppThemeProvider } from "@lib/contexts/ThemeContext"; // Our new ThemeProvider
import Session from "supertokens-web-js/recipe/session";
import SuperTokensReact, { SuperTokensWrapper } from "supertokens-auth-react";
import { frontendConfig } from "../config/frontendConfig";
import { redirectToAuth } from "supertokens-auth-react";

if (typeof window !== "undefined") {
  // we only want to call this init function on the frontend, so we check typeof window !== 'undefined'
  SuperTokensReact.init(frontendConfig());
}

const clientSideEmotionCache = createEmotionCache();

export interface MyAppProps extends AppProps {
  emotionCache?: EmotionCache;
}

Modal.setAppElement("#modal-root");

export function AppState({ children }: any) {
  const [sub, setSub] = useState<string>("");
  const [client, setClient] =
    useState<ApolloClient<NormalizedCacheObject> | null>(
      new ApolloClient({ cache: new InMemoryCache() }),
    );
  const [activeToken, setActiveToken] = useState<string>("");

  const router = useRouter();

  // always get latest token
  useEffect(() => {
    (async () => {
      try {
        const token = await Session.getAccessToken();
        if (token !== activeToken) {
          console.log(token, " token refreshed");
          setActiveToken(token);
        }
      } catch (e) {
        console.log(e, " unable to get latest token");
      }
    })();
  });

  // make apollo client
  useEffect(() => {
    (async () => {
      try {
        // if (!activeToken) {
        //   return
        // }
        const token = await Session.getAccessToken();
        if (!token) {
          console.log("no token inside make apollo client");
          return;
        }
        console.log(token, " token inside make apollo client");
        if (!token) return;
        const newClient = await makeApolloClient(token);
        setClient(newClient);
      } catch (e) {
        console.log(e, " unable to make apollo client");
      }
    })();
  }, [activeToken]);

  useEffect(() => {
    (async () => {
      try {
        const userId = await Session.getUserId();
        console.log(userId, " userId");
        setSub(userId);
      } catch (e) {
        console.log(
          e,
          " something went wrong with getting sub inside UserNavigation",
        );
      }
    })();
  }, []);

  console.log(sub, " prerender sub");

  return (
    <SuperTokensWrapper>
      <ApolloProvider client={client}>
        <AppContext.Provider
          value={{
            sub,
            client: client as null,
          }}
        >
          <RadixTooltipProvider>
            {" "}
            {/* Changed TooltipProvider to RadixTooltipProvider */}
            {children}
          </RadixTooltipProvider>
        </AppContext.Provider>
      </ApolloProvider>
    </SuperTokensWrapper>
  );
}

function MyApp({
  Component,
  emotionCache = clientSideEmotionCache,
  pageProps,
}: MyAppProps) {
  useEffect(() => {
    async function doRefresh() {
      if (pageProps.fromSupertokens === "needs-refresh") {
        if (await Session.attemptRefreshingSession()) {
          location.reload();
        } else {
          redirectToAuth();
        }
      }
    }
    doRefresh();
  }, [pageProps.fromSupertokens]);

  return (
    <AppThemeProvider>
      {" "}
      {/* Wrap with our new ThemeProvider */}
      <CacheProvider value={emotionCache}>
        <Head>
          <meta name="viewport" content="initial-scale=1, width=device-width" />
        </Head>
        <MUIThemeProvider theme={MUITheme}>
          <ChakraProvider>
            <ShopifyThemeProvider theme={shopifyTheme}>
              {" "}
              {/* Use aliased ShopifyThemeProvider and theme */}
              <AudioModeProvider>
                <AgentAudioControlProvider>
                  <WakeWordProvider>
                    <UserRoleProvider>
                      <FinanceProvider>
                        <AppState>
                          <SideBarWithHeader>
                            <Component {...pageProps} />
                          </SideBarWithHeader>
                        </AppState>
                      </FinanceProvider>
                    </UserRoleProvider>
                  </WakeWordProvider>
                </AgentAudioControlProvider>
              </AudioModeProvider>
            </ShopifyThemeProvider>
          </ChakraProvider>
        </MUIThemeProvider>
      </CacheProvider>
    </AppThemeProvider>
  );
}

export default MyApp;
