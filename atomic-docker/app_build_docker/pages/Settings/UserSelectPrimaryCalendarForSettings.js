"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getServerSideProps = getServerSideProps;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const react_native_1 = require("react-native");
const picker_1 = require("@react-native-picker/picker");
const client_1 = require("@apollo/client");
const Box_1 = __importDefault(require("@components/common/Box"));
const Text_1 = __importDefault(require("@components/common/Text"));
const theme_1 = require("@lib/theme/theme");
const OnBoardHelper2_1 = require("@lib/OnBoard/OnBoardHelper2");
const react_2 = require("@chakra-ui/react");
const listCalendars_1 = __importDefault(require("@lib/apollo/gql/listCalendars"));
const ScheduleHelper_1 = require("@lib/Schedule/ScheduleHelper");
const user_context_1 = require("@lib/user-context");
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const backendConfig_1 = require("@config/backendConfig");
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
function UserSelectPrimaryCalendarForSettings() {
    const [selectedValue, setSelectedValue] = (0, react_1.useState)();
    const { sub, client } = (0, user_context_1.useAppContext)();
    const userId = sub;
    // const dark = useColorScheme() === 'dark'
    const toast = (0, react_2.useToast)();
    const { loading, error, data, refetch } = (0, client_1.useQuery)(listCalendars_1.default, {
        variables: { userId: sub },
    });
    if (error) {
        toast({
            status: 'error',
            title: 'Error loading calendars',
            description: error.toString(),
            duration: 9000,
            isClosable: true,
        });
    }
    const calendars = data?.Calendar;
    (0, react_1.useEffect)(() => {
        (async () => {
            const result = await (0, ScheduleHelper_1.getGlobalPrimaryCalendarFunction)(client, userId);
            if (result?.id)
                setSelectedValue(result?.id);
            toast({
                status: 'info',
                title: 'See a change success message',
                description: 'You should see a success changed primary calendar message. Move the picker until you do even with a single calendar.',
                duration: 9000,
                isClosable: true,
            });
        })();
    }, [client, userId, toast]);
    (0, react_1.useEffect)(() => {
        (async () => {
            await (0, OnBoardHelper2_1.createInitialSelectedCalendar)(client, userId, setSelectedValue);
        })();
    }, [client, userId]);
    const changeSelectedCalendar = async (value) => {
        try {
            const newSelectedCalendar = calendars.find(i => i.id === value);
            setSelectedValue(newSelectedCalendar?.id);
            await saveSelectedCalendar(newSelectedCalendar);
            toast({
                status: 'success',
                title: 'Primary Changed',
                description: `Primary calendar changed to ${newSelectedCalendar?.id}`,
                duration: 9000,
                isClosable: true,
            });
        }
        catch (e) {
            console.log(e, ' unable to set calendar');
        }
        await refetch();
    };
    const saveSelectedCalendar = async (newSelectedCalendar) => {
        try {
            await (0, OnBoardHelper2_1.setPrimaryCalendar)(client, newSelectedCalendar);
            const calendarsToDropPrimary = calendars.filter(i => i.id !== newSelectedCalendar.id).map(i => i.id);
            await (0, OnBoardHelper2_1.dropPrimaryLabelForCalendars)(client, calendarsToDropPrimary);
            toast({
                status: 'success',
                title: 'Primary changed',
                description: 'You have successfully changed your primary calendar',
                duration: 9000,
                isClosable: true,
            });
        }
        catch (e) {
            console.log(e, ' unable to save calendar');
        }
    };
    if (loading) {
        return ((0, jsx_runtime_1.jsx)(Box_1.default, { backgroundColor: "primaryCardBackground", flex: 1, justifyContent: "center", alignItems: "center", style: { width: '100%' }, minHeight: "80vh", children: (0, jsx_runtime_1.jsx)(react_native_1.ActivityIndicator, { size: "large", color: theme_1.palette.white }) }));
    }
    return ((0, jsx_runtime_1.jsxs)(Box_1.default, { justifyContent: "space-around", alignItems: "center", style: { width: '100%', minHeight: '70vh' }, children: [(0, jsx_runtime_1.jsx)(Text_1.default, { pt: { phone: 'm', tablet: 's' }, variant: "subheader", children: "Select your primary calendar" }), (0, jsx_runtime_1.jsx)(Text_1.default, { pt: { phone: 'm', tablet: 's' }, variant: "optionHeader", children: `Current primary: ${selectedValue}` }), (0, jsx_runtime_1.jsxs)("div", { className: "flex-1 flex flex-col justify-center items-start", children: [(0, jsx_runtime_1.jsx)(Box_1.default, { justifyContent: "center", alignItems: "center", style: { width: '90%' }, children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "caption", children: "New events will be created on this calendar" }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { mb: { phone: 's', tablet: 'm' }, justifyContent: "center", alignItems: "center", style: { width: '90%' }, children: (0, jsx_runtime_1.jsx)(Box_1.default, { mb: { phone: 's', tablet: 'm' }, style: { width: '100%' }, children: (0, jsx_runtime_1.jsx)(picker_1.Picker, { style: { width: '100%', height: '100%', color: theme_1.palette.textBlack }, selectedValue: selectedValue, onValueChange: changeSelectedCalendar, children: calendars.map(i => ((0, jsx_runtime_1.jsx)(picker_1.Picker.Item, { color: theme_1.palette.textBlack, label: i?.title, value: i?.id }, i?.id))) }) }) })] })] }));
}
exports.default = UserSelectPrimaryCalendarForSettings;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlclNlbGVjdFByaW1hcnlDYWxlbmRhckZvclNldHRpbmdzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiVXNlclNlbGVjdFByaW1hcnlDYWxlbmRhckZvclNldHRpbmdzLnRzeCJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQThCQSxnREFxQ0M7O0FBbkVELGlDQUtpQjtBQUNqQiwrQ0FBZ0U7QUFDaEUsd0RBQWtEO0FBQ2xELDJDQUE4RTtBQUU5RSxpRUFBd0M7QUFDeEMsbUVBQTBDO0FBSTFDLDRDQUEwQztBQUUxQyxnRUFBMEo7QUFDMUosNENBQTJDO0FBRTNDLGtGQUF5RDtBQUN6RCxpRUFBK0U7QUFHL0Usb0RBQWlEO0FBRWpELHdFQUE4QztBQUM5Qyx5REFBcUQ7QUFDckQsOEVBQXFEO0FBRTlDLEtBQUssVUFBVSxrQkFBa0IsQ0FBQyxFQUFFLEdBQUcsRUFBRSxHQUFHLEVBQWlEO0lBQ2hHLDBGQUEwRjtJQUMxRixzQ0FBc0M7SUFDdEMseUVBQXlFO0lBQ3pFLDBCQUFlLENBQUMsSUFBSSxDQUFDLElBQUEsNkJBQWEsR0FBRSxDQUFDLENBQUE7SUFDckMsSUFBSSxPQUFPLENBQUE7SUFDWCxJQUFJLENBQUM7UUFDRCxPQUFPLEdBQUcsTUFBTSxpQkFBTyxDQUFDLFVBQVUsQ0FBQyxHQUFHLEVBQUUsR0FBRyxFQUFFO1lBQ3pDLDZCQUE2QixFQUFFLEtBQUs7Z0JBQ2hDLE9BQU8sRUFBRSxDQUFBO1lBQ2IsQ0FBQztTQUNKLENBQUMsQ0FBQTtJQUNOLENBQUM7SUFBQyxPQUFPLEdBQVEsRUFBRSxDQUFDO1FBQ2hCLElBQUksR0FBRyxDQUFDLElBQUksS0FBSyxpQkFBTyxDQUFDLEtBQUssQ0FBQyxpQkFBaUIsRUFBRSxDQUFDO1lBQy9DLE9BQU8sRUFBRSxLQUFLLEVBQUUsRUFBRSxlQUFlLEVBQUUsZUFBZSxFQUFFLEVBQUUsQ0FBQTtRQUMxRCxDQUFDO2FBQU0sSUFBSSxHQUFHLENBQUMsSUFBSSxLQUFLLGlCQUFPLENBQUMs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QUFFLEtBQUssRUFBRSxHQUFHLEVBQUUsTUFBTSxFQUFFLEdBQUcsRUFBRSxFQUFFLGNBQWMsRUFBQyxRQUFRLEVBQUMsVUFBVSxFQUFDLFFBQVEsRUFBRSxLQUFLLEVBQUUsRUFBRSxLQUFLLEVBQUUsS0FBSyxFQUFFLFlBQ3RHLHVCQUFDLGFBQUcsSUFBQyxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsR0FBRyxFQUFFLE1BQU0sRUFBRSxHQUFHLEVBQUUsRUFBRSxLQUFLLEVBQUUsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLFlBQzFELHVCQUFDLGVBQU0sSUFDSCxLQUFLLEVBQUUsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLE1BQU0sRUFBRSxNQUFNLEVBQUUsS0FBSyxFQUFFLGVBQU8sQ0FBQyxTQUFTLEVBQUUsRUFDbEUsYUFBYSxFQUFFLGFBQWEsRUFDNUIsYUFBYSxFQUFFLHNCQUFzQixZQUNwQyxTQUFTLENBQUMsR0FBRyxDQUFDLENBQUMsQ0FBQyxFQUFFLENBQUMsQ0FDaEIsdUJBQUMsZUFBTSxDQUFDLElBQUksSUFBQyxLQUFLLEVBQUUsZUFBTyxDQUFDLFNBQVMsRUFBRSxLQUFLLEVBQUUsQ0FBQyxFQUFFLEtBQUssRUFBRSxLQUFLLEVBQUUsQ0FBQyxFQUFFLEVBQUUsSUFBTyxDQUFDLEVBQUUsRUFBRSxDQUFJLENBQ3ZGLENBQUMsR0FDRyxHQUNQLEdBQ0osSUFDSixJQUNKLENBQ1QsQ0FBQTtBQUNMLENBQUM7QUFFRCxrQkFBZSxvQ0FBb0MsQ0FBQSIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBSZWFjdCwge1xuICAgIHVzZVN0YXRlLFxuICAgIERpc3BhdGNoLFxuICAgIFNldFN0YXRlQWN0aW9uLFxuICAgIHVzZUVmZmVjdCxcbiAgIH0gZnJvbSAncmVhY3QnXG5pbXBvcnQgeyBBY3Rpdml0eUluZGljYXRvciwgdXNlQ29sb3JTY2hlbWUgfSBmcm9tICdyZWFjdC1uYXRpdmUnXG5pbXBvcnQge1BpY2tlcn0gZnJvbSAnQHJlYWN0LW5hdGl2ZS1waWNrZXIvcGlja2VyJ1xuaW1wb3J0IHsgQXBvbGxvQ2xpZW50LCBOb3JtYWxpemVkQ2FjaGVPYmplY3QsIHVzZVF1ZXJ5IH0gZnJvbSAnQGFwb2xsby9jbGllbnQnXG5cbmltcG9ydCBCb3ggZnJvbSAnQGNvbXBvbmVudHMvY29tbW9uL0JveCdcbmltcG9ydCBUZXh0IGZyb20gJ0Bjb21wb25lbnRzL2NvbW1vbi9UZXh0J1xuaW1wb3J0IEJ1dHRvbiBmcm9tICdAY29tcG9uZW50cy9CdXR0b24nXG5cblxuaW1wb3J0IHsgcGFsZXR0ZSB9IGZyb20gJ0BsaWIvdGhlbWUvdGhlbWUnXG5pbXBvcnQgeyBDYWxlbmRhclR5cGUgfSBmcm9tICdAbGliL2RhdGFUeXBlcy9DYWxlbmRhclR5cGUnXG5pbXBvcnQgeyBjcmVhdGVJbml0aWFsU2VsZWN0ZWRDYWxlbmRhciwgZHJvcFByaW1hcnlMYWJlbEZvckNhbGVuZGFyLCBkcm9wUHJpbWFyeUxhYmVsRm9yQ2FsZW5kYXJzLCBzZXRQcmltYXJ5Q2FsZW5kYXIgfSBmcm9tICdAbGliL09uQm9hcmQvT25Cb2FyZEhlbHBlcjInXG5pbXBvcnQgeyB1c2VUb2FzdCB9IGZyb20gJ0BjaGFrcmEtdWkvcmVhY3QnXG5cbmltcG9ydCBsaXN0Q2FsZW5kYXJzIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9saXN0Q2FsZW5kYXJzJ1xuaW1wb3J0IHsgZ2V0R2xvYmFsUHJpbWFyeUNhbGVuZGFyRnVuY3Rpb24gfSBmcm9tICdAbGliL1NjaGVkdWxlL1NjaGVkdWxlSGVscGVyJ1xuaW1wb3J0IHsgdXNlUm91dGVyIH0gZnJvbSAnbmV4dC9yb3V0ZXInXG5cbmltcG9ydCB7IHVzZUFwcENvbnRleHQgfSBmcm9tICdAbGliL3VzZXItY29udGV4dCdcbmltcG9ydCB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCBzdXBlcnRva2Vuc05vZGUgZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZSdcbmltcG9ydCB7IGJhY2tlbmRDb25maWcgfSBmcm9tICdAY29uZmlnL2JhY2tlbmRDb25maWcnXG5pbXBvcnQgU2Vzc2lvbiBmcm9tICdzdXBlcnRva2Vucy1ub2RlL3JlY2lwZS9zZXNzaW9uJ1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0U2VydmVyU2lkZVByb3BzKHsgcmVxLCByZXMgfTogeyByZXE6IE5leHRBcGlSZXF1ZXN0LCByZXM6IE5leHRBcGlSZXNwb25zZSB9KSB7XG4gICAgLy8gTm90aWNlIGhvdyB0aGUgc2VydmVyIHVzZXMgYEFQSWAgZnJvbSBgd2l0aFNTUkNvbnRleHRgLCBpbnN0ZWFkIG9mIHRoZSB0b3AtbGV2ZWwgYEFQSWAuXG4gICAgLy8gY29uc3QgU1NSID0gd2l0aFNTUkNvbnRleHQoeyByZXEgfSlcbiAgICAvLyB0aGlzIHJ1bnMgb24gdGhlIGJhY2tlbmQsIHNvIHdlIG11c3QgY2FsbCBpbml0IG9uIHN1cGVydG9rZW5zLW5vZGUgU0RLXG4gICAgc3VwZXJ0b2tlbnNOb2RlLmluaXQoYmFja2VuZENvbmZpZygpKVxuICAgIGxldCBzZXNzaW9uXG4gICAgdHJ5IHtcbiAgICAgICAgc2Vzc2lvbiA9IGF3YWl0IFNlc3Npb24uZ2V0U2Vzc2lvbihyZXEsIHJlcywge1xuICAgICAgICAgICAgb3ZlcnJpZGVHbG9iYWxDbGFpbVZhbGlkYXRvcnM6IGFzeW5jIGZ1bmN0aW9uICgpIHtcbiAgICAgICAgICAgICAgICByZXR1cm4gW11cbiAgICAgICAgICAgIH0sXG4gICAgICAgIH0pXG4gICAgfSBjYXRjaCAoZXJyOiBhbnkpIHtcbiAgICAgICAgaWYgKGVyci50eXBlID09PSBTZXNzaW9uLkVycm9yLlRSWV9SRUZSRVNIX1RPS0VOKSB7XG4gICAgICAgICAgICByZXR1cm4geyBwcm9wczogeyBmcm9tU3VwZXJ0b2tlbnM6ICduZWVkcy1yZWZyZXNoJyB9IH1cbiAgICAgICAgfSBlbHNlIGlmIChlcnIudHlwZSA9PT0gU2Vzc2lvbi5FcnJvci5VTkFVVEhPUklTRUQpIHtcbiAgICAgICAgICAgIC8vIHRoaXMgd2lsbCBmb3JjZSB0aGUgZnJvbnRlbmQgdG8gdHJ5IGFuZCByZWZyZXNoIHdoaWNoIHdpbGwgZmFpbFxuICAgICAgICAgICAgLy8gY2xlYXJpbmcgYWxsIGNvb2tpZXMgYW5kIHJlZGlyZWN0aW5nIHRoZSB1c2VyIHRvIHRoZSBsb2dpbiBzY3JlZW4uXG4gICAgICAgICAgICByZXR1cm4geyBwcm9wczogeyBmcm9tU3VwZXJ0b2tlbnM6ICduZWVkcy1yZWZyZXNoJyB9IH1cbiAgICAgICAgfVxuICAgICAgICB0aHJvdyBlcnJcbiAgICB9XG5cbiAgICBpZiAoIXNlc3Npb24/LmdldFVzZXJJZCgpKSB7XG4gICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICByZWRpcmVjdDoge1xuICAgICAgICAgICAgICAgIGRlc3RpbmF0aW9uOiAnL1VzZXIvTG9naW4vVXNlckxvZ2luJyxcbiAgICAgICAgICAgICAgICBwZXJtYW5lbnQ6IGZhbHNlLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgfVxuICAgIH1cblxuICAgIHJldHVybiB7XG4gICAgICAgIHByb3BzOiB7XG4gICAgICAgIHN1Yjogc2Vzc2lvbi5nZXRVc2VySWQoKSxcbiAgICAgICAgfVxuICAgIH1cbn1cblxuXG5mdW5jdGlvbiBVc2VyU2VsZWN0UHJpbWFyeUNhbGVuZGFyRm9yU2V0dGluZ3MoKSB7XG4gICAgY29uc3QgW3NlbGVjdGVkVmFsdWUsIHNldFNlbGVjdGVkVmFsdWVdID0gdXNlU3RhdGU8c3RyaW5nPigpXG4gICAgY29uc3QgeyBzdWIsIGNsaWVudCB9ID0gdXNlQXBwQ29udGV4dCgpXG4gICAgXG4gICAgY29uc3QgdXNlcklkID0gc3ViXG4gICAgLy8gY29uc3QgZGFyayA9IHVzZUNvbG9yU2NoZW1lKCkgPT09ICdkYXJrJ1xuICAgIGNvbnN0IHRvYXN0ID0gdXNlVG9hc3QoKVxuICAgIGNvbnN0IHsgbG9hZGluZywgZXJyb3IsIGRhdGEsIHJlZmV0Y2ggfSA9IHVzZVF1ZXJ5PHsgQ2FsZW5kYXI6IENhbGVuZGFyVHlwZVtdfT4obGlzdENhbGVuZGFycywge1xuICAgICAgICB2YXJpYWJsZXM6IHsgdXNlcklkOiBzdWIgfSxcbiAgICB9KVxuXG4gICAgaWYgKGVycm9yKSB7XG4gICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgIHRpdGxlOiAnRXJyb3IgbG9hZGluZyBjYWxlbmRhcnMnLFxuICAgICAgICAgICAgZGVzY3JpcHRpb246IGVycm9yLnRvU3RyaW5nKCksXG4gICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICAgIH0pXG4gICAgfVxuXG4gICAgY29uc3QgY2FsZW5kYXJzID0gZGF0YT8uQ2FsZW5kYXJcbiAgICBcbiAgICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgICAgICAoYXN5bmMgKCkgPT4ge1xuICAgICAgICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgZ2V0R2xvYmFsUHJpbWFyeUNhbGVuZGFyRnVuY3Rpb24oY2xpZW50LCB1c2VySWQpXG4gICAgICAgICAgICBpZiAocmVzdWx0Py5pZCkgc2V0U2VsZWN0ZWRWYWx1ZShyZXN1bHQ/LmlkKVxuXG4gICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgc3RhdHVzOiAnaW5mbycsXG4gICAgICAgICAgICAgICAgdGl0bGU6ICdTZWUgYSBjaGFuZ2Ugc3VjY2VzcyBtZXNzYWdlJyxcbiAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1lvdSBzaG91bGQgc2VlIGEgc3VjY2VzcyBjaGFuZ2VkIHByaW1hcnkgY2FsZW5kYXIgbWVzc2FnZS4gTW92ZSB0aGUgcGlja2VyIHVudGlsIHlvdSBkbyBldmVuIHdpdGggYSBzaW5nbGUgY2FsZW5kYXIuJyxcbiAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICAgICAgfSlcbiAgICAgICAgfSkoKVxuICAgIH0sIFtjbGllbnQsIHVzZXJJZCwgdG9hc3RdKVxuXG4gICAgXG4gICAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICAgICAgKGFzeW5jICgpID0+IHtcbiAgICAgICAgICAgIGF3YWl0IGNyZWF0ZUluaXRpYWxTZWxlY3RlZENhbGVuZGFyKGNsaWVudCwgdXNlcklkLCBzZXRTZWxlY3RlZFZhbHVlKVxuICAgICAgICB9KSgpXG4gICAgfSwgW2NsaWVudCwgdXNlcklkXSlcblxuXG4gICAgY29uc3QgY2hhbmdlU2VsZWN0ZWRDYWxlbmRhciA9IGFzeW5jICh2YWx1ZTogc3RyaW5nKSA9PiB7XG4gICAgICAgIHRyeSB7XG4gICAgICAgICAgICBjb25zdCBuZXdTZWxlY3RlZENhbGVuZGFyID0gY2FsZW5kYXJzLmZpbmQoaSA9PiBpLmlkID09PSB2YWx1ZSlcbiAgICAgICAgICAgIHNldFNlbGVjdGVkVmFsdWUobmV3U2VsZWN0ZWRDYWxlbmRhcj8uaWQpXG4gICAgICAgICAgICBhd2FpdCBzYXZlU2VsZWN0ZWRDYWxlbmRhcihuZXdTZWxlY3RlZENhbGVuZGFyKVxuICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgIHN0YXR1czogJ3N1Y2Nlc3MnLFxuICAgICAgICAgICAgICAgIHRpdGxlOiAnUHJpbWFyeSBDaGFuZ2VkJyxcbiAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogYFByaW1hcnkgY2FsZW5kYXIgY2hhbmdlZCB0byAke25ld1NlbGVjdGVkQ2FsZW5kYXI/LmlkfWAsXG4gICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZSxcbiAgICAgICAgICAgIH0pXG4gICAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHNldCBjYWxlbmRhcicpXG4gICAgICAgIH1cblxuICAgICAgICBhd2FpdCByZWZldGNoKClcbiAgICB9XG5cbiAgICBjb25zdCBzYXZlU2VsZWN0ZWRDYWxlbmRhciA9IGFzeW5jIChuZXdTZWxlY3RlZENhbGVuZGFyOiBDYWxlbmRhclR5cGUpID0+IHtcbiAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgIGF3YWl0IHNldFByaW1hcnlDYWxlbmRhcihjbGllbnQsIG5ld1NlbGVjdGVkQ2FsZW5kYXIpXG4gICAgICAgICAgICBjb25zdCBjYWxlbmRhcnNUb0Ryb3BQcmltYXJ5ID0gY2FsZW5kYXJzLmZpbHRlcihpID0+IGkuaWQgIT09IG5ld1NlbGVjdGVkQ2FsZW5kYXIuaWQpLm1hcChpID0+IGkuaWQpXG4gICAgICAgICAgICBhd2FpdCBkcm9wUHJpbWFyeUxhYmVsRm9yQ2FsZW5kYXJzKGNsaWVudCwgY2FsZW5kYXJzVG9Ecm9wUHJpbWFyeSlcblxuICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgIHN0YXR1czogJ3N1Y2Nlc3MnLFxuICAgICAgICAgICAgICAgIHRpdGxlOiAnUHJpbWFyeSBjaGFuZ2VkJyxcbiAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1lvdSBoYXZlIHN1Y2Nlc3NmdWxseSBjaGFuZ2VkIHlvdXIgcHJpbWFyeSBjYWxlbmRhcicsXG4gICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZSxcbiAgICAgICAgICAgIH0pXG4gICAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHNhdmUgY2FsZW5kYXInKVxuICAgICAgICB9XG4gICAgfVxuXG4gICAgaWYgKGxvYWRpbmcpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxCb3ggYmFja2dyb3VuZENvbG9yPVwicHJpbWFyeUNhcmRCYWNrZ3JvdW5kXCIgZmxleD17MX0ganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCIgc3R5bGU9e3sgd2lkdGg6ICcxMDAlJ319IG1pbkhlaWdodD1cIjgwdmhcIj5cbiAgICAgICAgICAgICAgICA8QWN0aXZpdHlJbmRpY2F0b3Igc2l6ZT1cImxhcmdlXCIgY29sb3I9e3BhbGV0dGUud2hpdGV9IC8+XG4gICAgICAgICAgICA8L0JveD5cbiAgICAgICAgKVxuICAgIH1cblxuICAgIHJldHVybiAoXG4gICAgICAgIDxCb3gganVzdGlmeUNvbnRlbnQ9XCJzcGFjZS1hcm91bmRcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCIgc3R5bGU9e3sgd2lkdGg6ICcxMDAlJywgbWluSGVpZ2h0OiAnNzB2aCcgfX0+XG4gICAgICAgICAgICA8VGV4dCBwdD17eyBwaG9uZTogJ20nLCB0YWJsZXQ6ICdzJyB9fSB2YXJpYW50PVwic3ViaGVhZGVyXCI+XG4gICAgICAgICAgICAgICAgU2VsZWN0IHlvdXIgcHJpbWFyeSBjYWxlbmRhclxuICAgICAgICAgICAgPC9UZXh0PlxuICAgICAgICAgICAgPFRleHQgcHQ9e3sgcGhvbmU6ICdtJywgdGFibGV0OiAncycgfX0gdmFyaWFudD1cIm9wdGlvbkhlYWRlclwiPlxuICAgICAgICAgICAgICAgIHtgQ3VycmVudCBwcmltYXJ5OiAke3NlbGVjdGVkVmFsdWV9YH1cbiAgICAgICAgICAgIDwvVGV4dD5cbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZmxleC0xIGZsZXggZmxleC1jb2wganVzdGlmeS1jZW50ZXIgaXRlbXMtc3RhcnRcIj5cbiAgICAgICAgICAgICAgICA8Qm94IGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiIHN0eWxlPXt7IHdpZHRoOiAnOTAlJyB9fT5cbiAgICAgICAgICAgICAgICAgICAgXG4gICAgICAgICAgICAgICAgICAgIDxUZXh0IHZhcmlhbnQ9XCJjYXB0aW9uXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICBOZXcgZXZlbnRzIHdpbGwgYmUgY3JlYXRlZCBvbiB0aGlzIGNhbGVuZGFyXG4gICAgICAgICAgICAgICAgICAgIDwvVGV4dD5cbiAgICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgICAgICA8Qm94IG1iPXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19IGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiICBzdHlsZT17eyB3aWR0aDogJzkwJScgfX0+XG4gICAgICAgICAgICAgICAgICAgIDxCb3ggbWI9e3sgcGhvbmU6ICdzJywgdGFibGV0OiAnbScgfX0gc3R5bGU9e3sgd2lkdGg6ICcxMDAlJyB9fT5cbiAgICAgICAgICAgICAgICAgICAgICAgIDxQaWNrZXJcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzdHlsZT17eyB3aWR0aDogJzEwMCUnLCBoZWlnaHQ6ICcxMDAlJywgY29sb3I6IHBhbGV0dGUudGV4dEJsYWNrIH19XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc2VsZWN0ZWRWYWx1ZT17c2VsZWN0ZWRWYWx1ZX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBvblZhbHVlQ2hhbmdlPXtjaGFuZ2VTZWxlY3RlZENhbGVuZGFyfT5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB7Y2FsZW5kYXJzLm1hcChpID0+IChcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPFBpY2tlci5JdGVtIGNvbG9yPXtwYWxldHRlLnRleHRCbGFja30gbGFiZWw9e2k/LnRpdGxlfSB2YWx1ZT17aT8uaWR9IGtleT17aT8uaWR9IC8+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgKSl9XG4gICAgICAgICAgICAgICAgICAgICAgICA8L1BpY2tlcj5cbiAgICAgICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgPC9Cb3g+XG4gICAgKVxufVxuXG5leHBvcnQgZGVmYXVsdCBVc2VyU2VsZWN0UHJpbWFyeUNhbGVuZGFyRm9yU2V0dGluZ3NcblxuIl19