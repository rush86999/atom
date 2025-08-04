"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AppState = AppState;
const jsx_runtime_1 = require("react/jsx-runtime");
/* eslint-disable */
require("../styles/globals.css");
require("../styles/burger.css");
require("../styles/Calendar.css");
// import '../styles/DatePicker.css'
require("../styles/DateTimePicker.css");
require("../styles/chat-style.css");
require("@fontsource/roboto/300.css");
require("@fontsource/roboto/400.css");
require("@fontsource/roboto/500.css");
require("@fontsource/roboto/700.css");
require("@styles/react-big-calendar.css");
require("@styles/drag-and-drop-big-calendar.css");
// import 'react-big-calendar/lib/css/react-big-calendar.css'
// import 'react-big-calendar/lib/addons/dragAndDrop/styles.css'
require("setimmediate");
const user_context_1 = require("@lib/user-context");
const client_1 = require("@apollo/client");
const react_1 = require("react");
const apollo_1 = __importDefault(require("@lib/apollo/apollo"));
const react_2 = require("@chakra-ui/react");
// import { Spinner } from '@chakra-ui/react' // Spinner seems unused here, consider removing if not needed elsewhere
const SideBarWithHeader_1 = __importDefault(require("@layouts/SideBarWithHeader"));
const restyle_1 = require("@shopify/restyle"); // Aliased to avoid conflict
const theme_1 = require("@lib/theme/theme");
// import { useRouter } from 'next/router' // useRouter seems unused here
const styles_1 = require("@mui/material/styles");
const react_3 = require("@emotion/react");
const theme_2 = __importDefault(require("@lib/mui/theme"));
const createEmotionCache_1 = __importDefault(require("@lib/mui/createEmotionCache"));
const head_1 = __importDefault(require("next/head"));
const react_modal_1 = __importDefault(require("react-modal"));
const tooltip_1 = require("@components/chat/ui/tooltip"); // Aliased
const AudioModeContext_1 = require("@lib/contexts/AudioModeContext");
const AgentAudioControlContext_1 = require("contexts/AgentAudioControlContext");
const WakeWordContext_1 = require("contexts/WakeWordContext");
const userRoleContext_1 = require("../contexts/userRole/userRoleContext");
const finance_1 = require("../contexts/finance");
const ThemeContext_1 = require("@lib/contexts/ThemeContext"); // Our new ThemeProvider
const session_1 = __importDefault(require("supertokens-web-js/recipe/session"));
const supertokens_auth_react_1 = __importStar(require("supertokens-auth-react"));
const frontendConfig_1 = require("../config/frontendConfig");
const supertokens_auth_react_2 = require("supertokens-auth-react");
if (typeof window !== "undefined") {
    // we only want to call this init function on the frontend, so we check typeof window !== 'undefined'
    supertokens_auth_react_1.default.init((0, frontendConfig_1.frontendConfig)());
}
const clientSideEmotionCache = (0, createEmotionCache_1.default)();
react_modal_1.default.setAppElement("#modal-root");
function AppState({ children }) {
    const [sub, setSub] = (0, react_1.useState)("");
    const [client, setClient] = (0, react_1.useState)(new client_1.ApolloClient({ cache: new client_1.InMemoryCache() }));
    const [activeToken, setActiveToken] = (0, react_1.useState)("");
    const router = useRouter();
    // always get latest token
    (0, react_1.useEffect)(() => {
        (async () => {
            try {
                const token = await session_1.default.getAccessToken();
                if (token !== activeToken) {
                    console.log(token, " token refreshed");
                    setActiveToken(token);
                }
            }
            catch (e) {
                console.log(e, " unable to get latest token");
            }
        })();
    });
    // make apollo client
    (0, react_1.useEffect)(() => {
        (async () => {
            try {
                // if (!activeToken) {
                //   return
                // }
                const token = await session_1.default.getAccessToken();
                if (!token) {
                    console.log("no token inside make apollo client");
                    return;
                }
                console.log(token, " token inside make apollo client");
                if (!token)
                    return;
                const newClient = await (0, apollo_1.default)(token);
                setClient(newClient);
            }
            catch (e) {
                console.log(e, " unable to make apollo client");
            }
        })();
    }, [activeToken]);
    (0, react_1.useEffect)(() => {
        (async () => {
            try {
                const userId = await session_1.default.getUserId();
                console.log(userId, " userId");
                setSub(userId);
            }
            catch (e) {
                console.log(e, " something went wrong with getting sub inside UserNavigation");
            }
        })();
    }, []);
    console.log(sub, " prerender sub");
    return ((0, jsx_runtime_1.jsx)(supertokens_auth_react_1.SuperTokensWrapper, { children: (0, jsx_runtime_1.jsx)(client_1.ApolloProvider, { client: client, children: (0, jsx_runtime_1.jsx)(user_context_1.AppContext.Provider, { value: {
                    sub,
                    client: client,
                }, children: (0, jsx_runtime_1.jsxs)(tooltip_1.TooltipProvider, { children: [" ", children] }) }) }) }));
}
function MyApp({ Component, emotionCache = clientSideEmotionCache, pageProps, }) {
    (0, react_1.useEffect)(() => {
        async function doRefresh() {
            if (pageProps.fromSupertokens === "needs-refresh") {
                if (await session_1.default.attemptRefreshingSession()) {
                    location.reload();
                }
                else {
                    (0, supertokens_auth_react_2.redirectToAuth)();
                }
            }
        }
        doRefresh();
    }, [pageProps.fromSupertokens]);
    return ((0, jsx_runtime_1.jsxs)(ThemeContext_1.ThemeProvider, { children: [" ", (0, jsx_runtime_1.jsxs)(react_3.CacheProvider, { value: emotionCache, children: [(0, jsx_runtime_1.jsx)(head_1.default, { children: (0, jsx_runtime_1.jsx)("meta", { name: "viewport", content: "initial-scale=1, width=device-width" }) }), (0, jsx_runtime_1.jsx)(styles_1.ThemeProvider, { theme: theme_2.default, children: (0, jsx_runtime_1.jsx)(react_2.ChakraProvider, { children: (0, jsx_runtime_1.jsxs)(restyle_1.ThemeProvider, { theme: theme_1.theme, children: [" ", (0, jsx_runtime_1.jsx)(AudioModeContext_1.AudioModeProvider, { children: (0, jsx_runtime_1.jsx)(AgentAudioControlContext_1.AgentAudioControlProvider, { children: (0, jsx_runtime_1.jsx)(WakeWordContext_1.WakeWordProvider, { children: (0, jsx_runtime_1.jsx)(userRoleContext_1.UserRoleProvider, { children: (0, jsx_runtime_1.jsx)(finance_1.FinanceProvider, { children: (0, jsx_runtime_1.jsx)(AppState, { children: (0, jsx_runtime_1.jsx)(SideBarWithHeader_1.default, { children: (0, jsx_runtime_1.jsx)(Component, { ...pageProps }) }) }) }) }) }) }) })] }) }) })] })] }));
}
exports.default = MyApp;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiX2FwcC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIl9hcHAudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0FBdUVBLDRCQWtGQzs7QUF6SkQsb0JBQW9CO0FBQ3BCLGlDQUErQjtBQUMvQixnQ0FBOEI7QUFDOUIsa0NBQWdDO0FBQ2hDLG9DQUFvQztBQUNwQyx3Q0FBc0M7QUFDdEMsb0NBQWtDO0FBQ2xDLHNDQUFvQztBQUNwQyxzQ0FBb0M7QUFDcEMsc0NBQW9DO0FBQ3BDLHNDQUFvQztBQUNwQywwQ0FBd0M7QUFDeEMsa0RBQWdEO0FBRWhELDZEQUE2RDtBQUM3RCxnRUFBZ0U7QUFDaEUsd0JBQXNCO0FBRXRCLG9EQUErQztBQUMvQywyQ0FLd0I7QUFDeEIsaUNBQTRDO0FBQzVDLGdFQUFrRDtBQUdsRCw0Q0FBa0Q7QUFDbEQscUhBQXFIO0FBQ3JILG1GQUEyRDtBQUMzRCw4Q0FBeUUsQ0FBQyw0QkFBNEI7QUFFdEcsNENBRTBCO0FBRTFCLHlFQUF5RTtBQUN6RSxpREFBeUU7QUFDekUsMENBQTZEO0FBQzdELDJEQUFzQztBQUN0QyxxRkFBNkQ7QUFDN0QscURBQTZCO0FBQzdCLDhEQUFnQztBQUVoQyx5REFBc0YsQ0FBQyxVQUFVO0FBQ2pHLHFFQUFtRTtBQUNuRSxnRkFBOEU7QUFDOUUsOERBQTREO0FBQzVELDBFQUF3RTtBQUN4RSxpREFBc0Q7QUFDdEQsNkRBQStFLENBQUMsd0JBQXdCO0FBQ3hHLGdGQUF3RDtBQUN4RCxpRkFBOEU7QUFDOUUsNkRBQTBEO0FBQzFELG1FQUF3RDtBQUV4RCxJQUFJLE9BQU8sTUFBTSxLQUFLLFdBQVcsRUFBRSxDQUFDO0lBQ2xDLHFHQUFxRztJQUNyRyxnQ0FBZ0IsQ0FBQyxJQUFJLENBQUMsSUFBQSwrQkFBYyxHQUFFLENBQUMsQ0FBQztBQUMxQyxDQUFDO0FBRUQsTUFBTSxzQkFBc0IsR0FBRyxJQUFBLDRCQUFrQixHQUFFLENBQUM7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WSxhQUN0QyxHQUFHLEVBRUosdUJBQUMsb0NBQWlCLGNBQ2hCLHVCQUFDLG9EQUF5QixjQUN4Qix1QkFBQyxrQ0FBZ0IsY0FDZix1QkFBQyxrQ0FBZ0IsY0FDZix1QkFBQyx5QkFBZSxjQUNkLHVCQUFDLFFBQVEsY0FDUCx1QkFBQywyQkFBaUIsY0FDaEIsdUJBQUMsU0FBUyxPQUFLLFNBQVMsR0FBSSxHQUNWLEdBQ1gsR0FDSyxHQUNELEdBQ0YsR0FDTyxHQUNWLElBQ0MsR0FDUixHQUNBLElBQ0wsSUFDQyxDQUNwQixDQUFDO0FBQ0osQ0FBQztBQUVELGtCQUFlLEtBQUssQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbIi8qIGVzbGludC1kaXNhYmxlICovXG5pbXBvcnQgXCIuLi9zdHlsZXMvZ2xvYmFscy5jc3NcIjtcbmltcG9ydCBcIi4uL3N0eWxlcy9idXJnZXIuY3NzXCI7XG5pbXBvcnQgXCIuLi9zdHlsZXMvQ2FsZW5kYXIuY3NzXCI7XG4vLyBpbXBvcnQgJy4uL3N0eWxlcy9EYXRlUGlja2VyLmNzcydcbmltcG9ydCBcIi4uL3N0eWxlcy9EYXRlVGltZVBpY2tlci5jc3NcIjtcbmltcG9ydCBcIi4uL3N0eWxlcy9jaGF0LXN0eWxlLmNzc1wiO1xuaW1wb3J0IFwiQGZvbnRzb3VyY2Uvcm9ib3RvLzMwMC5jc3NcIjtcbmltcG9ydCBcIkBmb250c291cmNlL3JvYm90by80MDAuY3NzXCI7XG5pbXBvcnQgXCJAZm9udHNvdXJjZS9yb2JvdG8vNTAwLmNzc1wiO1xuaW1wb3J0IFwiQGZvbnRzb3VyY2Uvcm9ib3RvLzcwMC5jc3NcIjtcbmltcG9ydCBcIkBzdHlsZXMvcmVhY3QtYmlnLWNhbGVuZGFyLmNzc1wiO1xuaW1wb3J0IFwiQHN0eWxlcy9kcmFnLWFuZC1kcm9wLWJpZy1jYWxlbmRhci5jc3NcIjtcblxuLy8gaW1wb3J0ICdyZWFjdC1iaWctY2FsZW5kYXIvbGliL2Nzcy9yZWFjdC1iaWctY2FsZW5kYXIuY3NzJ1xuLy8gaW1wb3J0ICdyZWFjdC1iaWctY2FsZW5kYXIvbGliL2FkZG9ucy9kcmFnQW5kRHJvcC9zdHlsZXMuY3NzJ1xuaW1wb3J0IFwic2V0aW1tZWRpYXRlXCI7XG5cbmltcG9ydCB7IEFwcENvbnRleHQgfSBmcm9tIFwiQGxpYi91c2VyLWNvbnRleHRcIjtcbmltcG9ydCB7XG4gIEFwb2xsb0NsaWVudCxcbiAgQXBvbGxvUHJvdmlkZXIsXG4gIEluTWVtb3J5Q2FjaGUsXG4gIE5vcm1hbGl6ZWRDYWNoZU9iamVjdCxcbn0gZnJvbSBcIkBhcG9sbG8vY2xpZW50XCI7XG5pbXBvcnQgeyB1c2VFZmZlY3QsIHVzZVN0YXRlIH0gZnJvbSBcInJlYWN0XCI7XG5pbXBvcnQgbWFrZUFwb2xsb0NsaWVudCBmcm9tIFwiQGxpYi9hcG9sbG8vYXBvbGxvXCI7XG5pbXBvcnQgeyBBcHBQcm9wcyB9IGZyb20gXCJuZXh0L2FwcFwiO1xuXG5pbXBvcnQgeyBDaGFrcmFQcm92aWRlciB9IGZyb20gXCJAY2hha3JhLXVpL3JlYWN0XCI7XG4vLyBpbXBvcnQgeyBTcGlubmVyIH0gZnJvbSAnQGNoYWtyYS11aS9yZWFjdCcgLy8gU3Bpbm5lciBzZWVtcyB1bnVzZWQgaGVyZSwgY29uc2lkZXIgcmVtb3ZpbmcgaWYgbm90IG5lZWRlZCBlbHNld2hlcmVcbmltcG9ydCBTaWRlQmFyV2l0aEhlYWRlciBmcm9tIFwiQGxheW91dHMvU2lkZUJhcldpdGhIZWFkZXJcIjtcbmltcG9ydCB7IFRoZW1lUHJvdmlkZXIgYXMgU2hvcGlmeVRoZW1lUHJvdmlkZXIgfSBmcm9tIFwiQHNob3BpZnkvcmVzdHlsZVwiOyAvLyBBbGlhc2VkIHRvIGF2b2lkIGNvbmZsaWN0XG5cbmltcG9ydCB7XG4gIHRoZW1lIGFzIHNob3BpZnlUaGVtZSwgLy8gQWxpYXNlZCB0byBhdm9pZCBjb25mbGljdFxufSBmcm9tIFwiQGxpYi90aGVtZS90aGVtZVwiO1xuXG4vLyBpbXBvcnQgeyB1c2VSb3V0ZXIgfSBmcm9tICduZXh0L3JvdXRlcicgLy8gdXNlUm91dGVyIHNlZW1zIHVudXNlZCBoZXJlXG5pbXBvcnQgeyBUaGVtZVByb3ZpZGVyIGFzIE1VSVRoZW1lUHJvdmlkZXIgfSBmcm9tIFwiQG11aS9tYXRlcmlhbC9zdHlsZXNcIjtcbmltcG9ydCB7IENhY2hlUHJvdmlkZXIsIEVtb3Rpb25DYWNoZSB9IGZyb20gXCJAZW1vdGlvbi9yZWFjdFwiO1xuaW1wb3J0IE1VSVRoZW1lIGZyb20gXCJAbGliL211aS90aGVtZVwiO1xuaW1wb3J0IGNyZWF0ZUVtb3Rpb25DYWNoZSBmcm9tIFwiQGxpYi9tdWkvY3JlYXRlRW1vdGlvbkNhY2hlXCI7XG5pbXBvcnQgSGVhZCBmcm9tIFwibmV4dC9oZWFkXCI7XG5pbXBvcnQgTW9kYWwgZnJvbSBcInJlYWN0LW1vZGFsXCI7XG5cbmltcG9ydCB7IFRvb2x0aXBQcm92aWRlciBhcyBSYWRpeFRvb2x0aXBQcm92aWRlciB9IGZyb20gXCJAY29tcG9uZW50cy9jaGF0L3VpL3Rvb2x0aXBcIjsgLy8gQWxpYXNlZFxuaW1wb3J0IHsgQXVkaW9Nb2RlUHJvdmlkZXIgfSBmcm9tIFwiQGxpYi9jb250ZXh0cy9BdWRpb01vZGVDb250ZXh0XCI7XG5pbXBvcnQgeyBBZ2VudEF1ZGlvQ29udHJvbFByb3ZpZGVyIH0gZnJvbSBcImNvbnRleHRzL0FnZW50QXVkaW9Db250cm9sQ29udGV4dFwiO1xuaW1wb3J0IHsgV2FrZVdvcmRQcm92aWRlciB9IGZyb20gXCJjb250ZXh0cy9XYWtlV29yZENvbnRleHRcIjtcbmltcG9ydCB7IFVzZXJSb2xlUHJvdmlkZXIgfSBmcm9tIFwiLi4vY29udGV4dHMvdXNlclJvbGUvdXNlclJvbGVDb250ZXh0XCI7XG5pbXBvcnQgeyBGaW5hbmNlUHJvdmlkZXIgfSBmcm9tIFwiLi4vY29udGV4dHMvZmluYW5jZVwiO1xuaW1wb3J0IHsgVGhlbWVQcm92aWRlciBhcyBBcHBUaGVtZVByb3ZpZGVyIH0gZnJvbSBcIkBsaWIvY29udGV4dHMvVGhlbWVDb250ZXh0XCI7IC8vIE91ciBuZXcgVGhlbWVQcm92aWRlclxuaW1wb3J0IFNlc3Npb24gZnJvbSBcInN1cGVydG9rZW5zLXdlYi1qcy9yZWNpcGUvc2Vzc2lvblwiO1xuaW1wb3J0IFN1cGVyVG9rZW5zUmVhY3QsIHsgU3VwZXJUb2tlbnNXcmFwcGVyIH0gZnJvbSBcInN1cGVydG9rZW5zLWF1dGgtcmVhY3RcIjtcbmltcG9ydCB7IGZyb250ZW5kQ29uZmlnIH0gZnJvbSBcIi4uL2NvbmZpZy9mcm9udGVuZENvbmZpZ1wiO1xuaW1wb3J0IHsgcmVkaXJlY3RUb0F1dGggfSBmcm9tIFwic3VwZXJ0b2tlbnMtYXV0aC1yZWFjdFwiO1xuXG5pZiAodHlwZW9mIHdpbmRvdyAhPT0gXCJ1bmRlZmluZWRcIikge1xuICAvLyB3ZSBvbmx5IHdhbnQgdG8gY2FsbCB0aGlzIGluaXQgZnVuY3Rpb24gb24gdGhlIGZyb250ZW5kLCBzbyB3ZSBjaGVjayB0eXBlb2Ygd2luZG93ICE9PSAndW5kZWZpbmVkJ1xuICBTdXBlclRva2Vuc1JlYWN0LmluaXQoZnJvbnRlbmRDb25maWcoKSk7XG59XG5cbmNvbnN0IGNsaWVudFNpZGVFbW90aW9uQ2FjaGUgPSBjcmVhdGVFbW90aW9uQ2FjaGUoKTtcblxuZXhwb3J0IGludGVyZmFjZSBNeUFwcFByb3BzIGV4dGVuZHMgQXBwUHJvcHMge1xuICBlbW90aW9uQ2FjaGU/OiBFbW90aW9uQ2FjaGU7XG59XG5cbk1vZGFsLnNldEFwcEVsZW1lbnQoXCIjbW9kYWwtcm9vdFwiKTtcblxuZXhwb3J0IGZ1bmN0aW9uIEFwcFN0YXRlKHsgY2hpbGRyZW4gfTogYW55KSB7XG4gIGNvbnN0IFtzdWIsIHNldFN1Yl0gPSB1c2VTdGF0ZTxzdHJpbmc+KFwiXCIpO1xuICBjb25zdCBbY2xpZW50LCBzZXRDbGllbnRdID1cbiAgICB1c2VTdGF0ZTxBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PiB8IG51bGw+KFxuICAgICAgbmV3IEFwb2xsb0NsaWVudCh7IGNhY2hlOiBuZXcgSW5NZW1vcnlDYWNoZSgpIH0pLFxuICAgICk7XG4gIGNvbnN0IFthY3RpdmVUb2tlbiwgc2V0QWN0aXZlVG9rZW5dID0gdXNlU3RhdGU8c3RyaW5nPihcIlwiKTtcblxuICBjb25zdCByb3V0ZXIgPSB1c2VSb3V0ZXIoKTtcblxuICAvLyBhbHdheXMgZ2V0IGxhdGVzdCB0b2tlblxuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIChhc3luYyAoKSA9PiB7XG4gICAgICB0cnkge1xuICAgICAgICBjb25zdCB0b2tlbiA9IGF3YWl0IFNlc3Npb24uZ2V0QWNjZXNzVG9rZW4oKTtcbiAgICAgICAgaWYgKHRva2VuICE9PSBhY3RpdmVUb2tlbikge1xuICAgICAgICAgIGNvbnNvbGUubG9nKHRva2VuLCBcIiB0b2tlbiByZWZyZXNoZWRcIik7XG4gICAgICAgICAgc2V0QWN0aXZlVG9rZW4odG9rZW4pO1xuICAgICAgICB9XG4gICAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKGUsIFwiIHVuYWJsZSB0byBnZXQgbGF0ZXN0IHRva2VuXCIpO1xuICAgICAgfVxuICAgIH0pKCk7XG4gIH0pO1xuXG4gIC8vIG1ha2UgYXBvbGxvIGNsaWVudFxuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIChhc3luYyAoKSA9PiB7XG4gICAgICB0cnkge1xuICAgICAgICAvLyBpZiAoIWFjdGl2ZVRva2VuKSB7XG4gICAgICAgIC8vICAgcmV0dXJuXG4gICAgICAgIC8vIH1cbiAgICAgICAgY29uc3QgdG9rZW4gPSBhd2FpdCBTZXNzaW9uLmdldEFjY2Vzc1Rva2VuKCk7XG4gICAgICAgIGlmICghdG9rZW4pIHtcbiAgICAgICAgICBjb25zb2xlLmxvZyhcIm5vIHRva2VuIGluc2lkZSBtYWtlIGFwb2xsbyBjbGllbnRcIik7XG4gICAgICAgICAgcmV0dXJuO1xuICAgICAgICB9XG4gICAgICAgIGNvbnNvbGUubG9nKHRva2VuLCBcIiB0b2tlbiBpbnNpZGUgbWFrZSBhcG9sbG8gY2xpZW50XCIpO1xuICAgICAgICBpZiAoIXRva2VuKSByZXR1cm47XG4gICAgICAgIGNvbnN0IG5ld0NsaWVudCA9IGF3YWl0IG1ha2VBcG9sbG9DbGllbnQodG9rZW4pO1xuICAgICAgICBzZXRDbGllbnQobmV3Q2xpZW50KTtcbiAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY29uc29sZS5sb2coZSwgXCIgdW5hYmxlIHRvIG1ha2UgYXBvbGxvIGNsaWVudFwiKTtcbiAgICAgIH1cbiAgICB9KSgpO1xuICB9LCBbYWN0aXZlVG9rZW5dKTtcblxuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIChhc3luYyAoKSA9PiB7XG4gICAgICB0cnkge1xuICAgICAgICBjb25zdCB1c2VySWQgPSBhd2FpdCBTZXNzaW9uLmdldFVzZXJJZCgpO1xuICAgICAgICBjb25zb2xlLmxvZyh1c2VySWQsIFwiIHVzZXJJZFwiKTtcbiAgICAgICAgc2V0U3ViKHVzZXJJZCk7XG4gICAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIGUsXG4gICAgICAgICAgXCIgc29tZXRoaW5nIHdlbnQgd3Jvbmcgd2l0aCBnZXR0aW5nIHN1YiBpbnNpZGUgVXNlck5hdmlnYXRpb25cIixcbiAgICAgICAgKTtcbiAgICAgIH1cbiAgICB9KSgpO1xuICB9LCBbXSk7XG5cbiAgY29uc29sZS5sb2coc3ViLCBcIiBwcmVyZW5kZXIgc3ViXCIpO1xuXG4gIHJldHVybiAoXG4gICAgPFN1cGVyVG9rZW5zV3JhcHBlcj5cbiAgICAgIDxBcG9sbG9Qcm92aWRlciBjbGllbnQ9e2NsaWVudH0+XG4gICAgICAgIDxBcHBDb250ZXh0LlByb3ZpZGVyXG4gICAgICAgICAgdmFsdWU9e3tcbiAgICAgICAgICAgIHN1YixcbiAgICAgICAgICAgIGNsaWVudDogY2xpZW50IGFzIG51bGwsXG4gICAgICAgICAgfX1cbiAgICAgICAgPlxuICAgICAgICAgIDxSYWRpeFRvb2x0aXBQcm92aWRlcj5cbiAgICAgICAgICAgIHtcIiBcIn1cbiAgICAgICAgICAgIHsvKiBDaGFuZ2VkIFRvb2x0aXBQcm92aWRlciB0byBSYWRpeFRvb2x0aXBQcm92aWRlciAqL31cbiAgICAgICAgICAgIHtjaGlsZHJlbn1cbiAgICAgICAgICA8L1JhZGl4VG9vbHRpcFByb3ZpZGVyPlxuICAgICAgICA8L0FwcENvbnRleHQuUHJvdmlkZXI+XG4gICAgICA8L0Fwb2xsb1Byb3ZpZGVyPlxuICAgIDwvU3VwZXJUb2tlbnNXcmFwcGVyPlxuICApO1xufVxuXG5mdW5jdGlvbiBNeUFwcCh7XG4gIENvbXBvbmVudCxcbiAgZW1vdGlvbkNhY2hlID0gY2xpZW50U2lkZUVtb3Rpb25DYWNoZSxcbiAgcGFnZVByb3BzLFxufTogTXlBcHBQcm9wcykge1xuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIGFzeW5jIGZ1bmN0aW9uIGRvUmVmcmVzaCgpIHtcbiAgICAgIGlmIChwYWdlUHJvcHMuZnJvbVN1cGVydG9rZW5zID09PSBcIm5lZWRzLXJlZnJlc2hcIikge1xuICAgICAgICBpZiAoYXdhaXQgU2Vzc2lvbi5hdHRlbXB0UmVmcmVzaGluZ1Nlc3Npb24oKSkge1xuICAgICAgICAgIGxvY2F0aW9uLnJlbG9hZCgpO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIHJlZGlyZWN0VG9BdXRoKCk7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9XG4gICAgZG9SZWZyZXNoKCk7XG4gIH0sIFtwYWdlUHJvcHMuZnJvbVN1cGVydG9rZW5zXSk7XG5cbiAgcmV0dXJuIChcbiAgICA8QXBwVGhlbWVQcm92aWRlcj5cbiAgICAgIHtcIiBcIn1cbiAgICAgIHsvKiBXcmFwIHdpdGggb3VyIG5ldyBUaGVtZVByb3ZpZGVyICovfVxuICAgICAgPENhY2hlUHJvdmlkZXIgdmFsdWU9e2Vtb3Rpb25DYWNoZX0+XG4gICAgICAgIDxIZWFkPlxuICAgICAgICAgIDxtZXRhIG5hbWU9XCJ2aWV3cG9ydFwiIGNvbnRlbnQ9XCJpbml0aWFsLXNjYWxlPTEsIHdpZHRoPWRldmljZS13aWR0aFwiIC8+XG4gICAgICAgIDwvSGVhZD5cbiAgICAgICAgPE1VSVRoZW1lUHJvdmlkZXIgdGhlbWU9e01VSVRoZW1lfT5cbiAgICAgICAgICA8Q2hha3JhUHJvdmlkZXI+XG4gICAgICAgICAgICA8U2hvcGlmeVRoZW1lUHJvdmlkZXIgdGhlbWU9e3Nob3BpZnlUaGVtZX0+XG4gICAgICAgICAgICAgIHtcIiBcIn1cbiAgICAgICAgICAgICAgey8qIFVzZSBhbGlhc2VkIFNob3BpZnlUaGVtZVByb3ZpZGVyIGFuZCB0aGVtZSAqL31cbiAgICAgICAgICAgICAgPEF1ZGlvTW9kZVByb3ZpZGVyPlxuICAgICAgICAgICAgICAgIDxBZ2VudEF1ZGlvQ29udHJvbFByb3ZpZGVyPlxuICAgICAgICAgICAgICAgICAgPFdha2VXb3JkUHJvdmlkZXI+XG4gICAgICAgICAgICAgICAgICAgIDxVc2VyUm9sZVByb3ZpZGVyPlxuICAgICAgICAgICAgICAgICAgICAgIDxGaW5hbmNlUHJvdmlkZXI+XG4gICAgICAgICAgICAgICAgICAgICAgICA8QXBwU3RhdGU+XG4gICAgICAgICAgICAgICAgICAgICAgICAgIDxTaWRlQmFyV2l0aEhlYWRlcj5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA8Q29tcG9uZW50IHsuLi5wYWdlUHJvcHN9IC8+XG4gICAgICAgICAgICAgICAgICAgICAgICAgIDwvU2lkZUJhcldpdGhIZWFkZXI+XG4gICAgICAgICAgICAgICAgICAgICAgICA8L0FwcFN0YXRlPlxuICAgICAgICAgICAgICAgICAgICAgIDwvRmluYW5jZVByb3ZpZGVyPlxuICAgICAgICAgICAgICAgICAgICA8L1VzZXJSb2xlUHJvdmlkZXI+XG4gICAgICAgICAgICAgICAgICA8L1dha2VXb3JkUHJvdmlkZXI+XG4gICAgICAgICAgICAgICAgPC9BZ2VudEF1ZGlvQ29udHJvbFByb3ZpZGVyPlxuICAgICAgICAgICAgICA8L0F1ZGlvTW9kZVByb3ZpZGVyPlxuICAgICAgICAgICAgPC9TaG9waWZ5VGhlbWVQcm92aWRlcj5cbiAgICAgICAgICA8L0NoYWtyYVByb3ZpZGVyPlxuICAgICAgICA8L01VSVRoZW1lUHJvdmlkZXI+XG4gICAgICA8L0NhY2hlUHJvdmlkZXI+XG4gICAgPC9BcHBUaGVtZVByb3ZpZGVyPlxuICApO1xufVxuXG5leHBvcnQgZGVmYXVsdCBNeUFwcDtcbiJdfQ==