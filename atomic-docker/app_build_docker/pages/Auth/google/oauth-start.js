"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getServerSideProps = getServerSideProps;
const jsx_runtime_1 = require("react/jsx-runtime");
const image_1 = __importDefault(require("next/image"));
const constants_1 = require("@lib/constants");
const react_1 = require("react");
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const backendConfig_1 = require("../../../config/backendConfig");
const session_1 = __importDefault(require("supertokens-node/recipe/session"));
async function getServerSideProps({ req, res }) {
    // Notice how the server uses `API` from `withSSRContext`, instead of the top-level `API`.
    // const SSR = withSSRContext({ req })
    // this runs on the backend, so we must call init on supertokens-node SDK
    supertokens_node_1.default.init((0, backendConfig_1.backendConfig)());
    let session;
    try {
        session = await session_1.default.getSession(req, res, {
            overrideGlobalClaimValidators: async function () {
                return [];
            },
        });
    }
    catch (err) {
        if (err.type === session_1.default.Error.TRY_REFRESH_TOKEN) {
            return { props: { fromSupertokens: 'needs-refresh' } };
        }
        else if (err.type === session_1.default.Error.UNAUTHORISED) {
            // this will force the frontend to try and refresh which will fail
            // clearing all cookies and redirecting the user to the login screen.
            return { props: { fromSupertokens: 'needs-refresh' } };
        }
        throw err;
    }
    if (!session?.getUserId()) {
        return {
            redirect: {
                destination: '/User/Login/UserLogin',
                permanent: false,
            },
        };
    }
    return {
        props: {
            sub: session.getUserId(),
        }
    };
}
const GoogleOAuthStart = () => {
    const [url, setUrl] = (0, react_1.useState)('');
    (0, react_1.useEffect)(() => {
        const makeLink = () => {
            const newUrl = new URL(constants_1.googleOAuthAtomicWebAPIStartUrl);
            setUrl(newUrl.href);
        };
        makeLink();
    }, []);
    let googleSignInButton = constants_1.googleSignInNormalButton;
    if (typeof window !== "undefined") {
        googleSignInButton = window.matchMedia('(prefers-color-scheme: dark)').matches ? constants_1.googleSignInDarkButton : constants_1.googleSignInNormalButton;
    }
    const routeToGoogleCalendarSignIn = (e) => {
        e?.preventDefault();
        const newUrl = new URL(constants_1.googleOAuthAtomicWebAPIStartUrl);
        window.location.href = newUrl.href;
    };
    return ((0, jsx_runtime_1.jsxs)("div", { className: "flex flex-col justify-center items-center h-full w-full", style: { minHeight: '70vh' }, children: [(0, jsx_runtime_1.jsxs)("div", { className: " lg:my-12 sm:my-8 lg:h-1/6 sm:w-1/2", children: [(0, jsx_runtime_1.jsx)("h1", { className: "text-xl font-bold text-center  text-gray-900 dark:text-gray-200 sm:text-2xl", children: "Sign in to your Google Account" }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1.5 text-sm text-center text-gray-500", children: "Sign in to your Google calendar to sync events and avoid conflict 😊 " })] }), (0, jsx_runtime_1.jsx)("div", { className: "flex flex-col justify-start items-center lg:h-5/6", children: (0, jsx_runtime_1.jsx)("div", { children: (0, jsx_runtime_1.jsx)("a", { href: url, onClick: routeToGoogleCalendarSignIn, children: (0, jsx_runtime_1.jsx)(image_1.default, { src: googleSignInButton, alt: "Google Sign In", width: 382, height: 92, className: "rounded" }) }) }) })] }));
};
exports.default = GoogleOAuthStart;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoib2F1dGgtc3RhcnQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJvYXV0aC1zdGFydC50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUFVQSxnREFxQ0M7O0FBL0NELHVEQUE4QjtBQUc5Qiw4Q0FBa0g7QUFDbEgsaUNBQTJDO0FBRTNDLHdFQUE4QztBQUM5QyxpRUFBNkQ7QUFDN0QsOEVBQXFEO0FBRTlDLEtBQUssVUFBVSxrQkFBa0IsQ0FBQyxFQUFFLEdBQUcsRUFBRSxHQUFHLEVBQWlEO0lBQ2xHLDBGQUEwRjtJQUMxRixzQ0FBc0M7SUFDdEMseUVBQXlFO0lBQ3pFLDBCQUFlLENBQUMsSUFBSSxDQUFDLElBQUEsNkJBQWEsR0FBRSxDQUFDLENBQUE7SUFDckMsSUFBSSxPQUFPLENBQUE7SUFDWCxJQUFJLENBQUM7UUFDSCxPQUFPLEdBQUcsTUFBTSxpQkFBTyxDQUFDLFVBQVUsQ0FBQyxHQUFHLEVBQUUsR0FBRyxFQUFFO1lBQzNDLDZCQUE2QixFQUFFLEtBQUs7Z0JBQ2xDLE9BQU8sRUFBRSxDQUFBO1lBQ1gsQ0FBQztTQUNGLENBQUMsQ0FBQTtJQUNKLENBQUM7SUFBQyxPQUFPLEdBQVEsRUFBRSxDQUFDO1FBQ2xCLElBQUksR0FBRyxDQUFDLElBQUksS0FBSyxpQkFBTyxDQUFDLEtBQUssQ0FBQyxpQkFBaUIsRUFBRSxDQUFDO1lBQ2pELE9BQU8sRUFBRSxLQUFLLEVBQUUsRUFBRSxlQUFlLEVBQUUsZUFBZSxFQUFFLEVBQUUsQ0FBQTtRQUN4RCxDQUFDO2FBQU0sSUFBSSxHQUFHLENBQUMsSUFBSSxLQUFLLGlCQUFPLENBQUMsS0FBSyxDQUFDLFlBQVksRUFBRSxDQUFDO1lBQ25ELGtFQUFrRTtZQUNsRSxxRUFBcUU7WUFDckUsT0FBTyxFQUFFLEtBQUssRUFBRSxFQUFFLGVBQWUsRUFBRSxlQUFlLEVBQUUsRUFBRSxDQUFBO1FBQ3hELENBQUM7UUFDRCxNQUFNLEdBQUcsQ0FBQTtJQUNYLENBQUM7SUFFRCxJQUFJLENBQUMsT0FBTyxFQUFFLFNBQVMsRUFBRSxFQUFFLENBQUM7UUFDMUIsT0FBTztZQUNMLFFBQVEsRUFBRTtnQkFDUixXQUFXLEVBQUUsdUJBQXVCO2dCQUNwQyxTQUFTLEVBQUUsS0FBSzthQUNqQjtTQUNGLENBQUE7SUFDSCxDQUFDO0lBRUQsT0FBTztRQUNMLEtBQUssRUFBRTtZQUNMLEdBQUcsRUFBRSxPQUFPLENBQUMsU0FBUyxFQUFFO1NBQ3pCO0tBQ0YsQ0FBQTtBQUNILENBQUM7QUFHRCxNQUFNLGdCQUFnQixHQUFhLEdBQUcsRUFBRTtJQUNwQyxNQUFNLENBQUMsR0FBRyxFQUFFLE1BQU0sQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBQyxFQUFFLENBQUMsQ0FBQTtJQUVsQyxJQUFBLGlCQUFTLEVBQUMsR0FBRyxFQUFFO1FBQ1gsTUFBTSxRQUFRLEdBQUcsR0FBRyxFQUFFO1lBQ2xCLE1BQU0sTUFBTSxHQUFHLElBQUksR0FBRyxDQUFDLDJDQUErQixDQUFDLENBQUE7WUFDdkQsTUFBTSxDQUFDLE1BQU0sQ0FBQyxJQUFJLENBQUMsQ0FBQTtRQUN2QixDQUFDLENBQUE7UUFDRCxRQUFRLEVBQUUsQ0FBQTtJQUNkLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQTtJQUVOLElBQUksa0JBQWtCLEdBQUcsb0NBQXdCLENBQUE7SUFFakQsSUFBSSxPQUFPLE1BQU0sS0FBSyxXQUFXLEVBQUUsQ0FBQztRQUNoQyxrQkFBa0IsR0FBRyxNQUFNLENBQUMsVUFBVSxDQUFDLDhCQUE4QixDQUFDLENBQUMsT0FBTyxDQUFDLENBQUMsQ0FBQyxrQ0FBc0IsQ0FBQyxDQUFDLENBQUMsb0NBQXdCLENBQUE7SUFDdEksQ0FBQztJQUVELE1BQU0sMkJBQTJCLEdBQUcsQ0FBQyxDQUFpQyxFQUFFLEVBQUU7UUFDdEUsQ0FBQyxFQUFFLGNBQWMsRUFBRSxDQUFBO1FBQ25CLE1BQU0sTUFBTSxHQUFHLElBQUksR0FBRyxDQUFDLDJDQUErQixDQUFDLENBQUE7UUFDdkQsTUFBTSxDQUFDLFFBQVEsQ0FBQyxJQUFJLEdBQUcsTUFBTSxDQUFDLElBQUksQ0FBQTtJQUV0QyxDQUFDLENBQUE7SUFHRCxPQUFPLENBQ0gsaUNBQUssU0FBUyxFQUFDLHlEQUF5RCxFQUFDLEtBQUssRUFBRSxFQUFFLFNBQVMsRUFBRSxNQUFNLEVBQUMsYUFDaEcsaUNBQUssU0FBUyxFQUFDLHFDQUFxQyxhQUNoRCwrQkFBSSxTQUFTLEVBQUMsNkVBQTZFLFlBQ3RGLGdDQUFnQyxHQUNoQyxFQUVMLDhCQUFHLFNBQVMsRUFBQywwQ0FBMEMsWUFDbEQsdUVBQXVFLEdBQ3hFLElBQ0YsRUFDTixnQ0FBSyxTQUFTLEVBQUMsbURBQW1ELFlBQzlELDBDQUNJLDhCQUFHLElBQUksRUFBRSxHQUFHLEVBQUUsT0FBTyxFQUFFLDJCQUEyQixZQUM5Qyx1QkFBQyxlQUFLLElBQ0YsR0FBRyxFQUFFLGtCQUFrQixFQUN2QixHQUFHLEVBQUMsZ0JBQWdCLEVBQ3BCLEtBQUssRUFBRSxHQUFHLEVBQ1YsTUFBTSxFQUFFLEVBQUUsRUFDVixTQUFTLEVBQUMsU0FBUyxHQUNyQixHQUNGLEdBQ0YsR0FDSixJQUNKLENBQ1QsQ0FBQTtBQUNMLENBQUMsQ0FBQTtBQUVELGtCQUFlLGdCQUFnQixDQUFBIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IEltYWdlIGZyb20gJ25leHQvaW1hZ2UnXG5pbXBvcnQgdHlwZSB7IE5leHRQYWdlIH0gZnJvbSAnbmV4dCdcblxuaW1wb3J0IHsgZ29vZ2xlT0F1dGhBdG9taWNXZWJBUElTdGFydFVybCwgZ29vZ2xlU2lnbkluRGFya0J1dHRvbiwgZ29vZ2xlU2lnbkluTm9ybWFsQnV0dG9uIH0gZnJvbSBcIkBsaWIvY29uc3RhbnRzXCJcbmltcG9ydCB7IHVzZUVmZmVjdCwgdXNlU3RhdGUgfSBmcm9tICdyZWFjdCdcbmltcG9ydCB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCBzdXBlcnRva2Vuc05vZGUgZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZSdcbmltcG9ydCB7IGJhY2tlbmRDb25maWcgfSBmcm9tICcuLi8uLi8uLi9jb25maWcvYmFja2VuZENvbmZpZydcbmltcG9ydCBTZXNzaW9uIGZyb20gJ3N1cGVydG9rZW5zLW5vZGUvcmVjaXBlL3Nlc3Npb24nXG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRTZXJ2ZXJTaWRlUHJvcHMoeyByZXEsIHJlcyB9OiB7IHJlcTogTmV4dEFwaVJlcXVlc3QsIHJlczogTmV4dEFwaVJlc3BvbnNlIH0pIHtcbiAgLy8gTm90aWNlIGhvdyB0aGUgc2VydmVyIHVzZXMgYEFQSWAgZnJvbSBgd2l0aFNTUkNvbnRleHRgLCBpbnN0ZWFkIG9mIHRoZSB0b3AtbGV2ZWwgYEFQSWAuXG4gIC8vIGNvbnN0IFNTUiA9IHdpdGhTU1JDb250ZXh0KHsgcmVxIH0pXG4gIC8vIHRoaXMgcnVucyBvbiB0aGUgYmFja2VuZCwgc28gd2UgbXVzdCBjYWxsIGluaXQgb24gc3VwZXJ0b2tlbnMtbm9kZSBTREtcbiAgc3VwZXJ0b2tlbnNOb2RlLmluaXQoYmFja2VuZENvbmZpZygpKVxuICBsZXQgc2Vzc2lvblxuICB0cnkge1xuICAgIHNlc3Npb24gPSBhd2FpdCBTZXNzaW9uLmdldFNlc3Npb24ocmVxLCByZXMsIHtcbiAgICAgIG92ZXJyaWRlR2xvYmFsQ2xhaW1WYWxpZGF0b3JzOiBhc3luYyBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiBbXVxuICAgICAgfSxcbiAgICB9KVxuICB9IGNhdGNoIChlcnI6IGFueSkge1xuICAgIGlmIChlcnIudHlwZSA9PT0gU2Vzc2lvbi5FcnJvci5UUllfUkVGUkVTSF9UT0tFTikge1xuICAgICAgcmV0dXJuIHsgcHJvcHM6IHsgZnJvbVN1cGVydG9rZW5zOiAnbmVlZHMtcmVmcmVzaCcgfSB9XG4gICAgfSBlbHNlIGlmIChlcnIudHlwZSA9PT0gU2Vzc2lvbi5FcnJvci5VTkFVVEhPUklTRUQpIHtcbiAgICAgIC8vIHRoaXMgd2lsbCBmb3JjZSB0aGUgZnJvbnRlbmQgdG8gdHJ5IGFuZCByZWZyZXNoIHdoaWNoIHdpbGwgZmFpbFxuICAgICAgLy8gY2xlYXJpbmcgYWxsIGNvb2tpZXMgYW5kIHJlZGlyZWN0aW5nIHRoZSB1c2VyIHRvIHRoZSBsb2dpbiBzY3JlZW4uXG4gICAgICByZXR1cm4geyBwcm9wczogeyBmcm9tU3VwZXJ0b2tlbnM6ICduZWVkcy1yZWZyZXNoJyB9IH1cbiAgICB9XG4gICAgdGhyb3cgZXJyXG4gIH1cblxuICBpZiAoIXNlc3Npb24/LmdldFVzZXJJZCgpKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIHJlZGlyZWN0OiB7XG4gICAgICAgIGRlc3RpbmF0aW9uOiAnL1VzZXIvTG9naW4vVXNlckxvZ2luJyxcbiAgICAgICAgcGVybWFuZW50OiBmYWxzZSxcbiAgICAgIH0sXG4gICAgfVxuICB9XG5cbiAgcmV0dXJuIHtcbiAgICBwcm9wczoge1xuICAgICAgc3ViOiBzZXNzaW9uLmdldFVzZXJJZCgpLFxuICAgIH1cbiAgfVxufVxuXG5cbmNvbnN0IEdvb2dsZU9BdXRoU3RhcnQ6IE5leHRQYWdlID0gKCkgPT4ge1xuICAgIGNvbnN0IFt1cmwsIHNldFVybF0gPSB1c2VTdGF0ZSgnJylcblxuICAgIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgICAgIGNvbnN0IG1ha2VMaW5rID0gKCkgPT4ge1xuICAgICAgICAgICAgY29uc3QgbmV3VXJsID0gbmV3IFVSTChnb29nbGVPQXV0aEF0b21pY1dlYkFQSVN0YXJ0VXJsKVxuICAgICAgICAgICAgc2V0VXJsKG5ld1VybC5ocmVmKVxuICAgICAgICB9XG4gICAgICAgIG1ha2VMaW5rKClcbiAgICB9LCBbXSlcblxuICAgIGxldCBnb29nbGVTaWduSW5CdXR0b24gPSBnb29nbGVTaWduSW5Ob3JtYWxCdXR0b25cbiAgICBcbiAgICBpZiAodHlwZW9mIHdpbmRvdyAhPT0gXCJ1bmRlZmluZWRcIikge1xuICAgICAgICBnb29nbGVTaWduSW5CdXR0b24gPSB3aW5kb3cubWF0Y2hNZWRpYSgnKHByZWZlcnMtY29sb3Itc2NoZW1lOiBkYXJrKScpLm1hdGNoZXMgPyBnb29nbGVTaWduSW5EYXJrQnV0dG9uIDogZ29vZ2xlU2lnbkluTm9ybWFsQnV0dG9uXG4gICAgfVxuICAgIFxuICAgIGNvbnN0IHJvdXRlVG9Hb29nbGVDYWxlbmRhclNpZ25JbiA9IChlOiB7IHByZXZlbnREZWZhdWx0OiAoKSA9PiB2b2lkIH0pID0+IHtcbiAgICAgICAgZT8ucHJldmVudERlZmF1bHQoKVxuICAgICAgICBjb25zdCBuZXdVcmwgPSBuZXcgVVJMKGdvb2dsZU9BdXRoQXRvbWljV2ViQVBJU3RhcnRVcmwpXG4gICAgICAgIHdpbmRvdy5sb2NhdGlvbi5ocmVmID0gbmV3VXJsLmhyZWZcbiAgICAgICAgXG4gICAgfVxuXG5cbiAgICByZXR1cm4gKFxuICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cImZsZXggZmxleC1jb2wganVzdGlmeS1jZW50ZXIgaXRlbXMtY2VudGVyIGgtZnVsbCB3LWZ1bGxcIiBzdHlsZT17eyBtaW5IZWlnaHQ6ICc3MHZoJ319PlxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCIgbGc6bXktMTIgc206bXktOCBsZzpoLTEvNiBzbTp3LTEvMlwiPlxuICAgICAgICAgICAgICAgIDxoMSBjbGFzc05hbWU9XCJ0ZXh0LXhsIGZvbnQtYm9sZCB0ZXh0LWNlbnRlciAgdGV4dC1ncmF5LTkwMCBkYXJrOnRleHQtZ3JheS0yMDAgc206dGV4dC0yeGxcIj5cbiAgICAgICAgICAgICAgICAgICAge1wiU2lnbiBpbiB0byB5b3VyIEdvb2dsZSBBY2NvdW50XCJ9XG4gICAgICAgICAgICAgICAgPC9oMT5cblxuICAgICAgICAgICAgICAgIDxwIGNsYXNzTmFtZT1cIm10LTEuNSB0ZXh0LXNtIHRleHQtY2VudGVyIHRleHQtZ3JheS01MDBcIj5cbiAgICAgICAgICAgICAgICAgICAge1wiU2lnbiBpbiB0byB5b3VyIEdvb2dsZSBjYWxlbmRhciB0byBzeW5jIGV2ZW50cyBhbmQgYXZvaWQgY29uZmxpY3Qg8J+YiiBcIn1cbiAgICAgICAgICAgICAgICA8L3A+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZmxleCBmbGV4LWNvbCBqdXN0aWZ5LXN0YXJ0IGl0ZW1zLWNlbnRlciBsZzpoLTUvNlwiPlxuICAgICAgICAgICAgICAgIDxkaXY+XG4gICAgICAgICAgICAgICAgICAgIDxhIGhyZWY9e3VybH0gb25DbGljaz17cm91dGVUb0dvb2dsZUNhbGVuZGFyU2lnbklufT5cbiAgICAgICAgICAgICAgICAgICAgICAgIDxJbWFnZVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNyYz17Z29vZ2xlU2lnbkluQnV0dG9ufVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGFsdD1cIkdvb2dsZSBTaWduIEluXCJcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB3aWR0aD17MzgyfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGhlaWdodD17OTJ9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY2xhc3NOYW1lPVwicm91bmRlZFwiXG4gICAgICAgICAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgICAgICA8L2E+XG4gICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgPC9kaXY+XG4gICAgKVxufVxuXG5leHBvcnQgZGVmYXVsdCBHb29nbGVPQXV0aFN0YXJ0XG4iXX0=