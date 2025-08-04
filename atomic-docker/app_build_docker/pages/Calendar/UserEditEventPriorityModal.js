"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getServerSideProps = getServerSideProps;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const react_2 = require("@chakra-ui/react");
const Box_1 = __importDefault(require("@components/common/Box"));
const Text_1 = __importDefault(require("@components/common/Text"));
const TextField_1 = __importDefault(require("@components/TextField"));
const react_3 = require("@chakra-ui/react");
const Button_1 = __importDefault(require("@components/Button"));
const getEventById_1 = __importDefault(require("@lib/apollo/gql/getEventById"));
const updateEventForPriority_1 = __importDefault(require("@lib/apollo/gql/updateEventForPriority"));
const client_1 = require("@apollo/client");
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
function UserEditEventPriorityModal(props) {
    const [priority, setPriority] = (0, react_1.useState)(props.priority);
    const [isMessage1, setIsMessage1] = (0, react_1.useState)(false);
    const [error, setError] = (0, react_1.useState)('');
    const [success, setSuccess] = (0, react_1.useState)('');
    const client = props?.client;
    const eventId = props?.eventId;
    console.log(props?.priority, '   props?.priority');
    console.log(priority, '   priority');
    console.log(eventId, '   eventId');
    const toast = (0, react_3.useToast)();
    const updatePriority = async () => {
        try {
            // validate
            if (priority < 1) {
                toast({
                    status: 'error',
                    title: 'Priority must be greater than 0',
                    description: 'Priority must be greater than 0',
                    duration: 9000,
                    isClosable: true,
                });
                setError('Priority must be greater than 0');
                setTimeout(() => setError(''), 3000);
                return;
            }
            if (isNaN(priority)) {
                toast({
                    status: 'error',
                    title: 'Priority must be a number',
                    description: 'Priority must be a number',
                    duration: 9000,
                    isClosable: true,
                });
                setError('Priority must be a number');
                setTimeout(() => setError(''), 3000);
                return;
            }
            const existingEvent = (await client.query({
                query: getEventById_1.default,
                variables: {
                    id: eventId,
                },
            })).data?.Event_by_pk;
            if (existingEvent) {
                await client.mutate({
                    mutation: updateEventForPriority_1.default,
                    variables: {
                        id: existingEvent.id,
                        priority,
                    },
                    update(cache, { data }) {
                        cache.modify({
                            fields: {
                                Event(existingEvents = []) {
                                    const newEventRef = cache.writeFragment({
                                        data: data?.update_Event_by_pk,
                                        fragment: (0, client_1.gql) `
                                    fragment NewEvent on Event {
                                      id
                                      startDate
                                      endDate
                                      allDay
                                      recurrence
                                      recurrenceRule
                                      location
                                      notes
                                      attachments
                                      links
                                      timezone
                                      taskId
                                      taskType
                                      priority
                                      followUpEventId
                                      isFollowUp
                                      isPreEvent
                                      isPostEvent
                                      preEventId
                                      postEventId
                                      modifiable
                                      forEventId
                                      conferenceId
                                      maxAttendees
                                      attendeesOmitted
                                      sendUpdates
                                      anyoneCanAddSelf
                                      guestsCanInviteOthers
                                      guestsCanSeeOtherGuests
                                      originalStartDate
                                      originalTimezone
                                      originalAllDay
                                      status
                                      summary
                                      title
                                      transparency
                                      visibility
                                      recurringEventId
                                      iCalUID
                                      htmlLink
                                      colorId
                                      creator
                                      organizer
                                      endTimeUnspecified
                                      extendedProperties
                                      hangoutLink
                                      guestsCanModify
                                      locked
                                      source
                                      eventType
                                      privateCopy
                                      backgroundColor
                                      foregroundColor
                                      useDefaultAlarms
                                      deleted
                                      createdDate
                                      updatedAt
                                      userId
                                      calendarId
                                      positiveImpactScore
                                      negativeImpactScore
                                      positiveImpactDayOfWeek
                                      positiveImpactTime
                                      negativeImpactDayOfWeek
                                      negativeImpactTime
                                      preferredDayOfWeek
                                      preferredTime
                                      isExternalMeeting
                                      isExternalMeetingModifiable
                                      isMeetingModifiable
                                      isMeeting
                                      dailyTaskList
                                      weeklyTaskList
                                      isBreak
                                      preferredStartTimeRange
                                      preferredEndTimeRange
                                      copyAvailability
                                      copyTimeBlocking
                                      copyTimePreference
                                      copyReminders
                                      copyPriorityLevel
                                      copyModifiable
                                      copyCategories
                                      copyIsBreak
                                      userModifiedAvailability
                                      userModifiedTimeBlocking
                                      userModifiedTimePreference
                                      userModifiedReminders
                                      userModifiedPriorityLevel
                                      userModifiedCategories
                                      userModifiedModifiable
                                      userModifiedIsBreak
                                      hardDeadline
                                      softDeadline
                                      copyIsMeeting
                                      copyIsExternalMeeting
                                      userModifiedIsMeeting
                                      userModifiedIsExternalMeeting
                                      duration
                                      copyDuration
                                      userModifiedDuration
                                      method
                                      unlink
                                      copyColor
                                      userModifiedColor
                                      byWeekDay
                                      localSynced
                                      timeBlocking
                                      meetingId
                                      eventId
                                    }
                                  `
                                    });
                                    const filteredEvents = existingEvents?.filter((e) => (e.id !== data?.update_Event_by_pk?.id));
                                    return [...filteredEvents, newEventRef];
                                }
                            }
                        });
                    }
                });
                toast({
                    status: 'success',
                    title: 'Event priority updated successfully',
                    description: 'Event priority updated successfully',
                    duration: 9000,
                    isClosable: true,
                });
                setSuccess('Event priority updated successfully');
                setTimeout(() => setSuccess(''), 3000);
            }
            props.hidePriority();
        }
        catch (e) {
            console.log(e, ' error in useEffect for UserEditEventPriorityModal');
            setError('Oops... something went wrong');
            setTimeout(() => setError(''), 3000);
        }
    };
    const onChangePriority = (e) => {
        console.log(typeof e?.target?.value === 'number', ' number');
        const intValue = parseInt(e?.target?.value.replace(/[^0-9.]/g, ''), 10);
        if (isNaN(intValue)) {
            setPriority(0);
            return;
        }
        setPriority(intValue);
    };
    return ((0, jsx_runtime_1.jsx)(Box_1.default, { justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsxs)(Box_1.default, { children: [success && ((0, jsx_runtime_1.jsx)("div", { className: "alert alert-success shadow-lg", children: (0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("svg", { xmlns: "http://www.w3.org/2000/svg", className: "stroke-current flex-shrink-0 h-6 w-6", fill: "none", viewBox: "0 0 24 24", children: (0, jsx_runtime_1.jsx)("path", { strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: "2", d: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" }) }), (0, jsx_runtime_1.jsx)("span", { children: success })] }) })), error && ((0, jsx_runtime_1.jsx)("div", { className: "alert alert-error shadow-lg", children: (0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("svg", { xmlns: "http://www.w3.org/2000/svg", className: "stroke-current flex-shrink-0 h-6 w-6", fill: "none", viewBox: "0 0 24 24", children: (0, jsx_runtime_1.jsx)("path", { strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: "2", d: "M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" }) }), (0, jsx_runtime_1.jsx)("span", { children: error })] }) })), (0, jsx_runtime_1.jsx)(Box_1.default, { justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsx)(react_2.Tooltip, { hasArrow: true, label: 'Higher values have higher priority over other events', bg: 'purple.700', color: 'white', children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "buttonLink", children: "Priority (Hint)" }) }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { justifyContent: "center", alignItems: "flex-start", children: (0, jsx_runtime_1.jsx)(TextField_1.default, { label: "Priority", value: `${priority}`, onChange: onChangePriority, type: "number" }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsx)(Button_1.default, { onClick: updatePriority, children: "Update" }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsx)("button", { className: "btn btn-link no-underline hover:no-underline", onClick: props.hidePriority, children: "Close" }) })] }) }));
}
exports.default = UserEditEventPriorityModal;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlckVkaXRFdmVudFByaW9yaXR5TW9kYWwuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJVc2VyRWRpdEV2ZW50UHJpb3JpdHlNb2RhbC50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUFvQkEsZ0RBcUNDOztBQXpERCxpQ0FFYztBQUVkLDRDQUEwQztBQUMxQyxpRUFBd0M7QUFDeEMsbUVBQTBDO0FBQzFDLHNFQUE2QztBQUc3Qyw0Q0FBMkM7QUFDM0MsZ0VBQXVDO0FBQ3ZDLGdGQUF1RDtBQUN2RCxvR0FBMkU7QUFDM0UsMkNBQXlFO0FBRXpFLHdFQUE4QztBQUM5Qyw4REFBMEQ7QUFDMUQsOEVBQXFEO0FBRTlDLEtBQUssVUFBVSxrQkFBa0IsQ0FBQyxFQUFFLEdBQUcsRUFBRSxHQUFHLEVBQWlEO0lBQ2xHLDBGQUEwRjtJQUMxRixzQ0FBc0M7SUFDdEMseUVBQXlFO0lBQ3pFLDBCQUFlLENBQUMsSUFBSSxDQUFDLElBQUEsNkJBQWEsR0FBRSxDQUFDLENBQUE7SUFDckMsSUFBSSxPQUFPLENBQUE7SUFDWCxJQUFJLENBQUM7UUFDSCxPQUFPLEdBQUcsTUFBTSxpQkFBTyxDQUFDLFVBQVUsQ0FBQyxHQUFHLEVBQUUsR0FBRyxFQUFFO1lBQzNDLDZCQUE2QixFQUFFLEtBQUs7Z0JBQ2xDLE9BQU8sRUFBRSxDQUFBO1lBQ1gsQ0FBQztTQUNGLENBQUMsQ0FBQTtJQUNKLENBQUM7SUFBQyxPQUFPLEdBQVEsRUFBRSxDQUFDO1FBQ2xCLElBQUksR0FBRyxDQUFDLElBQUksS0FBSyxpQkFBTyxDQUFDLEtBQUssQ0FBQyxpQkFBaUIsRUFBRSxDQUFDO1lBQ2pELE9BQU8sRUFBRSxLQUFLLEVBQUUsRUFBRSxlQUFlLEVBQUUsZUFBZSxFQUFFLEVBQUUsQ0FBQTtRQUN4RCxDQUFDO2FBQU0sSUFBSSxHQUFHLENBQUMsSUFBSSxLQUFLLGlCQUFPLENBQUMsS0FBSyxDQUFDLFlBQVksRUFBRSxDQUFDO1lBQ25ELGtFQUFrRTtZQUNsRSxxRUFB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LGdCQUFNLElBQUMsT0FBTyxFQUFFLGNBQWMsdUJBRXRCLEdBQ1AsRUFDTix1QkFBQyxhQUFHLElBQUMsY0FBYyxFQUFDLFFBQVEsRUFBQyxVQUFVLEVBQUMsUUFBUSxZQUM1QyxtQ0FBUSxTQUFTLEVBQUMsOENBQThDLEVBQUMsT0FBTyxFQUFFLEtBQUssQ0FBQyxZQUFZLHNCQUVuRixHQUVQLElBQ0osR0FDSixDQUNULENBQUE7QUFDTCxDQUFDO0FBRUQsa0JBQWUsMEJBQTBCLENBQUEiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgUmVhY3QsIHtcbiAgICB1c2VTdGF0ZSxcbn0gZnJvbSAncmVhY3QnXG5cbmltcG9ydCB7IFRvb2x0aXAgfSBmcm9tICdAY2hha3JhLXVpL3JlYWN0J1xuaW1wb3J0IEJveCBmcm9tICdAY29tcG9uZW50cy9jb21tb24vQm94J1xuaW1wb3J0IFRleHQgZnJvbSAnQGNvbXBvbmVudHMvY29tbW9uL1RleHQnXG5pbXBvcnQgVGV4dEZpZWxkIGZyb20gJ0Bjb21wb25lbnRzL1RleHRGaWVsZCdcblxuaW1wb3J0IHtFdmVudFR5cGV9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL0V2ZW50VHlwZSdcbmltcG9ydCB7IHVzZVRvYXN0IH0gZnJvbSAnQGNoYWtyYS11aS9yZWFjdCdcbmltcG9ydCBCdXR0b24gZnJvbSAnQGNvbXBvbmVudHMvQnV0dG9uJ1xuaW1wb3J0IGdldEV2ZW50QnlJZCBmcm9tICdAbGliL2Fwb2xsby9ncWwvZ2V0RXZlbnRCeUlkJ1xuaW1wb3J0IHVwZGF0ZUV2ZW50Rm9yUHJpb3JpdHkgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL3VwZGF0ZUV2ZW50Rm9yUHJpb3JpdHknXG5pbXBvcnQgeyBBcG9sbG9DbGllbnQsIGdxbCwgTm9ybWFsaXplZENhY2hlT2JqZWN0IH0gZnJvbSAnQGFwb2xsby9jbGllbnQnXG5pbXBvcnQgeyBOZXh0QXBpUmVxdWVzdCwgTmV4dEFwaVJlc3BvbnNlIH0gZnJvbSAnbmV4dCc7XG5pbXBvcnQgc3VwZXJ0b2tlbnNOb2RlIGZyb20gJ3N1cGVydG9rZW5zLW5vZGUnXG5pbXBvcnQgeyBiYWNrZW5kQ29uZmlnIH0gZnJvbSAnLi4vLi4vY29uZmlnL2JhY2tlbmRDb25maWcnXG5pbXBvcnQgU2Vzc2lvbiBmcm9tICdzdXBlcnRva2Vucy1ub2RlL3JlY2lwZS9zZXNzaW9uJ1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0U2VydmVyU2lkZVByb3BzKHsgcmVxLCByZXMgfTogeyByZXE6IE5leHRBcGlSZXF1ZXN0LCByZXM6IE5leHRBcGlSZXNwb25zZSB9KSB7XG4gIC8vIE5vdGljZSBob3cgdGhlIHNlcnZlciB1c2VzIGBBUElgIGZyb20gYHdpdGhTU1JDb250ZXh0YCwgaW5zdGVhZCBvZiB0aGUgdG9wLWxldmVsIGBBUElgLlxuICAvLyBjb25zdCBTU1IgPSB3aXRoU1NSQ29udGV4dCh7IHJlcSB9KVxuICAvLyB0aGlzIHJ1bnMgb24gdGhlIGJhY2tlbmQsIHNvIHdlIG11c3QgY2FsbCBpbml0IG9uIHN1cGVydG9rZW5zLW5vZGUgU0RLXG4gIHN1cGVydG9rZW5zTm9kZS5pbml0KGJhY2tlbmRDb25maWcoKSlcbiAgbGV0IHNlc3Npb25cbiAgdHJ5IHtcbiAgICBzZXNzaW9uID0gYXdhaXQgU2Vzc2lvbi5nZXRTZXNzaW9uKHJlcSwgcmVzLCB7XG4gICAgICBvdmVycmlkZUdsb2JhbENsYWltVmFsaWRhdG9yczogYXN5bmMgZnVuY3Rpb24gKCkge1xuICAgICAgICByZXR1cm4gW11cbiAgICAgIH0sXG4gICAgfSlcbiAgfSBjYXRjaCAoZXJyOiBhbnkpIHtcbiAgICBpZiAoZXJyLnR5cGUgPT09IFNlc3Npb24uRXJyb3IuVFJZX1JFRlJFU0hfVE9LRU4pIHtcbiAgICAgIHJldHVybiB7IHByb3BzOiB7IGZyb21TdXBlcnRva2VuczogJ25lZWRzLXJlZnJlc2gnIH0gfVxuICAgIH0gZWxzZSBpZiAoZXJyLnR5cGUgPT09IFNlc3Npb24uRXJyb3IuVU5BVVRIT1JJU0VEKSB7XG4gICAgICAvLyB0aGlzIHdpbGwgZm9yY2UgdGhlIGZyb250ZW5kIHRvIHRyeSBhbmQgcmVmcmVzaCB3aGljaCB3aWxsIGZhaWxcbiAgICAgIC8vIGNsZWFyaW5nIGFsbCBjb29raWVzIGFuZCByZWRpcmVjdGluZyB0aGUgdXNlciB0byB0aGUgbG9naW4gc2NyZWVuLlxuICAgICAgcmV0dXJuIHsgcHJvcHM6IHsgZnJvbVN1cGVydG9rZW5zOiAnbmVlZHMtcmVmcmVzaCcgfSB9XG4gICAgfVxuICAgIHRocm93IGVyclxuICB9XG5cbiAgaWYgKCFzZXNzaW9uPy5nZXRVc2VySWQoKSkge1xuICAgIHJldHVybiB7XG4gICAgICByZWRpcmVjdDoge1xuICAgICAgICBkZXN0aW5hdGlvbjogJy9Vc2VyL0xvZ2luL1VzZXJMb2dpbicsXG4gICAgICAgIHBlcm1hbmVudDogZmFsc2UsXG4gICAgICB9LFxuICAgIH1cbiAgfVxuXG4gIHJldHVybiB7XG4gICAgcHJvcHM6IHtcbiAgICAgIHN1Yjogc2Vzc2lvbi5nZXRVc2VySWQoKSxcbiAgICB9XG4gIH1cbn1cblxuXG50eXBlIFByb3BzID0ge1xuICAgIGV2ZW50SWQ6IHN0cmluZyxcbiAgICBoaWRlUHJpb3JpdHk6ICgpID0+IHZvaWQsXG4gICAgcHJpb3JpdHk6IG51bWJlcixcbiAgICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxufVxuXG5mdW5jdGlvbiBVc2VyRWRpdEV2ZW50UHJpb3JpdHlNb2RhbChwcm9wczogUHJvcHMpIHtcbiAgICBjb25zdCBbcHJpb3JpdHksIHNldFByaW9yaXR5XSA9IHVzZVN0YXRlPG51bWJlcj4ocHJvcHMucHJpb3JpdHkpXG4gICAgY29uc3QgW2lzTWVzc2FnZTEsIHNldElzTWVzc2FnZTFdID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gICAgY29uc3QgW2Vycm9yLCBzZXRFcnJvcl0gPSB1c2VTdGF0ZTxzdHJpbmc+KCcnKVxuICAgIGNvbnN0IFtzdWNjZXNzLCBzZXRTdWNjZXNzXSA9IHVzZVN0YXRlPHN0cmluZz4oJycpXG5cbiAgICBjb25zdCBjbGllbnQgPSBwcm9wcz8uY2xpZW50XG4gICAgY29uc3QgZXZlbnRJZCA9IHByb3BzPy5ldmVudElkXG5cbiAgICBjb25zb2xlLmxvZyhwcm9wcz8ucHJpb3JpdHksICcgICBwcm9wcz8ucHJpb3JpdHknKVxuICAgIGNvbnNvbGUubG9nKHByaW9yaXR5LCAnICAgcHJpb3JpdHknKVxuICAgIGNvbnNvbGUubG9nKGV2ZW50SWQsICcgICBldmVudElkJylcbiAgICBjb25zdCB0b2FzdCA9IHVzZVRvYXN0KClcblxuICAgIGNvbnN0IHVwZGF0ZVByaW9yaXR5ID0gYXN5bmMgKCkgPT4ge1xuICAgICAgICB0cnkge1xuICAgICAgICAgICAgLy8gdmFsaWRhdGVcbiAgICAgICAgICAgIGlmIChwcmlvcml0eSA8IDEpIHtcbiAgICAgICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgICAgICAgICAgdGl0bGU6ICdQcmlvcml0eSBtdXN0IGJlIGdyZWF0ZXIgdGhhbiAwJyxcbiAgICAgICAgICAgICAgICAgICAgZGVzY3JpcHRpb246ICdQcmlvcml0eSBtdXN0IGJlIGdyZWF0ZXIgdGhhbiAwJyxcbiAgICAgICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICAgICAgICAgICAgfSlcbiAgICAgICAgICAgICAgICBzZXRFcnJvcignUHJpb3JpdHkgbXVzdCBiZSBncmVhdGVyIHRoYW4gMCcpXG4gICAgICAgICAgICAgICAgc2V0VGltZW91dCgoKSA9PiBzZXRFcnJvcignJyksIDMwMDApXG4gICAgICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGlmIChpc05hTihwcmlvcml0eSkpIHtcbiAgICAgICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgICAgICAgICAgICAgIHRpdGxlOiAnUHJpb3JpdHkgbXVzdCBiZSBhIG51bWJlcicsXG4gICAgICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnUHJpb3JpdHkgbXVzdCBiZSBhIG51bWJlcicsXG4gICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICAgICAgICAgIH0pXG5cbiAgICAgICAgICAgICAgICBzZXRFcnJvcignUHJpb3JpdHkgbXVzdCBiZSBhIG51bWJlcicpXG4gICAgICAgICAgICAgICAgc2V0VGltZW91dCgoKSA9PiBzZXRFcnJvcignJyksIDMwMDApXG4gICAgICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGNvbnN0IGV4aXN0aW5nRXZlbnQgPSAoYXdhaXQgY2xpZW50LnF1ZXJ5PHsgRXZlbnRfYnlfcGs6IEV2ZW50VHlwZSB9Pih7XG4gICAgICAgICAgICAgICAgcXVlcnk6IGdldEV2ZW50QnlJZCxcbiAgICAgICAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgICAgICAgICAgaWQ6IGV2ZW50SWQsXG4gICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIH0pKS5kYXRhPy5FdmVudF9ieV9wa1xuICAgICAgICAgICAgaWYgKGV4aXN0aW5nRXZlbnQpIHtcbiAgICAgICAgICAgICAgICBhd2FpdCBjbGllbnQubXV0YXRlPHsgdXBkYXRlX0V2ZW50X2J5X3BrOiBFdmVudFR5cGUgfT4oe1xuICAgICAgICAgICAgICAgICAgICBtdXRhdGlvbjogdXBkYXRlRXZlbnRGb3JQcmlvcml0eSxcbiAgICAgICAgICAgICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICAgICAgICAgICAgICBpZDogZXhpc3RpbmdFdmVudC5pZCxcbiAgICAgICAgICAgICAgICAgICAgICAgIHByaW9yaXR5LCAgXG4gICAgICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZShjYWNoZSwgeyBkYXRhIH0pIHtcbiAgICAgICAgICAgICAgICAgICAgICAgXG4gICAgICAgICAgICAgICAgXG4gICAgICAgICAgICAgICAgICAgICAgICBjYWNoZS5tb2RpZnkoe1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGZpZWxkczoge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBFdmVudChleGlzdGluZ0V2ZW50cyA9IFtdKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvbnN0IG5ld0V2ZW50UmVmID0gY2FjaGUud3JpdGVGcmFnbWVudCh7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgZGF0YTogZGF0YT8udXBkYXRlX0V2ZW50X2J5X3BrLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGZyYWdtZW50OiBncWxgXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBmcmFnbWVudCBOZXdFdmVudCBvbiBFdmVudCB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBlbmREYXRlXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGFsbERheVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICByZWN1cnJlbmNlXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2VSdWxlXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGxvY2F0aW9uXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG5vdGVzXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGF0dGFjaG1lbnRzXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGxpbmtzXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHRhc2tJZFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB0YXNrVHlwZVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBwcmlvcml0eVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBmb2xsb3dVcEV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgaXNGb2xsb3dVcFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBpc1ByZUV2ZW50XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlzUG9zdEV2ZW50XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHByZUV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgcG9zdEV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgbW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBmb3JFdmVudElkXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvbmZlcmVuY2VJZFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBtYXhBdHRlbmRlZXNcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVzT21pdHRlZFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBzZW5kVXBkYXRlc1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBhbnlvbmVDYW5BZGRTZWxmXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0c1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbFRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG9yaWdpbmFsQWxsRGF5XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHN0YXR1c1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBzdW1tYXJ5XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHRpdGxlXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHRyYW5zcGFyZW5jeVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB2aXNpYmlsaXR5XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJlY3VycmluZ0V2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgaUNhbFVJRFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBodG1sTGlua1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb2xvcklkXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNyZWF0b3JcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgb3JnYW5pemVyXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGVuZFRpbWVVbnNwZWNpZmllZFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBleHRlbmRlZFByb3BlcnRpZXNcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgaGFuZ291dExpbmtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuTW9kaWZ5XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGxvY2tlZFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBzb3VyY2VcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgZXZlbnRUeXBlXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHByaXZhdGVDb3B5XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgdXNlRGVmYXVsdEFsYXJtc1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBwb3NpdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3REYXlPZldlZWtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RUaW1lXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0VGltZVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWREYXlPZldlZWtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkVGltZVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgaXNNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBpc01lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgZGFpbHlUYXNrTGlzdFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB3ZWVrbHlUYXNrTGlzdFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBpc0JyZWFrXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlSZW1pbmRlcnNcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY29weUNhdGVnb3JpZXNcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY29weUlzQnJlYWtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRSZW1pbmRlcnNcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRDYXRlZ29yaWVzXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZE1vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNCcmVha1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBoYXJkRGVhZGxpbmVcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgc29mdERlYWRsaW5lXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlJc01lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZElzTWVldGluZ1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBkdXJhdGlvblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb3B5RHVyYXRpb25cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkRHVyYXRpb25cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgbWV0aG9kXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVubGlua1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb3B5Q29sb3JcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkQ29sb3JcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgYnlXZWVrRGF5XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGxvY2FsU3luY2VkXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGBcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvbnN0IGZpbHRlcmVkRXZlbnRzID0gZXhpc3RpbmdFdmVudHM/LmZpbHRlcigoZTogRXZlbnRUeXBlKSA9PiAoZS5pZCAhPT0gZGF0YT8udXBkYXRlX0V2ZW50X2J5X3BrPy5pZCkpXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiBbLi4uZmlsdGVyZWRFdmVudHMsIG5ld0V2ZW50UmVmXTtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH0pICAgXG4gICAgICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgICAgICBzdGF0dXM6ICdzdWNjZXNzJyxcbiAgICAgICAgICAgICAgICAgICAgdGl0bGU6ICdFdmVudCBwcmlvcml0eSB1cGRhdGVkIHN1Y2Nlc3NmdWxseScsXG4gICAgICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnRXZlbnQgcHJpb3JpdHkgdXBkYXRlZCBzdWNjZXNzZnVsbHknLFxuICAgICAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZSxcbiAgICAgICAgICAgICAgICB9KVxuXG4gICAgICAgICAgICAgICAgc2V0U3VjY2VzcygnRXZlbnQgcHJpb3JpdHkgdXBkYXRlZCBzdWNjZXNzZnVsbHknKVxuICAgICAgICAgICAgICAgIHNldFRpbWVvdXQoKCkgPT4gc2V0U3VjY2VzcygnJyksIDMwMDApXG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBcbiAgICAgICAgICAgIHByb3BzLmhpZGVQcmlvcml0eSgpXG4gICAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKGUsICcgZXJyb3IgaW4gdXNlRWZmZWN0IGZvciBVc2VyRWRpdEV2ZW50UHJpb3JpdHlNb2RhbCcpXG4gICAgICAgICAgICBzZXRFcnJvcignT29wcy4uLiBzb21ldGhpbmcgd2VudCB3cm9uZycpXG4gICAgICAgICAgICBzZXRUaW1lb3V0KCgpID0+IHNldEVycm9yKCcnKSwgMzAwMClcbiAgICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IG9uQ2hhbmdlUHJpb3JpdHkgPSAoZTogeyB0YXJnZXQ6IHsgdmFsdWU6IHN0cmluZyB9IH0pID0+IHtcbiAgICAgICAgY29uc29sZS5sb2codHlwZW9mIGU/LnRhcmdldD8udmFsdWUgPT09ICdudW1iZXInLCAnIG51bWJlcicpXG4gICAgICAgIGNvbnN0IGludFZhbHVlID0gcGFyc2VJbnQoZT8udGFyZ2V0Py52YWx1ZS5yZXBsYWNlKC9bXjAtOS5dL2csICcnKSwgMTApXG5cbiAgICAgICAgaWYgKGlzTmFOKGludFZhbHVlKSkge1xuICAgICAgICAgICAgc2V0UHJpb3JpdHkoMClcbiAgICAgICAgICAgIHJldHVyblxuICAgICAgICB9XG5cbiAgICAgICAgc2V0UHJpb3JpdHkoaW50VmFsdWUpXG4gICAgfVxuXG5cbiAgICByZXR1cm4gKFxuICAgICAgICA8Qm94IGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgPEJveD5cbiAgICAgICAgICAgICAgICB7c3VjY2VzcyAmJiAoXG4gICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiYWxlcnQgYWxlcnQtc3VjY2VzcyBzaGFkb3ctbGdcIj5cbiAgICAgICAgICAgICAgICAgICAgICAgIDxkaXY+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPHN2ZyB4bWxucz1cImh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnXCIgY2xhc3NOYW1lPVwic3Ryb2tlLWN1cnJlbnQgZmxleC1zaHJpbmstMCBoLTYgdy02XCIgZmlsbD1cIm5vbmVcIiB2aWV3Qm94PVwiMCAwIDI0IDI0XCI+PHBhdGggc3Ryb2tlTGluZWNhcD1cInJvdW5kXCIgc3Ryb2tlTGluZWpvaW49XCJyb3VuZFwiIHN0cm9rZVdpZHRoPVwiMlwiIGQ9XCJNOSAxMmwyIDIgNC00bTYgMmE5IDkgMCAxMS0xOCAwIDkgOSAwIDAxMTggMHpcIiAvPjwvc3ZnPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxzcGFuPntzdWNjZXNzfTwvc3Bhbj5cbiAgICAgICAgICAgICAgICAgICAgICAgIDwvZGl2PlxuICAgICAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICApfVxuICAgICAgICAgICAgICAgIHtlcnJvciAmJiAoXG4gICAgICAgICAgICAgICAgICAgIDxkaXYgY2xhc3NOYW1lPVwiYWxlcnQgYWxlcnQtZXJyb3Igc2hhZG93LWxnXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICA8ZGl2PlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxzdmcgeG1sbnM9XCJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2Z1wiIGNsYXNzTmFtZT1cInN0cm9rZS1jdXJyZW50IGZsZXgtc2hyaW5rLTAgaC02IHctNlwiIGZpbGw9XCJub25lXCIgdmlld0JveD1cIjAgMCAyNCAyNFwiPjxwYXRoIHN0cm9rZUxpbmVjYXA9XCJyb3VuZFwiIHN0cm9rZUxpbmVqb2luPVwicm91bmRcIiBzdHJva2VXaWR0aD1cIjJcIiBkPVwiTTEwIDE0bDItMm0wIDBsMi0ybS0yIDJsLTItMm0yIDJsMiAybTctMmE5IDkgMCAxMS0xOCAwIDkgOSAwIDAxMTggMHpcIiAvPjwvc3ZnPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxzcGFuPntlcnJvcn08L3NwYW4+XG4gICAgICAgICAgICAgICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgICAgICAgICAgPC9kaXY+XG4gICAgICAgICAgICAgICAgKX1cbiAgICAgICAgICAgICAgICA8Qm94IGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgICAgICAgICA8VG9vbHRpcCBoYXNBcnJvdyBsYWJlbD0nSGlnaGVyIHZhbHVlcyBoYXZlIGhpZ2hlciBwcmlvcml0eSBvdmVyIG90aGVyIGV2ZW50cycgYmc9J3B1cnBsZS43MDAnIGNvbG9yPSd3aGl0ZSc+XG4gICAgICAgICAgICAgICAgICAgICAgICA8VGV4dCB2YXJpYW50PVwiYnV0dG9uTGlua1wiPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIFByaW9yaXR5IChIaW50KVxuICAgICAgICAgICAgICAgICAgICAgICAgPC9UZXh0PlxuICAgICAgICAgICAgICAgICAgICA8L1Rvb2x0aXA+XG4gICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgPEJveCBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJmbGV4LXN0YXJ0XCI+XG4gICAgICAgICAgICAgICAgICAgICAgICA8VGV4dEZpZWxkXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgbGFiZWw9XCJQcmlvcml0eVwiXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdmFsdWU9e2Ake3ByaW9yaXR5fWB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgb25DaGFuZ2U9e29uQ2hhbmdlUHJpb3JpdHl9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdHlwZT1cIm51bWJlclwiXG4gICAgICAgICAgICAgICAgICAgICAgICAvPiAgXG4gICAgICAgICAgICAgICAgICAgIFxuICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgIDxCb3gganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgICAgIDxCdXR0b24gb25DbGljaz17dXBkYXRlUHJpb3JpdHl9PlxuICAgICAgICAgICAgICAgICAgICAgICAgVXBkYXRlXG4gICAgICAgICAgICAgICAgICAgIDwvQnV0dG9uPlxuICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgIDxCb3gganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgICAgIDxidXR0b24gY2xhc3NOYW1lPVwiYnRuIGJ0bi1saW5rIG5vLXVuZGVybGluZSBob3Zlcjpuby11bmRlcmxpbmVcIiBvbkNsaWNrPXtwcm9wcy5oaWRlUHJpb3JpdHl9PlxuICAgICAgICAgICAgICAgICAgICAgICAgQ2xvc2VcbiAgICAgICAgICAgICAgICAgICAgPC9idXR0b24+XG4gICAgICAgICAgICAgICAgICAgIFxuICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgPC9Cb3g+IFxuICAgICAgICA8L0JveD5cbiAgICApXG59XG5cbmV4cG9ydCBkZWZhdWx0IFVzZXJFZGl0RXZlbnRQcmlvcml0eU1vZGFsXG4iXX0=