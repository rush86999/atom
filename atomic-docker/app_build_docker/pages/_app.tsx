/* eslint-disable */
import '../styles/globals.css'
import '../styles/burger.css'
import '../styles/Calendar.css'
// import '../styles/DatePicker.css'
import '../styles/DateTimePicker.css'
import '../styles/chat-style.css'
import '@fontsource/roboto/300.css'
import '@fontsource/roboto/400.css'
import '@fontsource/roboto/500.css'
import '@fontsource/roboto/700.css'
import '@styles/react-big-calendar.css'
import '@styles/drag-and-drop-big-calendar.css'

// import 'react-big-calendar/lib/css/react-big-calendar.css'
// import 'react-big-calendar/lib/addons/dragAndDrop/styles.css'
import 'setimmediate'

import { AppContext } from '@lib/user-context';
import { ApolloClient, ApolloProvider, InMemoryCache, NormalizedCacheObject } from '@apollo/client';
import { useEffect, useState } from 'react';
import makeApolloClient from '@lib/apollo/apollo';
import { AppProps } from 'next/app'

import { ChakraProvider } from '@chakra-ui/react'
import { Spinner } from '@chakra-ui/react'
import SideBarWithHeader from '@layouts/SideBarWithHeader'
import {ThemeProvider} from '@shopify/restyle'

import {
  theme,
} from '@lib/theme/theme'

import { useRouter } from 'next/router'
import { ThemeProvider as MUIThemeProvider } from '@mui/material/styles'
import { CacheProvider, EmotionCache } from '@emotion/react';
import MUITheme from '@lib/mui/theme';
import createEmotionCache from '@lib/mui/createEmotionCache'
import Head from 'next/head'
import Modal from 'react-modal'

import { TooltipProvider } from '@components/chat/ui/tooltip'
import { AudioModeProvider } from '@lib/contexts/AudioModeContext'; // Added AudioModeProvider
import Session from "supertokens-web-js/recipe/session"
import SuperTokensReact, { SuperTokensWrapper } from 'supertokens-auth-react'
import { frontendConfig } from '../config/frontendConfig'
import { redirectToAuth } from 'supertokens-auth-react'

if (typeof window !== 'undefined') {
  // we only want to call this init function on the frontend, so we check typeof window !== 'undefined'
  SuperTokensReact.init(frontendConfig())
}


const clientSideEmotionCache = createEmotionCache()

export interface MyAppProps extends AppProps {
  emotionCache?: EmotionCache;
}



Modal.setAppElement('#modal-root')

export function AppState({ children }: any) {
    const [sub, setSub] = useState<string>('')
    const [client, setClient] = useState<ApolloClient<NormalizedCacheObject> | null>(new ApolloClient({ cache: new InMemoryCache()}))
    const [activeToken, setActiveToken] = useState<string>('')

    const router = useRouter()


    // always get latest token
    useEffect(() => {
      (async () => {
        try {
          const token = await Session.getAccessToken()
          if (token !== activeToken) {
            console.log(token, ' token refreshed')
            setActiveToken(token)
          }
        } catch (e) {
          console.log(e, ' unable to get latest token')
        }
      })()
    })

    // make apollo client
    useEffect(() => {
      (async () => {
        try {
          // if (!activeToken) {
          //   return
          // }
          const token = await Session.getAccessToken()
          if (!token) {
            console.log('no token inside make apollo client')
            return
          }
          console.log(token, ' token inside make apollo client')
          if (!token) return
          const newClient = await makeApolloClient(token)
          setClient(newClient)
        } catch (e) {
          console.log(e, ' unable to make apollo client')
        }
      })()
    }, [activeToken])

    useEffect(() => {
      (async () => {
        try {
          const userId = await Session.getUserId()
          console.log(userId, ' userId')
          setSub(userId)
        } catch(e) {
          console.log(e, ' something went wrong with getting sub inside UserNavigation')

        }
      })()
    }, [])


    console.log(sub, ' prerender sub')

    return (
      <SuperTokensWrapper>
        <ApolloProvider client={client}>
          <AppContext.Provider value={{
            sub,
            client: client as null,
          }}>
            <TooltipProvider>
              {children}
            </TooltipProvider>
          
          </AppContext.Provider>
        </ApolloProvider>
      </SuperTokensWrapper>
    )
}

function MyApp({ Component, emotionCache = clientSideEmotionCache, pageProps }: MyAppProps) {
  

  useEffect(() => {

    async function doRefresh() {
        // pageProps.fromSupertokens === 'needs-refresh' will be true
        // when in getServerSideProps, getSession throws a TRY_REFRESH_TOKEN
        // error.

        if (pageProps.fromSupertokens === 'needs-refresh') {
            if (await Session.attemptRefreshingSession()) {
                // post session refreshing, we reload the page. This will
                // send the new access token to the server, and then 
                // getServerSideProps will succeed
                location.reload()
            } else {
                // the user's session has expired. So we redirect
                // them to the login page
                redirectToAuth()
            }
        }
    }
    doRefresh()

  }, [pageProps.fromSupertokens])


  return (
     <CacheProvider value={emotionCache}>
      <Head>
        <meta name="viewport" content="initial-scale=1, width=device-width" />
      </Head>
      <MUIThemeProvider theme={MUITheme}>


          <ChakraProvider>
            <ThemeProvider theme={theme}>
              <AudioModeProvider> {/* Wrap with AudioModeProvider */}
                <AppState>
                  <SideBarWithHeader>
                      <Component {...pageProps} />
                  </SideBarWithHeader>
                </AppState>
              </AudioModeProvider>
            </ThemeProvider>
            </ChakraProvider>
       
      </MUIThemeProvider>
    </CacheProvider>
  )
}

export default MyApp
