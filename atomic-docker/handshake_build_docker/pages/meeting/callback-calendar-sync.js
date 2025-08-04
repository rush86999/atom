"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const router_1 = require("next/router");
const react_1 = require("react");
const react_2 = require("@chakra-ui/react");
const axios_1 = __importDefault(require("axios"));
const dayjs_1 = __importDefault(require("dayjs"));
const isoWeek_1 = __importDefault(require("dayjs/plugin/isoWeek"));
const duration_1 = __importDefault(require("dayjs/plugin/duration"));
const isBetween_1 = __importDefault(require("dayjs/plugin/isBetween"));
const timezone_1 = __importDefault(require("dayjs/plugin/timezone"));
const utc_1 = __importDefault(require("dayjs/plugin/utc"));
const swr_1 = __importDefault(require("swr"));
const qs_1 = __importDefault(require("qs"));
dayjs_1.default.extend(isoWeek_1.default);
dayjs_1.default.extend(duration_1.default);
dayjs_1.default.extend(isBetween_1.default);
dayjs_1.default.extend(timezone_1.default);
dayjs_1.default.extend(utc_1.default);
const meetingAssistPoster = async (url, data) => axios_1.default.post(url, data).then(res => res.data);
const meetingAssistAttendeePoster = async (url, data) => axios_1.default.post(url, data).then(res => res.data);
const CallbackCalendarSync = () => {
    const [isValid, setIsValid] = (0, react_1.useState)(true);
    const router = (0, router_1.useRouter)();
    const toast = (0, react_2.useToast)();
    const { access_token, attendeeId, meetingId } = router.query;
    console.log(router.query, ' router.query');
    // console.log(access_token, ' access_token')
    console.log(attendeeId, ' attendeeId');
    console.log(meetingId, ' meetingId');
    // get meeting assist
    const { data: meetingAssist, error: meetingAssistError } = (0, swr_1.default)([
        '/api/callback-calendar-sync', {
            method: 'getMeetingAssist',
            variables: { id: meetingId },
        }
    ], meetingAssistPoster);
    // get meeting assist attendee
    const { data: meetingAssistAttendee, error: meetingAssistAttendeeError } = (0, swr_1.default)([
        '/api/callback-calendar-sync', {
            method: 'getMeetingAssistAttendee',
            variables: { id: attendeeId },
        }
    ], meetingAssistAttendeePoster);
    // validate callback
    (0, react_1.useEffect)(() => {
        const validateCallback = async () => {
            try {
                // const meetingAssist = await getMeetingAssist(meetingId as string)
                if (!meetingAssist?.id) {
                    return false;
                }
                if (meetingAssistError) {
                    toast({
                        title: 'Oops...',
                        description: 'Something went wrong, the meeting id is invalid. Maybe try again',
                        status: 'error',
                        duration: 9000,
                        isClosable: true
                    });
                    setIsValid(false);
                    return false;
                }
                // const meetingAssistAttendee = await getMeetingAssistAttendee(attendeeId as string)
                if (!meetingAssistAttendee?.id) {
                    return false;
                }
                if (meetingAssistAttendeeError) {
                    toast({
                        title: 'Oops...',
                        description: 'Something went wrong, the attendee id is invalid. Maybe try again',
                        status: 'error',
                        duration: 9000,
                        isClosable: true
                    });
                    setIsValid(false);
                    return false;
                }
                return true;
            }
            catch (e) {
                console.log(e, ' uanble to validate callback');
            }
        };
        (async () => {
            try {
                const validatedCallback = await validateCallback();
                if (validatedCallback) {
                    // validate timezone
                    if (!meetingAssist?.timezone) {
                        console.log(' unable to get meetingAssist timezone inside callback-calendar-sync');
                        toast({
                            title: 'Oops...',
                            description: 'Something went wrong, let us know so we can work on it',
                            status: 'error',
                            duration: 9000,
                            isClosable: true
                        });
                        setIsValid(false);
                        return;
                    }
                    if (!access_token) {
                        console.log(' unable to get access_token');
                        toast({
                            title: 'Oops...',
                            description: 'Something went wrong, let us know so we can work on it',
                            status: 'error',
                            duration: 9000,
                            isClosable: true
                        });
                        setIsValid(false);
                        return;
                    }
                    if (!attendeeId) {
                        console.log(attendeeId, ' missing attendeeId');
                        toast({
                            title: 'Oops...',
                            description: 'Something went wrong, let us know so we can work on it',
                            status: 'error',
                            duration: 9000,
                            isClosable: true
                        });
                        setIsValid(false);
                        return;
                    }
                    await axios_1.default.post('/api/callback-calendar-sync', {
                        method: 'googleCalendarSync',
                        variables: {
                            token: access_token,
                            windowStartDate: meetingAssist?.windowStartDate,
                            windowEndDate: meetingAssist?.windowEndDate,
                            attendeeId: attendeeId,
                            hostTimezone: meetingAssist?.timezone,
                        }
                    });
                    router.push(`/?${qs_1.default.stringify({
                        calendarSyncCompleted: 'true',
                        meetingId: meetingAssist?.id,
                        attendeeId,
                    })}`);
                }
            }
            catch (e) {
                toast({
                    title: 'Oops...',
                    description: 'Something went wrong, let us know so we can work on it',
                    status: 'error',
                    duration: 9000,
                    isClosable: true
                });
                console.log(e, ' unable to validate attendee and meeting');
            }
        })();
    }, [access_token, attendeeId, meetingAssist?.id, meetingAssist?.timezone, meetingAssist?.windowEndDate, meetingAssist?.windowStartDate, meetingAssistAttendee?.id, meetingAssistAttendeeError, meetingAssistError, router, router.query, toast]);
    return ((0, jsx_runtime_1.jsxs)("div", { className: "flex flex-col justify-center items-center h-screen w-full", children: [(0, jsx_runtime_1.jsxs)("div", { className: "sm:text-left lg:my-12 sm:my-8 lg:h-1/6 lg:w-1/2", children: [(0, jsx_runtime_1.jsx)("h1", { className: "text-xl font-bold text-gray-900 dark:text-gray-200 sm:text-2xl", children: "Validating your returned values" }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1.5 text-sm text-gray-500", children: "Please wait as we validate a successful calendar sync " }), !isValid
                        ? ((0, jsx_runtime_1.jsx)("p", { className: "mt-1.5 text-sm text-red-500", children: "Something went wrong with the sync " })) : null] }), (0, jsx_runtime_1.jsx)("div", { className: "flex justify-center items-center lg:h-5/6 w-full", children: (0, jsx_runtime_1.jsx)(react_2.Spinner, { color: 'pink.500' }) })] }));
};
exports.default = CallbackCalendarSync;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsbGJhY2stY2FsZW5kYXItc3luYy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImNhbGxiYWNrLWNhbGVuZGFyLXN5bmMudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7OztBQUFBLHdDQUF1QztBQUN2QyxpQ0FBMkM7QUFFM0MsNENBQW9EO0FBQ3BELGtEQUF5QjtBQUN6QixrREFBeUI7QUFDekIsbUVBQTBDO0FBQzFDLHFFQUE0QztBQUM1Qyx1RUFBOEM7QUFDOUMscUVBQTRDO0FBQzVDLDJEQUFrQztBQUNsQyw4Q0FBd0I7QUFDeEIsNENBQW1CO0FBR25CLGVBQUssQ0FBQyxNQUFNLENBQUMsaUJBQU8sQ0FBQyxDQUFBO0FBQ3JCLGVBQUssQ0FBQyxNQUFNLENBQUMsa0JBQVEsQ0FBQyxDQUFBO0FBQ3RCLGVBQUssQ0FBQyxNQUFNLENBQUMsbUJBQVMsQ0FBQyxDQUFBO0FBQ3ZCLGVBQUssQ0FBQyxNQUFNLENBQUMsa0JBQVEsQ0FBQyxDQUFBO0FBQ3RCLGVBQUssQ0FBQyxNQUFNLENBQUMsYUFBRyxDQUFDLENBQUE7QUFFakIsTUFBTSxtQkFBbUIsR0FBRyxLQUFLLEVBQUUsR0FBVyxFQUFFLElBQVMsRUFBOEIsRUFBRSxDQUFDLGVBQUssQ0FBQyxJQUFJLENBQUMsR0FBRyxFQUFFLElBQUksQ0FBQyxDQUFDLElBQUksQ0FBQyxHQUFHLENBQUMsRUFBRSxDQUFDLEdBQUcsQ0FBQyxJQUFJLENBQUMsQ0FBQTtBQUVySSxNQUFNLDJCQUEyQixHQUFHLEtBQUssRUFBRSxHQUFXLEVBQUUsSUFBUyxFQUFzQyxFQUFFLENBQUMsZUFBSyxDQUFDLElBQUksQ0FBQyxHQUFHLEVBQUUsSUFBSSxDQUFDLENBQUMsSUFBSSxDQUFDLEdBQUcsQ0FBQyxFQUFFLENBQUMsR0FBRyxDQUFDLElBQUksQ0FBQyxDQUFBO0FBRXJKLE1BQU0sb0JBQW9CLEdBQWEsR0FBRyxFQUFFO0lBQ3hDLE1BQU0sQ0FBQyxPQUFPLEVBQUUsVUFBVSxDQUFDLEdBQUcs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LGdFQUFnRSxZQUN6RSxpQ0FBaUMsR0FDakMsRUFFTCw4QkFBRyxTQUFTLEVBQUMsOEJBQThCLFlBQ3RDLHdEQUF3RCxHQUN6RCxFQUVKLENBQUMsT0FBTzt3QkFDSixDQUFDLENBQUMsQ0FDRSw4QkFBRyxTQUFTLEVBQUMsNkJBQTZCLFlBQ3JDLHFDQUFxQyxHQUN0QyxDQUNQLENBQUMsQ0FBQyxDQUFDLElBQUksSUFFVixFQUNOLGdDQUFLLFNBQVMsRUFBQyxrREFBa0QsWUFDN0QsdUJBQUMsZUFBTyxJQUFDLEtBQUssRUFBQyxVQUFVLEdBQUcsR0FDMUIsSUFDSixDQUNULENBQUE7QUFDTCxDQUFDLENBQUE7QUFFRCxrQkFBZSxvQkFBb0IsQ0FBQSIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IHVzZVJvdXRlciB9IGZyb20gJ25leHQvcm91dGVyJ1xuaW1wb3J0IHsgdXNlRWZmZWN0LCB1c2VTdGF0ZSB9IGZyb20gXCJyZWFjdFwiXG5pbXBvcnQgdHlwZSB7IE5leHRQYWdlIH0gZnJvbSAnbmV4dCdcbmltcG9ydCB7IHVzZVRvYXN0LCBTcGlubmVyIH0gZnJvbSAnQGNoYWtyYS11aS9yZWFjdCdcbmltcG9ydCBheGlvcyBmcm9tICdheGlvcydcbmltcG9ydCBkYXlqcyBmcm9tICdkYXlqcydcbmltcG9ydCBpc29XZWVrIGZyb20gJ2RheWpzL3BsdWdpbi9pc29XZWVrJ1xuaW1wb3J0IGR1cmF0aW9uIGZyb20gJ2RheWpzL3BsdWdpbi9kdXJhdGlvbidcbmltcG9ydCBpc0JldHdlZW4gZnJvbSAnZGF5anMvcGx1Z2luL2lzQmV0d2VlbidcbmltcG9ydCB0aW1lem9uZSBmcm9tICdkYXlqcy9wbHVnaW4vdGltZXpvbmUnXG5pbXBvcnQgdXRjIGZyb20gJ2RheWpzL3BsdWdpbi91dGMnXG5pbXBvcnQgdXNlU1dSIGZyb20gJ3N3cidcbmltcG9ydCBxcyBmcm9tICdxcydcbmltcG9ydCB7IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGUsIE1lZXRpbmdBc3Npc3RUeXBlIH0gZnJvbSAnQGxpYi90eXBlcydcblxuZGF5anMuZXh0ZW5kKGlzb1dlZWspXG5kYXlqcy5leHRlbmQoZHVyYXRpb24pXG5kYXlqcy5leHRlbmQoaXNCZXR3ZWVuKVxuZGF5anMuZXh0ZW5kKHRpbWV6b25lKVxuZGF5anMuZXh0ZW5kKHV0YylcblxuY29uc3QgbWVldGluZ0Fzc2lzdFBvc3RlciA9IGFzeW5jICh1cmw6IHN0cmluZywgZGF0YTogYW55KTogUHJvbWlzZTxNZWV0aW5nQXNzaXN0VHlwZT4gPT4gYXhpb3MucG9zdCh1cmwsIGRhdGEpLnRoZW4ocmVzID0+IHJlcy5kYXRhKVxuXG5jb25zdCBtZWV0aW5nQXNzaXN0QXR0ZW5kZWVQb3N0ZXIgPSBhc3luYyAodXJsOiBzdHJpbmcsIGRhdGE6IGFueSk6IFByb21pc2U8TWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZT4gPT4gYXhpb3MucG9zdCh1cmwsIGRhdGEpLnRoZW4ocmVzID0+IHJlcy5kYXRhKVxuXG5jb25zdCBDYWxsYmFja0NhbGVuZGFyU3luYzogTmV4dFBhZ2UgPSAoKSA9PiB7XG4gICAgY29uc3QgW2lzVmFsaWQsIHNldElzVmFsaWRdID0gdXNlU3RhdGU8Ym9vbGVhbj4odHJ1ZSlcbiAgICBjb25zdCByb3V0ZXIgPSB1c2VSb3V0ZXIoKVxuICAgIGNvbnN0IHRvYXN0ID0gdXNlVG9hc3QoKVxuICAgIFxuICAgIGNvbnN0IHsgYWNjZXNzX3Rva2VuLCBhdHRlbmRlZUlkLCBtZWV0aW5nSWQgfSA9IHJvdXRlci5xdWVyeVxuICAgIGNvbnNvbGUubG9nKHJvdXRlci5xdWVyeSwgJyByb3V0ZXIucXVlcnknKVxuICAgIC8vIGNvbnNvbGUubG9nKGFjY2Vzc190b2tlbiwgJyBhY2Nlc3NfdG9rZW4nKVxuICAgIGNvbnNvbGUubG9nKGF0dGVuZGVlSWQsICcgYXR0ZW5kZWVJZCcpXG4gICAgY29uc29sZS5sb2cobWVldGluZ0lkLCAnIG1lZXRpbmdJZCcpXG5cbiAgICAvLyBnZXQgbWVldGluZyBhc3Npc3RcbiAgICBjb25zdCB7IGRhdGE6IG1lZXRpbmdBc3Npc3QsIGVycm9yOiBtZWV0aW5nQXNzaXN0RXJyb3IgfSA9IHVzZVNXUjxNZWV0aW5nQXNzaXN0VHlwZT4oW1xuICAgICAgICAnL2FwaS9jYWxsYmFjay1jYWxlbmRhci1zeW5jJywge1xuICAgICAgICAgICAgbWV0aG9kOiAnZ2V0TWVldGluZ0Fzc2lzdCcsXG4gICAgICAgICAgICB2YXJpYWJsZXM6IHsgaWQ6IG1lZXRpbmdJZCB9LFxuICAgICAgICB9XSwgbWVldGluZ0Fzc2lzdFBvc3RlcilcbiAgICBcbiAgICBcbiAgICAvLyBnZXQgbWVldGluZyBhc3Npc3QgYXR0ZW5kZWVcblxuICAgIGNvbnN0IHsgZGF0YTogbWVldGluZ0Fzc2lzdEF0dGVuZGVlLCBlcnJvcjogbWVldGluZ0Fzc2lzdEF0dGVuZGVlRXJyb3IgfSA9IHVzZVNXUjxNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlPihbXG4gICAgICAgICcvYXBpL2NhbGxiYWNrLWNhbGVuZGFyLXN5bmMnLCB7XG4gICAgICAgICAgICBtZXRob2Q6ICdnZXRNZWV0aW5nQXNzaXN0QXR0ZW5kZWUnLFxuICAgICAgICAgICAgdmFyaWFibGVzOiB7IGlkOiBhdHRlbmRlZUlkIH0sXG4gICAgICAgIH1dLCBtZWV0aW5nQXNzaXN0QXR0ZW5kZWVQb3N0ZXIpXG4gICAgXG4gICAgLy8gdmFsaWRhdGUgY2FsbGJhY2tcbiAgICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgICAgICBjb25zdCB2YWxpZGF0ZUNhbGxiYWNrID0gYXN5bmMgKCkgPT4ge1xuICAgICAgICAgICAgdHJ5IHtcblxuICAgICAgICAgICAgICAgIC8vIGNvbnN0IG1lZXRpbmdBc3Npc3QgPSBhd2FpdCBnZXRNZWV0aW5nQXNzaXN0KG1lZXRpbmdJZCBhcyBzdHJpbmcpXG4gICAgICAgICAgICAgICAgaWYgKCFtZWV0aW5nQXNzaXN0Py5pZCkge1xuICAgICAgICAgICAgICAgICAgICByZXR1cm4gZmFsc2VcbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICBpZiAobWVldGluZ0Fzc2lzdEVycm9yKSB7XG4gICAgICAgICAgICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgICAgICAgICB0aXRsZTogJ09vcHMuLi4nLFxuICAgICAgICAgICAgICAgICAgICAgICAgZGVzY3JpcHRpb246ICdTb21ldGhpbmcgd2VudCB3cm9uZywgdGhlIG1lZXRpbmcgaWQgaXMgaW52YWxpZC4gTWF5YmUgdHJ5IGFnYWluJyxcbiAgICAgICAgICAgICAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZVxuICAgICAgICAgICAgICAgICAgICAgfSlcbiAgICAgICAgICAgICAgICAgICAgc2V0SXNWYWxpZChmYWxzZSlcbiAgICAgICAgICAgICAgICAgICAgcmV0dXJuIGZhbHNlXG4gICAgICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICAgICAgLy8gY29uc3QgbWVldGluZ0Fzc2lzdEF0dGVuZGVlID0gYXdhaXQgZ2V0TWVldGluZ0Fzc2lzdEF0dGVuZGVlKGF0dGVuZGVlSWQgYXMgc3RyaW5nKVxuXG4gICAgICAgICAgICAgICAgaWYgKCFtZWV0aW5nQXNzaXN0QXR0ZW5kZWU/LmlkKSB7XG4gICAgICAgICAgICAgICAgICAgIHJldHVybiBmYWxzZVxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIGlmIChtZWV0aW5nQXNzaXN0QXR0ZW5kZWVFcnJvcikge1xuICAgICAgICAgICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgICAgICAgICB0aXRsZTogJ09vcHMuLi4nLFxuICAgICAgICAgICAgICAgICAgICAgICAgZGVzY3JpcHRpb246ICdTb21ldGhpbmcgd2VudCB3cm9uZywgdGhlIGF0dGVuZGVlIGlkIGlzIGludmFsaWQuIE1heWJlIHRyeSBhZ2FpbicsXG4gICAgICAgICAgICAgICAgICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgICAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWVcbiAgICAgICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAgICAgICAgIHNldElzVmFsaWQoZmFsc2UpXG4gICAgICAgICAgICAgICAgICAgIHJldHVybiBmYWxzZSBcbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICByZXR1cm4gdHJ1ZVxuICAgICAgICAgICAgICAgIFxuICAgICAgICAgICAgfSBjYXRjaCAoZSkge1xuICAgICAgICAgICAgICAgIGNvbnNvbGUubG9nKGUsICcgdWFuYmxlIHRvIHZhbGlkYXRlIGNhbGxiYWNrJylcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgICAoYXN5bmMgKCkgPT4ge1xuICAgICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgICAgICBjb25zdCB2YWxpZGF0ZWRDYWxsYmFjayA9IGF3YWl0IHZhbGlkYXRlQ2FsbGJhY2soKVxuXG4gICAgICAgICAgICAgICAgaWYgKHZhbGlkYXRlZENhbGxiYWNrKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgLy8gdmFsaWRhdGUgdGltZXpvbmVcbiAgICAgICAgICAgICAgICAgICAgaWYgKCFtZWV0aW5nQXNzaXN0Py50aW1lem9uZSkge1xuICAgICAgICAgICAgICAgICAgICAgICAgY29uc29sZS5sb2coJyB1bmFibGUgdG8gZ2V0IG1lZXRpbmdBc3Npc3QgdGltZXpvbmUgaW5zaWRlIGNhbGxiYWNrLWNhbGVuZGFyLXN5bmMnKVxuICAgICAgICAgICAgICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHRpdGxlOiAnT29wcy4uLicsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZGVzY3JpcHRpb246ICdTb21ldGhpbmcgd2VudCB3cm9uZywgbGV0IHVzIGtub3cgc28gd2UgY2FuIHdvcmsgb24gaXQnLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlXG4gICAgICAgICAgICAgICAgICAgICAgICB9KVxuICAgICAgICAgICAgICAgICAgICAgICAgc2V0SXNWYWxpZChmYWxzZSlcbiAgICAgICAgICAgICAgICAgICAgICAgIHJldHVyblxuICAgICAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICAgICAgaWYgKCFhY2Nlc3NfdG9rZW4pIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvbnNvbGUubG9nKCcgdW5hYmxlIHRvIGdldCBhY2Nlc3NfdG9rZW4nKVxuICAgICAgICAgICAgICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHRpdGxlOiAnT29wcy4uLicsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZGVzY3JpcHRpb246ICdTb21ldGhpbmcgd2VudCB3cm9uZywgbGV0IHVzIGtub3cgc28gd2UgY2FuIHdvcmsgb24gaXQnLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlXG4gICAgICAgICAgICAgICAgICAgICAgICB9KVxuICAgICAgICAgICAgICAgICAgICAgICAgc2V0SXNWYWxpZChmYWxzZSlcbiAgICAgICAgICAgICAgICAgICAgICAgIHJldHVyblxuICAgICAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICAgICAgaWYgKCFhdHRlbmRlZUlkKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICBjb25zb2xlLmxvZyhhdHRlbmRlZUlkLCAnIG1pc3NpbmcgYXR0ZW5kZWVJZCcpXG4gICAgICAgICAgICAgICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHRpdGxlOiAnT29wcy4uLicsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZGVzY3JpcHRpb246ICdTb21ldGhpbmcgd2VudCB3cm9uZywgbGV0IHVzIGtub3cgc28gd2UgY2FuIHdvcmsgb24gaXQnLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlXG4gICAgICAgICAgICAgICAgICAgICAgICAgfSlcbiAgICAgICAgICAgICAgICAgICAgICAgIHNldElzVmFsaWQoZmFsc2UpXG4gICAgICAgICAgICAgICAgICAgICAgICByZXR1cm5cbiAgICAgICAgICAgICAgICAgICAgfVxuXG5cbiAgICAgICAgICAgICAgICAgICAgYXdhaXQgYXhpb3MucG9zdCgnL2FwaS9jYWxsYmFjay1jYWxlbmRhci1zeW5jJywge1xuICAgICAgICAgICAgICAgICAgICAgICAgbWV0aG9kOiAnZ29vZ2xlQ2FsZW5kYXJTeW5jJywgXG4gICAgICAgICAgICAgICAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB0b2tlbjogYWNjZXNzX3Rva2VuLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHdpbmRvd1N0YXJ0RGF0ZTogbWVldGluZ0Fzc2lzdD8ud2luZG93U3RhcnREYXRlLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHdpbmRvd0VuZERhdGU6IG1lZXRpbmdBc3Npc3Q/LndpbmRvd0VuZERhdGUsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVJZDogYXR0ZW5kZWVJZCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBob3N0VGltZXpvbmU6IG1lZXRpbmdBc3Npc3Q/LnRpbWV6b25lLFxuICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICB9KVxuXG4gICAgICAgICAgICAgICAgICAgIHJvdXRlci5wdXNoKGAvPyR7cXMuc3RyaW5naWZ5KHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBjYWxlbmRhclN5bmNDb21wbGV0ZWQ6ICd0cnVlJyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBtZWV0aW5nSWQ6IG1lZXRpbmdBc3Npc3Q/LmlkLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlSWQsXG4gICAgICAgICAgICAgICAgICAgICAgICB9KX1gLCAgXG4gICAgICAgICAgICAgICAgICAgIClcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgICAgICB0aXRsZTogJ09vcHMuLi4nLFxuICAgICAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ1NvbWV0aGluZyB3ZW50IHdyb25nLCBsZXQgdXMga25vdyBzbyB3ZSBjYW4gd29yayBvbiBpdCcsXG4gICAgICAgICAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWVcbiAgICAgICAgICAgICAgICB9KVxuICAgICAgICAgICAgICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHZhbGlkYXRlIGF0dGVuZGVlIGFuZCBtZWV0aW5nJylcbiAgICAgICAgICAgIH1cbiAgICAgICAgfSkoKVxuICAgIH0sIFthY2Nlc3NfdG9rZW4sIGF0dGVuZGVlSWQsIG1lZXRpbmdBc3Npc3Q/LmlkLCBtZWV0aW5nQXNzaXN0Py50aW1lem9uZSwgbWVldGluZ0Fzc2lzdD8ud2luZG93RW5kRGF0ZSwgbWVldGluZ0Fzc2lzdD8ud2luZG93U3RhcnREYXRlLCBtZWV0aW5nQXNzaXN0QXR0ZW5kZWU/LmlkLCBtZWV0aW5nQXNzaXN0QXR0ZW5kZWVFcnJvciwgbWVldGluZ0Fzc2lzdEVycm9yLCByb3V0ZXIsIHJvdXRlci5xdWVyeSwgdG9hc3RdKVxuXG4gICAgcmV0dXJuIChcbiAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJmbGV4IGZsZXgtY29sIGp1c3RpZnktY2VudGVyIGl0ZW1zLWNlbnRlciBoLXNjcmVlbiB3LWZ1bGxcIj5cbiAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwic206dGV4dC1sZWZ0IGxnOm15LTEyIHNtOm15LTggbGc6aC0xLzYgbGc6dy0xLzJcIj5cbiAgICAgICAgICAgICAgICA8aDEgY2xhc3NOYW1lPVwidGV4dC14bCBmb250LWJvbGQgdGV4dC1ncmF5LTkwMCBkYXJrOnRleHQtZ3JheS0yMDAgc206dGV4dC0yeGxcIj5cbiAgICAgICAgICAgICAgICAgICAge1wiVmFsaWRhdGluZyB5b3VyIHJldHVybmVkIHZhbHVlc1wifVxuICAgICAgICAgICAgICAgIDwvaDE+XG5cbiAgICAgICAgICAgICAgICA8cCBjbGFzc05hbWU9XCJtdC0xLjUgdGV4dC1zbSB0ZXh0LWdyYXktNTAwXCI+XG4gICAgICAgICAgICAgICAgICAgIHtcIlBsZWFzZSB3YWl0IGFzIHdlIHZhbGlkYXRlIGEgc3VjY2Vzc2Z1bCBjYWxlbmRhciBzeW5jIFwifVxuICAgICAgICAgICAgICAgIDwvcD5cbiAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgIWlzVmFsaWRcbiAgICAgICAgICAgICAgICAgICAgPyAoXG4gICAgICAgICAgICAgICAgICAgICAgICA8cCBjbGFzc05hbWU9XCJtdC0xLjUgdGV4dC1zbSB0ZXh0LXJlZC01MDBcIj5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB7XCJTb21ldGhpbmcgd2VudCB3cm9uZyB3aXRoIHRoZSBzeW5jIFwifVxuICAgICAgICAgICAgICAgICAgICAgICAgPC9wPlxuICAgICAgICAgICAgICAgICAgICApIDogbnVsbFxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJmbGV4IGp1c3RpZnktY2VudGVyIGl0ZW1zLWNlbnRlciBsZzpoLTUvNiB3LWZ1bGxcIj5cbiAgICAgICAgICAgICAgICA8U3Bpbm5lciBjb2xvcj0ncGluay41MDAnIC8+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgPC9kaXY+XG4gICAgKVxufVxuXG5leHBvcnQgZGVmYXVsdCBDYWxsYmFja0NhbGVuZGFyU3luY1xuIl19