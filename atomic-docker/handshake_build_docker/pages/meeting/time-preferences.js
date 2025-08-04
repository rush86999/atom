"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const uuid_1 = require("uuid");
const modal_time_preferences_1 = __importDefault(require("./modal-time-preferences"));
const date_fns_1 = require("date-fns");
const dayjs_1 = __importDefault(require("dayjs"));
const isoWeek_1 = __importDefault(require("dayjs/plugin/isoWeek"));
const duration_1 = __importDefault(require("dayjs/plugin/duration"));
const isBetween_1 = __importDefault(require("dayjs/plugin/isBetween"));
const timezone_1 = __importDefault(require("dayjs/plugin/timezone"));
const utc_1 = __importDefault(require("dayjs/plugin/utc"));
const customParseFormat_1 = __importDefault(require("dayjs/plugin/customParseFormat"));
const constants_1 = require("@lib/constants");
const react_2 = require("@chakra-ui/react");
const react_datepicker_1 = __importDefault(require("react-datepicker"));
const axios_1 = __importDefault(require("axios"));
const lodash_1 = __importDefault(require("lodash"));
const io5_1 = require("react-icons/io5");
dayjs_1.default.extend(isoWeek_1.default);
dayjs_1.default.extend(duration_1.default);
dayjs_1.default.extend(isBetween_1.default);
dayjs_1.default.extend(timezone_1.default);
dayjs_1.default.extend(utc_1.default);
dayjs_1.default.extend(customParseFormat_1.default);
const MeetingAssistTimePreferences = (props) => {
    const [selectedDate, setSelectedDate] = (0, react_1.useState)(new Date());
    const [meetingAttendees, setMeetingAttendees] = (0, react_1.useState)();
    const [meetingAssist, setMeetingAssist] = (0, react_1.useState)();
    const [oldPreferredTimes, setOldPreferredTimes] = (0, react_1.useState)();
    const [newPreferredTimes, setNewPreferredTimes] = (0, react_1.useState)();
    const [preferredTimesRemoved, setPreferredTimesRemoved] = (0, react_1.useState)();
    const [preferredTimesUI, setPreferredTimesUI] = (0, react_1.useState)();
    const [minDate, setMinDate] = (0, react_1.useState)(new Date());
    const [maxDate, setMaxDate] = (0, react_1.useState)((0, dayjs_1.default)().add(5, 'd').toDate());
    const [availableSlotsByDate, setAvailableSlotsByDate] = (0, react_1.useState)();
    const [meetingAlreadyCreated, setMeetingAlreadyCreated] = (0, react_1.useState)();
    const [isHost, setIsHost] = (0, react_1.useState)(false);
    const [customPreferredTimes, setCustomPreferredTimes] = (0, react_1.useState)();
    const [slotDuration, setSlotDuration] = (0, react_1.useState)(30);
    const [hostPreferences, setHostPreferences] = (0, react_1.useState)();
    const { isOpen, onOpen, onClose } = (0, react_2.useDisclosure)();
    const toast = (0, react_2.useToast)();
    const meetingId = props?.meetingId;
    const attendeeId = props?.attendeeId;
    const preferredTimesEndRef = (0, react_1.useRef)(null);
    const convertPTR2PDR = (pt) => ({
        ...pt,
        startTime: (0, dayjs_1.default)().hour(parseInt(pt.startTime.slice(0, 2), 10)).minute(parseInt(pt.startTime.slice(3), 10)).format(),
        endTime: (0, dayjs_1.default)().hour(parseInt(pt.endTime.slice(0, 2), 10)).minute(parseInt(pt.endTime.slice(3), 10)).format(),
    });
    const convertPDR2PTR = (pd) => ({
        ...pd,
        startTime: (0, dayjs_1.default)(pd.startTime).format('HH:mm'),
        endTime: (0, dayjs_1.default)(pd.endTime).format('HH:mm'),
    });
    (0, react_1.useEffect)(() => {
        const convertPreferredTimesFromAttendeeTimeZoneToUserTimeZone = (preferredTimesInAttendeeZone, attendees) => {
            return (preferredTimesInAttendeeZone?.map(pt => {
                const foundAttendee = attendees.find(a => (a?.id === pt?.attendeeId));
                if (foundAttendee?.id) {
                    const newPt = {
                        ...pt,
                        startTime: (0, dayjs_1.default)().hour(parseInt(pt?.startTime.slice(0, 2), 10)).minute(parseInt(pt?.startTime.slice(3), 10)).tz(foundAttendee?.timezone, true).tz(dayjs_1.default.tz.guess()).format(),
                        endTime: (0, dayjs_1.default)().hour(parseInt(pt?.endTime.slice(0, 2), 10)).minute(parseInt(pt?.endTime.slice(3), 10)).tz(foundAttendee?.timezone, true).tz(dayjs_1.default.tz.guess()).format(),
                    };
                    return newPt;
                }
                return null;
            })?.filter(e => (e !== null)));
        };
        (async () => {
            try {
                if (!meetingId) {
                    toast({
                        title: 'No meeting id present',
                        description: 'Seems like there is no meeting id to allow time preference selection',
                        status: 'error',
                        duration: 9000,
                        isClosable: true
                    });
                    return;
                }
                const oldMeetingAssist = (await axios_1.default.post('/api/time-preferences', {
                    method: 'getMeetingAssist',
                    variables: {
                        id: meetingId,
                    },
                }))?.data;
                if (!oldMeetingAssist || (!(oldMeetingAssist?.id))) {
                    toast({
                        title: 'No meeting present',
                        description: 'Seems like there is no meeting to allow time preference selection',
                        status: 'error',
                        duration: 9000,
                        isClosable: true
                    });
                    return;
                }
                if (!oldMeetingAssist?.timezone) {
                    console.log(oldMeetingAssist?.timezone, ' oldMeetingAssist?.timezone not present');
                    toast({
                        title: 'No meeting present',
                        description: 'Seems like there is no meeting to allow time preference selection',
                        status: 'error',
                        duration: 9000,
                        isClosable: true
                    });
                    return;
                }
                if (!oldMeetingAssist?.windowStartDate) {
                    console.log(oldMeetingAssist?.windowStartDate, ' oldMeetingAssist?.windowStartDate not present');
                    toast({
                        title: 'No meeting present',
                        description: 'Seems like there is no meeting to allow time preference selection',
                        status: 'error',
                        duration: 9000,
                        isClosable: true
                    });
                    return;
                }
                if (!oldMeetingAssist?.windowEndDate) {
                    console.log(oldMeetingAssist?.windowEndDate, ' oldMeetingAssist?.windowEndDate not present');
                    toast({
                        title: 'No meeting present',
                        description: 'Seems like there is no meeting to allow time preference selection',
                        status: 'error',
                        duration: 9000,
                        isClosable: true
                    });
                    return;
                }
                if (!oldMeetingAssist?.userId) {
                    console.log(' no userId present inside oldMeetingAssist');
                    toast({
                        title: 'No meeting present',
                        description: 'Seems like there is no meeting to allow time preference selection',
                        status: 'error',
                        duration: 9000,
                        isClosable: true
                    });
                    return;
                }
                console.log(oldMeetingAssist, ' oldMeetingAssist');
                setMeetingAssist(oldMeetingAssist);
                setMinDate((0, dayjs_1.default)(oldMeetingAssist?.windowStartDate?.slice(0, 19)).tz(oldMeetingAssist?.timezone, true).tz(dayjs_1.default.tz.guess()).toDate());
                setMaxDate((0, dayjs_1.default)(oldMeetingAssist?.windowEndDate?.slice(0, 19)).tz(oldMeetingAssist?.timezone, true).tz(dayjs_1.default.tz.guess()).toDate());
                setSelectedDate((0, dayjs_1.default)(oldMeetingAssist?.windowStartDate?.slice(0, 19)).tz(oldMeetingAssist?.timezone, true).tz(dayjs_1.default.tz.guess()).toDate());
                const attendees = (await axios_1.default.post('/api/time-preferences', {
                    method: 'listMeetingAssistAttendeesGivenMeetingId',
                    variables: {
                        meetingId,
                    },
                }))?.data;
                if (!attendees || (!(attendees?.length > 0))) {
                    console.log('there are no attendees inside time preferences');
                    toast({
                        title: 'No attendees present',
                        description: 'Seems like there are no attendees to confirm a meeting',
                        status: 'error',
                        duration: 9000,
                        isClosable: true
                    });
                    return;
                }
                setMeetingAttendees(attendees);
                const externalAttendees = attendees.filter(a => !!a?.externalAttendee);
                const internalAttendees = attendees.filter(a => !a?.externalAttendee);
                const meetingAssistEventsInUserTimezone = [];
                for (const externalAttendee of externalAttendees) {
                    const oldMeetingAssistEvents = (await axios_1.default.post('/api/time-preferences', {
                        method: 'listMeetingAssistEventsForAttendeeGivenDates',
                        variables: {
                            attendeeId: externalAttendee?.id,
                            hostStartDate: oldMeetingAssist?.windowStartDate,
                            hostEndDate: oldMeetingAssist?.windowEndDate,
                            userTimezone: externalAttendee?.timezone,
                            hostTimezone: oldMeetingAssist?.timezone,
                        },
                    }))?.data;
                    console.log(oldMeetingAssistEvents, ' oldMeetingAssistEvents');
                    if (!oldMeetingAssistEvents || (!(oldMeetingAssistEvents?.length > 0))) {
                        continue;
                    }
                    const oldMeetingAssistEventsInUserTimezone = oldMeetingAssistEvents?.map(e => ({
                        ...e,
                        startDate: (0, dayjs_1.default)(e?.startDate.slice(0, 19)).tz(e?.timezone, true).tz(dayjs_1.default.tz.guess()).format(),
                        endDate: (0, dayjs_1.default)(e?.endDate.slice(0, 19)).tz(e?.timezone, true).tz(dayjs_1.default.tz.guess()).format(),
                        timezone: dayjs_1.default.tz.guess(),
                    }));
                    meetingAssistEventsInUserTimezone.push(...oldMeetingAssistEventsInUserTimezone);
                }
                const eventsInUserTimezone = [];
                for (const internalAttendee of internalAttendees) {
                    const oldEventsInEventTimezone = (await axios_1.default.post('/api/time-preferences', {
                        method: 'listEventsForUserGivenDates',
                        variables: {
                            userId: internalAttendee?.userId,
                            hostStartDate: oldMeetingAssist?.windowStartDate,
                            hostEndDate: oldMeetingAssist?.windowEndDate,
                            userTimezone: internalAttendee?.timezone,
                            hostTimezone: oldMeetingAssist?.timezone,
                        },
                    }))?.data;
                    console.log(oldEventsInEventTimezone, ' oldEventsInEventTimezone');
                    if (!oldEventsInEventTimezone || (!(oldEventsInEventTimezone?.length > 0))) {
                        continue;
                    }
                    const oldEventsInUserTimezone = oldEventsInEventTimezone?.map(e => ({
                        ...e,
                        startDate: (0, dayjs_1.default)(e?.startDate.slice(0, 19)).tz(e?.timezone, true).tz(dayjs_1.default.tz.guess()).format(),
                        endDate: (0, dayjs_1.default)(e?.endDate.slice(0, 19)).tz(e?.timezone, true).tz(dayjs_1.default.tz.guess()).format(),
                        timezone: dayjs_1.default.tz.guess(),
                    }));
                    eventsInUserTimezone.push(...oldEventsInUserTimezone);
                }
                const preferredTimesInAttendeeZone = (await axios_1.default.post('/api/time-preferences', {
                    method: 'listMeetingAssistPreferredTimeRangesGivenMeetingId',
                    variables: {
                        meetingId,
                    },
                }))?.data;
                if (preferredTimesInAttendeeZone && (preferredTimesInAttendeeZone?.length > 0)) {
                    const preferredTimesInUserZone = convertPreferredTimesFromAttendeeTimeZoneToUserTimeZone(preferredTimesInAttendeeZone, attendees);
                    if (!preferredTimesInUserZone?.[0]?.id) {
                        console.log(' unable to form preferredTimesInUserZone');
                        return;
                    }
                    setOldPreferredTimes(preferredTimesInUserZone?.map(pt => ({ ...pt, dayOfWeek: !pt?.dayOfWeek ? -1 : pt?.dayOfWeek })));
                    setPreferredTimesUI(preferredTimesInUserZone?.map(pt => ({ ...pt, dayOfWeek: !pt?.dayOfWeek ? -1 : pt?.dayOfWeek })));
                }
                const oldHostPreferences = (await axios_1.default.post('/api/time-preferences', {
                    method: 'getUserPreferences',
                    variables: {
                        userId: oldMeetingAssist?.userId,
                    },
                }))?.data;
                if (!oldHostPreferences?.id) {
                    console.log('no hostPreferences present');
                    return;
                }
                const oldSlotDuration = oldMeetingAssist?.duration;
                const notAvailableSlots = [];
                const currentTimezone = dayjs_1.default.tz.guess();
                const notAvailableFromMeetingAssists = meetingAssistEventsInUserTimezone?.map(me => ({
                    startDate: me?.startDate,
                    endDate: me?.endDate,
                }));
                if (notAvailableFromMeetingAssists?.[0]?.startDate) {
                    notAvailableSlots.push(...notAvailableFromMeetingAssists);
                }
                const notAvailableFromEvents = eventsInUserTimezone?.map(e => ({
                    startDate: e?.startDate,
                    endDate: e?.endDate,
                }));
                if (notAvailableFromEvents?.[0]?.startDate) {
                    notAvailableSlots.push(...notAvailableFromEvents);
                }
                setSlotDuration(oldSlotDuration);
                setHostPreferences(oldHostPreferences);
                console.log(notAvailableSlots, ' notAvailableSlots');
                const newAvailableSlotsByDate = (await axios_1.default.post('/api/time-preferences', {
                    method: 'generateAvailableSlotsforTimeWindow',
                    variables: {
                        windowStartDate: oldMeetingAssist?.windowStartDate,
                        windowEndDate: oldMeetingAssist?.windowEndDate,
                        slotDuration: oldSlotDuration,
                        hostPreferences: oldHostPreferences,
                        hostTimezone: oldMeetingAssist?.timezone,
                        userTimezone: currentTimezone,
                        notAvailableSlotsInUserTimezone: notAvailableSlots?.length > 0 ? notAvailableSlots : undefined,
                    },
                }))?.data;
                setAvailableSlotsByDate(newAvailableSlotsByDate);
            }
            catch (e) {
                console.log(e, ' unable to get meeting assist or other relevant data');
            }
        })();
    }, [meetingId, toast]);
    (0, react_1.useEffect)(() => {
        (async () => {
            try {
                if (!meetingAssist?.id) {
                    return;
                }
                if (!meetingAttendees?.[0]?.id) {
                    return;
                }
                const userAttendee = meetingAttendees?.find(m => (m?.id === attendeeId));
                if (userAttendee?.userId === meetingAssist?.userId) {
                    setIsHost(true);
                }
                if (!userAttendee?.id) {
                    console.log('unable to find user attendee');
                    return;
                }
                if (!meetingAssist?.timezone) {
                    console.log('no timezone present');
                    return;
                }
                const events = (await axios_1.default.post('/api/time-preferences', {
                    method: 'findEventsForUserGivenMeetingId',
                    variables: {
                        userId: userAttendee?.userId,
                        hostStartDate: meetingAssist?.windowStartDate,
                        hostEndDate: meetingAssist?.windowEndDate,
                        userTimezone: dayjs_1.default.tz.guess(),
                        hostTimezone: meetingAssist?.timezone,
                        meetingId,
                    },
                }))?.data;
                if (events?.[0]?.id) {
                    toast({
                        title: 'Meeting already created',
                        description: 'Seems like meeting is already created',
                        status: 'error',
                        duration: 9000,
                        isClosable: true
                    });
                    setMeetingAlreadyCreated(true);
                }
            }
            catch (e) {
                console.log(e, ' unable to check if meeting already created');
            }
        })();
    }, [attendeeId, meetingAssist?.id, meetingAssist?.timezone, meetingAssist?.userId, meetingAssist?.windowEndDate, meetingAssist?.windowStartDate, meetingAttendees, meetingId, toast]);
    (0, react_1.useEffect)(() => {
        preferredTimesEndRef?.current?.scrollIntoView({
            behavior: 'smooth',
            block: 'end',
            inline: 'nearest'
        });
    }, [preferredTimesUI]);
    const onSelectedSlot = (i) => {
        if (!availableSlotsByDate) {
            console.log('no availableSlotsByDate');
            return;
        }
        if (meetingAssist?.cancelled) {
            console.log('meeting is cancelled');
            toast({
                title: 'Meeting cancelled',
                description: 'Seems like meeting is cancelled',
                status: 'warning',
                duration: 9000,
                isClosable: true
            });
            return;
        }
        if ((0, dayjs_1.default)().isAfter((0, dayjs_1.default)(meetingAssist?.windowEndDate?.slice(0, 19)).tz(meetingAssist?.timezone, true).format())) {
            console.log('meeting is expired');
            toast({
                title: 'Meeting expired',
                description: 'Seems like meeting is expired',
                status: 'warning',
                duration: 9000,
                isClosable: true
            });
            return;
        }
        if (meetingAssist?.expireDate && ((0, dayjs_1.default)().isAfter((0, dayjs_1.default)(meetingAssist?.expireDate?.slice(0, 19)).tz(meetingAssist?.timezone, true).format()))) {
            console.log('meeting is expired');
            toast({
                title: 'Meeting expired',
                description: 'Seems like meeting is expired',
                status: 'warning',
                duration: 9000,
                isClosable: true
            });
            return;
        }
        const newAvailableSlotsByDate = lodash_1.default.cloneDeep(availableSlotsByDate);
        if (!newAvailableSlotsByDate[`${(0, dayjs_1.default)(selectedDate).format('YYYY-MM-DD')}`]?.[i]?.id) {
            console.log('no available date slots by date');
            return;
        }
        newAvailableSlotsByDate[`${(0, dayjs_1.default)(selectedDate).format('YYYY-MM-DD')}`][i].selected = !newAvailableSlotsByDate?.[`${(0, dayjs_1.default)(selectedDate).format('YYYY-MM-DD')}`]?.[i]?.selected;
        const selected = newAvailableSlotsByDate[`${(0, dayjs_1.default)(selectedDate).format('YYYY-MM-DD')}`][i].selected;
        setAvailableSlotsByDate(newAvailableSlotsByDate);
        if (selected) {
            const newPt = convertSlotToPreferredTime(newAvailableSlotsByDate[`${(0, dayjs_1.default)(selectedDate).format('YYYY-MM-DD')}`][i]);
            if (!newPt?.id) {
                console.log('no newPt converted from slot');
                return;
            }
            addNewPreferredTime(newPt, newAvailableSlotsByDate[`${(0, dayjs_1.default)(selectedDate).format('YYYY-MM-DD')}`][i]?.id);
        }
        else {
            const removedPt = preferredTimesUI?.find(pt => (pt?.slotId === newAvailableSlotsByDate[`${(0, dayjs_1.default)(selectedDate).format('YYYY-MM-DD')}`][i]?.id));
            if (removedPt?.id) {
                removePreferredTime(removedPt);
            }
        }
    };
    const convertCustomAvailableTimeToPreferred = (availableTime) => {
        if (!meetingAssist?.userId) {
            console.log('no userId present inside converttopreferredtime');
            toast({
                title: 'No meeting present',
                description: 'Seems like there is no meeting to allow time preference selection',
                status: 'error',
                duration: 9000,
                isClosable: true
            });
            return;
        }
        const newPreferredTime = {
            id: (0, uuid_1.v4)(),
            meetingId,
            dayOfWeek: availableTime?.dayOfWeekInt === -1 ? undefined : availableTime?.dayOfWeekInt,
            startTime: availableTime?.startTime,
            endTime: availableTime?.endTime,
            updatedAt: (0, dayjs_1.default)().format(),
            createdDate: (0, dayjs_1.default)().format(),
            hostId: meetingAssist?.userId,
            attendeeId,
        };
        return newPreferredTime;
    };
    const onSubmitCustomAvailableTime = (availableTime) => {
        onClose();
        if ((0, dayjs_1.default)().isAfter((0, dayjs_1.default)(meetingAssist?.windowEndDate?.slice(0, 19)).tz(meetingAssist?.timezone, true).format())) {
            console.log('meeting is expired');
            toast({
                title: 'Meeting expired',
                description: 'Seems like meeting is expired',
                status: 'warning',
                duration: 9000,
                isClosable: true
            });
            return;
        }
        if (meetingAssist?.expireDate && ((0, dayjs_1.default)().isAfter((0, dayjs_1.default)(meetingAssist?.expireDate?.slice(0, 19)).tz(meetingAssist?.timezone, true).format()))) {
            console.log('meeting is expired');
            toast({
                title: 'Meeting expired',
                description: 'Seems like meeting is expired',
                status: 'warning',
                duration: 9000,
                isClosable: true
            });
            return;
        }
        if (meetingAssist?.cancelled) {
            console.log('meeting is cancelled');
            toast({
                title: 'Meeting cancelled',
                description: 'Seems like meeting is cancelled',
                status: 'warning',
                duration: 9000,
                isClosable: true
            });
            return;
        }
        const newPreferredTime = convertCustomAvailableTimeToPreferred(availableTime);
        if (!newPreferredTime) {
            console.log('newPreferredTime is undefined');
            return;
        }
        const newPreferredTimesUI = lodash_1.default.cloneDeep(preferredTimesUI) || [];
        newPreferredTimesUI.push(convertPTR2PDR(newPreferredTime));
        setPreferredTimesUI(newPreferredTimesUI);
        const newCustomPreferredTimes = lodash_1.default.cloneDeep(customPreferredTimes) || [];
        newCustomPreferredTimes.push(convertPTR2PDR(newPreferredTime));
        setCustomPreferredTimes(newCustomPreferredTimes);
    };
    const onCancelCustomAvailableTime = () => onClose();
    const convertSlotToPreferredTime = (slot) => {
        if (!meetingAssist?.userId) {
            console.log('no userId present inside converttopreferredtime');
            toast({
                title: 'No meeting present',
                description: 'Seems like there is no meeting to allow time preference selection',
                status: 'error',
                duration: 9000,
                isClosable: true
            });
            return;
        }
        const newPreferredTime = {
            id: (0, uuid_1.v4)(),
            meetingId,
            dayOfWeek: (0, date_fns_1.getISODay)((0, dayjs_1.default)(selectedDate).toDate()),
            startTime: (0, dayjs_1.default)(slot?.startDate).format(),
            endTime: (0, dayjs_1.default)(slot?.endDate).format(),
            updatedAt: (0, dayjs_1.default)().format(),
            createdDate: (0, dayjs_1.default)().format(),
            hostId: meetingAssist?.userId,
            attendeeId,
        };
        return newPreferredTime;
    };
    const addNewPreferredTime = (newPt, slotId) => {
        if (!newPt?.id) {
            console.log('no newPt present inside addNewPreferredTime');
            return;
        }
        if ((0, dayjs_1.default)().isAfter((0, dayjs_1.default)(meetingAssist?.windowEndDate?.slice(0, 19)).tz(meetingAssist?.timezone, true).format())) {
            console.log('meeting is expired');
            toast({
                title: 'Meeting expired',
                description: 'Seems like meeting is expired',
                status: 'warning',
                duration: 9000,
                isClosable: true
            });
            return;
        }
        if (meetingAssist?.expireDate && ((0, dayjs_1.default)().isAfter((0, dayjs_1.default)(meetingAssist?.expireDate?.slice(0, 19)).tz(meetingAssist?.timezone, true).format()))) {
            console.log('meeting is expired');
            toast({
                title: 'Meeting expired',
                description: 'Seems like meeting is expired',
                status: 'warning',
                duration: 9000,
                isClosable: true
            });
            return;
        }
        if (meetingAlreadyCreated || meetingAssist?.cancelled) {
            console.log('meeting already created');
            toast({
                title: 'Meeting already created',
                description: 'Seems like meeting is already created',
                status: 'error',
                duration: 9000,
                isClosable: true
            });
            return;
        }
        const clonedNewPreferredTimes = (lodash_1.default.cloneDeep(newPreferredTimes)
            || []);
        clonedNewPreferredTimes.push({ ...newPt, slotId });
        setNewPreferredTimes(clonedNewPreferredTimes);
        const clonedPreferredTimesUI = (lodash_1.default.cloneDeep(preferredTimesUI) || []);
        clonedPreferredTimesUI.push({ ...newPt, slotId });
        setPreferredTimesUI(clonedPreferredTimesUI);
    };
    const removePreferredTime = (removedPt) => {
        if (!removedPt?.id) {
            console.log('no removedPt found');
            return;
        }
        if (meetingAlreadyCreated || meetingAssist?.cancelled) {
            console.log('meeting already created inside removedPreferredTime');
            toast({
                title: 'Meeting already created',
                description: 'Seems like meeting is already created',
                status: 'error',
                duration: 9000,
                isClosable: true
            });
            return;
        }
        const clonedPreferredTimesUI = (lodash_1.default.cloneDeep(preferredTimesUI) || []);
        const foundIndex = clonedPreferredTimesUI.findIndex(pt => (pt?.id === removedPt?.id));
        if (foundIndex > -1) {
            const newClonedPreferredTimesUI = clonedPreferredTimesUI
                .slice(0, foundIndex)
                .concat(clonedPreferredTimesUI.slice(foundIndex + 1));
            setPreferredTimesUI(newClonedPreferredTimesUI);
        }
        const foundOldIndex = oldPreferredTimes?.findIndex(oPt => (oPt?.id === removedPt?.id));
        if ((foundOldIndex) && (foundOldIndex > -1)) {
            const clonedPreferredTimesRemoved = (lodash_1.default.cloneDeep(preferredTimesRemoved) || []);
            clonedPreferredTimesRemoved.push(removedPt);
            setPreferredTimesRemoved(clonedPreferredTimesRemoved);
        }
        const foundNewIndex = newPreferredTimes?.findIndex(pt => (pt?.id === removedPt?.id));
        if ((foundNewIndex) && (foundNewIndex > -1)) {
            const slicedNewPreferredTimes = newPreferredTimes
                ?.slice(0, foundNewIndex)
                ?.concat(newPreferredTimes?.slice(foundNewIndex + 1));
            setNewPreferredTimes(slicedNewPreferredTimes);
        }
        const foundCustomIndex = customPreferredTimes?.findIndex(c => (c?.id === removedPt?.id));
        if ((foundCustomIndex) && (foundCustomIndex > -1)) {
            const slicedCustomPreferredTimes = customPreferredTimes
                ?.slice(0, foundCustomIndex)
                ?.concat(customPreferredTimes?.slice(foundCustomIndex + 1));
            setCustomPreferredTimes(slicedCustomPreferredTimes);
        }
    };
    const removePreferredTimeByIndex = (index) => {
        if (meetingAssist?.cancelled) {
            console.log('meeting is cancelled');
            toast({
                title: 'Meeting cancelled',
                description: 'Seems like meeting is cancelled',
                status: 'warning',
                duration: 9000,
                isClosable: true
            });
            return;
        }
        if ((0, dayjs_1.default)().isAfter((0, dayjs_1.default)(meetingAssist?.windowEndDate?.slice(0, 19)).tz(meetingAssist?.timezone, true).format())) {
            console.log('meeting is expired');
            toast({
                title: 'Meeting expired',
                description: 'Seems like meeting is expired',
                status: 'warning',
                duration: 9000,
                isClosable: true
            });
            return;
        }
        if (meetingAssist?.expireDate && ((0, dayjs_1.default)().isAfter((0, dayjs_1.default)(meetingAssist?.expireDate?.slice(0, 19)).tz(meetingAssist?.timezone, true).format()))) {
            console.log('meeting is expired');
            toast({
                title: 'Meeting expired',
                description: 'Seems like meeting is expired',
                status: 'warning',
                duration: 9000,
                isClosable: true
            });
            return;
        }
        const removedPt = preferredTimesUI?.[index];
        if (!removedPt?.id) {
            console.log(' something went wrong removedPt not found');
            return;
        }
        removePreferredTime(removedPt);
    };
    const removePreferredTimesInDb = async () => {
        try {
            const ids = preferredTimesRemoved?.map(pt => (pt?.id));
            if (ids?.[0]) {
                return axios_1.default.post('/api/time-preferences', {
                    method: 'deleteMeetingAssistPreferredTimesByIds',
                    variables: {
                        ids,
                    },
                });
            }
        }
        catch (e) {
            console.log(e, ' unable to remove preferred times');
        }
    };
    const convertPreferredTimesInUserTimeZoneToHostTimeZone = (preferredTimesToConvert, hostTimezone) => {
        const convertedPreferredTimes = preferredTimesToConvert?.map(pt => {
            return {
                ...pt,
                startTime: (0, dayjs_1.default)(pt?.startTime, 'HH:mm', true).tz(dayjs_1.default.tz.guess(), true).tz(hostTimezone).format('HH:mm'),
                endTime: (0, dayjs_1.default)(pt?.endTime, 'HH:mm', true).tz(dayjs_1.default.tz.guess(), true).tz(hostTimezone).format('HH:mm'),
            };
        });
        return convertedPreferredTimes;
    };
    const convertToPreferredTimesForMeetingAssist = () => {
        const preferredTimesAddedInUserTimezone = [];
        let preferredTimesAddedInUserTimezoneViaSlots = [];
        if (newPreferredTimes && (newPreferredTimes?.length > 0)) {
            preferredTimesAddedInUserTimezoneViaSlots = newPreferredTimes?.map(pt => lodash_1.default.omit(pt, ['slotId']));
        }
        if (preferredTimesAddedInUserTimezoneViaSlots?.[0]?.id) {
            preferredTimesAddedInUserTimezone.push(...preferredTimesAddedInUserTimezoneViaSlots);
        }
        let customPreferredTimesAddedInUser = [];
        if (customPreferredTimes && (customPreferredTimes?.length > 0)) {
            customPreferredTimesAddedInUser = customPreferredTimes?.map(pt => lodash_1.default.omit(pt, ['slotId']));
        }
        if (customPreferredTimesAddedInUser?.[0]?.id) {
            preferredTimesAddedInUserTimezone.push(...customPreferredTimesAddedInUser);
        }
        if (oldPreferredTimes?.[0]?.id) {
            preferredTimesAddedInUserTimezone.push(...oldPreferredTimes);
        }
        if (!preferredTimesAddedInUserTimezone?.[0]?.id) {
            console.log(' undefined preferredTimes inside convertToPreferredTimesForMeetingAssist');
            return;
        }
        if (!meetingAssist?.timezone) {
            console.log('no meeting asssit inside addPreferredTimesInDb');
            toast({
                title: 'Meeting does not exist',
                description: 'Seems like meeting does not exist',
                status: 'error',
                duration: 9000,
                isClosable: true
            });
            return;
        }
        console.log(preferredTimesAddedInUserTimezone, ' preferredTimesAddedInUserTimezone');
        if (preferredTimesAddedInUserTimezone && (preferredTimesAddedInUserTimezone?.length > 0)) {
            const convertedPreferredTimes = convertPreferredTimesInUserTimeZoneToHostTimeZone(preferredTimesAddedInUserTimezone?.map(pd => convertPDR2PTR(pd)), meetingAssist?.timezone);
            return convertedPreferredTimes;
        }
        return null;
    };
    const addPreferredTimesInDb = async () => {
        try {
            const preferredTimesAddedInUserTimezone = [];
            let preferredTimesAddedInUserTimezoneViaSlots = [];
            if (newPreferredTimes && (newPreferredTimes?.length > 0)) {
                preferredTimesAddedInUserTimezoneViaSlots = newPreferredTimes?.map(pt => lodash_1.default.omit(pt, ['slotId']));
            }
            if (preferredTimesAddedInUserTimezoneViaSlots?.[0]?.id) {
                preferredTimesAddedInUserTimezone.push(...preferredTimesAddedInUserTimezoneViaSlots);
            }
            let customPreferredTimesAddedInUser = [];
            if (customPreferredTimes && (customPreferredTimes?.length > 0)) {
                customPreferredTimesAddedInUser = customPreferredTimes?.map(pt => lodash_1.default.omit(pt, ['slotId']));
            }
            if (customPreferredTimesAddedInUser?.[0]?.id) {
                preferredTimesAddedInUserTimezone.push(...customPreferredTimesAddedInUser);
            }
            if (!preferredTimesAddedInUserTimezone?.[0]?.id) {
                console.log(' undefined preferredTimes');
                return;
            }
            if (!meetingAssist?.timezone) {
                console.log('no meeting asssit inside addPreferredTimesInDb');
                toast({
                    title: 'Meeting does not exist',
                    description: 'Seems like meeting does not exist',
                    status: 'error',
                    duration: 9000,
                    isClosable: true
                });
                return;
            }
            console.log(preferredTimesAddedInUserTimezone, ' preferredTimesAddedInUserTimezone');
            if (preferredTimesAddedInUserTimezone && (preferredTimesAddedInUserTimezone?.length > 0)) {
                const convertedPreferredTimes = convertPreferredTimesInUserTimeZoneToHostTimeZone(preferredTimesAddedInUserTimezone?.map(pd => convertPDR2PTR(pd)), meetingAssist?.timezone);
                const res = (await axios_1.default.post('/api/time-preferences', {
                    method: 'upsertMeetingAssistPreferredTimes',
                    variables: {
                        preferredTimes: convertedPreferredTimes,
                    },
                }))?.data;
                return console.log(res, ' successfully upersted meetingassistpreferredtimes');
            }
            console.log('nothing happened');
        }
        catch (e) {
            console.log(e, ' unable to add preferred times in db');
        }
    };
    const callMeetingAssist = async () => {
        try {
            console.log('meetingassist called');
            if (!meetingAssist?.id) {
                console.log('no meeting assist present inside callMeetingAssist');
                toast({
                    title: 'Meeting does not exist',
                    description: 'Seems like meeting does not exist',
                    status: 'error',
                    duration: 9000,
                    isClosable: true
                });
                return;
            }
            if (!meetingAssist?.timezone) {
                console.log('no meeting assist timezone present inside callMeetingAssist');
                toast({
                    title: 'Meeting does not exist',
                    description: 'Seems like meeting does not exist',
                    status: 'error',
                    duration: 9000,
                    isClosable: true
                });
                return;
            }
            console.log(meetingAssist, ' callMeetingAssist');
            console.log(meetingAssist?.originalMeetingId, ' meetingAssist?.originalMeetingId');
            if (meetingAssist?.originalMeetingId) {
                const originalPreferredTimes = convertToPreferredTimesForMeetingAssist();
                console.log(originalPreferredTimes, ' originalPreferredTimes');
                await axios_1.default.post(process.env.NEXT_PUBLIC_ATOMIC_HANDSHAKE_API, {
                    originalMeetingAssist: meetingAssist,
                    originalPreferredTimes,
                }, {
                    headers: {
                        'Content-Type': 'application/json',
                    },
                });
            }
            await axios_1.default.post('/api/time-preferences', {
                method: 'startMeetingAssist',
                variables: {
                    body: {
                        userId: meetingAssist?.userId,
                        windowStartDate: meetingAssist?.windowStartDate,
                        windowEndDate: meetingAssist?.windowEndDate,
                        timezone: meetingAssist?.timezone,
                    },
                },
            });
            console.log('successfully called meeting assist');
        }
        catch (e) {
            console.log(e, ' unable to call meeting assist');
        }
    };
    const onSubmit = async () => {
        try {
            if (meetingAssist?.cancelled) {
                console.log('meeting is cancelled');
                toast({
                    title: 'Meeting cancelled',
                    description: 'Seems like meeting is cancelled',
                    status: 'warning',
                    duration: 9000,
                    isClosable: true
                });
                return;
            }
            if ((0, dayjs_1.default)().isAfter((0, dayjs_1.default)(meetingAssist?.windowEndDate?.slice(0, 19)).tz(meetingAssist?.timezone, true).format())) {
                console.log('meeting is expired');
                toast({
                    title: 'Meeting expired',
                    description: 'Seems like meeting is expired',
                    status: 'warning',
                    duration: 9000,
                    isClosable: true
                });
                return;
            }
            if (meetingAssist?.expireDate && ((0, dayjs_1.default)().isAfter((0, dayjs_1.default)(meetingAssist?.expireDate?.slice(0, 19)).tz(meetingAssist?.timezone, true).format()))) {
                console.log('meeting is expired');
                toast({
                    title: 'Meeting expired',
                    description: 'Seems like meeting is expired',
                    status: 'warning',
                    duration: 9000,
                    isClosable: true
                });
                return;
            }
            if (meetingAlreadyCreated) {
                console.log('meeting already created on submit');
                toast({
                    title: 'Meeting already created',
                    description: 'Seems like meeting is already created',
                    status: 'error',
                    duration: 9000,
                    isClosable: true
                });
                return;
            }
            await removePreferredTimesInDb();
            await addPreferredTimesInDb();
            if (meetingAttendees?.length &&
                meetingAssist?.minThresholdCount &&
                (meetingAttendees?.length >= meetingAssist?.minThresholdCount)) {
                console.log('min threshold met');
                await callMeetingAssist();
            }
            toast({
                title: 'Attendance submitted',
                description: 'Your attendance & time preferences have been successfully submitted. You may now close the window.',
                status: 'success',
                duration: 18000,
                isClosable: true
            });
        }
        catch (e) {
            console.log(e, ' unable to save');
        }
    };
    console.log(newPreferredTimes, ' newPreferredTimes');
    console.log(preferredTimesUI, ' preferredTimesUI');
    return ((0, jsx_runtime_1.jsxs)("div", { className: "flex flex-col justify-center items-center h-full w-full ", children: [(0, jsx_runtime_1.jsxs)("div", { className: "lg:flex lg:justify-center lg:items-center lg:flex-row sm:flex-col h-3/4 w-full ", children: [(0, jsx_runtime_1.jsxs)("div", { className: "lg:w-2/3 flex flex-col justify-center items-center lg:m-2 m-3 h-1/2 lg:h-full ", children: [(0, jsx_runtime_1.jsx)("div", { className: "flex items-center justify-center lg:my-2 my-3 w-full h-1/6", children: (0, jsx_runtime_1.jsx)("div", { children: (0, jsx_runtime_1.jsx)(react_datepicker_1.default, { selected: selectedDate, onChange: (date) => setSelectedDate(date), minDate: minDate, maxDate: maxDate, placeholderText: "Select a date to see available slots for possible time selection", className: "text-gray-900 bg-gray-200 dark:text-gray-200 dark:bg-gray-900 rounded-lg text-center" }) }) }), (0, jsx_runtime_1.jsx)("div", { className: "flex justify-center items-center h-5/6 w-full my-3 overflow-y-scroll", children: (availableSlotsByDate?.[`${(0, dayjs_1.default)(selectedDate).format('YYYY-MM-DD')}`]
                                    && availableSlotsByDate?.[`${(0, dayjs_1.default)(selectedDate).format('YYYY-MM-DD')}`]?.length > 0)
                                    && (meetingAssist?.attendeeCanModify || meetingAssist?.enableAttendeePreferences)
                                    ? ((0, jsx_runtime_1.jsx)("div", { className: "space-y-2 lg:w-1/2 h-full", children: availableSlotsByDate?.[`${(0, dayjs_1.default)(selectedDate).format('YYYY-MM-DD')}`]?.map((av, i) => ((0, jsx_runtime_1.jsxs)("div", { className: "w-full m-auto", children: [(0, jsx_runtime_1.jsx)("input", { className: "peer hidden", type: "radio", name: av?.id, value: av?.id, id: av?.id, checked: av?.selected, onChange: () => onSelectedSlot(i) }), (0, jsx_runtime_1.jsx)("label", { className: "flex cursor-pointer items-center justify-center rounded-lg border  border-purple-900 p-4 text-sm font-medium shadow-sm transition-colors hover:bg-purple-900 hover:text-gray-200  peer-checked:border-pink-500 peer-checked:ring-1 peer-checked:ring-pink-500 text-center dark:text-gray-200 text-gray-900", htmlFor: av?.id, children: (0, jsx_runtime_1.jsx)("span", { className: "", children: `${(0, dayjs_1.default)(av?.startDate).format('h:mm A')} - ${(0, dayjs_1.default)(av?.endDate).format('h:mm A')}` }) })] }, av?.id))) }))
                                    : ((0, jsx_runtime_1.jsx)("div", { className: "flex justify-center items-center h-full w-full", children: (0, jsx_runtime_1.jsx)("div", { className: "text-center sm:text-left w-1/2", children: (0, jsx_runtime_1.jsx)("h2", { className: " font-bold text-gray-900 dark:text-gray-200 sm:text-xl m-3", children: "Looks like there are no slots available for this date. You can either choose another date or click Submit. You will still be able to book an appointment. Just make sure to click Submit." }) }) })) })] }), (0, jsx_runtime_1.jsxs)("div", { className: "lg:w-1/3 flex flex-col justify-center items-center m-3 h-1/2 lg:h-full", children: [(0, jsx_runtime_1.jsx)("div", { className: "lg:h-1/6 lg:w-full" }), (0, jsx_runtime_1.jsxs)("div", { className: "flex flex-col items-center justify-center space-y-2 lg:h-5/6 w-full my-3 overflow-y-scroll", children: [preferredTimesUI?.map((pt, i) => ((0, jsx_runtime_1.jsx)("div", { children: (0, jsx_runtime_1.jsxs)("div", { className: "flex flex-col items-start justify-center rounded-lg border hover:border-pink-900 border-purple-900 p-4 text-sm font-medium shadow-sm transition-colors lg:ml-1 sm:ml-2 ease-in-out delay-150 duration-300", children: [(0, jsx_runtime_1.jsx)("div", { children: ((pt?.dayOfWeek !== undefined) && (pt?.dayOfWeek > 0)) && (constants_1.dayOfWeekIntToString?.[pt?.dayOfWeek]?.[0] + constants_1.dayOfWeekIntToString?.[pt?.dayOfWeek]?.slice(1).toLowerCase().trim()) }), (0, jsx_runtime_1.jsxs)("div", { className: "flex justify-center items-center  hover:text-pink-900 dark:text-gray-200 text-gray-900", children: [(0, jsx_runtime_1.jsx)("div", { className: "", children: `${(0, dayjs_1.default)(pt?.startTime).format('h:mm A')} - ${(0, dayjs_1.default)(pt?.endTime).format('h:mm A')}` }), (0, jsx_runtime_1.jsx)("div", { className: "flex flex-end items-center", children: (meetingAssist?.attendeeCanModify || (meetingAssist?.enableAttendeePreferences
                                                                && ((newPreferredTimes?.some(pt2 => (pt2?.id === pt?.id))) || (customPreferredTimes?.some(pt2 => (pt2?.id === pt?.id))))))
                                                                ? ((0, jsx_runtime_1.jsx)("div", { className: "", children: (0, jsx_runtime_1.jsx)(io5_1.IoCloseOutline, { size: 45, onClick: () => removePreferredTimeByIndex(i), className: "text-red-500 cursor-pointer p-3" }) })) : null })] })] }) }, pt?.id))), (0, jsx_runtime_1.jsx)("div", { ref: preferredTimesEndRef })] }), (0, jsx_runtime_1.jsxs)("div", { className: "lg:h-1/6 w-full flex flex-col justify-center items-center my-3 ", children: [(0, jsx_runtime_1.jsx)("button", { className: 'btn btn-primary lg:p-3 p-4', onClick: onSubmit, children: 'Submit' }), (meetingAssist?.guaranteeAvailability || isHost)
                                        ? ((0, jsx_runtime_1.jsx)("div", { className: ' lg:pt-3 pt-4', children: (0, jsx_runtime_1.jsx)(react_2.Tooltip, { label: 'If none of the times work for you, then you can add a custom time. Atomic will take the custom time into account when scheduling a meeting', children: (0, jsx_runtime_1.jsx)("button", { className: 'btn btn-primary', onClick: onOpen, children: 'Custom Time Preferences' }) }) })) : null] })] })] }), (0, jsx_runtime_1.jsx)("p", { className: "lg:m-3 m-4 text-lg text-center text-gray-500", children: "You do not have to select a time slot. Go ahead and press submit if you have no time preference." }), (0, jsx_runtime_1.jsx)("div", { children: hostPreferences
                    && meetingAssist
                    &&
                        ((0, jsx_runtime_1.jsxs)(react_2.Modal, { isOpen: isOpen, onClose: onClose, children: [(0, jsx_runtime_1.jsx)(react_2.ModalOverlay, {}), (0, jsx_runtime_1.jsxs)(react_2.ModalContent, { children: [(0, jsx_runtime_1.jsx)(react_2.ModalCloseButton, {}), (0, jsx_runtime_1.jsx)(react_2.ModalBody, { children: (0, jsx_runtime_1.jsx)(modal_time_preferences_1.default, { minDate: minDate, maxDate: maxDate, slotDuration: slotDuration, hostPreferences: hostPreferences, meetingAssist: meetingAssist, onSubmit: onSubmitCustomAvailableTime, onCancel: onCancelCustomAvailableTime }) })] })] })) })] }));
};
exports.default = MeetingAssistTimePreferences;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidGltZS1wcmVmZXJlbmNlcy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInRpbWUtcHJlZmVyZW5jZXMudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7OztBQUFBLGlDQUFtRDtBQUVuRCwrQkFBaUM7QUFDakMsc0ZBQTJEO0FBRTNELHVDQUFvQztBQUNwQyxrREFBeUI7QUFDekIsbUVBQTBDO0FBQzFDLHFFQUE0QztBQUM1Qyx1RUFBOEM7QUFDOUMscUVBQTRDO0FBQzVDLDJEQUFrQztBQUNsQyx1RkFBOEQ7QUFDOUQsOENBQXNEO0FBQ3RELDRDQVd5QjtBQUN6Qix3RUFBaUU7QUFDakUsa0RBQXlCO0FBRXpCLG9EQUFzQjtBQUN0Qix5Q0FBZ0Q7QUFHaEQsZUFBSyxDQUFDLE1BQU0sQ0FBQyxpQkFBTyxDQUFDLENBQUE7QUFDckIsZUFBSyxDQUFDLE1BQU0sQ0FBQyxrQkFBUSxDQUFDLENBQUE7QUFDdEIsZUFBSyxDQUFDLE1BQU0sQ0FBQyxtQkFBUyxDQUFDLENBQUE7QUFDdkIsZUFBSyxDQUFDLE1BQU0sQ0FBQyxrQkFBUSxDQUFDLENBQUE7QUFDdEIsZUFBSyxDQUFDLE1BQU0sQ0FBQyxhQUFHLENBQUMsQ0FBQTtBQUNqQixlQUFLLENBQUMsTUFBTSxDQUFDLDJCQUFpQixDQUFDLENBQUE7QUFRL0IsTUFBTSw0QkFBNEIsR0FBb0IsQ0FBQyxLQUFZLEVBQUUsRUFBRTtJQUNuRSxNQUFNLENBQUMsWUFBWSxFQUFFLGVBQWUsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBYyxJQUFJLElBQUksRUFBRSxDQUFDLENBQUE7SUFDekUsTUFBTSxDQUFDLGdCQUFnQixFQUFFLG1CQUFtQixDQUFDLEdBQUcsSUFBQSxnQkFBUSxHQUErQixDQUFBO0lBQ3ZGLE1BQU0sQ0FBQyxhQUFhLEVBQUUsZ0JBQWdCLENBQUMsR0FBRyxJQUFBLGdCQUFRLEdBQXFCLENBQUE7SUFDdkUsTUFBTSxDQUFDLGlCQUFpQixFQUFFLG9CQUFvQixDQUFDLEdBQUcsSUFB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R0FDSCxHQUNSLENBQ2IsQ0FBQyxDQUFDLENBQUMsSUFBSSxJQUVWLElBQ0osSUFDSixFQUNOLDhCQUFHLFNBQVMsRUFBQyw4Q0FBOEMsaUhBRXZELEVBQ0osMENBRVEsZUFBZTt1QkFDWixhQUFhOzt3QkFFaEIsQ0FDSSx3QkFBQyxhQUFLLElBQUMsTUFBTSxFQUFFLE1BQU0sRUFBRSxPQUFPLEVBQUUsT0FBTyxhQUNuQyx1QkFBQyxvQkFBWSxLQUFHLEVBQ2hCLHdCQUFDLG9CQUFZLGVBQ1QsdUJBQUMsd0JBQWdCLEtBQUcsRUFDcEIsdUJBQUMsaUJBQVMsY0FDTix1QkFBQyxnQ0FBb0IsSUFDakIsT0FBTyxFQUFFLE9BQU8sRUFDaEIsT0FBTyxFQUFFLE9BQU8sRUFDaEIsWUFBWSxFQUFFLFlBQVksRUFDMUIsZUFBZSxFQUFFLGVBQWUsRUFDaEMsYUFBYSxFQUFFLGFBQWEsRUFDNUIsUUFBUSxFQUFFLDJCQUEyQixFQUNyQyxRQUFRLEVBQUUsMkJBQTJCLEdBQ3ZDLEdBQ00sSUFDRCxJQUNYLENBQ1gsR0FFSCxJQUNKLENBQ1QsQ0FBQTtBQUNMLENBQUMsQ0FBQTtBQUVELGtCQUFlLDRCQUE0QixDQUFBIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgdXNlRWZmZWN0LCB1c2VSZWYsIHVzZVN0YXRlIH0gZnJvbSBcInJlYWN0XCJcbmltcG9ydCB0eXBlIHsgTmV4dFBhZ2UgfSBmcm9tICduZXh0J1xuaW1wb3J0IHsgdjQgYXMgdXVpZCB9IGZyb20gJ3V1aWQnXG5pbXBvcnQgTW9kYWxUaW1lUHJlZmVyZW5jZXMgZnJvbSAnLi9tb2RhbC10aW1lLXByZWZlcmVuY2VzJ1xuaW1wb3J0IHsgQXZhaWxhYmxlU2xvdCwgQXZhaWxhYmxlU2xvdHNCeURhdGUsIEN1c3RvbUF2YWlsYWJsZVRpbWVUeXBlLCBFdmVudFR5cGUsIE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGUsIE1lZXRpbmdBc3Npc3RFdmVudFR5cGUsIE1lZXRpbmdBc3Npc3RQcmVmZXJyZWREYXRlUmFuZ2VUeXBlLCBNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlVHlwZSwgTWVldGluZ0Fzc2lzdFR5cGUsIE5vdEF2YWlsYWJsZVNsb3QsIFRpbWUsIFVzZXJQcmVmZXJlbmNlVHlwZSB9IGZyb20gXCJAbGliL3R5cGVzXCJcbmltcG9ydCB7IGdldElTT0RheSB9IGZyb20gJ2RhdGUtZm5zJ1xuaW1wb3J0IGRheWpzIGZyb20gJ2RheWpzJ1xuaW1wb3J0IGlzb1dlZWsgZnJvbSAnZGF5anMvcGx1Z2luL2lzb1dlZWsnXG5pbXBvcnQgZHVyYXRpb24gZnJvbSAnZGF5anMvcGx1Z2luL2R1cmF0aW9uJ1xuaW1wb3J0IGlzQmV0d2VlbiBmcm9tICdkYXlqcy9wbHVnaW4vaXNCZXR3ZWVuJ1xuaW1wb3J0IHRpbWV6b25lIGZyb20gJ2RheWpzL3BsdWdpbi90aW1lem9uZSdcbmltcG9ydCB1dGMgZnJvbSAnZGF5anMvcGx1Z2luL3V0YydcbmltcG9ydCBjdXN0b21QYXJzZUZvcm1hdCBmcm9tICdkYXlqcy9wbHVnaW4vY3VzdG9tUGFyc2VGb3JtYXQnXG5pbXBvcnQgeyBkYXlPZldlZWtJbnRUb1N0cmluZyB9IGZyb20gJ0BsaWIvY29uc3RhbnRzJztcbmltcG9ydCB7XG4gICAgQnV0dG9uLFxuICAgIHVzZURpc2Nsb3N1cmUsXG4gICAgdXNlVG9hc3QsXG4gICAgVG9vbHRpcCxcbiAgICBNb2RhbCxcbiAgICBNb2RhbE92ZXJsYXksXG4gICAgTW9kYWxDb250ZW50LFxuICAgIE1vZGFsRm9vdGVyLFxuICAgIE1vZGFsQm9keSxcbiAgICBNb2RhbENsb3NlQnV0dG9uLFxufSBmcm9tICdAY2hha3JhLXVpL3JlYWN0J1xuaW1wb3J0IERhdGVQaWNrZXIsIHsgQ2FsZW5kYXJDb250YWluZXIgfSBmcm9tIFwicmVhY3QtZGF0ZXBpY2tlclwiO1xuaW1wb3J0IGF4aW9zIGZyb20gJ2F4aW9zJ1xuXG5pbXBvcnQgXyBmcm9tIFwibG9kYXNoXCJcbmltcG9ydCB7IElvQ2xvc2VPdXRsaW5lIH0gZnJvbSAncmVhY3QtaWNvbnMvaW81J1xuXG5cbmRheWpzLmV4dGVuZChpc29XZWVrKVxuZGF5anMuZXh0ZW5kKGR1cmF0aW9uKVxuZGF5anMuZXh0ZW5kKGlzQmV0d2VlbilcbmRheWpzLmV4dGVuZCh0aW1lem9uZSlcbmRheWpzLmV4dGVuZCh1dGMpXG5kYXlqcy5leHRlbmQoY3VzdG9tUGFyc2VGb3JtYXQpXG5cbnR5cGUgUHJvcHMgPSB7XG4gICAgbWVldGluZ0lkOiBzdHJpbmcsXG4gICAgYXR0ZW5kZWVJZDogc3RyaW5nLFxufVxuXG5cbmNvbnN0IE1lZXRpbmdBc3Npc3RUaW1lUHJlZmVyZW5jZXM6IE5leHRQYWdlPFByb3BzPiA9IChwcm9wczogUHJvcHMpID0+IHtcbiAgICBjb25zdCBbc2VsZWN0ZWREYXRlLCBzZXRTZWxlY3RlZERhdGVdID0gdXNlU3RhdGU8RGF0ZSB8IG51bGw+KG5ldyBEYXRlKCkpXG4gICAgY29uc3QgW21lZXRpbmdBdHRlbmRlZXMsIHNldE1lZXRpbmdBdHRlbmRlZXNdID0gdXNlU3RhdGU8TWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVtdPigpXG4gICAgY29uc3QgW21lZXRpbmdBc3Npc3QsIHNldE1lZXRpbmdBc3Npc3RdID0gdXNlU3RhdGU8TWVldGluZ0Fzc2lzdFR5cGU+KClcbiAgICBjb25zdCBbb2xkUHJlZmVycmVkVGltZXMsIHNldE9sZFByZWZlcnJlZFRpbWVzXSA9IHVzZVN0YXRlPE1lZXRpbmdBc3Npc3RQcmVmZXJyZWREYXRlUmFuZ2VUeXBlW10+KClcbiAgICBjb25zdCBbbmV3UHJlZmVycmVkVGltZXMsIHNldE5ld1ByZWZlcnJlZFRpbWVzXSA9IHVzZVN0YXRlPChNZWV0aW5nQXNzaXN0UHJlZmVycmVkRGF0ZVJhbmdlVHlwZSAmIHsgc2xvdElkOiBzdHJpbmcgfSlbXT4oKVxuICAgIGNvbnN0IFtwcmVmZXJyZWRUaW1lc1JlbW92ZWQsIHNldFByZWZlcnJlZFRpbWVzUmVtb3ZlZF0gPSB1c2VTdGF0ZTxNZWV0aW5nQXNzaXN0UHJlZmVycmVkRGF0ZVJhbmdlVHlwZVtdPigpXG4gICAgY29uc3QgW3ByZWZlcnJlZFRpbWVzVUksIHNldFByZWZlcnJlZFRpbWVzVUldID0gdXNlU3RhdGU8KE1lZXRpbmdBc3Npc3RQcmVmZXJyZWREYXRlUmFuZ2VUeXBlICYgeyBzbG90SWQ/OiBzdHJpbmcgfSlbXT4oKVxuICAgIGNvbnN0IFttaW5EYXRlLCBzZXRNaW5EYXRlXSA9IHVzZVN0YXRlPERhdGU+KG5ldyBEYXRlKCkpXG4gICAgY29uc3QgW21heERhdGUsIHNldE1heERhdGVdID0gdXNlU3RhdGU8RGF0ZT4oZGF5anMoKS5hZGQoNSwgJ2QnKS50b0RhdGUoKSlcbiAgICBjb25zdCBbYXZhaWxhYmxlU2xvdHNCeURhdGUsIHNldEF2YWlsYWJsZVNsb3RzQnlEYXRlXSA9IHVzZVN0YXRlPEF2YWlsYWJsZVNsb3RzQnlEYXRlPigpXG4gICAgY29uc3QgW21lZXRpbmdBbHJlYWR5Q3JlYXRlZCwgc2V0TWVldGluZ0FscmVhZHlDcmVhdGVkXSA9IHVzZVN0YXRlPGJvb2xlYW4+KClcbiAgICBjb25zdCBbaXNIb3N0LCBzZXRJc0hvc3RdID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gICAgY29uc3QgW2N1c3RvbVByZWZlcnJlZFRpbWVzLCBzZXRDdXN0b21QcmVmZXJyZWRUaW1lc10gPSB1c2VTdGF0ZTwoTWVldGluZ0Fzc2lzdFByZWZlcnJlZERhdGVSYW5nZVR5cGUgJiB7IHNsb3RJZD86IHN0cmluZyB9KVtdPigpXG4gICAgY29uc3QgW3Nsb3REdXJhdGlvbiwgc2V0U2xvdER1cmF0aW9uXSA9IHVzZVN0YXRlPG51bWJlcj4oMzApXG4gICAgY29uc3QgW2hvc3RQcmVmZXJlbmNlcywgc2V0SG9zdFByZWZlcmVuY2VzXSA9IHVzZVN0YXRlPFVzZXJQcmVmZXJlbmNlVHlwZT4oKVxuXG4gICAgY29uc3QgeyBpc09wZW4sIG9uT3Blbiwgb25DbG9zZSB9ID0gdXNlRGlzY2xvc3VyZSgpXG5cbiAgICBjb25zdCB0b2FzdCA9IHVzZVRvYXN0KClcblxuICAgIGNvbnN0IG1lZXRpbmdJZCA9IHByb3BzPy5tZWV0aW5nSWRcbiAgICBjb25zdCBhdHRlbmRlZUlkID0gcHJvcHM/LmF0dGVuZGVlSWRcbiAgICBjb25zdCBwcmVmZXJyZWRUaW1lc0VuZFJlZiA9IHVzZVJlZjxIVE1MRGl2RWxlbWVudD4obnVsbClcblxuICAgIGNvbnN0IGNvbnZlcnRQVFIyUERSID0gKHB0OiBNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlVHlwZSB8IChNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlVHlwZSAmIHsgc2xvdElkOiBzdHJpbmc7IH0pKTogTWVldGluZ0Fzc2lzdFByZWZlcnJlZERhdGVSYW5nZVR5cGUgfCAoTWVldGluZ0Fzc2lzdFByZWZlcnJlZERhdGVSYW5nZVR5cGUgJiB7IHNsb3RJZDogc3RyaW5nOyB9KSA9PiAoe1xuICAgICAgICAuLi5wdCxcbiAgICAgICAgc3RhcnRUaW1lOiBkYXlqcygpLmhvdXIocGFyc2VJbnQocHQuc3RhcnRUaW1lLnNsaWNlKDAsIDIpLCAxMCkpLm1pbnV0ZShwYXJzZUludChwdC5zdGFydFRpbWUuc2xpY2UoMyksIDEwKSkuZm9ybWF0KCksXG4gICAgICAgIGVuZFRpbWU6IGRheWpzKCkuaG91cihwYXJzZUludChwdC5lbmRUaW1lLnNsaWNlKDAsIDIpLCAxMCkpLm1pbnV0ZShwYXJzZUludChwdC5lbmRUaW1lLnNsaWNlKDMpLCAxMCkpLmZvcm1hdCgpLFxuICAgIH0pXG5cbiAgICBjb25zdCBjb252ZXJ0UERSMlBUUiA9IChwZDogTWVldGluZ0Fzc2lzdFByZWZlcnJlZERhdGVSYW5nZVR5cGUgfCAoTWVldGluZ0Fzc2lzdFByZWZlcnJlZERhdGVSYW5nZVR5cGUgJiB7IHNsb3RJZD86IHN0cmluZyB8IHVuZGVmaW5lZDsgfSkpOiBNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlVHlwZSB8IChNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlVHlwZSAgJiB7IHNsb3RJZD86IHN0cmluZyB8IHVuZGVmaW5lZDsgfSkgPT4gKHtcbiAgICAgICAgLi4ucGQsXG4gICAgICAgIHN0YXJ0VGltZTogZGF5anMocGQuc3RhcnRUaW1lKS5mb3JtYXQoJ0hIOm1tJykgYXMgVGltZSxcbiAgICAgICAgZW5kVGltZTogZGF5anMocGQuZW5kVGltZSkuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgfSlcblxuICAgIHVzZUVmZmVjdCgoKSA9PiB7IFxuICAgICAgICBjb25zdCBjb252ZXJ0UHJlZmVycmVkVGltZXNGcm9tQXR0ZW5kZWVUaW1lWm9uZVRvVXNlclRpbWVab25lID0gKHByZWZlcnJlZFRpbWVzSW5BdHRlbmRlZVpvbmU6IE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW10sIGF0dGVuZGVlczogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVtdKTogTWVldGluZ0Fzc2lzdFByZWZlcnJlZERhdGVSYW5nZVR5cGVbXSA9PiB7XG4gICAgICAgICAgICByZXR1cm4gKHByZWZlcnJlZFRpbWVzSW5BdHRlbmRlZVpvbmU/Lm1hcChwdCA9PiB7XG4gICAgICAgICAgICAgICAgICAgICAgICBjb25zdCBmb3VuZEF0dGVuZGVlID0gYXR0ZW5kZWVzLmZpbmQoYSA9PiAoYT8uaWQgPT09IHB0Py5hdHRlbmRlZUlkKSlcblxuICAgICAgICAgICAgICAgICAgICAgICAgaWYgKGZvdW5kQXR0ZW5kZWU/LmlkKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY29uc3QgbmV3UHQgPSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC4uLnB0LFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBzdGFydFRpbWU6IGRheWpzKCkuaG91cihwYXJzZUludChwdD8uc3RhcnRUaW1lLnNsaWNlKDAsIDIpLCAxMCkpLm1pbnV0ZShwYXJzZUludChwdD8uc3RhcnRUaW1lLnNsaWNlKDMpLCAxMCkpLnR6KGZvdW5kQXR0ZW5kZWU/LnRpbWV6b25lLCB0cnVlKS50eihkYXlqcy50ei5ndWVzcygpKS5mb3JtYXQoKSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgZW5kVGltZTogZGF5anMoKS5ob3VyKHBhcnNlSW50KHB0Py5lbmRUaW1lLnNsaWNlKDAsIDIpLCAxMCkpLm1pbnV0ZShwYXJzZUludChwdD8uZW5kVGltZS5zbGljZSgzKSwgMTApKS50eihmb3VuZEF0dGVuZGVlPy50aW1lem9uZSwgdHJ1ZSkudHooZGF5anMudHouZ3Vlc3MoKSkuZm9ybWF0KCksXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiBuZXdQdFxuICAgICAgICAgICAgICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICAgICAgICAgICAgICByZXR1cm4gbnVsbFxuICAgICAgICAgICAgICAgICAgICB9KT8uZmlsdGVyKGUgPT4gKGUgIT09IG51bGwpKSkgYXMgTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXVxuICAgICAgICB9XG4gICAgICAgIChhc3luYyAoKSA9PiB7XG4gICAgICAgICAgICB0cnkge1xuICAgICAgICAgICAgICAgIGlmICghbWVldGluZ0lkKSB7XG4gICAgICAgICAgICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHRpdGxlOiAnTm8gbWVldGluZyBpZCBwcmVzZW50JyxcbiAgICAgICAgICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnU2VlbXMgbGlrZSB0aGVyZSBpcyBubyBtZWV0aW5nIGlkIHRvIGFsbG93IHRpbWUgcHJlZmVyZW5jZSBzZWxlY3Rpb24nLFxuICAgICAgICAgICAgICAgICAgICAgICAgc3RhdHVzOiAnZXJyb3InLFxuICAgICAgICAgICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlXG4gICAgICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAgICAgICAgIHJldHVyblxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIGNvbnN0IG9sZE1lZXRpbmdBc3Npc3QgPSAoYXdhaXQgYXhpb3MucG9zdDxNZWV0aW5nQXNzaXN0VHlwZT4oJy9hcGkvdGltZS1wcmVmZXJlbmNlcycsIHtcbiAgICAgICAgICAgICAgICAgICAgbWV0aG9kOiAnZ2V0TWVldGluZ0Fzc2lzdCcsXG4gICAgICAgICAgICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgICAgICAgICAgICAgaWQ6IG1lZXRpbmdJZCxcbiAgICAgICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICB9KSk/LmRhdGFcbiAgICAgICAgICAgICAgICBpZiAoIW9sZE1lZXRpbmdBc3Npc3QgfHwgKCEob2xkTWVldGluZ0Fzc2lzdD8uaWQpKSkge1xuICAgICAgICAgICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgICAgICAgICB0aXRsZTogJ05vIG1lZXRpbmcgcHJlc2VudCcsXG4gICAgICAgICAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1NlZW1zIGxpa2UgdGhlcmUgaXMgbm8gbWVldGluZyB0byBhbGxvdyB0aW1lIHByZWZlcmVuY2Ugc2VsZWN0aW9uJyxcbiAgICAgICAgICAgICAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZVxuICAgICAgICAgICAgICAgICAgICB9KVxuICAgICAgICAgICAgICAgICAgICByZXR1cm5cbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICBpZiAoIW9sZE1lZXRpbmdBc3Npc3Q/LnRpbWV6b25lKSB7XG4gICAgICAgICAgICAgICAgICAgIGNvbnNvbGUubG9nKG9sZE1lZXRpbmdBc3Npc3Q/LnRpbWV6b25lLCAnIG9sZE1lZXRpbmdBc3Npc3Q/LnRpbWV6b25lIG5vdCBwcmVzZW50JylcbiAgICAgICAgICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgICAgICAgICAgdGl0bGU6ICdObyBtZWV0aW5nIHByZXNlbnQnLFxuICAgICAgICAgICAgICAgICAgICAgICAgZGVzY3JpcHRpb246ICdTZWVtcyBsaWtlIHRoZXJlIGlzIG5vIG1lZXRpbmcgdG8gYWxsb3cgdGltZSBwcmVmZXJlbmNlIHNlbGVjdGlvbicsXG4gICAgICAgICAgICAgICAgICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgICAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWVcbiAgICAgICAgICAgICAgICAgICAgfSlcbiAgICAgICAgICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICAgICAgaWYgKCFvbGRNZWV0aW5nQXNzaXN0Py53aW5kb3dTdGFydERhdGUpIHtcbiAgICAgICAgICAgICAgICAgICAgY29uc29sZS5sb2cob2xkTWVldGluZ0Fzc2lzdD8ud2luZG93U3RhcnREYXRlLCAnIG9sZE1lZXRpbmdBc3Npc3Q/LndpbmRvd1N0YXJ0RGF0ZSBub3QgcHJlc2VudCcpXG4gICAgICAgICAgICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHRpdGxlOiAnTm8gbWVldGluZyBwcmVzZW50JyxcbiAgICAgICAgICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnU2VlbXMgbGlrZSB0aGVyZSBpcyBubyBtZWV0aW5nIHRvIGFsbG93IHRpbWUgcHJlZmVyZW5jZSBzZWxlY3Rpb24nLFxuICAgICAgICAgICAgICAgICAgICAgICAgc3RhdHVzOiAnZXJyb3InLFxuICAgICAgICAgICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlXG4gICAgICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAgICAgICAgIHJldHVyblxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIGlmICghb2xkTWVldGluZ0Fzc2lzdD8ud2luZG93RW5kRGF0ZSkge1xuICAgICAgICAgICAgICAgICAgICBjb25zb2xlLmxvZyhvbGRNZWV0aW5nQXNzaXN0Py53aW5kb3dFbmREYXRlLCAnIG9sZE1lZXRpbmdBc3Npc3Q/LndpbmRvd0VuZERhdGUgbm90IHByZXNlbnQnKVxuICAgICAgICAgICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgICAgICAgICB0aXRsZTogJ05vIG1lZXRpbmcgcHJlc2VudCcsXG4gICAgICAgICAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1NlZW1zIGxpa2UgdGhlcmUgaXMgbm8gbWVldGluZyB0byBhbGxvdyB0aW1lIHByZWZlcmVuY2Ugc2VsZWN0aW9uJyxcbiAgICAgICAgICAgICAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZVxuICAgICAgICAgICAgICAgICAgICB9KVxuICAgICAgICAgICAgICAgICAgICByZXR1cm5cbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICBpZiAoIW9sZE1lZXRpbmdBc3Npc3Q/LnVzZXJJZCkge1xuICAgICAgICAgICAgICAgICAgICBjb25zb2xlLmxvZygnIG5vIHVzZXJJZCBwcmVzZW50IGluc2lkZSBvbGRNZWV0aW5nQXNzaXN0JylcbiAgICAgICAgICAgICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHRpdGxlOiAnTm8gbWVldGluZyBwcmVzZW50JyxcbiAgICAgICAgICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnU2VlbXMgbGlrZSB0aGVyZSBpcyBubyBtZWV0aW5nIHRvIGFsbG93IHRpbWUgcHJlZmVyZW5jZSBzZWxlY3Rpb24nLFxuICAgICAgICAgICAgICAgICAgICAgICAgc3RhdHVzOiAnZXJyb3InLFxuICAgICAgICAgICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlXG4gICAgICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAgICAgICAgIHJldHVyblxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICBjb25zb2xlLmxvZyhvbGRNZWV0aW5nQXNzaXN0LCAnIG9sZE1lZXRpbmdBc3Npc3QnKVxuICAgICAgICAgICAgICAgIHNldE1lZXRpbmdBc3Npc3Qob2xkTWVldGluZ0Fzc2lzdClcbiAgICAgICAgICAgICAgICBzZXRNaW5EYXRlKGRheWpzKG9sZE1lZXRpbmdBc3Npc3Q/LndpbmRvd1N0YXJ0RGF0ZT8uc2xpY2UoMCwgMTkpKS50eihvbGRNZWV0aW5nQXNzaXN0Py50aW1lem9uZSwgdHJ1ZSkudHooZGF5anMudHouZ3Vlc3MoKSkudG9EYXRlKCkpXG4gICAgICAgICAgICAgICAgc2V0TWF4RGF0ZShkYXlqcyhvbGRNZWV0aW5nQXNzaXN0Py53aW5kb3dFbmREYXRlPy5zbGljZSgwLCAxOSkpLnR6KG9sZE1lZXRpbmdBc3Npc3Q/LnRpbWV6b25lLCB0cnVlKS50eihkYXlqcy50ei5ndWVzcygpKS50b0RhdGUoKSlcbiAgICAgICAgICAgICAgICBzZXRTZWxlY3RlZERhdGUoZGF5anMob2xkTWVldGluZ0Fzc2lzdD8ud2luZG93U3RhcnREYXRlPy5zbGljZSgwLCAxOSkpLnR6KG9sZE1lZXRpbmdBc3Npc3Q/LnRpbWV6b25lLCB0cnVlKS50eihkYXlqcy50ei5ndWVzcygpKS50b0RhdGUoKSlcblxuICAgICAgICAgICAgICAgIGNvbnN0IGF0dGVuZGVlcyA9IChhd2FpdCBheGlvcy5wb3N0PE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXT4oJy9hcGkvdGltZS1wcmVmZXJlbmNlcycsIHtcbiAgICAgICAgICAgICAgICAgICAgbWV0aG9kOiAnbGlzdE1lZXRpbmdBc3Npc3RBdHRlbmRlZXNHaXZlbk1lZXRpbmdJZCcsXG4gICAgICAgICAgICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkLFxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgIH0pKT8uZGF0YVxuXG4gICAgICAgICAgICAgICAgaWYgKCFhdHRlbmRlZXMgfHwgKCEoYXR0ZW5kZWVzPy5sZW5ndGggPiAwKSkpIHtcbiAgICAgICAgICAgICAgICAgICAgY29uc29sZS5sb2coJ3RoZXJlIGFyZSBubyBhdHRlbmRlZXMgaW5zaWRlIHRpbWUgcHJlZmVyZW5jZXMnKVxuICAgICAgICAgICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgICAgICAgICB0aXRsZTogJ05vIGF0dGVuZGVlcyBwcmVzZW50JyxcbiAgICAgICAgICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnU2VlbXMgbGlrZSB0aGVyZSBhcmUgbm8gYXR0ZW5kZWVzIHRvIGNvbmZpcm0gYSBtZWV0aW5nJyxcbiAgICAgICAgICAgICAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZVxuICAgICAgICAgICAgICAgICAgICB9KVxuICAgICAgICAgICAgICAgICAgICByZXR1cm5cbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICBzZXRNZWV0aW5nQXR0ZW5kZWVzKGF0dGVuZGVlcylcblxuICAgICAgICAgICAgICAgIGNvbnN0IGV4dGVybmFsQXR0ZW5kZWVzID0gYXR0ZW5kZWVzLmZpbHRlcihhID0+ICEhYT8uZXh0ZXJuYWxBdHRlbmRlZSlcblxuICAgICAgICAgICAgICAgIGNvbnN0IGludGVybmFsQXR0ZW5kZWVzID0gYXR0ZW5kZWVzLmZpbHRlcihhID0+ICFhPy5leHRlcm5hbEF0dGVuZGVlKVxuXG4gICAgICAgICAgICAgICAgY29uc3QgbWVldGluZ0Fzc2lzdEV2ZW50c0luVXNlclRpbWV6b25lOiBNZWV0aW5nQXNzaXN0RXZlbnRUeXBlW10gPSBbXVxuXG4gICAgICAgICAgICAgICAgZm9yIChjb25zdCBleHRlcm5hbEF0dGVuZGVlIG9mIGV4dGVybmFsQXR0ZW5kZWVzKSB7XG5cblxuICAgICAgICAgICAgICAgICAgICBjb25zdCBvbGRNZWV0aW5nQXNzaXN0RXZlbnRzID0gKGF3YWl0IGF4aW9zLnBvc3Q8TWVldGluZ0Fzc2lzdEV2ZW50VHlwZVtdPignL2FwaS90aW1lLXByZWZlcmVuY2VzJywge1xuICAgICAgICAgICAgICAgICAgICAgICAgbWV0aG9kOiAnbGlzdE1lZXRpbmdBc3Npc3RFdmVudHNGb3JBdHRlbmRlZUdpdmVuRGF0ZXMnLFxuICAgICAgICAgICAgICAgICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVJZDogZXh0ZXJuYWxBdHRlbmRlZT8uaWQsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgaG9zdFN0YXJ0RGF0ZTogb2xkTWVldGluZ0Fzc2lzdD8ud2luZG93U3RhcnREYXRlIGFzIHN0cmluZyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBob3N0RW5kRGF0ZTogb2xkTWVldGluZ0Fzc2lzdD8ud2luZG93RW5kRGF0ZSBhcyBzdHJpbmcsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdXNlclRpbWV6b25lOiBleHRlcm5hbEF0dGVuZGVlPy50aW1lem9uZSBhcyBzdHJpbmcsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgaG9zdFRpbWV6b25lOiBvbGRNZWV0aW5nQXNzaXN0Py50aW1lem9uZSBhcyBzdHJpbmcsXG4gICAgICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgICAgICB9KSk/LmRhdGFcbiAgICAgICAgICAgICAgICAgICAgY29uc29sZS5sb2cob2xkTWVldGluZ0Fzc2lzdEV2ZW50cywgJyBvbGRNZWV0aW5nQXNzaXN0RXZlbnRzJylcbiAgICAgICAgICAgICAgICAgICAgaWYgKCFvbGRNZWV0aW5nQXNzaXN0RXZlbnRzIHx8ICghKG9sZE1lZXRpbmdBc3Npc3RFdmVudHM/Lmxlbmd0aCA+IDApKSkge1xuICAgICAgICAgICAgICAgICAgICAgICAgY29udGludWVcbiAgICAgICAgICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICAgICAgICAgIGNvbnN0IG9sZE1lZXRpbmdBc3Npc3RFdmVudHNJblVzZXJUaW1lem9uZSA9IG9sZE1lZXRpbmdBc3Npc3RFdmVudHM/Lm1hcChlID0+ICh7XG4gICAgICAgICAgICAgICAgICAgICAgICAuLi5lLFxuICAgICAgICAgICAgICAgICAgICAgICAgc3RhcnREYXRlOiBkYXlqcyhlPy5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihlPy50aW1lem9uZSwgdHJ1ZSkudHooZGF5anMudHouZ3Vlc3MoKSkuZm9ybWF0KCksXG4gICAgICAgICAgICAgICAgICAgICAgICBlbmREYXRlOiBkYXlqcyhlPy5lbmREYXRlLnNsaWNlKDAsIDE5KSkudHooZT8udGltZXpvbmUsIHRydWUpLnR6KGRheWpzLnR6Lmd1ZXNzKCkpLmZvcm1hdCgpLFxuICAgICAgICAgICAgICAgICAgICAgICAgdGltZXpvbmU6IGRheWpzLnR6Lmd1ZXNzKCksXG4gICAgICAgICAgICAgICAgICAgIH0pKVxuXG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdBc3Npc3RFdmVudHNJblVzZXJUaW1lem9uZS5wdXNoKC4uLm9sZE1lZXRpbmdBc3Npc3RFdmVudHNJblVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgICB9XG5cblxuICAgICAgICAgICAgICAgIGNvbnN0IGV2ZW50c0luVXNlclRpbWV6b25lOiBFdmVudFR5cGVbXSA9IFtdXG5cbiAgICAgICAgICAgICAgICBmb3IgKGNvbnN0IGludGVybmFsQXR0ZW5kZWUgb2YgaW50ZXJuYWxBdHRlbmRlZXMpIHtcblxuICAgICAgICAgICAgICAgICAgICBjb25zdCBvbGRFdmVudHNJbkV2ZW50VGltZXpvbmUgPSAoYXdhaXQgYXhpb3MucG9zdDxFdmVudFR5cGVbXT4oJy9hcGkvdGltZS1wcmVmZXJlbmNlcycsIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIG1ldGhvZDogJ2xpc3RFdmVudHNGb3JVc2VyR2l2ZW5EYXRlcycsXG4gICAgICAgICAgICAgICAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB1c2VySWQ6IGludGVybmFsQXR0ZW5kZWU/LnVzZXJJZCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBob3N0U3RhcnREYXRlOiBvbGRNZWV0aW5nQXNzaXN0Py53aW5kb3dTdGFydERhdGUgYXMgc3RyaW5nLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGhvc3RFbmREYXRlOiBvbGRNZWV0aW5nQXNzaXN0Py53aW5kb3dFbmREYXRlIGFzIHN0cmluZyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB1c2VyVGltZXpvbmU6IGludGVybmFsQXR0ZW5kZWU/LnRpbWV6b25lIGFzIHN0cmluZyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBob3N0VGltZXpvbmU6IG9sZE1lZXRpbmdBc3Npc3Q/LnRpbWV6b25lIGFzIHN0cmluZyxcbiAgICAgICAgICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgICAgIH0pKT8uZGF0YVxuICAgICAgICAgICAgICAgICAgICBcbiAgICAgICAgICAgICAgICAgICAgY29uc29sZS5sb2cob2xkRXZlbnRzSW5FdmVudFRpbWV6b25lLCAnIG9sZEV2ZW50c0luRXZlbnRUaW1lem9uZScpXG5cbiAgICAgICAgICAgICAgICAgICAgaWYgKCFvbGRFdmVudHNJbkV2ZW50VGltZXpvbmUgfHwgKCEob2xkRXZlbnRzSW5FdmVudFRpbWV6b25lPy5sZW5ndGggPiAwKSkpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvbnRpbnVlXG4gICAgICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgICAgICBjb25zdCBvbGRFdmVudHNJblVzZXJUaW1lem9uZSA9IG9sZEV2ZW50c0luRXZlbnRUaW1lem9uZT8ubWFwKGUgPT4gKHtcbiAgICAgICAgICAgICAgICAgICAgICAgIC4uLmUsXG4gICAgICAgICAgICAgICAgICAgICAgICBzdGFydERhdGU6IGRheWpzKGU/LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGU/LnRpbWV6b25lLCB0cnVlKS50eihkYXlqcy50ei5ndWVzcygpKS5mb3JtYXQoKSxcbiAgICAgICAgICAgICAgICAgICAgICAgIGVuZERhdGU6IGRheWpzKGU/LmVuZERhdGUuc2xpY2UoMCwgMTkpKS50eihlPy50aW1lem9uZSwgdHJ1ZSkudHooZGF5anMudHouZ3Vlc3MoKSkuZm9ybWF0KCksXG4gICAgICAgICAgICAgICAgICAgICAgICB0aW1lem9uZTogZGF5anMudHouZ3Vlc3MoKSxcbiAgICAgICAgICAgICAgICAgICAgfSkpXG5cbiAgICAgICAgICAgICAgICAgICAgZXZlbnRzSW5Vc2VyVGltZXpvbmUucHVzaCguLi5vbGRFdmVudHNJblVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICBjb25zdCBwcmVmZXJyZWRUaW1lc0luQXR0ZW5kZWVab25lID0gKGF3YWl0IGF4aW9zLnBvc3Q8TWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXT4oJy9hcGkvdGltZS1wcmVmZXJlbmNlcycsIHtcbiAgICAgICAgICAgICAgICAgICAgbWV0aG9kOiAnbGlzdE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VzR2l2ZW5NZWV0aW5nSWQnLFxuICAgICAgICAgICAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgICAgICAgICAgICAgIG1lZXRpbmdJZCxcbiAgICAgICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICB9KSk/LmRhdGFcbiAgICAgICAgICAgICAgICBcbiAgICAgICAgICAgICAgICBpZiAocHJlZmVycmVkVGltZXNJbkF0dGVuZGVlWm9uZSAmJiAocHJlZmVycmVkVGltZXNJbkF0dGVuZGVlWm9uZT8ubGVuZ3RoID4gMCkpIHtcbiAgICAgICAgICAgICAgICAgICAgY29uc3QgcHJlZmVycmVkVGltZXNJblVzZXJab25lID0gY29udmVydFByZWZlcnJlZFRpbWVzRnJvbUF0dGVuZGVlVGltZVpvbmVUb1VzZXJUaW1lWm9uZShwcmVmZXJyZWRUaW1lc0luQXR0ZW5kZWVab25lLCBhdHRlbmRlZXMpXG5cbiAgICAgICAgICAgICAgICAgICAgaWYgKCFwcmVmZXJyZWRUaW1lc0luVXNlclpvbmU/LlswXT8uaWQpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvbnNvbGUubG9nKCcgdW5hYmxlIHRvIGZvcm0gcHJlZmVycmVkVGltZXNJblVzZXJab25lJylcbiAgICAgICAgICAgICAgICAgICAgICAgIHJldHVyblxuICAgICAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICAgICAgc2V0T2xkUHJlZmVycmVkVGltZXMocHJlZmVycmVkVGltZXNJblVzZXJab25lPy5tYXAocHQgPT4gKHsgLi4ucHQsIGRheU9mV2VlazogIXB0Py5kYXlPZldlZWsgPyAtMSA6IHB0Py5kYXlPZldlZWsgfSkpKVxuICAgICAgICAgICAgICAgICAgICBzZXRQcmVmZXJyZWRUaW1lc1VJKHByZWZlcnJlZFRpbWVzSW5Vc2VyWm9uZT8ubWFwKHB0ID0+ICh7IC4uLnB0LCBkYXlPZldlZWs6ICFwdD8uZGF5T2ZXZWVrID8gLTEgOiBwdD8uZGF5T2ZXZWVrIH0pKSlcblxuICAgICAgICAgICAgICAgIH1cblxuXG4gICAgICAgICAgICAgICAgY29uc3Qgb2xkSG9zdFByZWZlcmVuY2VzID0gKGF3YWl0IGF4aW9zLnBvc3Q8VXNlclByZWZlcmVuY2VUeXBlPignL2FwaS90aW1lLXByZWZlcmVuY2VzJywge1xuICAgICAgICAgICAgICAgICAgICBtZXRob2Q6ICdnZXRVc2VyUHJlZmVyZW5jZXMnLFxuICAgICAgICAgICAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJJZDogb2xkTWVldGluZ0Fzc2lzdD8udXNlcklkLFxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgIH0pKT8uZGF0YVxuXG4gICAgICAgICAgICAgICAgaWYgKCFvbGRIb3N0UHJlZmVyZW5jZXM/LmlkKSB7XG4gICAgICAgICAgICAgICAgICAgIGNvbnNvbGUubG9nKCdubyBob3N0UHJlZmVyZW5jZXMgcHJlc2VudCcpXG4gICAgICAgICAgICAgICAgICAgIHJldHVyblxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIGNvbnN0IG9sZFNsb3REdXJhdGlvbiA9IG9sZE1lZXRpbmdBc3Npc3Q/LmR1cmF0aW9uXG5cbiAgICAgICAgICAgICAgICBjb25zdCBub3RBdmFpbGFibGVTbG90czogTm90QXZhaWxhYmxlU2xvdFtdID0gW11cbiAgICAgICAgICAgICAgICBjb25zdCBjdXJyZW50VGltZXpvbmUgPSBkYXlqcy50ei5ndWVzcygpXG5cbiAgICAgICAgICAgICAgICBjb25zdCBub3RBdmFpbGFibGVGcm9tTWVldGluZ0Fzc2lzdHM6IE5vdEF2YWlsYWJsZVNsb3RbXSA9IG1lZXRpbmdBc3Npc3RFdmVudHNJblVzZXJUaW1lem9uZT8ubWFwKG1lID0+ICh7XG4gICAgICAgICAgICAgICAgICAgIHN0YXJ0RGF0ZTogbWU/LnN0YXJ0RGF0ZSxcbiAgICAgICAgICAgICAgICAgICAgZW5kRGF0ZTogbWU/LmVuZERhdGUsXG4gICAgICAgICAgICAgICAgfSkpXG5cbiAgICAgICAgICAgICAgICBpZiAobm90QXZhaWxhYmxlRnJvbU1lZXRpbmdBc3Npc3RzPy5bMF0/LnN0YXJ0RGF0ZSkge1xuICAgICAgICAgICAgICAgICAgICBub3RBdmFpbGFibGVTbG90cy5wdXNoKC4uLm5vdEF2YWlsYWJsZUZyb21NZWV0aW5nQXNzaXN0cylcbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICBjb25zdCBub3RBdmFpbGFibGVGcm9tRXZlbnRzOiBOb3RBdmFpbGFibGVTbG90W10gPSBldmVudHNJblVzZXJUaW1lem9uZT8ubWFwKGUgPT4gKHtcbiAgICAgICAgICAgICAgICAgICAgc3RhcnREYXRlOiBlPy5zdGFydERhdGUsXG4gICAgICAgICAgICAgICAgICAgIGVuZERhdGU6IGU/LmVuZERhdGUsXG4gICAgICAgICAgICAgICAgfSkpXG5cbiAgICAgICAgICAgICAgICBpZiAobm90QXZhaWxhYmxlRnJvbUV2ZW50cz8uWzBdPy5zdGFydERhdGUpIHtcbiAgICAgICAgICAgICAgICAgICAgbm90QXZhaWxhYmxlU2xvdHMucHVzaCguLi5ub3RBdmFpbGFibGVGcm9tRXZlbnRzKVxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIHNldFNsb3REdXJhdGlvbihvbGRTbG90RHVyYXRpb24pXG4gICAgICAgICAgICAgICAgc2V0SG9zdFByZWZlcmVuY2VzKG9sZEhvc3RQcmVmZXJlbmNlcylcblxuXG4gICAgICAgICAgICAgICAgY29uc29sZS5sb2cobm90QXZhaWxhYmxlU2xvdHMsICcgbm90QXZhaWxhYmxlU2xvdHMnKVxuICAgICAgICAgICAgICAgIGNvbnN0IG5ld0F2YWlsYWJsZVNsb3RzQnlEYXRlID0gKGF3YWl0IGF4aW9zLnBvc3Q8QXZhaWxhYmxlU2xvdHNCeURhdGU+KCcvYXBpL3RpbWUtcHJlZmVyZW5jZXMnLCB7XG4gICAgICAgICAgICAgICAgICAgIG1ldGhvZDogJ2dlbmVyYXRlQXZhaWxhYmxlU2xvdHNmb3JUaW1lV2luZG93JyxcbiAgICAgICAgICAgICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICAgICAgICAgICAgICB3aW5kb3dTdGFydERhdGU6IG9sZE1lZXRpbmdBc3Npc3Q/LndpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgICAgICAgICAgICAgICAgICAgIHdpbmRvd0VuZERhdGU6IG9sZE1lZXRpbmdBc3Npc3Q/LndpbmRvd0VuZERhdGUsXG4gICAgICAgICAgICAgICAgICAgICAgICBzbG90RHVyYXRpb246IG9sZFNsb3REdXJhdGlvbixcbiAgICAgICAgICAgICAgICAgICAgICAgIGhvc3RQcmVmZXJlbmNlczogb2xkSG9zdFByZWZlcmVuY2VzIGFzIFVzZXJQcmVmZXJlbmNlVHlwZSxcbiAgICAgICAgICAgICAgICAgICAgICAgIGhvc3RUaW1lem9uZTogb2xkTWVldGluZ0Fzc2lzdD8udGltZXpvbmUsXG4gICAgICAgICAgICAgICAgICAgICAgICB1c2VyVGltZXpvbmU6IGN1cnJlbnRUaW1lem9uZSxcbiAgICAgICAgICAgICAgICAgICAgICAgIG5vdEF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmU6IG5vdEF2YWlsYWJsZVNsb3RzPy5sZW5ndGggPiAwID8gbm90QXZhaWxhYmxlU2xvdHMgOiB1bmRlZmluZWQsXG4gICAgICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgfSkpPy5kYXRhXG5cbiAgICAgICAgICAgICAgICBzZXRBdmFpbGFibGVTbG90c0J5RGF0ZShuZXdBdmFpbGFibGVTbG90c0J5RGF0ZSlcbiAgICAgICAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgICAgICAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgbWVldGluZyBhc3Npc3Qgb3Igb3RoZXIgcmVsZXZhbnQgZGF0YScpXG4gICAgICAgICAgICB9XG4gICAgICAgIH0pKClcbiAgICB9LCBbbWVldGluZ0lkLCB0b2FzdF0pXG5cbiAgICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgICAgICAoYXN5bmMgKCkgPT4ge1xuICAgICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgICAgICBpZiAoIW1lZXRpbmdBc3Npc3Q/LmlkKSB7XG4gICAgICAgICAgICAgICAgICAgIHJldHVyblxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIGlmICghbWVldGluZ0F0dGVuZGVlcz8uWzBdPy5pZCkge1xuICAgICAgICAgICAgICAgICAgICByZXR1cm5cbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICBjb25zdCB1c2VyQXR0ZW5kZWUgPSBtZWV0aW5nQXR0ZW5kZWVzPy5maW5kKG0gPT4gKG0/LmlkID09PSBhdHRlbmRlZUlkKSlcblxuICAgICAgICAgICAgICAgIGlmICh1c2VyQXR0ZW5kZWU/LnVzZXJJZCA9PT0gbWVldGluZ0Fzc2lzdD8udXNlcklkKSB7XG4gICAgICAgICAgICAgICAgICAgIHNldElzSG9zdCh0cnVlKVxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIGlmICghdXNlckF0dGVuZGVlPy5pZCkge1xuICAgICAgICAgICAgICAgICAgICBjb25zb2xlLmxvZygndW5hYmxlIHRvIGZpbmQgdXNlciBhdHRlbmRlZScpXG4gICAgICAgICAgICAgICAgICAgIHJldHVyblxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIGlmICghbWVldGluZ0Fzc2lzdD8udGltZXpvbmUpIHtcbiAgICAgICAgICAgICAgICAgICAgY29uc29sZS5sb2coJ25vIHRpbWV6b25lIHByZXNlbnQnKVxuICAgICAgICAgICAgICAgICAgICByZXR1cm5cbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICBjb25zdCBldmVudHMgPSAoYXdhaXQgYXhpb3MucG9zdCgnL2FwaS90aW1lLXByZWZlcmVuY2VzJywge1xuICAgICAgICAgICAgICAgICAgICBtZXRob2Q6ICdmaW5kRXZlbnRzRm9yVXNlckdpdmVuTWVldGluZ0lkJyxcbiAgICAgICAgICAgICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICAgICAgICAgICAgICB1c2VySWQ6IHVzZXJBdHRlbmRlZT8udXNlcklkLFxuICAgICAgICAgICAgICAgICAgICAgICAgaG9zdFN0YXJ0RGF0ZTogbWVldGluZ0Fzc2lzdD8ud2luZG93U3RhcnREYXRlLFxuICAgICAgICAgICAgICAgICAgICAgICAgaG9zdEVuZERhdGU6IG1lZXRpbmdBc3Npc3Q/LndpbmRvd0VuZERhdGUsXG4gICAgICAgICAgICAgICAgICAgICAgICB1c2VyVGltZXpvbmU6IGRheWpzLnR6Lmd1ZXNzKCksXG4gICAgICAgICAgICAgICAgICAgICAgICBob3N0VGltZXpvbmU6IG1lZXRpbmdBc3Npc3Q/LnRpbWV6b25lLFxuICAgICAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkLFxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgIH0pKT8uZGF0YVxuXG4gICAgICAgICAgICAgICAgaWYgKGV2ZW50cz8uWzBdPy5pZCkge1xuICAgICAgICAgICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgICAgICAgICB0aXRsZTogJ01lZXRpbmcgYWxyZWFkeSBjcmVhdGVkJyxcbiAgICAgICAgICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnU2VlbXMgbGlrZSBtZWV0aW5nIGlzIGFscmVhZHkgY3JlYXRlZCcsXG4gICAgICAgICAgICAgICAgICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgICAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWVcbiAgICAgICAgICAgICAgICAgICAgfSlcbiAgICAgICAgICAgICAgICAgICAgc2V0TWVldGluZ0FscmVhZHlDcmVhdGVkKHRydWUpXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBjYXRjaCAoZSkge1xuICAgICAgICAgICAgICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGNoZWNrIGlmIG1lZXRpbmcgYWxyZWFkeSBjcmVhdGVkJylcbiAgICAgICAgICAgIH1cbiAgICAgICAgfSkoKVxuICAgIH0sIFthdHRlbmRlZUlkLCBtZWV0aW5nQXNzaXN0Py5pZCwgbWVldGluZ0Fzc2lzdD8udGltZXpvbmUsIG1lZXRpbmdBc3Npc3Q/LnVzZXJJZCwgbWVldGluZ0Fzc2lzdD8ud2luZG93RW5kRGF0ZSwgbWVldGluZ0Fzc2lzdD8ud2luZG93U3RhcnREYXRlLCBtZWV0aW5nQXR0ZW5kZWVzLCBtZWV0aW5nSWQsIHRvYXN0XSlcbiAgICBcbiAgICBcbiAgICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgICAgICBwcmVmZXJyZWRUaW1lc0VuZFJlZj8uY3VycmVudD8uc2Nyb2xsSW50b1ZpZXcoe1xuICAgICAgICAgICAgYmVoYXZpb3I6ICdzbW9vdGgnLFxuICAgICAgICAgICAgYmxvY2s6ICdlbmQnLFxuICAgICAgICAgICAgaW5saW5lOiAnbmVhcmVzdCdcbiAgICAgICAgICAgIH0pO1xuICAgIH0sIFtwcmVmZXJyZWRUaW1lc1VJXSlcblxuICAgIGNvbnN0IG9uU2VsZWN0ZWRTbG90ID0gKGk6IG51bWJlcikgPT4ge1xuICAgICAgICBpZiAoIWF2YWlsYWJsZVNsb3RzQnlEYXRlKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZygnbm8gYXZhaWxhYmxlU2xvdHNCeURhdGUnKVxuICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cblxuICAgICAgICBpZiAobWVldGluZ0Fzc2lzdD8uY2FuY2VsbGVkKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZygnbWVldGluZyBpcyBjYW5jZWxsZWQnKVxuICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgIHRpdGxlOiAnTWVldGluZyBjYW5jZWxsZWQnLFxuICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnU2VlbXMgbGlrZSBtZWV0aW5nIGlzIGNhbmNlbGxlZCcsXG4gICAgICAgICAgICAgICAgc3RhdHVzOiAnd2FybmluZycsXG4gICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZVxuICAgICAgICAgICAgfSlcbiAgICAgICAgICAgIHJldHVyblxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKGRheWpzKCkuaXNBZnRlcihkYXlqcyhtZWV0aW5nQXNzaXN0Py53aW5kb3dFbmREYXRlPy5zbGljZSgwLCAxOSkpLnR6KG1lZXRpbmdBc3Npc3Q/LnRpbWV6b25lLCB0cnVlKS5mb3JtYXQoKSkpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKCdtZWV0aW5nIGlzIGV4cGlyZWQnKVxuICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgIHRpdGxlOiAnTWVldGluZyBleHBpcmVkJyxcbiAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1NlZW1zIGxpa2UgbWVldGluZyBpcyBleHBpcmVkJyxcbiAgICAgICAgICAgICAgICBzdGF0dXM6ICd3YXJuaW5nJyxcbiAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlXG4gICAgICAgICAgICB9KVxuICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cblxuICAgICAgICBpZiAobWVldGluZ0Fzc2lzdD8uZXhwaXJlRGF0ZSAmJiAoZGF5anMoKS5pc0FmdGVyKGRheWpzKG1lZXRpbmdBc3Npc3Q/LmV4cGlyZURhdGU/LnNsaWNlKDAsIDE5KSkudHoobWVldGluZ0Fzc2lzdD8udGltZXpvbmUsIHRydWUpLmZvcm1hdCgpKSkpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKCdtZWV0aW5nIGlzIGV4cGlyZWQnKVxuICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgIHRpdGxlOiAnTWVldGluZyBleHBpcmVkJyxcbiAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1NlZW1zIGxpa2UgbWVldGluZyBpcyBleHBpcmVkJyxcbiAgICAgICAgICAgICAgICBzdGF0dXM6ICd3YXJuaW5nJyxcbiAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlXG4gICAgICAgICAgICB9KVxuICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cblxuICAgICAgICBcblxuICAgICAgICBjb25zdCBuZXdBdmFpbGFibGVTbG90c0J5RGF0ZSA9IF8uY2xvbmVEZWVwKGF2YWlsYWJsZVNsb3RzQnlEYXRlKVxuICAgICAgICBcbiAgICAgICAgaWYgKCFuZXdBdmFpbGFibGVTbG90c0J5RGF0ZVtgJHtkYXlqcyhzZWxlY3RlZERhdGUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpfWBdPy5baV0/LmlkKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZygnbm8gYXZhaWxhYmxlIGRhdGUgc2xvdHMgYnkgZGF0ZScpXG4gICAgICAgICAgICByZXR1cm5cbiAgICAgICAgfVxuXG4gICAgICAgIG5ld0F2YWlsYWJsZVNsb3RzQnlEYXRlW2Ake2RheWpzKHNlbGVjdGVkRGF0ZSkuZm9ybWF0KCdZWVlZLU1NLUREJyl9YF1baV0uc2VsZWN0ZWQgPSAhbmV3QXZhaWxhYmxlU2xvdHNCeURhdGU/LltgJHtkYXlqcyhzZWxlY3RlZERhdGUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpfWBdPy5baV0/LnNlbGVjdGVkXG4gICAgICAgIGNvbnN0IHNlbGVjdGVkID0gbmV3QXZhaWxhYmxlU2xvdHNCeURhdGVbYCR7ZGF5anMoc2VsZWN0ZWREYXRlKS5mb3JtYXQoJ1lZWVktTU0tREQnKX1gXVtpXS5zZWxlY3RlZFxuICAgICAgICBzZXRBdmFpbGFibGVTbG90c0J5RGF0ZShuZXdBdmFpbGFibGVTbG90c0J5RGF0ZSlcblxuICAgICAgICBpZiAoc2VsZWN0ZWQpIHtcbiAgICAgICAgICAgIGNvbnN0IG5ld1B0ID0gY29udmVydFNsb3RUb1ByZWZlcnJlZFRpbWUobmV3QXZhaWxhYmxlU2xvdHNCeURhdGVbYCR7ZGF5anMoc2VsZWN0ZWREYXRlKS5mb3JtYXQoJ1lZWVktTU0tREQnKX1gXVtpXSlcblxuICAgICAgICAgICAgaWYgKCFuZXdQdD8uaWQpIHtcbiAgICAgICAgICAgICAgICBjb25zb2xlLmxvZygnbm8gbmV3UHQgY29udmVydGVkIGZyb20gc2xvdCcpXG4gICAgICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGFkZE5ld1ByZWZlcnJlZFRpbWUobmV3UHQsIG5ld0F2YWlsYWJsZVNsb3RzQnlEYXRlW2Ake2RheWpzKHNlbGVjdGVkRGF0ZSkuZm9ybWF0KCdZWVlZLU1NLUREJyl9YF1baV0/LmlkKVxuXG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBjb25zdCByZW1vdmVkUHQgPSBwcmVmZXJyZWRUaW1lc1VJPy5maW5kKHB0ID0+IChwdD8uc2xvdElkID09PSBuZXdBdmFpbGFibGVTbG90c0J5RGF0ZVtgJHtkYXlqcyhzZWxlY3RlZERhdGUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpfWBdW2ldPy5pZCkpXG5cbiAgICAgICAgICAgIGlmIChyZW1vdmVkUHQ/LmlkKSB7XG4gICAgICAgICAgICAgICAgcmVtb3ZlUHJlZmVycmVkVGltZShyZW1vdmVkUHQpXG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgICAgXG4gICAgfVxuXG4gICAgY29uc3QgY29udmVydEN1c3RvbUF2YWlsYWJsZVRpbWVUb1ByZWZlcnJlZCA9IChhdmFpbGFibGVUaW1lOiBDdXN0b21BdmFpbGFibGVUaW1lVHlwZSk6IE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlICYge1xuICAgICAgICBzbG90SWQ/OiBzdHJpbmcgfCB1bmRlZmluZWQ7XG4gICAgfSB8IHVuZGVmaW5lZCA9PiB7XG4gICAgICAgIGlmICghbWVldGluZ0Fzc2lzdD8udXNlcklkKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZygnbm8gdXNlcklkIHByZXNlbnQgaW5zaWRlIGNvbnZlcnR0b3ByZWZlcnJlZHRpbWUnKVxuICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgIHRpdGxlOiAnTm8gbWVldGluZyBwcmVzZW50JyxcbiAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1NlZW1zIGxpa2UgdGhlcmUgaXMgbm8gbWVldGluZyB0byBhbGxvdyB0aW1lIHByZWZlcmVuY2Ugc2VsZWN0aW9uJyxcbiAgICAgICAgICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZVxuICAgICAgICAgICAgfSlcbiAgICAgICAgICAgIHJldHVyblxuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgbmV3UHJlZmVycmVkVGltZTogTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgbWVldGluZ0lkLFxuICAgICAgICAgICAgZGF5T2ZXZWVrOiBhdmFpbGFibGVUaW1lPy5kYXlPZldlZWtJbnQgPT09IC0xID8gdW5kZWZpbmVkIDogYXZhaWxhYmxlVGltZT8uZGF5T2ZXZWVrSW50LFxuICAgICAgICAgICAgc3RhcnRUaW1lOiBhdmFpbGFibGVUaW1lPy5zdGFydFRpbWUgYXMgVGltZSxcbiAgICAgICAgICAgIGVuZFRpbWU6IGF2YWlsYWJsZVRpbWU/LmVuZFRpbWUgYXMgVGltZSxcbiAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgaG9zdElkOiBtZWV0aW5nQXNzaXN0Py51c2VySWQgYXMgc3RyaW5nLFxuICAgICAgICAgICAgYXR0ZW5kZWVJZCxcbiAgICAgICAgfVxuXG4gICAgICAgIHJldHVybiBuZXdQcmVmZXJyZWRUaW1lXG4gICAgfVxuXG4gICAgY29uc3Qgb25TdWJtaXRDdXN0b21BdmFpbGFibGVUaW1lID0gKGF2YWlsYWJsZVRpbWU6IEN1c3RvbUF2YWlsYWJsZVRpbWVUeXBlKSA9PiB7XG4gICAgICAgIG9uQ2xvc2UoKVxuXG4gICAgICAgIGlmIChkYXlqcygpLmlzQWZ0ZXIoZGF5anMobWVldGluZ0Fzc2lzdD8ud2luZG93RW5kRGF0ZT8uc2xpY2UoMCwgMTkpKS50eihtZWV0aW5nQXNzaXN0Py50aW1lem9uZSwgdHJ1ZSkuZm9ybWF0KCkpKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZygnbWVldGluZyBpcyBleHBpcmVkJylcbiAgICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgICAgICB0aXRsZTogJ01lZXRpbmcgZXhwaXJlZCcsXG4gICAgICAgICAgICAgICAgZGVzY3JpcHRpb246ICdTZWVtcyBsaWtlIG1lZXRpbmcgaXMgZXhwaXJlZCcsXG4gICAgICAgICAgICAgICAgc3RhdHVzOiAnd2FybmluZycsXG4gICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZVxuICAgICAgICAgICAgfSlcbiAgICAgICAgICAgIHJldHVyblxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKG1lZXRpbmdBc3Npc3Q/LmV4cGlyZURhdGUgJiYgKGRheWpzKCkuaXNBZnRlcihkYXlqcyhtZWV0aW5nQXNzaXN0Py5leHBpcmVEYXRlPy5zbGljZSgwLCAxOSkpLnR6KG1lZXRpbmdBc3Npc3Q/LnRpbWV6b25lLCB0cnVlKS5mb3JtYXQoKSkpKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZygnbWVldGluZyBpcyBleHBpcmVkJylcbiAgICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgICAgICB0aXRsZTogJ01lZXRpbmcgZXhwaXJlZCcsXG4gICAgICAgICAgICAgICAgZGVzY3JpcHRpb246ICdTZWVtcyBsaWtlIG1lZXRpbmcgaXMgZXhwaXJlZCcsXG4gICAgICAgICAgICAgICAgc3RhdHVzOiAnd2FybmluZycsXG4gICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZVxuICAgICAgICAgICAgfSlcbiAgICAgICAgICAgIHJldHVyblxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKG1lZXRpbmdBc3Npc3Q/LmNhbmNlbGxlZCkge1xuICAgICAgICAgICAgY29uc29sZS5sb2coJ21lZXRpbmcgaXMgY2FuY2VsbGVkJylcbiAgICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgICAgICB0aXRsZTogJ01lZXRpbmcgY2FuY2VsbGVkJyxcbiAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1NlZW1zIGxpa2UgbWVldGluZyBpcyBjYW5jZWxsZWQnLFxuICAgICAgICAgICAgICAgIHN0YXR1czogJ3dhcm5pbmcnLFxuICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWVcbiAgICAgICAgICAgIH0pXG4gICAgICAgICAgICByZXR1cm5cbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IG5ld1ByZWZlcnJlZFRpbWUgPSBjb252ZXJ0Q3VzdG9tQXZhaWxhYmxlVGltZVRvUHJlZmVycmVkKFxuICAgICAgICAgICAgYXZhaWxhYmxlVGltZSxcbiAgICAgICAgKVxuICAgICAgICBcbiAgICAgICAgaWYgKCFuZXdQcmVmZXJyZWRUaW1lKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZygnbmV3UHJlZmVycmVkVGltZSBpcyB1bmRlZmluZWQnKVxuICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cbiAgICAgICAgY29uc3QgbmV3UHJlZmVycmVkVGltZXNVSSA9IF8uY2xvbmVEZWVwKHByZWZlcnJlZFRpbWVzVUkpIHx8IFtdXG5cbiAgICAgICAgbmV3UHJlZmVycmVkVGltZXNVSS5wdXNoKGNvbnZlcnRQVFIyUERSKG5ld1ByZWZlcnJlZFRpbWUpKVxuXG4gICAgICAgIHNldFByZWZlcnJlZFRpbWVzVUkobmV3UHJlZmVycmVkVGltZXNVSSlcblxuICAgICAgICBjb25zdCBuZXdDdXN0b21QcmVmZXJyZWRUaW1lcyA9IF8uY2xvbmVEZWVwKGN1c3RvbVByZWZlcnJlZFRpbWVzKSB8fCBbXVxuXG4gICAgICAgIG5ld0N1c3RvbVByZWZlcnJlZFRpbWVzLnB1c2goY29udmVydFBUUjJQRFIobmV3UHJlZmVycmVkVGltZSkpXG5cbiAgICAgICAgc2V0Q3VzdG9tUHJlZmVycmVkVGltZXMobmV3Q3VzdG9tUHJlZmVycmVkVGltZXMpXG5cbiAgICB9XG5cbiAgICBjb25zdCBvbkNhbmNlbEN1c3RvbUF2YWlsYWJsZVRpbWUgPSAoKSA9PiBvbkNsb3NlKClcbiAgICAgICAgXG4gICAgY29uc3QgY29udmVydFNsb3RUb1ByZWZlcnJlZFRpbWUgPSAoc2xvdDogQXZhaWxhYmxlU2xvdCk6IE1lZXRpbmdBc3Npc3RQcmVmZXJyZWREYXRlUmFuZ2VUeXBlIHwgdW5kZWZpbmVkID0+IHtcbiAgICAgICAgaWYgKCFtZWV0aW5nQXNzaXN0Py51c2VySWQpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKCdubyB1c2VySWQgcHJlc2VudCBpbnNpZGUgY29udmVydHRvcHJlZmVycmVkdGltZScpXG4gICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgdGl0bGU6ICdObyBtZWV0aW5nIHByZXNlbnQnLFxuICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnU2VlbXMgbGlrZSB0aGVyZSBpcyBubyBtZWV0aW5nIHRvIGFsbG93IHRpbWUgcHJlZmVyZW5jZSBzZWxlY3Rpb24nLFxuICAgICAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlXG4gICAgICAgICAgICB9KVxuICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cbiAgICAgICAgY29uc3QgbmV3UHJlZmVycmVkVGltZTogTWVldGluZ0Fzc2lzdFByZWZlcnJlZERhdGVSYW5nZVR5cGUgPSB7XG4gICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgbWVldGluZ0lkLFxuICAgICAgICAgICAgZGF5T2ZXZWVrOiBnZXRJU09EYXkoZGF5anMoc2VsZWN0ZWREYXRlKS50b0RhdGUoKSksXG4gICAgICAgICAgICBzdGFydFRpbWU6IGRheWpzKHNsb3Q/LnN0YXJ0RGF0ZSkuZm9ybWF0KCksXG4gICAgICAgICAgICBlbmRUaW1lOiBkYXlqcyhzbG90Py5lbmREYXRlKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgaG9zdElkOiBtZWV0aW5nQXNzaXN0Py51c2VySWQgYXMgc3RyaW5nLFxuICAgICAgICAgICAgYXR0ZW5kZWVJZCxcbiAgICAgICAgfVxuXG4gICAgICAgIHJldHVybiBuZXdQcmVmZXJyZWRUaW1lXG4gICAgfVxuXG4gICAgY29uc3QgYWRkTmV3UHJlZmVycmVkVGltZSA9IChcbiAgICAgICAgbmV3UHQ6IE1lZXRpbmdBc3Npc3RQcmVmZXJyZWREYXRlUmFuZ2VUeXBlLFxuICAgICAgICBzbG90SWQ6IHN0cmluZyxcbiAgICApID0+IHtcbiAgICAgICAgaWYgKCFuZXdQdD8uaWQpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKCdubyBuZXdQdCBwcmVzZW50IGluc2lkZSBhZGROZXdQcmVmZXJyZWRUaW1lJylcbiAgICAgICAgICAgIHJldHVyblxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKGRheWpzKCkuaXNBZnRlcihkYXlqcyhtZWV0aW5nQXNzaXN0Py53aW5kb3dFbmREYXRlPy5zbGljZSgwLCAxOSkpLnR6KG1lZXRpbmdBc3Npc3Q/LnRpbWV6b25lLCB0cnVlKS5mb3JtYXQoKSkpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKCdtZWV0aW5nIGlzIGV4cGlyZWQnKVxuICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgIHRpdGxlOiAnTWVldGluZyBleHBpcmVkJyxcbiAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1NlZW1zIGxpa2UgbWVldGluZyBpcyBleHBpcmVkJyxcbiAgICAgICAgICAgICAgICBzdGF0dXM6ICd3YXJuaW5nJyxcbiAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlXG4gICAgICAgICAgICB9KVxuICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cblxuICAgICAgICBpZiAobWVldGluZ0Fzc2lzdD8uZXhwaXJlRGF0ZSAmJiAoZGF5anMoKS5pc0FmdGVyKGRheWpzKG1lZXRpbmdBc3Npc3Q/LmV4cGlyZURhdGU/LnNsaWNlKDAsIDE5KSkudHoobWVldGluZ0Fzc2lzdD8udGltZXpvbmUsIHRydWUpLmZvcm1hdCgpKSkpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKCdtZWV0aW5nIGlzIGV4cGlyZWQnKVxuICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgIHRpdGxlOiAnTWVldGluZyBleHBpcmVkJyxcbiAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1NlZW1zIGxpa2UgbWVldGluZyBpcyBleHBpcmVkJyxcbiAgICAgICAgICAgICAgICBzdGF0dXM6ICd3YXJuaW5nJyxcbiAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlXG4gICAgICAgICAgICB9KVxuICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cblxuICAgICAgICBpZiAobWVldGluZ0FscmVhZHlDcmVhdGVkIHx8IG1lZXRpbmdBc3Npc3Q/LmNhbmNlbGxlZCkge1xuICAgICAgICAgICAgY29uc29sZS5sb2coJ21lZXRpbmcgYWxyZWFkeSBjcmVhdGVkJylcbiAgICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgdGl0bGU6ICdNZWV0aW5nIGFscmVhZHkgY3JlYXRlZCcsXG4gICAgICAgICAgICAgICAgZGVzY3JpcHRpb246ICdTZWVtcyBsaWtlIG1lZXRpbmcgaXMgYWxyZWFkeSBjcmVhdGVkJyxcbiAgICAgICAgICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZVxuICAgICAgICAgICAgfSlcbiAgICAgICAgICAgIHJldHVyblxuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgY2xvbmVkTmV3UHJlZmVycmVkVGltZXMgPSAoXy5jbG9uZURlZXAobmV3UHJlZmVycmVkVGltZXMpXG4gICAgICAgICAgICB8fCBbXSkgYXMgKE1lZXRpbmdBc3Npc3RQcmVmZXJyZWREYXRlUmFuZ2VUeXBlICYgeyBzbG90SWQ6IHN0cmluZyB9KVtdXG4gICAgICAgIGNsb25lZE5ld1ByZWZlcnJlZFRpbWVzLnB1c2goey4uLm5ld1B0LCBzbG90SWQgfSBhcyBNZWV0aW5nQXNzaXN0UHJlZmVycmVkRGF0ZVJhbmdlVHlwZSAmIHsgc2xvdElkOiBzdHJpbmc7IH0pXG4gICAgICAgIHNldE5ld1ByZWZlcnJlZFRpbWVzKGNsb25lZE5ld1ByZWZlcnJlZFRpbWVzKVxuXG4gICAgICAgIGNvbnN0IGNsb25lZFByZWZlcnJlZFRpbWVzVUkgPSAoXy5jbG9uZURlZXAocHJlZmVycmVkVGltZXNVSSkgfHwgW10pXG4gICAgICAgIGNsb25lZFByZWZlcnJlZFRpbWVzVUkucHVzaCh7IC4uLm5ld1B0LCBzbG90SWQgfSBhcyBNZWV0aW5nQXNzaXN0UHJlZmVycmVkRGF0ZVJhbmdlVHlwZSAmIHsgc2xvdElkOiBzdHJpbmc7IH0pXG4gICAgICAgIHNldFByZWZlcnJlZFRpbWVzVUkoY2xvbmVkUHJlZmVycmVkVGltZXNVSSlcbiAgICB9XG5cbiAgICBjb25zdCByZW1vdmVQcmVmZXJyZWRUaW1lID0gKFxuICAgICAgICByZW1vdmVkUHQ6IE1lZXRpbmdBc3Npc3RQcmVmZXJyZWREYXRlUmFuZ2VUeXBlLFxuICAgICkgPT4ge1xuICAgICAgICBpZiAoIXJlbW92ZWRQdD8uaWQpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKCdubyByZW1vdmVkUHQgZm91bmQnKVxuICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cblxuXG4gICAgICAgIGlmIChtZWV0aW5nQWxyZWFkeUNyZWF0ZWQgfHwgbWVldGluZ0Fzc2lzdD8uY2FuY2VsbGVkKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZygnbWVldGluZyBhbHJlYWR5IGNyZWF0ZWQgaW5zaWRlIHJlbW92ZWRQcmVmZXJyZWRUaW1lJylcbiAgICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgdGl0bGU6ICdNZWV0aW5nIGFscmVhZHkgY3JlYXRlZCcsXG4gICAgICAgICAgICAgICAgZGVzY3JpcHRpb246ICdTZWVtcyBsaWtlIG1lZXRpbmcgaXMgYWxyZWFkeSBjcmVhdGVkJyxcbiAgICAgICAgICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZVxuICAgICAgICAgICAgfSlcbiAgICAgICAgICAgIHJldHVyblxuICAgICAgICB9XG5cblxuICAgICAgICBjb25zdCBjbG9uZWRQcmVmZXJyZWRUaW1lc1VJID0gKF8uY2xvbmVEZWVwKHByZWZlcnJlZFRpbWVzVUkpIHx8IFtdKVxuXG4gICAgICAgIGNvbnN0IGZvdW5kSW5kZXggPSBjbG9uZWRQcmVmZXJyZWRUaW1lc1VJLmZpbmRJbmRleChwdCA9PiAocHQ/LmlkID09PSByZW1vdmVkUHQ/LmlkKSlcblxuICAgICAgICBpZiAoZm91bmRJbmRleCA+IC0xKSB7XG4gICAgICAgICAgICBjb25zdCBuZXdDbG9uZWRQcmVmZXJyZWRUaW1lc1VJID0gY2xvbmVkUHJlZmVycmVkVGltZXNVSVxuICAgICAgICAgICAgICAgIC5zbGljZSgwLCBmb3VuZEluZGV4KVxuICAgICAgICAgICAgICAgIC5jb25jYXQoY2xvbmVkUHJlZmVycmVkVGltZXNVSS5zbGljZShmb3VuZEluZGV4ICsgMSkpXG4gICAgICAgICAgICBcbiAgICAgICAgICAgIHNldFByZWZlcnJlZFRpbWVzVUkobmV3Q2xvbmVkUHJlZmVycmVkVGltZXNVSSlcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IGZvdW5kT2xkSW5kZXggPSBvbGRQcmVmZXJyZWRUaW1lcz8uZmluZEluZGV4KG9QdCA9PiAob1B0Py5pZCA9PT0gcmVtb3ZlZFB0Py5pZCkpXG5cbiAgICAgICAgaWYgKChmb3VuZE9sZEluZGV4KSAmJiAoZm91bmRPbGRJbmRleCA+IC0xKSkge1xuXG4gICAgICAgICAgICBjb25zdCBjbG9uZWRQcmVmZXJyZWRUaW1lc1JlbW92ZWQgPSAoXy5jbG9uZURlZXAocHJlZmVycmVkVGltZXNSZW1vdmVkKSB8fCBbXSkgYXMgTWVldGluZ0Fzc2lzdFByZWZlcnJlZERhdGVSYW5nZVR5cGVbXVxuICAgICAgICAgICAgY2xvbmVkUHJlZmVycmVkVGltZXNSZW1vdmVkLnB1c2gocmVtb3ZlZFB0KVxuICAgICAgICAgICAgc2V0UHJlZmVycmVkVGltZXNSZW1vdmVkKGNsb25lZFByZWZlcnJlZFRpbWVzUmVtb3ZlZClcblxuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgZm91bmROZXdJbmRleCA9IG5ld1ByZWZlcnJlZFRpbWVzPy5maW5kSW5kZXgocHQgPT4gKHB0Py5pZCA9PT0gcmVtb3ZlZFB0Py5pZCkpXG5cbiAgICAgICAgaWYgKChmb3VuZE5ld0luZGV4KSAmJiAoZm91bmROZXdJbmRleCA+IC0xKSkge1xuICAgICAgICAgICAgY29uc3Qgc2xpY2VkTmV3UHJlZmVycmVkVGltZXMgPSBuZXdQcmVmZXJyZWRUaW1lc1xuICAgICAgICAgICAgICAgID8uc2xpY2UoMCwgZm91bmROZXdJbmRleClcbiAgICAgICAgICAgICAgICA/LmNvbmNhdChuZXdQcmVmZXJyZWRUaW1lcz8uc2xpY2UoZm91bmROZXdJbmRleCArIDEpKVxuXG4gICAgICAgICAgICBzZXROZXdQcmVmZXJyZWRUaW1lcyhzbGljZWROZXdQcmVmZXJyZWRUaW1lcylcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IGZvdW5kQ3VzdG9tSW5kZXggPSBjdXN0b21QcmVmZXJyZWRUaW1lcz8uZmluZEluZGV4KGMgPT4gKGM/LmlkID09PSByZW1vdmVkUHQ/LmlkKSlcblxuICAgICAgICBpZiAoKGZvdW5kQ3VzdG9tSW5kZXgpICYmIChmb3VuZEN1c3RvbUluZGV4ID4gLTEpKSB7XG4gICAgICAgICAgICBjb25zdCBzbGljZWRDdXN0b21QcmVmZXJyZWRUaW1lcyA9IGN1c3RvbVByZWZlcnJlZFRpbWVzXG4gICAgICAgICAgICAgICAgPy5zbGljZSgwLCBmb3VuZEN1c3RvbUluZGV4KVxuICAgICAgICAgICAgICAgID8uY29uY2F0KGN1c3RvbVByZWZlcnJlZFRpbWVzPy5zbGljZShmb3VuZEN1c3RvbUluZGV4ICsgMSkpXG5cbiAgICAgICAgICAgIHNldEN1c3RvbVByZWZlcnJlZFRpbWVzKHNsaWNlZEN1c3RvbVByZWZlcnJlZFRpbWVzKVxuICAgICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgcmVtb3ZlUHJlZmVycmVkVGltZUJ5SW5kZXggPSAoaW5kZXg6IG51bWJlcikgPT4ge1xuICAgICAgICBpZiAobWVldGluZ0Fzc2lzdD8uY2FuY2VsbGVkKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZygnbWVldGluZyBpcyBjYW5jZWxsZWQnKVxuICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgIHRpdGxlOiAnTWVldGluZyBjYW5jZWxsZWQnLFxuICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnU2VlbXMgbGlrZSBtZWV0aW5nIGlzIGNhbmNlbGxlZCcsXG4gICAgICAgICAgICAgICAgc3RhdHVzOiAnd2FybmluZycsXG4gICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZVxuICAgICAgICAgICAgfSlcbiAgICAgICAgICAgIHJldHVyblxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKGRheWpzKCkuaXNBZnRlcihkYXlqcyhtZWV0aW5nQXNzaXN0Py53aW5kb3dFbmREYXRlPy5zbGljZSgwLCAxOSkpLnR6KG1lZXRpbmdBc3Npc3Q/LnRpbWV6b25lLCB0cnVlKS5mb3JtYXQoKSkpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKCdtZWV0aW5nIGlzIGV4cGlyZWQnKVxuICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgIHRpdGxlOiAnTWVldGluZyBleHBpcmVkJyxcbiAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1NlZW1zIGxpa2UgbWVldGluZyBpcyBleHBpcmVkJyxcbiAgICAgICAgICAgICAgICBzdGF0dXM6ICd3YXJuaW5nJyxcbiAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlXG4gICAgICAgICAgICB9KVxuICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cblxuICAgICAgICBpZiAobWVldGluZ0Fzc2lzdD8uZXhwaXJlRGF0ZSAmJiAoZGF5anMoKS5pc0FmdGVyKGRheWpzKG1lZXRpbmdBc3Npc3Q/LmV4cGlyZURhdGU/LnNsaWNlKDAsIDE5KSkudHoobWVldGluZ0Fzc2lzdD8udGltZXpvbmUsIHRydWUpLmZvcm1hdCgpKSkpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKCdtZWV0aW5nIGlzIGV4cGlyZWQnKVxuICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgIHRpdGxlOiAnTWVldGluZyBleHBpcmVkJyxcbiAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1NlZW1zIGxpa2UgbWVldGluZyBpcyBleHBpcmVkJyxcbiAgICAgICAgICAgICAgICBzdGF0dXM6ICd3YXJuaW5nJyxcbiAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlXG4gICAgICAgICAgICB9KVxuICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCByZW1vdmVkUHQgPSBwcmVmZXJyZWRUaW1lc1VJPy5baW5kZXhdXG5cbiAgICAgICAgaWYgKCFyZW1vdmVkUHQ/LmlkKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZygnIHNvbWV0aGluZyB3ZW50IHdyb25nIHJlbW92ZWRQdCBub3QgZm91bmQnKVxuICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cblxuICAgICAgICByZW1vdmVQcmVmZXJyZWRUaW1lKHJlbW92ZWRQdClcblxuICAgIH1cblxuICAgIGNvbnN0IHJlbW92ZVByZWZlcnJlZFRpbWVzSW5EYiA9IGFzeW5jICgpID0+IHtcbiAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgIGNvbnN0IGlkcyA9IHByZWZlcnJlZFRpbWVzUmVtb3ZlZD8ubWFwKHB0ID0+IChwdD8uaWQpKVxuXG4gICAgICAgICAgICBpZiAoaWRzPy5bMF0pIHtcbiAgICAgICAgICAgICAgICByZXR1cm4gYXhpb3MucG9zdCgnL2FwaS90aW1lLXByZWZlcmVuY2VzJywge1xuICAgICAgICAgICAgICAgICAgICBtZXRob2Q6ICdkZWxldGVNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZXNCeUlkcycsXG4gICAgICAgICAgICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgICAgICAgICAgICAgaWRzLFxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICB9XG4gICAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHJlbW92ZSBwcmVmZXJyZWQgdGltZXMnKVxuICAgICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgY29udmVydFByZWZlcnJlZFRpbWVzSW5Vc2VyVGltZVpvbmVUb0hvc3RUaW1lWm9uZSA9IChwcmVmZXJyZWRUaW1lc1RvQ29udmVydDogTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXSwgaG9zdFRpbWV6b25lOiBzdHJpbmcpID0+IHtcbiAgICAgICAgY29uc3QgY29udmVydGVkUHJlZmVycmVkVGltZXMgPSBwcmVmZXJyZWRUaW1lc1RvQ29udmVydD8ubWFwKHB0ID0+IHtcbiAgICAgICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICAgICAgLi4ucHQsXG4gICAgICAgICAgICAgICAgc3RhcnRUaW1lOiBkYXlqcyhwdD8uc3RhcnRUaW1lLCAnSEg6bW0nLCB0cnVlKS50eihkYXlqcy50ei5ndWVzcygpLCB0cnVlKS50eihob3N0VGltZXpvbmUpLmZvcm1hdCgnSEg6bW0nKSxcbiAgICAgICAgICAgICAgICBlbmRUaW1lOiBkYXlqcyhwdD8uZW5kVGltZSwgJ0hIOm1tJywgdHJ1ZSkudHooZGF5anMudHouZ3Vlc3MoKSwgdHJ1ZSkudHooaG9zdFRpbWV6b25lKS5mb3JtYXQoJ0hIOm1tJyksXG4gICAgICAgICAgICB9XG4gICAgICAgIH0pXG5cbiAgICAgICAgcmV0dXJuIGNvbnZlcnRlZFByZWZlcnJlZFRpbWVzXG4gICAgfVxuXG4gICAgY29uc3QgY29udmVydFRvUHJlZmVycmVkVGltZXNGb3JNZWV0aW5nQXNzaXN0ID0gKCkgPT4ge1xuICAgICAgICBjb25zdCBwcmVmZXJyZWRUaW1lc0FkZGVkSW5Vc2VyVGltZXpvbmUgPSBbXVxuICAgICAgICBsZXQgcHJlZmVycmVkVGltZXNBZGRlZEluVXNlclRpbWV6b25lVmlhU2xvdHM6ICgoTWVldGluZ0Fzc2lzdFByZWZlcnJlZERhdGVSYW5nZVR5cGUgJiB7IHNsb3RJZDogc3RyaW5nIH0pIHwgdW5kZWZpbmVkKVtdIHwgeyBpZDogYW55IH1bXSA9IFtdXG5cbiAgICAgICAgaWYgKG5ld1ByZWZlcnJlZFRpbWVzICYmIChuZXdQcmVmZXJyZWRUaW1lcz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgICAgICAgIHByZWZlcnJlZFRpbWVzQWRkZWRJblVzZXJUaW1lem9uZVZpYVNsb3RzID0gbmV3UHJlZmVycmVkVGltZXM/Lm1hcChwdCA9PiBfLm9taXQocHQsIFsnc2xvdElkJ10pKVxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKHByZWZlcnJlZFRpbWVzQWRkZWRJblVzZXJUaW1lem9uZVZpYVNsb3RzPy5bMF0/LmlkKSB7XG4gICAgICAgICAgICBwcmVmZXJyZWRUaW1lc0FkZGVkSW5Vc2VyVGltZXpvbmUucHVzaCguLi5wcmVmZXJyZWRUaW1lc0FkZGVkSW5Vc2VyVGltZXpvbmVWaWFTbG90cylcbiAgICAgICAgfVxuXG4gICAgICAgIGxldCBjdXN0b21QcmVmZXJyZWRUaW1lc0FkZGVkSW5Vc2VyOiAoKE1lZXRpbmdBc3Npc3RQcmVmZXJyZWREYXRlUmFuZ2VUeXBlICYgeyBzbG90SWQ/OiBzdHJpbmcgfCB1bmRlZmluZWQgfSkgfCB1bmRlZmluZWQpW10gfCB7IGlkOiBhbnkgfVtdID0gW11cblxuICAgICAgICBpZiAoY3VzdG9tUHJlZmVycmVkVGltZXMgJiYgKGN1c3RvbVByZWZlcnJlZFRpbWVzPy5sZW5ndGggPiAwKSkge1xuICAgICAgICAgICAgY3VzdG9tUHJlZmVycmVkVGltZXNBZGRlZEluVXNlciA9IGN1c3RvbVByZWZlcnJlZFRpbWVzPy5tYXAocHQgPT4gXy5vbWl0KHB0LCBbJ3Nsb3RJZCddKSlcbiAgICAgICAgfVxuXG4gICAgICAgIGlmIChjdXN0b21QcmVmZXJyZWRUaW1lc0FkZGVkSW5Vc2VyPy5bMF0/LmlkKSB7XG4gICAgICAgICAgICBwcmVmZXJyZWRUaW1lc0FkZGVkSW5Vc2VyVGltZXpvbmUucHVzaCguLi5jdXN0b21QcmVmZXJyZWRUaW1lc0FkZGVkSW5Vc2VyKVxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKG9sZFByZWZlcnJlZFRpbWVzPy5bMF0/LmlkKSB7XG4gICAgICAgICAgICBwcmVmZXJyZWRUaW1lc0FkZGVkSW5Vc2VyVGltZXpvbmUucHVzaCguLi5vbGRQcmVmZXJyZWRUaW1lcylcbiAgICAgICAgfVxuXG4gICAgICAgIGlmICghcHJlZmVycmVkVGltZXNBZGRlZEluVXNlclRpbWV6b25lPy5bMF0/LmlkKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZygnIHVuZGVmaW5lZCBwcmVmZXJyZWRUaW1lcyBpbnNpZGUgY29udmVydFRvUHJlZmVycmVkVGltZXNGb3JNZWV0aW5nQXNzaXN0JylcbiAgICAgICAgICAgIHJldHVyblxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKCFtZWV0aW5nQXNzaXN0Py50aW1lem9uZSkge1xuICAgICAgICAgICAgY29uc29sZS5sb2coJ25vIG1lZXRpbmcgYXNzc2l0IGluc2lkZSBhZGRQcmVmZXJyZWRUaW1lc0luRGInKVxuICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgIHRpdGxlOiAnTWVldGluZyBkb2VzIG5vdCBleGlzdCcsXG4gICAgICAgICAgICAgICAgZGVzY3JpcHRpb246ICdTZWVtcyBsaWtlIG1lZXRpbmcgZG9lcyBub3QgZXhpc3QnLFxuICAgICAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlXG4gICAgICAgICAgICB9KVxuICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cbiAgICAgICAgICAgIFxuICAgICAgICBjb25zb2xlLmxvZyhwcmVmZXJyZWRUaW1lc0FkZGVkSW5Vc2VyVGltZXpvbmUsICcgcHJlZmVycmVkVGltZXNBZGRlZEluVXNlclRpbWV6b25lJylcblxuICAgICAgICBpZiAocHJlZmVycmVkVGltZXNBZGRlZEluVXNlclRpbWV6b25lICYmIChwcmVmZXJyZWRUaW1lc0FkZGVkSW5Vc2VyVGltZXpvbmU/Lmxlbmd0aCA+IDApKSB7XG4gICAgICAgICAgICBjb25zdCBjb252ZXJ0ZWRQcmVmZXJyZWRUaW1lcyA9IGNvbnZlcnRQcmVmZXJyZWRUaW1lc0luVXNlclRpbWVab25lVG9Ib3N0VGltZVpvbmUoXG4gICAgICAgICAgICAgICAgcHJlZmVycmVkVGltZXNBZGRlZEluVXNlclRpbWV6b25lPy5tYXAocGQgPT4gY29udmVydFBEUjJQVFIocGQgYXMgTWVldGluZ0Fzc2lzdFByZWZlcnJlZERhdGVSYW5nZVR5cGUgJiB7IHNsb3RJZD86IHN0cmluZyB8IHVuZGVmaW5lZDsgfSkpLFxuICAgICAgICAgICAgICAgIG1lZXRpbmdBc3Npc3Q/LnRpbWV6b25lLFxuICAgICAgICAgICAgKVxuXG4gICAgICAgICAgICByZXR1cm4gY29udmVydGVkUHJlZmVycmVkVGltZXNcblxuICAgICAgICB9XG5cbiAgICAgICAgcmV0dXJuIG51bGxcbiAgICB9XG5cbiAgICBjb25zdCBhZGRQcmVmZXJyZWRUaW1lc0luRGIgPSBhc3luYyAoKSA9PiB7XG4gICAgICAgIHRyeSB7XG4gICAgICAgICAgICBjb25zdCBwcmVmZXJyZWRUaW1lc0FkZGVkSW5Vc2VyVGltZXpvbmUgPSBbXVxuICAgICAgICAgICAgbGV0IHByZWZlcnJlZFRpbWVzQWRkZWRJblVzZXJUaW1lem9uZVZpYVNsb3RzOiAoKE1lZXRpbmdBc3Npc3RQcmVmZXJyZWREYXRlUmFuZ2VUeXBlICYgeyBzbG90SWQ6IHN0cmluZyB9KSB8IHVuZGVmaW5lZClbXSB8IHsgaWQ6IGFueSB9W10gPSBbXVxuXG4gICAgICAgICAgICBpZiAobmV3UHJlZmVycmVkVGltZXMgJiYgKG5ld1ByZWZlcnJlZFRpbWVzPy5sZW5ndGggPiAwKSkge1xuICAgICAgICAgICAgICAgIHByZWZlcnJlZFRpbWVzQWRkZWRJblVzZXJUaW1lem9uZVZpYVNsb3RzID0gbmV3UHJlZmVycmVkVGltZXM/Lm1hcChwdCA9PiBfLm9taXQocHQsIFsnc2xvdElkJ10pKVxuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBpZiAocHJlZmVycmVkVGltZXNBZGRlZEluVXNlclRpbWV6b25lVmlhU2xvdHM/LlswXT8uaWQpIHtcbiAgICAgICAgICAgICAgICBwcmVmZXJyZWRUaW1lc0FkZGVkSW5Vc2VyVGltZXpvbmUucHVzaCguLi5wcmVmZXJyZWRUaW1lc0FkZGVkSW5Vc2VyVGltZXpvbmVWaWFTbG90cylcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgbGV0IGN1c3RvbVByZWZlcnJlZFRpbWVzQWRkZWRJblVzZXI6ICgoTWVldGluZ0Fzc2lzdFByZWZlcnJlZERhdGVSYW5nZVR5cGUgJiB7IHNsb3RJZD86IHN0cmluZyB8IHVuZGVmaW5lZCB9KSB8IHVuZGVmaW5lZClbXSB8IHsgaWQ6IGFueSB9W10gPSBbXVxuXG4gICAgICAgICAgICBpZiAoY3VzdG9tUHJlZmVycmVkVGltZXMgJiYgKGN1c3RvbVByZWZlcnJlZFRpbWVzPy5sZW5ndGggPiAwKSkge1xuICAgICAgICAgICAgICAgIGN1c3RvbVByZWZlcnJlZFRpbWVzQWRkZWRJblVzZXIgPSBjdXN0b21QcmVmZXJyZWRUaW1lcz8ubWFwKHB0ID0+IF8ub21pdChwdCwgWydzbG90SWQnXSkpXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGlmIChjdXN0b21QcmVmZXJyZWRUaW1lc0FkZGVkSW5Vc2VyPy5bMF0/LmlkKSB7XG4gICAgICAgICAgICAgICAgcHJlZmVycmVkVGltZXNBZGRlZEluVXNlclRpbWV6b25lLnB1c2goLi4uY3VzdG9tUHJlZmVycmVkVGltZXNBZGRlZEluVXNlcilcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgaWYgKCFwcmVmZXJyZWRUaW1lc0FkZGVkSW5Vc2VyVGltZXpvbmU/LlswXT8uaWQpIHtcbiAgICAgICAgICAgICAgICBjb25zb2xlLmxvZygnIHVuZGVmaW5lZCBwcmVmZXJyZWRUaW1lcycpXG4gICAgICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGlmICghbWVldGluZ0Fzc2lzdD8udGltZXpvbmUpIHtcbiAgICAgICAgICAgICAgICBjb25zb2xlLmxvZygnbm8gbWVldGluZyBhc3NzaXQgaW5zaWRlIGFkZFByZWZlcnJlZFRpbWVzSW5EYicpXG4gICAgICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgICAgICB0aXRsZTogJ01lZXRpbmcgZG9lcyBub3QgZXhpc3QnLFxuICAgICAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1NlZW1zIGxpa2UgbWVldGluZyBkb2VzIG5vdCBleGlzdCcsXG4gICAgICAgICAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWVcbiAgICAgICAgICAgICAgICB9KVxuICAgICAgICAgICAgICAgIHJldHVyblxuICAgICAgICAgICAgfVxuICAgICAgICAgICAgY29uc29sZS5sb2cocHJlZmVycmVkVGltZXNBZGRlZEluVXNlclRpbWV6b25lLCAnIHByZWZlcnJlZFRpbWVzQWRkZWRJblVzZXJUaW1lem9uZScpXG5cbiAgICAgICAgICAgIGlmIChwcmVmZXJyZWRUaW1lc0FkZGVkSW5Vc2VyVGltZXpvbmUgJiYgKHByZWZlcnJlZFRpbWVzQWRkZWRJblVzZXJUaW1lem9uZT8ubGVuZ3RoID4gMCkpIHtcbiAgICAgICAgICAgICAgICBjb25zdCBjb252ZXJ0ZWRQcmVmZXJyZWRUaW1lcyA9IGNvbnZlcnRQcmVmZXJyZWRUaW1lc0luVXNlclRpbWVab25lVG9Ib3N0VGltZVpvbmUoXG4gICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZFRpbWVzQWRkZWRJblVzZXJUaW1lem9uZT8ubWFwKHBkID0+IGNvbnZlcnRQRFIyUFRSKHBkIGFzIE1lZXRpbmdBc3Npc3RQcmVmZXJyZWREYXRlUmFuZ2VUeXBlICYgeyBzbG90SWQ/OiBzdHJpbmcgfCB1bmRlZmluZWQ7IH0pKSxcbiAgICAgICAgICAgICAgICAgICAgbWVldGluZ0Fzc2lzdD8udGltZXpvbmUsXG4gICAgICAgICAgICAgICAgKVxuICAgIFxuICAgICAgICAgICAgICAgIGNvbnN0IHJlcyA9IChhd2FpdCBheGlvcy5wb3N0PG51bWJlcj4oJy9hcGkvdGltZS1wcmVmZXJlbmNlcycsIHtcbiAgICAgICAgICAgICAgICAgICAgbWV0aG9kOiAndXBzZXJ0TWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVzJyxcbiAgICAgICAgICAgICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWRUaW1lczogY29udmVydGVkUHJlZmVycmVkVGltZXMgYXMgTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXSxcbiAgICAgICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICB9KSk/LmRhdGFcbiAgICAgICAgICAgICAgICByZXR1cm4gY29uc29sZS5sb2cocmVzLCAnIHN1Y2Nlc3NmdWxseSB1cGVyc3RlZCBtZWV0aW5nYXNzaXN0cHJlZmVycmVkdGltZXMnKVxuICAgICAgICAgICAgfVxuICAgICAgICAgICAgXG4gICAgICAgICAgICBjb25zb2xlLmxvZygnbm90aGluZyBoYXBwZW5lZCcpXG4gICAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGFkZCBwcmVmZXJyZWQgdGltZXMgaW4gZGInKVxuICAgICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgY2FsbE1lZXRpbmdBc3Npc3QgPSBhc3luYyAoKSA9PiB7XG4gICAgICAgIHRyeSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZygnbWVldGluZ2Fzc2lzdCBjYWxsZWQnKVxuICAgICAgICAgICAgaWYgKCFtZWV0aW5nQXNzaXN0Py5pZCkge1xuICAgICAgICAgICAgICAgIGNvbnNvbGUubG9nKCdubyBtZWV0aW5nIGFzc2lzdCBwcmVzZW50IGluc2lkZSBjYWxsTWVldGluZ0Fzc2lzdCcpXG4gICAgICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgICAgICB0aXRsZTogJ01lZXRpbmcgZG9lcyBub3QgZXhpc3QnLFxuICAgICAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1NlZW1zIGxpa2UgbWVldGluZyBkb2VzIG5vdCBleGlzdCcsXG4gICAgICAgICAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWVcbiAgICAgICAgICAgICAgICB9KVxuICAgICAgICAgICAgICAgIHJldHVyblxuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBpZiAoIW1lZXRpbmdBc3Npc3Q/LnRpbWV6b25lKSB7XG4gICAgICAgICAgICAgICAgY29uc29sZS5sb2coJ25vIG1lZXRpbmcgYXNzaXN0IHRpbWV6b25lIHByZXNlbnQgaW5zaWRlIGNhbGxNZWV0aW5nQXNzaXN0JylcbiAgICAgICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgICAgIHRpdGxlOiAnTWVldGluZyBkb2VzIG5vdCBleGlzdCcsXG4gICAgICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnU2VlbXMgbGlrZSBtZWV0aW5nIGRvZXMgbm90IGV4aXN0JyxcbiAgICAgICAgICAgICAgICAgICAgc3RhdHVzOiAnZXJyb3InLFxuICAgICAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZVxuICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGNvbnNvbGUubG9nKG1lZXRpbmdBc3Npc3QsICcgY2FsbE1lZXRpbmdBc3Npc3QnKVxuICAgICAgICAgICAgY29uc29sZS5sb2cobWVldGluZ0Fzc2lzdD8ub3JpZ2luYWxNZWV0aW5nSWQsICcgbWVldGluZ0Fzc2lzdD8ub3JpZ2luYWxNZWV0aW5nSWQnKVxuXG4gICAgICAgICAgICBpZiAobWVldGluZ0Fzc2lzdD8ub3JpZ2luYWxNZWV0aW5nSWQpIHtcbiAgICAgICAgICAgICAgICBcbiAgICAgICAgICAgICAgICBjb25zdCBvcmlnaW5hbFByZWZlcnJlZFRpbWVzID0gY29udmVydFRvUHJlZmVycmVkVGltZXNGb3JNZWV0aW5nQXNzaXN0KClcblxuICAgICAgICAgICAgICAgIGNvbnNvbGUubG9nKG9yaWdpbmFsUHJlZmVycmVkVGltZXMsICcgb3JpZ2luYWxQcmVmZXJyZWRUaW1lcycpXG5cbiAgICAgICAgICAgICAgICBhd2FpdCBheGlvcy5wb3N0KFxuICAgICAgICAgICAgICAgICAgICBwcm9jZXNzLmVudi5ORVhUX1BVQkxJQ19BVE9NSUNfSEFORFNIQUtFX0FQSSBhcyBzdHJpbmcsXG4gICAgICAgICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIG9yaWdpbmFsTWVldGluZ0Fzc2lzdDogbWVldGluZ0Fzc2lzdCxcbiAgICAgICAgICAgICAgICAgICAgICAgIG9yaWdpbmFsUHJlZmVycmVkVGltZXMsXG4gICAgICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIClcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgYXdhaXQgYXhpb3MucG9zdCgnL2FwaS90aW1lLXByZWZlcmVuY2VzJywge1xuICAgICAgICAgICAgICAgIG1ldGhvZDogJ3N0YXJ0TWVldGluZ0Fzc2lzdCcsXG4gICAgICAgICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICAgICAgICAgIGJvZHk6IHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJJZDogbWVldGluZ0Fzc2lzdD8udXNlcklkLFxuICAgICAgICAgICAgICAgICAgICAgICAgd2luZG93U3RhcnREYXRlOiBtZWV0aW5nQXNzaXN0Py53aW5kb3dTdGFydERhdGUsXG4gICAgICAgICAgICAgICAgICAgICAgICB3aW5kb3dFbmREYXRlOiBtZWV0aW5nQXNzaXN0Py53aW5kb3dFbmREYXRlLFxuICAgICAgICAgICAgICAgICAgICAgICAgdGltZXpvbmU6IG1lZXRpbmdBc3Npc3Q/LnRpbWV6b25lLFxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICB9KVxuXG4gICAgICAgICAgICBcblxuICAgICAgICAgICAgY29uc29sZS5sb2coJ3N1Y2Nlc3NmdWxseSBjYWxsZWQgbWVldGluZyBhc3Npc3QnKVxuICAgICAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBjYWxsIG1lZXRpbmcgYXNzaXN0JylcbiAgICAgICAgfVxuICAgIH1cblxuXG4gICAgY29uc3Qgb25TdWJtaXQgPSBhc3luYyAoKSA9PiB7XG4gICAgICAgIHRyeSB7XG4gICAgICAgICAgICBpZiAobWVldGluZ0Fzc2lzdD8uY2FuY2VsbGVkKSB7XG4gICAgICAgICAgICAgICAgY29uc29sZS5sb2coJ21lZXRpbmcgaXMgY2FuY2VsbGVkJylcbiAgICAgICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgICAgIHRpdGxlOiAnTWVldGluZyBjYW5jZWxsZWQnLFxuICAgICAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1NlZW1zIGxpa2UgbWVldGluZyBpcyBjYW5jZWxsZWQnLFxuICAgICAgICAgICAgICAgICAgICBzdGF0dXM6ICd3YXJuaW5nJyxcbiAgICAgICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWVcbiAgICAgICAgICAgICAgICB9KVxuICAgICAgICAgICAgICAgIHJldHVyblxuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBpZiAoZGF5anMoKS5pc0FmdGVyKGRheWpzKG1lZXRpbmdBc3Npc3Q/LndpbmRvd0VuZERhdGU/LnNsaWNlKDAsIDE5KSkudHoobWVldGluZ0Fzc2lzdD8udGltZXpvbmUsIHRydWUpLmZvcm1hdCgpKSkge1xuICAgICAgICAgICAgY29uc29sZS5sb2coJ21lZXRpbmcgaXMgZXhwaXJlZCcpXG4gICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgdGl0bGU6ICdNZWV0aW5nIGV4cGlyZWQnLFxuICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnU2VlbXMgbGlrZSBtZWV0aW5nIGlzIGV4cGlyZWQnLFxuICAgICAgICAgICAgICAgIHN0YXR1czogJ3dhcm5pbmcnLFxuICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWVcbiAgICAgICAgICAgIH0pXG4gICAgICAgICAgICByZXR1cm5cbiAgICAgICAgfVxuXG4gICAgICAgIGlmIChtZWV0aW5nQXNzaXN0Py5leHBpcmVEYXRlICYmIChkYXlqcygpLmlzQWZ0ZXIoZGF5anMobWVldGluZ0Fzc2lzdD8uZXhwaXJlRGF0ZT8uc2xpY2UoMCwgMTkpKS50eihtZWV0aW5nQXNzaXN0Py50aW1lem9uZSwgdHJ1ZSkuZm9ybWF0KCkpKSkge1xuICAgICAgICAgICAgY29uc29sZS5sb2coJ21lZXRpbmcgaXMgZXhwaXJlZCcpXG4gICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgdGl0bGU6ICdNZWV0aW5nIGV4cGlyZWQnLFxuICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnU2VlbXMgbGlrZSBtZWV0aW5nIGlzIGV4cGlyZWQnLFxuICAgICAgICAgICAgICAgIHN0YXR1czogJ3dhcm5pbmcnLFxuICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWVcbiAgICAgICAgICAgIH0pXG4gICAgICAgICAgICByZXR1cm5cbiAgICAgICAgfVxuXG4gICAgICAgICAgICBpZiAobWVldGluZ0FscmVhZHlDcmVhdGVkKSB7XG4gICAgICAgICAgICAgICAgY29uc29sZS5sb2coJ21lZXRpbmcgYWxyZWFkeSBjcmVhdGVkIG9uIHN1Ym1pdCcpXG4gICAgICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgICAgICB0aXRsZTogJ01lZXRpbmcgYWxyZWFkeSBjcmVhdGVkJyxcbiAgICAgICAgICAgICAgICAgICAgZGVzY3JpcHRpb246ICdTZWVtcyBsaWtlIG1lZXRpbmcgaXMgYWxyZWFkeSBjcmVhdGVkJyxcbiAgICAgICAgICAgICAgICAgICAgc3RhdHVzOiAnZXJyb3InLFxuICAgICAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZVxuICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGF3YWl0IHJlbW92ZVByZWZlcnJlZFRpbWVzSW5EYigpXG5cbiAgICAgICAgICAgIGF3YWl0IGFkZFByZWZlcnJlZFRpbWVzSW5EYigpXG5cbiAgICAgICAgICAgIGlmIChcbiAgICAgICAgICAgICAgICBtZWV0aW5nQXR0ZW5kZWVzPy5sZW5ndGggJiZcbiAgICAgICAgICAgICAgICBtZWV0aW5nQXNzaXN0Py5taW5UaHJlc2hvbGRDb3VudCAmJlxuICAgICAgICAgICAgICAgIChtZWV0aW5nQXR0ZW5kZWVzPy5sZW5ndGggPj0gbWVldGluZ0Fzc2lzdD8ubWluVGhyZXNob2xkQ291bnQpXG4gICAgICAgICAgICApIHtcbiAgICAgICAgICAgICAgICBjb25zb2xlLmxvZygnbWluIHRocmVzaG9sZCBtZXQnKVxuICAgICAgICAgICAgICAgIGF3YWl0IGNhbGxNZWV0aW5nQXNzaXN0KClcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgICAgICAgICAgdGl0bGU6ICdBdHRlbmRhbmNlIHN1Ym1pdHRlZCcsXG4gICAgICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnWW91ciBhdHRlbmRhbmNlICYgdGltZSBwcmVmZXJlbmNlcyBoYXZlIGJlZW4gc3VjY2Vzc2Z1bGx5IHN1Ym1pdHRlZC4gWW91IG1heSBub3cgY2xvc2UgdGhlIHdpbmRvdy4nLFxuICAgICAgICAgICAgICAgICAgICBzdGF0dXM6ICdzdWNjZXNzJyxcbiAgICAgICAgICAgICAgICAgICAgZHVyYXRpb246IDE4MDAwLFxuICAgICAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlXG4gICAgICAgICAgICAgICAgfSlcbiAgICAgICAgfSBjYXRjaCAoZSkge1xuICAgICAgICAgICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gc2F2ZScpXG4gICAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhuZXdQcmVmZXJyZWRUaW1lcywgJyBuZXdQcmVmZXJyZWRUaW1lcycpXG5cbiAgICBjb25zb2xlLmxvZyhwcmVmZXJyZWRUaW1lc1VJLCAnIHByZWZlcnJlZFRpbWVzVUknKVxuXG4gICAgcmV0dXJuIChcbiAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJmbGV4IGZsZXgtY29sIGp1c3RpZnktY2VudGVyIGl0ZW1zLWNlbnRlciBoLWZ1bGwgdy1mdWxsIFwiPlxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJsZzpmbGV4IGxnOmp1c3RpZnktY2VudGVyIGxnOml0ZW1zLWNlbnRlciBsZzpmbGV4LXJvdyBzbTpmbGV4LWNvbCBoLTMvNCB3LWZ1bGwgXCI+XG4gICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJsZzp3LTIvMyBmbGV4IGZsZXgtY29sIGp1c3RpZnktY2VudGVyIGl0ZW1zLWNlbnRlciBsZzptLTIgbS0zIGgtMS8yIGxnOmgtZnVsbCBcIj5cbiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJmbGV4IGl0ZW1zLWNlbnRlciBqdXN0aWZ5LWNlbnRlciBsZzpteS0yIG15LTMgdy1mdWxsIGgtMS82XCI+XG4gICAgICAgICAgICAgICAgICAgICAgICA8ZGl2PlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxEYXRlUGlja2VyXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNlbGVjdGVkPXtzZWxlY3RlZERhdGV9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG9uQ2hhbmdlPXsoZGF0ZSkgPT4gc2V0U2VsZWN0ZWREYXRlKGRhdGUpfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBtaW5EYXRlPXttaW5EYXRlfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBtYXhEYXRlPXttYXhEYXRlfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBwbGFjZWhvbGRlclRleHQ9XCJTZWxlY3QgYSBkYXRlIHRvIHNlZSBhdmFpbGFibGUgc2xvdHMgZm9yIHBvc3NpYmxlIHRpbWUgc2VsZWN0aW9uXCJcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY2xhc3NOYW1lPVwidGV4dC1ncmF5LTkwMCBiZy1ncmF5LTIwMCBkYXJrOnRleHQtZ3JheS0yMDAgZGFyazpiZy1ncmF5LTkwMCByb3VuZGVkLWxnIHRleHQtY2VudGVyXCJcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgICAgICAgICAgPC9kaXY+XG5cbiAgICAgICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZmxleCBqdXN0aWZ5LWNlbnRlciBpdGVtcy1jZW50ZXIgaC01LzYgdy1mdWxsIG15LTMgb3ZlcmZsb3cteS1zY3JvbGxcIj5cbiAgICAgICAgICAgICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAoYXZhaWxhYmxlU2xvdHNCeURhdGU/LltgJHtkYXlqcyhzZWxlY3RlZERhdGUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpfWBdXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICYmIGF2YWlsYWJsZVNsb3RzQnlEYXRlPy5bYCR7ZGF5anMoc2VsZWN0ZWREYXRlKS5mb3JtYXQoJ1lZWVktTU0tREQnKX1gXT8ubGVuZ3RoID4gMClcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgJiYgKG1lZXRpbmdBc3Npc3Q/LmF0dGVuZGVlQ2FuTW9kaWZ5IHx8IG1lZXRpbmdBc3Npc3Q/LmVuYWJsZUF0dGVuZGVlUHJlZmVyZW5jZXMpXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPyAoXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwic3BhY2UteS0yIGxnOnctMS8yIGgtZnVsbFwiPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB7YXZhaWxhYmxlU2xvdHNCeURhdGU/LltgJHtkYXlqcyhzZWxlY3RlZERhdGUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpfWBdPy5tYXAoKGF2LCBpKSA9PiAoXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8ZGl2IGtleT17YXY/LmlkfSBjbGFzc05hbWU9XCJ3LWZ1bGwgbS1hdXRvXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPGlucHV0XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNsYXNzTmFtZT1cInBlZXIgaGlkZGVuXCJcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgdHlwZT1cInJhZGlvXCJcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgbmFtZT17YXY/LmlkfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB2YWx1ZT17YXY/LmlkfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBpZD17YXY/LmlkfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBjaGVja2VkPXthdj8uc2VsZWN0ZWR9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG9uQ2hhbmdlPXsoKSA9PiBvblNlbGVjdGVkU2xvdChpKX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAvPlxuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPGxhYmVsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNsYXNzTmFtZT1cImZsZXggY3Vyc29yLXBvaW50ZXIgaXRlbXMtY2VudGVyIGp1c3RpZnktY2VudGVyIHJvdW5kZWQtbGcgYm9yZGVyICBib3JkZXItcHVycGxlLTkwMCBwLTQgdGV4dC1zbSBmb250LW1lZGl1bSBzaGFkb3ctc20gdHJhbnNpdGlvbi1jb2xvcnMgaG92ZXI6YmctcHVycGxlLTkwMCBob3Zlcjp0ZXh0LWdyYXktMjAwICBwZWVyLWNoZWNrZWQ6Ym9yZGVyLXBpbmstNTAwIHBlZXItY2hlY2tlZDpyaW5nLTEgcGVlci1jaGVja2VkOnJpbmctcGluay01MDAgdGV4dC1jZW50ZXIgZGFyazp0ZXh0LWdyYXktMjAwIHRleHQtZ3JheS05MDBcIlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBodG1sRm9yPXthdj8uaWR9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8c3BhbiBjbGFzc05hbWU9XCJcIj4gXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB7YCR7ZGF5anMoYXY/LnN0YXJ0RGF0ZSkuZm9ybWF0KCdoOm1tIEEnKX0gLSAke2RheWpzKGF2Py5lbmREYXRlKS5mb3JtYXQoJ2g6bW0gQScpfWB9IFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L3NwYW4+XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L2xhYmVsPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICkpfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICApXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgOiAoXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZmxleCBqdXN0aWZ5LWNlbnRlciBpdGVtcy1jZW50ZXIgaC1mdWxsIHctZnVsbFwiPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJ0ZXh0LWNlbnRlciBzbTp0ZXh0LWxlZnQgdy0xLzJcIj5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8aDIgY2xhc3NOYW1lPVwiIGZvbnQtYm9sZCB0ZXh0LWdyYXktOTAwIGRhcms6dGV4dC1ncmF5LTIwMCBzbTp0ZXh0LXhsIG0tM1wiPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBMb29rcyBsaWtlIHRoZXJlIGFyZSBubyBzbG90cyBhdmFpbGFibGUgZm9yIHRoaXMgZGF0ZS4gWW91IGNhbiBlaXRoZXIgY2hvb3NlIGFub3RoZXIgZGF0ZSBvciBjbGljayBTdWJtaXQuIFlvdSB3aWxsIHN0aWxsIGJlIGFibGUgdG8gYm9vayBhbiBhcHBvaW50bWVudC4gSnVzdCBtYWtlIHN1cmUgdG8gY2xpY2sgU3VibWl0LlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvaDI+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgKVxuICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cImxnOnctMS8zIGZsZXggZmxleC1jb2wganVzdGlmeS1jZW50ZXIgaXRlbXMtY2VudGVyIG0tMyBoLTEvMiBsZzpoLWZ1bGxcIj5cbiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJsZzpoLTEvNiBsZzp3LWZ1bGxcIiAvPlxuICAgICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cImZsZXggZmxleC1jb2wgaXRlbXMtY2VudGVyIGp1c3RpZnktY2VudGVyIHNwYWNlLXktMiBsZzpoLTUvNiB3LWZ1bGwgbXktMyBvdmVyZmxvdy15LXNjcm9sbFwiPlxuICAgICAgICAgICAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZFRpbWVzVUk/Lm1hcCgocHQsIGkpID0+IChcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPGRpdiBrZXk9e3B0Py5pZH0+XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxkaXZcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBjbGFzc05hbWU9XCJmbGV4IGZsZXgtY29sIGl0ZW1zLXN0YXJ0IGp1c3RpZnktY2VudGVyIHJvdW5kZWQtbGcgYm9yZGVyIGhvdmVyOmJvcmRlci1waW5rLTkwMCBib3JkZXItcHVycGxlLTkwMCBwLTQgdGV4dC1zbSBmb250LW1lZGl1bSBzaGFkb3ctc20gdHJhbnNpdGlvbi1jb2xvcnMgbGc6bWwtMSBzbTptbC0yIGVhc2UtaW4tb3V0IGRlbGF5LTE1MCBkdXJhdGlvbi0zMDBcIlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxkaXY+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHsoKHB0Py5kYXlPZldlZWsgIT09IHVuZGVmaW5lZCkgJiYgKHB0Py5kYXlPZldlZWsgPiAwKSkgJiYgKGRheU9mV2Vla0ludFRvU3RyaW5nPy5bcHQ/LmRheU9mV2Vla10/LlswXSArIGRheU9mV2Vla0ludFRvU3RyaW5nPy5bcHQ/LmRheU9mV2Vla10/LnNsaWNlKDEpLnRvTG93ZXJDYXNlKCkudHJpbSgpKX0gIFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZmxleCBqdXN0aWZ5LWNlbnRlciBpdGVtcy1jZW50ZXIgIGhvdmVyOnRleHQtcGluay05MDAgZGFyazp0ZXh0LWdyYXktMjAwIHRleHQtZ3JheS05MDBcIj5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJcIj5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHtgJHtkYXlqcyhwdD8uc3RhcnRUaW1lKS5mb3JtYXQoJ2g6bW0gQScpfSAtICR7ZGF5anMocHQ/LmVuZFRpbWUpLmZvcm1hdCgnaDptbSBBJyl9YH0gXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvZGl2PlxuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiZmxleCBmbGV4LWVuZCBpdGVtcy1jZW50ZXJcIj4gICBcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHsobWVldGluZ0Fzc2lzdD8uYXR0ZW5kZWVDYW5Nb2RpZnkgfHwgKFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG1lZXRpbmdBc3Npc3Q/LmVuYWJsZUF0dGVuZGVlUHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAmJiAoKG5ld1ByZWZlcnJlZFRpbWVzPy5zb21lKHB0MiA9PiAocHQyPy5pZCA9PT0gcHQ/LmlkKSkpIHx8IChjdXN0b21QcmVmZXJyZWRUaW1lcz8uc29tZShwdDIgPT4gKHB0Mj8uaWQgPT09IHB0Py5pZCkpKSlcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICkpXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA/IChcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8ZGl2IGNsYXNzTmFtZT1cIlwiPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8SW9DbG9zZU91dGxpbmUgc2l6ZT17NDV9IG9uQ2xpY2s9eygpID0+IHJlbW92ZVByZWZlcnJlZFRpbWVCeUluZGV4KGkpfSAgY2xhc3NOYW1lPVwidGV4dC1yZWQtNTAwIGN1cnNvci1wb2ludGVyIHAtM1wiIC8+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICApIDogbnVsbH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC9kaXY+XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICApKVxuICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgPGRpdiByZWY9e3ByZWZlcnJlZFRpbWVzRW5kUmVmfSAvPlxuICAgICAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJsZzpoLTEvNiB3LWZ1bGwgZmxleCBmbGV4LWNvbCBqdXN0aWZ5LWNlbnRlciBpdGVtcy1jZW50ZXIgbXktMyBcIj5cbiAgICAgICAgICAgICAgICAgICAgICAgIDxidXR0b24gY2xhc3NOYW1lPSdidG4gYnRuLXByaW1hcnkgbGc6cC0zIHAtNCcgb25DbGljaz17b25TdWJtaXR9PlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHsnU3VibWl0J31cbiAgICAgICAgICAgICAgICAgICAgICAgIDwvYnV0dG9uPlxuICAgICAgICAgICAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgIChtZWV0aW5nQXNzaXN0Py5ndWFyYW50ZWVBdmFpbGFiaWxpdHkgfHwgaXNIb3N0KVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgID8gKFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9JyBsZzpwdC0zIHB0LTQnPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxUb29sdGlwIGxhYmVsPSdJZiBub25lIG9mIHRoZSB0aW1lcyB3b3JrIGZvciB5b3UsIHRoZW4geW91IGNhbiBhZGQgYSBjdXN0b20gdGltZS4gQXRvbWljIHdpbGwgdGFrZSB0aGUgY3VzdG9tIHRpbWUgaW50byBhY2NvdW50IHdoZW4gc2NoZWR1bGluZyBhIG1lZXRpbmcnPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8YnV0dG9uIGNsYXNzTmFtZT0nYnRuIGJ0bi1wcmltYXJ5JyBvbkNsaWNrPXtvbk9wZW59PlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgeydDdXN0b20gVGltZSBQcmVmZXJlbmNlcyd9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvYnV0dG9uPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvVG9vbHRpcD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICkgOiBudWxsXG4gICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgICAgIDwvZGl2PiAgIFxuICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICA8cCBjbGFzc05hbWU9XCJsZzptLTMgbS00IHRleHQtbGcgdGV4dC1jZW50ZXIgdGV4dC1ncmF5LTUwMFwiPlxuICAgICAgICAgICAgICAgIFlvdSBkbyBub3QgaGF2ZSB0byBzZWxlY3QgYSB0aW1lIHNsb3QuIEdvIGFoZWFkIGFuZCBwcmVzcyBzdWJtaXQgaWYgeW91IGhhdmUgbm8gdGltZSBwcmVmZXJlbmNlLlxuICAgICAgICAgICAgPC9wPlxuICAgICAgICAgICAgPGRpdj5cbiAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICAgIGhvc3RQcmVmZXJlbmNlc1xuICAgICAgICAgICAgICAgICAgICAmJiBtZWV0aW5nQXNzaXN0XG4gICAgICAgICAgICAgICAgICAgICYmICAgXG4gICAgICAgICAgICAgICAgICAgIChcbiAgICAgICAgICAgICAgICAgICAgICAgIDxNb2RhbCBpc09wZW49e2lzT3Blbn0gb25DbG9zZT17b25DbG9zZX0+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPE1vZGFsT3ZlcmxheSAvPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxNb2RhbENvbnRlbnQ+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxNb2RhbENsb3NlQnV0dG9uIC8+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxNb2RhbEJvZHk+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8TW9kYWxUaW1lUHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBtaW5EYXRlPXttaW5EYXRlfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG1heERhdGU9e21heERhdGV9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgc2xvdER1cmF0aW9uPXtzbG90RHVyYXRpb259XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgaG9zdFByZWZlcmVuY2VzPXtob3N0UHJlZmVyZW5jZXN9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgbWVldGluZ0Fzc2lzdD17bWVldGluZ0Fzc2lzdH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBvblN1Ym1pdD17b25TdWJtaXRDdXN0b21BdmFpbGFibGVUaW1lfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG9uQ2FuY2VsPXtvbkNhbmNlbEN1c3RvbUF2YWlsYWJsZVRpbWV9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L01vZGFsQm9keT5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L01vZGFsQ29udGVudD5cbiAgICAgICAgICAgICAgICAgICAgICAgIDwvTW9kYWw+XG4gICAgICAgICAgICAgICAgICAgIClcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgPC9kaXY+XG4gICAgKVxufVxuXG5leHBvcnQgZGVmYXVsdCBNZWV0aW5nQXNzaXN0VGltZVByZWZlcmVuY2VzXG4iXX0=