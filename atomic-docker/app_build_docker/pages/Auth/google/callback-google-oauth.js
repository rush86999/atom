"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getServerSideProps = getServerSideProps;
const jsx_runtime_1 = require("react/jsx-runtime");
const router_1 = require("next/router");
const react_1 = require("react");
const react_2 = require("@chakra-ui/react");
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
const CallbackGoogleOAuth = () => {
    const [isValid, setIsValid] = (0, react_1.useState)(true);
    const router = (0, router_1.useRouter)();
    const toast = (0, react_2.useToast)();
    console.log(router.query, ' router.query');
    // console.log(access_token, ' access_token')
    const error = router.query?.error;
    // validate callback
    (0, react_1.useEffect)(() => {
        const validateCallback = () => {
            if (error) {
                toast({
                    title: 'Oops...',
                    description: 'Something went wrong, Google Auth did not work. Maybe try again? Or if it keeps happening let us know.',
                    status: 'error',
                    duration: 9000,
                    isClosable: true
                });
                setIsValid(false);
                return false;
            }
            return true;
        };
        (() => {
            const validatedCallback = validateCallback();
            if (validatedCallback) {
                toast({
                    title: 'Google succesfully authenticate',
                    description: 'Google is successfully authenticated. You can now use Google apps with Atomic',
                    status: 'success',
                    duration: 9000,
                    isClosable: true
                });
            }
        })();
    }, [error, toast]);
    return ((0, jsx_runtime_1.jsx)("div", { className: "flex flex-col justify-center items-center h-screen w-full", children: (0, jsx_runtime_1.jsxs)("div", { className: "sm:text-left lg:my-12 sm:my-8 lg:h-1/6 lg:w-1/2", children: [(0, jsx_runtime_1.jsx)("h1", { className: "text-xl font-bold text-gray-900 dark:text-gray-200 sm:text-2xl", children: "Validating your returned values" }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1.5 text-sm text-gray-500", children: "Please wait as we validate a successful Google authentication" }), (0, jsx_runtime_1.jsx)("div", { className: "flex justify-center items-center lg:h-5/6 w-full", children: (0, jsx_runtime_1.jsx)(react_2.Spinner, { color: 'pink.500' }) }), !isValid
                    ? ((0, jsx_runtime_1.jsx)("p", { className: "mt-1.5 text-sm text-red-500", children: "Something went wrong with the Auth!? Go back & try again! " })) : ((0, jsx_runtime_1.jsx)("p", { className: "mt-1.5 text-sm text-green-500", children: "Google Auth Success. Close me! " }))] }) }));
};
exports.default = CallbackGoogleOAuth;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsbGJhY2stZ29vZ2xlLW9hdXRoLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiY2FsbGJhY2stZ29vZ2xlLW9hdXRoLnRzeCJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQWVBLGdEQXFDQzs7QUFwREQsd0NBQXVDO0FBQ3ZDLGlDQUEyQztBQUUzQyw0Q0FBb0Q7QUFRcEQsd0VBQThDO0FBQzlDLGlFQUE2RDtBQUM3RCw4RUFBcUQ7QUFFOUMsS0FBSyxVQUFVLGtCQUFrQixDQUFDLEVBQUUsR0FBRyxFQUFFLEdBQUcsRUFBaUQ7SUFDbEcsMEZBQTBGO0lBQzFGLHNDQUFzQztJQUN0Qyx5RUFBeUU7SUFDekUsMEJBQWUsQ0FBQyxJQUFJLENBQUMsSUFBQSw2QkFBYSxHQUFFLENBQUMsQ0FBQTtJQUNyQyxJQUFJLE9BQU8sQ0FBQTtJQUNYLElBQUksQ0FBQztRQUNILE9BQU8sR0FBRyxNQUFNLGlCQUFPLENBQUMsVUFBVSxDQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUU7WUFDM0MsNkJBQTZCLEVBQUUsS0FBSztnQkFDbEMsT0FBTyxFQUFFLENBQUE7WUFDWCxDQUFDO1NBQ0YsQ0FBQyxDQUFBO0lBQ0osQ0FBQztJQUFDLE9BQU8sR0FBUSxFQUFFLENBQUM7UUFDbEIsSUFBSSxHQUFHLENBQUMsSUFBSSxLQUFLLGlCQUFPLENBQUMsS0FBSyxDQUFDLGlCQUFpQixFQUFFLENBQUM7WUFDakQsT0FBTyxFQUFFLEtBQUssRUFBRSxFQUFFLGVBQWUsRUFBRSxlQUFlLEVBQUUsRUFBRSxDQUFBO1FBQ3hELENBQUM7YUFBTSxJQUFJLEdBQUcsQ0FBQyxJQUFJLEtBQUssaUJBQU8sQ0FBQyxLQUFLLENBQUMsWUFBWSxFQUFFLENBQUM7WUFDbkQsa0VBQWtFO1lBQ2xFLHFFQUFxRTtZQUNyRSxPQUFPLEVBQUUsS0FBSyxFQUFFLEVBQUUsZUFBZSxFQUFFLGVBQWUsRUFBRSxFQUFFLENBQUE7UUFDeEQsQ0FBQztRQUNELE1BQU0sR0FBRyxDQUFBO0lBQ1gsQ0FBQztJQUVELElBQUksQ0FBQyxPQUFPLEVBQUUsU0FBUyxFQUFFLEVBQUUsQ0FBQztRQUMxQixPQUFPO1lBQ0wsUUFBUSxFQUFFO2dCQUNSLFdBQVcsRUFBRSx1QkFBdUI7Z0JBQ3BDLFNBQVMsRUFBRSxLQUFLO2FBQ2pCO1NBQ0YsQ0FBQTtJQUNILENBQUM7SUFFRCxPQUFPO1FBQ0wsS0FBSyxFQUFFO1lBQ0wsR0FBRyxFQUFFLE9BQU8sQ0FBQyxTQUFTLEVBQUU7U0FDekI7S0FDRixDQUFBO0FBQ0gsQ0FBQztBQUdELE1BQU0sbUJBQW1CLEdBQWEsR0FBRyxFQUFFO0lBQ3ZDLE1BQU0sQ0FBQyxPQUFPLEVBQUUsVUFBVSxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFVLElBQUksQ0FBQyxDQUFBO0lBQ3JELE1BQU0sTUFBTSxHQUFHLElBQUEsa0JBQVMsR0FBRSxDQUFBO0lBQzFCLE1BQU0sS0FBSyxHQUFHLElBQUEsZ0JBQVEsR0FBRSxDQUFBO0lBR3hCLE9BQU8sQ0FBQyxHQUFHLENBQUMsTUFBTSxDQUFDLEtBQUssRUFBRSxlQUFlLENBQUMsQ0FBQTtJQUMxQyw2Q0FBNkM7SUFFN0MsTUFBTSxLQUFLLEdBQUcsTUFBTSxDQUFDLEtBQUssRUFBRSxLQUFlLENBQUE7SUFFM0Msb0JBQW9CO0lBQ3BCLElBQUEsaUJBQVMsRUFBQyxHQUFHLEVBQUU7UUFDWCxNQUFNLGdCQUFnQixHQUFHLEdBQUcsRUFBRTtZQUMxQixJQUFJLEtBQUssRUFBRSxDQUFDO2dCQUNKLEtBQUssQ0FBQztvQkFDTixLQUFLLEVBQUUsU0FBUztvQkFDaEIsV0FBVyxFQUFFLHdHQUF3RztvQkFDckgsTUFBTSxFQUFFLE9BQU87b0JBQ2YsUUFBUSxFQUFFLElBQUk7b0JBQ2QsVUFBVSxFQUFFLElBQUk7aUJBQ2YsQ0FBQyxDQUFBO2dCQUNOLFVBQVUsQ0FBQyxLQUFLLENBQUMsQ0FBQTtnQkFDakIsT0FBTyxLQUFLLENBQUE7WUFDaEIsQ0FBQztZQUVELE9BQU8sSUFBSSxDQUFBO1FBRWYsQ0FBQyxDQUFBO1FBRUQsQ0FBQyxHQUFHLEVBQUU7WUFFRixNQUFNLGlCQUFpQixHQUFHLGdCQUFnQixFQUFFLENBQUE7WUFFNUMsSUFBSSxpQkFBaUIsRUFBRSxDQUFDO2dCQUNwQixLQUFLLENBQUM7b0JBQ0YsS0FBSyxFQUFFLGlDQUFpQztvQkFDeEMsV0FBVyxFQUFFLCtFQUErRTtvQkFDNUYsTUFBTSxFQUFFLFNBQVM7b0JBQ2pCLFFBQVEsRUFBRSxJQUFJO29CQUNkLFVBQVUsRUFBRSxJQUFJO2lCQUNuQixDQUFDLENBQUE7WUFFTixDQUFDO1FBRUwsQ0FBQyxDQUFDLEVBQUUsQ0FBQTtJQUNSLENBQUMsRUFBRSxDQUFDLEtBQUssRUFBRSxLQUFLLENBQUMsQ0FBQyxDQUFBO0lBRWxCLE9BQU8sQ0FDSCxnQ0FBSyxTQUFTLEVBQUMsMkRBQTJELFlBQ3RFLGlDQUFLLFNBQVMsRUFBQyxpREFBaUQsYUFDNUQsK0JBQUksU0FBUyxFQUFDLGdFQUFnRSxZQUN6RSxpQ0FBaUMsR0FDakMsRUFFTCw4QkFBRyxTQUFTLEVBQUMsOEJBQThCLFlBQ3RDLCtEQUErRCxHQUNoRSxFQUNKLGdDQUFLLFNBQVMsRUFBQyxrREFBa0QsWUFDN0QsdUJBQUMsZUFBTyxJQUFDLEtBQUssRUFBQyxVQUFVLEdBQUcsR0FDMUIsRUFFTixDQUFDLE9BQU87b0JBQ0osQ0FBQyxDQUFDLENBQ0UsOEJBQUcsU0FBUyxFQUFDLDZCQUE2QixZQUNyQyw0REFBNEQsR0FDN0QsQ0FDUCxDQUFDLENBQUMsQ0FBQyxDQUNBLDhCQUFHLFNBQVMsRUFBQywrQkFBK0IsWUFDdkMsaUNBQWlDLEdBQ2xDLENBQ1AsSUFFSCxHQUVKLENBQ1QsQ0FBQTtBQUNMLENBQUMsQ0FBQTtBQUVELGtCQUFlLG1CQUFtQixDQUFBIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgdXNlUm91dGVyIH0gZnJvbSAnbmV4dC9yb3V0ZXInXG5pbXBvcnQgeyB1c2VFZmZlY3QsIHVzZVN0YXRlIH0gZnJvbSBcInJlYWN0XCJcbmltcG9ydCB0eXBlIHsgTmV4dFBhZ2UgfSBmcm9tICduZXh0J1xuaW1wb3J0IHsgdXNlVG9hc3QsIFNwaW5uZXIgfSBmcm9tICdAY2hha3JhLXVpL3JlYWN0J1xuaW1wb3J0IHsgTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL01lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGUnXG5pbXBvcnQgeyBNZWV0aW5nQXNzaXN0VHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL01lZXRpbmdBc3Npc3RUeXBlJ1xuXG5pbXBvcnQgeyB1c2VBcHBDb250ZXh0IH0gZnJvbSAnQGxpYi91c2VyLWNvbnRleHQnXG5pbXBvcnQgYXhpb3MgZnJvbSAnYXhpb3MnXG5pbXBvcnQgcXMgZnJvbSAncXMnXG5pbXBvcnQgeyBOZXh0QXBpUmVxdWVzdCwgTmV4dEFwaVJlc3BvbnNlIH0gZnJvbSAnbmV4dCc7XG5pbXBvcnQgc3VwZXJ0b2tlbnNOb2RlIGZyb20gJ3N1cGVydG9rZW5zLW5vZGUnXG5pbXBvcnQgeyBiYWNrZW5kQ29uZmlnIH0gZnJvbSAnLi4vLi4vLi4vY29uZmlnL2JhY2tlbmRDb25maWcnXG5pbXBvcnQgU2Vzc2lvbiBmcm9tICdzdXBlcnRva2Vucy1ub2RlL3JlY2lwZS9zZXNzaW9uJ1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0U2VydmVyU2lkZVByb3BzKHsgcmVxLCByZXMgfTogeyByZXE6IE5leHRBcGlSZXF1ZXN0LCByZXM6IE5leHRBcGlSZXNwb25zZSB9KSB7XG4gIC8vIE5vdGljZSBob3cgdGhlIHNlcnZlciB1c2VzIGBBUElgIGZyb20gYHdpdGhTU1JDb250ZXh0YCwgaW5zdGVhZCBvZiB0aGUgdG9wLWxldmVsIGBBUElgLlxuICAvLyBjb25zdCBTU1IgPSB3aXRoU1NSQ29udGV4dCh7IHJlcSB9KVxuICAvLyB0aGlzIHJ1bnMgb24gdGhlIGJhY2tlbmQsIHNvIHdlIG11c3QgY2FsbCBpbml0IG9uIHN1cGVydG9rZW5zLW5vZGUgU0RLXG4gIHN1cGVydG9rZW5zTm9kZS5pbml0KGJhY2tlbmRDb25maWcoKSlcbiAgbGV0IHNlc3Npb25cbiAgdHJ5IHtcbiAgICBzZXNzaW9uID0gYXdhaXQgU2Vzc2lvbi5nZXRTZXNzaW9uKHJlcSwgcmVzLCB7XG4gICAgICBvdmVycmlkZUdsb2JhbENsYWltVmFsaWRhdG9yczogYXN5bmMgZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gW11cbiAgICAgIH0sXG4gICAgfSlcbiAgfSBjYXRjaCAoZXJyOiBhbnkpIHtcbiAgICBpZiAoZXJyLnR5cGUgPT09IFNlc3Npb24uRXJyb3IuVFJZX1JFRlJFU0hfVE9LRU4pIHtcbiAgICAgIHJldHVybiB7IHByb3BzOiB7IGZyb21TdXBlcnRva2VuczogJ25lZWRzLXJlZnJlc2gnIH0gfVxuICAgIH0gZWxzZSBpZiAoZXJyLnR5cGUgPT09IFNlc3Npb24uRXJyb3IuVU5BVVRIT1JJU0VEKSB7XG4gICAgICAvLyB0aGlzIHdpbGwgZm9yY2UgdGhlIGZyb250ZW5kIHRvIHRyeSBhbmQgcmVmcmVzaCB3aGljaCB3aWxsIGZhaWxcbiAgICAgIC8vIGNsZWFyaW5nIGFsbCBjb29raWVzIGFuZCByZWRpcmVjdGluZyB0aGUgdXNlciB0byB0aGUgbG9naW4gc2NyZWVuLlxuICAgICAgcmV0dXJuIHsgcHJvcHM6IHsgZnJvbVN1cGVydG9rZW5zOiAnbmVlZHMtcmVmcmVzaCcgfSB9XG4gICAgfVxuICAgIHRocm93IGVyclxuICB9XG5cbiAgaWYgKCFzZXNzaW9uPy5nZXRVc2VySWQoKSkge1xuICAgIHJldHVybiB7XG4gICAgICByZWRpcmVjdDoge1xuICAgICAgICBkZXN0aW5hdGlvbjogJy9Vc2VyL0xvZ2luL1VzZXJMb2dpbicsXG4gICAgICAgIHBlcm1hbmVudDogZmFsc2UsXG4gICAgICB9LFxuICAgIH1cbiAgfVxuXG4gIHJldHVybiB7XG4gICAgcHJvcHM6IHtcbiAgICAgIHN1Yjogc2Vzc2lvbi5nZXRVc2VySWQoKSxcbiAgICB9XG4gIH1cbn1cblxuXG5jb25zdCBDYWxsYmFja0dvb2dsZU9BdXRoOiBOZXh0UGFnZSA9ICgpID0+IHtcbiAgICBjb25zdCBbaXNWYWxpZCwgc2V0SXNWYWxpZF0gPSB1c2VTdGF0ZTxib29sZWFuPih0cnVlKVxuICAgIGNvbnN0IHJvdXRlciA9IHVzZVJvdXRlcigpXG4gICAgY29uc3QgdG9hc3QgPSB1c2VUb2FzdCgpXG4gIFxuXG4gICAgY29uc29sZS5sb2cocm91dGVyLnF1ZXJ5LCAnIHJvdXRlci5xdWVyeScpXG4gICAgLy8gY29uc29sZS5sb2coYWNjZXNzX3Rva2VuLCAnIGFjY2Vzc190b2tlbicpXG5cbiAgICBjb25zdCBlcnJvciA9IHJvdXRlci5xdWVyeT8uZXJyb3IgYXMgc3RyaW5nXG4gICAgXG4gICAgLy8gdmFsaWRhdGUgY2FsbGJhY2tcbiAgICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgICAgICBjb25zdCB2YWxpZGF0ZUNhbGxiYWNrID0gKCkgPT4ge1xuICAgICAgICAgICAgaWYgKGVycm9yKSB7XG4gICAgICAgICAgICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgICAgICAgICAgdGl0bGU6ICdPb3BzLi4uJyxcbiAgICAgICAgICAgICAgICAgICAgZGVzY3JpcHRpb246ICdTb21ldGhpbmcgd2VudCB3cm9uZywgR29vZ2xlIEF1dGggZGlkIG5vdCB3b3JrLiBNYXliZSB0cnkgYWdhaW4/IE9yIGlmIGl0IGtlZXBzIGhhcHBlbmluZyBsZXQgdXMga25vdy4nLFxuICAgICAgICAgICAgICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlXG4gICAgICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAgICAgc2V0SXNWYWxpZChmYWxzZSlcbiAgICAgICAgICAgICAgICByZXR1cm4gZmFsc2VcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgcmV0dXJuIHRydWVcblxuICAgICAgICB9XG5cbiAgICAgICAgKCgpID0+IHtcbiAgXG4gICAgICAgICAgICBjb25zdCB2YWxpZGF0ZWRDYWxsYmFjayA9IHZhbGlkYXRlQ2FsbGJhY2soKVxuXG4gICAgICAgICAgICBpZiAodmFsaWRhdGVkQ2FsbGJhY2spIHtcbiAgICAgICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgICAgIHRpdGxlOiAnR29vZ2xlIHN1Y2Nlc2Z1bGx5IGF1dGhlbnRpY2F0ZScsXG4gICAgICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnR29vZ2xlIGlzIHN1Y2Nlc3NmdWxseSBhdXRoZW50aWNhdGVkLiBZb3UgY2FuIG5vdyB1c2UgR29vZ2xlIGFwcHMgd2l0aCBBdG9taWMnLFxuICAgICAgICAgICAgICAgICAgICBzdGF0dXM6ICdzdWNjZXNzJyxcbiAgICAgICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWVcbiAgICAgICAgICAgICAgICB9KVxuICAgICAgICAgICAgICAgIFxuICAgICAgICAgICAgfVxuICAgICAgICAgICAgXG4gICAgICAgIH0pKClcbiAgICB9LCBbZXJyb3IsIHRvYXN0XSlcblxuICAgIHJldHVybiAoXG4gICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZmxleCBmbGV4LWNvbCBqdXN0aWZ5LWNlbnRlciBpdGVtcy1jZW50ZXIgaC1zY3JlZW4gdy1mdWxsXCI+XG4gICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cInNtOnRleHQtbGVmdCBsZzpteS0xMiBzbTpteS04IGxnOmgtMS82IGxnOnctMS8yXCI+XG4gICAgICAgICAgICAgICAgPGgxIGNsYXNzTmFtZT1cInRleHQteGwgZm9udC1ib2xkIHRleHQtZ3JheS05MDAgZGFyazp0ZXh0LWdyYXktMjAwIHNtOnRleHQtMnhsXCI+XG4gICAgICAgICAgICAgICAgICAgIHtcIlZhbGlkYXRpbmcgeW91ciByZXR1cm5lZCB2YWx1ZXNcIn1cbiAgICAgICAgICAgICAgICA8L2gxPlxuXG4gICAgICAgICAgICAgICAgPHAgY2xhc3NOYW1lPVwibXQtMS41IHRleHQtc20gdGV4dC1ncmF5LTUwMFwiPlxuICAgICAgICAgICAgICAgICAgICB7XCJQbGVhc2Ugd2FpdCBhcyB3ZSB2YWxpZGF0ZSBhIHN1Y2Nlc3NmdWwgR29vZ2xlIGF1dGhlbnRpY2F0aW9uXCJ9XG4gICAgICAgICAgICAgICAgPC9wPlxuICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZmxleCBqdXN0aWZ5LWNlbnRlciBpdGVtcy1jZW50ZXIgbGc6aC01LzYgdy1mdWxsXCI+XG4gICAgICAgICAgICAgICAgICAgIDxTcGlubmVyIGNvbG9yPSdwaW5rLjUwMCcgLz5cbiAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgIWlzVmFsaWRcbiAgICAgICAgICAgICAgICAgICAgPyAoXG4gICAgICAgICAgICAgICAgICAgICAgICA8cCBjbGFzc05hbWU9XCJtdC0xLjUgdGV4dC1zbSB0ZXh0LXJlZC01MDBcIj5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB7XCJTb21ldGhpbmcgd2VudCB3cm9uZyB3aXRoIHRoZSBBdXRoIT8gR28gYmFjayAmIHRyeSBhZ2FpbiEgXCJ9XG4gICAgICAgICAgICAgICAgICAgICAgICA8L3A+XG4gICAgICAgICAgICAgICAgICAgICkgOiAoXG4gICAgICAgICAgICAgICAgICAgICAgICA8cCBjbGFzc05hbWU9XCJtdC0xLjUgdGV4dC1zbSB0ZXh0LWdyZWVuLTUwMFwiPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHtcIkdvb2dsZSBBdXRoIFN1Y2Nlc3MuIENsb3NlIG1lISBcIn1cbiAgICAgICAgICAgICAgICAgICAgICAgIDwvcD5cbiAgICAgICAgICAgICAgICAgICAgKVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgXG4gICAgICAgIDwvZGl2PlxuICAgIClcbn1cblxuZXhwb3J0IGRlZmF1bHQgQ2FsbGJhY2tHb29nbGVPQXV0aFxuIl19