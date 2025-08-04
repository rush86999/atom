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
exports.default = MyDocument;
const jsx_runtime_1 = require("react/jsx-runtime");
// pages/_document.js
const document_1 = __importStar(require("next/document"));
const react_1 = require("@chakra-ui/react");
const create_instance_1 = __importDefault(require("@emotion/server/create-instance"));
const theme_1 = __importDefault(require("@lib/mui/theme"));
const createEmotionCache_1 = __importDefault(require("@lib/mui/createEmotionCache"));
function MyDocument(props) {
    const { emotionStyleTags } = props;
    return ((0, jsx_runtime_1.jsxs)(document_1.Html, { lang: 'en', children: [(0, jsx_runtime_1.jsxs)(document_1.Head, { children: [(0, jsx_runtime_1.jsx)("meta", { name: "theme-color", content: theme_1.default.palette.primary.main }), (0, jsx_runtime_1.jsx)("link", { rel: "shortcut icon", href: "/favicon.ico" }), (0, jsx_runtime_1.jsx)("meta", { name: "emotion-insertion-point", content: "" }), emotionStyleTags, (0, jsx_runtime_1.jsx)("link", { href: "https://fonts.googleapis.com/css?family=Heebo:300,400,500,700&display=swap", rel: "stylesheet" }), (0, jsx_runtime_1.jsx)("link", { rel: "stylesheet", href: "https://code.ionicframework.com/ionicons/2.0.1/css/ionicons.min.css" }), (0, jsx_runtime_1.jsx)("link", { rel: "stylesheet", href: "https://use.fontawesome.com/releases/v6.1.1/css/all.css" }), (0, jsx_runtime_1.jsx)("style", { type: "text/css", children: `
              @font-face {
                font-family: 'MaterialIcons';
                src: url(https://fonts.gstatic.com/s/materialicons/v140/flUhRq6tzZclQEJ-Vdg-IuiaDsNcIhQ8tQ.woff2) format('woff2');
              }

              @font-face {
                font-family: 'FontAwesome';
                src: url(https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.3.0/webfonts/fa-solid-900.woff2) format('woff2');
              }


              @font-face {
                font-family: 'Entypo';
                src: url(https://cdnjs.cloudflare.com/ajax/libs/entypo/2.0/entypo.woff) format('woff');
              }

              @font-face {
                font-family: 'MaterialCommunityIcons';
                src: url(https://cdn.jsdelivr.net/npm/@expo/vector-icons/build/vendor/react-native-vector-icons/Fonts/MaterialCommunityIcons.ttf) format('truetype');
              }

          ` })] }), (0, jsx_runtime_1.jsxs)("body", { children: [(0, jsx_runtime_1.jsx)(react_1.ColorModeScript, { initialColorMode: "system" }), (0, jsx_runtime_1.jsx)(document_1.Main, {}), (0, jsx_runtime_1.jsx)("div", { id: "modal-root" }), (0, jsx_runtime_1.jsx)(document_1.NextScript, {})] })] }));
}
MyDocument.getInitialProps = async (ctx) => {
    const originalRenderPage = ctx.renderPage;
    // You can consider sharing the same Emotion cache between all the SSR requests to speed up performance.
    // However, be aware that it can have global side effects.
    const cache = (0, createEmotionCache_1.default)();
    const { extractCriticalToChunks } = (0, create_instance_1.default)(cache);
    ctx.renderPage = () => originalRenderPage({
        enhanceApp: (App) => function EnhanceApp(props) {
            return (0, jsx_runtime_1.jsx)(App, { emotionCache: cache, ...props });
        },
    });
    const initialProps = await document_1.default.getInitialProps(ctx);
    // This is important. It prevents Emotion to render invalid HTML.
    // See https://github.com/mui/material-ui/issues/26561#issuecomment-855286153
    const emotionStyles = extractCriticalToChunks(initialProps.html);
    const emotionStyleTags = emotionStyles.styles.map((style) => ((0, jsx_runtime_1.jsx)("style", { "data-emotion": `${style.key} ${style.ids.join(' ')}`, 
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML: { __html: style.css } }, style.key)));
    return {
        ...initialProps,
        emotionStyleTags,
    };
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiX2RvY3VtZW50LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiX2RvY3VtZW50LnRzeCJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztBQW9CQSw2QkFzREM7O0FBMUVELHFCQUFxQjtBQUdyQiwwREFDeUM7QUFDekMsNENBQWtEO0FBSWxELHNGQUFrRTtBQUNsRSwyREFBbUM7QUFDbkMscUZBQTREO0FBUzVELFNBQXdCLFVBQVUsQ0FBQyxLQUFzQjtJQUN2RCxNQUFNLEVBQUUsZ0JBQWdCLEVBQUUsR0FBRyxLQUFLLENBQUM7SUFHakMsT0FBTyxDQUNMLHdCQUFDLGVBQUksSUFBQyxJQUFJLEVBQUMsSUFBSSxhQUNiLHdCQUFDLGVBQUksZUFDRixpQ0FBTSxJQUFJLEVBQUMsYUFBYSxFQUFDLE9BQU8sRUFBRSxlQUFLLENBQUMsT0FBTyxDQUFDLE9BQU8sQ0FBQyxJQUFJLEdBQUksRUFDakUsaUNBQU0sR0FBRyxFQUFDLGVBQWUsRUFBQyxJQUFJLEVBQUMsY0FBYyxHQUFHLEVBQ2hELGlDQUFNLElBQUksRUFBQyx5QkFBeUIsRUFBQyxPQUFPLEVBQUMsRUFBRSxHQUFHLEVBQ2pELGdCQUFnQixFQUNqQixpQ0FDRSxJQUFJLEVBQUMsNEVBQTRFLEVBQ2pGLEdBQUcsRUFBQyxZQUFZLEdBQ2hCLEVBQ0YsaUNBQU0sR0FBRyxFQUFDLFlBQVksRUFBQyxJQUFJLEVBQUMscUVBQXFFLEdBQVEsRUFFekcsaUNBQU0sR0FBRyxFQUFDLFlBQVksRUFBQyxJQUFJLEVBQUMseURBQXlELEdBQUcsRUFFeEYsa0NBQU8sSUFBSSxFQUFDLFVBQVUsWUFDbkI7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7V0FzQkYsR0FDTyxJQUNILEVBQ1AsNkNBQ0UsdUJBQUMsdUJBQWUsSUFBQyxnQkFBZ0IsRUFBQyxRQUFRLEdBQUcsRUFDN0MsdUJBQUMsZUFBSSxLQUFHLEVBQ1IsZ0NBQUssRUFBRSxFQUFDLFlBQVksR0FBTyxFQUMzQix1QkFBQyxxQkFBVSxLQUFHLElBRVQsSUFDRixDQUNSLENBQUE7QUFDTCxDQUFDO0FBRUQsVUFBVSxDQUFDLGVBQWUsR0FBRyxLQUFLLEVBQUUsR0FBb0IsRUFBRSxFQUFFO0lBRTNELE1BQU0sa0JBQWtCLEdBQUcsR0FBRyxDQUFDLFVBQVUsQ0FBQztJQUV6Qyx3R0FBd0c7SUFDeEcsMERBQTBEO0lBQzFELE1BQU0sS0FBSyxHQUFHLElBQUEsNEJBQWtCLEdBQUUsQ0FBQztJQUNuQyxNQUFNLEVBQUUsdUJBQXVCLEVBQUUsR0FBRyxJQUFBLHlCQUFtQixFQUFDLEtBQUssQ0FBQyxDQUFDO0lBRS9ELEdBQUcsQ0FBQyxVQUFVLEdBQUcsR0FBRyxFQUFFLENBQ3BCLGtCQUFrQixDQUFDO1FBQ2pCLFVBQVUsRUFBRSxDQUFDLEdBQW9FLEVBQUUsRUFBRSxDQUNuRixTQUFTLFVBQVUsQ0FBQyxLQUFLO1lBQ3ZCLE9BQU8sdUJBQUMsR0FBRyxJQUFDLFlBQVksRUFBRSxLQUFLLEtBQU0sS0FBSyxHQUFJLENBQUM7UUFDakQsQ0FBQztLQUNKLENBQUMsQ0FBQztJQUVMLE1BQU0sWUFBWSxHQUFHLE1BQU0sa0JBQVEsQ0FBQyxlQUFlLENBQUMsR0FBRyxDQUFDLENBQUM7SUFDekQsaUVBQWlFO0lBQ2pFLDZFQUE2RTtJQUM3RSxNQUFNLGFBQWEsR0FBRyx1QkFBdUIsQ0FBQyxZQUFZLENBQUMsSUFBSSxDQUFDLENBQUM7SUFDakUsTUFBTSxnQkFBZ0IsR0FBRyxhQUFhLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLEtBQUssRUFBRSxFQUFFLENBQUMsQ0FDM0Qsa0RBQ2dCLEdBQUcsS0FBSyxDQUFDLEdBQUcsSUFBSSxLQUFLLENBQUMsR0FBRyxDQUFDLElBQUksQ0FBQyxHQUFHLENBQUMsRUFBRTtRQUVuRCwyQ0FBMkM7UUFDM0MsdUJBQXVCLEVBQUUsRUFBRSxNQUFNLEVBQUUsS0FBSyxDQUFDLEdBQUcsRUFBRSxJQUZ6QyxLQUFLLENBQUMsR0FBRyxDQUdkLENBQ0gsQ0FBQyxDQUFDO0lBRUgsT0FBTztRQUNMLEdBQUcsWUFBWTtRQUNmLGdCQUFnQjtLQUNqQixDQUFDO0FBQ0osQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiLy8gcGFnZXMvX2RvY3VtZW50LmpzXG5cblxuaW1wb3J0IERvY3VtZW50LCB7IEh0bWwsIEhlYWQsIE1haW4sIE5leHRTY3JpcHQsICBEb2N1bWVudFByb3BzLFxuICBEb2N1bWVudENvbnRleHQsIH0gZnJvbSAnbmV4dC9kb2N1bWVudCdcbmltcG9ydCB7IENvbG9yTW9kZVNjcmlwdCB9IGZyb20gJ0BjaGFrcmEtdWkvcmVhY3QnXG5cbmltcG9ydCB7IEFwcFR5cGUgfSBmcm9tICduZXh0L2FwcCdcblxuaW1wb3J0IGNyZWF0ZUVtb3Rpb25TZXJ2ZXIgZnJvbSAnQGVtb3Rpb24vc2VydmVyL2NyZWF0ZS1pbnN0YW5jZSc7XG5pbXBvcnQgdGhlbWUgZnJvbSAnQGxpYi9tdWkvdGhlbWUnO1xuaW1wb3J0IGNyZWF0ZUVtb3Rpb25DYWNoZSBmcm9tICdAbGliL211aS9jcmVhdGVFbW90aW9uQ2FjaGUnXG5pbXBvcnQgeyBNeUFwcFByb3BzIH0gZnJvbSAnLi9fYXBwJztcblxuXG5cbmludGVyZmFjZSBNeURvY3VtZW50UHJvcHMgZXh0ZW5kcyBEb2N1bWVudFByb3BzIHtcbiAgZW1vdGlvblN0eWxlVGFnczogSlNYLkVsZW1lbnRbXTtcbn1cblxuZXhwb3J0IGRlZmF1bHQgZnVuY3Rpb24gTXlEb2N1bWVudChwcm9wczogTXlEb2N1bWVudFByb3BzKSB7XG4gIGNvbnN0IHsgZW1vdGlvblN0eWxlVGFncyB9ID0gcHJvcHM7XG5cbiAgXG4gICAgcmV0dXJuIChcbiAgICAgIDxIdG1sIGxhbmc9J2VuJz5cbiAgICAgICAgPEhlYWQ+XG4gICAgICAgICAgIDxtZXRhIG5hbWU9XCJ0aGVtZS1jb2xvclwiIGNvbnRlbnQ9e3RoZW1lLnBhbGV0dGUucHJpbWFyeS5tYWlufSAvPlxuICAgICAgICAgIDxsaW5rIHJlbD1cInNob3J0Y3V0IGljb25cIiBocmVmPVwiL2Zhdmljb24uaWNvXCIgLz5cbiAgICAgICAgICA8bWV0YSBuYW1lPVwiZW1vdGlvbi1pbnNlcnRpb24tcG9pbnRcIiBjb250ZW50PVwiXCIgLz5cbiAgICAgICAgICB7ZW1vdGlvblN0eWxlVGFnc31cbiAgICAgICAgICA8bGlua1xuICAgICAgICAgICAgaHJlZj1cImh0dHBzOi8vZm9udHMuZ29vZ2xlYXBpcy5jb20vY3NzP2ZhbWlseT1IZWVibzozMDAsNDAwLDUwMCw3MDAmZGlzcGxheT1zd2FwXCJcbiAgICAgICAgICAgIHJlbD1cInN0eWxlc2hlZXRcIlxuICAgICAgICAgIC8+XG4gICAgICAgICAgPGxpbmsgcmVsPVwic3R5bGVzaGVldFwiIGhyZWY9XCJodHRwczovL2NvZGUuaW9uaWNmcmFtZXdvcmsuY29tL2lvbmljb25zLzIuMC4xL2Nzcy9pb25pY29ucy5taW4uY3NzXCI+PC9saW5rPlxuICAgICAgICAgIFxuICAgICAgICAgIDxsaW5rIHJlbD1cInN0eWxlc2hlZXRcIiBocmVmPVwiaHR0cHM6Ly91c2UuZm9udGF3ZXNvbWUuY29tL3JlbGVhc2VzL3Y2LjEuMS9jc3MvYWxsLmNzc1wiIC8+XG5cbiAgICAgICAgICA8c3R5bGUgdHlwZT1cInRleHQvY3NzXCI+XG4gICAgICAgICAgICB7YFxuICAgICAgICAgICAgICBAZm9udC1mYWNlIHtcbiAgICAgICAgICAgICAgICBmb250LWZhbWlseTogJ01hdGVyaWFsSWNvbnMnO1xuICAgICAgICAgICAgICAgIHNyYzogdXJsKGh0dHBzOi8vZm9udHMuZ3N0YXRpYy5jb20vcy9tYXRlcmlhbGljb25zL3YxNDAvZmxVaFJxNnR6WmNsUUVKLVZkZy1JdWlhRHNOY0loUTh0US53b2ZmMikgZm9ybWF0KCd3b2ZmMicpO1xuICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgQGZvbnQtZmFjZSB7XG4gICAgICAgICAgICAgICAgZm9udC1mYW1pbHk6ICdGb250QXdlc29tZSc7XG4gICAgICAgICAgICAgICAgc3JjOiB1cmwoaHR0cHM6Ly9jZG5qcy5jbG91ZGZsYXJlLmNvbS9hamF4L2xpYnMvZm9udC1hd2Vzb21lLzYuMy4wL3dlYmZvbnRzL2ZhLXNvbGlkLTkwMC53b2ZmMikgZm9ybWF0KCd3b2ZmMicpO1xuICAgICAgICAgICAgICB9XG5cblxuICAgICAgICAgICAgICBAZm9udC1mYWNlIHtcbiAgICAgICAgICAgICAgICBmb250LWZhbWlseTogJ0VudHlwbyc7XG4gICAgICAgICAgICAgICAgc3JjOiB1cmwoaHR0cHM6Ly9jZG5qcy5jbG91ZGZsYXJlLmNvbS9hamF4L2xpYnMvZW50eXBvLzIuMC9lbnR5cG8ud29mZikgZm9ybWF0KCd3b2ZmJyk7XG4gICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICBAZm9udC1mYWNlIHtcbiAgICAgICAgICAgICAgICBmb250LWZhbWlseTogJ01hdGVyaWFsQ29tbXVuaXR5SWNvbnMnO1xuICAgICAgICAgICAgICAgIHNyYzogdXJsKGh0dHBzOi8vY2RuLmpzZGVsaXZyLm5ldC9ucG0vQGV4cG8vdmVjdG9yLWljb25zL2J1aWxkL3ZlbmRvci9yZWFjdC1uYXRpdmUtdmVjdG9yLWljb25zL0ZvbnRzL01hdGVyaWFsQ29tbXVuaXR5SWNvbnMudHRmKSBmb3JtYXQoJ3RydWV0eXBlJyk7XG4gICAgICAgICAgICAgIH1cblxuICAgICAgICAgIGB9XG4gICAgICAgICAgPC9zdHlsZT5cbiAgICAgICAgPC9IZWFkPlxuICAgICAgICA8Ym9keT5cbiAgICAgICAgICA8Q29sb3JNb2RlU2NyaXB0IGluaXRpYWxDb2xvck1vZGU9XCJzeXN0ZW1cIiAvPlxuICAgICAgICAgIDxNYWluIC8+XG4gICAgICAgICAgPGRpdiBpZD1cIm1vZGFsLXJvb3RcIj48L2Rpdj5cbiAgICAgICAgICA8TmV4dFNjcmlwdCAvPlxuICAgICAgICAgIFxuICAgICAgICA8L2JvZHk+XG4gICAgICA8L0h0bWw+XG4gICAgKVxufVxuXG5NeURvY3VtZW50LmdldEluaXRpYWxQcm9wcyA9IGFzeW5jIChjdHg6IERvY3VtZW50Q29udGV4dCkgPT4ge1xuXG4gY29uc3Qgb3JpZ2luYWxSZW5kZXJQYWdlID0gY3R4LnJlbmRlclBhZ2U7XG5cbiAgLy8gWW91IGNhbiBjb25zaWRlciBzaGFyaW5nIHRoZSBzYW1lIEVtb3Rpb24gY2FjaGUgYmV0d2VlbiBhbGwgdGhlIFNTUiByZXF1ZXN0cyB0byBzcGVlZCB1cCBwZXJmb3JtYW5jZS5cbiAgLy8gSG93ZXZlciwgYmUgYXdhcmUgdGhhdCBpdCBjYW4gaGF2ZSBnbG9iYWwgc2lkZSBlZmZlY3RzLlxuICBjb25zdCBjYWNoZSA9IGNyZWF0ZUVtb3Rpb25DYWNoZSgpO1xuICBjb25zdCB7IGV4dHJhY3RDcml0aWNhbFRvQ2h1bmtzIH0gPSBjcmVhdGVFbW90aW9uU2VydmVyKGNhY2hlKTtcblxuICBjdHgucmVuZGVyUGFnZSA9ICgpID0+XG4gICAgb3JpZ2luYWxSZW5kZXJQYWdlKHtcbiAgICAgIGVuaGFuY2VBcHA6IChBcHA6IFJlYWN0LkNvbXBvbmVudFR5cGU8UmVhY3QuQ29tcG9uZW50UHJvcHM8QXBwVHlwZT4gJiBNeUFwcFByb3BzPikgPT5cbiAgICAgICAgZnVuY3Rpb24gRW5oYW5jZUFwcChwcm9wcykge1xuICAgICAgICAgIHJldHVybiA8QXBwIGVtb3Rpb25DYWNoZT17Y2FjaGV9IHsuLi5wcm9wc30gLz47XG4gICAgICAgIH0sXG4gICAgfSk7XG5cbiAgY29uc3QgaW5pdGlhbFByb3BzID0gYXdhaXQgRG9jdW1lbnQuZ2V0SW5pdGlhbFByb3BzKGN0eCk7XG4gIC8vIFRoaXMgaXMgaW1wb3J0YW50LiBJdCBwcmV2ZW50cyBFbW90aW9uIHRvIHJlbmRlciBpbnZhbGlkIEhUTUwuXG4gIC8vIFNlZSBodHRwczovL2dpdGh1Yi5jb20vbXVpL21hdGVyaWFsLXVpL2lzc3Vlcy8yNjU2MSNpc3N1ZWNvbW1lbnQtODU1Mjg2MTUzXG4gIGNvbnN0IGVtb3Rpb25TdHlsZXMgPSBleHRyYWN0Q3JpdGljYWxUb0NodW5rcyhpbml0aWFsUHJvcHMuaHRtbCk7XG4gIGNvbnN0IGVtb3Rpb25TdHlsZVRhZ3MgPSBlbW90aW9uU3R5bGVzLnN0eWxlcy5tYXAoKHN0eWxlKSA9PiAoXG4gICAgPHN0eWxlXG4gICAgICBkYXRhLWVtb3Rpb249e2Ake3N0eWxlLmtleX0gJHtzdHlsZS5pZHMuam9pbignICcpfWB9XG4gICAgICBrZXk9e3N0eWxlLmtleX1cbiAgICAgIC8vIGVzbGludC1kaXNhYmxlLW5leHQtbGluZSByZWFjdC9uby1kYW5nZXJcbiAgICAgIGRhbmdlcm91c2x5U2V0SW5uZXJIVE1MPXt7IF9faHRtbDogc3R5bGUuY3NzIH19XG4gICAgLz5cbiAgKSk7XG5cbiAgcmV0dXJuIHtcbiAgICAuLi5pbml0aWFsUHJvcHMsXG4gICAgZW1vdGlvblN0eWxlVGFncyxcbiAgfTtcbn07XG5cbiJdfQ==