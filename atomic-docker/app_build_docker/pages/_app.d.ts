import "../styles/globals.css";
import "../styles/burger.css";
import "../styles/Calendar.css";
import "../styles/DateTimePicker.css";
import "../styles/chat-style.css";
import "@fontsource/roboto/300.css";
import "@fontsource/roboto/400.css";
import "@fontsource/roboto/500.css";
import "@fontsource/roboto/700.css";
import "@styles/react-big-calendar.css";
import "@styles/drag-and-drop-big-calendar.css";
import "setimmediate";
import { AppProps } from "next/app";
import { EmotionCache } from "@emotion/react";
export interface MyAppProps extends AppProps {
    emotionCache?: EmotionCache;
}
export declare function AppState({ children }: any): JSX.Element;
declare function MyApp({ Component, emotionCache, pageProps, }: MyAppProps): JSX.Element;
export default MyApp;
