"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getServerSideProps = getServerSideProps;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const react_native_1 = require("react-native");
const client_1 = require("@apollo/client");
const Switch_1 = __importDefault(require("@components/Switch"));
const react_2 = require("@chakra-ui/react");
const Box_1 = __importDefault(require("@components/common/Box"));
const Text_1 = __importDefault(require("@components/common/Text"));
const theme_1 = require("@lib/theme/theme");
const calendar_integrationHelper_1 = require("@lib/Settings/calendar_integrationHelper");
const constants_1 = require("@lib/calendarLib/constants");
const calendarDbHelper_1 = require("@lib/calendarLib/calendarDbHelper");
const getCalendarWithResource_1 = __importDefault(require("@lib/apollo/gql/getCalendarWithResource"));
const getCalendarIntegrationByResourceAndName_1 = __importDefault(require("@lib/apollo/gql/getCalendarIntegrationByResourceAndName"));
const OnBoardHelper2_1 = require("@lib/OnBoard/OnBoardHelper2");
const AttendeeHelper_1 = require("@lib/Calendar/Attendee/AttendeeHelper");
const ReminderHelper_1 = require("@lib/Calendar/Reminder/ReminderHelper");
const ConferenceHelper_1 = require("@lib/Calendar/Conference/ConferenceHelper");
const router_1 = require("next/router");
const user_context_1 = require("@lib/user-context");
const Button_1 = __importDefault(require("@components/Button"));
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
function CalendarCheckBox(props) {
    const { enabled: oldEnabled, updateEnabledValue, index, name, id, calendars, } = props;
    const [enabled, setEnabled] = (0, react_1.useState)(oldEnabled);
    (0, react_1.useEffect)(() => {
        (async () => {
            try {
                const index = calendars.findIndex(i => (i?.id === id));
                if (index !== -1) {
                    setEnabled(true);
                }
            }
            catch (e) {
                console.log(e, ' error in calendar checkbox');
            }
        })();
    }, [calendars, calendars?.length, id]);
    const updateEnabled = (value) => {
        setEnabled(value);
        updateEnabledValue(index, value, id);
    };
    return ((0, jsx_runtime_1.jsxs)("div", { className: "flex justify-between items-center sm:w-1/3 w-9/12", children: [(0, jsx_runtime_1.jsx)(Box_1.default, { children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "optionHeader", style: { color: theme_1.palette.darkGray }, children: name }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { children: (0, jsx_runtime_1.jsx)(Switch_1.default, { onValueChange: updateEnabled, checked: enabled }) })] }));
}
function UserGoogleCalendarList(props) {
    const router = (0, router_1.useRouter)();
    const { sub, client } = (0, user_context_1.useAppContext)();
    const [calendarList, setCalendarList] = (0, react_1.useState)([]);
    const [loading, setLoading] = (0, react_1.useState)(false);
    // const [integration, setIntegration] = useState<CalendarIntegrationType>()
    // const [calendars, setCalendars] = useState<CalendarType[]>([])
    const [enabledCalendars, setEnabledCalendars] = (0, react_1.useState)([]);
    const [enableAllCalendars, setEnableAllCalendars] = (0, react_1.useState)(false);
    const [disableLoading, setDisableLoading] = (0, react_1.useState)(false);
    const toast = (0, react_2.useToast)();
    const token = props?.token;
    console.log(token, ' token inside UserViewGoogleCalendarList');
    const { loading: existingCalendarLoading, error: existingCalendarError, data } = (0, client_1.useQuery)(getCalendarWithResource_1.default, {
        variables: { userId: sub, resource: constants_1.googleResourceName },
    });
    const { loading: integrationLoading, error: integrationError, data: integrationData } = (0, client_1.useQuery)(getCalendarIntegrationByResourceAndName_1.default, {
        variables: {
            name: constants_1.googleCalendarName,
            resource: constants_1.googleResourceName,
            userId: sub,
        }
    });
    const calendars = data?.Calendar;
    const calendarIntegrations = integrationData?.Calendar_Integration;
    // set enabledCalendars
    (0, react_1.useEffect)(() => {
        if (!token)
            return;
        (async () => {
            try {
                setLoading(true);
                const results = await (0, calendar_integrationHelper_1.listGoogleCalendars)(token);
                console.log(results, ' results from listGoogleCalendars');
                const existingEnabledCalendars = results.map(calendar => {
                    const calendarId = calendar.id;
                    const calendarName = calendar.summary;
                    const calendarIndex = calendars?.findIndex(c => c.id === calendarId);
                    return {
                        id: calendarId,
                        name: calendarName,
                        enabled: (calendarIndex > -1),
                    };
                });
                setCalendarList(results);
                setEnabledCalendars(existingEnabledCalendars);
                setLoading(false);
                setDisableLoading(true);
            }
            catch (e) {
                console.log(e, ' error getting calendars');
                setLoading(false);
                toast({
                    status: 'error',
                    title: 'Error getting calendars',
                    description: e.toString(),
                    duration: 9000,
                    isClosable: true,
                });
                setDisableLoading(true);
            }
        })();
    }, [token, calendars?.length, calendars, toast]);
    // const dark = useColorScheme() === 'dark'
    const updateEnabledCalendarValue = async (index, value) => {
        try {
            const newEnabledCalendars = enabledCalendars.map((c, idx) => {
                if (idx === index) {
                    return {
                        ...c,
                        enabled: value,
                    };
                }
                return c;
            });
            setEnabledCalendars(newEnabledCalendars);
        }
        catch (e) {
            console.log(e, ' error updating enabled value');
            toast({
                status: 'error',
                title: 'Error updating enabled value',
                description: e.toString(),
                duration: 9000,
                isClosable: true,
            });
        }
    };
    const upsertCalendarInDb = async (index) => {
        try {
            console.log(calendarList?.[index], sub, ' calendarList?.[index], sub inside  upsertCalendarInDb');
            return (0, calendarDbHelper_1.upsertGoogleCalendarInDb)(client, calendarList?.[index], sub);
        }
        catch (e) {
            console.log(e, ' error creating calendar');
        }
    };
    const deleteCalendarInDb = async (index) => {
        try {
            await (0, calendarDbHelper_1.deleteGoogleCalendarInDb)(client, calendarList?.[index]?.id);
        }
        catch (e) {
            console.log(e, ' error deleting calendar');
        }
    };
    // delete event trigger in db
    const deleteEventTriggerInDb = async (index) => {
        try {
            await (0, calendar_integrationHelper_1.deleteEventTriggerByResourceId)(calendarList?.[index]?.id);
        }
        catch (e) {
            console.log(e, ' error deleting event trigger');
        }
    };
    const triggerCalendarSync = async (index) => {
        try {
            return (0, calendar_integrationHelper_1.triggerGoogleCalendarSync)(calendarIntegrations?.[0]?.id, calendarList?.[index]?.id, sub);
        }
        catch (e) {
            console.log(e, ' error triggering calendar sync');
        }
    };
    const addCalendarToSync = async (index) => {
        try {
            updateEnabledCalendarValue(index, true);
            await Promise.all([
                upsertCalendarInDb(index),
                triggerCalendarSync(index),
            ]);
            toast({
                status: 'success',
                title: 'Pick a Primary Calendar',
                description: 'Make sure to pick a primary calendar under settings or Atomic will not work properly ',
                duration: 9000,
                isClosable: true,
            });
        }
        catch (e) {
            console.log(e, ' error adding calendar to sync');
        }
    };
    const removeCalendarFromSync = async (index) => {
        try {
            updateEnabledCalendarValue(index, false);
            const eventsToDelete = await (0, OnBoardHelper2_1.listEventsForCalendar)(client, calendarList?.[index]?.id);
            await (0, AttendeeHelper_1.deleteAttendeesForEvents)(client, eventsToDelete.map(e => e.id));
            const conferenceIds = eventsToDelete.map(e => e.conferenceId)
                .filter(id => !!id);
            await (0, ReminderHelper_1.deleteRemindersForEvents)(client, eventsToDelete.map(e => e.id), sub);
            await Promise.all([
                deleteEventTriggerInDb(index),
                (0, calendarDbHelper_1.deleteEventsByCalendarId)(client, calendarList?.[index]?.id),
            ]);
            if (conferenceIds?.length > 0) {
                await (0, ConferenceHelper_1.deleteConferencesWithIds)(client, conferenceIds);
            }
            await deleteCalendarInDb(index);
            // await deleteCalendarWebhook(client, calendarList?.[index]?.id)
        }
        catch (e) {
            console.log(e, ' error removing calendar from sync');
        }
    };
    const addAllCalendarToSync = async () => {
        try {
            const promises = [];
            for (let i = 0; i < calendarList?.length; i++) {
                promises.push(addCalendarToSync(i));
            }
            await Promise.all(promises);
        }
        catch (e) {
            console.log(e, ' error adding calendar to sync all');
        }
    };
    const removeAllCalendarFromSync = async () => {
        try {
            const promises = [];
            for (let i = 0; i < calendarList?.length; i++) {
                promises.push(removeCalendarFromSync(i));
            }
            await Promise.all(promises);
        }
        catch (e) {
            console.log(e, ' error removing calendar from sync all');
        }
    };
    const updateEnabledValue = async (index, value) => {
        try {
            const newEnabledCalendars = enabledCalendars
                .slice(0, index)
                .concat([{ ...(enabledCalendars?.[index]), enabled: value }])
                .concat(enabledCalendars.slice(index + 1));
            setEnabledCalendars(newEnabledCalendars);
            if (value) {
                return addCalendarToSync(index);
            }
            else {
                return removeCalendarFromSync(index);
            }
        }
        catch (e) {
            console.log(e, ' error updating enabled value');
            toast({
                status: 'error',
                title: 'Error updating enabled value',
                description: e.toString(),
                duration: 9000,
                isClosable: true,
            });
        }
    };
    const updateAllCalendars = async (value) => {
        try {
            if (value) {
                setEnableAllCalendars(true);
                return addAllCalendarToSync();
            }
            setEnableAllCalendars(false);
            return removeAllCalendarFromSync();
        }
        catch (e) {
            console.log(e, ' error updating all calendars');
            toast({
                status: 'error',
                title: 'Error updating all calendars',
                description: e.toString(),
                duration: 9000,
                isClosable: true,
            });
        }
    };
    const navigateToSelectPrimaryCalendar = () => router.push('/Settings/UserSelectPrimaryCalendarForSettings');
    const renderItem = (item, index) => {
        return ((0, jsx_runtime_1.jsx)(CalendarCheckBox, { updateEnabledValue: updateEnabledValue, index: index, enabled: item?.enabled, name: item?.name, id: item?.id, calendars: calendars }, item?.id));
    };
    if (loading || existingCalendarLoading || integrationLoading || !disableLoading) {
        return ((0, jsx_runtime_1.jsx)(Box_1.default, { justifyContent: "center", alignItems: "center", style: { width: '100%' }, minHeight: "70vh", children: (0, jsx_runtime_1.jsx)(react_native_1.ActivityIndicator, { size: "large", color: theme_1.palette.white }) }));
    }
    return ((0, jsx_runtime_1.jsxs)("div", { className: "w-full h-full flex flex-col justify-center items-center", style: { minHeight: '70vh' }, children: [(0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-around", alignItems: "center", children: [(0, jsx_runtime_1.jsx)(Box_1.default, { children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "optionHeader", style: { color: theme_1.palette.darkGray }, children: "All Google Calendars" }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { children: (0, jsx_runtime_1.jsx)(Switch_1.default, { onValueChange: updateAllCalendars, checked: enableAllCalendars }) })] }), (0, jsx_runtime_1.jsx)(Box_1.default, { justifyContent: "center", alignItems: "center", width: "100%", children: enabledCalendars?.map((item, index) => renderItem(item, index)) }), (0, jsx_runtime_1.jsx)("div", { className: "flex justify-center items-center mt-3", children: (0, jsx_runtime_1.jsx)(Button_1.default, { onClick: navigateToSelectPrimaryCalendar, children: "Select Primary Calendar" }) }), (0, jsx_runtime_1.jsx)("div", { className: "flex justify-center items-center mt-3", children: (0, jsx_runtime_1.jsx)(Button_1.default, { onClick: () => props?.setIsGoogleCalendarList(false), children: "Close" }) })] }));
}
exports.default = UserGoogleCalendarList;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlckNhbGVuZGFyTGlzdC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIlVzZXJDYWxlbmRhckxpc3QudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7O0FBK0NBLGdEQXFDQzs7QUFwRkQsaUNBQTRFO0FBQzVFLCtDQUlxQjtBQUNyQiwyQ0FBeUM7QUFDekMsZ0VBQXdDO0FBRXhDLDRDQUEyQztBQUUzQyxpRUFBd0M7QUFDeEMsbUVBQTBDO0FBQzFDLDRDQUEwQztBQUsxQyx5RkFJaUQ7QUFFakQsMERBR21DO0FBS25DLHdFQUFnSTtBQUNoSSxzR0FBNkU7QUFDN0Usc0lBQTZHO0FBQzdHLGdFQUFtRTtBQUNuRSwwRUFBZ0Y7QUFDaEYsMEVBQWdGO0FBQ2hGLGdGQUFvRjtBQUNwRix3Q0FBdUM7QUFDdkMsb0RBQWlEO0FBQ2pELGdFQUF1QztBQUV2Qyx3RUFBOEM7QUFDOUMseURBQXFEO0FBQ3JELDhFQUFxRDtBQUU5QyxLQUFLLFVBQVUsa0JBQWtCLENBQUMsRUFBRSxHQUFHLEVBQUUsR0FBRyxFQUFpRDtJQUNoRywwRkFBMEY7SUFDMUYsc0NBQXNDO0lBQ3RDLHlFQUF5RTtJQUN6RSwwQkFBZSxDQUFDLElBQUksQ0FBQyxJQUFBLDZCQUFhLEdBQUUsQ0FBQyxDQUFBO0lBQ3JDLElBQUksT0FBTyxDQUFBO0lBQ1gsSUFBSSxDQUFDO1FBQ0QsT0FBTyxHQUFHLE1BQU0saUJBQU8sQ0FBQyxVQUFVLENBQUMsR0FBRyxFQUFFLEdBQUcsRUFBRTtZQUN6Qyw2QkFBNkIsRUFBRSxLQUFLO2dCQUNoQyxPQUFPLEVBQUUsQ0FBQTtZQUNiLENBQUM7U0FDSixDQUFDLENBQUE7SUFDTixDQUFDO0lBQUMsT0FBTyxHQUFRLEVBQUUsQ0FBQztRQUNoQixJQUFJLEdBQUcsQ0FBQyxJQUFJLEtBQUssaUJBQU8sQ0FBQyxLQUFLLENBQUMsaUJBQWlCLEVBQUUsQ0FBQztZQUMvQyxPQUFPLEVBQUUsS0FBSyxFQUFFLEVBQUUsZUFBZSxFQUFFLGVBQWUsRUFB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S0FBSyxFQUFDLGNBQWMsRUFBQyxjQUFjLEVBQUMsVUFBVSxFQUFDLFFBQVEsYUFDdEUsdUJBQUMsYUFBRyxjQUNBLHVCQUFDLGNBQUksSUFBQyxPQUFPLEVBQUMsY0FBYyxFQUFDLEtBQUssRUFBRSxFQUFFLEtBQUssRUFBRSxlQUFPLENBQUMsUUFBUSxFQUFFLHFDQUV4RCxHQUNMLEVBQ04sdUJBQUMsYUFBRyxjQUNBLHVCQUFDLGdCQUFPLElBQ0osYUFBYSxFQUFFLGtCQUFrQixFQUNqQyxPQUFPLEVBQUUsa0JBQWtCLEdBQzdCLEdBQ0EsSUFDSixFQUNOLHVCQUFDLGFBQUcsSUFBQyxjQUFjLEVBQUMsUUFBUSxFQUFDLFVBQVUsRUFBQyxRQUFRLEVBQUMsS0FBSyxFQUFDLE1BQU0sWUFDNUQsZ0JBQWdCLEVBQUUsR0FBRyxDQUFDLENBQUMsSUFBSSxFQUFFLEtBQUssRUFBRSxFQUFFLENBQUMsVUFBVSxDQUFDLElBQUksRUFBRSxLQUFLLENBQUMsQ0FBQyxHQUMxRCxFQUNOLGdDQUFLLFNBQVMsRUFBQyx1Q0FBdUMsWUFDbEQsdUJBQUMsZ0JBQU0sSUFBQyxPQUFPLEVBQUUsK0JBQStCLHdDQUV2QyxHQUNQLEVBQ04sZ0NBQUssU0FBUyxFQUFDLHVDQUF1QyxZQUNsRCx1QkFBQyxnQkFBTSxJQUFDLE9BQU8sRUFBRSxHQUFHLEVBQUUsQ0FBQyxLQUFLLEVBQUUsdUJBQXVCLENBQUMsS0FBSyxDQUFDLHNCQUVuRCxHQUNQLElBQ0osQ0FDVCxDQUFBO0FBQ0wsQ0FBQztBQUVELGtCQUFlLHNCQUFzQixDQUFBIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IFJlYWN0LCB7IHVzZVN0YXRlLCB1c2VFZmZlY3QsIFNldFN0YXRlQWN0aW9uLCBEaXNwYXRjaCB9IGZyb20gJ3JlYWN0J1xuaW1wb3J0IHtcbiAgICBBY3Rpdml0eUluZGljYXRvcixcbiAgRmxhdExpc3QsXG4gIHVzZUNvbG9yU2NoZW1lLFxufSBmcm9tICdyZWFjdC1uYXRpdmUnXG5pbXBvcnQgeyB1c2VRdWVyeSB9IGZyb20gJ0BhcG9sbG8vY2xpZW50J1xuaW1wb3J0IFN3aXRjaDEgZnJvbSAnQGNvbXBvbmVudHMvU3dpdGNoJ1xuXG5pbXBvcnQgeyB1c2VUb2FzdCB9IGZyb20gJ0BjaGFrcmEtdWkvcmVhY3QnXG5cbmltcG9ydCBCb3ggZnJvbSAnQGNvbXBvbmVudHMvY29tbW9uL0JveCdcbmltcG9ydCBUZXh0IGZyb20gJ0Bjb21wb25lbnRzL2NvbW1vbi9UZXh0J1xuaW1wb3J0IHsgcGFsZXR0ZSB9IGZyb20gJ0BsaWIvdGhlbWUvdGhlbWUnXG5cbmltcG9ydCB7IENhbGVuZGFySW50ZWdyYXRpb25UeXBlIH0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvQ2FsZW5kYXJfSW50ZWdyYXRpb25UeXBlJ1xuaW1wb3J0IHsgQ2FsZW5kYXJUeXBlIH0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvQ2FsZW5kYXJUeXBlJ1xuXG5pbXBvcnQge1xuICB0cmlnZ2VyR29vZ2xlQ2FsZW5kYXJTeW5jLFxuICBsaXN0R29vZ2xlQ2FsZW5kYXJzLFxuICBkZWxldGVFdmVudFRyaWdnZXJCeVJlc291cmNlSWQsXG59IGZyb20gJ0BsaWIvU2V0dGluZ3MvY2FsZW5kYXJfaW50ZWdyYXRpb25IZWxwZXInXG4gXG5pbXBvcnQge1xuICAgZ29vZ2xlQ2FsZW5kYXJOYW1lLFxuICAgZ29vZ2xlUmVzb3VyY2VOYW1lLFxufSBmcm9tICdAbGliL2NhbGVuZGFyTGliL2NvbnN0YW50cydcblxuXG5pbXBvcnQgeyBDYWxlbmRhckxpc3RJdGVtUmVzcG9uc2VUeXBlIH0gZnJvbSAnQGxpYi9jYWxlbmRhckxpYi90eXBlcydcbmltcG9ydCB7IGVuYWJsZWRDYWxlbmRhclR5cGUgfSBmcm9tICdAbGliL1NldHRpbmdzL3R5cGVzJ1xuaW1wb3J0IHsgZGVsZXRlRXZlbnRzQnlDYWxlbmRhcklkLCBkZWxldGVHb29nbGVDYWxlbmRhckluRGIsIHVwc2VydEdvb2dsZUNhbGVuZGFySW5EYiB9IGZyb20gJ0BsaWIvY2FsZW5kYXJMaWIvY2FsZW5kYXJEYkhlbHBlcidcbmltcG9ydCBnZXRDYWxlbmRhcldpdGhSZXNvdXJjZSBmcm9tICdAbGliL2Fwb2xsby9ncWwvZ2V0Q2FsZW5kYXJXaXRoUmVzb3VyY2UnXG5pbXBvcnQgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5UmVzb3VyY2VBbmROYW1lIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9nZXRDYWxlbmRhckludGVncmF0aW9uQnlSZXNvdXJjZUFuZE5hbWUnXG5pbXBvcnQgeyBsaXN0RXZlbnRzRm9yQ2FsZW5kYXIgfSBmcm9tICdAbGliL09uQm9hcmQvT25Cb2FyZEhlbHBlcjInXG5pbXBvcnQgeyBkZWxldGVBdHRlbmRlZXNGb3JFdmVudHMgfSBmcm9tICdAbGliL0NhbGVuZGFyL0F0dGVuZGVlL0F0dGVuZGVlSGVscGVyJ1xuaW1wb3J0IHsgZGVsZXRlUmVtaW5kZXJzRm9yRXZlbnRzIH0gZnJvbSAnQGxpYi9DYWxlbmRhci9SZW1pbmRlci9SZW1pbmRlckhlbHBlcidcbmltcG9ydCB7IGRlbGV0ZUNvbmZlcmVuY2VzV2l0aElkcyB9IGZyb20gJ0BsaWIvQ2FsZW5kYXIvQ29uZmVyZW5jZS9Db25mZXJlbmNlSGVscGVyJ1xuaW1wb3J0IHsgdXNlUm91dGVyIH0gZnJvbSAnbmV4dC9yb3V0ZXInXG5pbXBvcnQgeyB1c2VBcHBDb250ZXh0IH0gZnJvbSAnQGxpYi91c2VyLWNvbnRleHQnXG5pbXBvcnQgQnV0dG9uIGZyb20gJ0Bjb21wb25lbnRzL0J1dHRvbidcbmltcG9ydCB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCBzdXBlcnRva2Vuc05vZGUgZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZSdcbmltcG9ydCB7IGJhY2tlbmRDb25maWcgfSBmcm9tICdAY29uZmlnL2JhY2tlbmRDb25maWcnXG5pbXBvcnQgU2Vzc2lvbiBmcm9tICdzdXBlcnRva2Vucy1ub2RlL3JlY2lwZS9zZXNzaW9uJ1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0U2VydmVyU2lkZVByb3BzKHsgcmVxLCByZXMgfTogeyByZXE6IE5leHRBcGlSZXF1ZXN0LCByZXM6IE5leHRBcGlSZXNwb25zZSB9KSB7XG4gICAgLy8gTm90aWNlIGhvdyB0aGUgc2VydmVyIHVzZXMgYEFQSWAgZnJvbSBgd2l0aFNTUkNvbnRleHRgLCBpbnN0ZWFkIG9mIHRoZSB0b3AtbGV2ZWwgYEFQSWAuXG4gICAgLy8gY29uc3QgU1NSID0gd2l0aFNTUkNvbnRleHQoeyByZXEgfSlcbiAgICAvLyB0aGlzIHJ1bnMgb24gdGhlIGJhY2tlbmQsIHNvIHdlIG11c3QgY2FsbCBpbml0IG9uIHN1cGVydG9rZW5zLW5vZGUgU0RLXG4gICAgc3VwZXJ0b2tlbnNOb2RlLmluaXQoYmFja2VuZENvbmZpZygpKVxuICAgIGxldCBzZXNzaW9uXG4gICAgdHJ5IHtcbiAgICAgICAgc2Vzc2lvbiA9IGF3YWl0IFNlc3Npb24uZ2V0U2Vzc2lvbihyZXEsIHJlcywge1xuICAgICAgICAgICAgb3ZlcnJpZGVHbG9iYWxDbGFpbVZhbGlkYXRvcnM6IGFzeW5jIGZ1bmN0aW9uICgpIHtcbiAgICAgICAgICAgICAgICByZXR1cm4gW11cbiAgICAgICAgICAgIH0sXG4gICAgICAgIH0pXG4gICAgfSBjYXRjaCAoZXJyOiBhbnkpIHtcbiAgICAgICAgaWYgKGVyci50eXBlID09PSBTZXNzaW9uLkVycm9yLlRSWV9SRUZSRVNIX1RPS0VOKSB7XG4gICAgICAgICAgICByZXR1cm4geyBwcm9wczogeyBmcm9tU3VwZXJ0b2tlbnM6ICduZWVkcy1yZWZyZXNoJyB9IH1cbiAgICAgICAgfSBlbHNlIGlmIChlcnIudHlwZSA9PT0gU2Vzc2lvbi5FcnJvci5VTkFVVEhPUklTRUQpIHtcbiAgICAgICAgICAgIC8vIHRoaXMgd2lsbCBmb3JjZSB0aGUgZnJvbnRlbmQgdG8gdHJ5IGFuZCByZWZyZXNoIHdoaWNoIHdpbGwgZmFpbFxuICAgICAgICAgICAgLy8gY2xlYXJpbmcgYWxsIGNvb2tpZXMgYW5kIHJlZGlyZWN0aW5nIHRoZSB1c2VyIHRvIHRoZSBsb2dpbiBzY3JlZW4uXG4gICAgICAgICAgICByZXR1cm4geyBwcm9wczogeyBmcm9tU3VwZXJ0b2tlbnM6ICduZWVkcy1yZWZyZXNoJyB9IH1cbiAgICAgICAgfVxuICAgICAgICB0aHJvdyBlcnJcbiAgICB9XG5cbiAgICBpZiAoIXNlc3Npb24/LmdldFVzZXJJZCgpKSB7XG4gICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICByZWRpcmVjdDoge1xuICAgICAgICAgICAgICAgIGRlc3RpbmF0aW9uOiAnL1VzZXIvTG9naW4vVXNlckxvZ2luJyxcbiAgICAgICAgICAgICAgICBwZXJtYW5lbnQ6IGZhbHNlLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgfVxuICAgIH1cblxuICAgIHJldHVybiB7XG4gICAgICAgIHByb3BzOiB7XG4gICAgICAgIHN1Yjogc2Vzc2lvbi5nZXRVc2VySWQoKSxcbiAgICAgICAgfVxuICAgIH1cbn1cblxudHlwZSBDaGVja0JveFByb3BzVHlwZSA9IHtcbiAgdXBkYXRlRW5hYmxlZFZhbHVlOiAoaW5kZXg6IG51bWJlciwgdmFsdWU6IGJvb2xlYW4sIGlkOiBzdHJpbmcpID0+IFByb21pc2U8YW55PixcbiAgaW5kZXg6IG51bWJlcixcbiAgZW5hYmxlZDogYm9vbGVhbixcbiAgbmFtZTogc3RyaW5nLFxuLy8gICBkYXJrOiBib29sZWFuLFxuICAgIGlkOiBzdHJpbmcsXG4gIGNhbGVuZGFyczogQ2FsZW5kYXJUeXBlW10sXG59XG5cbnR5cGUgUmVuZGVySXRlbVR5cGUgPSB7XG4gIGl0ZW06IGVuYWJsZWRDYWxlbmRhclR5cGUsXG4gIGluZGV4OiBudW1iZXIsXG59XG5mdW5jdGlvbiBDYWxlbmRhckNoZWNrQm94KHByb3BzOiBDaGVja0JveFByb3BzVHlwZSkge1xuICBjb25zdCB7XG4gICAgZW5hYmxlZDogb2xkRW5hYmxlZCxcbiAgICB1cGRhdGVFbmFibGVkVmFsdWUsXG4gICAgaW5kZXgsXG4gICAgbmFtZSxcblxuICAgIGlkLFxuICAgIGNhbGVuZGFycyxcbiAgfSA9IHByb3BzXG4gIGNvbnN0IFtlbmFibGVkLCBzZXRFbmFibGVkXSA9IHVzZVN0YXRlPGJvb2xlYW4+KG9sZEVuYWJsZWQpXG5cbiAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICAgICAgKGFzeW5jICgpID0+IHtcbiAgICAgICAgICAgIHRyeSB7XG5cbiAgICAgICAgICAgICAgICBjb25zdCBpbmRleCA9IGNhbGVuZGFycy5maW5kSW5kZXgoaSA9PiAoaT8uaWQgPT09IGlkKSlcbiAgICAgICAgICAgICAgICBpZiAoaW5kZXggIT09IC0xKSB7XG4gICAgICAgICAgICAgICAgICAgIHNldEVuYWJsZWQodHJ1ZSlcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgICAgICAgICAgY29uc29sZS5sb2coZSwgJyBlcnJvciBpbiBjYWxlbmRhciBjaGVja2JveCcpXG4gICAgICAgICAgICB9XG4gICAgICAgIH0pKClcbiAgICB9LCBbY2FsZW5kYXJzLCBjYWxlbmRhcnM/Lmxlbmd0aCwgaWRdKVxuXG4gIGNvbnN0IHVwZGF0ZUVuYWJsZWQgPSAodmFsdWU6IGJvb2xlYW4pID0+IHtcbiAgICBzZXRFbmFibGVkKHZhbHVlKVxuICAgIHVwZGF0ZUVuYWJsZWRWYWx1ZShpbmRleCwgdmFsdWUsIGlkKVxuICB9XG5cbiAgcmV0dXJuIChcbiAgICAgPGRpdiBjbGFzc05hbWU9XCJmbGV4IGp1c3RpZnktYmV0d2VlbiBpdGVtcy1jZW50ZXIgc206dy0xLzMgdy05LzEyXCI+XG4gICAgICAgIDxCb3g+XG4gICAgICAgICAgPFRleHQgdmFyaWFudD1cIm9wdGlvbkhlYWRlclwiIHN0eWxlPXt7IGNvbG9yOiBwYWxldHRlLmRhcmtHcmF5IH19PlxuICAgICAgICAgICAge25hbWV9XG4gICAgICAgICAgPC9UZXh0PlxuICAgICAgICA8L0JveD5cbiAgICAgICAgPEJveD5cbiAgICAgICAgICA8U3dpdGNoMVxuICAgICAgICAgICAgb25WYWx1ZUNoYW5nZT17dXBkYXRlRW5hYmxlZH1cbiAgICAgICAgICAgIGNoZWNrZWQ9e2VuYWJsZWR9XG4gICAgICAgICAgLz5cbiAgICAgICAgPC9Cb3g+XG4gIFxuICAgICAgPC9kaXY+XG4gIClcbn1cblxudHlwZSBQcm9wcyA9IHtcbiAgICBzZXRJc0dvb2dsZUNhbGVuZGFyTGlzdDogRGlzcGF0Y2g8U2V0U3RhdGVBY3Rpb248Ym9vbGVhbj4+XG4gICAgdG9rZW46IHN0cmluZyxcbn1cbmZ1bmN0aW9uIFVzZXJHb29nbGVDYWxlbmRhckxpc3QocHJvcHM6IFByb3BzKSB7XG4gICAgY29uc3Qgcm91dGVyID0gdXNlUm91dGVyKClcbiAgICBjb25zdCB7IHN1YiwgY2xpZW50IH0gPSB1c2VBcHBDb250ZXh0KClcbiAgIFxuXG4gICAgY29uc3QgW2NhbGVuZGFyTGlzdCwgc2V0Q2FsZW5kYXJMaXN0XSA9IHVzZVN0YXRlPENhbGVuZGFyTGlzdEl0ZW1SZXNwb25zZVR5cGVbXT4oW10pXG4gICAgY29uc3QgW2xvYWRpbmcsIHNldExvYWRpbmddID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gICAgLy8gY29uc3QgW2ludGVncmF0aW9uLCBzZXRJbnRlZ3JhdGlvbl0gPSB1c2VTdGF0ZTxDYWxlbmRhckludGVncmF0aW9uVHlwZT4oKVxuICAgIC8vIGNvbnN0IFtjYWxlbmRhcnMsIHNldENhbGVuZGFyc10gPSB1c2VTdGF0ZTxDYWxlbmRhclR5cGVbXT4oW10pXG4gICAgY29uc3QgW2VuYWJsZWRDYWxlbmRhcnMsIHNldEVuYWJsZWRDYWxlbmRhcnNdID0gdXNlU3RhdGU8ZW5hYmxlZENhbGVuZGFyVHlwZVtdPihbXSlcbiAgICBjb25zdCBbZW5hYmxlQWxsQ2FsZW5kYXJzLCBzZXRFbmFibGVBbGxDYWxlbmRhcnNdID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gICAgY29uc3QgW2Rpc2FibGVMb2FkaW5nLCBzZXREaXNhYmxlTG9hZGluZ10gPSB1c2VTdGF0ZTxib29sZWFuPihmYWxzZSlcbiAgICBcbiAgICBjb25zdCB0b2FzdCA9IHVzZVRvYXN0KClcbiAgICBjb25zdCB0b2tlbiA9IHByb3BzPy50b2tlblxuXG4gICAgY29uc29sZS5sb2codG9rZW4sICcgdG9rZW4gaW5zaWRlIFVzZXJWaWV3R29vZ2xlQ2FsZW5kYXJMaXN0JylcblxuICAgIGNvbnN0IHsgbG9hZGluZzogZXhpc3RpbmdDYWxlbmRhckxvYWRpbmcsIGVycm9yOiBleGlzdGluZ0NhbGVuZGFyRXJyb3IsIGRhdGEgfSA9IHVzZVF1ZXJ5PHsgQ2FsZW5kYXI6IENhbGVuZGFyVHlwZVtdIH0+KGdldENhbGVuZGFyV2l0aFJlc291cmNlLCB7XG4gICAgICAgIHZhcmlhYmxlczogeyB1c2VySWQ6IHN1YiwgcmVzb3VyY2U6IGdvb2dsZVJlc291cmNlTmFtZSB9LFxuICAgIH0pXG5cbiAgICBjb25zdCB7IGxvYWRpbmc6IGludGVncmF0aW9uTG9hZGluZywgZXJyb3I6IGludGVncmF0aW9uRXJyb3IsIGRhdGE6IGludGVncmF0aW9uRGF0YSB9ID0gdXNlUXVlcnk8eyBDYWxlbmRhcl9JbnRlZ3JhdGlvbjogQ2FsZW5kYXJJbnRlZ3JhdGlvblR5cGVbXSB9PihnZXRDYWxlbmRhckludGVncmF0aW9uQnlSZXNvdXJjZUFuZE5hbWUsIHtcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICBuYW1lOiBnb29nbGVDYWxlbmRhck5hbWUsXG4gICAgICAgICAgICByZXNvdXJjZTogZ29vZ2xlUmVzb3VyY2VOYW1lLFxuICAgICAgICAgICAgdXNlcklkOiBzdWIsXG4gICAgICAgIH1cbiAgICB9KVxuXG4gICAgY29uc3QgY2FsZW5kYXJzID0gZGF0YT8uQ2FsZW5kYXJcbiAgICBjb25zdCBjYWxlbmRhckludGVncmF0aW9ucyA9IGludGVncmF0aW9uRGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb25cblxuICAgIC8vIHNldCBlbmFibGVkQ2FsZW5kYXJzXG4gICAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICAgICAgaWYgKCF0b2tlbikgcmV0dXJuXG4gICAgICAgIChhc3luYyAoKSA9PiB7XG4gICAgICAgICAgICB0cnkge1xuICAgICAgICAgICAgICAgIHNldExvYWRpbmcodHJ1ZSlcbiAgICAgICAgICAgICAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgbGlzdEdvb2dsZUNhbGVuZGFycyh0b2tlbilcbiAgICAgICAgICAgICAgICBjb25zb2xlLmxvZyhyZXN1bHRzLCAnIHJlc3VsdHMgZnJvbSBsaXN0R29vZ2xlQ2FsZW5kYXJzJylcbiAgICAgICAgICAgICAgICBjb25zdCBleGlzdGluZ0VuYWJsZWRDYWxlbmRhcnMgPSByZXN1bHRzLm1hcChjYWxlbmRhciA9PiB7XG4gICAgICAgICAgICAgICAgICAgIGNvbnN0IGNhbGVuZGFySWQgPSBjYWxlbmRhci5pZFxuICAgICAgICAgICAgICAgICAgICBjb25zdCBjYWxlbmRhck5hbWUgPSBjYWxlbmRhci5zdW1tYXJ5XG4gICAgICAgICAgICAgICAgICAgIGNvbnN0IGNhbGVuZGFySW5kZXggPSBjYWxlbmRhcnM/LmZpbmRJbmRleChjID0+IGMuaWQgPT09IGNhbGVuZGFySWQpXG4gICAgICAgICAgICAgICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICAgICAgICAgICAgICBpZDogY2FsZW5kYXJJZCxcbiAgICAgICAgICAgICAgICAgICAgICAgIG5hbWU6IGNhbGVuZGFyTmFtZSxcbiAgICAgICAgICAgICAgICAgICAgICAgIGVuYWJsZWQ6IChjYWxlbmRhckluZGV4ID4gLTEpLFxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfSlcbiAgICAgICAgICAgICAgICBzZXRDYWxlbmRhckxpc3QocmVzdWx0cylcbiAgICAgICAgICAgICAgICBzZXRFbmFibGVkQ2FsZW5kYXJzKGV4aXN0aW5nRW5hYmxlZENhbGVuZGFycylcbiAgICAgICAgICAgICAgICBzZXRMb2FkaW5nKGZhbHNlKVxuICAgICAgICAgICAgICAgIHNldERpc2FibGVMb2FkaW5nKHRydWUpXG4gICAgICAgICAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgICAgICAgICAgY29uc29sZS5sb2coZSwgJyBlcnJvciBnZXR0aW5nIGNhbGVuZGFycycpXG4gICAgICAgICAgICAgICAgc2V0TG9hZGluZyhmYWxzZSlcbiAgICAgICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgICAgICAgICAgdGl0bGU6ICdFcnJvciBnZXR0aW5nIGNhbGVuZGFycycsXG4gICAgICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiBlLnRvU3RyaW5nKCksXG4gICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAgICAgc2V0RGlzYWJsZUxvYWRpbmcodHJ1ZSlcbiAgICAgICAgICAgIH1cbiAgICAgICAgfSkoKVxuICAgIH0sIFt0b2tlbiwgY2FsZW5kYXJzPy5sZW5ndGgsIGNhbGVuZGFycywgdG9hc3RdKVxuXG4gICAgLy8gY29uc3QgZGFyayA9IHVzZUNvbG9yU2NoZW1lKCkgPT09ICdkYXJrJ1xuICAgIGNvbnN0IHVwZGF0ZUVuYWJsZWRDYWxlbmRhclZhbHVlID0gYXN5bmMgKGluZGV4OiBudW1iZXIsIHZhbHVlOiBib29sZWFuKSA9PiB7XG4gICAgICAgIHRyeSB7XG4gICAgICAgICAgICBjb25zdCBuZXdFbmFibGVkQ2FsZW5kYXJzID0gZW5hYmxlZENhbGVuZGFycy5tYXAoKGMsIGlkeCkgPT4ge1xuICAgICAgICAgICAgICAgIGlmIChpZHggPT09IGluZGV4KSB7XG4gICAgICAgICAgICAgICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICAgICAgICAgICAgICAuLi5jLFxuICAgICAgICAgICAgICAgICAgICAgICAgZW5hYmxlZDogdmFsdWUsXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgcmV0dXJuIGNcbiAgICAgICAgICAgIH0pXG4gICAgICAgICAgICBzZXRFbmFibGVkQ2FsZW5kYXJzKG5ld0VuYWJsZWRDYWxlbmRhcnMpXG4gICAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKGUsICcgZXJyb3IgdXBkYXRpbmcgZW5hYmxlZCB2YWx1ZScpXG4gICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgc3RhdHVzOiAnZXJyb3InLFxuICAgICAgICAgICAgICAgIHRpdGxlOiAnRXJyb3IgdXBkYXRpbmcgZW5hYmxlZCB2YWx1ZScsXG4gICAgICAgICAgICAgICAgZGVzY3JpcHRpb246IGUudG9TdHJpbmcoKSxcbiAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICAgICAgfSlcbiAgICAgICAgfVxuICAgIH1cbiAgICBjb25zdCB1cHNlcnRDYWxlbmRhckluRGIgPSBhc3luYyAoaW5kZXg6IG51bWJlcikgPT4ge1xuICAgICAgICB0cnkge1xuICAgICAgICAgICAgY29uc29sZS5sb2coY2FsZW5kYXJMaXN0Py5baW5kZXhdLCBzdWIsICcgY2FsZW5kYXJMaXN0Py5baW5kZXhdLCBzdWIgaW5zaWRlICB1cHNlcnRDYWxlbmRhckluRGInKVxuICAgICAgICAgICAgcmV0dXJuIHVwc2VydEdvb2dsZUNhbGVuZGFySW5EYihcbiAgICAgICAgICAgICAgICBjbGllbnQsXG4gICAgICAgICAgICAgICAgY2FsZW5kYXJMaXN0Py5baW5kZXhdLFxuICAgICAgICAgICAgICAgIHN1YixcbiAgICAgICAgICAgIClcbiAgICAgICAgfSBjYXRjaCAoZSkge1xuICAgICAgICAgICAgY29uc29sZS5sb2coZSwgJyBlcnJvciBjcmVhdGluZyBjYWxlbmRhcicpXG4gICAgICAgIH1cbiAgICB9XG4gICAgY29uc3QgZGVsZXRlQ2FsZW5kYXJJbkRiID0gYXN5bmMgKGluZGV4OiBudW1iZXIpID0+IHtcbiAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgIGF3YWl0IGRlbGV0ZUdvb2dsZUNhbGVuZGFySW5EYihjbGllbnQsIGNhbGVuZGFyTGlzdD8uW2luZGV4XT8uaWQpXG4gICAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKGUsICcgZXJyb3IgZGVsZXRpbmcgY2FsZW5kYXInKVxuICAgICAgICB9XG4gICAgfVxuXG4gICAgLy8gZGVsZXRlIGV2ZW50IHRyaWdnZXIgaW4gZGJcbiAgICBjb25zdCBkZWxldGVFdmVudFRyaWdnZXJJbkRiID0gYXN5bmMgKGluZGV4OiBudW1iZXIpID0+IHtcbiAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgIGF3YWl0IGRlbGV0ZUV2ZW50VHJpZ2dlckJ5UmVzb3VyY2VJZChjYWxlbmRhckxpc3Q/LltpbmRleF0/LmlkKVxuICAgICAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZyhlLCAnIGVycm9yIGRlbGV0aW5nIGV2ZW50IHRyaWdnZXInKVxuICAgICAgICB9XG4gICAgfVxuICAgIFxuICAgIGNvbnN0IHRyaWdnZXJDYWxlbmRhclN5bmMgPSBhc3luYyAoXG4gICAgICAgIGluZGV4OiBudW1iZXIsXG4gICAgKSA9PiB7XG4gICAgICAgIHRyeSB7XG4gICAgICAgICAgICByZXR1cm4gdHJpZ2dlckdvb2dsZUNhbGVuZGFyU3luYyhjYWxlbmRhckludGVncmF0aW9ucz8uWzBdPy5pZCwgY2FsZW5kYXJMaXN0Py5baW5kZXhdPy5pZCwgc3ViKVxuICAgICAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZyhlLCAnIGVycm9yIHRyaWdnZXJpbmcgY2FsZW5kYXIgc3luYycpXG4gICAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCBhZGRDYWxlbmRhclRvU3luYyA9IGFzeW5jIChpbmRleDogbnVtYmVyKSA9PiB7XG4gICAgICAgIHRyeSB7XG4gICAgICAgICAgICB1cGRhdGVFbmFibGVkQ2FsZW5kYXJWYWx1ZShpbmRleCwgdHJ1ZSlcbiAgICAgICAgICAgIGF3YWl0IFByb21pc2UuYWxsKFtcbiAgICAgICAgICAgICAgICB1cHNlcnRDYWxlbmRhckluRGIoaW5kZXgpLFxuICAgICAgICAgICAgICAgIHRyaWdnZXJDYWxlbmRhclN5bmMoaW5kZXgpLFxuICAgICAgICAgICAgXSlcblxuICAgICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgICAgICBzdGF0dXM6ICdzdWNjZXNzJyxcbiAgICAgICAgICAgICAgICB0aXRsZTogJ1BpY2sgYSBQcmltYXJ5IENhbGVuZGFyJyxcbiAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ01ha2Ugc3VyZSB0byBwaWNrIGEgcHJpbWFyeSBjYWxlbmRhciB1bmRlciBzZXR0aW5ncyBvciBBdG9taWMgd2lsbCBub3Qgd29yayBwcm9wZXJseSAnLFxuICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICAgICAgICB9KVxuICAgICAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZyhlLCAnIGVycm9yIGFkZGluZyBjYWxlbmRhciB0byBzeW5jJylcbiAgICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IHJlbW92ZUNhbGVuZGFyRnJvbVN5bmMgPSBhc3luYyAoaW5kZXg6IG51bWJlcikgPT4ge1xuICAgICAgICB0cnkge1xuICAgICAgICAgICAgdXBkYXRlRW5hYmxlZENhbGVuZGFyVmFsdWUoaW5kZXgsIGZhbHNlKVxuXG4gICAgICAgICAgICBjb25zdCBldmVudHNUb0RlbGV0ZSA9IGF3YWl0IGxpc3RFdmVudHNGb3JDYWxlbmRhcihjbGllbnQsIGNhbGVuZGFyTGlzdD8uW2luZGV4XT8uaWQpXG4gICAgICAgICAgICBhd2FpdCBkZWxldGVBdHRlbmRlZXNGb3JFdmVudHMoY2xpZW50LCBldmVudHNUb0RlbGV0ZS5tYXAoZSA9PiBlLmlkKSlcbiAgICAgICAgICAgIGNvbnN0IGNvbmZlcmVuY2VJZHMgPSBldmVudHNUb0RlbGV0ZS5tYXAoZSA9PiBlLmNvbmZlcmVuY2VJZClcbiAgICAgICAgICAgICAgICAuZmlsdGVyKGlkID0+ICEhaWQpXG5cbiAgICAgICAgICAgIGF3YWl0IGRlbGV0ZVJlbWluZGVyc0ZvckV2ZW50cyhjbGllbnQsIGV2ZW50c1RvRGVsZXRlLm1hcChlID0+IGUuaWQpLCBzdWIpXG4gICAgICAgICAgICBhd2FpdCBQcm9taXNlLmFsbChbXG4gICAgICAgICAgICAgICAgZGVsZXRlRXZlbnRUcmlnZ2VySW5EYihpbmRleCksXG4gICAgICAgICAgICAgICAgZGVsZXRlRXZlbnRzQnlDYWxlbmRhcklkKGNsaWVudCwgY2FsZW5kYXJMaXN0Py5baW5kZXhdPy5pZCksXG4gICAgICAgICAgICBdKVxuXG4gICAgICAgICAgICBpZiAoY29uZmVyZW5jZUlkcz8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgICAgIGF3YWl0IGRlbGV0ZUNvbmZlcmVuY2VzV2l0aElkcyhjbGllbnQsIGNvbmZlcmVuY2VJZHMpXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGF3YWl0IGRlbGV0ZUNhbGVuZGFySW5EYihpbmRleClcbiAgICAgICAgICAgIC8vIGF3YWl0IGRlbGV0ZUNhbGVuZGFyV2ViaG9vayhjbGllbnQsIGNhbGVuZGFyTGlzdD8uW2luZGV4XT8uaWQpXG4gICAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKGUsICcgZXJyb3IgcmVtb3ZpbmcgY2FsZW5kYXIgZnJvbSBzeW5jJylcbiAgICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IGFkZEFsbENhbGVuZGFyVG9TeW5jID0gYXN5bmMgKCkgPT4ge1xuICAgICAgICB0cnkge1xuICAgICAgICAgICAgY29uc3QgcHJvbWlzZXMgPSBbXVxuICAgICAgICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCBjYWxlbmRhckxpc3Q/Lmxlbmd0aDsgaSsrKSB7XG4gICAgICAgICAgICAgICAgcHJvbWlzZXMucHVzaChhZGRDYWxlbmRhclRvU3luYyhpKSlcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIGF3YWl0IFByb21pc2UuYWxsKHByb21pc2VzKVxuICAgICAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZyhlLCAnIGVycm9yIGFkZGluZyBjYWxlbmRhciB0byBzeW5jIGFsbCcpXG4gICAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCByZW1vdmVBbGxDYWxlbmRhckZyb21TeW5jID0gYXN5bmMgKCkgPT4ge1xuICAgICAgICB0cnkge1xuICAgICAgICAgICAgY29uc3QgcHJvbWlzZXMgPSBbXVxuICAgICAgICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCBjYWxlbmRhckxpc3Q/Lmxlbmd0aDsgaSsrKSB7XG4gICAgICAgICAgICAgICAgcHJvbWlzZXMucHVzaChyZW1vdmVDYWxlbmRhckZyb21TeW5jKGkpKVxuICAgICAgICAgICAgfVxuICAgICAgICAgICAgYXdhaXQgUHJvbWlzZS5hbGwocHJvbWlzZXMpXG4gICAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKGUsICcgZXJyb3IgcmVtb3ZpbmcgY2FsZW5kYXIgZnJvbSBzeW5jIGFsbCcpXG4gICAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCB1cGRhdGVFbmFibGVkVmFsdWUgPSBhc3luYyAoaW5kZXg6IG51bWJlciwgdmFsdWU6IGJvb2xlYW4pID0+IHtcbiAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgIFxuICAgICAgICAgICAgY29uc3QgbmV3RW5hYmxlZENhbGVuZGFycyA9IGVuYWJsZWRDYWxlbmRhcnNcbiAgICAgICAgICAgICAgICAuc2xpY2UoMCwgaW5kZXgpXG4gICAgICAgICAgICAgICAgLmNvbmNhdChbeyAuLi4oZW5hYmxlZENhbGVuZGFycz8uW2luZGV4XSksIGVuYWJsZWQ6IHZhbHVlIH1dKVxuICAgICAgICAgICAgICAgIC5jb25jYXQoZW5hYmxlZENhbGVuZGFycy5zbGljZShpbmRleCArIDEpKVxuXG4gICAgICAgICAgICBzZXRFbmFibGVkQ2FsZW5kYXJzKG5ld0VuYWJsZWRDYWxlbmRhcnMpXG4gICAgICAgICAgICBcbiAgICAgICAgICAgIGlmICh2YWx1ZSkge1xuICAgICAgICAgICAgICAgIHJldHVybiBhZGRDYWxlbmRhclRvU3luYyhpbmRleClcbiAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgcmV0dXJuIHJlbW92ZUNhbGVuZGFyRnJvbVN5bmMoaW5kZXgpXG4gICAgICAgICAgICB9XG4gICAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKGUsICcgZXJyb3IgdXBkYXRpbmcgZW5hYmxlZCB2YWx1ZScpXG4gICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgc3RhdHVzOiAnZXJyb3InLFxuICAgICAgICAgICAgICAgIHRpdGxlOiAnRXJyb3IgdXBkYXRpbmcgZW5hYmxlZCB2YWx1ZScsXG4gICAgICAgICAgICAgICAgZGVzY3JpcHRpb246IGUudG9TdHJpbmcoKSxcbiAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICAgICAgfSlcbiAgICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IHVwZGF0ZUFsbENhbGVuZGFycyA9IGFzeW5jICh2YWx1ZTogYm9vbGVhbikgPT4ge1xuICAgICAgICB0cnkge1xuICAgICAgICAgICAgaWYgKHZhbHVlKSB7XG4gICAgICAgICAgICAgICAgc2V0RW5hYmxlQWxsQ2FsZW5kYXJzKHRydWUpXG4gICAgICAgICAgICAgICAgcmV0dXJuIGFkZEFsbENhbGVuZGFyVG9TeW5jKClcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIHNldEVuYWJsZUFsbENhbGVuZGFycyhmYWxzZSlcbiAgICAgICAgICAgIHJldHVybiByZW1vdmVBbGxDYWxlbmRhckZyb21TeW5jKClcbiAgICAgICAgfSBjYXRjaCAoZSkge1xuICAgICAgICAgICAgY29uc29sZS5sb2coZSwgJyBlcnJvciB1cGRhdGluZyBhbGwgY2FsZW5kYXJzJylcbiAgICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgICAgICAgICAgdGl0bGU6ICdFcnJvciB1cGRhdGluZyBhbGwgY2FsZW5kYXJzJyxcbiAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogZS50b1N0cmluZygpLFxuICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICAgICAgICB9KVxuICAgICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgbmF2aWdhdGVUb1NlbGVjdFByaW1hcnlDYWxlbmRhciA9ICgpID0+IHJvdXRlci5wdXNoKCcvU2V0dGluZ3MvVXNlclNlbGVjdFByaW1hcnlDYWxlbmRhckZvclNldHRpbmdzJylcblxuICAgIGNvbnN0IHJlbmRlckl0ZW0gPSAoaXRlbTogZW5hYmxlZENhbGVuZGFyVHlwZSwgaW5kZXg6IG51bWJlcikgPT4ge1xuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPENhbGVuZGFyQ2hlY2tCb3hcbiAgICAgICAgICAgICAgICB1cGRhdGVFbmFibGVkVmFsdWU9e3VwZGF0ZUVuYWJsZWRWYWx1ZX1cbiAgICAgICAgICAgICAgICBpbmRleD17aW5kZXh9XG4gICAgICAgICAgICAgICAgZW5hYmxlZD17aXRlbT8uZW5hYmxlZH1cbiAgICAgICAgICAgICAgICBuYW1lPXtpdGVtPy5uYW1lfVxuICAgICAgICAgICAgICAgIGlkPXtpdGVtPy5pZH1cbiAgICAgICAgICAgICAgICBjYWxlbmRhcnM9e2NhbGVuZGFyc31cbiAgICAgICAgICAgICAgICBrZXk9e2l0ZW0/LmlkfVxuICAgICAgICAgICAgLz5cbiAgICAgICAgKVxuICAgIH1cblxuICAgIGlmIChsb2FkaW5nIHx8IGV4aXN0aW5nQ2FsZW5kYXJMb2FkaW5nIHx8IGludGVncmF0aW9uTG9hZGluZyB8fCAhZGlzYWJsZUxvYWRpbmcpIHtcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgPEJveCBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiBzdHlsZT17eyB3aWR0aDogJzEwMCUnfX0gbWluSGVpZ2h0PVwiNzB2aFwiPlxuICAgICAgICAgICAgPEFjdGl2aXR5SW5kaWNhdG9yIHNpemU9XCJsYXJnZVwiIGNvbG9yPXtwYWxldHRlLndoaXRlfSAvPlxuICAgICAgICA8L0JveD5cbiAgICAgICAgKVxuICAgIH1cblxuICAgIHJldHVybiAoXG4gICAgICAgIDxkaXYgY2xhc3NOYW1lPVwidy1mdWxsIGgtZnVsbCBmbGV4IGZsZXgtY29sIGp1c3RpZnktY2VudGVyIGl0ZW1zLWNlbnRlclwiIHN0eWxlPXt7IG1pbkhlaWdodDogJzcwdmgnfX0+XG4gICAgICAgICAgICA8Qm94IGZsZXhEaXJlY3Rpb249XCJyb3dcIiBqdXN0aWZ5Q29udGVudD1cInNwYWNlLWFyb3VuZFwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiA+XG4gICAgICAgICAgICAgICAgPEJveD5cbiAgICAgICAgICAgICAgICAgICAgPFRleHQgdmFyaWFudD1cIm9wdGlvbkhlYWRlclwiIHN0eWxlPXt7IGNvbG9yOiBwYWxldHRlLmRhcmtHcmF5IH19PlxuICAgICAgICAgICAgICAgICAgICBBbGwgR29vZ2xlIENhbGVuZGFyc1xuICAgICAgICAgICAgICAgICAgICA8L1RleHQ+XG4gICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgPEJveD5cbiAgICAgICAgICAgICAgICAgICAgPFN3aXRjaDFcbiAgICAgICAgICAgICAgICAgICAgICAgIG9uVmFsdWVDaGFuZ2U9e3VwZGF0ZUFsbENhbGVuZGFyc31cbiAgICAgICAgICAgICAgICAgICAgICAgIGNoZWNrZWQ9e2VuYWJsZUFsbENhbGVuZGFyc31cbiAgICAgICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgPEJveCBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiB3aWR0aD1cIjEwMCVcIj5cbiAgICAgICAgICAgIHtlbmFibGVkQ2FsZW5kYXJzPy5tYXAoKGl0ZW0sIGluZGV4KSA9PiByZW5kZXJJdGVtKGl0ZW0sIGluZGV4KSl9XG4gICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZmxleCBqdXN0aWZ5LWNlbnRlciBpdGVtcy1jZW50ZXIgbXQtM1wiPlxuICAgICAgICAgICAgICAgIDxCdXR0b24gb25DbGljaz17bmF2aWdhdGVUb1NlbGVjdFByaW1hcnlDYWxlbmRhcn0+XG4gICAgICAgICAgICAgICAgICAgIFNlbGVjdCBQcmltYXJ5IENhbGVuZGFyXG4gICAgICAgICAgICAgICAgPC9CdXR0b24+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZmxleCBqdXN0aWZ5LWNlbnRlciBpdGVtcy1jZW50ZXIgbXQtM1wiPlxuICAgICAgICAgICAgICAgIDxCdXR0b24gb25DbGljaz17KCkgPT4gcHJvcHM/LnNldElzR29vZ2xlQ2FsZW5kYXJMaXN0KGZhbHNlKX0+XG4gICAgICAgICAgICAgICAgICAgIENsb3NlXG4gICAgICAgICAgICAgICAgPC9CdXR0b24+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgPC9kaXY+XG4gICAgKVxufVxuXG5leHBvcnQgZGVmYXVsdCBVc2VyR29vZ2xlQ2FsZW5kYXJMaXN0XG4iXX0=