"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getServerSideProps = getServerSideProps;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const react_2 = require("@chakra-ui/react");
const router_1 = require("next/router");
const session_1 = __importDefault(require("supertokens-web-js/recipe/session"));
const dynamic_1 = __importDefault(require("next/dynamic"));
const prebuiltui_1 = require("supertokens-auth-react/recipe/thirdpartyemailpassword/prebuiltui");
const supertokens_auth_react_1 = require("supertokens-auth-react");
const ui_1 = require("supertokens-auth-react/ui");
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const backendConfig_1 = require("@config/backendConfig");
const session_2 = __importDefault(require("supertokens-node/recipe/session"));
async function getServerSideProps({ req, res }) {
    // Notice how the server uses `API` from `withSSRContext`, instead of the top-level `API`.
    // const SSR = withSSRContext({ req })
    // this runs on the backend, so we must call init on supertokens-node SDK
    supertokens_node_1.default.init((0, backendConfig_1.backendConfig)());
    let session;
    try {
        session = await session_2.default.getSession(req, res, {
            overrideGlobalClaimValidators: async function () {
                return [];
            },
        });
    }
    catch (err) {
        if (err.type === session_2.default.Error.TRY_REFRESH_TOKEN) {
            return { props: { fromSupertokens: 'needs-refresh' } };
        }
        else if (err.type === session_2.default.Error.UNAUTHORISED) {
            // this will force the frontend to try and refresh which will fail
            // clearing all cookies and redirecting the user to the login screen.
            return { props: { fromSupertokens: 'needs-refresh' } };
        }
        throw err;
    }
    if (session?.getUserId()) {
        return {
            redirect: {
                destination: '/',
                permanent: false,
            },
        };
    }
}
const SuperTokensComponentNoSSR = (0, dynamic_1.default)(new Promise((res) => res(() => (0, ui_1.getRoutingComponent)([prebuiltui_1.ThirdPartyEmailPasswordPreBuiltUI]))), { ssr: false });
function UserLogin() {
    const [email, setEmail] = (0, react_1.useState)('');
    const [password, setPassword] = (0, react_1.useState)('');
    const [user, setUser] = (0, react_1.useState)();
    const [passChallenge, setPassChallenge] = (0, react_1.useState)('');
    const [isLoading, setIsLoading] = (0, react_1.useState)(false);
    // const dark = useColorScheme() === 'dark'
    const toast = (0, react_2.useToast)();
    const router = (0, router_1.useRouter)();
    // check if user already logged in and confirmed
    (0, react_1.useEffect)(() => {
        async function checkLoggedIn() {
            try {
                const userId = await session_1.default.getUserId();
                if (userId) {
                    router.push('/');
                }
            }
            catch (e) {
                console.log(e, ' unable to auth');
            }
        }
        checkLoggedIn();
    }, [router]);
    // if the user visits a page that is not handled by us (like /auth/random), then we redirect them back to the auth page.
    (0, react_1.useEffect)(() => {
        if ((0, ui_1.canHandleRoute)([prebuiltui_1.ThirdPartyEmailPasswordPreBuiltUI]) === false) {
            (0, supertokens_auth_react_1.redirectToAuth)();
        }
    }, []);
    return ((0, jsx_runtime_1.jsx)(SuperTokensComponentNoSSR, {}));
}
exports.default = UserLogin;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlckxvZ2luLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiVXNlckxvZ2luLnRzeCJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQWFBLGdEQStCQzs7QUE1Q0QsaUNBQWtEO0FBQ2xELDRDQUEyQztBQUMzQyx3Q0FBdUM7QUFDdkMsZ0ZBQXdEO0FBQ3hELDJEQUFrQztBQUNsQyxpR0FBcUg7QUFDckgsbUVBQXVEO0FBQ3ZELGtEQUErRTtBQUUvRSx3RUFBOEM7QUFDOUMseURBQXFEO0FBQ3JELDhFQUFxRDtBQUU5QyxLQUFLLFVBQVUsa0JBQWtCLENBQUMsRUFBRSxHQUFHLEVBQUUsR0FBRyxFQUFpRDtJQUNoRywwRkFBMEY7SUFDMUYsc0NBQXNDO0lBQ3RDLHlFQUF5RTtJQUN6RSwwQkFBZSxDQUFDLElBQUksQ0FBQyxJQUFBLDZCQUFhLEdBQUUsQ0FBQyxDQUFBO0lBQ3JDLElBQUksT0FBTyxDQUFBO0lBQ1gsSUFBSSxDQUFDO1FBQ0QsT0FBTyxHQUFHLE1BQU0saUJBQU8sQ0FBQyxVQUFVLENBQUMsR0FBRyxFQUFFLEdBQUcsRUFBRTtZQUN6Qyw2QkFBNkIsRUFBRSxLQUFLO2dCQUNoQyxPQUFPLEVBQUUsQ0FBQTtZQUNiLENBQUM7U0FDSixDQUFDLENBQUE7SUFDTixDQUFDO0lBQUMsT0FBTyxHQUFRLEVBQUUsQ0FBQztRQUNoQixJQUFJLEdBQUcsQ0FBQyxJQUFJLEtBQUssaUJBQU8sQ0FBQyxLQUFLLENBQUMsaUJBQWlCLEVBQUUsQ0FBQztZQUMvQyxPQUFPLEVBQUUsS0FBSyxFQUFFLEVBQUUsZUFBZSxFQUFFLGVBQWUsRUFBRSxFQUFFLENBQUE7UUFDMUQsQ0FBQzthQUFNLElBQUksR0FBRyxDQUFDLElBQUksS0FBSyxpQkFBTyxDQUFDLEtBQUssQ0FBQyxZQUFZLEVBQUUsQ0FBQztZQUNqRCxrRUFBa0U7WUFDbEUscUVBQXFFO1lBQ3JFLE9BQU8sRUFBRSxLQUFLLEVBQUUsRUFBRSxlQUFlLEVBQUUsZUFBZSxFQUFFLEVBQUUsQ0FBQTtRQUMxRCxDQUFDO1FBQ0QsTUFBTSxHQUFHLENBQUE7SUFDYixDQUFDO0lBRUQsSUFBSSxPQUFPLEVBQUUsU0FBUyxFQUFFLEVBQUUsQ0FBQztRQUN2QixPQUFPO1lBQ0gsUUFBUSxFQUFFO2dCQUNOLFdBQVcsRUFBRSxHQUFHO2dCQUNoQixTQUFTLEVBQUUsS0FBSzthQUNuQjtTQUNKLENBQUE7SUFDTCxDQUFDO0FBQ0wsQ0FBQztBQUdELE1BQU0seUJBQXlCLEdBQUcsSUFBQSxpQkFBTyxFQUN2QyxJQUFJLE9BQU8sQ0FBQyxDQUFDLEdBQUcsRUFBRSxFQUFFLENBQUMsR0FBRyxDQUFDLEdBQUcsRUFBRSxDQUFDLElBQUEsd0JBQW1CLEVBQUMsQ0FBQyw4Q0FBaUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxFQUN6RixFQUFFLEdBQUcsRUFBRSxLQUFLLEVBQUUsQ0FDZixDQUFBO0FBRUEsU0FBUyxTQUFTO0lBQ2YsTUFBTSxDQUFDLEtBQUssRUFBRSxRQUFRLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQVMsRUFBRSxDQUFDLENBQUE7SUFDOUMsTUFBTSxDQUFDLFFBQVEsRUFBRSxXQUFXLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQVMsRUFBRSxDQUFDLENBQUE7SUFDcEQsTUFBTSxDQUFDLElBQUksRUFBRSxPQUFPLENBQUMsR0FBRyxJQUFBLGdCQUFRLEdBQU8sQ0FBQTtJQUN2QyxNQUFNLENBQUMsYUFBYSxFQUFFLGdCQUFnQixDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFTLEVBQUUsQ0FBQyxDQUFBO0lBQzlELE1BQU0sQ0FBQyxTQUFTLEVBQUUsWUFBWSxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFVLEtBQUssQ0FBQyxDQUFBO0lBRTFELDJDQUEyQztJQUMzQyxNQUFNLEtBQUssR0FBRyxJQUFBLGdCQUFRLEdBQUUsQ0FBQTtJQUN4QixNQUFNLE1BQU0sR0FBRyxJQUFBLGtCQUFTLEdBQUUsQ0FBQTtJQUN4QixnREFBZ0Q7SUFDbEQsSUFBQSxpQkFBUyxFQUFDLEdBQUcsRUFBRTtRQUNiLEtBQUssVUFBVSxhQUFhO1lBQzFCLElBQUksQ0FBQztnQkFFSCxNQUFNLE1BQU0sR0FBRyxNQUFNLGlCQUFRLENBQUMsU0FBUyxFQUFFLENBQUE7Z0JBQ3pDLElBQUksTUFBTSxFQUFFLENBQUM7b0JBQ1gsTUFBTSxDQUFDLElBQUksQ0FBQyxHQUFHLENBQUMsQ0FBQTtnQkFDbEIsQ0FBQztZQUNILENBQUM7WUFBQyxPQUFNLENBQUMsRUFBRSxDQUFDO2dCQUNWLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLGlCQUFpQixDQUFDLENBQUE7WUFDbkMsQ0FBQztRQUNILENBQUM7UUFDRCxhQUFhLEVBQUUsQ0FBQTtJQUNqQixDQUFDLEVBQUUsQ0FBQyxNQUFNLENBQUMsQ0FBQyxDQUFBO0lBRVosd0hBQXdIO0lBQ3hILElBQUEsaUJBQVMsRUFBQyxHQUFHLEVBQUU7UUFDYixJQUFJLElBQUEsbUJBQWMsRUFBQyxDQUFDLDhDQUFpQyxDQUFDLENBQUMsS0FBSyxLQUFLLEVBQUUsQ0FBQztZQUNsRSxJQUFBLHVDQUFjLEdBQUUsQ0FBQTtRQUNsQixDQUFDO0lBQ0gsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFBO0lBR04sT0FBTyxDQUNILHVCQUFDLHlCQUF5QixLQUFHLENBQ2hDLENBQUE7QUFFSixDQUFDO0FBR0Qsa0JBQWUsU0FBUyxDQUFBIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IFJlYWN0LCB7IHVzZVN0YXRlLCB1c2VFZmZlY3QgfSBmcm9tICdyZWFjdCdcbmltcG9ydCB7IHVzZVRvYXN0IH0gZnJvbSAnQGNoYWtyYS11aS9yZWFjdCdcbmltcG9ydCB7IHVzZVJvdXRlciB9IGZyb20gJ25leHQvcm91dGVyJ1xuaW1wb3J0IFNlc3Npb24xIGZyb20gXCJzdXBlcnRva2Vucy13ZWItanMvcmVjaXBlL3Nlc3Npb25cIlxuaW1wb3J0IGR5bmFtaWMgZnJvbSAnbmV4dC9keW5hbWljJ1xuaW1wb3J0IHsgVGhpcmRQYXJ0eUVtYWlsUGFzc3dvcmRQcmVCdWlsdFVJIH0gZnJvbSBcInN1cGVydG9rZW5zLWF1dGgtcmVhY3QvcmVjaXBlL3RoaXJkcGFydHllbWFpbHBhc3N3b3JkL3ByZWJ1aWx0dWlcIjtcbmltcG9ydCB7IHJlZGlyZWN0VG9BdXRoIH0gZnJvbSAnc3VwZXJ0b2tlbnMtYXV0aC1yZWFjdCdcbmltcG9ydCB7IGNhbkhhbmRsZVJvdXRlLCBnZXRSb3V0aW5nQ29tcG9uZW50IH0gZnJvbSAnc3VwZXJ0b2tlbnMtYXV0aC1yZWFjdC91aSdcbmltcG9ydCB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCBzdXBlcnRva2Vuc05vZGUgZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZSdcbmltcG9ydCB7IGJhY2tlbmRDb25maWcgfSBmcm9tICdAY29uZmlnL2JhY2tlbmRDb25maWcnXG5pbXBvcnQgU2Vzc2lvbiBmcm9tICdzdXBlcnRva2Vucy1ub2RlL3JlY2lwZS9zZXNzaW9uJ1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0U2VydmVyU2lkZVByb3BzKHsgcmVxLCByZXMgfTogeyByZXE6IE5leHRBcGlSZXF1ZXN0LCByZXM6IE5leHRBcGlSZXNwb25zZSB9KSB7XG4gICAgLy8gTm90aWNlIGhvdyB0aGUgc2VydmVyIHVzZXMgYEFQSWAgZnJvbSBgd2l0aFNTUkNvbnRleHRgLCBpbnN0ZWFkIG9mIHRoZSB0b3AtbGV2ZWwgYEFQSWAuXG4gICAgLy8gY29uc3QgU1NSID0gd2l0aFNTUkNvbnRleHQoeyByZXEgfSlcbiAgICAvLyB0aGlzIHJ1bnMgb24gdGhlIGJhY2tlbmQsIHNvIHdlIG11c3QgY2FsbCBpbml0IG9uIHN1cGVydG9rZW5zLW5vZGUgU0RLXG4gICAgc3VwZXJ0b2tlbnNOb2RlLmluaXQoYmFja2VuZENvbmZpZygpKVxuICAgIGxldCBzZXNzaW9uXG4gICAgdHJ5IHtcbiAgICAgICAgc2Vzc2lvbiA9IGF3YWl0IFNlc3Npb24uZ2V0U2Vzc2lvbihyZXEsIHJlcywge1xuICAgICAgICAgICAgb3ZlcnJpZGVHbG9iYWxDbGFpbVZhbGlkYXRvcnM6IGFzeW5jIGZ1bmN0aW9uICgpIHtcbiAgICAgICAgICAgICAgICByZXR1cm4gW11cbiAgICAgICAgICAgIH0sXG4gICAgICAgIH0pXG4gICAgfSBjYXRjaCAoZXJyOiBhbnkpIHtcbiAgICAgICAgaWYgKGVyci50eXBlID09PSBTZXNzaW9uLkVycm9yLlRSWV9SRUZSRVNIX1RPS0VOKSB7XG4gICAgICAgICAgICByZXR1cm4geyBwcm9wczogeyBmcm9tU3VwZXJ0b2tlbnM6ICduZWVkcy1yZWZyZXNoJyB9IH1cbiAgICAgICAgfSBlbHNlIGlmIChlcnIudHlwZSA9PT0gU2Vzc2lvbi5FcnJvci5VTkFVVEhPUklTRUQpIHtcbiAgICAgICAgICAgIC8vIHRoaXMgd2lsbCBmb3JjZSB0aGUgZnJvbnRlbmQgdG8gdHJ5IGFuZCByZWZyZXNoIHdoaWNoIHdpbGwgZmFpbFxuICAgICAgICAgICAgLy8gY2xlYXJpbmcgYWxsIGNvb2tpZXMgYW5kIHJlZGlyZWN0aW5nIHRoZSB1c2VyIHRvIHRoZSBsb2dpbiBzY3JlZW4uXG4gICAgICAgICAgICByZXR1cm4geyBwcm9wczogeyBmcm9tU3VwZXJ0b2tlbnM6ICduZWVkcy1yZWZyZXNoJyB9IH1cbiAgICAgICAgfVxuICAgICAgICB0aHJvdyBlcnJcbiAgICB9XG5cbiAgICBpZiAoc2Vzc2lvbj8uZ2V0VXNlcklkKCkpIHtcbiAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICAgIHJlZGlyZWN0OiB7XG4gICAgICAgICAgICAgICAgZGVzdGluYXRpb246ICcvJyxcbiAgICAgICAgICAgICAgICBwZXJtYW5lbnQ6IGZhbHNlLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgfVxuICAgIH1cbn1cblxuXG5jb25zdCBTdXBlclRva2Vuc0NvbXBvbmVudE5vU1NSID0gZHluYW1pYzx7fT4oXG4gIG5ldyBQcm9taXNlKChyZXMpID0+IHJlcygoKSA9PiBnZXRSb3V0aW5nQ29tcG9uZW50KFtUaGlyZFBhcnR5RW1haWxQYXNzd29yZFByZUJ1aWx0VUldKSkpLFxuICB7IHNzcjogZmFsc2UgfVxuKVxuXG4gZnVuY3Rpb24gVXNlckxvZ2luKCkge1xuICAgIGNvbnN0IFtlbWFpbCwgc2V0RW1haWxdID0gdXNlU3RhdGU8c3RyaW5nPignJylcbiAgICBjb25zdCBbcGFzc3dvcmQsIHNldFBhc3N3b3JkXSA9IHVzZVN0YXRlPHN0cmluZz4oJycpXG4gICAgY29uc3QgW3VzZXIsIHNldFVzZXJdID0gdXNlU3RhdGU8YW55PigpXG4gICAgY29uc3QgW3Bhc3NDaGFsbGVuZ2UsIHNldFBhc3NDaGFsbGVuZ2VdID0gdXNlU3RhdGU8c3RyaW5nPignJylcbiAgICBjb25zdCBbaXNMb2FkaW5nLCBzZXRJc0xvYWRpbmddID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG5cbiAgICAvLyBjb25zdCBkYXJrID0gdXNlQ29sb3JTY2hlbWUoKSA9PT0gJ2RhcmsnXG4gICAgY29uc3QgdG9hc3QgPSB1c2VUb2FzdCgpXG4gICAgY29uc3Qgcm91dGVyID0gdXNlUm91dGVyKClcbiAgICAgIC8vIGNoZWNrIGlmIHVzZXIgYWxyZWFkeSBsb2dnZWQgaW4gYW5kIGNvbmZpcm1lZFxuICAgIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgICBhc3luYyBmdW5jdGlvbiBjaGVja0xvZ2dlZEluKCkge1xuICAgICAgICB0cnkge1xuICAgICAgICAgIFxuICAgICAgICAgIGNvbnN0IHVzZXJJZCA9IGF3YWl0IFNlc3Npb24xLmdldFVzZXJJZCgpXG4gICAgICAgICAgaWYgKHVzZXJJZCkge1xuICAgICAgICAgICAgcm91dGVyLnB1c2goJy8nKVxuICAgICAgICAgIH1cbiAgICAgICAgfSBjYXRjaChlKSB7XG4gICAgICAgICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gYXV0aCcpXG4gICAgICAgIH1cbiAgICAgIH1cbiAgICAgIGNoZWNrTG9nZ2VkSW4oKVxuICAgIH0sIFtyb3V0ZXJdKVxuXG4gICAgLy8gaWYgdGhlIHVzZXIgdmlzaXRzIGEgcGFnZSB0aGF0IGlzIG5vdCBoYW5kbGVkIGJ5IHVzIChsaWtlIC9hdXRoL3JhbmRvbSksIHRoZW4gd2UgcmVkaXJlY3QgdGhlbSBiYWNrIHRvIHRoZSBhdXRoIHBhZ2UuXG4gICAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICAgIGlmIChjYW5IYW5kbGVSb3V0ZShbVGhpcmRQYXJ0eUVtYWlsUGFzc3dvcmRQcmVCdWlsdFVJXSkgPT09IGZhbHNlKSB7IFxuICAgICAgICByZWRpcmVjdFRvQXV0aCgpXG4gICAgICB9XG4gICAgfSwgW10pXG5cblxuICAgIHJldHVybiAoXG4gICAgICAgIDxTdXBlclRva2Vuc0NvbXBvbmVudE5vU1NSIC8+XG4gICAgKVxuXG4gfVxuXG5cbiBleHBvcnQgZGVmYXVsdCBVc2VyTG9naW5cbiJdfQ==