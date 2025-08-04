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
const Button_1 = __importDefault(require("@components/Button"));
const Wizard_1 = __importDefault(require("@components/Wizard"));
const RegularCard_1 = __importDefault(require("@components/RegularCard"));
const user_context_1 = require("@lib/user-context");
const router_1 = require("next/router");
const zoomMeetingHelper_1 = require("@lib/zoom/zoomMeetingHelper");
const ContactHelper_1 = require("@lib/Contact/ContactHelper");
const googleCalendarHelper_1 = require("@lib/calendarLib/googleCalendarHelper");
const UserMeetingAssistHelper_1 = require("@lib/Assist/UserMeetingAssistHelper");
const OnBoardHelper3_1 = require("@lib/OnBoard/OnBoardHelper3");
const uuid_1 = require("uuid");
const date_utils_1 = require("@lib/date-utils");
const CMPWStep1_1 = __importDefault(require("./ChatMeetingPreferenceWizard/CMPWStep1"));
const CMPWStep2_1 = __importDefault(require("./ChatMeetingPreferenceWizard/CMPWStep2"));
const CMPWStep3_1 = __importDefault(require("./ChatMeetingPreferenceWizard/CMPWStep3"));
const CMPWStep4_1 = __importDefault(require("./ChatMeetingPreferenceWizard/CMPWStep4"));
const CMPWStep5_1 = __importDefault(require("./ChatMeetingPreferenceWizard/CMPWStep5"));
const lodash_1 = __importDefault(require("lodash"));
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
function UserChatMeetingPreferences() {
    const [sendUpdates, setSendUpdates] = (0, react_1.useState)('all');
    const [guestsCanInviteOthers, setGuestsCanInviteOthers] = (0, react_1.useState)(true);
    const [transparency, setTransparency] = (0, react_1.useState)('opaque');
    const [visibility, setVisibility] = (0, react_1.useState)('default');
    const [useDefaultAlarms, setUseDefaultAlarms] = (0, react_1.useState)(true);
    const [alarms, setAlarms] = (0, react_1.useState)([]);
    const [duration, setDuration] = (0, react_1.useState)(30);
    const [enableConference, setEnableConference] = (0, react_1.useState)(false);
    const [conferenceApp, setConferenceApp] = (0, react_1.useState)('google');
    const [zoomMeet, setZoomMeet] = (0, react_1.useState)(false);
    const [googleMeet, setGoogleMeet] = (0, react_1.useState)(false);
    const [isBufferTime, setIsBufferTime] = (0, react_1.useState)(false);
    const [beforeEventMinutes, setBeforeEventMinutes] = (0, react_1.useState)(0);
    const [afterEventMinutes, setAfterEventMinutes] = (0, react_1.useState)(0);
    const [anyoneCanAddSelf, setAnyoneCanAddSelf] = (0, react_1.useState)(true);
    const [guestsCanSeeOtherGuests, setGuestsCanSeeOtherGuests] = (0, react_1.useState)(true);
    const [name, setName] = (0, react_1.useState)('');
    const [user, setUser] = (0, react_1.useState)();
    const [isZoomAvailable, setIsZoomAvailable] = (0, react_1.useState)(false);
    const [isGoogleMeetAvailable, setIsGoogleMeetAvailable] = (0, react_1.useState)(false);
    const [primaryEmail, setPrimaryEmail] = (0, react_1.useState)('');
    const [id, setId] = (0, react_1.useState)('');
    const [activeIndex, setActiveIndex] = (0, react_1.useState)(0);
    const [completedStep, setCompletedStep] = (0, react_1.useState)();
    const [chatMeetingPreferences, setChatMeetingPreferences] = (0, react_1.useState)();
    const [lockAfter, setLockAfter] = (0, react_1.useState)(false);
    const { sub, client } = (0, user_context_1.useAppContext)();
    const userId = sub;
    console.log(sub, ' sub inside userchatmeetingpreferences');
    const router = (0, router_1.useRouter)();
    const toast = (0, react_2.useToast)();
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
    // check if google available
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
    // get user and update if necessary
    // get chat meeting preferences
    (0, react_1.useEffect)(() => {
        (async () => {
            try {
                if (!userId) {
                    return;
                }
                const newId = (0, uuid_1.v4)();
                let oldOrNewChatMeetingPreferences = await (0, OnBoardHelper3_1.getChatMeetingPreferences)(client, userId);
                if (!oldOrNewChatMeetingPreferences?.id) {
                    oldOrNewChatMeetingPreferences = {
                        id: newId,
                        userId,
                        timezone: date_utils_1.dayjs.tz.guess(),
                        enableConference: true,
                        updatedAt: (0, date_utils_1.dayjs)().format(),
                        createdDate: (0, date_utils_1.dayjs)().format()
                    };
                    await (0, OnBoardHelper3_1.upsertChatMeetingPreferencesGivenUserId)(client, oldOrNewChatMeetingPreferences);
                }
                if (oldOrNewChatMeetingPreferences?.sendUpdates) {
                    setSendUpdates(oldOrNewChatMeetingPreferences?.sendUpdates);
                }
                if (oldOrNewChatMeetingPreferences?.guestsCanInviteOthers !== undefined) {
                    setGuestsCanInviteOthers(oldOrNewChatMeetingPreferences?.guestsCanInviteOthers);
                }
                if (oldOrNewChatMeetingPreferences?.transparency) {
                    setTransparency(oldOrNewChatMeetingPreferences?.transparency);
                }
                if (oldOrNewChatMeetingPreferences?.visibility) {
                    setVisibility(oldOrNewChatMeetingPreferences?.visibility);
                }
                if (oldOrNewChatMeetingPreferences?.useDefaultAlarms !== undefined) {
                    setUseDefaultAlarms(oldOrNewChatMeetingPreferences?.useDefaultAlarms);
                }
                if (oldOrNewChatMeetingPreferences?.reminders) {
                    setAlarms(oldOrNewChatMeetingPreferences?.reminders);
                }
                if (oldOrNewChatMeetingPreferences?.duration) {
                    setDuration(oldOrNewChatMeetingPreferences?.duration);
                }
                if (oldOrNewChatMeetingPreferences?.enableConference !== undefined) {
                    setEnableConference(oldOrNewChatMeetingPreferences?.enableConference);
                }
                if (oldOrNewChatMeetingPreferences?.conferenceApp) {
                    setConferenceApp(oldOrNewChatMeetingPreferences?.conferenceApp);
                    if (oldOrNewChatMeetingPreferences?.conferenceApp === 'zoom') {
                        setZoomMeet(true);
                    }
                    else if (oldOrNewChatMeetingPreferences?.conferenceApp === 'google') {
                        setGoogleMeet(true);
                    }
                }
                if (oldOrNewChatMeetingPreferences?.bufferTime) {
                    setIsBufferTime(true);
                    if (oldOrNewChatMeetingPreferences?.bufferTime?.beforeEvent) {
                        setBeforeEventMinutes(oldOrNewChatMeetingPreferences?.bufferTime?.beforeEvent);
                    }
                    if (oldOrNewChatMeetingPreferences?.bufferTime?.afterEvent) {
                        setAfterEventMinutes(oldOrNewChatMeetingPreferences?.bufferTime?.afterEvent);
                    }
                }
                if (oldOrNewChatMeetingPreferences?.anyoneCanAddSelf !== undefined) {
                    setAnyoneCanAddSelf(oldOrNewChatMeetingPreferences?.anyoneCanAddSelf);
                }
                if (oldOrNewChatMeetingPreferences?.guestsCanSeeOtherGuests !== undefined) {
                    setGuestsCanSeeOtherGuests(oldOrNewChatMeetingPreferences?.guestsCanSeeOtherGuests);
                }
                const oldUser = await (0, UserMeetingAssistHelper_1.getUserGivenId)(client, userId);
                setUser(oldUser);
                if (oldOrNewChatMeetingPreferences?.name) {
                    setName(oldOrNewChatMeetingPreferences?.name);
                }
                else if (oldUser?.name) {
                    setName(oldUser?.name);
                }
                if (oldOrNewChatMeetingPreferences?.primaryEmail) {
                    setPrimaryEmail(oldOrNewChatMeetingPreferences?.primaryEmail);
                }
                else {
                    const oldDbInfoItems = await (0, ContactHelper_1.listUserContactInfosGivenUserId)(client, userId);
                    if (oldDbInfoItems && oldDbInfoItems?.length > 0) {
                        const email = oldDbInfoItems?.find(i => ((!!i?.primary && (i?.type === 'email'))))?.id;
                        setPrimaryEmail(email);
                    }
                }
                if (oldOrNewChatMeetingPreferences?.id) {
                    setId(oldOrNewChatMeetingPreferences?.id);
                }
                else {
                    setId(newId);
                }
                if (oldOrNewChatMeetingPreferences?.lockAfter !== undefined) {
                    setLockAfter(oldOrNewChatMeetingPreferences?.lockAfter ?? true);
                }
                setChatMeetingPreferences(oldOrNewChatMeetingPreferences);
            }
            catch (e) {
                console.log(e, ' unable to get chat meeting preferences');
            }
        })();
    }, [client, userId]);
    const saveChatMeetingPreferences = async () => {
        try {
            const updatedChatMeetingPreferences = {
                ...chatMeetingPreferences,
                id,
                userId,
                sendUpdates,
                guestsCanInviteOthers,
                transparency,
                visibility,
                useDefaultAlarms,
                reminders: alarms,
                duration,
                enableConference,
                conferenceApp,
                anyoneCanAddSelf,
                guestsCanSeeOtherGuests,
                name,
                primaryEmail,
                updatedAt: (0, date_utils_1.dayjs)().format(),
            };
            if (isBufferTime) {
                updatedChatMeetingPreferences.bufferTime = {
                    beforeEvent: beforeEventMinutes,
                    afterEvent: afterEventMinutes,
                };
            }
            await (0, OnBoardHelper3_1.upsertChatMeetingPreferencesGivenUserId)(client, lodash_1.default.omit(updatedChatMeetingPreferences, ['__typename']));
            toast({
                status: 'success',
                title: 'Meeting Preferences for chat saved',
                description: 'Meeting Preferencest saved successfully',
                duration: 9000,
                isClosable: true,
            });
        }
        catch (e) {
            console.log(e, ' unable to save chat meeting preferences');
            toast({
                status: 'error',
                title: 'Oops...',
                description: 'Looks like something went wrong',
                duration: 9000,
                isClosable: true,
            });
        }
    };
    const goToPrevStep = () => {
        const prevActiveIndex = activeIndex;
        const newActiveIndex = prevActiveIndex === 0 ? 0 : prevActiveIndex - 1;
        setActiveIndex(newActiveIndex);
    };
    const renderPrevButton = () => {
        if (activeIndex === 0) {
            return (0, jsx_runtime_1.jsx)(Box_1.default, { ml: { phone: 's', tablet: 'm' } });
        }
        return ((0, jsx_runtime_1.jsx)(Box_1.default, { ml: { phone: 's', tablet: 'm' }, children: (0, jsx_runtime_1.jsx)(Button_1.default, { onClick: goToPrevStep, children: "Back" }) }));
    };
    const goToNextStep = () => {
        const prevActiveIndex = activeIndex;
        const prevCompletedStep = completedStep;
        if (prevActiveIndex === 5) {
            return;
        }
        let newActiveIndex = prevActiveIndex + 1;
        if (!prevCompletedStep || (prevCompletedStep < prevActiveIndex)) {
            const newCompletedStep = prevActiveIndex;
            setCompletedStep(newCompletedStep);
        }
        if (newActiveIndex !== prevActiveIndex) {
            setActiveIndex(newActiveIndex);
        }
    };
    const renderNextButton = () => {
        if (activeIndex === 5) {
            return (0, jsx_runtime_1.jsx)(Box_1.default, { pt: { phone: 'm', tablet: 's' } });
        }
        return ((0, jsx_runtime_1.jsx)(Box_1.default, { mr: { phone: 's', tablet: 'm' }, mb: { phone: 's', tablet: 'm' }, pt: { phone: 's', tablet: 'm' }, children: (0, jsx_runtime_1.jsx)(Button_1.default, { onClick: goToNextStep, children: "Next" }) }));
    };
    const renderCurrentStep = () => {
        switch (activeIndex) {
            case 0:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(CMPWStep1_1.default, { sendUpdates: sendUpdates, guestsCanInviteOthers: guestsCanInviteOthers, transparency: transparency, visibility: visibility, name: name, setParentSendUpdates: setSendUpdates, setParentGuestsCanInviteOthers: setGuestsCanInviteOthers, setParentTransparency: setTransparency, setParentVisibility: setVisibility, setParentName: setName }), (0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [(0, jsx_runtime_1.jsx)(Box_1.default, {}), renderNextButton()] })] }));
            case 1:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(CMPWStep2_1.default, { useDefaultAlarms: useDefaultAlarms, alarms: alarms, setParentAlarms: setAlarms, setParentUseDefaultAlarms: setUseDefaultAlarms }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", style: { width: '100%' }, children: [renderPrevButton(), renderNextButton()] })] }));
            case 2:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(CMPWStep3_1.default, { isZoomAvailable: isZoomAvailable, isGoogleMeetAvailable: isGoogleMeetAvailable, zoomMeet: zoomMeet, googleMeet: googleMeet, enableConference: enableConference, setParentZoomMeet: setZoomMeet, setParentGoogleMeet: setGoogleMeet, setParentEnableConference: setEnableConference, setParentConferenceApp: setConferenceApp }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", style: { width: '100%' }, children: [renderPrevButton(), renderNextButton()] })] }));
            case 3:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(CMPWStep4_1.default, { isBufferTime: isBufferTime, beforeEventMinutes: beforeEventMinutes, afterEventMinutes: afterEventMinutes, setParentIsBufferTime: setIsBufferTime, setParentBeforeEventMinutes: setBeforeEventMinutes, setParentAfterEventMinutes: setAfterEventMinutes }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", style: { width: '100%' }, children: [renderPrevButton(), renderNextButton()] })] }));
            case 4:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(CMPWStep5_1.default, { anyoneCanAddSelf: anyoneCanAddSelf, guestsCanSeeOtherGuests: guestsCanSeeOtherGuests, primaryEmail: primaryEmail, lockAfter: lockAfter, setParentAnyoneCanAddSelf: setAnyoneCanAddSelf, setParentGuestsCanSeeOtherGuests: setGuestsCanSeeOtherGuests, setParentPrimaryEmail: setPrimaryEmail, setParentLockAfter: setLockAfter }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", style: { width: '100%' }, children: [renderPrevButton(), renderNextButton()] })] }));
            case 5:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, style: { width: '100%' }, p: { phone: 's', tablet: 'm' }, justifyContent: "center", alignItems: "center", minHeight: "65vh", maxHeight: "65vh", children: [(0, jsx_runtime_1.jsx)(Box_1.default, { p: { phone: 'm', tablet: 'l' }, children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "subheaderNormal", children: "Save Meeting Preferences via Chat" }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { pt: { phone: 'm', tablet: 'l' }, children: (0, jsx_runtime_1.jsx)(Button_1.default, { onClick: saveChatMeetingPreferences, children: "Save" }) })] }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", alignItems: "center", style: { width: '100%' }, children: [renderPrevButton(), renderNextButton(), (0, jsx_runtime_1.jsx)(Box_1.default, {})] })] }));
            default:
                return ((0, jsx_runtime_1.jsx)(Box_1.default, { justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsx)(RegularCard_1.default, { children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "header", children: "Oops... something went wrong" }) }) }));
        }
    };
    return ((0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, justifyContent: "center", alignItems: "center", height: "100%", style: { width: '100%' }, children: [(0, jsx_runtime_1.jsx)(Wizard_1.default, { items: [
                    {
                        index: 0,
                        label: 'Step 1',
                    },
                    {
                        index: 1,
                        label: 'Step 2',
                    },
                    {
                        index: 2,
                        label: 'Step 3',
                    },
                    {
                        index: 3,
                        label: 'Step 4',
                    },
                    {
                        index: 4,
                        label: 'Step 5',
                    },
                    {
                        index: 5,
                        label: 'Last Step',
                    },
                ], completed: completedStep, activeIndex: activeIndex }), renderCurrentStep()] }));
}
exports.default = UserChatMeetingPreferences;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlckNoYXRNZWV0aW5nUHJlZmVyZW5jZXMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJVc2VyQ2hhdE1lZXRpbmdQcmVmZXJlbmNlcy50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUF1Q0EsZ0RBcUNDOztBQTVFRCxpQ0FHYztBQUdkLDRDQUEyQztBQUUzQyxpRUFBd0M7QUFDeEMsbUVBQTBDO0FBRTFDLGdFQUF1QztBQUN2QyxnRUFBdUM7QUFDdkMsMEVBQWlEO0FBQ2pELG9EQUFpRDtBQUNqRCx3Q0FBdUM7QUFJdkMsbUVBQTJEO0FBQzNELDhEQUE0RTtBQUM1RSxnRkFBMkU7QUFDM0UsaUZBQW9FO0FBQ3BFLGdFQUFnSDtBQUNoSCwrQkFBaUM7QUFFakMsZ0RBQXVDO0FBRXZDLHdGQUErRDtBQUMvRCx3RkFBK0Q7QUFDL0Qsd0ZBQStEO0FBQy9ELHdGQUErRDtBQUMvRCx3RkFBZ0U7QUFDaEUsb0RBQXNCO0FBRXRCLHdFQUE4QztBQUM5Qyx5REFBcUQ7QUFDckQsOEVBQXFEO0FBRTlDLEtBQUssVUFBVSxrQkFBa0IsQ0FBQyxFQUFFLEdBQUcsRUFBRSxHQUFHLEVBQWlEO0lBQ2hHLDBGQUEwRjtJQUMxRixzQ0FBc0M7SUFDdEMseUVBQXlFO0lBQ3pFLDBCQUFlLENBQUMsSUFBSSxDQUFDLElBQUEsNkJBQWEsR0FBRSxDQUFDLENBQUE7SUFDckMsSUFBSSxPQUFPLENBQUE7SUFDWCxJQUFJLENBQUM7UUFDRCxPQUFPLEdBQUcsTUFBTSxpQkFBTyxDQUFDLFVBQVUsQ0FBQyxHQUFHLEVBQUUsR0FBRyxFQUFFO1lBQ3pDLDZCQUE2QixFQUFFLEtBQUs7Z0JBQ2hDLE9BQU8sRUFBRSxDQUFBO1lBQ2IsQ0FBQztTQUNKLENBQUMsQ0FBQTtJQUNOLENBQUM7SUFBQyxPQUFPLEdBQVEsRUFBRSxDQUFDO1FBQ2hCLElBQUksR0FBRyxDQUFDLElBQUksS0FBSyxpQkFBTyxDQUFDLEtBQUssQ0FBQyxpQkFBaUIsRUFBRSxDQUFDO1lBQy9D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QUMsUUFBUSxZQUM1Qyx1QkFBQyxxQkFBVyxjQUNSLHVCQUFDLGNBQUksSUFBQyxPQUFPLEVBQUMsUUFBUSw2Q0FFZixHQUNHLEdBQ1osQ0FDVCxDQUFBO1FBRVQsQ0FBQztJQUNMLENBQUMsQ0FBQTtJQUVELE9BQU8sQ0FDSCx3QkFBQyxhQUFHLElBQUMsSUFBSSxFQUFFLENBQUMsRUFBRSxjQUFjLEVBQUMsUUFBUSxFQUFDLFVBQVUsRUFBQyxRQUFRLEVBQUMsTUFBTSxFQUFDLE1BQU0sRUFBQyxLQUFLLEVBQUUsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLGFBQzVGLHVCQUFDLGdCQUFNLElBQ0gsS0FBSyxFQUFFO29CQUNIO3dCQUNJLEtBQUssRUFBRSxDQUFDO3dCQUNSLEtBQUssRUFBRSxRQUFRO3FCQUNsQjtvQkFDRDt3QkFDSSxLQUFLLEVBQUUsQ0FBQzt3QkFDUixLQUFLLEVBQUUsUUFBUTtxQkFDbEI7b0JBQ0Q7d0JBQ0ksS0FBSyxFQUFFLENBQUM7d0JBQ1IsS0FBSyxFQUFFLFFBQVE7cUJBQ2xCO29CQUNBO3dCQUNHLEtBQUssRUFBRSxDQUFDO3dCQUNSLEtBQUssRUFBRSxRQUFRO3FCQUNsQjtvQkFDQTt3QkFDRyxLQUFLLEVBQUUsQ0FBQzt3QkFDUixLQUFLLEVBQUUsUUFBUTtxQkFDbEI7b0JBQ0E7d0JBQ0csS0FBSyxFQUFFLENBQUM7d0JBQ1IsS0FBSyxFQUFFLFdBQVc7cUJBQ3JCO2lCQUNKLEVBRUQsU0FBUyxFQUFFLGFBQWEsRUFDeEIsV0FBVyxFQUFFLFdBQVcsR0FDMUIsRUFDRCxpQkFBaUIsRUFBRSxJQUNsQixDQUNULENBQUE7QUFDTCxDQUFDO0FBR0Qsa0JBQWUsMEJBQTBCLENBQUEiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgUmVhY3QsIHtcbiAgICB1c2VTdGF0ZSxcbiAgICB1c2VFZmZlY3QsXG59IGZyb20gJ3JlYWN0J1xuXG5pbXBvcnQgeyBBcG9sbG9DbGllbnQsIGdxbCwgTm9ybWFsaXplZENhY2hlT2JqZWN0IH0gZnJvbSAnQGFwb2xsby9jbGllbnQnXG5pbXBvcnQgeyB1c2VUb2FzdCB9IGZyb20gJ0BjaGFrcmEtdWkvcmVhY3QnXG5cbmltcG9ydCBCb3ggZnJvbSAnQGNvbXBvbmVudHMvY29tbW9uL0JveCdcbmltcG9ydCBUZXh0IGZyb20gJ0Bjb21wb25lbnRzL2NvbW1vbi9UZXh0J1xuXG5pbXBvcnQgQnV0dG9uIGZyb20gJ0Bjb21wb25lbnRzL0J1dHRvbidcbmltcG9ydCBXaXphcmQgZnJvbSAnQGNvbXBvbmVudHMvV2l6YXJkJ1xuaW1wb3J0IFJlZ3VsYXJDYXJkIGZyb20gJ0Bjb21wb25lbnRzL1JlZ3VsYXJDYXJkJ1xuaW1wb3J0IHsgdXNlQXBwQ29udGV4dCB9IGZyb20gJ0BsaWIvdXNlci1jb250ZXh0J1xuaW1wb3J0IHsgdXNlUm91dGVyIH0gZnJvbSAnbmV4dC9yb3V0ZXInXG5pbXBvcnQgeyBDb25mZXJlbmNlQXBwVHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL01lZXRpbmdBc3Npc3RUeXBlJ1xuaW1wb3J0IHsgVXNlckNvbnRhY3RJbmZvVHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL1VzZXJDb250YWN0SW5mb1R5cGUnXG5pbXBvcnQgeyBVc2VyVHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL1VzZXJUeXBlJ1xuaW1wb3J0IHsgem9vbUF2YWlsYWJsZSB9IGZyb20gJ0BsaWIvem9vbS96b29tTWVldGluZ0hlbHBlcidcbmltcG9ydCB7IGxpc3RVc2VyQ29udGFjdEluZm9zR2l2ZW5Vc2VySWQgfSBmcm9tICdAbGliL0NvbnRhY3QvQ29udGFjdEhlbHBlcidcbmltcG9ydCB7IGdvb2dsZU1lZXRBdmFpbGFibGUgfSBmcm9tICdAbGliL2NhbGVuZGFyTGliL2dvb2dsZUNhbGVuZGFySGVscGVyJ1xuaW1wb3J0IHsgZ2V0VXNlckdpdmVuSWQgfSBmcm9tICdAbGliL0Fzc2lzdC9Vc2VyTWVldGluZ0Fzc2lzdEhlbHBlcidcbmltcG9ydCB7IGdldENoYXRNZWV0aW5nUHJlZmVyZW5jZXMsIHVwc2VydENoYXRNZWV0aW5nUHJlZmVyZW5jZXNHaXZlblVzZXJJZCB9IGZyb20gJ0BsaWIvT25Cb2FyZC9PbkJvYXJkSGVscGVyMydcbmltcG9ydCB7IHY0IGFzIHV1aWQgfSBmcm9tICd1dWlkJ1xuaW1wb3J0IHsgQ2hhdE1lZXRpbmdQcmVmZXJlbmNlc1R5cGUgfSBmcm9tICdAbGliL2RhdGFUeXBlcy9DaGF0TWVldGluZ1ByZWZlcmVuY2VUeXBlJ1xuaW1wb3J0IHsgZGF5anMgfSBmcm9tICdAbGliL2RhdGUtdXRpbHMnXG5pbXBvcnQgeyBTZW5kVXBkYXRlc1R5cGUsIFRyYW5zcGFyZW5jeVR5cGUsIFZpc2liaWxpdHlUeXBlIH0gZnJvbSAnQGxpYi9jYWxlbmRhckxpYi90eXBlcydcbmltcG9ydCBDTVBXU3RlcDEgZnJvbSAnLi9DaGF0TWVldGluZ1ByZWZlcmVuY2VXaXphcmQvQ01QV1N0ZXAxJ1xuaW1wb3J0IENNUFdTdGVwMiBmcm9tICcuL0NoYXRNZWV0aW5nUHJlZmVyZW5jZVdpemFyZC9DTVBXU3RlcDInXG5pbXBvcnQgQ01QV1N0ZXAzIGZyb20gJy4vQ2hhdE1lZXRpbmdQcmVmZXJlbmNlV2l6YXJkL0NNUFdTdGVwMydcbmltcG9ydCBDTVBXU3RlcDQgZnJvbSAnLi9DaGF0TWVldGluZ1ByZWZlcmVuY2VXaXphcmQvQ01QV1N0ZXA0J1xuaW1wb3J0IENNUFdTdGVwNSBmcm9tICcuL0NoYXRNZWV0aW5nUHJlZmVyZW5jZVdpemFyZC9DTVBXU3RlcDUnO1xuaW1wb3J0IF8gZnJvbSAnbG9kYXNoJ1xuaW1wb3J0IHsgTmV4dEFwaVJlcXVlc3QsIE5leHRBcGlSZXNwb25zZSB9IGZyb20gJ25leHQnO1xuaW1wb3J0IHN1cGVydG9rZW5zTm9kZSBmcm9tICdzdXBlcnRva2Vucy1ub2RlJ1xuaW1wb3J0IHsgYmFja2VuZENvbmZpZyB9IGZyb20gJ0Bjb25maWcvYmFja2VuZENvbmZpZydcbmltcG9ydCBTZXNzaW9uIGZyb20gJ3N1cGVydG9rZW5zLW5vZGUvcmVjaXBlL3Nlc3Npb24nXG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRTZXJ2ZXJTaWRlUHJvcHMoeyByZXEsIHJlcyB9OiB7IHJlcTogTmV4dEFwaVJlcXVlc3QsIHJlczogTmV4dEFwaVJlc3BvbnNlIH0pIHtcbiAgICAvLyBOb3RpY2UgaG93IHRoZSBzZXJ2ZXIgdXNlcyBgQVBJYCBmcm9tIGB3aXRoU1NSQ29udGV4dGAsIGluc3RlYWQgb2YgdGhlIHRvcC1sZXZlbCBgQVBJYC5cbiAgICAvLyBjb25zdCBTU1IgPSB3aXRoU1NSQ29udGV4dCh7IHJlcSB9KVxuICAgIC8vIHRoaXMgcnVucyBvbiB0aGUgYmFja2VuZCwgc28gd2UgbXVzdCBjYWxsIGluaXQgb24gc3VwZXJ0b2tlbnMtbm9kZSBTREtcbiAgICBzdXBlcnRva2Vuc05vZGUuaW5pdChiYWNrZW5kQ29uZmlnKCkpXG4gICAgbGV0IHNlc3Npb25cbiAgICB0cnkge1xuICAgICAgICBzZXNzaW9uID0gYXdhaXQgU2Vzc2lvbi5nZXRTZXNzaW9uKHJlcSwgcmVzLCB7XG4gICAgICAgICAgICBvdmVycmlkZUdsb2JhbENsYWltVmFsaWRhdG9yczogYXN5bmMgZnVuY3Rpb24gKCkge1xuICAgICAgICAgICAgICAgIHJldHVybiBbXVxuICAgICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICB9IGNhdGNoIChlcnI6IGFueSkge1xuICAgICAgICBpZiAoZXJyLnR5cGUgPT09IFNlc3Npb24uRXJyb3IuVFJZX1JFRlJFU0hfVE9LRU4pIHtcbiAgICAgICAgICAgIHJldHVybiB7IHByb3BzOiB7IGZyb21TdXBlcnRva2VuczogJ25lZWRzLXJlZnJlc2gnIH0gfVxuICAgICAgICB9IGVsc2UgaWYgKGVyci50eXBlID09PSBTZXNzaW9uLkVycm9yLlVOQVVUSE9SSVNFRCkge1xuICAgICAgICAgICAgLy8gdGhpcyB3aWxsIGZvcmNlIHRoZSBmcm9udGVuZCB0byB0cnkgYW5kIHJlZnJlc2ggd2hpY2ggd2lsbCBmYWlsXG4gICAgICAgICAgICAvLyBjbGVhcmluZyBhbGwgY29va2llcyBhbmQgcmVkaXJlY3RpbmcgdGhlIHVzZXIgdG8gdGhlIGxvZ2luIHNjcmVlbi5cbiAgICAgICAgICAgIHJldHVybiB7IHByb3BzOiB7IGZyb21TdXBlcnRva2VuczogJ25lZWRzLXJlZnJlc2gnIH0gfVxuICAgICAgICB9XG4gICAgICAgIHRocm93IGVyclxuICAgIH1cblxuICAgIGlmICghc2Vzc2lvbj8uZ2V0VXNlcklkKCkpIHtcbiAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICAgIHJlZGlyZWN0OiB7XG4gICAgICAgICAgICAgICAgZGVzdGluYXRpb246ICcvVXNlci9Mb2dpbi9Vc2VyTG9naW4nLFxuICAgICAgICAgICAgICAgIHBlcm1hbmVudDogZmFsc2UsXG4gICAgICAgICAgICB9LFxuICAgICAgICB9XG4gICAgfVxuXG4gICAgcmV0dXJuIHtcbiAgICAgICAgcHJvcHM6IHtcbiAgICAgICAgc3ViOiBzZXNzaW9uLmdldFVzZXJJZCgpLFxuICAgICAgICB9XG4gICAgfVxufVxuXG5mdW5jdGlvbiBVc2VyQ2hhdE1lZXRpbmdQcmVmZXJlbmNlcygpIHtcbiAgICBjb25zdCBbc2VuZFVwZGF0ZXMsIHNldFNlbmRVcGRhdGVzXSA9IHVzZVN0YXRlPFNlbmRVcGRhdGVzVHlwZT4oJ2FsbCcpXG4gICAgY29uc3QgW2d1ZXN0c0Nhbkludml0ZU90aGVycywgc2V0R3Vlc3RzQ2FuSW52aXRlT3RoZXJzXSA9IHVzZVN0YXRlPGJvb2xlYW4+KHRydWUpXG4gICAgY29uc3QgW3RyYW5zcGFyZW5jeSwgc2V0VHJhbnNwYXJlbmN5XSA9IHVzZVN0YXRlPFRyYW5zcGFyZW5jeVR5cGU+KCdvcGFxdWUnKVxuICAgIGNvbnN0IFt2aXNpYmlsaXR5LCBzZXRWaXNpYmlsaXR5XSA9IHVzZVN0YXRlPFZpc2liaWxpdHlUeXBlPignZGVmYXVsdCcpXG4gICAgY29uc3QgW3VzZURlZmF1bHRBbGFybXMsIHNldFVzZURlZmF1bHRBbGFybXNdID0gdXNlU3RhdGU8Ym9vbGVhbj4odHJ1ZSlcbiAgICBjb25zdCBbYWxhcm1zLCBzZXRBbGFybXNdID0gdXNlU3RhdGU8bnVtYmVyW10+KFtdKVxuICAgIGNvbnN0IFtkdXJhdGlvbiwgc2V0RHVyYXRpb25dID0gdXNlU3RhdGU8bnVtYmVyPigzMClcbiAgICBjb25zdCBbZW5hYmxlQ29uZmVyZW5jZSwgc2V0RW5hYmxlQ29uZmVyZW5jZV0gPSB1c2VTdGF0ZTxib29sZWFuPihmYWxzZSlcbiAgICBjb25zdCBbY29uZmVyZW5jZUFwcCwgc2V0Q29uZmVyZW5jZUFwcF0gPSB1c2VTdGF0ZTxDb25mZXJlbmNlQXBwVHlwZSB8IG51bGwgfCB1bmRlZmluZWQ+KCdnb29nbGUnKVxuICAgIGNvbnN0IFt6b29tTWVldCwgc2V0Wm9vbU1lZXRdID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gICAgY29uc3QgW2dvb2dsZU1lZXQsIHNldEdvb2dsZU1lZXRdID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gICAgY29uc3QgW2lzQnVmZmVyVGltZSwgc2V0SXNCdWZmZXJUaW1lXSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKVxuICAgIGNvbnN0IFtiZWZvcmVFdmVudE1pbnV0ZXMsIHNldEJlZm9yZUV2ZW50TWludXRlc10gPSB1c2VTdGF0ZTxudW1iZXI+KDApXG4gICAgY29uc3QgW2FmdGVyRXZlbnRNaW51dGVzLCBzZXRBZnRlckV2ZW50TWludXRlc10gPSB1c2VTdGF0ZTxudW1iZXI+KDApXG4gICAgY29uc3QgW2FueW9uZUNhbkFkZFNlbGYsIHNldEFueW9uZUNhbkFkZFNlbGZdID0gdXNlU3RhdGU8Ym9vbGVhbj4odHJ1ZSlcbiAgICBjb25zdCBbZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsIHNldEd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXSA9IHVzZVN0YXRlPGJvb2xlYW4+KHRydWUpXG4gICAgY29uc3QgW25hbWUsIHNldE5hbWVdID0gdXNlU3RhdGU8c3RyaW5nPignJylcbiAgICBjb25zdCBbdXNlciwgc2V0VXNlcl0gPSB1c2VTdGF0ZTxVc2VyVHlwZT4oKVxuICAgIGNvbnN0IFtpc1pvb21BdmFpbGFibGUsIHNldElzWm9vbUF2YWlsYWJsZV0gPSB1c2VTdGF0ZTxib29sZWFuPihmYWxzZSlcbiAgICBjb25zdCBbaXNHb29nbGVNZWV0QXZhaWxhYmxlLCBzZXRJc0dvb2dsZU1lZXRBdmFpbGFibGVdID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gICAgY29uc3QgW3ByaW1hcnlFbWFpbCwgc2V0UHJpbWFyeUVtYWlsXSA9IHVzZVN0YXRlPHN0cmluZz4oJycpXG4gICAgY29uc3QgW2lkLCBzZXRJZF0gPSB1c2VTdGF0ZTxzdHJpbmc+KCcnKVxuICAgIGNvbnN0IFthY3RpdmVJbmRleCwgc2V0QWN0aXZlSW5kZXhdID0gdXNlU3RhdGU8bnVtYmVyPigwKVxuICAgIGNvbnN0IFtjb21wbGV0ZWRTdGVwLCBzZXRDb21wbGV0ZWRTdGVwXSA9IHVzZVN0YXRlPG51bWJlciB8IHVuZGVmaW5lZD4oKVxuICAgIGNvbnN0IFtjaGF0TWVldGluZ1ByZWZlcmVuY2VzLCBzZXRDaGF0TWVldGluZ1ByZWZlcmVuY2VzXSA9IHVzZVN0YXRlPENoYXRNZWV0aW5nUHJlZmVyZW5jZXNUeXBlPigpXG4gICAgY29uc3QgW2xvY2tBZnRlciwgc2V0TG9ja0FmdGVyXSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKVxuXG5cbiAgICBjb25zdCB7IHN1YiwgY2xpZW50IH0gPSB1c2VBcHBDb250ZXh0KClcbiAgICBjb25zdCB1c2VySWQgPSBzdWJcbiAgICBjb25zb2xlLmxvZyhzdWIsICcgc3ViIGluc2lkZSB1c2VyY2hhdG1lZXRpbmdwcmVmZXJlbmNlcycpXG4gICAgY29uc3Qgcm91dGVyID0gdXNlUm91dGVyKClcbiAgICBjb25zdCB0b2FzdCA9IHVzZVRvYXN0KClcblxuXG4gICAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICAgICAgKGFzeW5jICgpID0+IHtcbiAgICAgICAgaWYgKCF1c2VySWQgfHwgIWNsaWVudCkge1xuICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cbiAgICAgICAgY29uc3QgaXNBdmFpbGFibGUgPSBhd2FpdCB6b29tQXZhaWxhYmxlKGNsaWVudCwgdXNlcklkKVxuICAgICAgICBpZiAoaXNBdmFpbGFibGUpIHtcbiAgICAgICAgICAgIHNldElzWm9vbUF2YWlsYWJsZSh0cnVlKVxuICAgICAgICB9XG4gICAgICAgIH0pKClcbiAgICB9LCBbY2xpZW50LCB1c2VySWRdKVxuXG4gICAgLy8gY2hlY2sgaWYgZ29vZ2xlIGF2YWlsYWJsZVxuICAgIHVzZUVmZmVjdCgoKSA9PiB7XG4gICAgICAgIChhc3luYyAoKSA9PiB7XG4gICAgICAgIGlmICghdXNlcklkIHx8ICFjbGllbnQpIHtcbiAgICAgICAgICAgIHJldHVyblxuICAgICAgICB9XG4gICAgICAgIGNvbnN0IGlzQXZhaWxhYmxlID0gYXdhaXQgZ29vZ2xlTWVldEF2YWlsYWJsZShjbGllbnQsIHVzZXJJZClcbiAgICAgICAgaWYgKGlzQXZhaWxhYmxlKSB7XG4gICAgICAgICAgICBzZXRJc0dvb2dsZU1lZXRBdmFpbGFibGUoaXNBdmFpbGFibGUpXG4gICAgICAgIH1cbiAgICAgICAgfSkoKVxuICAgIH0sIFtjbGllbnQsIHVzZXJJZF0pXG5cbiAgICAvLyBnZXQgdXNlciBhbmQgdXBkYXRlIGlmIG5lY2Vzc2FyeVxuICAgIFxuICAgIC8vIGdldCBjaGF0IG1lZXRpbmcgcHJlZmVyZW5jZXNcbiAgICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgICAgICAoYXN5bmMgKCkgPT4ge1xuICAgICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgICAgICBpZiAoIXVzZXJJZCkge1xuICAgICAgICAgICAgICAgICAgICByZXR1cm5cbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICBjb25zdCBuZXdJZCA9IHV1aWQoKVxuXG4gICAgICAgICAgICAgICAgbGV0IG9sZE9yTmV3Q2hhdE1lZXRpbmdQcmVmZXJlbmNlczogQ2hhdE1lZXRpbmdQcmVmZXJlbmNlc1R5cGUgPSBhd2FpdCBnZXRDaGF0TWVldGluZ1ByZWZlcmVuY2VzKGNsaWVudCwgdXNlcklkKVxuXG4gICAgICAgICAgICAgICAgaWYgKCFvbGRPck5ld0NoYXRNZWV0aW5nUHJlZmVyZW5jZXM/LmlkKSB7XG4gICAgICAgICAgICAgICAgICAgIG9sZE9yTmV3Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcyA9IHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGlkOiBuZXdJZCxcbiAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgICAgICAgICAgICAgIHRpbWV6b25lOiBkYXlqcy50ei5ndWVzcygpLFxuICAgICAgICAgICAgICAgICAgICAgICAgZW5hYmxlQ29uZmVyZW5jZTogdHJ1ZSxcbiAgICAgICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgXG4gICAgICAgICAgICAgICAgICAgIGF3YWl0IHVwc2VydENoYXRNZWV0aW5nUHJlZmVyZW5jZXNHaXZlblVzZXJJZChjbGllbnQsIG9sZE9yTmV3Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcylcbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICBpZiAob2xkT3JOZXdDaGF0TWVldGluZ1ByZWZlcmVuY2VzPy5zZW5kVXBkYXRlcykge1xuICAgICAgICAgICAgICAgICAgICBzZXRTZW5kVXBkYXRlcyhvbGRPck5ld0NoYXRNZWV0aW5nUHJlZmVyZW5jZXM/LnNlbmRVcGRhdGVzKVxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIGlmIChvbGRPck5ld0NoYXRNZWV0aW5nUHJlZmVyZW5jZXM/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICAgICAgICAgICAgICAgIHNldEd1ZXN0c0Nhbkludml0ZU90aGVycyhvbGRPck5ld0NoYXRNZWV0aW5nUHJlZmVyZW5jZXM/Lmd1ZXN0c0Nhbkludml0ZU90aGVycylcbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICBpZiAob2xkT3JOZXdDaGF0TWVldGluZ1ByZWZlcmVuY2VzPy50cmFuc3BhcmVuY3kpIHtcbiAgICAgICAgICAgICAgICAgICAgc2V0VHJhbnNwYXJlbmN5KG9sZE9yTmV3Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcz8udHJhbnNwYXJlbmN5KVxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIGlmIChvbGRPck5ld0NoYXRNZWV0aW5nUHJlZmVyZW5jZXM/LnZpc2liaWxpdHkpIHtcbiAgICAgICAgICAgICAgICAgICAgc2V0VmlzaWJpbGl0eShvbGRPck5ld0NoYXRNZWV0aW5nUHJlZmVyZW5jZXM/LnZpc2liaWxpdHkpXG4gICAgICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICAgICAgaWYgKG9sZE9yTmV3Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcz8udXNlRGVmYXVsdEFsYXJtcyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICAgICAgICAgICAgICAgIHNldFVzZURlZmF1bHRBbGFybXMob2xkT3JOZXdDaGF0TWVldGluZ1ByZWZlcmVuY2VzPy51c2VEZWZhdWx0QWxhcm1zKVxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIGlmIChvbGRPck5ld0NoYXRNZWV0aW5nUHJlZmVyZW5jZXM/LnJlbWluZGVycykge1xuICAgICAgICAgICAgICAgICAgICBzZXRBbGFybXMob2xkT3JOZXdDaGF0TWVldGluZ1ByZWZlcmVuY2VzPy5yZW1pbmRlcnMpXG4gICAgICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICAgICAgaWYgKG9sZE9yTmV3Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcz8uZHVyYXRpb24pIHtcbiAgICAgICAgICAgICAgICAgICAgc2V0RHVyYXRpb24ob2xkT3JOZXdDaGF0TWVldGluZ1ByZWZlcmVuY2VzPy5kdXJhdGlvbilcbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICBpZiAob2xkT3JOZXdDaGF0TWVldGluZ1ByZWZlcmVuY2VzPy5lbmFibGVDb25mZXJlbmNlICE9PSB1bmRlZmluZWQpIHtcbiAgICAgICAgICAgICAgICAgICAgc2V0RW5hYmxlQ29uZmVyZW5jZShvbGRPck5ld0NoYXRNZWV0aW5nUHJlZmVyZW5jZXM/LmVuYWJsZUNvbmZlcmVuY2UpXG4gICAgICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICAgICAgaWYgKG9sZE9yTmV3Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcz8uY29uZmVyZW5jZUFwcCkge1xuICAgICAgICAgICAgICAgICAgICBzZXRDb25mZXJlbmNlQXBwKG9sZE9yTmV3Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcz8uY29uZmVyZW5jZUFwcClcbiAgICAgICAgICAgICAgICAgICAgaWYgKG9sZE9yTmV3Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcz8uY29uZmVyZW5jZUFwcCA9PT0gJ3pvb20nKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICBzZXRab29tTWVldCh0cnVlKVxuICAgICAgICAgICAgICAgICAgICB9IGVsc2UgaWYgKG9sZE9yTmV3Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcz8uY29uZmVyZW5jZUFwcCA9PT0gJ2dvb2dsZScpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHNldEdvb2dsZU1lZXQodHJ1ZSlcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIGlmIChvbGRPck5ld0NoYXRNZWV0aW5nUHJlZmVyZW5jZXM/LmJ1ZmZlclRpbWUpIHtcbiAgICAgICAgICAgICAgICAgICAgc2V0SXNCdWZmZXJUaW1lKHRydWUpXG5cbiAgICAgICAgICAgICAgICAgICAgaWYgKG9sZE9yTmV3Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcz8uYnVmZmVyVGltZT8uYmVmb3JlRXZlbnQpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHNldEJlZm9yZUV2ZW50TWludXRlcyhvbGRPck5ld0NoYXRNZWV0aW5nUHJlZmVyZW5jZXM/LmJ1ZmZlclRpbWU/LmJlZm9yZUV2ZW50KVxuICAgICAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICAgICAgaWYgKG9sZE9yTmV3Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcz8uYnVmZmVyVGltZT8uYWZ0ZXJFdmVudCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgc2V0QWZ0ZXJFdmVudE1pbnV0ZXMob2xkT3JOZXdDaGF0TWVldGluZ1ByZWZlcmVuY2VzPy5idWZmZXJUaW1lPy5hZnRlckV2ZW50KVxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICAgICAgaWYgKG9sZE9yTmV3Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcz8uYW55b25lQ2FuQWRkU2VsZiAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICAgICAgICAgICAgICAgIHNldEFueW9uZUNhbkFkZFNlbGYob2xkT3JOZXdDaGF0TWVldGluZ1ByZWZlcmVuY2VzPy5hbnlvbmVDYW5BZGRTZWxmKVxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIGlmIChvbGRPck5ld0NoYXRNZWV0aW5nUHJlZmVyZW5jZXM/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzICE9PSB1bmRlZmluZWQpIHtcbiAgICAgICAgICAgICAgICAgICAgc2V0R3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMob2xkT3JOZXdDaGF0TWVldGluZ1ByZWZlcmVuY2VzPy5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cylcbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICBjb25zdCBvbGRVc2VyID0gYXdhaXQgZ2V0VXNlckdpdmVuSWQoY2xpZW50LCB1c2VySWQpXG4gICAgICAgICAgICAgICAgc2V0VXNlcihvbGRVc2VyKVxuXG4gICAgICAgICAgICAgICAgaWYgKG9sZE9yTmV3Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcz8ubmFtZSkge1xuICAgICAgICAgICAgICAgICAgICBzZXROYW1lKG9sZE9yTmV3Q2hhdE1lZXRpbmdQcmVmZXJlbmNlcz8ubmFtZSlcbiAgICAgICAgICAgICAgICB9IGVsc2UgaWYgKG9sZFVzZXI/Lm5hbWUpIHtcbiAgICAgICAgICAgICAgICAgICAgc2V0TmFtZShvbGRVc2VyPy5uYW1lKVxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIGlmIChvbGRPck5ld0NoYXRNZWV0aW5nUHJlZmVyZW5jZXM/LnByaW1hcnlFbWFpbCkge1xuICAgICAgICAgICAgICAgICAgICBzZXRQcmltYXJ5RW1haWwob2xkT3JOZXdDaGF0TWVldGluZ1ByZWZlcmVuY2VzPy5wcmltYXJ5RW1haWwpXG4gICAgICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICAgICAgY29uc3Qgb2xkRGJJbmZvSXRlbXMgPSBhd2FpdCBsaXN0VXNlckNvbnRhY3RJbmZvc0dpdmVuVXNlcklkKGNsaWVudCwgdXNlcklkKVxuICAgICAgICAgICAgICAgICAgICBpZiAob2xkRGJJbmZvSXRlbXMgJiYgb2xkRGJJbmZvSXRlbXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvbnN0IGVtYWlsID0gb2xkRGJJbmZvSXRlbXM/LmZpbmQoaSA9PiAoKCEhaT8ucHJpbWFyeSAmJiAoaT8udHlwZSA9PT0gJ2VtYWlsJykpKSk/LmlkXG4gICAgICAgICAgICAgICAgICAgICAgICBzZXRQcmltYXJ5RW1haWwoZW1haWwpXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICBpZiAob2xkT3JOZXdDaGF0TWVldGluZ1ByZWZlcmVuY2VzPy5pZCkge1xuICAgICAgICAgICAgICAgICAgICBzZXRJZChvbGRPck5ld0NoYXRNZWV0aW5nUHJlZmVyZW5jZXM/LmlkKVxuICAgICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgICAgIHNldElkKG5ld0lkKVxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIGlmIChvbGRPck5ld0NoYXRNZWV0aW5nUHJlZmVyZW5jZXM/LmxvY2tBZnRlciAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICAgICAgICAgICAgICAgIHNldExvY2tBZnRlcihvbGRPck5ld0NoYXRNZWV0aW5nUHJlZmVyZW5jZXM/LmxvY2tBZnRlciA/PyB0cnVlKVxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIHNldENoYXRNZWV0aW5nUHJlZmVyZW5jZXMob2xkT3JOZXdDaGF0TWVldGluZ1ByZWZlcmVuY2VzKVxuXG4gICAgICAgICAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgICAgICAgICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGNoYXQgbWVldGluZyBwcmVmZXJlbmNlcycpXG4gICAgICAgICAgICB9XG4gICAgICAgIH0pKClcbiAgICB9LCBbY2xpZW50LCB1c2VySWRdKVxuXG4gICAgY29uc3Qgc2F2ZUNoYXRNZWV0aW5nUHJlZmVyZW5jZXMgPSBhc3luYyAoKSA9PiB7XG4gICAgICAgIHRyeSB7XG4gICAgICAgICAgICBjb25zdCB1cGRhdGVkQ2hhdE1lZXRpbmdQcmVmZXJlbmNlczogQ2hhdE1lZXRpbmdQcmVmZXJlbmNlc1R5cGUgPSB7XG4gICAgICAgICAgICAgICAgLi4uY2hhdE1lZXRpbmdQcmVmZXJlbmNlcyxcbiAgICAgICAgICAgICAgICBpZCxcbiAgICAgICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICAgICAgc2VuZFVwZGF0ZXMsXG4gICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgICAgICAgICAgIHRyYW5zcGFyZW5jeSxcbiAgICAgICAgICAgICAgICB2aXNpYmlsaXR5LFxuICAgICAgICAgICAgICAgIHVzZURlZmF1bHRBbGFybXMsXG4gICAgICAgICAgICAgICAgcmVtaW5kZXJzOiBhbGFybXMsXG4gICAgICAgICAgICAgICAgZHVyYXRpb24sXG4gICAgICAgICAgICAgICAgZW5hYmxlQ29uZmVyZW5jZSxcbiAgICAgICAgICAgICAgICBjb25mZXJlbmNlQXBwLFxuICAgICAgICAgICAgICAgIGFueW9uZUNhbkFkZFNlbGYsXG4gICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgICAgICAgICAgICAgbmFtZSxcbiAgICAgICAgICAgICAgICBwcmltYXJ5RW1haWwsXG4gICAgICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBpZiAoaXNCdWZmZXJUaW1lKSB7XG4gICAgICAgICAgICAgICAgdXBkYXRlZENoYXRNZWV0aW5nUHJlZmVyZW5jZXMuYnVmZmVyVGltZSA9IHtcbiAgICAgICAgICAgICAgICAgICAgYmVmb3JlRXZlbnQ6IGJlZm9yZUV2ZW50TWludXRlcyxcbiAgICAgICAgICAgICAgICAgICAgYWZ0ZXJFdmVudDogYWZ0ZXJFdmVudE1pbnV0ZXMsXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBhd2FpdCB1cHNlcnRDaGF0TWVldGluZ1ByZWZlcmVuY2VzR2l2ZW5Vc2VySWQoY2xpZW50LCBfLm9taXQodXBkYXRlZENoYXRNZWV0aW5nUHJlZmVyZW5jZXMsIFsnX190eXBlbmFtZSddKSBhcyBDaGF0TWVldGluZ1ByZWZlcmVuY2VzVHlwZSlcbiAgICAgICAgICAgIFxuICAgICAgICAgICAgdG9hc3Qoe1xuICAgICAgICAgICAgICAgIHN0YXR1czogJ3N1Y2Nlc3MnLFxuICAgICAgICAgICAgICAgIHRpdGxlOiAnTWVldGluZyBQcmVmZXJlbmNlcyBmb3IgY2hhdCBzYXZlZCcsXG4gICAgICAgICAgICAgICAgZGVzY3JpcHRpb246ICdNZWV0aW5nIFByZWZlcmVuY2VzdCBzYXZlZCBzdWNjZXNzZnVsbHknLFxuICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICAgICAgICB9KVxuICAgICAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBzYXZlIGNoYXQgbWVldGluZyBwcmVmZXJlbmNlcycpXG4gICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgc3RhdHVzOiAnZXJyb3InLFxuICAgICAgICAgICAgICAgIHRpdGxlOiAnT29wcy4uLicsXG4gICAgICAgICAgICAgICAgZGVzY3JpcHRpb246ICdMb29rcyBsaWtlIHNvbWV0aGluZyB3ZW50IHdyb25nJyxcbiAgICAgICAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICAgICAgfSlcbiAgICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IGdvVG9QcmV2U3RlcCA9ICgpID0+IHtcbiAgICAgICAgY29uc3QgcHJldkFjdGl2ZUluZGV4ID0gYWN0aXZlSW5kZXhcbiAgICAgICAgY29uc3QgbmV3QWN0aXZlSW5kZXggPSBwcmV2QWN0aXZlSW5kZXggPT09IDAgPyAwIDogcHJldkFjdGl2ZUluZGV4IC0gMVxuICAgICAgICBzZXRBY3RpdmVJbmRleChuZXdBY3RpdmVJbmRleClcbiAgICB9XG5cbiAgICBjb25zdCByZW5kZXJQcmV2QnV0dG9uID0gKCkgPT4ge1xuICAgICAgICBpZiAoYWN0aXZlSW5kZXggPT09IDApIHtcbiAgICAgICAgICAgIHJldHVybiA8Qm94IG1sPXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19Lz5cbiAgICAgICAgfVxuXG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICA8Qm94IG1sPXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19PlxuICAgICAgICAgICAgICAgIDxCdXR0b24gb25DbGljaz17Z29Ub1ByZXZTdGVwfT5cbiAgICAgICAgICAgICAgICAgICAgQmFja1xuICAgICAgICAgICAgICAgIDwvQnV0dG9uPlxuICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgIClcbiAgICB9XG5cbiAgICBjb25zdCBnb1RvTmV4dFN0ZXAgPSAoKSA9PiB7XG4gICAgICAgIGNvbnN0IHByZXZBY3RpdmVJbmRleCA9IGFjdGl2ZUluZGV4XG4gICAgICAgIGNvbnN0IHByZXZDb21wbGV0ZWRTdGVwID0gY29tcGxldGVkU3RlcFxuICAgIFxuICAgICAgICBpZiAocHJldkFjdGl2ZUluZGV4ID09PSA1KSB7XG4gICAgICAgICAgICByZXR1cm5cbiAgICAgICAgfVxuICAgIFxuICAgICAgICBsZXQgbmV3QWN0aXZlSW5kZXggPSBwcmV2QWN0aXZlSW5kZXggKyAxXG4gICAgXG4gICAgICAgIGlmICghcHJldkNvbXBsZXRlZFN0ZXAgfHwgKHByZXZDb21wbGV0ZWRTdGVwIDwgcHJldkFjdGl2ZUluZGV4KSkge1xuICAgICAgICAgICAgY29uc3QgbmV3Q29tcGxldGVkU3RlcCA9IHByZXZBY3RpdmVJbmRleFxuICAgICAgICAgICAgc2V0Q29tcGxldGVkU3RlcChuZXdDb21wbGV0ZWRTdGVwKVxuICAgICAgICB9XG4gICAgXG4gICAgICAgIGlmIChuZXdBY3RpdmVJbmRleCAhPT0gcHJldkFjdGl2ZUluZGV4KSB7XG4gICAgICAgICAgc2V0QWN0aXZlSW5kZXgobmV3QWN0aXZlSW5kZXgpXG4gICAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCByZW5kZXJOZXh0QnV0dG9uID0gKCkgPT4ge1xuICAgICAgICBpZiAoYWN0aXZlSW5kZXggPT09IDUpIHtcbiAgICAgICAgICByZXR1cm4gPEJveCBwdD17eyBwaG9uZTogJ20nLCB0YWJsZXQ6ICdzJyB9fS8+XG4gICAgICAgIH1cblxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgIDxCb3ggbXI9e3sgcGhvbmU6ICdzJywgdGFibGV0OiAnbScgfX0gbWI9e3sgcGhvbmU6ICdzJywgdGFibGV0OiAnbScgfX0gcHQ9e3sgcGhvbmU6ICdzJywgdGFibGV0OiAnbSd9fT5cbiAgICAgICAgICAgIDxCdXR0b24gb25DbGljaz17Z29Ub05leHRTdGVwfT5cbiAgICAgICAgICAgICAgTmV4dFxuICAgICAgICAgICAgPC9CdXR0b24+XG4gICAgICAgICAgPC9Cb3g+XG4gICAgICAgIClcbiAgICB9XG5cbiAgICBjb25zdCByZW5kZXJDdXJyZW50U3RlcCA9ICgpID0+IHtcblxuICAgICAgICBzd2l0Y2goYWN0aXZlSW5kZXgpIHtcbiAgICAgICAgICAgIGNhc2UgMDpcbiAgICAgICAgICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgICAgICAgICA8Qm94IHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0gZmxleD17MX0gYWxpZ25JdGVtcz1cImNlbnRlclwiIGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICA8Q01QV1N0ZXAxXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc2VuZFVwZGF0ZXM9e3NlbmRVcGRhdGVzfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVycz17Z3Vlc3RzQ2FuSW52aXRlT3RoZXJzfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHRyYW5zcGFyZW5jeT17dHJhbnNwYXJlbmN5fVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHZpc2liaWxpdHk9e3Zpc2liaWxpdHl9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgbmFtZT17bmFtZX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzZXRQYXJlbnRTZW5kVXBkYXRlcz17c2V0U2VuZFVwZGF0ZXN9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc2V0UGFyZW50R3Vlc3RzQ2FuSW52aXRlT3RoZXJzPXtzZXRHdWVzdHNDYW5JbnZpdGVPdGhlcnN9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc2V0UGFyZW50VHJhbnNwYXJlbmN5PXtzZXRUcmFuc3BhcmVuY3l9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc2V0UGFyZW50VmlzaWJpbGl0eT17c2V0VmlzaWJpbGl0eX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzZXRQYXJlbnROYW1lPXtzZXROYW1lfVxuICAgICAgICAgICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICAgICAgICAgIDxCb3ggc3R5bGU9e3sgd2lkdGg6ICcxMDAlJyB9fSBmbGV4RGlyZWN0aW9uPVwicm93XCIganVzdGlmeUNvbnRlbnQ9XCJzcGFjZS1iZXR3ZWVuXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxCb3ggLz5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB7cmVuZGVyTmV4dEJ1dHRvbigpfVxuICAgICAgICAgICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgIClcbiAgICAgICAgICAgIFxuICAgICAgICAgICAgY2FzZSAxOlxuICAgICAgICAgICAgICAgIHJldHVybiAoXG4gICAgICAgICAgICAgICAgICAgIDxCb3ggc3R5bGU9e3sgd2lkdGg6ICcxMDAlJyB9fSBmbGV4PXsxfSBhbGlnbkl0ZW1zPVwiY2VudGVyXCIganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgICAgICAgICAgICAgIDxDTVBXU3RlcDJcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zPXt1c2VEZWZhdWx0QWxhcm1zfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGFsYXJtcz17YWxhcm1zfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNldFBhcmVudEFsYXJtcz17c2V0QWxhcm1zfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNldFBhcmVudFVzZURlZmF1bHRBbGFybXM9e3NldFVzZURlZmF1bHRBbGFybXN9XG4gICAgICAgICAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgICAgICAgICAgPEJveCBmbGV4RGlyZWN0aW9uPVwicm93XCIganVzdGlmeUNvbnRlbnQ9XCJzcGFjZS1iZXR3ZWVuXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiICBzdHlsZT17eyB3aWR0aDogJzEwMCUnfX0+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAge3JlbmRlclByZXZCdXR0b24oKX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB7cmVuZGVyTmV4dEJ1dHRvbigpfVxuICAgICAgICAgICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgIClcbiAgICAgICAgICAgIGNhc2UgMjpcbiAgICAgICAgICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgICAgICAgICA8Qm94IHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0gZmxleD17MX0gYWxpZ25JdGVtcz1cImNlbnRlclwiIGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICA8Q01QV1N0ZXAzXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgaXNab29tQXZhaWxhYmxlPXtpc1pvb21BdmFpbGFibGV9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgaXNHb29nbGVNZWV0QXZhaWxhYmxlPXtpc0dvb2dsZU1lZXRBdmFpbGFibGV9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgem9vbU1lZXQ9e3pvb21NZWV0fVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGdvb2dsZU1lZXQ9e2dvb2dsZU1lZXR9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZW5hYmxlQ29uZmVyZW5jZT17ZW5hYmxlQ29uZmVyZW5jZX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzZXRQYXJlbnRab29tTWVldD17c2V0Wm9vbU1lZXR9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc2V0UGFyZW50R29vZ2xlTWVldD17c2V0R29vZ2xlTWVldH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzZXRQYXJlbnRFbmFibGVDb25mZXJlbmNlPXtzZXRFbmFibGVDb25mZXJlbmNlfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNldFBhcmVudENvbmZlcmVuY2VBcHA9e3NldENvbmZlcmVuY2VBcHB9XG4gICAgICAgICAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgICAgICAgICAgPEJveCBmbGV4RGlyZWN0aW9uPVwicm93XCIganVzdGlmeUNvbnRlbnQ9XCJzcGFjZS1iZXR3ZWVuXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiICBzdHlsZT17eyB3aWR0aDogJzEwMCUnfX0+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAge3JlbmRlclByZXZCdXR0b24oKX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB7cmVuZGVyTmV4dEJ1dHRvbigpfVxuICAgICAgICAgICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgIClcbiAgICAgICAgICAgIGNhc2UgMzpcbiAgICAgICAgICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgICAgICAgICA8Qm94IHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0gZmxleD17MX0gYWxpZ25JdGVtcz1cImNlbnRlclwiIGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICA8Q01QV1N0ZXA0XG4gICAgICAgICAgICAgICAgICAgICAgICAgICBpc0J1ZmZlclRpbWU9e2lzQnVmZmVyVGltZX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgIGJlZm9yZUV2ZW50TWludXRlcz17YmVmb3JlRXZlbnRNaW51dGVzfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgYWZ0ZXJFdmVudE1pbnV0ZXM9e2FmdGVyRXZlbnRNaW51dGVzfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgc2V0UGFyZW50SXNCdWZmZXJUaW1lPXtzZXRJc0J1ZmZlclRpbWV9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICBzZXRQYXJlbnRCZWZvcmVFdmVudE1pbnV0ZXM9e3NldEJlZm9yZUV2ZW50TWludXRlc31cbiAgICAgICAgICAgICAgICAgICAgICAgICAgIHNldFBhcmVudEFmdGVyRXZlbnRNaW51dGVzPXtzZXRBZnRlckV2ZW50TWludXRlc31cbiAgICAgICAgICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICAgICAgICAgICAgICA8Qm94IGZsZXhEaXJlY3Rpb249XCJyb3dcIiBqdXN0aWZ5Q29udGVudD1cInNwYWNlLWJldHdlZW5cIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCIgIHN0eWxlPXt7IHdpZHRoOiAnMTAwJSd9fT5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB7cmVuZGVyUHJldkJ1dHRvbigpfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHtyZW5kZXJOZXh0QnV0dG9uKCl9XG4gICAgICAgICAgICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgKVxuICAgICAgICAgICAgXG4gICAgICAgICAgICBjYXNlIDQ6XG4gICAgICAgICAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgICAgICAgICAgPEJveCBzdHlsZT17eyB3aWR0aDogJzEwMCUnIH19IGZsZXg9ezF9IGFsaWduSXRlbXM9XCJjZW50ZXJcIiBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiPlxuICAgICAgICAgICAgICAgICAgICAgICAgPENNUFdTdGVwNVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGFueW9uZUNhbkFkZFNlbGY9e2FueW9uZUNhbkFkZFNlbGZ9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHM9e2d1ZXN0c0NhblNlZU90aGVyR3Vlc3RzfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHByaW1hcnlFbWFpbD17cHJpbWFyeUVtYWlsfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGxvY2tBZnRlcj17bG9ja0FmdGVyfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNldFBhcmVudEFueW9uZUNhbkFkZFNlbGY9e3NldEFueW9uZUNhbkFkZFNlbGZ9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc2V0UGFyZW50R3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHM9e3NldEd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNldFBhcmVudFByaW1hcnlFbWFpbD17c2V0UHJpbWFyeUVtYWlsfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNldFBhcmVudExvY2tBZnRlcj17c2V0TG9ja0FmdGVyfVxuICAgICAgICAgICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICAgICAgICAgIDxCb3ggZmxleERpcmVjdGlvbj1cInJvd1wiIGp1c3RpZnlDb250ZW50PVwic3BhY2UtYmV0d2VlblwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiAgc3R5bGU9e3sgd2lkdGg6ICcxMDAlJ319PlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHtyZW5kZXJQcmV2QnV0dG9uKCl9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAge3JlbmRlck5leHRCdXR0b24oKX1cbiAgICAgICAgICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgICAgICApXG4gICAgICAgICAgICBcbiAgICAgICAgICAgIGNhc2UgNTpcbiAgICAgICAgICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgICAgICAgICA8Qm94IHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0gZmxleD17MX0gYWxpZ25JdGVtcz1cImNlbnRlclwiIGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICA8Qm94IGZsZXg9ezF9IHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0gcD17eyBwaG9uZTogJ3MnLCB0YWJsZXQ6ICdtJyB9fSBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiBtaW5IZWlnaHQ9XCI2NXZoXCIgbWF4SGVpZ2h0PVwiNjV2aFwiPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxCb3ggcD17eyBwaG9uZTogJ20nLCB0YWJsZXQ6ICdsJ319PlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8VGV4dCB2YXJpYW50PVwic3ViaGVhZGVyTm9ybWFsXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBTYXZlIE1lZXRpbmcgUHJlZmVyZW5jZXMgdmlhIENoYXRcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC9UZXh0PlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxCb3ggcHQ9e3sgcGhvbmU6ICdtJywgdGFibGV0OiAnbCcgfX0+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxCdXR0b24gb25DbGljaz17c2F2ZUNoYXRNZWV0aW5nUHJlZmVyZW5jZXN9PlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgU2F2ZVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L0J1dHRvbj5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgICAgICAgICAgPEJveCBmbGV4RGlyZWN0aW9uPVwicm93XCIganVzdGlmeUNvbnRlbnQ9XCJzcGFjZS1iZXR3ZWVuXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiIHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAge3JlbmRlclByZXZCdXR0b24oKX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB7cmVuZGVyTmV4dEJ1dHRvbigpfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxCb3ggLz5cbiAgICAgICAgICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgICAgICApXG5cbiAgICAgICAgICAgIGRlZmF1bHQ6XG4gICAgICAgICAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgICAgICAgICAgPEJveCBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgICAgICAgICAgICAgIDxSZWd1bGFyQ2FyZD5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA8VGV4dCB2YXJpYW50PVwiaGVhZGVyXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIE9vcHMuLi4gc29tZXRoaW5nIHdlbnQgd3JvbmdcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L1RleHQ+XG4gICAgICAgICAgICAgICAgICAgICAgICA8L1JlZ3VsYXJDYXJkPlxuICAgICAgICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgICAgICApXG5cbiAgICAgICAgfVxuICAgIH1cblxuICAgIHJldHVybiAoXG4gICAgICAgIDxCb3ggZmxleD17MX0ganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCIgaGVpZ2h0PVwiMTAwJVwiIHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0+XG4gICAgICAgICAgICA8V2l6YXJkXG4gICAgICAgICAgICAgICAgaXRlbXM9e1tcbiAgICAgICAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgICAgICAgICAgaW5kZXg6IDAsXG4gICAgICAgICAgICAgICAgICAgICAgICBsYWJlbDogJ1N0ZXAgMScsXG4gICAgICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGluZGV4OiAxLFxuICAgICAgICAgICAgICAgICAgICAgICAgbGFiZWw6ICdTdGVwIDInLFxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICAgICAgICBpbmRleDogMixcbiAgICAgICAgICAgICAgICAgICAgICAgIGxhYmVsOiAnU3RlcCAzJyxcbiAgICAgICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGluZGV4OiAzLFxuICAgICAgICAgICAgICAgICAgICAgICAgbGFiZWw6ICdTdGVwIDQnLFxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgICAgICAgICAgaW5kZXg6IDQsXG4gICAgICAgICAgICAgICAgICAgICAgICBsYWJlbDogJ1N0ZXAgNScsXG4gICAgICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICAgICAgICBpbmRleDogNSxcbiAgICAgICAgICAgICAgICAgICAgICAgIGxhYmVsOiAnTGFzdCBTdGVwJyxcbiAgICAgICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICBdfVxuXG4gICAgICAgICAgICAgICAgY29tcGxldGVkPXtjb21wbGV0ZWRTdGVwfVxuICAgICAgICAgICAgICAgIGFjdGl2ZUluZGV4PXthY3RpdmVJbmRleH1cbiAgICAgICAgICAgIC8+XG4gICAgICAgICAgICB7cmVuZGVyQ3VycmVudFN0ZXAoKX1cbiAgICAgICAgPC9Cb3g+XG4gICAgKVxufSAgIFxuXG5cbmV4cG9ydCBkZWZhdWx0IFVzZXJDaGF0TWVldGluZ1ByZWZlcmVuY2VzXG4iXX0=