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
const Box_1 = __importDefault(require("@components/common/Box"));
const Text_1 = __importDefault(require("@components/common/Text"));
const Button_1 = __importDefault(require("@components/Button"));
const RegularCard_1 = __importDefault(require("@components/RegularCard"));
const date_utils_1 = require("@lib/date-utils");
const CategoryHelper_1 = require("@lib/Category/CategoryHelper");
const zoomMeetingHelper_1 = require("@lib/zoom/zoomMeetingHelper");
const googleCalendarHelper_1 = require("@lib/calendarLib/googleCalendarHelper");
const EditEventAttendees_1 = __importDefault(require("@pages/Calendar/EditEventWizard/EditEventAttendees"));
const EditEventBaseStep_1 = __importDefault(require("@pages/Calendar/EditEventWizard/EditEventBaseStep"));
const EditEventBaseStep2_1 = __importDefault(require("@pages/Calendar/EditEventWizard/EditEventBaseStep2"));
const EditEventBaseStep3_1 = __importDefault(require("@pages/Calendar/EditEventWizard/EditEventBaseStep3"));
const EditEventRecurStepAlt_1 = __importDefault(require("@pages/Calendar/EditEventWizard/EditEventRecurStepAlt"));
const EditEventVirtualMeet_1 = __importDefault(require("@pages/Calendar/EditEventWizard/EditEventVirtualMeet"));
const EditEventVisibilityAndAlarmsStep_1 = __importDefault(require("@pages/Calendar/EditEventWizard/EditEventVisibilityAndAlarmsStep"));
const EditEventUpdateCategories_1 = __importDefault(require("@pages/Calendar/EditEventWizard/EditEventUpdateCategories"));
const UserEditCalendarHelper_1 = require("@lib/Calendar/UserEditCalendarHelper");
const ReminderHelper_1 = require("@lib/Calendar/Reminder/ReminderHelper");
const AttendeeHelper_1 = require("@lib/Calendar/Attendee/AttendeeHelper");
const getGlobalPrimaryCalendar_1 = __importDefault(require("@lib/apollo/gql/getGlobalPrimaryCalendar"));
const getEventById_1 = __importDefault(require("@lib/apollo/gql/getEventById"));
const getConferenceById_1 = __importDefault(require("@lib/apollo/gql/getConferenceById"));
const getCalendarById_1 = __importDefault(require("@lib/apollo/gql/getCalendarById"));
const router_1 = require("next/router");
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
function UserEditEvent(props) {
    const [categories, setCategories] = (0, react_1.useState)([]);
    const [selectedCategories, setSelectedCategories] = (0, react_1.useState)([]);
    const [title, setTitle] = (0, react_1.useState)();
    const [allDay, setAllDay] = (0, react_1.useState)(false);
    const [isRecurring, setIsRecurring] = (0, react_1.useState)(false);
    const [recurringEndDate, setRecurringEndDate] = (0, react_1.useState)(new Date());
    const [frequency, setFrequency] = (0, react_1.useState)('daily');
    const [interval, setInterval] = (0, react_1.useState)('1');
    const [alarms, setAlarms] = (0, react_1.useState)([]); // will be number for createEvent function
    const [notes, setNotes] = (0, react_1.useState)();
    const [location, setLocation] = (0, react_1.useState)();
    const [isZoomAvailable, setIsZoomAvailable] = (0, react_1.useState)(false);
    const [isGoogleMeetAvailable, setIsGoogleMeetAvailable] = (0, react_1.useState)(false);
    const [zoomMeet, setZoomMeet] = (0, react_1.useState)();
    const [googleMeet, setGoogleMeet] = (0, react_1.useState)();
    const [zoomPrivateMeeting, setZoomPrivateMeeting] = (0, react_1.useState)(false);
    const [attendees, setAttendees] = (0, react_1.useState)([]);
    const [visibility, setVisibility] = (0, react_1.useState)('default');
    const [isAttendees, setIsAttendees] = (0, react_1.useState)(false);
    const [activeIndex, setActiveIndex] = (0, react_1.useState)(0);
    const [completedStep, setCompletedStep] = (0, react_1.useState)();
    const [selectedCalendarId, setSelectedCalendarId] = (0, react_1.useState)();
    const [calendar, setCalendar] = (0, react_1.useState)();
    const [isBreak, setIsBreak] = (0, react_1.useState)(false);
    const [startDate, setStartDate] = (0, react_1.useState)(new Date());
    const [endDate, setEndDate] = (0, react_1.useState)(new Date());
    const [transparency, setTransparency] = (0, react_1.useState)('opaque');
    const [isExternalMeeting, setIsExternalMeeting] = (0, react_1.useState)(false);
    const [isMeeting, setIsMeeting] = (0, react_1.useState)(false);
    const [modifiable, setModifiable] = (0, react_1.useState)(true);
    const [byWeekDay, setByWeekDay] = (0, react_1.useState)([]);
    const [oldEvent, setOldEvent] = (0, react_1.useState)();
    const router = (0, router_1.useRouter)();
    const toast = (0, react_2.useToast)();
    const userId = props?.sub;
    const id = props?.id;
    const closeEditEvent = props?.closeEditEvent;
    const client = props?.client;
    console.log(id, ' eventId prerender inside usereditevent');
    // get categories
    (0, react_1.useEffect)(() => {
        (async () => {
            try {
                if (!userId || !client) {
                    console.log(userId, client, 'no userId or client');
                    return;
                }
                const results = await (0, CategoryHelper_1.listUserCategories)(client, userId);
                if (!results?.[0]?.id) {
                    console.log(' no categories available');
                    return;
                }
                setCategories(results);
            }
            catch (e) {
                console.log(e, ' unable to get categories');
            }
        })();
    }, [client, userId]);
    // get event selected categories
    (0, react_1.useEffect)(() => {
        (async () => {
            try {
                if (!id || !client) {
                    console.log(userId, client, 'no userId or client');
                    return;
                }
                const results = await (0, CategoryHelper_1.listCategoriesForEvent)(client, id);
                console.log(results, ' listCategoriesForEvent inside usereditevent');
                if (!results?.[0]?.id) {
                    console.log(' no selected categories available');
                    return;
                }
                setSelectedCategories(results);
            }
            catch (e) {
                console.log(e, ' unable to get selected categories');
            }
        })();
    }, [client, id, userId]);
    // check if zoom available
    (0, react_1.useEffect)(() => {
        (async () => {
            if (!userId || !client) {
                console.log(userId, client, 'no userId or client');
                return;
            }
            const isAvailable = await (0, zoomMeetingHelper_1.zoomAvailable)(client, userId);
            if (isAvailable) {
                setIsZoomAvailable(true);
            }
        })();
    }, [client, userId]);
    // check if google available
    (0, react_1.useEffect)(() => {
        (async () => {
            if (!userId || !client) {
                console.log(userId, client, 'no userId or client');
                return;
            }
            const isAvailable = await (0, googleCalendarHelper_1.googleMeetAvailable)(client, userId);
            if (isAvailable) {
                setIsGoogleMeetAvailable(isAvailable);
            }
        })();
    }, [client, userId]);
    // get event Calendar else global primary calendar
    (0, react_1.useEffect)(() => {
        (async () => {
            if (!userId || !client) {
                return;
            }
            if (!id) {
                console.log(' no eventId');
            }
            const event = (await client.query({
                query: getEventById_1.default,
                variables: {
                    id: id,
                },
            })).data?.Event_by_pk;
            if (!event?.id) {
                console.log(' no event available');
                return;
            }
            const calendarDoc = (await client.query({
                query: getCalendarById_1.default,
                variables: {
                    id: event?.calendarId,
                },
            })).data?.Calendar_by_pk;
            if (!calendarDoc?.id) {
                const calendar = (await client.query({
                    query: getGlobalPrimaryCalendar_1.default,
                    variables: {
                        userId,
                    },
                })).data?.Calendar?.[0];
                if (!calendar?.id) {
                    console.log(' no primary calendar available');
                    return;
                }
                setSelectedCalendarId(calendar?.id);
                setCalendar(calendar);
            }
            else {
                setSelectedCalendarId(calendarDoc?.id);
                setCalendar(calendarDoc);
            }
        })();
    }, [client, id, userId]);
    // get alarms
    (0, react_1.useEffect)(() => {
        (async () => {
            if (!id || !client) {
                return;
            }
            const results = await (0, ReminderHelper_1.listRemindersForEvent)(client, id);
            if (!results?.[0]?.minutes) {
                console.log(' no alarms available');
                return;
            }
            setAlarms(results?.map(r => r.minutes));
        })();
    }, [client, id]);
    // get event
    (0, react_1.useEffect)(() => {
        (async () => {
            console.log(' get event useEffect called inside usereditevent');
            if (!id || !client) {
                console.log('no eventId or client inside userEditEvent');
                return;
            }
            const event = (await client.query({
                query: getEventById_1.default,
                variables: {
                    id: id,
                },
            })).data?.Event_by_pk;
            if (!event?.id) {
                console.log(' no event available');
                return;
            }
            console.log(event, ' event inside usereditevent');
            setTitle(event?.title || event?.summary);
            setAllDay(event?.allDay);
            setIsRecurring(event?.recurrence?.length > 0);
            if (event?.recurrenceRule?.endDate) {
                setRecurringEndDate((0, date_utils_1.dayjs)(event?.recurrenceRule?.endDate?.slice(0, 19)).tz(event?.timezone, true).toDate());
                setFrequency(event?.recurrenceRule?.frequency);
                setInterval(`${event?.recurrenceRule?.interval}`);
            }
            setStartDate(date_utils_1.dayjs.tz(event?.startDate, event?.timezone || date_utils_1.dayjs.tz.guess()).toDate());
            setEndDate(date_utils_1.dayjs.tz(event?.endDate, event?.timezone || date_utils_1.dayjs.tz.guess()).toDate());
            setNotes(event?.notes);
            setLocation(event?.location?.title);
            setVisibility(event?.visibility);
            setIsBreak(event?.isBreak);
            setTransparency(event?.transparency);
            setIsExternalMeeting(event?.isExternalMeeting);
            setIsMeeting(event?.isMeeting);
            setModifiable(event?.modifiable);
            setByWeekDay(event?.byWeekDay);
            setOldEvent(event);
        })();
    }, [client, id]);
    // get conference in db
    (0, react_1.useEffect)(() => {
        (async () => {
            if (!id || !client) {
                return;
            }
            const oldEvent = (await client.query({
                query: getEventById_1.default,
                variables: {
                    id: id,
                },
            })).data?.Event_by_pk;
            if (!oldEvent?.id) {
                console.log(' no event available');
                return;
            }
            if (!oldEvent?.conferenceId) {
                console.log(oldEvent?.conferenceId, ' no conferenceId inside userEditEvent');
                return;
            }
            const conference = (await client.query({
                query: getConferenceById_1.default,
                variables: {
                    id: oldEvent?.conferenceId,
                },
            })).data?.Conference_by_pk;
            if (!conference?.id) {
                console.log(' no conference available');
                return;
            }
            if (conference?.app === 'zoom') {
                setZoomMeet(true);
            }
            if (conference?.app === 'google') {
                setGoogleMeet(true);
            }
            if (conference?.zoomPrivateMeeting === true) {
                setZoomPrivateMeeting(true);
            }
        })();
    }, [client, id]);
    // get event attendees
    (0, react_1.useEffect)(() => {
        (async () => {
            if (!id || !client) {
                return;
            }
            const results = await (0, AttendeeHelper_1.listAttendeesForEvent)(client, id);
            if (!results?.[0]?.id) {
                console.log(' no attendees available');
                return;
            }
            setAttendees(results.map(r => ({ id: r.id, name: r.name, emails: r.emails, phoneNumbers: r.phoneNumbers, imAddresses: r.imAddresses, additionalGuests: r.additionalGuests, optional: r.optional, resource: r.resource })));
            setIsAttendees(true);
        })();
    }, [client, id]);
    const updateEventForUser = async () => {
        try {
            // validate before update
            if (!userId || !client) {
                console.log('no userId or client inside updateEventForUser');
                return;
            }
            if (!id) {
                console.log('no eventId inside updateEventForUser');
                return;
            }
            if (!selectedCalendarId) {
                console.log('no calendarId inside updateEventForUser');
                return;
            }
            console.log(frequency, interval, byWeekDay, ' frequency, interval and byWeekDay inside updateEventForUser');
            await (0, UserEditCalendarHelper_1.updateEvent)(id, (0, date_utils_1.dayjs)(startDate).format(), (0, date_utils_1.dayjs)(endDate).format(), userId, client, selectedCalendarId, selectedCategories?.map(category => category.id), title, allDay, isRecurring ? (0, date_utils_1.dayjs)(recurringEndDate).format() : null, isRecurring ? frequency : null, isRecurring ? parseInt(interval, 10) : null, alarms, notes, location ? { title: location } : undefined, false, false, false, modifiable, undefined, undefined, undefined, false, date_utils_1.dayjs.tz.guess(), undefined, undefined, undefined, undefined, undefined, undefined, zoomMeet, googleMeet, 'scheduled', undefined, zoomPrivateMeeting, attendees, undefined, undefined, attendees?.[0]?.emails?.[0]?.value ? 'all' : undefined, undefined, title, transparency, visibility, undefined, undefined, undefined, calendar?.colorId, date_utils_1.dayjs.tz.guess(), selectedCategories?.[0]?.color || oldEvent?.backgroundColor || calendar?.backgroundColor, oldEvent?.foregroundColor || calendar?.foregroundColor, alarms?.length > 0 ? false : true, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, isExternalMeeting, undefined, undefined, isMeeting, undefined, undefined, isBreak, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, true, undefined, undefined, alarms?.length > 0, undefined, true, true, true, undefined, undefined, undefined, undefined, true, true, date_utils_1.dayjs.duration((0, date_utils_1.dayjs)(endDate).diff((0, date_utils_1.dayjs)(startDate))).asMinutes(), undefined, undefined, 'update', undefined, byWeekDay);
            toast({
                status: 'success',
                title: 'Event Edited',
                description: 'Event edited successfully',
                duration: 9000,
                isClosable: true,
            });
            closeEditEvent();
        }
        catch (e) {
            console.log(e, ' createEventForUser');
            toast({
                status: 'error',
                title: 'Event Editing failed',
                description: 'Unable to edit event. Please try again',
                duration: 9000,
                isClosable: true,
            });
        }
    };
    const onActiveIndexChanged = (index) => setActiveIndex(index);
    const goToPrevStep = () => {
        const prevActiveIndex = activeIndex;
        if (((activeIndex - 1) === 3) && (!isRecurring)) {
            setActiveIndex(prevActiveIndex - 2);
        }
        else {
            const newActiveIndex = prevActiveIndex === 0 ? 0 : prevActiveIndex - 1;
            setActiveIndex(newActiveIndex);
        }
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
        /**
         0 - EditEventBaseStep
         1 - EditEventBaseStep2
         2 - EditEventBaseStep3
         3 - EditEventRecurStep
         4 - EditEventVirtualMeet
         5 - EditEventAttendees
         6 - EditEventVisibilityAndAlarmsStep
         7 - EditEventUpdateCategories
         */
        if (prevActiveIndex === 8) {
            return;
        }
        if (!isRecurring && isAttendees) {
            let newActiveIndex = prevActiveIndex + 1;
            if (prevActiveIndex === 2) {
                newActiveIndex = 4;
            }
            // validate user category list
            if (prevActiveIndex === 6) {
                if (categories?.length === 0) {
                    toast({
                        status: 'info',
                        title: 'No categories available',
                        description: 'Please add at least one category in your settings in order to add to your event',
                        duration: 9000,
                        isClosable: true,
                    });
                    newActiveIndex = 8;
                }
            }
            if (prevActiveIndex === 8) {
                return;
            }
            if (!prevCompletedStep || (prevCompletedStep < prevActiveIndex)) {
                const newCompletedStep = prevActiveIndex;
                setCompletedStep(newCompletedStep);
            }
            if (newActiveIndex !== prevActiveIndex) {
                return setActiveIndex(newActiveIndex);
            }
            return;
        }
        if (!isAttendees && isRecurring) {
            let newActiveIndex = prevActiveIndex + 1;
            if (prevActiveIndex === 3) {
                newActiveIndex = 6;
            }
            // validate user category list
            if (prevActiveIndex === 6) {
                if (categories?.length === 0) {
                    toast({
                        status: 'info',
                        title: 'No categories available',
                        description: 'Please add at least one category in your settings in order to add to your event',
                        duration: 9000,
                        isClosable: true,
                    });
                    newActiveIndex = 8;
                }
            }
            if (!prevCompletedStep || (prevCompletedStep < prevActiveIndex)) {
                const newCompletedStep = prevActiveIndex;
                setCompletedStep(newCompletedStep);
            }
            if (newActiveIndex !== prevActiveIndex) {
                return setActiveIndex(newActiveIndex);
            }
            return;
        }
        if (!isAttendees && !isRecurring) {
            console.log('inside !isAttendees && !isRecurring');
            let newActiveIndex = prevActiveIndex + 1;
            if (prevActiveIndex === 2) {
                newActiveIndex = 6;
            }
            // validate user category list
            if (prevActiveIndex === 6) {
                if (categories?.length === 0) {
                    toast({
                        status: 'info',
                        title: 'No categories available',
                        description: 'Please add at least one category in your settings in order to add to your event',
                        duration: 9000,
                        isClosable: true,
                    });
                    newActiveIndex = 8;
                }
            }
            if (!prevCompletedStep || (prevCompletedStep < prevActiveIndex)) {
                const newCompletedStep = prevActiveIndex;
                setCompletedStep(newCompletedStep);
            }
            if (newActiveIndex !== prevActiveIndex) {
                return setActiveIndex(newActiveIndex);
            }
            return;
        }
        let newActiveIndex = prevActiveIndex + 1;
        // validate user category list
        if (prevActiveIndex === 6) {
            if (categories?.length === 0) {
                toast({
                    status: 'info',
                    title: 'No categories available',
                    description: 'Please add at least one category in your settings in order to add to your event',
                    duration: 9000,
                    isClosable: true,
                });
                newActiveIndex = 8;
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
        if (activeIndex === 8) {
            return (0, jsx_runtime_1.jsx)(Box_1.default, { pt: { phone: 'm', tablet: 's' } });
        }
        return ((0, jsx_runtime_1.jsx)(Box_1.default, { p: { phone: 's', tablet: 'm' }, children: (0, jsx_runtime_1.jsx)(Button_1.default, { onClick: goToNextStep, children: "Next" }) }));
    };
    const renderCurrentStep = () => {
        /**
         0 - CreateEventBaseStep
         1 - CreateEventBaseStep2
         2 - CreateEventBaseStep3
         3 - CreateEventRecurStep
         4 - CreateEventVirtualMeet
         5 - CreateEventAttendees
         6 - CreateEventVisibilityAndAlarmsStep
         7 - CreateEventAddCategories
         */
        switch (activeIndex) {
            case 0:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%', height: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", minHeight: "75vh", children: [(0, jsx_runtime_1.jsx)(EditEventBaseStep_1.default, { title: title, notes: notes, location: location, startDate: startDate, endDate: endDate, setParentTitle: setTitle, setParentNotes: setNotes, setParentLocation: setLocation, setParentStartDate: setStartDate, setParentEndDate: setEndDate }), (0, jsx_runtime_1.jsx)(Box_1.default, { px: "m", width: "90%", alignItems: "center", mt: "s", children: (0, jsx_runtime_1.jsxs)(Text_1.default, { variant: "caption", textAlign: "center", color: "textSecondary", children: ["Tip: Atomic can learn from your past events! After typing a title, see if Atomic suggests details from similar entries. You can also 'train' specific events to act as powerful templates.", (0, jsx_runtime_1.jsxs)(Text_1.default, { variant: "link", onPress: () => router.push('https://docs.atomiclife.app/docs/features/smart-scheduling'), children: [' ', "Learn more about smart scheduling"] })] }) }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", style: { width: '95%' }, children: [(0, jsx_runtime_1.jsx)(Box_1.default, {}), renderNextButton()] })] }));
            case 1:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(EditEventBaseStep2_1.default, { allDay: allDay, isRecurring: isRecurring, isAttendees: isAttendees, isBreak: isBreak, setParentAllDay: setAllDay, setParentIsRecurring: setIsRecurring, setParentIsAttendees: setIsAttendees, setParentIsBreak: setIsBreak }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [renderPrevButton(), renderNextButton()] })] }));
            case 2:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(EditEventBaseStep3_1.default, { modifiable: modifiable, setParentModifiable: setModifiable, isMeeting: isMeeting, setParentIsMeeting: setIsMeeting, isExternalMeeting: isExternalMeeting, setParentIsExternalMeeting: setIsExternalMeeting, transparency: transparency, setParentTransparency: setTransparency }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [renderPrevButton(), renderNextButton()] })] }));
            case 3:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(EditEventRecurStepAlt_1.default, { recurringEndDate: recurringEndDate, setParentRecurringEndDate: setRecurringEndDate, frequency: frequency, setParentFrequency: setFrequency, interval: interval, setParentInterval: setInterval, byWeekDay: byWeekDay, setParentByWeekDay: setByWeekDay }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [renderPrevButton(), renderNextButton()] })] }));
            case 4:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(EditEventVirtualMeet_1.default, { isZoomAvailable: isZoomAvailable, isGoogleMeetAvailable: isGoogleMeetAvailable, zoomMeet: zoomMeet, googleMeet: googleMeet, setParentZoomMeet: setZoomMeet, setParentGoogleMeet: setGoogleMeet, zoomPrivateMeeting: zoomPrivateMeeting, setParentZoomPrivateMeeting: setZoomPrivateMeeting }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [renderPrevButton(), renderNextButton()] })] }));
            case 5:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(EditEventAttendees_1.default, { attendees: attendees, setParentAttendees: setAttendees, userId: userId, client: client }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [renderPrevButton(), renderNextButton()] })] }));
            case 6:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(EditEventVisibilityAndAlarmsStep_1.default, { alarms: alarms, setParentAlarms: setAlarms, visibility: visibility, setParentVisibility: setVisibility, userId: userId }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [renderPrevButton(), renderNextButton()] })] }));
            case 7:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(EditEventUpdateCategories_1.default, { categories: categories, setParentSelectedCategories: setSelectedCategories, selectedCategories: selectedCategories }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [renderPrevButton(), renderNextButton()] })] }));
            case 8:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, style: { width: '100%' }, p: { phone: 's', tablet: 'm' }, justifyContent: "center", alignItems: "center", minHeight: "65vh", maxHeight: "65vh", children: [(0, jsx_runtime_1.jsx)(Box_1.default, { p: { phone: 'm', tablet: 'l' }, children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "subheaderNormal", children: "Update Event" }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { pt: { phone: 'm', tablet: 'l' }, children: (0, jsx_runtime_1.jsx)(Button_1.default, { onClick: updateEventForUser, children: "Update" }) })] }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", style: { width: '75%' }, children: [renderPrevButton(), (0, jsx_runtime_1.jsx)(Box_1.default, {})] })] }));
            default:
                return ((0, jsx_runtime_1.jsx)(Box_1.default, { justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsx)(RegularCard_1.default, { children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "header", children: "Oops... something went wrong" }) }) }));
        }
    };
    return ((0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, justifyContent: "center", alignItems: "center", width: "100%", height: "100%", minHeight: "80vh", children: [(0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, justifyContent: "center", alignItems: "center", width: "100%", height: "100%", minHeight: "80vh", children: [(0, jsx_runtime_1.jsx)(Wizard_1.default, { items: [
                            {
                                index: 0,
                                label: 'Update Base',
                            },
                            {
                                index: 1,
                                label: 'Continue Base',
                            },
                            {
                                index: 2,
                                label: 'Continue Base',
                            },
                            {
                                index: 3,
                                label: 'Update Recurrence',
                            },
                            {
                                index: 4,
                                label: 'Update Virtual Meet',
                            },
                            {
                                index: 5,
                                label: 'Update Event Attendees',
                            },
                            {
                                index: 6,
                                label: 'Update Visibility And Alarms',
                            },
                            {
                                index: 7,
                                label: 'Update Categories for Event',
                            },
                            {
                                index: 8,
                                label: 'Update Event',
                            },
                        ], completed: completedStep, activeIndex: activeIndex }), renderCurrentStep()] }), (0, jsx_runtime_1.jsx)(Box_1.default, { children: (0, jsx_runtime_1.jsx)("button", { className: "btn btn-link no-underline hover:no-underline", onClick: closeEditEvent, children: "Close" }) })] }));
}
exports.default = UserEditEvent;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlckVkaXRFdmVudC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIlVzZXJFZGl0RXZlbnQudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7O0FBMERBLGdEQXFDQzs7QUEvRkQsaUNBQStEO0FBQy9ELGdFQUF1QztBQUV2Qyw0Q0FBMkM7QUFDM0MsaUVBQXdDO0FBQ3hDLG1FQUEwQztBQUMxQyxnRUFBdUM7QUFDdkMsMEVBQWlEO0FBQ2pELGdEQUF1QztBQUt2QyxpRUFHcUM7QUFFckMsbUVBRW9DO0FBQ3BDLGdGQUU4QztBQUk5Qyw0R0FBbUY7QUFDbkYsMEdBQWlGO0FBQ2pGLDRHQUFtRjtBQUNuRiw0R0FBbUY7QUFDbkYsa0hBQXNGO0FBQ3RGLGdIQUF1RjtBQUN2Rix3SUFBK0c7QUFDL0csMEhBQWlHO0FBR2pHLGlGQUFrRTtBQUdsRSwwRUFBNkU7QUFDN0UsMEVBQTZFO0FBSTdFLHdHQUErRTtBQUMvRSxnRkFBdUQ7QUFDdkQsMEZBQWlFO0FBRWpFLHNGQUE2RDtBQUc3RCx3Q0FBdUM7QUFFdkMsd0VBQThDO0FBQzlDLDhEQUEwRDtBQUMxRCw4RUFBcUQ7QUFFOUMsS0FBSyxVQUFVLGtCQUFrQixDQUFDLEVBQUUsR0FBRyxFQUFFLEdBQUcsRUFBaUQ7SUFDbEcsMEZBQTBGO0lBQzFGLHNDQUFzQztJQUN0Qyx5RUFBeUU7SUFDekUsMEJBQWUsQ0FBQyxJQUFJLENBQUMsSUFBQSw2QkFBYSxHQUFFLENBQUMsQ0FBQTtJQUNyQyxJQUFJLE9BQU8sQ0FBQTtJQUNYLElBQUksQ0FBQztRQUNILE9BQU8sR0FBRyxNQUFNLGlCQUFPLENBQUMsVUFBVSxDQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUU7WUFDM0MsNkJBQTZCLEVBQUUsS0FBSztnQkFDbEMsT0FBTyxFQUFFLENBQUE7WUFDWCxDQUFDO1NBQ0YsQ0FBQyxDQUFBO0lBQ0osQ0FBQztJQUFDLE9BQU8sR0FBUSxFQUFFLENBQUM7UUFDbEIsSUFBSSxHQUFHLENBQUMsSUFBSSxLQUFLLGlC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RS9FLEdBQ0wsSUFDRixDQUNQLENBQUE7QUFDSCxDQUFDO0FBRUQsa0JBQWUsYUFBYSxDQUFBIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IFJlYWN0LCB7IHVzZVN0YXRlLCB1c2VFZmZlY3QsIHVzZUNhbGxiYWNrIH0gZnJvbSAncmVhY3QnXG5pbXBvcnQgV2l6YXJkIGZyb20gJ0Bjb21wb25lbnRzL1dpemFyZCdcblxuaW1wb3J0IHsgdXNlVG9hc3QgfSBmcm9tICdAY2hha3JhLXVpL3JlYWN0J1xuaW1wb3J0IEJveCBmcm9tICdAY29tcG9uZW50cy9jb21tb24vQm94J1xuaW1wb3J0IFRleHQgZnJvbSAnQGNvbXBvbmVudHMvY29tbW9uL1RleHQnXG5pbXBvcnQgQnV0dG9uIGZyb20gJ0Bjb21wb25lbnRzL0J1dHRvbidcbmltcG9ydCBSZWd1bGFyQ2FyZCBmcm9tICdAY29tcG9uZW50cy9SZWd1bGFyQ2FyZCdcbmltcG9ydCB7IGRheWpzIH0gZnJvbSAnQGxpYi9kYXRlLXV0aWxzJ1xuXG5pbXBvcnQge1xuICBDYXRlZ29yeVR5cGVcbn0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvQ2F0ZWdvcnlUeXBlJ1xuaW1wb3J0IHtcbiAgbGlzdENhdGVnb3JpZXNGb3JFdmVudCxcbiAgbGlzdFVzZXJDYXRlZ29yaWVzLFxufSBmcm9tICdAbGliL0NhdGVnb3J5L0NhdGVnb3J5SGVscGVyJ1xuXG5pbXBvcnQge1xuICB6b29tQXZhaWxhYmxlXG59IGZyb20gJ0BsaWIvem9vbS96b29tTWVldGluZ0hlbHBlcidcbmltcG9ydCB7XG4gIGdvb2dsZU1lZXRBdmFpbGFibGUsXG59IGZyb20gJ0BsaWIvY2FsZW5kYXJMaWIvZ29vZ2xlQ2FsZW5kYXJIZWxwZXInXG5pbXBvcnQgeyBQZXJzb24sIFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlIH0gZnJvbSAnQGxpYi9DYWxlbmRhci90eXBlcydcbmltcG9ydCB7IFZpc2liaWxpdHlUeXBlIH0gZnJvbSAnQGxpYi9jYWxlbmRhckxpYi90eXBlcydcblxuaW1wb3J0IEVkaXRFdmVudEF0dGVuZGVlcyBmcm9tICdAcGFnZXMvQ2FsZW5kYXIvRWRpdEV2ZW50V2l6YXJkL0VkaXRFdmVudEF0dGVuZGVlcydcbmltcG9ydCBFZGl0RXZlbnRCYXNlU3RlcCBmcm9tICdAcGFnZXMvQ2FsZW5kYXIvRWRpdEV2ZW50V2l6YXJkL0VkaXRFdmVudEJhc2VTdGVwJ1xuaW1wb3J0IEVkaXRFdmVudEJhc2VTdGVwMiBmcm9tICdAcGFnZXMvQ2FsZW5kYXIvRWRpdEV2ZW50V2l6YXJkL0VkaXRFdmVudEJhc2VTdGVwMidcbmltcG9ydCBFZGl0RXZlbnRCYXNlU3RlcDMgZnJvbSAnQHBhZ2VzL0NhbGVuZGFyL0VkaXRFdmVudFdpemFyZC9FZGl0RXZlbnRCYXNlU3RlcDMnXG5pbXBvcnQgRWRpdEV2ZW50UmVjdXJTdGVwIGZyb20gJ0BwYWdlcy9DYWxlbmRhci9FZGl0RXZlbnRXaXphcmQvRWRpdEV2ZW50UmVjdXJTdGVwQWx0J1xuaW1wb3J0IEVkaXRFdmVudFZpcnR1YWxNZWV0IGZyb20gJ0BwYWdlcy9DYWxlbmRhci9FZGl0RXZlbnRXaXphcmQvRWRpdEV2ZW50VmlydHVhbE1lZXQnXG5pbXBvcnQgRWRpdEV2ZW50VmlzaWJpbGl0eUFuZEFsYXJtc1N0ZXAgZnJvbSAnQHBhZ2VzL0NhbGVuZGFyL0VkaXRFdmVudFdpemFyZC9FZGl0RXZlbnRWaXNpYmlsaXR5QW5kQWxhcm1zU3RlcCdcbmltcG9ydCBFZGl0RXZlbnRVcGRhdGVDYXRlZ29yaWVzIGZyb20gJ0BwYWdlcy9DYWxlbmRhci9FZGl0RXZlbnRXaXphcmQvRWRpdEV2ZW50VXBkYXRlQ2F0ZWdvcmllcydcblxuXG5pbXBvcnQgeyB1cGRhdGVFdmVudCB9IGZyb20gJ0BsaWIvQ2FsZW5kYXIvVXNlckVkaXRDYWxlbmRhckhlbHBlcidcbmltcG9ydCB7IENhbGVuZGFyVHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL0NhbGVuZGFyVHlwZSdcbmltcG9ydCB7IEV2ZW50VHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL0V2ZW50VHlwZSdcbmltcG9ydCB7IGxpc3RSZW1pbmRlcnNGb3JFdmVudCB9IGZyb20gJ0BsaWIvQ2FsZW5kYXIvUmVtaW5kZXIvUmVtaW5kZXJIZWxwZXInXG5pbXBvcnQgeyBsaXN0QXR0ZW5kZWVzRm9yRXZlbnQgfSBmcm9tICdAbGliL0NhbGVuZGFyL0F0dGVuZGVlL0F0dGVuZGVlSGVscGVyJ1xuaW1wb3J0IHsgVHJhbnNwYXJlbmN5VHlwZSB9IGZyb20gJ0BsaWIvY2FsZW5kYXJMaWIvdHlwZXMnO1xuaW1wb3J0IHsgRGF5IH0gZnJvbSAnQGxpYi9TY2hlZHVsZS9jb25zdGFudHMnXG5pbXBvcnQgeyBBcG9sbG9DbGllbnQsIE5vcm1hbGl6ZWRDYWNoZU9iamVjdCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50J1xuaW1wb3J0IGdldEdsb2JhbFByaW1hcnlDYWxlbmRhciBmcm9tICdAbGliL2Fwb2xsby9ncWwvZ2V0R2xvYmFsUHJpbWFyeUNhbGVuZGFyJ1xuaW1wb3J0IGdldEV2ZW50QnlJZCBmcm9tICdAbGliL2Fwb2xsby9ncWwvZ2V0RXZlbnRCeUlkJ1xuaW1wb3J0IGdldENvbmZlcmVuY2VCeUlkIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9nZXRDb25mZXJlbmNlQnlJZCdcbmltcG9ydCB7IENvbmZlcmVuY2VUeXBlIH0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvQ29uZmVyZW5jZVR5cGUnXG5pbXBvcnQgZ2V0Q2FsZW5kYXJCeUlkIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9nZXRDYWxlbmRhckJ5SWQnXG5pbXBvcnQgeyB1c2VGb2N1c0VmZmVjdCB9IGZyb20gJ0BjaGFrcmEtdWkvcmVhY3QnXG5pbXBvcnQgeyB1c2VBcHBDb250ZXh0IH0gZnJvbSAnQGxpYi91c2VyLWNvbnRleHQnXG5pbXBvcnQgeyB1c2VSb3V0ZXIgfSBmcm9tICduZXh0L3JvdXRlcidcbmltcG9ydCB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCBzdXBlcnRva2Vuc05vZGUgZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZSdcbmltcG9ydCB7IGJhY2tlbmRDb25maWcgfSBmcm9tICcuLi8uLi9jb25maWcvYmFja2VuZENvbmZpZydcbmltcG9ydCBTZXNzaW9uIGZyb20gJ3N1cGVydG9rZW5zLW5vZGUvcmVjaXBlL3Nlc3Npb24nXG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRTZXJ2ZXJTaWRlUHJvcHMoeyByZXEsIHJlcyB9OiB7IHJlcTogTmV4dEFwaVJlcXVlc3QsIHJlczogTmV4dEFwaVJlc3BvbnNlIH0pIHtcbiAgLy8gTm90aWNlIGhvdyB0aGUgc2VydmVyIHVzZXMgYEFQSWAgZnJvbSBgd2l0aFNTUkNvbnRleHRgLCBpbnN0ZWFkIG9mIHRoZSB0b3AtbGV2ZWwgYEFQSWAuXG4gIC8vIGNvbnN0IFNTUiA9IHdpdGhTU1JDb250ZXh0KHsgcmVxIH0pXG4gIC8vIHRoaXMgcnVucyBvbiB0aGUgYmFja2VuZCwgc28gd2UgbXVzdCBjYWxsIGluaXQgb24gc3VwZXJ0b2tlbnMtbm9kZSBTREtcbiAgc3VwZXJ0b2tlbnNOb2RlLmluaXQoYmFja2VuZENvbmZpZygpKVxuICBsZXQgc2Vzc2lvblxuICB0cnkge1xuICAgIHNlc3Npb24gPSBhd2FpdCBTZXNzaW9uLmdldFNlc3Npb24ocmVxLCByZXMsIHtcbiAgICAgIG92ZXJyaWRlR2xvYmFsQ2xhaW1WYWxpZGF0b3JzOiBhc3luYyBmdW5jdGlvbiAoKSB7XG4gICAgICAgIHJldHVybiBbXVxuICAgICAgfSxcbiAgICB9KVxuICB9IGNhdGNoIChlcnI6IGFueSkge1xuICAgIGlmIChlcnIudHlwZSA9PT0gU2Vzc2lvbi5FcnJvci5UUllfUkVGUkVTSF9UT0tFTikge1xuICAgICAgcmV0dXJuIHsgcHJvcHM6IHsgZnJvbVN1cGVydG9rZW5zOiAnbmVlZHMtcmVmcmVzaCcgfSB9XG4gICAgfSBlbHNlIGlmIChlcnIudHlwZSA9PT0gU2Vzc2lvbi5FcnJvci5VTkFVVEhPUklTRUQpIHtcbiAgICAgIC8vIHRoaXMgd2lsbCBmb3JjZSB0aGUgZnJvbnRlbmQgdG8gdHJ5IGFuZCByZWZyZXNoIHdoaWNoIHdpbGwgZmFpbFxuICAgICAgLy8gY2xlYXJpbmcgYWxsIGNvb2tpZXMgYW5kIHJlZGlyZWN0aW5nIHRoZSB1c2VyIHRvIHRoZSBsb2dpbiBzY3JlZW4uXG4gICAgICByZXR1cm4geyBwcm9wczogeyBmcm9tU3VwZXJ0b2tlbnM6ICduZWVkcy1yZWZyZXNoJyB9IH1cbiAgICB9XG4gICAgdGhyb3cgZXJyXG4gIH1cblxuICBpZiAoIXNlc3Npb24/LmdldFVzZXJJZCgpKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIHJlZGlyZWN0OiB7XG4gICAgICAgIGRlc3RpbmF0aW9uOiAnL1VzZXIvTG9naW4vVXNlckxvZ2luJyxcbiAgICAgICAgcGVybWFuZW50OiBmYWxzZSxcbiAgICAgIH0sXG4gICAgfVxuICB9XG5cbiAgcmV0dXJuIHtcbiAgICBwcm9wczoge1xuICAgICAgc3ViOiBzZXNzaW9uLmdldFVzZXJJZCgpLFxuICAgIH1cbiAgfVxufVxuXG5cbnR5cGUgUHJvcHMgPSB7XG4gIGlkOiBzdHJpbmcsXG4gIGNsb3NlRWRpdEV2ZW50OiAoKSA9PiB2b2lkLFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBzdWI6IHN0cmluZyxcbn1cblxuZnVuY3Rpb24gVXNlckVkaXRFdmVudChwcm9wczogUHJvcHMpIHtcbiAgY29uc3QgW2NhdGVnb3JpZXMsIHNldENhdGVnb3JpZXNdID0gdXNlU3RhdGU8Q2F0ZWdvcnlUeXBlW10+KFtdKVxuICBjb25zdCBbc2VsZWN0ZWRDYXRlZ29yaWVzLCBzZXRTZWxlY3RlZENhdGVnb3JpZXNdID0gdXNlU3RhdGU8Q2F0ZWdvcnlUeXBlW10+KFtdKVxuICBjb25zdCBbdGl0bGUsIHNldFRpdGxlXSA9IHVzZVN0YXRlPHN0cmluZz4oKVxuICBjb25zdCBbYWxsRGF5LCBzZXRBbGxEYXldID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gIGNvbnN0IFtpc1JlY3VycmluZywgc2V0SXNSZWN1cnJpbmddID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gIGNvbnN0IFtyZWN1cnJpbmdFbmREYXRlLCBzZXRSZWN1cnJpbmdFbmREYXRlXSA9IHVzZVN0YXRlPERhdGU+KG5ldyBEYXRlKCkpXG4gIGNvbnN0IFtmcmVxdWVuY3ksIHNldEZyZXF1ZW5jeV0gPSB1c2VTdGF0ZTxSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZT4oJ2RhaWx5JylcbiAgY29uc3QgW2ludGVydmFsLCBzZXRJbnRlcnZhbF0gPSB1c2VTdGF0ZTxzdHJpbmc+KCcxJylcbiAgY29uc3QgW2FsYXJtcywgc2V0QWxhcm1zXSA9IHVzZVN0YXRlPG51bWJlcltdPihbXSkgLy8gd2lsbCBiZSBudW1iZXIgZm9yIGNyZWF0ZUV2ZW50IGZ1bmN0aW9uXG4gIGNvbnN0IFtub3Rlcywgc2V0Tm90ZXNdID0gdXNlU3RhdGU8c3RyaW5nPigpXG4gIGNvbnN0IFtsb2NhdGlvbiwgc2V0TG9jYXRpb25dID0gdXNlU3RhdGU8c3RyaW5nPigpXG4gIGNvbnN0IFtpc1pvb21BdmFpbGFibGUsIHNldElzWm9vbUF2YWlsYWJsZV0gPSB1c2VTdGF0ZTxib29sZWFuPihmYWxzZSlcbiAgY29uc3QgW2lzR29vZ2xlTWVldEF2YWlsYWJsZSwgc2V0SXNHb29nbGVNZWV0QXZhaWxhYmxlXSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKVxuICBjb25zdCBbem9vbU1lZXQsIHNldFpvb21NZWV0XSA9IHVzZVN0YXRlPGJvb2xlYW4+KClcbiAgY29uc3QgW2dvb2dsZU1lZXQsIHNldEdvb2dsZU1lZXRdID0gdXNlU3RhdGU8Ym9vbGVhbj4oKVxuICBjb25zdCBbem9vbVByaXZhdGVNZWV0aW5nLCBzZXRab29tUHJpdmF0ZU1lZXRpbmddID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gIGNvbnN0IFthdHRlbmRlZXMsIHNldEF0dGVuZGVlc10gPSB1c2VTdGF0ZTxQZXJzb25bXT4oW10pXG4gIGNvbnN0IFt2aXNpYmlsaXR5LCBzZXRWaXNpYmlsaXR5XSA9IHVzZVN0YXRlPFZpc2liaWxpdHlUeXBlPignZGVmYXVsdCcpXG4gIGNvbnN0IFtpc0F0dGVuZGVlcywgc2V0SXNBdHRlbmRlZXNdID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gIGNvbnN0IFthY3RpdmVJbmRleCwgc2V0QWN0aXZlSW5kZXhdID0gdXNlU3RhdGU8bnVtYmVyPigwKVxuICBjb25zdCBbY29tcGxldGVkU3RlcCwgc2V0Q29tcGxldGVkU3RlcF0gPSB1c2VTdGF0ZTxudW1iZXIgfCB1bmRlZmluZWQ+KClcbiAgY29uc3QgW3NlbGVjdGVkQ2FsZW5kYXJJZCwgc2V0U2VsZWN0ZWRDYWxlbmRhcklkXSA9IHVzZVN0YXRlPHN0cmluZz4oKVxuICBjb25zdCBbY2FsZW5kYXIsIHNldENhbGVuZGFyXSA9IHVzZVN0YXRlPENhbGVuZGFyVHlwZT4oKVxuICBjb25zdCBbaXNCcmVhaywgc2V0SXNCcmVha10gPSB1c2VTdGF0ZTxib29sZWFuPihmYWxzZSlcbiAgY29uc3QgW3N0YXJ0RGF0ZSwgc2V0U3RhcnREYXRlXSA9IHVzZVN0YXRlPERhdGU+KG5ldyBEYXRlKCkpXG4gIGNvbnN0IFtlbmREYXRlLCBzZXRFbmREYXRlXSA9IHVzZVN0YXRlPERhdGU+KG5ldyBEYXRlKCkpXG4gIGNvbnN0IFt0cmFuc3BhcmVuY3ksIHNldFRyYW5zcGFyZW5jeV0gPSB1c2VTdGF0ZTxUcmFuc3BhcmVuY3lUeXBlPignb3BhcXVlJylcbiAgY29uc3QgW2lzRXh0ZXJuYWxNZWV0aW5nLCBzZXRJc0V4dGVybmFsTWVldGluZ10gPSB1c2VTdGF0ZTxib29sZWFuPihmYWxzZSlcbiAgY29uc3QgW2lzTWVldGluZywgc2V0SXNNZWV0aW5nXSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKVxuICBjb25zdCBbbW9kaWZpYWJsZSwgc2V0TW9kaWZpYWJsZV0gPSB1c2VTdGF0ZTxib29sZWFuPih0cnVlKVxuICBjb25zdCBbYnlXZWVrRGF5LCBzZXRCeVdlZWtEYXldID0gdXNlU3RhdGU8RGF5W10+KFtdKVxuICBjb25zdCBbb2xkRXZlbnQsIHNldE9sZEV2ZW50XSA9IHVzZVN0YXRlPEV2ZW50VHlwZT4oKVxuXG4gIGNvbnN0IHJvdXRlciA9IHVzZVJvdXRlcigpXG4gIGNvbnN0IHRvYXN0ID0gdXNlVG9hc3QoKVxuICBcbiAgY29uc3QgdXNlcklkID0gcHJvcHM/LnN1YlxuICBjb25zdCBpZCA9IHByb3BzPy5pZFxuICBjb25zdCBjbG9zZUVkaXRFdmVudCA9IHByb3BzPy5jbG9zZUVkaXRFdmVudFxuICBjb25zdCBjbGllbnQgPSBwcm9wcz8uY2xpZW50XG4gIFxuICBjb25zb2xlLmxvZyhpZCwgJyBldmVudElkIHByZXJlbmRlciBpbnNpZGUgdXNlcmVkaXRldmVudCcpXG4gIC8vIGdldCBjYXRlZ29yaWVzXG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgKGFzeW5jKCkgPT4ge1xuICAgICAgdHJ5IHtcbiAgICAgICAgaWYgKCF1c2VySWQgfHwgIWNsaWVudCkge1xuICAgICAgICAgIGNvbnNvbGUubG9nKHVzZXJJZCwgY2xpZW50LCAnbm8gdXNlcklkIG9yIGNsaWVudCcpXG4gICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cbiAgICAgICAgY29uc3QgcmVzdWx0cyA9IGF3YWl0IGxpc3RVc2VyQ2F0ZWdvcmllcyhjbGllbnQsIHVzZXJJZClcblxuICAgICAgICBpZiAoIXJlc3VsdHM/LlswXT8uaWQpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZygnIG5vIGNhdGVnb3JpZXMgYXZhaWxhYmxlJylcbiAgICAgICAgICByZXR1cm5cbiAgICAgICAgfVxuICAgICAgICBzZXRDYXRlZ29yaWVzKHJlc3VsdHMpXG4gICAgICB9IGNhdGNoKGUpIHtcbiAgICAgICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGNhdGVnb3JpZXMnKVxuICAgICAgfVxuICAgIH0pKClcbiAgfSwgW2NsaWVudCwgdXNlcklkXSlcblxuICAvLyBnZXQgZXZlbnQgc2VsZWN0ZWQgY2F0ZWdvcmllc1xuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIChhc3luYyAoKSA9PiB7XG4gICAgICB0cnkge1xuICAgICAgICBpZiAoIWlkIHx8ICFjbGllbnQpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZyh1c2VySWQsIGNsaWVudCwgJ25vIHVzZXJJZCBvciBjbGllbnQnKVxuICAgICAgICAgIHJldHVyblxuICAgICAgICB9XG4gICAgICAgIGNvbnN0IHJlc3VsdHMgPSBhd2FpdCBsaXN0Q2F0ZWdvcmllc0ZvckV2ZW50KGNsaWVudCwgaWQpXG4gICAgICAgIGNvbnNvbGUubG9nKHJlc3VsdHMsICcgbGlzdENhdGVnb3JpZXNGb3JFdmVudCBpbnNpZGUgdXNlcmVkaXRldmVudCcpXG4gICAgICAgIGlmICghcmVzdWx0cz8uWzBdPy5pZCkge1xuICAgICAgICAgIGNvbnNvbGUubG9nKCcgbm8gc2VsZWN0ZWQgY2F0ZWdvcmllcyBhdmFpbGFibGUnKVxuICAgICAgICAgIHJldHVyblxuXG4gICAgICAgIH1cbiAgICAgICAgc2V0U2VsZWN0ZWRDYXRlZ29yaWVzKHJlc3VsdHMpXG4gICAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBzZWxlY3RlZCBjYXRlZ29yaWVzJylcblxuICAgICAgfVxuICAgIH0pKClcbiAgfSwgW2NsaWVudCwgaWQsIHVzZXJJZF0pXG5cbiAgIC8vIGNoZWNrIGlmIHpvb20gYXZhaWxhYmxlXG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgKGFzeW5jICgpID0+IHtcbiAgICAgIGlmICghdXNlcklkIHx8ICFjbGllbnQpIHtcbiAgICAgICAgY29uc29sZS5sb2codXNlcklkLCBjbGllbnQsICdubyB1c2VySWQgb3IgY2xpZW50JylcbiAgICAgICAgcmV0dXJuXG4gICAgICB9XG4gICAgICBjb25zdCBpc0F2YWlsYWJsZSA9IGF3YWl0IHpvb21BdmFpbGFibGUoY2xpZW50LCB1c2VySWQpXG4gICAgICBpZiAoaXNBdmFpbGFibGUpIHtcbiAgICAgICAgc2V0SXNab29tQXZhaWxhYmxlKHRydWUpXG4gICAgICB9XG4gICAgfSkoKVxuICB9LCBbY2xpZW50LCB1c2VySWRdKVxuXG4gICAvLyBjaGVjayBpZiBnb29nbGUgYXZhaWxhYmxlXG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgKGFzeW5jICgpID0+IHtcbiAgICAgIGlmICghdXNlcklkIHx8ICFjbGllbnQpIHtcbiAgICAgICAgY29uc29sZS5sb2codXNlcklkLCBjbGllbnQsICdubyB1c2VySWQgb3IgY2xpZW50JylcbiAgICAgICAgcmV0dXJuXG4gICAgICB9XG4gICAgICBjb25zdCBpc0F2YWlsYWJsZSA9IGF3YWl0IGdvb2dsZU1lZXRBdmFpbGFibGUoY2xpZW50LCB1c2VySWQpXG4gICAgICBpZiAoaXNBdmFpbGFibGUpIHtcbiAgICAgICAgc2V0SXNHb29nbGVNZWV0QXZhaWxhYmxlKGlzQXZhaWxhYmxlKVxuICAgICAgfVxuICAgIH0pKClcbiAgfSwgW2NsaWVudCwgdXNlcklkXSlcblxuICAvLyBnZXQgZXZlbnQgQ2FsZW5kYXIgZWxzZSBnbG9iYWwgcHJpbWFyeSBjYWxlbmRhclxuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIChhc3luYyAoKSA9PiB7ICBcbiAgICAgIGlmICghdXNlcklkIHx8ICFjbGllbnQpIHtcbiAgICAgICAgcmV0dXJuXG4gICAgICB9XG4gICAgICBpZiAoIWlkKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKCcgbm8gZXZlbnRJZCcpXG4gICAgICB9XG5cbiAgICAgIGNvbnN0IGV2ZW50ID0gKGF3YWl0IGNsaWVudC5xdWVyeTx7IEV2ZW50X2J5X3BrOiBFdmVudFR5cGUgfT4oe1xuICAgICAgICBxdWVyeTogZ2V0RXZlbnRCeUlkLFxuICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIGlkOiBpZCxcbiAgICAgICAgfSxcbiAgICAgIH0pKS5kYXRhPy5FdmVudF9ieV9wa1xuICAgICAgaWYgKCFldmVudD8uaWQpIHtcblxuICAgICAgICBjb25zb2xlLmxvZygnIG5vIGV2ZW50IGF2YWlsYWJsZScpXG4gICAgICAgIHJldHVyblxuICAgICAgfVxuICAgICAgY29uc3QgY2FsZW5kYXJEb2MgPSAoYXdhaXQgY2xpZW50LnF1ZXJ5PHsgQ2FsZW5kYXJfYnlfcGs6IENhbGVuZGFyVHlwZSB9Pih7XG4gICAgICAgIHF1ZXJ5OiBnZXRDYWxlbmRhckJ5SWQsXG4gICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgIGlkOiBldmVudD8uY2FsZW5kYXJJZCxcbiAgICAgICAgfSxcbiAgICAgIH0pKS5kYXRhPy5DYWxlbmRhcl9ieV9wa1xuXG4gICAgICBpZiAoIWNhbGVuZGFyRG9jPy5pZCkge1xuICAgICAgICBjb25zdCBjYWxlbmRhciA9IChhd2FpdCBjbGllbnQucXVlcnk8eyBDYWxlbmRhcjogQ2FsZW5kYXJUeXBlW10gfT4oe1xuICAgICAgICAgIHF1ZXJ5OiBnZXRHbG9iYWxQcmltYXJ5Q2FsZW5kYXIsIFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pKS5kYXRhPy5DYWxlbmRhcj8uWzBdXG4gICAgICAgIGlmICghY2FsZW5kYXI/LmlkKSB7XG4gICAgICAgICAgY29uc29sZS5sb2coJyBubyBwcmltYXJ5IGNhbGVuZGFyIGF2YWlsYWJsZScpXG4gICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cbiAgICAgICAgc2V0U2VsZWN0ZWRDYWxlbmRhcklkKGNhbGVuZGFyPy5pZClcbiAgICAgICAgc2V0Q2FsZW5kYXIoY2FsZW5kYXIpXG4gICAgICB9IGVsc2Uge1xuICAgICAgICBzZXRTZWxlY3RlZENhbGVuZGFySWQoY2FsZW5kYXJEb2M/LmlkKVxuICAgICAgICBzZXRDYWxlbmRhcihjYWxlbmRhckRvYylcbiAgICAgIH1cbiAgICB9KSgpXG4gIH0sIFtjbGllbnQsIGlkLCB1c2VySWRdKVxuXG5cbiAgLy8gZ2V0IGFsYXJtc1xuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIChhc3luYyAoKSA9PiB7XG4gICAgICBpZiAoIWlkIHx8ICFjbGllbnQpIHtcbiAgICAgICAgcmV0dXJuXG4gICAgICB9XG4gICAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgbGlzdFJlbWluZGVyc0ZvckV2ZW50KGNsaWVudCwgaWQpXG4gICAgICBpZiAoIXJlc3VsdHM/LlswXT8ubWludXRlcykge1xuICAgICAgICBjb25zb2xlLmxvZygnIG5vIGFsYXJtcyBhdmFpbGFibGUnKVxuICAgICAgICByZXR1cm5cbiAgICAgIH1cbiAgICAgIHNldEFsYXJtcyhyZXN1bHRzPy5tYXAociA9PiByLm1pbnV0ZXMpKVxuICAgIH0pKClcbiAgfSwgW2NsaWVudCwgaWRdKVxuXG4gIFxuICAvLyBnZXQgZXZlbnRcbiAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICAoYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc29sZS5sb2coJyBnZXQgZXZlbnQgdXNlRWZmZWN0IGNhbGxlZCBpbnNpZGUgdXNlcmVkaXRldmVudCcpXG4gICAgICBpZiAoIWlkIHx8ICFjbGllbnQpIHtcbiAgICAgICAgY29uc29sZS5sb2coJ25vIGV2ZW50SWQgb3IgY2xpZW50IGluc2lkZSB1c2VyRWRpdEV2ZW50JylcbiAgICAgICAgcmV0dXJuXG4gICAgICB9XG4gICAgICBjb25zdCBldmVudCA9IChhd2FpdCBjbGllbnQucXVlcnk8eyBFdmVudF9ieV9wazogRXZlbnRUeXBlIH0+KHtcbiAgICAgICAgcXVlcnk6IGdldEV2ZW50QnlJZCxcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICBpZDogaWQsXG4gICAgICAgIH0sXG4gICAgICB9KSkuZGF0YT8uRXZlbnRfYnlfcGtcbiAgICAgIGlmICghZXZlbnQ/LmlkKSB7XG5cbiAgICAgICAgY29uc29sZS5sb2coJyBubyBldmVudCBhdmFpbGFibGUnKVxuICAgICAgICByZXR1cm5cbiAgICAgIH1cbiAgICAgIGNvbnNvbGUubG9nKGV2ZW50LCAnIGV2ZW50IGluc2lkZSB1c2VyZWRpdGV2ZW50JylcbiAgICAgIHNldFRpdGxlKGV2ZW50Py50aXRsZSB8fCBldmVudD8uc3VtbWFyeSlcbiAgICAgIHNldEFsbERheShldmVudD8uYWxsRGF5KVxuICAgICAgc2V0SXNSZWN1cnJpbmcoZXZlbnQ/LnJlY3VycmVuY2U/Lmxlbmd0aCA+IDApXG4gICAgICBpZiAoZXZlbnQ/LnJlY3VycmVuY2VSdWxlPy5lbmREYXRlKSB7XG4gICAgICAgIHNldFJlY3VycmluZ0VuZERhdGUoZGF5anMoZXZlbnQ/LnJlY3VycmVuY2VSdWxlPy5lbmREYXRlPy5zbGljZSgwLCAxOSkpLnR6KGV2ZW50Py50aW1lem9uZSwgdHJ1ZSkudG9EYXRlKCkpXG4gICAgICAgIHNldEZyZXF1ZW5jeShldmVudD8ucmVjdXJyZW5jZVJ1bGU/LmZyZXF1ZW5jeSBhcyBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZSlcbiAgICAgICAgc2V0SW50ZXJ2YWwoYCR7ZXZlbnQ/LnJlY3VycmVuY2VSdWxlPy5pbnRlcnZhbH1gKVxuICAgICAgfVxuICAgICAgc2V0U3RhcnREYXRlKGRheWpzLnR6KGV2ZW50Py5zdGFydERhdGUsIGV2ZW50Py50aW1lem9uZSB8fCBkYXlqcy50ei5ndWVzcygpKS50b0RhdGUoKSlcbiAgICAgIHNldEVuZERhdGUoZGF5anMudHooZXZlbnQ/LmVuZERhdGUsIGV2ZW50Py50aW1lem9uZSB8fCBkYXlqcy50ei5ndWVzcygpKS50b0RhdGUoKSlcbiAgICAgIHNldE5vdGVzKGV2ZW50Py5ub3RlcylcbiAgICAgIHNldExvY2F0aW9uKGV2ZW50Py5sb2NhdGlvbj8udGl0bGUpXG4gICAgICBzZXRWaXNpYmlsaXR5KGV2ZW50Py52aXNpYmlsaXR5KVxuICAgICAgc2V0SXNCcmVhayhldmVudD8uaXNCcmVhaylcbiAgICAgIHNldFRyYW5zcGFyZW5jeShldmVudD8udHJhbnNwYXJlbmN5KVxuICAgICAgc2V0SXNFeHRlcm5hbE1lZXRpbmcoZXZlbnQ/LmlzRXh0ZXJuYWxNZWV0aW5nKVxuICAgICAgc2V0SXNNZWV0aW5nKGV2ZW50Py5pc01lZXRpbmcpXG4gICAgICBzZXRNb2RpZmlhYmxlKGV2ZW50Py5tb2RpZmlhYmxlKVxuICAgICAgc2V0QnlXZWVrRGF5KGV2ZW50Py5ieVdlZWtEYXkgYXMgRGF5W10pXG4gICAgICBzZXRPbGRFdmVudChldmVudClcbiAgICB9KSgpXG4gIH0sIFtjbGllbnQsIGlkXSlcblxuXG4gIC8vIGdldCBjb25mZXJlbmNlIGluIGRiXG4gIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgKGFzeW5jICgpID0+IHtcbiAgICAgIGlmICghaWQgfHwgIWNsaWVudCkge1xuICAgICAgICByZXR1cm5cbiAgICAgIH1cbiAgICAgIGNvbnN0IG9sZEV2ZW50ID0gKGF3YWl0IGNsaWVudC5xdWVyeTx7IEV2ZW50X2J5X3BrOiBFdmVudFR5cGUgfT4oe1xuICAgICAgICBxdWVyeTogZ2V0RXZlbnRCeUlkLFxuICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIGlkOiBpZCxcbiAgICAgICAgfSxcbiAgICAgIH0pKS5kYXRhPy5FdmVudF9ieV9wa1xuICAgICAgaWYgKCFvbGRFdmVudD8uaWQpIHtcbiAgICAgICAgY29uc29sZS5sb2coJyBubyBldmVudCBhdmFpbGFibGUnKVxuICAgICAgICByZXR1cm5cbiAgICAgIH1cblxuICAgICAgaWYgKCFvbGRFdmVudD8uY29uZmVyZW5jZUlkKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKG9sZEV2ZW50Py5jb25mZXJlbmNlSWQsICcgbm8gY29uZmVyZW5jZUlkIGluc2lkZSB1c2VyRWRpdEV2ZW50JylcbiAgICAgICAgcmV0dXJuXG4gICAgICB9XG4gICAgICBjb25zdCBjb25mZXJlbmNlID0gKGF3YWl0IGNsaWVudC5xdWVyeTx7IENvbmZlcmVuY2VfYnlfcGs6IENvbmZlcmVuY2VUeXBlIH0+KHtcbiAgICAgICAgcXVlcnk6IGdldENvbmZlcmVuY2VCeUlkLFxuICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIGlkOiBvbGRFdmVudD8uY29uZmVyZW5jZUlkLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgfSkpLmRhdGE/LkNvbmZlcmVuY2VfYnlfcGtcbiAgICAgIGlmICghY29uZmVyZW5jZT8uaWQpIHtcbiAgICAgICAgY29uc29sZS5sb2coJyBubyBjb25mZXJlbmNlIGF2YWlsYWJsZScpXG4gICAgICAgIHJldHVyblxuICAgICAgfVxuICAgICAgaWYgKGNvbmZlcmVuY2U/LmFwcCA9PT0gJ3pvb20nKSB7XG4gICAgICAgIHNldFpvb21NZWV0KHRydWUpXG4gICAgICB9XG4gICAgICBpZiAoY29uZmVyZW5jZT8uYXBwID09PSAnZ29vZ2xlJykge1xuICAgICAgICBzZXRHb29nbGVNZWV0KHRydWUpXG4gICAgICB9XG5cbiAgICAgIGlmIChjb25mZXJlbmNlPy56b29tUHJpdmF0ZU1lZXRpbmcgPT09IHRydWUpIHtcbiAgICAgICAgc2V0Wm9vbVByaXZhdGVNZWV0aW5nKHRydWUpXG4gICAgICB9XG4gICAgfSkoKVxuICB9LCBbY2xpZW50LCBpZF0pXG5cbiAgLy8gZ2V0IGV2ZW50IGF0dGVuZGVlc1xuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIChhc3luYyAoKSA9PiB7XG4gICAgICBpZiAoIWlkIHx8ICFjbGllbnQpIHtcbiAgICAgICAgcmV0dXJuXG4gICAgICB9XG4gICAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgbGlzdEF0dGVuZGVlc0ZvckV2ZW50KGNsaWVudCwgaWQpXG4gICAgICBpZiAoIXJlc3VsdHM/LlswXT8uaWQpIHtcbiAgICAgICAgY29uc29sZS5sb2coJyBubyBhdHRlbmRlZXMgYXZhaWxhYmxlJylcbiAgICAgICAgcmV0dXJuXG4gICAgICB9XG4gICAgICBzZXRBdHRlbmRlZXMocmVzdWx0cy5tYXAociA9PiAoeyBpZDogci5pZCwgbmFtZTogci5uYW1lLCBlbWFpbHM6IHIuZW1haWxzLCBwaG9uZU51bWJlcnM6IHIucGhvbmVOdW1iZXJzLCBpbUFkZHJlc3Nlczogci5pbUFkZHJlc3NlcywgYWRkaXRpb25hbEd1ZXN0czogci5hZGRpdGlvbmFsR3Vlc3RzLCBvcHRpb25hbDogci5vcHRpb25hbCwgcmVzb3VyY2U6IHIucmVzb3VyY2UgfSBhcyBQZXJzb24pKSlcbiAgICAgIHNldElzQXR0ZW5kZWVzKHRydWUpXG4gICAgfSkoKVxuICB9LCBbY2xpZW50LCBpZF0pXG5cblxuICBjb25zdCB1cGRhdGVFdmVudEZvclVzZXIgPSBhc3luYyAoKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgIC8vIHZhbGlkYXRlIGJlZm9yZSB1cGRhdGVcbiAgICAgIGlmICghdXNlcklkIHx8ICFjbGllbnQpIHtcbiAgICAgICAgY29uc29sZS5sb2coJ25vIHVzZXJJZCBvciBjbGllbnQgaW5zaWRlIHVwZGF0ZUV2ZW50Rm9yVXNlcicpXG4gICAgICAgIHJldHVyblxuICAgICAgfVxuXG4gICAgICBpZiAoIWlkKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKCdubyBldmVudElkIGluc2lkZSB1cGRhdGVFdmVudEZvclVzZXInKVxuICAgICAgICByZXR1cm5cbiAgICAgIH1cblxuICAgICAgaWYgKCFzZWxlY3RlZENhbGVuZGFySWQpIHtcbiAgICAgICAgY29uc29sZS5sb2coJ25vIGNhbGVuZGFySWQgaW5zaWRlIHVwZGF0ZUV2ZW50Rm9yVXNlcicpXG4gICAgICAgIHJldHVyblxuICAgICAgfVxuXG5cblxuICAgICAgY29uc29sZS5sb2coZnJlcXVlbmN5LCBpbnRlcnZhbCwgYnlXZWVrRGF5LCAnIGZyZXF1ZW5jeSwgaW50ZXJ2YWwgYW5kIGJ5V2Vla0RheSBpbnNpZGUgdXBkYXRlRXZlbnRGb3JVc2VyJylcbiAgICAgIGF3YWl0IHVwZGF0ZUV2ZW50KFxuICAgICAgICBpZCxcbiAgICAgICAgZGF5anMoc3RhcnREYXRlKS5mb3JtYXQoKSxcbiAgICAgICAgZGF5anMoZW5kRGF0ZSkuZm9ybWF0KCksXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgY2xpZW50LFxuICAgICAgICBzZWxlY3RlZENhbGVuZGFySWQsXG4gICAgICAgIHNlbGVjdGVkQ2F0ZWdvcmllcz8ubWFwKGNhdGVnb3J5ID0+IGNhdGVnb3J5LmlkKSxcbiAgICAgICAgdGl0bGUsXG4gICAgICAgIGFsbERheSxcbiAgICAgICAgaXNSZWN1cnJpbmcgPyBkYXlqcyhyZWN1cnJpbmdFbmREYXRlKS5mb3JtYXQoKSA6IG51bGwsXG4gICAgICAgIGlzUmVjdXJyaW5nID8gZnJlcXVlbmN5IDogbnVsbCxcbiAgICAgICAgaXNSZWN1cnJpbmcgPyBwYXJzZUludCAoaW50ZXJ2YWwsIDEwKSA6IG51bGwsXG4gICAgICAgIGFsYXJtcyxcbiAgICAgICAgbm90ZXMsXG4gICAgICAgIGxvY2F0aW9uID8geyB0aXRsZTogbG9jYXRpb24gfSA6IHVuZGVmaW5lZCxcbiAgICAgICAgZmFsc2UsXG4gICAgICAgIGZhbHNlLFxuICAgICAgICBmYWxzZSxcbiAgICAgICAgbW9kaWZpYWJsZSxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgZmFsc2UsXG4gICAgICAgIGRheWpzLnR6Lmd1ZXNzKCksXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHpvb21NZWV0LFxuICAgICAgICBnb29nbGVNZWV0LFxuICAgICAgICAnc2NoZWR1bGVkJyxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB6b29tUHJpdmF0ZU1lZXRpbmcsXG4gICAgICAgIGF0dGVuZGVlcyxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIGF0dGVuZGVlcz8uWzBdPy5lbWFpbHM/LlswXT8udmFsdWUgPyAnYWxsJyA6IHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB0aXRsZSxcbiAgICAgICAgdHJhbnNwYXJlbmN5LFxuICAgICAgICB2aXNpYmlsaXR5LFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICBjYWxlbmRhcj8uY29sb3JJZCxcbiAgICAgICAgZGF5anMudHouZ3Vlc3MoKSxcbiAgICAgICAgc2VsZWN0ZWRDYXRlZ29yaWVzPy5bMF0/LmNvbG9yIHx8IG9sZEV2ZW50Py5iYWNrZ3JvdW5kQ29sb3IgfHwgY2FsZW5kYXI/LmJhY2tncm91bmRDb2xvcixcbiAgICAgICAgb2xkRXZlbnQ/LmZvcmVncm91bmRDb2xvciB8fCAgY2FsZW5kYXI/LmZvcmVncm91bmRDb2xvcixcbiAgICAgICAgYWxhcm1zPy5sZW5ndGggPiAwID8gZmFsc2UgOiB0cnVlLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmcsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICBpc01lZXRpbmcsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICBpc0JyZWFrLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdHJ1ZSxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIGFsYXJtcz8ubGVuZ3RoID4gMCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB0cnVlLFxuICAgICAgICB0cnVlLFxuICAgICAgICB0cnVlLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHRydWUsXG4gICAgICAgIHRydWUsXG4gICAgICAgIGRheWpzLmR1cmF0aW9uKGRheWpzKGVuZERhdGUpLmRpZmYoZGF5anMoc3RhcnREYXRlKSkpLmFzTWludXRlcygpLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgJ3VwZGF0ZScsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgYnlXZWVrRGF5LFxuICAgICAgKVxuXG4gICAgICB0b2FzdCh7XG4gICAgICAgIHN0YXR1czogJ3N1Y2Nlc3MnLFxuICAgICAgICB0aXRsZTogJ0V2ZW50IEVkaXRlZCcsXG4gICAgICAgIGRlc2NyaXB0aW9uOiAnRXZlbnQgZWRpdGVkIHN1Y2Nlc3NmdWxseScsXG4gICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgfSlcbiAgICAgIGNsb3NlRWRpdEV2ZW50KClcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICBjb25zb2xlLmxvZyhlLCAnIGNyZWF0ZUV2ZW50Rm9yVXNlcicpXG4gICAgICB0b2FzdCh7XG4gICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgdGl0bGU6ICdFdmVudCBFZGl0aW5nIGZhaWxlZCcsXG4gICAgICAgIGRlc2NyaXB0aW9uOiAnVW5hYmxlIHRvIGVkaXQgZXZlbnQuIFBsZWFzZSB0cnkgYWdhaW4nLFxuICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZSxcbiAgICAgIH0pXG4gICAgfVxuICB9XG5cbiAgY29uc3Qgb25BY3RpdmVJbmRleENoYW5nZWQgPSAoaW5kZXg6IG51bWJlcikgPT4gc2V0QWN0aXZlSW5kZXgoaW5kZXgpXG5cbiAgY29uc3QgZ29Ub1ByZXZTdGVwID0gKCkgPT4ge1xuICAgIGNvbnN0IHByZXZBY3RpdmVJbmRleCA9IGFjdGl2ZUluZGV4XG4gICAgaWYgKCgoYWN0aXZlSW5kZXggLSAxKSA9PT0gMykgJiYgKCFpc1JlY3VycmluZykpIHtcbiAgICAgIHNldEFjdGl2ZUluZGV4KHByZXZBY3RpdmVJbmRleCAtIDIpXG4gICAgfSBlbHNlIHtcbiAgICAgIGNvbnN0IG5ld0FjdGl2ZUluZGV4ID0gcHJldkFjdGl2ZUluZGV4ID09PSAwID8gMCA6IHByZXZBY3RpdmVJbmRleCAtIDFcbiAgICAgIHNldEFjdGl2ZUluZGV4KG5ld0FjdGl2ZUluZGV4KVxuICAgIH1cbiAgICBcbiAgfVxuXG4gIGNvbnN0IHJlbmRlclByZXZCdXR0b24gPSAoKSA9PiB7XG4gICAgaWYgKGFjdGl2ZUluZGV4ID09PSAwKSB7XG4gICAgICByZXR1cm4gPEJveCBwdD17eyBwaG9uZTogJ20nLCB0YWJsZXQ6ICdzJyB9fS8+XG4gICAgfVxuXG4gICAgcmV0dXJuIChcbiAgICA8Qm94IHA9e3sgcGhvbmU6ICdzJywgdGFibGV0OiAnbScgfX0+XG4gICAgICA8QnV0dG9uIG9uQ2xpY2s9e2dvVG9QcmV2U3RlcH0+XG4gICAgICAgIEJhY2tcbiAgICAgIDwvQnV0dG9uPlxuICAgIDwvQm94PlxuICApfVxuICBcbiAgY29uc3QgZ29Ub05leHRTdGVwID0gKCkgPT4ge1xuICAgIGNvbnN0IHByZXZBY3RpdmVJbmRleCA9IGFjdGl2ZUluZGV4XG4gICAgY29uc3QgcHJldkNvbXBsZXRlZFN0ZXAgPSBjb21wbGV0ZWRTdGVwXG4gICAgLyoqXG4gICAgIDAgLSBFZGl0RXZlbnRCYXNlU3RlcFxuICAgICAxIC0gRWRpdEV2ZW50QmFzZVN0ZXAyXG4gICAgIDIgLSBFZGl0RXZlbnRCYXNlU3RlcDNcbiAgICAgMyAtIEVkaXRFdmVudFJlY3VyU3RlcFxuICAgICA0IC0gRWRpdEV2ZW50VmlydHVhbE1lZXRcbiAgICAgNSAtIEVkaXRFdmVudEF0dGVuZGVlc1xuICAgICA2IC0gRWRpdEV2ZW50VmlzaWJpbGl0eUFuZEFsYXJtc1N0ZXBcbiAgICAgNyAtIEVkaXRFdmVudFVwZGF0ZUNhdGVnb3JpZXNcbiAgICAgKi9cbiAgICBpZiAocHJldkFjdGl2ZUluZGV4ID09PSA4KSB7XG4gICAgICByZXR1cm5cbiAgICB9XG4gICAgaWYgKCFpc1JlY3VycmluZyAmJiBpc0F0dGVuZGVlcykge1xuICAgICAgbGV0IG5ld0FjdGl2ZUluZGV4ID0gcHJldkFjdGl2ZUluZGV4ICsgMVxuXG4gICAgICBpZiAocHJldkFjdGl2ZUluZGV4ID09PSAyKSB7XG4gICAgICAgIG5ld0FjdGl2ZUluZGV4ID0gNFxuICAgICAgfVxuXG4gICAgICAvLyB2YWxpZGF0ZSB1c2VyIGNhdGVnb3J5IGxpc3RcbiAgICAgIGlmIChwcmV2QWN0aXZlSW5kZXggPT09IDYpIHtcbiAgICAgICAgaWYgKGNhdGVnb3JpZXM/Lmxlbmd0aCA9PT0gMCkge1xuICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgIHN0YXR1czogJ2luZm8nLFxuICAgICAgICAgICAgdGl0bGU6ICdObyBjYXRlZ29yaWVzIGF2YWlsYWJsZScsXG4gICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1BsZWFzZSBhZGQgYXQgbGVhc3Qgb25lIGNhdGVnb3J5IGluIHlvdXIgc2V0dGluZ3MgaW4gb3JkZXIgdG8gYWRkIHRvIHlvdXIgZXZlbnQnLFxuICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICAgIH0pXG4gICAgICAgICAgIG5ld0FjdGl2ZUluZGV4ID0gOFxuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIGlmIChwcmV2QWN0aXZlSW5kZXggPT09IDgpIHtcbiAgICAgICAgcmV0dXJuXG4gICAgICB9XG5cbiAgICAgIGlmICghcHJldkNvbXBsZXRlZFN0ZXAgfHwgKHByZXZDb21wbGV0ZWRTdGVwIDwgcHJldkFjdGl2ZUluZGV4KSkge1xuICAgICAgICBjb25zdCBuZXdDb21wbGV0ZWRTdGVwID0gcHJldkFjdGl2ZUluZGV4XG4gICAgICAgIHNldENvbXBsZXRlZFN0ZXAobmV3Q29tcGxldGVkU3RlcClcbiAgICAgIH1cblxuICAgICAgaWYgKG5ld0FjdGl2ZUluZGV4ICE9PSBwcmV2QWN0aXZlSW5kZXgpIHtcbiAgICAgICAgcmV0dXJuIHNldEFjdGl2ZUluZGV4KG5ld0FjdGl2ZUluZGV4KVxuICAgICAgfVxuICAgICAgcmV0dXJuXG4gICAgfVxuXG4gICAgaWYgKCFpc0F0dGVuZGVlcyAmJiBpc1JlY3VycmluZykge1xuICAgICAgbGV0IG5ld0FjdGl2ZUluZGV4ID0gcHJldkFjdGl2ZUluZGV4ICsgMVxuXG4gICAgICBpZiAocHJldkFjdGl2ZUluZGV4ID09PSAzKSB7XG4gICAgICAgIG5ld0FjdGl2ZUluZGV4ID0gNlxuICAgICAgfVxuXG4gICAgICAvLyB2YWxpZGF0ZSB1c2VyIGNhdGVnb3J5IGxpc3RcbiAgICAgIGlmIChwcmV2QWN0aXZlSW5kZXggPT09IDYpIHtcbiAgICAgICAgaWYgKGNhdGVnb3JpZXM/Lmxlbmd0aCA9PT0gMCkge1xuICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgIHN0YXR1czogJ2luZm8nLFxuICAgICAgICAgICAgdGl0bGU6ICdObyBjYXRlZ29yaWVzIGF2YWlsYWJsZScsXG4gICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1BsZWFzZSBhZGQgYXQgbGVhc3Qgb25lIGNhdGVnb3J5IGluIHlvdXIgc2V0dGluZ3MgaW4gb3JkZXIgdG8gYWRkIHRvIHlvdXIgZXZlbnQnLFxuICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICAgIH0pXG4gICAgICAgICAgIG5ld0FjdGl2ZUluZGV4ID0gOFxuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIGlmICghcHJldkNvbXBsZXRlZFN0ZXAgfHwgKHByZXZDb21wbGV0ZWRTdGVwIDwgcHJldkFjdGl2ZUluZGV4KSkge1xuICAgICAgICBjb25zdCBuZXdDb21wbGV0ZWRTdGVwID0gcHJldkFjdGl2ZUluZGV4XG4gICAgICAgIHNldENvbXBsZXRlZFN0ZXAobmV3Q29tcGxldGVkU3RlcClcbiAgICAgIH1cblxuICAgICAgaWYgKG5ld0FjdGl2ZUluZGV4ICE9PSBwcmV2QWN0aXZlSW5kZXgpIHtcbiAgICAgICAgcmV0dXJuIHNldEFjdGl2ZUluZGV4KG5ld0FjdGl2ZUluZGV4KVxuICAgICAgfVxuICAgICAgcmV0dXJuXG4gICAgfVxuXG4gICAgaWYgKCFpc0F0dGVuZGVlcyAmJiAhaXNSZWN1cnJpbmcpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdpbnNpZGUgIWlzQXR0ZW5kZWVzICYmICFpc1JlY3VycmluZycpXG4gICAgICBsZXQgbmV3QWN0aXZlSW5kZXggPSBwcmV2QWN0aXZlSW5kZXggKyAxXG5cbiAgICAgIGlmIChwcmV2QWN0aXZlSW5kZXggPT09IDIpIHtcbiAgICAgICAgbmV3QWN0aXZlSW5kZXggPSA2XG4gICAgICB9XG5cbiAgICAgIC8vIHZhbGlkYXRlIHVzZXIgY2F0ZWdvcnkgbGlzdFxuICAgICAgaWYgKHByZXZBY3RpdmVJbmRleCA9PT0gNikge1xuICAgICAgICBpZiAoY2F0ZWdvcmllcz8ubGVuZ3RoID09PSAwKSB7XG4gICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgc3RhdHVzOiAnaW5mbycsXG4gICAgICAgICAgICB0aXRsZTogJ05vIGNhdGVnb3JpZXMgYXZhaWxhYmxlJyxcbiAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnUGxlYXNlIGFkZCBhdCBsZWFzdCBvbmUgY2F0ZWdvcnkgaW4geW91ciBzZXR0aW5ncyBpbiBvcmRlciB0byBhZGQgdG8geW91ciBldmVudCcsXG4gICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICAgICAgfSlcbiAgICAgICAgICAgbmV3QWN0aXZlSW5kZXggPSA4XG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgICAgaWYgKCFwcmV2Q29tcGxldGVkU3RlcCB8fCAocHJldkNvbXBsZXRlZFN0ZXAgPCBwcmV2QWN0aXZlSW5kZXgpKSB7XG4gICAgICAgIGNvbnN0IG5ld0NvbXBsZXRlZFN0ZXAgPSBwcmV2QWN0aXZlSW5kZXhcbiAgICAgICAgc2V0Q29tcGxldGVkU3RlcChuZXdDb21wbGV0ZWRTdGVwKVxuICAgICAgfVxuXG4gICAgICBpZiAobmV3QWN0aXZlSW5kZXggIT09IHByZXZBY3RpdmVJbmRleCkge1xuICAgICAgICByZXR1cm4gc2V0QWN0aXZlSW5kZXgobmV3QWN0aXZlSW5kZXgpXG4gICAgICB9XG4gICAgICByZXR1cm5cbiAgICB9XG5cbiAgICBsZXQgbmV3QWN0aXZlSW5kZXggPSBwcmV2QWN0aXZlSW5kZXggKyAxXG5cbiAgICAvLyB2YWxpZGF0ZSB1c2VyIGNhdGVnb3J5IGxpc3RcbiAgICAgIGlmIChwcmV2QWN0aXZlSW5kZXggPT09IDYpIHtcbiAgICAgICAgaWYgKGNhdGVnb3JpZXM/Lmxlbmd0aCA9PT0gMCkge1xuICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgIHN0YXR1czogJ2luZm8nLFxuICAgICAgICAgICAgdGl0bGU6ICdObyBjYXRlZ29yaWVzIGF2YWlsYWJsZScsXG4gICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1BsZWFzZSBhZGQgYXQgbGVhc3Qgb25lIGNhdGVnb3J5IGluIHlvdXIgc2V0dGluZ3MgaW4gb3JkZXIgdG8gYWRkIHRvIHlvdXIgZXZlbnQnLFxuICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICAgIH0pXG4gICAgICAgICAgIG5ld0FjdGl2ZUluZGV4ID0gOFxuICAgICAgICB9XG4gICAgICB9XG5cbiAgICBpZiAoIXByZXZDb21wbGV0ZWRTdGVwIHx8IChwcmV2Q29tcGxldGVkU3RlcCA8IHByZXZBY3RpdmVJbmRleCkpIHtcbiAgICAgIGNvbnN0IG5ld0NvbXBsZXRlZFN0ZXAgPSBwcmV2QWN0aXZlSW5kZXhcbiAgICAgIHNldENvbXBsZXRlZFN0ZXAobmV3Q29tcGxldGVkU3RlcClcbiAgICB9XG5cbiAgICBpZiAobmV3QWN0aXZlSW5kZXggIT09IHByZXZBY3RpdmVJbmRleCkge1xuICAgICAgc2V0QWN0aXZlSW5kZXgobmV3QWN0aXZlSW5kZXgpXG4gICAgfVxuICB9XG5cbiAgY29uc3QgcmVuZGVyTmV4dEJ1dHRvbiA9ICgpID0+IHtcbiAgICBpZiAoYWN0aXZlSW5kZXggPT09IDgpIHtcbiAgICAgIHJldHVybiA8Qm94IHB0PXt7IHBob25lOiAnbScsIHRhYmxldDogJ3MnIH19Lz5cbiAgICB9XG5cbiAgICByZXR1cm4gKFxuICAgICAgPEJveCBwPXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19PlxuICAgICAgICA8QnV0dG9uIG9uQ2xpY2s9e2dvVG9OZXh0U3RlcH0+XG4gICAgICAgICAgTmV4dFxuICAgICAgICA8L0J1dHRvbj5cbiAgICAgIDwvQm94PlxuICAgIClcbiAgfVxuXG5cbiAgY29uc3QgcmVuZGVyQ3VycmVudFN0ZXAgPSAoKSA9PiB7XG4gICAgLyoqXG4gICAgIDAgLSBDcmVhdGVFdmVudEJhc2VTdGVwXG4gICAgIDEgLSBDcmVhdGVFdmVudEJhc2VTdGVwMlxuICAgICAyIC0gQ3JlYXRlRXZlbnRCYXNlU3RlcDNcbiAgICAgMyAtIENyZWF0ZUV2ZW50UmVjdXJTdGVwXG4gICAgIDQgLSBDcmVhdGVFdmVudFZpcnR1YWxNZWV0XG4gICAgIDUgLSBDcmVhdGVFdmVudEF0dGVuZGVlc1xuICAgICA2IC0gQ3JlYXRlRXZlbnRWaXNpYmlsaXR5QW5kQWxhcm1zU3RlcFxuICAgICA3IC0gQ3JlYXRlRXZlbnRBZGRDYXRlZ29yaWVzXG4gICAgICovXG4gICAgIHN3aXRjaChhY3RpdmVJbmRleCkge1xuICAgICAgY2FzZSAwOlxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgIDxCb3ggc3R5bGU9e3sgd2lkdGg6ICcxMDAlJywgaGVpZ2h0OiAnMTAwJScgfX0gZmxleD17MX0gYWxpZ25JdGVtcz1cImNlbnRlclwiIGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCIgbWluSGVpZ2h0PVwiNzV2aFwiID5cbiAgICAgICAgICAgIDxFZGl0RXZlbnRCYXNlU3RlcFxuICAgICAgICAgICAgICB0aXRsZT17dGl0bGV9XG4gICAgICAgICAgICAgIG5vdGVzPXtub3Rlc31cbiAgICAgICAgICAgICAgbG9jYXRpb249e2xvY2F0aW9ufVxuICAgICAgICAgICAgICBzdGFydERhdGU9e3N0YXJ0RGF0ZX1cbiAgICAgICAgICAgICAgZW5kRGF0ZT17ZW5kRGF0ZX1cbiAgICAgICAgICAgICAgc2V0UGFyZW50VGl0bGU9e3NldFRpdGxlfVxuICAgICAgICAgICAgICBzZXRQYXJlbnROb3Rlcz17c2V0Tm90ZXN9XG4gICAgICAgICAgICAgIHNldFBhcmVudExvY2F0aW9uPXtzZXRMb2NhdGlvbn1cbiAgICAgICAgICAgICAgc2V0UGFyZW50U3RhcnREYXRlPXtzZXRTdGFydERhdGV9XG4gICAgICAgICAgICAgIHNldFBhcmVudEVuZERhdGU9e3NldEVuZERhdGV9XG4gICAgICAgICAgICAvPlxuICAgICAgICAgICAgPEJveCBweD1cIm1cIiB3aWR0aD1cIjkwJVwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiBtdD1cInNcIj5cbiAgICAgICAgICAgICAgICA8VGV4dCB2YXJpYW50PVwiY2FwdGlvblwiIHRleHRBbGlnbj1cImNlbnRlclwiIGNvbG9yPVwidGV4dFNlY29uZGFyeVwiPlxuICAgICAgICAgICAgICAgICAgICBUaXA6IEF0b21pYyBjYW4gbGVhcm4gZnJvbSB5b3VyIHBhc3QgZXZlbnRzISBBZnRlciB0eXBpbmcgYSB0aXRsZSwgc2VlIGlmIEF0b21pYyBzdWdnZXN0cyBkZXRhaWxzIGZyb20gc2ltaWxhciBlbnRyaWVzLiBZb3UgY2FuIGFsc28gJ3RyYWluJyBzcGVjaWZpYyBldmVudHMgdG8gYWN0IGFzIHBvd2VyZnVsIHRlbXBsYXRlcy5cbiAgICAgICAgICAgICAgICAgICAgPFRleHQgdmFyaWFudD1cImxpbmtcIiBvblByZXNzPXsoKSA9PiByb3V0ZXIucHVzaCgnaHR0cHM6Ly9kb2NzLmF0b21pY2xpZmUuYXBwL2RvY3MvZmVhdHVyZXMvc21hcnQtc2NoZWR1bGluZycpfT5cbiAgICAgICAgICAgICAgICAgICAgICAgIHsnICd9TGVhcm4gbW9yZSBhYm91dCBzbWFydCBzY2hlZHVsaW5nXG4gICAgICAgICAgICAgICAgICAgIDwvVGV4dD5cbiAgICAgICAgICAgICAgICA8L1RleHQ+XG4gICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgIDxCb3ggZmxleERpcmVjdGlvbj1cInJvd1wiIGp1c3RpZnlDb250ZW50PVwic3BhY2UtYmV0d2VlblwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiBzdHlsZT17eyB3aWR0aDogJzk1JSd9fT5cbiAgICAgICAgICAgICAgPEJveCAvPlxuICAgICAgICAgICAgICB7cmVuZGVyTmV4dEJ1dHRvbigpfVxuICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgPC9Cb3g+XG4gICAgICAgIClcbiAgICAgIGNhc2UgMTogXG4gICAgICByZXR1cm4gKFxuICAgICAgICAgIDxCb3ggc3R5bGU9e3sgd2lkdGg6ICcxMDAlJyB9fSBmbGV4PXsxfSBhbGlnbkl0ZW1zPVwiY2VudGVyXCIganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgIDxFZGl0RXZlbnRCYXNlU3RlcDJcbiAgICAgICAgICAgICAgYWxsRGF5PXthbGxEYXl9XG4gICAgICAgICAgICAgIGlzUmVjdXJyaW5nPXtpc1JlY3VycmluZ31cbiAgICAgICAgICAgICAgaXNBdHRlbmRlZXM9e2lzQXR0ZW5kZWVzfVxuICAgICAgICAgICAgICBpc0JyZWFrPXtpc0JyZWFrfVxuICAgICAgICAgICAgICBzZXRQYXJlbnRBbGxEYXk9e3NldEFsbERheX1cbiAgICAgICAgICAgICAgc2V0UGFyZW50SXNSZWN1cnJpbmc9e3NldElzUmVjdXJyaW5nfVxuICAgICAgICAgICAgICBzZXRQYXJlbnRJc0F0dGVuZGVlcz17c2V0SXNBdHRlbmRlZXN9XG4gICAgICAgICAgICAgIHNldFBhcmVudElzQnJlYWs9e3NldElzQnJlYWt9ICAgICAgICBcbiAgICAgICAgICAgIC8+XG4gICAgICAgICAgICA8Qm94IGZsZXhEaXJlY3Rpb249XCJyb3dcIiBqdXN0aWZ5Q29udGVudD1cInNwYWNlLWJldHdlZW5cIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgIHtyZW5kZXJQcmV2QnV0dG9uKCl9XG4gICAgICAgICAgICAgIHtyZW5kZXJOZXh0QnV0dG9uKCl9XG4gICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICA8L0JveD5cbiAgICAgIClcbiAgICAgIGNhc2UgMjpcbiAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgIDxCb3ggc3R5bGU9e3sgd2lkdGg6ICcxMDAlJyB9fSBmbGV4PXsxfSBhbGlnbkl0ZW1zPVwiY2VudGVyXCIganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgICA8RWRpdEV2ZW50QmFzZVN0ZXAzXG4gICAgICAgICAgICAgICBtb2RpZmlhYmxlPXttb2RpZmlhYmxlfVxuICAgICAgICAgICAgICAgc2V0UGFyZW50TW9kaWZpYWJsZT17c2V0TW9kaWZpYWJsZX1cbiAgICAgICAgICAgICAgIGlzTWVldGluZz17aXNNZWV0aW5nfVxuICAgICAgICAgICAgICAgc2V0UGFyZW50SXNNZWV0aW5nPXtzZXRJc01lZXRpbmd9XG4gICAgICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZz17aXNFeHRlcm5hbE1lZXRpbmd9XG4gICAgICAgICAgICAgICBzZXRQYXJlbnRJc0V4dGVybmFsTWVldGluZz17c2V0SXNFeHRlcm5hbE1lZXRpbmd9XG4gICAgICAgICAgICAgICB0cmFuc3BhcmVuY3k9e3RyYW5zcGFyZW5jeX1cbiAgICAgICAgICAgICAgIHNldFBhcmVudFRyYW5zcGFyZW5jeT17c2V0VHJhbnNwYXJlbmN5fSAgXG4gICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICAgPEJveCBmbGV4RGlyZWN0aW9uPVwicm93XCIganVzdGlmeUNvbnRlbnQ9XCJzcGFjZS1iZXR3ZWVuXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgICB7cmVuZGVyUHJldkJ1dHRvbigpfVxuICAgICAgICAgICAgICB7cmVuZGVyTmV4dEJ1dHRvbigpfVxuICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgIDwvQm94PlxuICAgICAgICAgKVxuICAgICAgY2FzZSAzOlxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgIDxCb3ggc3R5bGU9e3sgd2lkdGg6ICcxMDAlJyB9fSBmbGV4PXsxfSBhbGlnbkl0ZW1zPVwiY2VudGVyXCIganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgIDxFZGl0RXZlbnRSZWN1clN0ZXBcbiAgICAgICAgICAgICAgcmVjdXJyaW5nRW5kRGF0ZT17cmVjdXJyaW5nRW5kRGF0ZX1cbiAgICAgICAgICAgICAgc2V0UGFyZW50UmVjdXJyaW5nRW5kRGF0ZT17c2V0UmVjdXJyaW5nRW5kRGF0ZX1cbiAgICAgICAgICAgICAgZnJlcXVlbmN5PXtmcmVxdWVuY3l9XG4gICAgICAgICAgICAgIHNldFBhcmVudEZyZXF1ZW5jeT17c2V0RnJlcXVlbmN5fVxuICAgICAgICAgICAgICBpbnRlcnZhbD17aW50ZXJ2YWx9XG4gICAgICAgICAgICAgIHNldFBhcmVudEludGVydmFsPXtzZXRJbnRlcnZhbH1cbiAgICAgICAgICAgICAgYnlXZWVrRGF5PXtieVdlZWtEYXl9XG4gICAgICAgICAgICAgIHNldFBhcmVudEJ5V2Vla0RheT17c2V0QnlXZWVrRGF5fVxuICAgICAgICAgICAgLz5cbiAgICAgICAgICAgIDxCb3ggZmxleERpcmVjdGlvbj1cInJvd1wiIGp1c3RpZnlDb250ZW50PVwic3BhY2UtYmV0d2VlblwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgICAge3JlbmRlclByZXZCdXR0b24oKX1cbiAgICAgICAgICAgICAge3JlbmRlck5leHRCdXR0b24oKX1cbiAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgIDwvQm94PlxuICAgICAgICApXG4gICAgICBjYXNlIDQ6XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgPEJveCBzdHlsZT17eyB3aWR0aDogJzEwMCUnIH19IGZsZXg9ezF9IGFsaWduSXRlbXM9XCJjZW50ZXJcIiBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiPlxuICAgICAgICAgICAgPEVkaXRFdmVudFZpcnR1YWxNZWV0XG4gICAgICAgICAgICAgIGlzWm9vbUF2YWlsYWJsZT17aXNab29tQXZhaWxhYmxlfVxuICAgICAgICAgICAgICBpc0dvb2dsZU1lZXRBdmFpbGFibGU9e2lzR29vZ2xlTWVldEF2YWlsYWJsZX1cbiAgICAgICAgICAgICAgem9vbU1lZXQ9e3pvb21NZWV0fVxuICAgICAgICAgICAgICBnb29nbGVNZWV0PXtnb29nbGVNZWV0fVxuICAgICAgICAgICAgICBzZXRQYXJlbnRab29tTWVldD17c2V0Wm9vbU1lZXR9XG4gICAgICAgICAgICAgIHNldFBhcmVudEdvb2dsZU1lZXQ9e3NldEdvb2dsZU1lZXR9XG4gICAgICAgICAgICAgIHpvb21Qcml2YXRlTWVldGluZz17em9vbVByaXZhdGVNZWV0aW5nfVxuICAgICAgICAgICAgICBzZXRQYXJlbnRab29tUHJpdmF0ZU1lZXRpbmc9e3NldFpvb21Qcml2YXRlTWVldGluZ31cbiAgICAgICAgICAgIC8+XG4gICAgICAgICAgICA8Qm94IGZsZXhEaXJlY3Rpb249XCJyb3dcIiBqdXN0aWZ5Q29udGVudD1cInNwYWNlLWJldHdlZW5cIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgIHtyZW5kZXJQcmV2QnV0dG9uKCl9XG4gICAgICAgICAgICAgIHtyZW5kZXJOZXh0QnV0dG9uKCl9XG4gICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICA8L0JveD5cbiAgICAgICAgKVxuICAgICAgY2FzZSA1OlxuICAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICA8Qm94IHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0gZmxleD17MX0gYWxpZ25JdGVtcz1cImNlbnRlclwiIGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCI+XG4gICAgICAgICAgICA8RWRpdEV2ZW50QXR0ZW5kZWVzXG4gICAgICAgICAgICAgIGF0dGVuZGVlcz17YXR0ZW5kZWVzfVxuICAgICAgICAgICAgICBzZXRQYXJlbnRBdHRlbmRlZXM9e3NldEF0dGVuZGVlc31cbiAgICAgICAgICAgICAgdXNlcklkPXt1c2VySWR9XG4gICAgICAgICAgICAgIGNsaWVudD17Y2xpZW50fVxuICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICAgPEJveCBmbGV4RGlyZWN0aW9uPVwicm93XCIganVzdGlmeUNvbnRlbnQ9XCJzcGFjZS1iZXR3ZWVuXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgICB7cmVuZGVyUHJldkJ1dHRvbigpfVxuICAgICAgICAgICAgICB7cmVuZGVyTmV4dEJ1dHRvbigpfVxuICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgPC9Cb3g+XG4gICAgICAgIClcbiAgICAgIGNhc2UgNjpcbiAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgPEJveCBzdHlsZT17eyB3aWR0aDogJzEwMCUnIH19IGZsZXg9ezF9IGFsaWduSXRlbXM9XCJjZW50ZXJcIiBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiPlxuICAgICAgICAgICAgPEVkaXRFdmVudFZpc2liaWxpdHlBbmRBbGFybXNTdGVwXG4gICAgICAgICAgICAgIGFsYXJtcz17YWxhcm1zfVxuICAgICAgICAgICAgICBzZXRQYXJlbnRBbGFybXM9e3NldEFsYXJtc31cbiAgICAgICAgICAgICAgdmlzaWJpbGl0eT17dmlzaWJpbGl0eX1cbiAgICAgICAgICAgICAgc2V0UGFyZW50VmlzaWJpbGl0eT17c2V0VmlzaWJpbGl0eX1cbiAgICAgICAgICAgICAgdXNlcklkPXt1c2VySWR9XG4gICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICA8Qm94IGZsZXhEaXJlY3Rpb249XCJyb3dcIiBqdXN0aWZ5Q29udGVudD1cInNwYWNlLWJldHdlZW5cIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICB7cmVuZGVyUHJldkJ1dHRvbigpfVxuICAgICAgICAgICAgICAge3JlbmRlck5leHRCdXR0b24oKX1cbiAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICA8L0JveD5cbiAgICAgICAgIClcbiAgICAgIGNhc2UgNzpcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICA8Qm94IHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0gZmxleD17MX0gYWxpZ25JdGVtcz1cImNlbnRlclwiIGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCI+XG4gICAgICAgICAgICA8RWRpdEV2ZW50VXBkYXRlQ2F0ZWdvcmllc1xuICAgICAgICAgICAgICBjYXRlZ29yaWVzPXtjYXRlZ29yaWVzfVxuICAgICAgICAgICAgICBzZXRQYXJlbnRTZWxlY3RlZENhdGVnb3JpZXM9e3NldFNlbGVjdGVkQ2F0ZWdvcmllc31cbiAgICAgICAgICAgICAgc2VsZWN0ZWRDYXRlZ29yaWVzPXtzZWxlY3RlZENhdGVnb3JpZXN9XG4gICAgICAgICAgICAvPlxuICAgICAgICAgICAgPEJveCBmbGV4RGlyZWN0aW9uPVwicm93XCIganVzdGlmeUNvbnRlbnQ9XCJzcGFjZS1iZXR3ZWVuXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgICB7cmVuZGVyUHJldkJ1dHRvbigpfVxuICAgICAgICAgICAgICB7cmVuZGVyTmV4dEJ1dHRvbigpfVxuICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgPC9Cb3g+XG4gICAgICAgICkgICAgICAgIFxuICAgICAgY2FzZSA4OiBcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICA8Qm94IGZsZXg9ezF9IGFsaWduSXRlbXM9XCJjZW50ZXJcIiBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiPlxuICAgICAgICAgICAgPEJveCBmbGV4PXsxfSBzdHlsZT17eyB3aWR0aDogJzEwMCUnIH19IHA9e3sgcGhvbmU6ICdzJywgdGFibGV0OiAnbScgfX0ganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCIgbWluSGVpZ2h0PVwiNjV2aFwiIG1heEhlaWdodD1cIjY1dmhcIj5cbiAgICAgICAgICAgICAgPEJveCBwPXt7IHBob25lOiAnbScsIHRhYmxldDogJ2wnfX0+XG4gICAgICAgICAgICAgICAgPFRleHQgdmFyaWFudD1cInN1YmhlYWRlck5vcm1hbFwiPlxuICAgICAgICAgICAgICAgICAgVXBkYXRlIEV2ZW50XG4gICAgICAgICAgICAgICAgPC9UZXh0PlxuICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgICAgPEJveCBwdD17eyBwaG9uZTogJ20nLCB0YWJsZXQ6ICdsJyB9fT5cbiAgICAgICAgICAgICAgICA8QnV0dG9uIG9uQ2xpY2s9e3VwZGF0ZUV2ZW50Rm9yVXNlcn0+XG4gICAgICAgICAgICAgICAgICBVcGRhdGVcbiAgICAgICAgICAgICAgICA8L0J1dHRvbj5cbiAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgIDxCb3ggZmxleERpcmVjdGlvbj1cInJvd1wiIGp1c3RpZnlDb250ZW50PVwic3BhY2UtYmV0d2VlblwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiBzdHlsZT17eyB3aWR0aDogJzc1JScgfX0+XG4gICAgICAgICAgICAgIHtyZW5kZXJQcmV2QnV0dG9uKCl9XG4gICAgICAgICAgICAgIDxCb3ggLz5cbiAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgIDwvQm94PlxuICAgICAgICApXG4gICAgICAgZGVmYXVsdDpcbiAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgIDxCb3gganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgPFJlZ3VsYXJDYXJkPlxuICAgICAgICAgICAgICAgPFRleHQgdmFyaWFudD1cImhlYWRlclwiPlxuICAgICAgICAgICAgICAgICBPb3BzLi4uIHNvbWV0aGluZyB3ZW50IHdyb25nXG4gICAgICAgICAgICAgICA8L1RleHQ+XG4gICAgICAgICAgICAgPC9SZWd1bGFyQ2FyZD5cbiAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICApXG4gICAgIH1cbiAgfVxuXG4gIHJldHVybiAoXG4gICAgPEJveCBmbGV4PXsxfSBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiB3aWR0aD1cIjEwMCVcIiBoZWlnaHQ9XCIxMDAlXCIgbWluSGVpZ2h0PVwiODB2aFwiPlxuICAgICAgPEJveCBmbGV4PXsxfSBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiB3aWR0aD1cIjEwMCVcIiBoZWlnaHQ9XCIxMDAlXCIgbWluSGVpZ2h0PVwiODB2aFwiPlxuICAgICAgICA8V2l6YXJkXG4gICAgICAgICAgaXRlbXM9e1tcbiAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgICAgaW5kZXg6IDAsXG4gICAgICAgICAgICAgICAgICBsYWJlbDogJ1VwZGF0ZSBCYXNlJyxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgICAgaW5kZXg6IDEsXG4gICAgICAgICAgICAgICAgICBsYWJlbDogJ0NvbnRpbnVlIEJhc2UnLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICBpbmRleDogMixcbiAgICAgICAgICAgICAgICAgIGxhYmVsOiAnQ29udGludWUgQmFzZScsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgICAgaW5kZXg6IDMsXG4gICAgICAgICAgICAgICAgICBsYWJlbDogJ1VwZGF0ZSBSZWN1cnJlbmNlJyxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICBpbmRleDogNCxcbiAgICAgICAgICAgICAgICAgIGxhYmVsOiAnVXBkYXRlIFZpcnR1YWwgTWVldCcsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgICAgaW5kZXg6IDUsXG4gICAgICAgICAgICAgICAgICBsYWJlbDogJ1VwZGF0ZSBFdmVudCBBdHRlbmRlZXMnLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICBpbmRleDogNixcbiAgICAgICAgICAgICAgICAgIGxhYmVsOiAnVXBkYXRlIFZpc2liaWxpdHkgQW5kIEFsYXJtcycsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICAgIGluZGV4OiA3LFxuICAgICAgICAgICAgICAgICAgbGFiZWw6ICdVcGRhdGUgQ2F0ZWdvcmllcyBmb3IgRXZlbnQnLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICBpbmRleDogOCxcbiAgICAgICAgICAgICAgICAgIGxhYmVsOiAnVXBkYXRlIEV2ZW50JyxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgXG4gICAgICAgICAgXX1cblxuICAgICAgICAgIGNvbXBsZXRlZD17Y29tcGxldGVkU3RlcH1cbiAgICAgICAgICBhY3RpdmVJbmRleD17YWN0aXZlSW5kZXh9XG4gICAgICAgIC8+XG4gICAgICAgIHtyZW5kZXJDdXJyZW50U3RlcCgpfVxuICAgICAgPC9Cb3g+XG4gICAgICA8Qm94PlxuICAgICAgICA8YnV0dG9uIGNsYXNzTmFtZT1cImJ0biBidG4tbGluayBuby11bmRlcmxpbmUgaG92ZXI6bm8tdW5kZXJsaW5lXCIgb25DbGljaz17Y2xvc2VFZGl0RXZlbnR9PlxuICAgICAgICAgICAgQ2xvc2VcbiAgICAgICAgPC9idXR0b24+XG4gICAgICA8L0JveD5cbiAgICA8L0JveD5cbiAgKVxufVxuXG5leHBvcnQgZGVmYXVsdCBVc2VyRWRpdEV2ZW50XG5cblxuXG4iXX0=