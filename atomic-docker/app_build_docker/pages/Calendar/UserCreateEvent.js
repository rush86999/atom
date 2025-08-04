"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getServerSideProps = getServerSideProps;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const Wizard_1 = __importDefault(require("@components/Wizard"));
const react_2 = require("@chakra-ui/react");
const date_utils_1 = require("@lib/date-utils");
const Box_1 = __importDefault(require("@components/common/Box"));
const Text_1 = __importDefault(require("@components/common/Text"));
const RegularCard_1 = __importDefault(require("@components/RegularCard"));
const Button_1 = __importDefault(require("@components/Button"));
const CategoryHelper_1 = require("@lib/Category/CategoryHelper");
const zoomMeetingHelper_1 = require("@lib/zoom/zoomMeetingHelper");
const googleCalendarHelper_1 = require("@lib/calendarLib/googleCalendarHelper");
const UserCreateCalendarHelper_1 = require("@lib/Calendar/UserCreateCalendarHelper");
const CreateEventAttendees_1 = __importDefault(require("@pages/Calendar/CreateEventWizard/CreateEventAttendees"));
const CreateEventBaseStep_1 = __importDefault(require("@pages/Calendar/CreateEventWizard/CreateEventBaseStep"));
const CreateEventBaseStep2_1 = __importDefault(require("@pages/Calendar/CreateEventWizard/CreateEventBaseStep2"));
const CreateEventRecurStepAlt_1 = __importDefault(require("@pages/Calendar/CreateEventWizard/CreateEventRecurStepAlt"));
const CreateEventVirtualMeet_1 = __importDefault(require("@pages/Calendar/CreateEventWizard/CreateEventVirtualMeet"));
const CreateEventVisibilityAndAlarmsStep_1 = __importDefault(require("@pages/Calendar/CreateEventWizard/CreateEventVisibilityAndAlarmsStep"));
const CreateEventAddCategories_1 = __importDefault(require("@pages/Calendar/CreateEventWizard/CreateEventAddCategories"));
const getGlobalPrimaryCalendar_1 = __importDefault(require("@lib/apollo/gql/getGlobalPrimaryCalendar"));
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const backendConfig_1 = require("../../config/backendConfig");
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
function UserCreateEvent(props) {
    const client = props?.client;
    const [tags, setTags] = (0, react_1.useState)([]);
    const [selectedCategories, setSelectedCategories] = (0, react_1.useState)([]);
    const [title, setTitle] = (0, react_1.useState)();
    const [allDay, setAllDay] = (0, react_1.useState)(false);
    const [isRecurring, setIsRecurring] = (0, react_1.useState)(false);
    const [recurringEndDate, setRecurringEndDate] = (0, react_1.useState)(new Date());
    const [frequency, setFrequency] = (0, react_1.useState)();
    const [interval, setInterval] = (0, react_1.useState)();
    const [alarms, setAlarms] = (0, react_1.useState)([]);
    const [notes, setNotes] = (0, react_1.useState)();
    const [location, setLocation] = (0, react_1.useState)();
    const [isZoomAvailable, setIsZoomAvailable] = (0, react_1.useState)(false);
    const [isGoogleMeetAvailable, setIsGoogleMeetAvailable] = (0, react_1.useState)(false);
    const [zoomMeet, setZoomMeet] = (0, react_1.useState)(false);
    const [googleMeet, setGoogleMeet] = (0, react_1.useState)(false);
    const [zoomPrivateMeeting, setZoomPrivateMeeting] = (0, react_1.useState)(false);
    const [attendees, setAttendees] = (0, react_1.useState)([]);
    const [visibility, setVisibility] = (0, react_1.useState)('default');
    const [isAttendees, setIsAttendees] = (0, react_1.useState)(false);
    const [activeIndex, setActiveIndex] = (0, react_1.useState)(0);
    const [completedStep, setCompletedStep] = (0, react_1.useState)();
    const [selectedCalendarId, setSelectedCalendarId] = (0, react_1.useState)();
    const [calendar, setCalendar] = (0, react_1.useState)();
    const [isBreak, setIsBreak] = (0, react_1.useState)(false);
    const [byWeekDay, setByWeekDay] = (0, react_1.useState)([]);
    const [startDate, setStartDate] = (0, react_1.useState)(props?.start);
    const [endDate, setEndDate] = (0, react_1.useState)(props?.end);
    const userId = props?.sub;
    const closeCreateEvent = props?.closeCreateEvent;
    const toast = (0, react_2.useToast)();
    (0, react_1.useEffect)(() => {
        (async () => {
            try {
                if (!userId || !client) {
                    return;
                }
                const results = await (0, CategoryHelper_1.listUserCategories)(client, userId);
                if (!results?.[0]?.id) {
                    console.log(' no categories available');
                    return;
                }
                setTags(results);
            }
            catch (e) {
                console.log(e, ' unable to get categories');
            }
        })();
    }, [client, userId]);
    (0, react_1.useEffect)(() => {
        (async () => {
            if (!userId || !client) {
                return;
            }
            const isAvailable = await (0, zoomMeetingHelper_1.zoomAvailable)(client, userId);
            if (isAvailable) {
                setIsZoomAvailable(true);
            }
        })();
    }, [client, userId]);
    (0, react_1.useEffect)(() => {
        (async () => {
            if (!userId || !client) {
                return;
            }
            const isAvailable = await (0, googleCalendarHelper_1.googleMeetAvailable)(client, userId);
            if (isAvailable) {
                setIsGoogleMeetAvailable(isAvailable);
            }
        })();
    }, [client, userId]);
    (0, react_1.useEffect)(() => {
        (async () => {
            if (!userId || !client) {
                return;
            }
            const result = (await client.query({
                query: getGlobalPrimaryCalendar_1.default,
                variables: {
                    userId,
                },
            })).data?.Calendar?.[0];
            if (!result?.id) {
                console.log(' no primary calendar available');
                return;
            }
            setSelectedCalendarId(result?.id);
            setCalendar(result);
        })();
    }, [client, userId]);
    const createEventForUser = async () => {
        try {
            if (!userId || !client) {
                return;
            }
            await (0, UserCreateCalendarHelper_1.createNewEvent)((0, date_utils_1.dayjs)(startDate).format(), (0, date_utils_1.dayjs)(endDate).format(), userId, client, selectedCalendarId, selectedCategories?.map(category => category.id), title, allDay, (0, date_utils_1.dayjs)(recurringEndDate).format(), frequency, parseInt(interval, 10), alarms, notes, location ? { title: location } : undefined, false, false, false, true, undefined, undefined, undefined, false, date_utils_1.dayjs.tz.guess(), undefined, undefined, undefined, undefined, undefined, undefined, zoomMeet, googleMeet, 'scheduled', undefined, zoomPrivateMeeting, attendees, undefined, undefined, undefined, undefined, title, 'opaque', visibility, undefined, undefined, undefined, calendar?.colorId, date_utils_1.dayjs.tz.guess(), calendar?.backgroundColor, calendar?.foregroundColor, alarms?.length > 0 ? false : true, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, isBreak, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, true, undefined, undefined, alarms?.length > 0, undefined, true, undefined, true, undefined, undefined, undefined, undefined, undefined, undefined, date_utils_1.dayjs.duration((0, date_utils_1.dayjs)(endDate).diff((0, date_utils_1.dayjs)(startDate))).asMinutes(), undefined, undefined, 'create', undefined, byWeekDay, 1);
            toast({
                status: 'success',
                title: 'Event Created',
                description: 'Event created successfully',
                duration: 9000,
                isClosable: true,
            });
            closeCreateEvent();
        }
        catch (e) {
            console.log(e, ' createEventForUser');
            toast({
                status: 'error',
                title: 'Something went wrong',
                description: 'Event was not created',
                duration: 9000,
                isClosable: true,
            });
        }
    };
    const onActiveIndexChanged = (index) => setActiveIndex(index);
    const goToPrevStep = () => {
        const prevActiveIndex = activeIndex;
        const newActiveIndex = prevActiveIndex === 0 ? 0 : prevActiveIndex - 1;
        setActiveIndex(newActiveIndex);
    };
    const renderPrevButton = () => {
        if (activeIndex === 0) {
            return (0, jsx_runtime_1.jsx)(Box_1.default, { pt: { phone: 'm', tablet: 's' } });
        }
        return ((0, jsx_runtime_1.jsx)(Box_1.default, { p: { phone: 's', tablet: 'm' }, children: (0, jsx_runtime_1.jsx)(Button_1.default, { onClick: goToPrevStep, children: "Back" }) }));
    };
    const goToNextStep = () => {
        const prevActiveIndex = activeIndex;
        const prevCompletedStep = completedStep;
        if (!isRecurring && isAttendees) {
            let newActiveIndex = prevActiveIndex + 1;
            if (prevActiveIndex === 1) {
                newActiveIndex = 3;
            }
            if (prevActiveIndex === 5) {
                if (tags?.length === 0) {
                    toast({
                        status: 'info',
                        title: 'No categories available',
                        description: 'Please add at least one category in your settings in order to add to your event',
                        duration: 9000,
                        isClosable: true,
                    });
                    newActiveIndex = 7;
                }
            }
            if (prevActiveIndex === 7) {
                return;
            }
            if (!prevCompletedStep || (prevCompletedStep < prevActiveIndex)) {
                const newCompletedStep = prevActiveIndex;
                setCompletedStep(newCompletedStep);
            }
            if (newActiveIndex !== prevActiveIndex) {
                return setActiveIndex(newActiveIndex);
            }
        }
        if (!isAttendees && isRecurring) {
            let newActiveIndex = prevActiveIndex + 1;
            if (prevActiveIndex === 2) {
                newActiveIndex = 5;
            }
            if (prevActiveIndex === 5) {
                if (tags?.length === 0) {
                    toast({
                        status: 'info',
                        title: 'No categories available',
                        description: 'Please add at least one category in your settings in order to add to your event',
                        duration: 9000,
                        isClosable: true,
                    });
                    newActiveIndex = 7;
                }
            }
            if (prevActiveIndex === 7) {
                return;
            }
            if (!prevCompletedStep || (prevCompletedStep < prevActiveIndex)) {
                const newCompletedStep = prevActiveIndex;
                setCompletedStep(newCompletedStep);
            }
            if (newActiveIndex !== prevActiveIndex) {
                return setActiveIndex(newActiveIndex);
            }
        }
        if (!isAttendees && !isRecurring) {
            let newActiveIndex = prevActiveIndex + 1;
            if (prevActiveIndex === 1) {
                newActiveIndex = 5;
            }
            if (prevActiveIndex === 5) {
                if (tags?.length === 0) {
                    toast({
                        status: 'info',
                        title: 'No categories available',
                        description: 'Please add at least one category in your settings in order to add to your event',
                        duration: 9000,
                        isClosable: true,
                    });
                    newActiveIndex = 7;
                }
            }
            if (prevActiveIndex === 7) {
                return;
            }
            if (!prevCompletedStep || (prevCompletedStep < prevActiveIndex)) {
                const newCompletedStep = prevActiveIndex;
                setCompletedStep(newCompletedStep);
            }
            if (newActiveIndex !== prevActiveIndex) {
                return setActiveIndex(newActiveIndex);
            }
        }
        if (prevActiveIndex === 7) {
            return;
        }
        let newActiveIndex = prevActiveIndex + 1;
        if (prevActiveIndex === 5) {
            if (tags?.length === 0) {
                toast({
                    status: 'info',
                    title: 'No categories available',
                    description: 'Please add at least one category in your settings in order to add to your event',
                    duration: 9000,
                    isClosable: true,
                });
                newActiveIndex = 7;
            }
        }
        if (!prevCompletedStep || (prevCompletedStep < prevActiveIndex)) {
            const newCompletedStep = prevActiveIndex;
            setCompletedStep(newCompletedStep);
        }
        if (newActiveIndex !== prevActiveIndex) {
            setActiveIndex(newActiveIndex);
        }
    };
    const renderNextButton = () => {
        if (activeIndex === 7) {
            return (0, jsx_runtime_1.jsx)(Box_1.default, { pt: { phone: 'm', tablet: 's' } });
        }
        return ((0, jsx_runtime_1.jsx)(Box_1.default, { p: { phone: 's', tablet: 'm' }, children: (0, jsx_runtime_1.jsx)(Button_1.default, { onClick: goToNextStep, children: "Next" }) }));
    };
    const renderCurrentStep = () => {
        switch (activeIndex) {
            case 0:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(CreateEventBaseStep_1.default, { title: title, notes: notes, location: location, setParentTitle: setTitle, setParentNotes: setNotes, setParentLocation: setLocation, startDate: startDate, endDate: endDate, setParentEndDate: setEndDate, setParentStartDate: setStartDate }), (0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [(0, jsx_runtime_1.jsx)(Box_1.default, {}), renderNextButton()] })] }));
            case 1:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(CreateEventBaseStep2_1.default, { allDay: allDay, isRecurring: isRecurring, isAttendees: isAttendees, isBreak: isBreak, setParentAllDay: setAllDay, setParentIsRecurring: setIsRecurring, setParentIsAttendees: setIsAttendees, setParentIsBreak: setIsBreak }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [renderPrevButton(), renderNextButton()] })] }));
            case 2:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(CreateEventRecurStepAlt_1.default, { recurringEndDate: recurringEndDate, setParentRecurringEndDate: setRecurringEndDate, frequency: frequency, setParentFrequency: setFrequency, interval: interval, setParentInterval: setInterval, byWeekDay: byWeekDay, setParentWeekDay: setByWeekDay }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [renderPrevButton(), renderNextButton()] })] }));
            case 3:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(CreateEventVirtualMeet_1.default, { isZoomAvailable: isZoomAvailable, isGoogleMeetAvailable: isGoogleMeetAvailable, zoomMeet: zoomMeet, googleMeet: googleMeet, setParentZoomMeet: setZoomMeet, setParentGoogleMeet: setGoogleMeet, zoomPrivateMeeting: zoomPrivateMeeting, setParentZoomPrivateMeeting: setZoomPrivateMeeting }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [renderPrevButton(), renderNextButton()] })] }));
            case 4:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(CreateEventAttendees_1.default, { attendees: attendees, setParentAttendees: setAttendees, userId: userId, client: client }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [renderPrevButton(), renderNextButton()] })] }));
            case 5:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(CreateEventVisibilityAndAlarmsStep_1.default, { alarms: alarms, setParentAlarms: setAlarms, visibility: visibility, setParentVisibility: setVisibility, userId: userId }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [renderPrevButton(), renderNextButton()] })] }));
            case 6:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(CreateEventAddCategories_1.default, { categories: tags, setParentSelectedCategories: setSelectedCategories, selectedCategories: selectedCategories }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [renderPrevButton(), renderNextButton()] })] }));
            case 7:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, style: { width: '100%' }, p: { phone: 's', tablet: 'm' }, justifyContent: "center", alignItems: "center", minHeight: "65vh", maxHeight: "65vh", children: [(0, jsx_runtime_1.jsx)(Box_1.default, { p: { phone: 'm', tablet: 'l' }, children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "subheaderNormal", children: "Create Event" }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { pt: { phone: 'm', tablet: 'l' }, children: (0, jsx_runtime_1.jsx)(Button_1.default, { onClick: createEventForUser, children: "Create" }) })] }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", style: { width: '75%' }, children: [renderPrevButton(), (0, jsx_runtime_1.jsx)(Box_1.default, {})] })] }));
            default:
                return ((0, jsx_runtime_1.jsx)(Box_1.default, { justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsx)(RegularCard_1.default, { children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "header", children: "Oops... something went wrong" }) }) }));
        }
    };
    return ((0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, justifyContent: "center", alignItems: "center", style: { height: '100%' }, children: [(0, jsx_runtime_1.jsx)(Wizard_1.default, { items: [
                    {
                        index: 0,
                        label: 'Set Base',
                    },
                    {
                        index: 1,
                        label: 'Continue Base',
                    },
                    {
                        index: 2,
                        label: 'Select Recurrence',
                    },
                    {
                        index: 3,
                        label: 'Select Virtual Meet',
                    },
                    {
                        index: 4,
                        label: 'Select Event Attendees',
                    },
                    {
                        index: 5,
                        label: 'Set Visibility And Alarms',
                    },
                    {
                        index: 6,
                        label: 'Select Categories for Event',
                    },
                    {
                        index: 7,
                        label: 'Create Event',
                    },
                ], completed: completedStep, activeIndex: activeIndex }), renderCurrentStep(), (0, jsx_runtime_1.jsx)(Box_1.default, { children: (0, jsx_runtime_1.jsx)("button", { className: "btn btn-link no-underline hover:no-underline", onClick: closeCreateEvent, children: "Close" }) })] }));
}
exports.default = UserCreateEvent;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlckNyZWF0ZUV2ZW50LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiVXNlckNyZWF0ZUV2ZW50LnRzeCJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQWdEQSxnREFxQ0M7O0FBckZELGlDQUFrRDtBQUNsRCxnRUFBdUM7QUFFdkMsNENBQTJDO0FBQzNDLGdEQUF1QztBQUN2QyxpRUFBd0M7QUFDeEMsbUVBQTBDO0FBQzFDLDBFQUFpRDtBQUNqRCxnRUFBdUM7QUFLdkMsaUVBRXFDO0FBRXJDLG1FQUVvQztBQUNwQyxnRkFFOEM7QUFHOUMscUZBQXVFO0FBRXZFLGtIQUF5RjtBQUN6RixnSEFBdUY7QUFDdkYsa0hBQXlGO0FBQ3pGLHdIQUE0RjtBQUM1RixzSEFBNkY7QUFDN0YsOElBQXFIO0FBQ3JILDBIQUFpRztBQUlqRyx3R0FBK0U7QUFPL0Usd0VBQThDO0FBQzlDLDhEQUEwRDtBQUMxRCw4RUFBcUQ7QUFFOUMsS0FBSyxVQUFVLGtCQUFrQixDQUFDLEVBQUUsR0FBRyxFQUFFLEdBQUcsRUFBaUQ7SUFDbEcsMEZBQTBGO0lBQzFGLHNDQUFzQztJQUN0Qyx5RUFBeUU7SUFDekUsMEJBQWUsQ0FBQyxJQUFJLENBQUMsSUFBQSw2QkFBYSxHQUFFLENBQUMsQ0FBQTtJQUNyQyxJQUFJLE9BQU8sQ0FBQTtJQUNYLElBQUksQ0FBQztRQUNILE9BQU8sR0FBRyxNQUFNLGlCQUFPLENBQUMsVUFBVSxDQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUU7WUFDM0MsNkJBQTZCLEVBQUUsS0FBSztnQkFDbEMsT0FBTyxFQUFFLENBQUE7WUFDWCxDQUFDO1NBQ0YsQ0FBQyxDQUFBO0lBQ0osQ0FBQztJQUFDLE9BQU8sR0FBUSxFQUFFLENBQUM7UUFDbEIsSUFBSSxHQUFHLENBQUMsSUFBSSxLQUFLLGlCQUFPLENBQUMsS0FBSyxDQUFDLGlCQUFpQixFQUFFLENBQUM7WUFDakQsT0FBTyxFQUFFLEtBQUssRUFBRSxFQUFFLGVBQWUsRUFBRSxlQUFlLEVBQUUs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QUFJLEVBQUUsQ0FBQyxFQUFFLGNBQWMsRUFBQyxRQUFRLEVBQUMsVUFBVSxFQUFDLFFBQVEsRUFBQyxLQUFLLEVBQUUsRUFBRSxNQUFNLEVBQUUsTUFBTSxFQUFDLGFBQ2hGLHVCQUFDLGdCQUFNLElBQ0wsS0FBSyxFQUFFO29CQUNIO3dCQUNJLEtBQUssRUFBRSxDQUFDO3dCQUNSLEtBQUssRUFBRSxVQUFVO3FCQUNwQjtvQkFDRDt3QkFDSSxLQUFLLEVBQUUsQ0FBQzt3QkFDUixLQUFLLEVBQUUsZUFBZTtxQkFDekI7b0JBQ0Q7d0JBQ0ksS0FBSyxFQUFFLENBQUM7d0JBQ1IsS0FBSyxFQUFFLG1CQUFtQjtxQkFDN0I7b0JBQ0M7d0JBQ0UsS0FBSyxFQUFFLENBQUM7d0JBQ1IsS0FBSyxFQUFFLHFCQUFxQjtxQkFDL0I7b0JBQ0M7d0JBQ0UsS0FBSyxFQUFFLENBQUM7d0JBQ1IsS0FBSyxFQUFFLHdCQUF3QjtxQkFDbEM7b0JBQ0M7d0JBQ0UsS0FBSyxFQUFFLENBQUM7d0JBQ1IsS0FBSyxFQUFFLDJCQUEyQjtxQkFDckM7b0JBQ0Q7d0JBQ0ksS0FBSyxFQUFFLENBQUM7d0JBQ1IsS0FBSyxFQUFFLDZCQUE2QjtxQkFDdkM7b0JBQ0Q7d0JBQ0ksS0FBSyxFQUFFLENBQUM7d0JBQ1IsS0FBSyxFQUFFLGNBQWM7cUJBQ3hCO2lCQUVKLEVBRUQsU0FBUyxFQUFFLGFBQWEsRUFDeEIsV0FBVyxFQUFFLFdBQVcsR0FDeEIsRUFDRCxpQkFBaUIsRUFBRSxFQUNwQix1QkFBQyxhQUFHLGNBQ0YsbUNBQVEsU0FBUyxFQUFDLDhDQUE4QyxFQUFDLE9BQU8sRUFBRSxnQkFBZ0Isc0JBRWpGLEdBQ0wsSUFDRixDQUNQLENBQUE7QUFFSCxDQUFDO0FBRUQsa0JBQWUsZUFBZSxDQUFBIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IFJlYWN0LCB7IHVzZVN0YXRlLCB1c2VFZmZlY3QgfSBmcm9tICdyZWFjdCdcbmltcG9ydCBXaXphcmQgZnJvbSAnQGNvbXBvbmVudHMvV2l6YXJkJ1xuXG5pbXBvcnQgeyB1c2VUb2FzdCB9IGZyb20gJ0BjaGFrcmEtdWkvcmVhY3QnXG5pbXBvcnQgeyBkYXlqcyB9IGZyb20gJ0BsaWIvZGF0ZS11dGlscydcbmltcG9ydCBCb3ggZnJvbSAnQGNvbXBvbmVudHMvY29tbW9uL0JveCdcbmltcG9ydCBUZXh0IGZyb20gJ0Bjb21wb25lbnRzL2NvbW1vbi9UZXh0J1xuaW1wb3J0IFJlZ3VsYXJDYXJkIGZyb20gJ0Bjb21wb25lbnRzL1JlZ3VsYXJDYXJkJ1xuaW1wb3J0IEJ1dHRvbiBmcm9tICdAY29tcG9uZW50cy9CdXR0b24nXG5cbmltcG9ydCB7XG4gIENhdGVnb3J5VHlwZVxufSBmcm9tICdAbGliL2RhdGFUeXBlcy9DYXRlZ29yeVR5cGUnXG5pbXBvcnQge1xuICBsaXN0VXNlckNhdGVnb3JpZXMsXG59IGZyb20gJ0BsaWIvQ2F0ZWdvcnkvQ2F0ZWdvcnlIZWxwZXInXG5cbmltcG9ydCB7XG4gIHpvb21BdmFpbGFibGVcbn0gZnJvbSAnQGxpYi96b29tL3pvb21NZWV0aW5nSGVscGVyJ1xuaW1wb3J0IHtcbiAgZ29vZ2xlTWVldEF2YWlsYWJsZSxcbn0gZnJvbSAnQGxpYi9jYWxlbmRhckxpYi9nb29nbGVDYWxlbmRhckhlbHBlcidcbmltcG9ydCB7IFBlcnNvbiwgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGUgfSBmcm9tICdAbGliL0NhbGVuZGFyL3R5cGVzJ1xuaW1wb3J0IHsgVmlzaWJpbGl0eVR5cGUgfSBmcm9tICdAbGliL2NhbGVuZGFyTGliL3R5cGVzJ1xuaW1wb3J0IHsgY3JlYXRlTmV3RXZlbnQgfSBmcm9tICdAbGliL0NhbGVuZGFyL1VzZXJDcmVhdGVDYWxlbmRhckhlbHBlcidcblxuaW1wb3J0IENyZWF0ZUV2ZW50QXR0ZW5kZWVzIGZyb20gJ0BwYWdlcy9DYWxlbmRhci9DcmVhdGVFdmVudFdpemFyZC9DcmVhdGVFdmVudEF0dGVuZGVlcydcbmltcG9ydCBDcmVhdGVFdmVudEJhc2VTdGVwIGZyb20gJ0BwYWdlcy9DYWxlbmRhci9DcmVhdGVFdmVudFdpemFyZC9DcmVhdGVFdmVudEJhc2VTdGVwJ1xuaW1wb3J0IENyZWF0ZUV2ZW50QmFzZVN0ZXAyIGZyb20gJ0BwYWdlcy9DYWxlbmRhci9DcmVhdGVFdmVudFdpemFyZC9DcmVhdGVFdmVudEJhc2VTdGVwMidcbmltcG9ydCBDcmVhdGVFdmVudFJlY3VyU3RlcCBmcm9tICdAcGFnZXMvQ2FsZW5kYXIvQ3JlYXRlRXZlbnRXaXphcmQvQ3JlYXRlRXZlbnRSZWN1clN0ZXBBbHQnXG5pbXBvcnQgQ3JlYXRlRXZlbnRWaXJ0dWFsTWVldCBmcm9tICdAcGFnZXMvQ2FsZW5kYXIvQ3JlYXRlRXZlbnRXaXphcmQvQ3JlYXRlRXZlbnRWaXJ0dWFsTWVldCdcbmltcG9ydCBDcmVhdGVFdmVudFZpc2liaWxpdHlBbmRBbGFybXNTdGVwIGZyb20gJ0BwYWdlcy9DYWxlbmRhci9DcmVhdGVFdmVudFdpemFyZC9DcmVhdGVFdmVudFZpc2liaWxpdHlBbmRBbGFybXNTdGVwJ1xuaW1wb3J0IENyZWF0ZUV2ZW50QWRkQ2F0ZWdvcmllcyBmcm9tICdAcGFnZXMvQ2FsZW5kYXIvQ3JlYXRlRXZlbnRXaXphcmQvQ3JlYXRlRXZlbnRBZGRDYXRlZ29yaWVzJ1xuXG5pbXBvcnQgeyBDYWxlbmRhclR5cGUgfSBmcm9tICdAbGliL2RhdGFUeXBlcy9DYWxlbmRhclR5cGUnXG5pbXBvcnQgeyBEYXkgfSBmcm9tICdAbGliL1NjaGVkdWxlL2NvbnN0YW50cydcbmltcG9ydCBnZXRHbG9iYWxQcmltYXJ5Q2FsZW5kYXIgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2dldEdsb2JhbFByaW1hcnlDYWxlbmRhcidcbmltcG9ydCB7IHVzZUFwcENvbnRleHQgfSBmcm9tICdAbGliL3VzZXItY29udGV4dCdcbmltcG9ydCB7IHVzZVJvdXRlciB9IGZyb20gJ25leHQvcm91dGVyJ1xuXG5pbXBvcnQgeyBTbG90SW5mbyB9IGZyb20gJ3JlYWN0LWJpZy1jYWxlbmRhcidcbmltcG9ydCB7IEFwb2xsb0NsaWVudCwgTm9ybWFsaXplZENhY2hlT2JqZWN0IH0gZnJvbSAnQGFwb2xsby9jbGllbnQnXG5pbXBvcnQgeyBOZXh0QXBpUmVxdWVzdCwgTmV4dEFwaVJlc3BvbnNlIH0gZnJvbSAnbmV4dCc7XG5pbXBvcnQgc3VwZXJ0b2tlbnNOb2RlIGZyb20gJ3N1cGVydG9rZW5zLW5vZGUnXG5pbXBvcnQgeyBiYWNrZW5kQ29uZmlnIH0gZnJvbSAnLi4vLi4vY29uZmlnL2JhY2tlbmRDb25maWcnXG5pbXBvcnQgU2Vzc2lvbiBmcm9tICdzdXBlcnRva2Vucy1ub2RlL3JlY2lwZS9zZXNzaW9uJ1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0U2VydmVyU2lkZVByb3BzKHsgcmVxLCByZXMgfTogeyByZXE6IE5leHRBcGlSZXF1ZXN0LCByZXM6IE5leHRBcGlSZXNwb25zZSB9KSB7XG4gIC8vIE5vdGljZSBob3cgdGhlIHNlcnZlciB1c2VzIGBBUElgIGZyb20gYHdpdGhTU1JDb250ZXh0YCwgaW5zdGVhZCBvZiB0aGUgdG9wLWxldmVsIGBBUElgLlxuICAvLyBjb25zdCBTU1IgPSB3aXRoU1NSQ29udGV4dCh7IHJlcSB9KVxuICAvLyB0aGlzIHJ1bnMgb24gdGhlIGJhY2tlbmQsIHNvIHdlIG11c3QgY2FsbCBpbml0IG9uIHN1cGVydG9rZW5zLW5vZGUgU0RLXG4gIHN1cGVydG9rZW5zTm9kZS5pbml0KGJhY2tlbmRDb25maWcoKSlcbiAgbGV0IHNlc3Npb25cbiAgdHJ5IHtcbiAgICBzZXNzaW9uID0gYXdhaXQgU2Vzc2lvbi5nZXRTZXNzaW9uKHJlcSwgcmVzLCB7XG4gICAgICBvdmVycmlkZUdsb2JhbENsYWltVmFsaWRhdG9yczogYXN5bmMgZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gW11cbiAgICAgIH0sXG4gICAgfSlcbiAgfSBjYXRjaCAoZXJyOiBhbnkpIHtcbiAgICBpZiAoZXJyLnR5cGUgPT09IFNlc3Npb24uRXJyb3IuVFJZX1JFRlJFU0hfVE9LRU4pIHtcbiAgICAgIHJldHVybiB7IHByb3BzOiB7IGZyb21TdXBlcnRva2VuczogJ25lZWRzLXJlZnJlc2gnIH0gfVxuICAgIH0gZWxzZSBpZiAoZXJyLnR5cGUgPT09IFNlc3Npb24uRXJyb3IuVU5BVVRIT1JJU0VEKSB7XG4gICAgICAvLyB0aGlzIHdpbGwgZm9yY2UgdGhlIGZyb250ZW5kIHRvIHRyeSBhbmQgcmVmcmVzaCB3aGljaCB3aWxsIGZhaWxcbiAgICAgIC8vIGNsZWFyaW5nIGFsbCBjb29raWVzIGFuZCByZWRpcmVjdGluZyB0aGUgdXNlciB0byB0aGUgbG9naW4gc2NyZWVuLlxuICAgICAgcmV0dXJuIHsgcHJvcHM6IHsgZnJvbVN1cGVydG9rZW5zOiAnbmVlZHMtcmVmcmVzaCcgfSB9XG4gICAgfVxuICAgIHRocm93IGVyclxuICB9XG5cbiAgaWYgKCFzZXNzaW9uPy5nZXRVc2VySWQoKSkge1xuICAgIHJldHVybiB7XG4gICAgICByZWRpcmVjdDoge1xuICAgICAgICBkZXN0aW5hdGlvbjogJy9Vc2VyL0xvZ2luL1VzZXJMb2dpbicsXG4gICAgICAgIHBlcm1hbmVudDogZmFsc2UsXG4gICAgICB9LFxuICAgIH1cbiAgfVxuXG4gIHJldHVybiB7XG4gICAgcHJvcHM6IHtcbiAgICAgIHN1Yjogc2Vzc2lvbi5nZXRVc2VySWQoKSxcbiAgICB9XG4gIH1cbn1cblxudHlwZSBQcm9wcyA9IHtcbiAgc3RhcnQ6IERhdGUsXG4gIGVuZDogRGF0ZSxcbiAgY2xvc2VDcmVhdGVFdmVudDogKCkgPT4gdm9pZCxcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgc3ViOiBzdHJpbmcsXG59XG5cbmZ1bmN0aW9uIFVzZXJDcmVhdGVFdmVudChwcm9wczogUHJvcHMpIHtcblxuXG4gIGNvbnN0IGNsaWVudCA9IHByb3BzPy5jbGllbnRcblxuICBjb25zdCBbdGFncywgc2V0VGFnc10gPSB1c2VTdGF0ZTxDYXRlZ29yeVR5cGVbXT4oW10pXG4gIGNvbnN0IFtzZWxlY3RlZENhdGVnb3JpZXMsIHNldFNlbGVjdGVkQ2F0ZWdvcmllc10gPSB1c2VTdGF0ZTxDYXRlZ29yeVR5cGVbXT4oW10pXG4gIGNvbnN0IFt0aXRsZSwgc2V0VGl0bGVdID0gdXNlU3RhdGU8c3RyaW5nPigpXG4gIGNvbnN0IFthbGxEYXksIHNldEFsbERheV0gPSB1c2VTdGF0ZTxib29sZWFuPihmYWxzZSlcbiAgY29uc3QgW2lzUmVjdXJyaW5nLCBzZXRJc1JlY3VycmluZ10gPSB1c2VTdGF0ZTxib29sZWFuPihmYWxzZSlcbiAgY29uc3QgW3JlY3VycmluZ0VuZERhdGUsIHNldFJlY3VycmluZ0VuZERhdGVdID0gdXNlU3RhdGU8RGF0ZT4obmV3IERhdGUoKSlcbiAgY29uc3QgW2ZyZXF1ZW5jeSwgc2V0RnJlcXVlbmN5XSA9IHVzZVN0YXRlPFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlPigpXG4gIGNvbnN0IFtpbnRlcnZhbCwgc2V0SW50ZXJ2YWxdID0gdXNlU3RhdGU8c3RyaW5nPigpXG4gIGNvbnN0IFthbGFybXMsIHNldEFsYXJtc10gPSB1c2VTdGF0ZTxudW1iZXJbXT4oW10pXG4gIGNvbnN0IFtub3Rlcywgc2V0Tm90ZXNdID0gdXNlU3RhdGU8c3RyaW5nPigpXG4gIGNvbnN0IFtsb2NhdGlvbiwgc2V0TG9jYXRpb25dID0gdXNlU3RhdGU8c3RyaW5nPigpXG4gIGNvbnN0IFtpc1pvb21BdmFpbGFibGUsIHNldElzWm9vbUF2YWlsYWJsZV0gPSB1c2VTdGF0ZTxib29sZWFuPihmYWxzZSlcbiAgY29uc3QgW2lzR29vZ2xlTWVldEF2YWlsYWJsZSwgc2V0SXNHb29nbGVNZWV0QXZhaWxhYmxlXSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKVxuICBjb25zdCBbem9vbU1lZXQsIHNldFpvb21NZWV0XSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKVxuICBjb25zdCBbZ29vZ2xlTWVldCwgc2V0R29vZ2xlTWVldF0gPSB1c2VTdGF0ZTxib29sZWFuPihmYWxzZSlcbiAgY29uc3QgW3pvb21Qcml2YXRlTWVldGluZywgc2V0Wm9vbVByaXZhdGVNZWV0aW5nXSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKVxuICBjb25zdCBbYXR0ZW5kZWVzLCBzZXRBdHRlbmRlZXNdID0gdXNlU3RhdGU8UGVyc29uW10+KFtdKVxuICBjb25zdCBbdmlzaWJpbGl0eSwgc2V0VmlzaWJpbGl0eV0gPSB1c2VTdGF0ZTxWaXNpYmlsaXR5VHlwZT4oJ2RlZmF1bHQnKVxuICBjb25zdCBbaXNBdHRlbmRlZXMsIHNldElzQXR0ZW5kZWVzXSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKVxuICBjb25zdCBbYWN0aXZlSW5kZXgsIHNldEFjdGl2ZUluZGV4XSA9IHVzZVN0YXRlPG51bWJlcj4oMClcbiAgY29uc3QgW2NvbXBsZXRlZFN0ZXAsIHNldENvbXBsZXRlZFN0ZXBdID0gdXNlU3RhdGU8bnVtYmVyIHwgdW5kZWZpbmVkPigpXG4gIGNvbnN0IFtzZWxlY3RlZENhbGVuZGFySWQsIHNldFNlbGVjdGVkQ2FsZW5kYXJJZF0gPSB1c2VTdGF0ZTxzdHJpbmc+KClcbiAgY29uc3QgW2NhbGVuZGFyLCBzZXRDYWxlbmRhcl0gPSB1c2VTdGF0ZTxDYWxlbmRhclR5cGU+KClcbiAgY29uc3QgW2lzQnJlYWssIHNldElzQnJlYWtdID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gIGNvbnN0IFtieVdlZWtEYXksIHNldEJ5V2Vla0RheV0gPSB1c2VTdGF0ZTxEYXlbXT4oW10pXG4gIGNvbnN0IFtzdGFydERhdGUsIHNldFN0YXJ0RGF0ZV0gPSB1c2VTdGF0ZTxEYXRlPihwcm9wcz8uc3RhcnQpXG4gIGNvbnN0IFtlbmREYXRlLCBzZXRFbmREYXRlXSA9IHVzZVN0YXRlPERhdGU+KHByb3BzPy5lbmQpXG5cbiAgY29uc3QgdXNlcklkID0gcHJvcHM/LnN1YlxuICBjb25zdCBjbG9zZUNyZWF0ZUV2ZW50ID0gcHJvcHM/LmNsb3NlQ3JlYXRlRXZlbnRcbiAgY29uc3QgdG9hc3QgPSB1c2VUb2FzdCgpXG4gIFxuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIChhc3luYygpID0+IHtcbiAgICAgIHRyeSB7XG4gICAgICAgIGlmICghdXNlcklkIHx8ICFjbGllbnQpIHtcbiAgICAgICAgICByZXR1cm5cbiAgICAgICAgfVxuICAgICAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgbGlzdFVzZXJDYXRlZ29yaWVzKGNsaWVudCwgdXNlcklkKVxuICAgICAgICBpZiAoIXJlc3VsdHM/LlswXT8uaWQpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZygnIG5vIGNhdGVnb3JpZXMgYXZhaWxhYmxlJylcbiAgICAgICAgICByZXR1cm5cbiAgICAgICAgfVxuICAgICAgICBzZXRUYWdzKHJlc3VsdHMpXG4gICAgICB9IGNhdGNoKGUpIHtcbiAgICAgICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGNhdGVnb3JpZXMnKVxuICAgICAgfVxuICAgIH0pKClcbiAgfSwgW2NsaWVudCwgdXNlcklkXSlcblxuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIChhc3luYyAoKSA9PiB7XG4gICAgICBpZiAoIXVzZXJJZCB8fCAhY2xpZW50KSB7XG4gICAgICAgIHJldHVyblxuICAgICAgfVxuICAgICAgY29uc3QgaXNBdmFpbGFibGUgPSBhd2FpdCB6b29tQXZhaWxhYmxlKGNsaWVudCwgdXNlcklkKVxuICAgICAgaWYgKGlzQXZhaWxhYmxlKSB7XG4gICAgICAgIHNldElzWm9vbUF2YWlsYWJsZSh0cnVlKVxuICAgICAgfVxuICAgIH0pKClcbiAgfSwgW2NsaWVudCwgdXNlcklkXSlcblxuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIChhc3luYyAoKSA9PiB7XG4gICAgICBpZiAoIXVzZXJJZCB8fCAhY2xpZW50KSB7XG4gICAgICAgIHJldHVyblxuICAgICAgfVxuICAgICAgY29uc3QgaXNBdmFpbGFibGUgPSBhd2FpdCBnb29nbGVNZWV0QXZhaWxhYmxlKGNsaWVudCwgdXNlcklkKVxuICAgICAgaWYgKGlzQXZhaWxhYmxlKSB7XG4gICAgICAgIHNldElzR29vZ2xlTWVldEF2YWlsYWJsZShpc0F2YWlsYWJsZSlcbiAgICAgIH1cbiAgICB9KSgpXG4gIH0sIFtjbGllbnQsIHVzZXJJZF0pXG5cbiAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICAoYXN5bmMgKCkgPT4geyAgXG4gICAgICBpZiAoIXVzZXJJZCB8fCAhY2xpZW50KSB7XG4gICAgICAgIHJldHVyblxuICAgICAgfVxuICAgICAgY29uc3QgcmVzdWx0ID0gKGF3YWl0IGNsaWVudC5xdWVyeTx7IENhbGVuZGFyOiBDYWxlbmRhclR5cGVbXSB9Pih7XG4gICAgICAgIHF1ZXJ5OiBnZXRHbG9iYWxQcmltYXJ5Q2FsZW5kYXIsIFxuICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgIH0sXG4gICAgICB9KSkuZGF0YT8uQ2FsZW5kYXI/LlswXVxuICAgICAgaWYgKCFyZXN1bHQ/LmlkKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKCcgbm8gcHJpbWFyeSBjYWxlbmRhciBhdmFpbGFibGUnKVxuICAgICAgICByZXR1cm5cbiAgICAgIH1cbiAgICAgIHNldFNlbGVjdGVkQ2FsZW5kYXJJZChyZXN1bHQ/LmlkKVxuICAgICAgc2V0Q2FsZW5kYXIocmVzdWx0KVxuICAgIH0pKClcbiAgfSwgW2NsaWVudCwgdXNlcklkXSlcbiAgY29uc3QgY3JlYXRlRXZlbnRGb3JVc2VyID0gYXN5bmMgKCkgPT4ge1xuICAgIHRyeSB7XG4gICAgICBpZiAoIXVzZXJJZCB8fCAhY2xpZW50KSB7XG4gICAgICAgIHJldHVyblxuICAgICAgfVxuICAgICAgYXdhaXQgY3JlYXRlTmV3RXZlbnQoXG4gICAgICAgIGRheWpzKHN0YXJ0RGF0ZSkuZm9ybWF0KCksXG4gICAgICAgIGRheWpzKGVuZERhdGUpLmZvcm1hdCgpLFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGNsaWVudCxcbiAgICAgICAgc2VsZWN0ZWRDYWxlbmRhcklkLFxuICAgICAgICBzZWxlY3RlZENhdGVnb3JpZXM/Lm1hcChjYXRlZ29yeSA9PiBjYXRlZ29yeS5pZCksXG4gICAgICAgIHRpdGxlLFxuICAgICAgICBhbGxEYXksXG4gICAgICAgIGRheWpzKHJlY3VycmluZ0VuZERhdGUpLmZvcm1hdCgpLFxuICAgICAgICBmcmVxdWVuY3ksXG4gICAgICAgcGFyc2VJbnQgKGludGVydmFsLCAxMCksXG4gICAgICAgIGFsYXJtcyxcbiAgICAgICAgbm90ZXMsXG4gICAgICAgIGxvY2F0aW9uID8geyB0aXRsZTogbG9jYXRpb24gfSA6IHVuZGVmaW5lZCxcbiAgICAgICAgZmFsc2UsXG4gICAgICAgIGZhbHNlLFxuICAgICAgICBmYWxzZSxcbiAgICAgICAgdHJ1ZSxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgZmFsc2UsXG4gICAgICAgIGRheWpzLnR6Lmd1ZXNzKCksXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHpvb21NZWV0LFxuICAgICAgICBnb29nbGVNZWV0LFxuICAgICAgICAnc2NoZWR1bGVkJyxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB6b29tUHJpdmF0ZU1lZXRpbmcsXG4gICAgICAgIGF0dGVuZGVlcyxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB0aXRsZSxcbiAgICAgICAgJ29wYXF1ZScsXG4gICAgICAgIHZpc2liaWxpdHksXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIGNhbGVuZGFyPy5jb2xvcklkLFxuICAgICAgICBkYXlqcy50ei5ndWVzcygpLFxuICAgICAgICBjYWxlbmRhcj8uYmFja2dyb3VuZENvbG9yLFxuICAgICAgICBjYWxlbmRhcj8uZm9yZWdyb3VuZENvbG9yLFxuICAgICAgICBhbGFybXM/Lmxlbmd0aCA+IDAgPyBmYWxzZSA6IHRydWUsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICBpc0JyZWFrLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdHJ1ZSxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIGFsYXJtcz8ubGVuZ3RoID4gMCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB0cnVlLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHRydWUsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIGRheWpzLmR1cmF0aW9uKGRheWpzKGVuZERhdGUpLmRpZmYoZGF5anMoc3RhcnREYXRlKSkpLmFzTWludXRlcygpLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgJ2NyZWF0ZScsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgYnlXZWVrRGF5LFxuICAgICAgICAxXG4gICAgICApXG5cbiAgICAgIHRvYXN0KHtcbiAgICAgICAgc3RhdHVzOiAnc3VjY2VzcycsXG4gICAgICAgIHRpdGxlOiAnRXZlbnQgQ3JlYXRlZCcsXG4gICAgICAgIGRlc2NyaXB0aW9uOiAnRXZlbnQgY3JlYXRlZCBzdWNjZXNzZnVsbHknLFxuICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZSxcbiAgICAgIH0pXG4gICAgICBjbG9zZUNyZWF0ZUV2ZW50KClcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICBjb25zb2xlLmxvZyhlLCAnIGNyZWF0ZUV2ZW50Rm9yVXNlcicpXG4gICAgICB0b2FzdCh7XG4gICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgdGl0bGU6ICdTb21ldGhpbmcgd2VudCB3cm9uZycsXG4gICAgICAgIGRlc2NyaXB0aW9uOiAnRXZlbnQgd2FzIG5vdCBjcmVhdGVkJyxcbiAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICB9KVxuICAgIH1cbiAgfVxuXG4gIGNvbnN0IG9uQWN0aXZlSW5kZXhDaGFuZ2VkID0gKGluZGV4OiBudW1iZXIpID0+IHNldEFjdGl2ZUluZGV4KGluZGV4KVxuXG4gIGNvbnN0IGdvVG9QcmV2U3RlcCA9ICgpID0+IHtcbiAgICBjb25zdCBwcmV2QWN0aXZlSW5kZXggPSBhY3RpdmVJbmRleFxuICAgIGNvbnN0IG5ld0FjdGl2ZUluZGV4ID0gcHJldkFjdGl2ZUluZGV4ID09PSAwID8gMCA6IHByZXZBY3RpdmVJbmRleCAtIDFcbiAgICBzZXRBY3RpdmVJbmRleChuZXdBY3RpdmVJbmRleClcbiAgfVxuXG4gIGNvbnN0IHJlbmRlclByZXZCdXR0b24gPSAoKSA9PiB7XG4gICAgaWYgKGFjdGl2ZUluZGV4ID09PSAwKSB7XG4gICAgICByZXR1cm4gPEJveCBwdD17eyBwaG9uZTogJ20nLCB0YWJsZXQ6ICdzJyB9fS8+XG4gICAgfVxuXG4gICAgcmV0dXJuIChcbiAgICA8Qm94IHA9e3sgcGhvbmU6ICdzJywgdGFibGV0OiAnbScgfX0+XG4gICAgICA8QnV0dG9uIG9uQ2xpY2s9e2dvVG9QcmV2U3RlcH0+XG4gICAgICAgIEJhY2tcbiAgICAgIDwvQnV0dG9uPlxuICAgIDwvQm94PlxuICApfVxuXG4gIGNvbnN0IGdvVG9OZXh0U3RlcCA9ICgpID0+IHtcbiAgICBjb25zdCBwcmV2QWN0aXZlSW5kZXggPSBhY3RpdmVJbmRleFxuICAgIGNvbnN0IHByZXZDb21wbGV0ZWRTdGVwID0gY29tcGxldGVkU3RlcFxuICAgIGlmICghaXNSZWN1cnJpbmcgJiYgaXNBdHRlbmRlZXMpIHtcbiAgICAgIGxldCBuZXdBY3RpdmVJbmRleCA9IHByZXZBY3RpdmVJbmRleCArIDFcblxuICAgICAgaWYgKHByZXZBY3RpdmVJbmRleCA9PT0gMSkge1xuICAgICAgICBuZXdBY3RpdmVJbmRleCA9IDNcbiAgICAgIH1cblxuICAgICAgaWYgKHByZXZBY3RpdmVJbmRleCA9PT0gNSkge1xuICAgICAgICBpZiAodGFncz8ubGVuZ3RoID09PSAwKSB7XG4gICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgc3RhdHVzOiAnaW5mbycsXG4gICAgICAgICAgICB0aXRsZTogJ05vIGNhdGVnb3JpZXMgYXZhaWxhYmxlJyxcbiAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnUGxlYXNlIGFkZCBhdCBsZWFzdCBvbmUgY2F0ZWdvcnkgaW4geW91ciBzZXR0aW5ncyBpbiBvcmRlciB0byBhZGQgdG8geW91ciBldmVudCcsXG4gICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICAgICAgfSlcbiAgICAgICAgICAgbmV3QWN0aXZlSW5kZXggPSA3XG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgICAgaWYgKHByZXZBY3RpdmVJbmRleCA9PT0gNykge1xuICAgICAgICByZXR1cm5cbiAgICAgIH1cblxuICAgICAgaWYgKCFwcmV2Q29tcGxldGVkU3RlcCB8fCAocHJldkNvbXBsZXRlZFN0ZXAgPCBwcmV2QWN0aXZlSW5kZXgpKSB7XG4gICAgICAgIGNvbnN0IG5ld0NvbXBsZXRlZFN0ZXAgPSBwcmV2QWN0aXZlSW5kZXhcbiAgICAgICAgc2V0Q29tcGxldGVkU3RlcChuZXdDb21wbGV0ZWRTdGVwKVxuICAgICAgfVxuXG4gICAgICBpZiAobmV3QWN0aXZlSW5kZXggIT09IHByZXZBY3RpdmVJbmRleCkge1xuICAgICAgICByZXR1cm4gc2V0QWN0aXZlSW5kZXgobmV3QWN0aXZlSW5kZXgpXG4gICAgICB9XG5cbiAgICB9XG5cbiAgICBpZiAoIWlzQXR0ZW5kZWVzICYmIGlzUmVjdXJyaW5nKSB7XG4gICAgICBsZXQgbmV3QWN0aXZlSW5kZXggPSBwcmV2QWN0aXZlSW5kZXggKyAxXG5cbiAgICAgIGlmIChwcmV2QWN0aXZlSW5kZXggPT09IDIpIHtcbiAgICAgICAgbmV3QWN0aXZlSW5kZXggPSA1XG4gICAgICB9XG5cbiAgICAgIGlmIChwcmV2QWN0aXZlSW5kZXggPT09IDUpIHtcbiAgICAgICAgaWYgKHRhZ3M/Lmxlbmd0aCA9PT0gMCkge1xuICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgIHN0YXR1czogJ2luZm8nLFxuICAgICAgICAgICAgdGl0bGU6ICdObyBjYXRlZ29yaWVzIGF2YWlsYWJsZScsXG4gICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1BsZWFzZSBhZGQgYXQgbGVhc3Qgb25lIGNhdGVnb3J5IGluIHlvdXIgc2V0dGluZ3MgaW4gb3JkZXIgdG8gYWRkIHRvIHlvdXIgZXZlbnQnLFxuICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICAgIH0pXG4gICAgICAgICAgIG5ld0FjdGl2ZUluZGV4ID0gN1xuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIGlmIChwcmV2QWN0aXZlSW5kZXggPT09IDcpIHtcbiAgICAgICAgcmV0dXJuXG4gICAgICB9XG5cbiAgICAgIGlmICghcHJldkNvbXBsZXRlZFN0ZXAgfHwgKHByZXZDb21wbGV0ZWRTdGVwIDwgcHJldkFjdGl2ZUluZGV4KSkge1xuICAgICAgICBjb25zdCBuZXdDb21wbGV0ZWRTdGVwID0gcHJldkFjdGl2ZUluZGV4XG4gICAgICAgIHNldENvbXBsZXRlZFN0ZXAobmV3Q29tcGxldGVkU3RlcClcbiAgICAgIH1cblxuICAgICAgaWYgKG5ld0FjdGl2ZUluZGV4ICE9PSBwcmV2QWN0aXZlSW5kZXgpIHtcbiAgICAgICAgcmV0dXJuIHNldEFjdGl2ZUluZGV4KG5ld0FjdGl2ZUluZGV4KVxuICAgICAgfVxuICAgIH1cblxuICAgIGlmICghaXNBdHRlbmRlZXMgJiYgIWlzUmVjdXJyaW5nKSB7XG4gICAgICBsZXQgbmV3QWN0aXZlSW5kZXggPSBwcmV2QWN0aXZlSW5kZXggKyAxXG5cbiAgICAgIGlmIChwcmV2QWN0aXZlSW5kZXggPT09IDEpIHtcbiAgICAgICAgbmV3QWN0aXZlSW5kZXggPSA1XG4gICAgICB9XG5cbiAgICAgIGlmIChwcmV2QWN0aXZlSW5kZXggPT09IDUpIHtcbiAgICAgICAgaWYgKHRhZ3M/Lmxlbmd0aCA9PT0gMCkge1xuICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgIHN0YXR1czogJ2luZm8nLFxuICAgICAgICAgICAgdGl0bGU6ICdObyBjYXRlZ29yaWVzIGF2YWlsYWJsZScsXG4gICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1BsZWFzZSBhZGQgYXQgbGVhc3Qgb25lIGNhdGVnb3J5IGluIHlvdXIgc2V0dGluZ3MgaW4gb3JkZXIgdG8gYWRkIHRvIHlvdXIgZXZlbnQnLFxuICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICAgIH0pXG4gICAgICAgICAgIG5ld0FjdGl2ZUluZGV4ID0gN1xuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIGlmIChwcmV2QWN0aXZlSW5kZXggPT09IDcpIHtcbiAgICAgICAgcmV0dXJuXG4gICAgICB9XG5cbiAgICAgIGlmICghcHJldkNvbXBsZXRlZFN0ZXAgfHwgKHByZXZDb21wbGV0ZWRTdGVwIDwgcHJldkFjdGl2ZUluZGV4KSkge1xuICAgICAgICBjb25zdCBuZXdDb21wbGV0ZWRTdGVwID0gcHJldkFjdGl2ZUluZGV4XG4gICAgICAgIHNldENvbXBsZXRlZFN0ZXAobmV3Q29tcGxldGVkU3RlcClcbiAgICAgIH1cblxuICAgICAgaWYgKG5ld0FjdGl2ZUluZGV4ICE9PSBwcmV2QWN0aXZlSW5kZXgpIHtcbiAgICAgICAgcmV0dXJuIHNldEFjdGl2ZUluZGV4KG5ld0FjdGl2ZUluZGV4KVxuICAgICAgfVxuICAgIH1cblxuICAgIGlmIChwcmV2QWN0aXZlSW5kZXggPT09IDcpIHtcbiAgICAgIHJldHVyblxuICAgIH1cblxuICAgIGxldCBuZXdBY3RpdmVJbmRleCA9IHByZXZBY3RpdmVJbmRleCArIDFcblxuICAgICAgaWYgKHByZXZBY3RpdmVJbmRleCA9PT0gNSkge1xuICAgICAgICBpZiAodGFncz8ubGVuZ3RoID09PSAwKSB7XG4gICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgc3RhdHVzOiAnaW5mbycsXG4gICAgICAgICAgICB0aXRsZTogJ05vIGNhdGVnb3JpZXMgYXZhaWxhYmxlJyxcbiAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnUGxlYXNlIGFkZCBhdCBsZWFzdCBvbmUgY2F0ZWdvcnkgaW4geW91ciBzZXR0aW5ncyBpbiBvcmRlciB0byBhZGQgdG8geW91ciBldmVudCcsXG4gICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICAgICAgfSlcbiAgICAgICAgICAgbmV3QWN0aXZlSW5kZXggPSA3XG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgIGlmICghcHJldkNvbXBsZXRlZFN0ZXAgfHwgKHByZXZDb21wbGV0ZWRTdGVwIDwgcHJldkFjdGl2ZUluZGV4KSkge1xuICAgICAgY29uc3QgbmV3Q29tcGxldGVkU3RlcCA9IHByZXZBY3RpdmVJbmRleFxuICAgICAgc2V0Q29tcGxldGVkU3RlcChuZXdDb21wbGV0ZWRTdGVwKVxuICAgIH1cblxuICAgIGlmIChuZXdBY3RpdmVJbmRleCAhPT0gcHJldkFjdGl2ZUluZGV4KSB7XG4gICAgICBzZXRBY3RpdmVJbmRleChuZXdBY3RpdmVJbmRleClcbiAgICB9XG4gIH1cblxuICBjb25zdCByZW5kZXJOZXh0QnV0dG9uID0gKCkgPT4ge1xuICAgIGlmIChhY3RpdmVJbmRleCA9PT0gNykge1xuICAgICAgcmV0dXJuIDxCb3ggcHQ9e3sgcGhvbmU6ICdtJywgdGFibGV0OiAncycgfX0vPlxuICAgIH1cblxuICAgIHJldHVybiAoXG4gICAgICA8Qm94IHA9e3sgcGhvbmU6ICdzJywgdGFibGV0OiAnbScgfX0+XG4gICAgICAgIDxCdXR0b24gb25DbGljaz17Z29Ub05leHRTdGVwfT5cbiAgICAgICAgICBOZXh0XG4gICAgICAgIDwvQnV0dG9uPlxuICAgICAgPC9Cb3g+XG4gICAgKVxuICB9XG5cbiAgY29uc3QgcmVuZGVyQ3VycmVudFN0ZXAgPSAoKSA9PiB7XG4gICAgIHN3aXRjaChhY3RpdmVJbmRleCkge1xuICAgICAgY2FzZSAwOlxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgIDxCb3ggc3R5bGU9e3sgd2lkdGg6ICcxMDAlJyB9fSBmbGV4PXsxfSBhbGlnbkl0ZW1zPVwiY2VudGVyXCIganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgIDxDcmVhdGVFdmVudEJhc2VTdGVwXG4gICAgICAgICAgICAgIHRpdGxlPXt0aXRsZX1cbiAgICAgICAgICAgICAgbm90ZXM9e25vdGVzfVxuICAgICAgICAgICAgICBsb2NhdGlvbj17bG9jYXRpb259XG4gICAgICAgICAgICAgIHNldFBhcmVudFRpdGxlPXtzZXRUaXRsZX1cbiAgICAgICAgICAgICAgc2V0UGFyZW50Tm90ZXM9e3NldE5vdGVzfVxuICAgICAgICAgICAgICBzZXRQYXJlbnRMb2NhdGlvbj17c2V0TG9jYXRpb259XG4gICAgICAgICAgICAgIHN0YXJ0RGF0ZT17c3RhcnREYXRlfVxuICAgICAgICAgICAgICBlbmREYXRlPXtlbmREYXRlfVxuICAgICAgICAgICAgICBzZXRQYXJlbnRFbmREYXRlPXtzZXRFbmREYXRlfVxuICAgICAgICAgICAgICBzZXRQYXJlbnRTdGFydERhdGU9e3NldFN0YXJ0RGF0ZX1cbiAgICAgICAgICAgIC8+XG4gICAgICAgICAgICA8Qm94IHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0gZmxleERpcmVjdGlvbj1cInJvd1wiIGp1c3RpZnlDb250ZW50PVwic3BhY2UtYmV0d2VlblwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgICAgPEJveCAvPlxuICAgICAgICAgICAgICB7cmVuZGVyTmV4dEJ1dHRvbigpfVxuICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgPC9Cb3g+XG4gICAgICAgIClcbiAgICAgIGNhc2UgMTogXG4gICAgICByZXR1cm4gKFxuICAgICAgICAgIDxCb3ggc3R5bGU9e3sgd2lkdGg6ICcxMDAlJyB9fSBmbGV4PXsxfSBhbGlnbkl0ZW1zPVwiY2VudGVyXCIganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgIDxDcmVhdGVFdmVudEJhc2VTdGVwMlxuICAgICAgICAgICAgICBhbGxEYXk9e2FsbERheX1cbiAgICAgICAgICAgICAgaXNSZWN1cnJpbmc9e2lzUmVjdXJyaW5nfVxuICAgICAgICAgICAgICBpc0F0dGVuZGVlcz17aXNBdHRlbmRlZXN9XG4gICAgICAgICAgICAgIGlzQnJlYWs9e2lzQnJlYWt9XG4gICAgICAgICAgICAgIHNldFBhcmVudEFsbERheT17c2V0QWxsRGF5fVxuICAgICAgICAgICAgICBzZXRQYXJlbnRJc1JlY3VycmluZz17c2V0SXNSZWN1cnJpbmd9XG4gICAgICAgICAgICAgIHNldFBhcmVudElzQXR0ZW5kZWVzPXtzZXRJc0F0dGVuZGVlc31cbiAgICAgICAgICAgICAgc2V0UGFyZW50SXNCcmVhaz17c2V0SXNCcmVha31cbiAgICAgICAgICAgIC8+XG4gICAgICAgICAgICA8Qm94IGZsZXhEaXJlY3Rpb249XCJyb3dcIiBqdXN0aWZ5Q29udGVudD1cInNwYWNlLWJldHdlZW5cIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgIHtyZW5kZXJQcmV2QnV0dG9uKCl9XG4gICAgICAgICAgICAgIHtyZW5kZXJOZXh0QnV0dG9uKCl9XG4gICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICA8L0JveD5cbiAgICAgICAgKVxuICAgICAgY2FzZSAyOlxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgIDxCb3ggc3R5bGU9e3sgd2lkdGg6ICcxMDAlJyB9fSBmbGV4PXsxfSBhbGlnbkl0ZW1zPVwiY2VudGVyXCIganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgIDxDcmVhdGVFdmVudFJlY3VyU3RlcFxuICAgICAgICAgICAgICByZWN1cnJpbmdFbmREYXRlPXtyZWN1cnJpbmdFbmREYXRlfVxuICAgICAgICAgICAgICBzZXRQYXJlbnRSZWN1cnJpbmdFbmREYXRlPXtzZXRSZWN1cnJpbmdFbmREYXRlfVxuICAgICAgICAgICAgICBmcmVxdWVuY3k9e2ZyZXF1ZW5jeX1cbiAgICAgICAgICAgICAgc2V0UGFyZW50RnJlcXVlbmN5PXtzZXRGcmVxdWVuY3l9XG4gICAgICAgICAgICAgIGludGVydmFsPXtpbnRlcnZhbH1cbiAgICAgICAgICAgICAgc2V0UGFyZW50SW50ZXJ2YWw9e3NldEludGVydmFsfVxuICAgICAgICAgICAgICBieVdlZWtEYXk9e2J5V2Vla0RheX1cbiAgICAgICAgICAgICAgc2V0UGFyZW50V2Vla0RheT17c2V0QnlXZWVrRGF5fVxuICAgICAgICAgICAgLz5cbiAgICAgICAgICAgIDxCb3ggZmxleERpcmVjdGlvbj1cInJvd1wiIGp1c3RpZnlDb250ZW50PVwic3BhY2UtYmV0d2VlblwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgICAge3JlbmRlclByZXZCdXR0b24oKX1cbiAgICAgICAgICAgICAge3JlbmRlck5leHRCdXR0b24oKX1cbiAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgIDwvQm94PlxuICAgICAgICApXG4gICAgICBjYXNlIDM6XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgPEJveCBzdHlsZT17eyB3aWR0aDogJzEwMCUnIH19IGZsZXg9ezF9IGFsaWduSXRlbXM9XCJjZW50ZXJcIiBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiPlxuICAgICAgICAgICAgPENyZWF0ZUV2ZW50VmlydHVhbE1lZXRcbiAgICAgICAgICAgICAgaXNab29tQXZhaWxhYmxlPXtpc1pvb21BdmFpbGFibGV9XG4gICAgICAgICAgICAgIGlzR29vZ2xlTWVldEF2YWlsYWJsZT17aXNHb29nbGVNZWV0QXZhaWxhYmxlfVxuICAgICAgICAgICAgICB6b29tTWVldD17em9vbU1lZXR9XG4gICAgICAgICAgICAgIGdvb2dsZU1lZXQ9e2dvb2dsZU1lZXR9XG4gICAgICAgICAgICAgIHNldFBhcmVudFpvb21NZWV0PXtzZXRab29tTWVldH1cbiAgICAgICAgICAgICAgc2V0UGFyZW50R29vZ2xlTWVldD17c2V0R29vZ2xlTWVldH1cbiAgICAgICAgICAgICAgem9vbVByaXZhdGVNZWV0aW5nPXt6b29tUHJpdmF0ZU1lZXRpbmd9XG4gICAgICAgICAgICAgIHNldFBhcmVudFpvb21Qcml2YXRlTWVldGluZz17c2V0Wm9vbVByaXZhdGVNZWV0aW5nfVxuICAgICAgICAgICAgLz5cbiAgICAgICAgICAgIDxCb3ggZmxleERpcmVjdGlvbj1cInJvd1wiIGp1c3RpZnlDb250ZW50PVwic3BhY2UtYmV0d2VlblwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgICAge3JlbmRlclByZXZCdXR0b24oKX1cbiAgICAgICAgICAgICAge3JlbmRlck5leHRCdXR0b24oKX1cbiAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgIDwvQm94PlxuICAgICAgICApXG4gICAgICBjYXNlIDQ6XG4gICAgICAgICByZXR1cm4gKFxuICAgICAgICAgIDxCb3ggc3R5bGU9e3sgd2lkdGg6ICcxMDAlJyB9fSBmbGV4PXsxfSBhbGlnbkl0ZW1zPVwiY2VudGVyXCIganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgIDxDcmVhdGVFdmVudEF0dGVuZGVlc1xuICAgICAgICAgICAgICBhdHRlbmRlZXM9e2F0dGVuZGVlc31cbiAgICAgICAgICAgICAgc2V0UGFyZW50QXR0ZW5kZWVzPXtzZXRBdHRlbmRlZXN9XG4gICAgICAgICAgICAgIHVzZXJJZD17dXNlcklkfVxuICAgICAgICAgICAgICBjbGllbnQ9e2NsaWVudH1cbiAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgIDxCb3ggZmxleERpcmVjdGlvbj1cInJvd1wiIGp1c3RpZnlDb250ZW50PVwic3BhY2UtYmV0d2VlblwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgICAge3JlbmRlclByZXZCdXR0b24oKX1cbiAgICAgICAgICAgICAge3JlbmRlck5leHRCdXR0b24oKX1cbiAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgIDwvQm94PlxuICAgICAgICApXG4gICAgICBjYXNlIDU6XG4gICAgICAgICByZXR1cm4gKFxuICAgICAgICAgIDxCb3ggc3R5bGU9e3sgd2lkdGg6ICcxMDAlJyB9fSBmbGV4PXsxfSBhbGlnbkl0ZW1zPVwiY2VudGVyXCIganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgIDxDcmVhdGVFdmVudFZpc2liaWxpdHlBbmRBbGFybXNTdGVwXG4gICAgICAgICAgICAgIGFsYXJtcz17YWxhcm1zfVxuICAgICAgICAgICAgICBzZXRQYXJlbnRBbGFybXM9e3NldEFsYXJtc31cbiAgICAgICAgICAgICAgdmlzaWJpbGl0eT17dmlzaWJpbGl0eX1cbiAgICAgICAgICAgICAgc2V0UGFyZW50VmlzaWJpbGl0eT17c2V0VmlzaWJpbGl0eX1cbiAgICAgICAgICAgICAgdXNlcklkPXt1c2VySWR9XG4gICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICA8Qm94IGZsZXhEaXJlY3Rpb249XCJyb3dcIiBqdXN0aWZ5Q29udGVudD1cInNwYWNlLWJldHdlZW5cIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICB7cmVuZGVyUHJldkJ1dHRvbigpfVxuICAgICAgICAgICAgICAge3JlbmRlck5leHRCdXR0b24oKX1cbiAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICA8L0JveD5cbiAgICAgICAgIClcbiAgICAgIGNhc2UgNjpcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICA8Qm94IHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0gZmxleD17MX0gYWxpZ25JdGVtcz1cImNlbnRlclwiIGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCI+XG4gICAgICAgICAgICA8Q3JlYXRlRXZlbnRBZGRDYXRlZ29yaWVzXG4gICAgICAgICAgICAgIGNhdGVnb3JpZXM9e3RhZ3N9XG4gICAgICAgICAgICAgIHNldFBhcmVudFNlbGVjdGVkQ2F0ZWdvcmllcz17c2V0U2VsZWN0ZWRDYXRlZ29yaWVzfVxuICAgICAgICAgICAgICBzZWxlY3RlZENhdGVnb3JpZXM9e3NlbGVjdGVkQ2F0ZWdvcmllc31cbiAgICAgICAgICAgIC8+XG4gICAgICAgICAgICA8Qm94IGZsZXhEaXJlY3Rpb249XCJyb3dcIiBqdXN0aWZ5Q29udGVudD1cInNwYWNlLWJldHdlZW5cIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgIHtyZW5kZXJQcmV2QnV0dG9uKCl9XG4gICAgICAgICAgICAgIHtyZW5kZXJOZXh0QnV0dG9uKCl9XG4gICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICA8L0JveD5cbiAgICAgICAgKSAgICAgICAgXG4gICAgICBjYXNlIDc6IFxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgIDxCb3ggZmxleD17MX0gYWxpZ25JdGVtcz1cImNlbnRlclwiIGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCI+XG4gICAgICAgICAgICA8Qm94IGZsZXg9ezF9IHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0gcD17eyBwaG9uZTogJ3MnLCB0YWJsZXQ6ICdtJyB9fSBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiAgbWluSGVpZ2h0PVwiNjV2aFwiIG1heEhlaWdodD1cIjY1dmhcIj5cbiAgICAgICAgICAgICAgPEJveCBwPXt7IHBob25lOiAnbScsIHRhYmxldDogJ2wnfX0+XG4gICAgICAgICAgICAgICAgPFRleHQgdmFyaWFudD1cInN1YmhlYWRlck5vcm1hbFwiPlxuICAgICAgICAgICAgICAgICAgQ3JlYXRlIEV2ZW50XG4gICAgICAgICAgICAgICAgPC9UZXh0PlxuICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgICAgPEJveCBwdD17eyBwaG9uZTogJ20nLCB0YWJsZXQ6ICdsJyB9fT5cbiAgICAgICAgICAgICAgICA8QnV0dG9uIG9uQ2xpY2s9e2NyZWF0ZUV2ZW50Rm9yVXNlcn0+XG4gICAgICAgICAgICAgICAgICBDcmVhdGVcbiAgICAgICAgICAgICAgICA8L0J1dHRvbj5cbiAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgIDxCb3ggZmxleERpcmVjdGlvbj1cInJvd1wiIGp1c3RpZnlDb250ZW50PVwic3BhY2UtYmV0d2VlblwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiBzdHlsZT17eyB3aWR0aDogJzc1JScgfX0+XG4gICAgICAgICAgICAgIHtyZW5kZXJQcmV2QnV0dG9uKCl9XG4gICAgICAgICAgICAgIDxCb3ggLz5cbiAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgIDwvQm94PlxuICAgICAgICApXG4gICAgICAgZGVmYXVsdDpcbiAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgIDxCb3gganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgPFJlZ3VsYXJDYXJkPlxuICAgICAgICAgICAgICAgPFRleHQgdmFyaWFudD1cImhlYWRlclwiPlxuICAgICAgICAgICAgICAgICBPb3BzLi4uIHNvbWV0aGluZyB3ZW50IHdyb25nXG4gICAgICAgICAgICAgICA8L1RleHQ+XG4gICAgICAgICAgICAgPC9SZWd1bGFyQ2FyZD5cbiAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICApXG4gICAgIH1cbiAgfVxuXG4gIHJldHVybiAoXG4gICAgPEJveCBmbGV4PXsxfSBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiBzdHlsZT17eyBoZWlnaHQ6ICcxMDAlJ319PlxuICAgICAgPFdpemFyZFxuICAgICAgICBpdGVtcz17W1xuICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgIGluZGV4OiAwLFxuICAgICAgICAgICAgICAgIGxhYmVsOiAnU2V0IEJhc2UnLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBpbmRleDogMSxcbiAgICAgICAgICAgICAgICBsYWJlbDogJ0NvbnRpbnVlIEJhc2UnLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBpbmRleDogMixcbiAgICAgICAgICAgICAgICBsYWJlbDogJ1NlbGVjdCBSZWN1cnJlbmNlJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBpbmRleDogMyxcbiAgICAgICAgICAgICAgICBsYWJlbDogJ1NlbGVjdCBWaXJ0dWFsIE1lZXQnLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgIGluZGV4OiA0LFxuICAgICAgICAgICAgICAgIGxhYmVsOiAnU2VsZWN0IEV2ZW50IEF0dGVuZGVlcycsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgaW5kZXg6IDUsXG4gICAgICAgICAgICAgICAgbGFiZWw6ICdTZXQgVmlzaWJpbGl0eSBBbmQgQWxhcm1zJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgaW5kZXg6IDYsXG4gICAgICAgICAgICAgICAgbGFiZWw6ICdTZWxlY3QgQ2F0ZWdvcmllcyBmb3IgRXZlbnQnLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBpbmRleDogNyxcbiAgICAgICAgICAgICAgICBsYWJlbDogJ0NyZWF0ZSBFdmVudCcsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgXG4gICAgICAgIF19XG5cbiAgICAgICAgY29tcGxldGVkPXtjb21wbGV0ZWRTdGVwfVxuICAgICAgICBhY3RpdmVJbmRleD17YWN0aXZlSW5kZXh9XG4gICAgICAvPlxuICAgICAge3JlbmRlckN1cnJlbnRTdGVwKCl9XG4gICAgICA8Qm94PlxuICAgICAgICA8YnV0dG9uIGNsYXNzTmFtZT1cImJ0biBidG4tbGluayBuby11bmRlcmxpbmUgaG92ZXI6bm8tdW5kZXJsaW5lXCIgb25DbGljaz17Y2xvc2VDcmVhdGVFdmVudH0+XG4gICAgICAgICAgICBDbG9zZVxuICAgICAgICA8L2J1dHRvbj5cbiAgICAgIDwvQm94PlxuICAgIDwvQm94PlxuICApXG5cbn1cblxuZXhwb3J0IGRlZmF1bHQgVXNlckNyZWF0ZUV2ZW50XG4iXX0=