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
// name = checkmark
const Box_1 = __importDefault(require("@components/common/Box"));
const Text_1 = __importDefault(require("@components/common/Text"));
const theme_1 = require("@lib/theme/theme");
const OnBoardHelper2_1 = require("@lib/OnBoard/OnBoardHelper2");
const client_1 = require("@apollo/client");
const listCalendars_1 = __importDefault(require("@lib/apollo/gql/listCalendars"));
const react_2 = require("@chakra-ui/react");
const ScheduleHelper_1 = require("@lib/Schedule/ScheduleHelper");
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
function UserSelectPrimaryCalendar(props) {
    // const [selectedCalendar, setSelectedCalendar] = useState<CalendarType>(props?.selectedCalendar)
    // const [calendars, setCalendars] = useState<CalendarType[]>([])
    const [selectedValue, setSelectedValue] = (0, react_1.useState)(props?.selectedCalendarId);
    const client = props?.client;
    const userId = props?.userId;
    // const dark = useColorScheme() === 'dark'
    const toast = (0, react_2.useToast)();
    const { loading, error, data, refetch } = (0, client_1.useQuery)(listCalendars_1.default, {
        variables: { userId: props?.userId },
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
    console.log(calendars, ' calendars');
    console.log(props?.selectedCalendarId, ' props?.selectedCalendarId');
    // getglobal primary calendar if any
    (0, react_1.useEffect)(() => {
        (async () => {
            const result = await (0, ScheduleHelper_1.getGlobalPrimaryCalendarFunction)(client, props?.userId);
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
    }, [client, props?.userId, toast]);
    const changeSelectedCalendar = async (value) => {
        try {
            const newSelectedCalendar = calendars.find(i => i.id === value);
            props?.setParentSelectedCalendarId(newSelectedCalendar?.id);
            setSelectedValue(newSelectedCalendar?.id);
            // setSelectedCalendar(newSelectedCalendar as CalendarType)
            await saveSelectedCalendar(newSelectedCalendar);
        }
        catch (e) {
            console.log(e, ' unable to set calendar');
        }
        await refetch();
    };
    const saveSelectedCalendar = async (newSelectedCalendar) => {
        try {
            await (0, OnBoardHelper2_1.setPrimaryCalendar)(client, newSelectedCalendar);
            // remove primary from other calendars
            const calendarsToDropPrimary = calendars.filter(i => i.id !== newSelectedCalendar.id).map(c => c.id);
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
    return ((0, jsx_runtime_1.jsxs)(Box_1.default, { justifyContent: "center", alignItems: "center", style: { width: '100%' }, children: [(0, jsx_runtime_1.jsx)(Text_1.default, { pt: { phone: 'm', tablet: 's' }, variant: "subheader", children: "Select your primary calendar" }), (0, jsx_runtime_1.jsx)(Text_1.default, { pt: { phone: 'm', tablet: 's' }, variant: "optionHeader", children: `Current primary: ${selectedValue}` }), (0, jsx_runtime_1.jsxs)("div", { className: "flex-1 flex flex-col justify-center items-start", style: { minHeight: '70vh' }, children: [(0, jsx_runtime_1.jsx)(Box_1.default, { flex: 1, justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "body", children: "New events will be created on this calendar" }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { flex: 2, mb: { phone: 's', tablet: 'm' }, justifyContent: "center", alignItems: "center", style: { width: '100%' }, children: (0, jsx_runtime_1.jsx)(Box_1.default, { mb: { phone: 's', tablet: 'm' }, style: { width: '100%' }, children: (0, jsx_runtime_1.jsx)(picker_1.Picker, { style: { width: '100%', height: '100%', color: theme_1.palette.textBlack }, selectedValue: selectedValue, onValueChange: changeSelectedCalendar, children: calendars.map(i => ((0, jsx_runtime_1.jsx)(picker_1.Picker.Item, { color: theme_1.palette.textBlack, label: i?.title, value: i?.id }, i?.id))) }) }) })] })] }));
}
exports.default = UserSelectPrimaryCalendar;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlclNlbGVjdFByaW1hcnlDYWxlbmRhci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIlVzZXJTZWxlY3RQcmltYXJ5Q2FsZW5kYXIudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7O0FBMkJBLGdEQXFDQzs7QUFoRUQsaUNBS2lCO0FBQ2pCLCtDQUFnRTtBQUNoRSx3REFBa0Q7QUFDbEQsbUJBQW1CO0FBRW5CLGlFQUF3QztBQUN4QyxtRUFBMEM7QUFHMUMsNENBQTBDO0FBRTFDLGdFQUEwSjtBQUMxSiwyQ0FBOEU7QUFDOUUsa0ZBQXlEO0FBQ3pELDRDQUEyQztBQUUzQyxpRUFBK0U7QUFFL0Usd0VBQThDO0FBQzlDLHlEQUFxRDtBQUNyRCw4RUFBcUQ7QUFFOUMsS0FBSyxVQUFVLGtCQUFrQixDQUFDLEVBQUUsR0FBRyxFQUFFLEdBQUcsRUFBaUQ7SUFDaEcsMEZBQTBGO0lBQzFGLHNDQUFzQztJQUN0Qyx5RUFBeUU7SUFDekUsMEJBQWUsQ0FBQyxJQUFJLENBQUMsSUFBQSw2QkFBYSxHQUFFLENBQUMsQ0FBQTtJQUNyQyxJQUFJLE9BQU8sQ0FBQTtJQUNYLElBQUksQ0FBQztRQUNELE9BQU8sR0FBRyxNQUFNLGlCQUFPLENBQUMsVUFBVSxDQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUU7WUFDekMsNkJBQTZCLEVBQUUsS0FBSztnQkFDaEMsT0FBTyxFQUFFLENBQUE7WUFDYixDQUFDO1NBQ0osQ0FBQyxDQUFBO0lBQ04sQ0FBQztJQUFDLE9BQU8sR0FBUSxFQUFFLENBQUM7UUFDaEIsSUFBSSxHQUFHLENBQUMsSUFBSSxLQUFLLGlCQUFPLENBQUMsS0FBSyxDQUFDLGlCQUFpQixFQUFFLENBQUM7WUFDL0MsT0FBTyxFQUFFLEtBQUssRUFBRSxFQUFFLGVBQWUsRUFBRSxlQUFlLEVBQUUsRUFBRSxDQUFBO1FBQzFELENBQUM7YUFBTSxJQUFJLEdBQUcsQ0FBQyxJQUFJLEtBQUssaUJBQU8sQ0FBQyxLQUFLLENBQUMsWUFBWSxFQUFFLENB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LFFBQVEsRUFBRSxLQUFLLEVBQUUsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLFlBQ2hILHVCQUFDLGFBQUcsSUFBQyxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsR0FBRyxFQUFFLE1BQU0sRUFBRSxHQUFHLEVBQUUsRUFBRSxLQUFLLEVBQUUsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLFlBQzFELHVCQUFDLGVBQU0sSUFDSCxLQUFLLEVBQUUsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLE1BQU0sRUFBRSxNQUFNLEVBQUUsS0FBSyxFQUFFLGVBQU8sQ0FBQyxTQUFTLEVBQUUsRUFDbEUsYUFBYSxFQUFFLGFBQWEsRUFDNUIsYUFBYSxFQUFFLHNCQUFzQixZQUNwQyxTQUFTLENBQUMsR0FBRyxDQUFDLENBQUMsQ0FBQyxFQUFFLENBQUMsQ0FDaEIsdUJBQUMsZUFBTSxDQUFDLElBQUksSUFBQyxLQUFLLEVBQUUsZUFBTyxDQUFDLFNBQVMsRUFBRSxLQUFLLEVBQUUsQ0FBQyxFQUFFLEtBQUssRUFBRSxLQUFLLEVBQUUsQ0FBQyxFQUFFLEVBQUUsSUFBTyxDQUFDLEVBQUUsRUFBRSxDQUFJLENBQ3ZGLENBQUMsR0FDRyxHQUNQLEdBQ0osSUFDSixJQUNKLENBQ1QsQ0FBQTtBQUNMLENBQUM7QUFFRCxrQkFBZSx5QkFBeUIsQ0FBQSIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBSZWFjdCwge1xuICAgIHVzZVN0YXRlLFxuICAgIERpc3BhdGNoLFxuICAgIFNldFN0YXRlQWN0aW9uLFxuICAgIHVzZUVmZmVjdCxcbiAgIH0gZnJvbSAncmVhY3QnXG5pbXBvcnQgeyBBY3Rpdml0eUluZGljYXRvciwgdXNlQ29sb3JTY2hlbWUgfSBmcm9tICdyZWFjdC1uYXRpdmUnXG5pbXBvcnQge1BpY2tlcn0gZnJvbSAnQHJlYWN0LW5hdGl2ZS1waWNrZXIvcGlja2VyJ1xuLy8gbmFtZSA9IGNoZWNrbWFya1xuXG5pbXBvcnQgQm94IGZyb20gJ0Bjb21wb25lbnRzL2NvbW1vbi9Cb3gnXG5pbXBvcnQgVGV4dCBmcm9tICdAY29tcG9uZW50cy9jb21tb24vVGV4dCdcbmltcG9ydCBCdXR0b24gZnJvbSAnQGNvbXBvbmVudHMvQnV0dG9uJ1xuXG5pbXBvcnQgeyBwYWxldHRlIH0gZnJvbSAnQGxpYi90aGVtZS90aGVtZSdcbmltcG9ydCB7IENhbGVuZGFyVHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL0NhbGVuZGFyVHlwZSdcbmltcG9ydCB7IGNyZWF0ZUluaXRpYWxTZWxlY3RlZENhbGVuZGFyLCBkcm9wUHJpbWFyeUxhYmVsRm9yQ2FsZW5kYXIsIGRyb3BQcmltYXJ5TGFiZWxGb3JDYWxlbmRhcnMsIHNldFByaW1hcnlDYWxlbmRhciB9IGZyb20gJ0BsaWIvT25Cb2FyZC9PbkJvYXJkSGVscGVyMidcbmltcG9ydCB7IEFwb2xsb0NsaWVudCwgTm9ybWFsaXplZENhY2hlT2JqZWN0LCB1c2VRdWVyeSB9IGZyb20gJ0BhcG9sbG8vY2xpZW50J1xuaW1wb3J0IGxpc3RDYWxlbmRhcnMgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2xpc3RDYWxlbmRhcnMnXG5pbXBvcnQgeyB1c2VUb2FzdCB9IGZyb20gJ0BjaGFrcmEtdWkvcmVhY3QnXG5cbmltcG9ydCB7IGdldEdsb2JhbFByaW1hcnlDYWxlbmRhckZ1bmN0aW9uIH0gZnJvbSAnQGxpYi9TY2hlZHVsZS9TY2hlZHVsZUhlbHBlcidcbmltcG9ydCB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCBzdXBlcnRva2Vuc05vZGUgZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZSdcbmltcG9ydCB7IGJhY2tlbmRDb25maWcgfSBmcm9tICdAY29uZmlnL2JhY2tlbmRDb25maWcnXG5pbXBvcnQgU2Vzc2lvbiBmcm9tICdzdXBlcnRva2Vucy1ub2RlL3JlY2lwZS9zZXNzaW9uJ1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0U2VydmVyU2lkZVByb3BzKHsgcmVxLCByZXMgfTogeyByZXE6IE5leHRBcGlSZXF1ZXN0LCByZXM6IE5leHRBcGlSZXNwb25zZSB9KSB7XG4gICAgLy8gTm90aWNlIGhvdyB0aGUgc2VydmVyIHVzZXMgYEFQSWAgZnJvbSBgd2l0aFNTUkNvbnRleHRgLCBpbnN0ZWFkIG9mIHRoZSB0b3AtbGV2ZWwgYEFQSWAuXG4gICAgLy8gY29uc3QgU1NSID0gd2l0aFNTUkNvbnRleHQoeyByZXEgfSlcbiAgICAvLyB0aGlzIHJ1bnMgb24gdGhlIGJhY2tlbmQsIHNvIHdlIG11c3QgY2FsbCBpbml0IG9uIHN1cGVydG9rZW5zLW5vZGUgU0RLXG4gICAgc3VwZXJ0b2tlbnNOb2RlLmluaXQoYmFja2VuZENvbmZpZygpKVxuICAgIGxldCBzZXNzaW9uXG4gICAgdHJ5IHtcbiAgICAgICAgc2Vzc2lvbiA9IGF3YWl0IFNlc3Npb24uZ2V0U2Vzc2lvbihyZXEsIHJlcywge1xuICAgICAgICAgICAgb3ZlcnJpZGVHbG9iYWxDbGFpbVZhbGlkYXRvcnM6IGFzeW5jIGZ1bmN0aW9uICgpIHtcbiAgICAgICAgICAgICAgICByZXR1cm4gW11cbiAgICAgICAgICAgIH0sXG4gICAgICAgIH0pXG4gICAgfSBjYXRjaCAoZXJyOiBhbnkpIHtcbiAgICAgICAgaWYgKGVyci50eXBlID09PSBTZXNzaW9uLkVycm9yLlRSWV9SRUZSRVNIX1RPS0VOKSB7XG4gICAgICAgICAgICByZXR1cm4geyBwcm9wczogeyBmcm9tU3VwZXJ0b2tlbnM6ICduZWVkcy1yZWZyZXNoJyB9IH1cbiAgICAgICAgfSBlbHNlIGlmIChlcnIudHlwZSA9PT0gU2Vzc2lvbi5FcnJvci5VTkFVVEhPUklTRUQpIHtcbiAgICAgICAgICAgIC8vIHRoaXMgd2lsbCBmb3JjZSB0aGUgZnJvbnRlbmQgdG8gdHJ5IGFuZCByZWZyZXNoIHdoaWNoIHdpbGwgZmFpbFxuICAgICAgICAgICAgLy8gY2xlYXJpbmcgYWxsIGNvb2tpZXMgYW5kIHJlZGlyZWN0aW5nIHRoZSB1c2VyIHRvIHRoZSBsb2dpbiBzY3JlZW4uXG4gICAgICAgICAgICByZXR1cm4geyBwcm9wczogeyBmcm9tU3VwZXJ0b2tlbnM6ICduZWVkcy1yZWZyZXNoJyB9IH1cbiAgICAgICAgfVxuICAgICAgICB0aHJvdyBlcnJcbiAgICB9XG5cbiAgICBpZiAoIXNlc3Npb24/LmdldFVzZXJJZCgpKSB7XG4gICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICByZWRpcmVjdDoge1xuICAgICAgICAgICAgICAgIGRlc3RpbmF0aW9uOiAnL1VzZXIvTG9naW4vVXNlckxvZ2luJyxcbiAgICAgICAgICAgICAgICBwZXJtYW5lbnQ6IGZhbHNlLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgfVxuICAgIH1cblxuICAgIHJldHVybiB7XG4gICAgICAgIHByb3BzOiB7XG4gICAgICAgIHN1Yjogc2Vzc2lvbi5nZXRVc2VySWQoKSxcbiAgICAgICAgfVxuICAgIH1cbn1cblxudHlwZSBQcm9wcyA9IHtcbiAgICBzZWxlY3RlZENhbGVuZGFySWQ6IHN0cmluZyxcbiAgICBzZXRQYXJlbnRTZWxlY3RlZENhbGVuZGFySWQ6IERpc3BhdGNoPHN0cmluZz4sXG4gICAgdXNlcklkOiBzdHJpbmcsXG4gICAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0Pixcbn1cblxuZnVuY3Rpb24gVXNlclNlbGVjdFByaW1hcnlDYWxlbmRhcihwcm9wczogUHJvcHMpIHtcbiAgICAvLyBjb25zdCBbc2VsZWN0ZWRDYWxlbmRhciwgc2V0U2VsZWN0ZWRDYWxlbmRhcl0gPSB1c2VTdGF0ZTxDYWxlbmRhclR5cGU+KHByb3BzPy5zZWxlY3RlZENhbGVuZGFyKVxuICAgIC8vIGNvbnN0IFtjYWxlbmRhcnMsIHNldENhbGVuZGFyc10gPSB1c2VTdGF0ZTxDYWxlbmRhclR5cGVbXT4oW10pXG4gICAgY29uc3QgW3NlbGVjdGVkVmFsdWUsIHNldFNlbGVjdGVkVmFsdWVdID0gdXNlU3RhdGU8c3RyaW5nPihwcm9wcz8uc2VsZWN0ZWRDYWxlbmRhcklkKVxuXG4gICAgY29uc3QgY2xpZW50ID0gcHJvcHM/LmNsaWVudFxuICAgIGNvbnN0IHVzZXJJZCA9IHByb3BzPy51c2VySWRcbiAgICAvLyBjb25zdCBkYXJrID0gdXNlQ29sb3JTY2hlbWUoKSA9PT0gJ2RhcmsnXG4gICAgY29uc3QgdG9hc3QgPSB1c2VUb2FzdCgpXG4gICAgY29uc3QgeyBsb2FkaW5nLCBlcnJvciwgZGF0YSwgcmVmZXRjaCB9ID0gdXNlUXVlcnk8eyBDYWxlbmRhcjogQ2FsZW5kYXJUeXBlW119PihsaXN0Q2FsZW5kYXJzLCB7XG4gICAgICAgIHZhcmlhYmxlczogeyB1c2VySWQ6IHByb3BzPy51c2VySWQgfSxcbiAgICB9KVxuXG4gICAgaWYgKGVycm9yKSB7XG4gICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgIHRpdGxlOiAnRXJyb3IgbG9hZGluZyBjYWxlbmRhcnMnLFxuICAgICAgICAgICAgZGVzY3JpcHRpb246IGVycm9yLnRvU3RyaW5nKCksXG4gICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICAgIH0pXG4gICAgfVxuXG4gICAgY29uc3QgY2FsZW5kYXJzID0gZGF0YT8uQ2FsZW5kYXJcbiAgICBjb25zb2xlLmxvZyhjYWxlbmRhcnMsICcgY2FsZW5kYXJzJylcbiAgICBjb25zb2xlLmxvZyhwcm9wcz8uc2VsZWN0ZWRDYWxlbmRhcklkLCcgcHJvcHM/LnNlbGVjdGVkQ2FsZW5kYXJJZCcpXG5cbiAgICAvLyBnZXRnbG9iYWwgcHJpbWFyeSBjYWxlbmRhciBpZiBhbnlcbiAgICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgICAgICAoYXN5bmMgKCkgPT4ge1xuICAgICAgICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgZ2V0R2xvYmFsUHJpbWFyeUNhbGVuZGFyRnVuY3Rpb24oY2xpZW50LCBwcm9wcz8udXNlcklkKVxuICAgICAgICAgICAgaWYgKHJlc3VsdD8uaWQpIHNldFNlbGVjdGVkVmFsdWUocmVzdWx0Py5pZClcblxuICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgIHN0YXR1czogJ2luZm8nLFxuICAgICAgICAgICAgICAgIHRpdGxlOiAnU2VlIGEgY2hhbmdlIHN1Y2Nlc3MgbWVzc2FnZScsXG4gICAgICAgICAgICAgICAgZGVzY3JpcHRpb246ICdZb3Ugc2hvdWxkIHNlZSBhIHN1Y2Nlc3MgY2hhbmdlZCBwcmltYXJ5IGNhbGVuZGFyIG1lc3NhZ2UuIE1vdmUgdGhlIHBpY2tlciB1bnRpbCB5b3UgZG8gZXZlbiB3aXRoIGEgc2luZ2xlIGNhbGVuZGFyLicsXG4gICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZSxcbiAgICAgICAgICAgIH0pXG4gICAgICAgIH0pKClcbiAgICB9LCBbY2xpZW50LCBwcm9wcz8udXNlcklkLCB0b2FzdF0pXG5cblxuICAgIGNvbnN0IGNoYW5nZVNlbGVjdGVkQ2FsZW5kYXIgPSBhc3luYyAodmFsdWU6IHN0cmluZykgPT4ge1xuICAgICAgICB0cnkge1xuICAgICAgICAgICAgY29uc3QgbmV3U2VsZWN0ZWRDYWxlbmRhciA9IGNhbGVuZGFycy5maW5kKGkgPT4gaS5pZCA9PT0gdmFsdWUpXG4gICAgICAgICAgICBwcm9wcz8uc2V0UGFyZW50U2VsZWN0ZWRDYWxlbmRhcklkKG5ld1NlbGVjdGVkQ2FsZW5kYXI/LmlkKVxuICAgICAgICAgICAgc2V0U2VsZWN0ZWRWYWx1ZShuZXdTZWxlY3RlZENhbGVuZGFyPy5pZClcbiAgICAgICAgICAgIC8vIHNldFNlbGVjdGVkQ2FsZW5kYXIobmV3U2VsZWN0ZWRDYWxlbmRhciBhcyBDYWxlbmRhclR5cGUpXG4gICAgICAgICAgICBhd2FpdCBzYXZlU2VsZWN0ZWRDYWxlbmRhcihuZXdTZWxlY3RlZENhbGVuZGFyKVxuICAgICAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBzZXQgY2FsZW5kYXInKVxuICAgICAgICB9XG4gICAgICAgIGF3YWl0IHJlZmV0Y2goKVxuICAgIH1cblxuICAgIGNvbnN0IHNhdmVTZWxlY3RlZENhbGVuZGFyID0gYXN5bmMgKG5ld1NlbGVjdGVkQ2FsZW5kYXI6IENhbGVuZGFyVHlwZSkgPT4ge1xuICAgICAgICB0cnkge1xuICAgICAgICAgICAgYXdhaXQgc2V0UHJpbWFyeUNhbGVuZGFyKGNsaWVudCwgbmV3U2VsZWN0ZWRDYWxlbmRhcilcbiAgICAgICAgICAgIC8vIHJlbW92ZSBwcmltYXJ5IGZyb20gb3RoZXIgY2FsZW5kYXJzXG4gICAgICAgICAgICBjb25zdCBjYWxlbmRhcnNUb0Ryb3BQcmltYXJ5ID0gY2FsZW5kYXJzLmZpbHRlcihpID0+IGkuaWQgIT09IG5ld1NlbGVjdGVkQ2FsZW5kYXIuaWQpLm1hcChjID0+IGMuaWQpXG4gICAgICAgICAgICBhd2FpdCBkcm9wUHJpbWFyeUxhYmVsRm9yQ2FsZW5kYXJzKGNsaWVudCwgY2FsZW5kYXJzVG9Ecm9wUHJpbWFyeSlcblxuICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgIHN0YXR1czogJ3N1Y2Nlc3MnLFxuICAgICAgICAgICAgICAgIHRpdGxlOiAnUHJpbWFyeSBjaGFuZ2VkJyxcbiAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1lvdSBoYXZlIHN1Y2Nlc3NmdWxseSBjaGFuZ2VkIHlvdXIgcHJpbWFyeSBjYWxlbmRhcicsXG4gICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZSxcbiAgICAgICAgICAgIH0pXG4gICAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHNhdmUgY2FsZW5kYXInKVxuICAgICAgICB9XG4gICAgfVxuXG4gICAgaWYgKGxvYWRpbmcpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgIDxCb3ggYmFja2dyb3VuZENvbG9yPVwicHJpbWFyeUNhcmRCYWNrZ3JvdW5kXCIgZmxleD17MX0ganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCIgc3R5bGU9e3sgd2lkdGg6ICcxMDAlJ319IG1pbkhlaWdodD1cIjgwdmhcIj5cbiAgICAgICAgICAgICAgPEFjdGl2aXR5SW5kaWNhdG9yIHNpemU9XCJsYXJnZVwiIGNvbG9yPXtwYWxldHRlLndoaXRlfSAvPlxuICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgIClcbiAgICB9XG5cbiAgICByZXR1cm4gKFxuICAgICAgICA8Qm94IGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiIHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0+XG4gICAgICAgICAgICA8VGV4dCBwdD17eyBwaG9uZTogJ20nLCB0YWJsZXQ6ICdzJyB9fSB2YXJpYW50PVwic3ViaGVhZGVyXCI+XG4gICAgICAgICAgICAgICAgU2VsZWN0IHlvdXIgcHJpbWFyeSBjYWxlbmRhclxuICAgICAgICAgICAgPC9UZXh0PlxuICAgICAgICAgICAgPFRleHQgcHQ9e3sgcGhvbmU6ICdtJywgdGFibGV0OiAncycgfX0gdmFyaWFudD1cIm9wdGlvbkhlYWRlclwiPlxuICAgICAgICAgICAgICAgIHtgQ3VycmVudCBwcmltYXJ5OiAke3NlbGVjdGVkVmFsdWV9YH1cbiAgICAgICAgICAgIDwvVGV4dD5cbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZmxleC0xIGZsZXggZmxleC1jb2wganVzdGlmeS1jZW50ZXIgaXRlbXMtc3RhcnRcIiBzdHlsZT17eyBtaW5IZWlnaHQ6ICc3MHZoJ319PlxuICAgICAgICAgICAgICAgIDxCb3ggZmxleD17MX0ganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgICAgIFxuICAgICAgICAgICAgICAgICAgICA8VGV4dCB2YXJpYW50PVwiYm9keVwiPlxuICAgICAgICAgICAgICAgICAgICAgICAgTmV3IGV2ZW50cyB3aWxsIGJlIGNyZWF0ZWQgb24gdGhpcyBjYWxlbmRhclxuICAgICAgICAgICAgICAgICAgICA8L1RleHQ+XG4gICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgPEJveCBmbGV4PXsyfSBtYj17eyBwaG9uZTogJ3MnLCB0YWJsZXQ6ICdtJyB9fSBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiAgc3R5bGU9e3sgd2lkdGg6ICcxMDAlJyB9fT5cbiAgICAgICAgICAgICAgICAgICAgPEJveCBtYj17eyBwaG9uZTogJ3MnLCB0YWJsZXQ6ICdtJyB9fSBzdHlsZT17eyB3aWR0aDogJzEwMCUnIH19PlxuICAgICAgICAgICAgICAgICAgICAgICAgPFBpY2tlclxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHN0eWxlPXt7IHdpZHRoOiAnMTAwJScsIGhlaWdodDogJzEwMCUnLCBjb2xvcjogcGFsZXR0ZS50ZXh0QmxhY2sgfX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzZWxlY3RlZFZhbHVlPXtzZWxlY3RlZFZhbHVlfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIG9uVmFsdWVDaGFuZ2U9e2NoYW5nZVNlbGVjdGVkQ2FsZW5kYXJ9PlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHtjYWxlbmRhcnMubWFwKGkgPT4gKFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8UGlja2VyLkl0ZW0gY29sb3I9e3BhbGV0dGUudGV4dEJsYWNrfSBsYWJlbD17aT8udGl0bGV9IHZhbHVlPXtpPy5pZH0ga2V5PXtpPy5pZH0gLz5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICApKX1cbiAgICAgICAgICAgICAgICAgICAgICAgIDwvUGlja2VyPlxuICAgICAgICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICA8L0JveD5cbiAgICApXG59XG5cbmV4cG9ydCBkZWZhdWx0IFVzZXJTZWxlY3RQcmltYXJ5Q2FsZW5kYXJcblxuIl19