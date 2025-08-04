"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getServerSideProps = getServerSideProps;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const client_1 = require("@apollo/client");
const react_2 = require("@chakra-ui/react");
const Box_1 = __importDefault(require("@components/common/Box"));
const Text_1 = __importDefault(require("@components/common/Text"));
const EditPreferenceStep1_1 = __importDefault(require("@pages/Settings/UserPreferenceWizard/EditPreferenceStep1"));
const EditPreferenceStep2_1 = __importDefault(require("@pages/Settings/UserPreferenceWizard/EditPreferenceStep2"));
const EditPreferenceStep3_1 = __importDefault(require("@pages/Settings/UserPreferenceWizard/EditPreferenceStep3"));
const EditPreferenceStep5_1 = __importDefault(require("@pages/Settings/UserPreferenceWizard/EditPreferenceStep5"));
const EditPreferenceStep6_1 = __importDefault(require("@pages/Settings/UserPreferenceWizard/EditPreferenceStep6"));
const lodash_1 = __importDefault(require("lodash"));
const Button_1 = __importDefault(require("@components/Button"));
const Wizard_1 = __importDefault(require("@components/Wizard"));
const RegularCard_1 = __importDefault(require("@components/RegularCard"));
const OnBoardHelper2_1 = require("@lib/OnBoard/OnBoardHelper2");
const user_context_1 = require("@lib/user-context");
const router_1 = require("next/router");
const DEFAULT_START_TIMES = [
    {
        day: 1,
        hour: 7,
        minutes: 0,
    },
    {
        day: 2,
        hour: 7,
        minutes: 0,
    },
    {
        day: 3,
        hour: 7,
        minutes: 0,
    },
    {
        day: 4,
        hour: 7,
        minutes: 0,
    },
    {
        day: 5,
        hour: 7,
        minutes: 0,
    },
    {
        day: 6,
        hour: 7,
        minutes: 0,
    },
    {
        day: 7,
        hour: 7,
        minutes: 0,
    }
];
const DEFAULT_END_TIMES = [
    {
        day: 1,
        hour: 19,
        minutes: 0,
    },
    {
        day: 2,
        hour: 19,
        minutes: 0,
    },
    {
        day: 3,
        hour: 19,
        minutes: 0,
    },
    {
        day: 4,
        hour: 19,
        minutes: 0,
    },
    {
        day: 5,
        hour: 19,
        minutes: 0,
    },
    {
        day: 6,
        hour: 19,
        minutes: 0,
    },
    {
        day: 7,
        hour: 19,
        minutes: 0,
    }
];
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
function UserCalendarPreferences() {
    const [reminders, setReminders] = (0, react_1.useState)([]);
    const [startTimes, setStartTimes] = (0, react_1.useState)([]);
    const [endTimes, setEndTimes] = (0, react_1.useState)([]);
    const [copyAvailability, setCopyAvailability] = (0, react_1.useState)(false);
    const [copyTimeBlocking, setCopyTimeBlocking] = (0, react_1.useState)(false);
    const [copyTimePreference, setCopyTimePreference] = (0, react_1.useState)(false);
    const [copyReminders, setCopyReminders] = (0, react_1.useState)(false);
    const [copyPriorityLevel, setCopyPriorityLevel] = (0, react_1.useState)(false);
    const [copyModifiable, setCopyModifiable] = (0, react_1.useState)(false);
    const [copyCategories, setCopyCategories] = (0, react_1.useState)(false);
    const [copyIsBreak, setCopyIsBreak] = (0, react_1.useState)(false);
    const [maxWorkLoadPercent, setMaxWorkLoadPercent] = (0, react_1.useState)(85);
    const [minNumberOfBreaks, setMinNumberOfBreaks] = (0, react_1.useState)();
    const [breakLength, setBreakLength] = (0, react_1.useState)();
    const [backToBackMeetings, setBackToBackMeetings] = (0, react_1.useState)(false);
    const [maxNumberOfMeetings, setMaxNumberOfMeetings] = (0, react_1.useState)(6);
    const [copyIsMeeting, setCopyIsMeeting] = (0, react_1.useState)(false);
    const [copyIsExternalMeeting, setCopyIsExternalMeeting] = (0, react_1.useState)(false);
    const [copyColor, setCopyColor] = (0, react_1.useState)(false);
    const [activeIndex, setActiveIndex] = (0, react_1.useState)(0);
    const [completedStep, setCompletedStep] = (0, react_1.useState)();
    const [breakColor, setBreakColor] = (0, react_1.useState)();
    const router = (0, router_1.useRouter)();
    const { sub, client } = (0, user_context_1.useAppContext)();
    const userId = sub;
    const toast = (0, react_2.useToast)();
    // get user preferences
    (0, react_1.useEffect)(() => {
        (async () => {
            try {
                const existinguser_preferences = await (0, OnBoardHelper2_1.getUserPreference)(client, userId);
                setReminders(existinguser_preferences?.reminders);
                setStartTimes(existinguser_preferences?.startTimes || DEFAULT_START_TIMES);
                setEndTimes(existinguser_preferences?.endTimes || DEFAULT_END_TIMES);
                setCopyAvailability(existinguser_preferences?.copyAvailability);
                setCopyTimeBlocking(existinguser_preferences?.copyTimeBlocking);
                setCopyTimePreference(existinguser_preferences?.copyTimePreference);
                setCopyReminders(existinguser_preferences?.copyReminders);
                setCopyPriorityLevel(existinguser_preferences?.copyPriorityLevel);
                setCopyModifiable(existinguser_preferences?.copyModifiable);
                setCopyCategories(existinguser_preferences?.copyCategories);
                setCopyIsBreak(existinguser_preferences?.copyIsBreak);
                setMaxWorkLoadPercent(existinguser_preferences?.maxWorkLoadPercent || 85);
                setMinNumberOfBreaks(existinguser_preferences?.minNumberOfBreaks || 1);
                setBreakLength(existinguser_preferences?.breakLength || 30);
                setBackToBackMeetings(existinguser_preferences?.backToBackMeetings);
                setMaxNumberOfMeetings(existinguser_preferences?.maxNumberOfMeetings);
                setCopyIsMeeting(existinguser_preferences?.copyIsMeeting);
                setCopyIsExternalMeeting(existinguser_preferences?.copyIsExternalMeeting);
                setCopyColor(existinguser_preferences?.copyColor);
                setBreakColor(existinguser_preferences?.breakColor || '#F7EBF7');
            }
            catch (e) {
                console.log(e, ' error in useEffect for UserCalendarPreferences');
            }
        })();
    }, [client, userId]);
    // save user preferences
    const saveuser_preferences = async () => {
        try {
            // validate
            if (maxWorkLoadPercent < 0 || maxWorkLoadPercent > 100) {
                toast({
                    title: 'Invalid max work load percent',
                    description: 'Max work load percent must be between 0 and 100',
                    status: 'error',
                    duration: 9000,
                    isClosable: true,
                });
                return;
            }
            if (minNumberOfBreaks < 0) {
                toast({
                    title: 'Invalid min number of breaks',
                    description: 'Min number of breaks must be greater than 0',
                    status: 'error',
                    duration: 9000,
                    isClosable: true,
                });
                return;
            }
            if ((minNumberOfBreaks > 0) && (breakLength <= 0)) {
                toast({
                    title: 'Invalid break length',
                    description: 'Break length must be greater than 0',
                    status: 'error',
                    duration: 9000,
                    isClosable: true,
                });
                return;
            }
            if (maxNumberOfMeetings < 0) {
                toast({
                    title: 'Invalid max number of meetings',
                    description: 'Max number of meetings must be greater than 0',
                    status: 'error',
                    duration: 9000,
                    isClosable: true,
                });
                return;
            }
            // save
            const existinguser_preferences = await (0, OnBoardHelper2_1.getUserPreference)(client, userId);
            if (!existinguser_preferences) {
                toast({
                    title: 'Error',
                    description: 'Error saving user preferences',
                    status: 'error',
                    duration: 9000,
                    isClosable: true,
                });
                return;
            }
            const upsertUserPreferenceMutation = (0, client_1.gql) `
                mutation InsertUserPreference($userPreference: User_Preference_insert_input!) {
                    insert_User_Preference_one(
                        object: $userPreference,
                        on_conflict: {
                        constraint: UserPreference_pkey,
                        update_columns: [
                            ${(reminders?.length > 0)
                && !lodash_1.default.isEqual(reminders, existinguser_preferences?.reminders) ? 'reminders,' : ''}
                            ${(startTimes?.length > 0)
                && !lodash_1.default.isEqual(startTimes, existinguser_preferences?.startTimes) ? 'startTimes,' : ''}
                            ${(endTimes?.length > 0)
                && !lodash_1.default.isEqual(endTimes, existinguser_preferences?.endTimes) ? 'endTimes,' : ''}
                            ${copyAvailability !== undefined ? 'copyAvailability,' : ''}
                            ${copyTimeBlocking !== undefined ? 'copyTimeBlocking,' : ''}
                            ${copyTimePreference !== undefined ? 'copyTimePreference,' : ''}
                            ${copyReminders !== undefined ? 'copyReminders,' : ''}
                            ${copyPriorityLevel !== undefined ? 'copyPriorityLevel,' : ''}
                            ${copyModifiable !== undefined ? 'copyModifiable,' : ''}
                            ${copyCategories !== undefined ? 'copyCategories,' : ''}
                            ${copyIsBreak !== undefined ? 'copyIsBreak,' : ''}
                            ${maxWorkLoadPercent !== undefined ? 'maxWorkLoadPercent,' : ''}
                            ${maxNumberOfMeetings !== undefined ? 'maxNumberOfMeetings,' : ''}
                            ${minNumberOfBreaks !== undefined ? 'minNumberOfBreaks,' : ''}
                            ${breakLength !== undefined ? 'breakLength,' : ''}
                            ${copyColor !== undefined ? 'copyColor,' : ''}
                            ${copyIsMeeting !== undefined ? 'copyIsMeeting,' : ''}
                            ${copyIsExternalMeeting !== undefined ? 'copyIsExternalMeeting,' : ''}
                            ${backToBackMeetings !== undefined ? 'backToBackMeetings,' : ''}
                            ${breakColor !== undefined ? 'breakColor,' : ''}
                            updatedAt,
                        ]
                        }
                    ) {
                        id
                        reminders
                        followUp
                        isPublicCalendar
                        publicCalendarCategories
                        startTimes
                        endTimes
                        copyAvailability
                        copyTimeBlocking
                        copyTimePreference
                        copyReminders
                        copyPriorityLevel
                        copyModifiable
                        copyCategories
                        copyIsBreak
                        maxWorkLoadPercent
                        backToBackMeetings
                        maxNumberOfMeetings
                        minNumberOfBreaks
                        breakLength
                        breakColor
                        copyIsMeeting
                        copyIsExternalMeeting
                        copyColor
                        deleted
                        createdDate
                        updatedAt
                        userId
                    }
                }`;
            const valuesToUpsert = {
                id: existinguser_preferences?.id,
                userId,
            };
            if ((reminders?.length > 0)
                && !lodash_1.default.isEqual(reminders, existinguser_preferences?.reminders)) {
                valuesToUpsert.reminders = reminders;
            }
            if ((startTimes?.length > 0)
                && !lodash_1.default.isEqual(startTimes, existinguser_preferences?.startTimes)) {
                valuesToUpsert.startTimes = startTimes;
            }
            if ((endTimes?.length > 0)
                && !lodash_1.default.isEqual(endTimes, existinguser_preferences?.endTimes)) {
                valuesToUpsert.endTimes = endTimes;
            }
            if (copyAvailability !== undefined) {
                valuesToUpsert.copyAvailability = copyAvailability;
            }
            if (copyTimeBlocking !== undefined) {
                valuesToUpsert.copyTimeBlocking = copyTimeBlocking;
            }
            if (copyTimePreference !== undefined) {
                valuesToUpsert.copyTimePreference = copyTimePreference;
            }
            if (copyReminders !== undefined) {
                valuesToUpsert.copyReminders = copyReminders;
            }
            if (copyPriorityLevel !== undefined) {
                valuesToUpsert.copyPriorityLevel = copyPriorityLevel;
            }
            if (copyModifiable !== undefined) {
                valuesToUpsert.copyModifiable = copyModifiable;
            }
            if (copyCategories !== undefined) {
                valuesToUpsert.copyCategories = copyCategories;
            }
            if (copyIsBreak !== undefined) {
                valuesToUpsert.copyIsBreak = copyIsBreak;
            }
            if (maxWorkLoadPercent !== undefined) {
                valuesToUpsert.maxWorkLoadPercent = maxWorkLoadPercent;
            }
            if (maxNumberOfMeetings !== undefined) {
                valuesToUpsert.maxNumberOfMeetings = maxNumberOfMeetings;
            }
            if (minNumberOfBreaks !== undefined) {
                valuesToUpsert.minNumberOfBreaks = minNumberOfBreaks;
            }
            if (breakLength !== undefined) {
                valuesToUpsert.breakLength = breakLength;
            }
            if (copyColor !== undefined) {
                valuesToUpsert.copyColor = copyColor;
            }
            if (copyIsMeeting !== undefined) {
                valuesToUpsert.copyIsMeeting = copyIsMeeting;
            }
            if (copyIsExternalMeeting !== undefined) {
                valuesToUpsert.copyIsExternalMeeting = copyIsExternalMeeting;
            }
            if (backToBackMeetings !== undefined) {
                valuesToUpsert.backToBackMeetings = backToBackMeetings;
            }
            if (breakColor !== undefined) {
                valuesToUpsert.breakColor = breakColor;
            }
            console.log(valuesToUpsert, ' valuesToUpsert inside upsertUserPreference for userId: ', userId, 'part of UserCalendarPreferences');
            await client.mutate({
                mutation: upsertUserPreferenceMutation,
                variables: {
                    userPreference: valuesToUpsert,
                },
            });
            toast({
                title: 'Success',
                description: 'User preferences saved',
                status: 'success',
                duration: 9000,
                isClosable: true,
            });
            router.back();
        }
        catch (e) {
            console.log(e, ' error in saveuser_preferences');
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
        /*
            0 - EditPreferenceStep1
            1 - EditPreferenceStep2
            2 - EditPreferenceStep3
            3 - EditPreferenceStep4
            4 - EditPreferenceStep5
        */
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
            return (0, jsx_runtime_1.jsx)(Box_1.default, { mr: { phone: 's', tablet: 'm' } });
        }
        return ((0, jsx_runtime_1.jsx)(Box_1.default, { mr: { phone: 's', tablet: 'm' }, children: (0, jsx_runtime_1.jsx)(Button_1.default, { onClick: goToNextStep, children: "Next" }) }));
    };
    const renderCurrentStep = () => {
        /*
            0 - EditPreferenceStep1
            1 - EditPreferenceStep2
            2 - EditPreferenceStep3
            3 - EditPreferenceStep4
            4 - EditPreferenceStep5
        */
        switch (activeIndex) {
            case 0:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(EditPreferenceStep1_1.default, { reminders: reminders, setParentReminders: setReminders }), (0, jsx_runtime_1.jsxs)(Box_1.default, { pt: { phone: 'm', tablet: 's' }, mb: { phone: 's', tablet: 'm' }, style: { width: '100%' }, flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [(0, jsx_runtime_1.jsx)(Box_1.default, {}), renderNextButton()] })] }));
            case 1:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(EditPreferenceStep2_1.default, { startTimes: startTimes, setParentStartTimes: setStartTimes, endTimes: endTimes, setParentEndTimes: setEndTimes }), (0, jsx_runtime_1.jsxs)(Box_1.default, { pt: { phone: 'm', tablet: 's' }, mb: { phone: 's', tablet: 'm' }, style: { width: '100%' }, flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [renderPrevButton(), renderNextButton()] })] }));
            case 2:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(EditPreferenceStep3_1.default, { copyAvailability: copyAvailability, setParentCopyAvailability: setCopyAvailability, copyTimeBlocking: copyTimeBlocking, setParentCopyTimeBlocking: setCopyTimeBlocking, copyTimePreference: copyTimePreference, setParentCopyTimePreference: setCopyTimePreference, copyReminders: copyReminders, setParentCopyReminders: setCopyReminders, copyPriorityLevel: copyPriorityLevel, setParentCopyPriorityLevel: setCopyPriorityLevel, copyModifiable: copyModifiable, setParentCopyModifiable: setCopyModifiable }), (0, jsx_runtime_1.jsxs)(Box_1.default, { pt: { phone: 'm', tablet: 's' }, mb: { phone: 's', tablet: 'm' }, style: { width: '100%' }, flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [renderPrevButton(), renderNextButton()] })] }));
            case 3:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(EditPreferenceStep5_1.default, { copyCategories: copyCategories, setParentCopyCategories: setCopyCategories, copyIsBreak: copyIsBreak, setParentCopyIsBreak: setCopyIsBreak, maxWorkLoadPercent: maxWorkLoadPercent, setParentMaxWorkLoadPercent: setMaxWorkLoadPercent, minNumberOfBreaks: minNumberOfBreaks, setParentMinNumberOfBreaks: setMinNumberOfBreaks, breakLength: breakLength, setParentBreakLength: setBreakLength }), (0, jsx_runtime_1.jsxs)(Box_1.default, { pt: { phone: 'm', tablet: 's' }, mb: { phone: 's', tablet: 'm' }, style: { width: '100%' }, flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [renderPrevButton(), renderNextButton()] })] }));
            case 4:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(EditPreferenceStep6_1.default, { backToBackMeetings: backToBackMeetings, setParentBackToBackMeetings: setBackToBackMeetings, copyIsMeeting: copyIsMeeting, setParentCopyIsMeeting: setCopyIsMeeting, copyIsExternalMeeting: copyIsExternalMeeting, setParentCopyIsExternalMeeting: setCopyIsExternalMeeting, copyColor: copyColor, setParentCopyColor: setCopyColor, breakColor: breakColor, setParentBreakColor: setBreakColor }), (0, jsx_runtime_1.jsxs)(Box_1.default, { pt: { phone: 'm', tablet: 's' }, mb: { phone: 's', tablet: 'm' }, style: { width: '100%' }, flexDirection: "row", justifyContent: "space-between", alignItems: "center", children: [renderPrevButton(), renderNextButton()] })] }));
            case 5:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsxs)(Box_1.default, { justifyContent: "center", alignItems: "center", minHeight: "60vh", children: [(0, jsx_runtime_1.jsx)(Box_1.default, { style: { width: '100%' }, p: { phone: 's', tablet: 'm' }, justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "subheaderNormal", children: "Save User Preferences" }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { justifyContent: "center", alignItems: "center", p: { phone: 's', tablet: 'm' }, children: (0, jsx_runtime_1.jsx)(Button_1.default, { onClick: saveuser_preferences, children: "Submit" }) })] }), (0, jsx_runtime_1.jsx)(Box_1.default, { pt: { phone: 'm', tablet: 's' }, mb: { phone: 's', tablet: 'm' }, flexDirection: "row", justifyContent: "flex-start", width: "100%", children: renderPrevButton() })] }));
            default:
                return ((0, jsx_runtime_1.jsx)(Box_1.default, { justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsx)(RegularCard_1.default, { children: (0, jsx_runtime_1.jsx)(Text_1.default, { variant: "header", children: "Oops... something went wrong" }) }) }));
        }
    };
    return ((0, jsx_runtime_1.jsxs)(Box_1.default, { style: { width: '100%' }, flex: 1, alignItems: "center", justifyContent: "center", children: [(0, jsx_runtime_1.jsx)(Wizard_1.default, { items: [
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
                        label: 'Save Preferences',
                    },
                ], completed: completedStep, activeIndex: activeIndex }), renderCurrentStep()] }));
}
exports.default = UserCalendarPreferences;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlckNhbGVuZGFyUHJlZmVyZW5jZXMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJVc2VyQ2FsZW5kYXJQcmVmZXJlbmNlcy50c3giXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUEwR0EsZ0RBcUNDOztBQS9JRCxpQ0FHYztBQUVkLDJDQUFvQztBQUNwQyw0Q0FBMkM7QUFDM0MsaUVBQXdDO0FBQ3hDLG1FQUEwQztBQUcxQyxtSEFBMEY7QUFDMUYsbUhBQTBGO0FBQzFGLG1IQUEwRjtBQUMxRixtSEFBMEY7QUFDMUYsbUhBQTBGO0FBQzFGLG9EQUFzQjtBQUN0QixnRUFBdUM7QUFDdkMsZ0VBQXVDO0FBQ3ZDLDBFQUFpRDtBQUNqRCxnRUFBK0Q7QUFDL0Qsb0RBQWlEO0FBRWpELHdDQUF1QztBQUV2QyxNQUFNLG1CQUFtQixHQUFHO0lBQ3hCO1FBQ0ksR0FBRyxFQUFFLENBQUM7UUFDTixJQUFJLEVBQUUsQ0FBQztRQUNQLE9BQU8sRUFBRSxDQUFDO0tBQ2I7SUFDRDtRQUNJLEdBQUcsRUFBRSxDQUFDO1FBQ04sSUFBSSxFQUFFLENBQUM7UUFDUCxPQUFPLEVBQUUsQ0FBQztLQUNiO0lBQ0Q7UUFDSSxHQUFHLEVBQUUsQ0FBQztRQUNOLElBQUksRUFBRSxDQUFDO1FBQ1AsT0FBTyxFQUFFLENBQUM7S0FDYjtJQUNEO1FBQ0ksR0FBRyxFQUFFLENBQUM7UUFDTixJQUFJLEVBQUUsQ0FBQztRQUNQLE9BQU8sRUFBRSxDQUFDO0tBQ2I7SUFDRDtRQUNJLEdBQUcsRUFBRSxDQUFDO1FBQ04sSUFBSSxFQUFFLENBQUM7UUFDUCxPQUFPLEVBQUUsQ0FBQztLQUNiO0lBQ0Q7UUFDSSxHQUFHLEVBQUUsQ0FBQztRQUNOLElBQUksRUFBRSxDQUFDO1FBQ1AsT0FBTyxFQUFFLENBQUM7S0FDYjtJQUNEO1FBQ0ksR0FBRyxFQUFFLENBQUM7UUFDTixJQUFJLEVBQUUsQ0FBQztRQUNQLE9BQU8sRUFBRSxDQUFDO0tBQ2I7Q0FDSixDQUFBO0FBRUQsTUFBTSxpQkFBaUIsR0FBRztJQUN0QjtRQUNJLEdBQUcsRUFBRSxDQUFDO1FBQ04sSUFBSSxFQUFFLEVBQUU7UUFDUixPQUFPLEVBQUUsQ0FBQztLQUNiO0lBQ0Q7UUFDSSxHQUFHLEVBQUUsQ0FBQztRQUNOLElBQUksRUFBRSxFQUFFO1FBQ1IsT0FBTyxFQUFFLENBQUM7S0FDYjtJQUNEO1FBQ0ksR0FBRyxFQUFFLENBQUM7UUFDTixJQUFJLEVBQUUsRUFBRTtRQUNSLE9BQU8sRUFBRSxDQUFDO0tBQ2I7SUFDRDtRQUNJLEdBQUcsRUFBRSxDQUFDO1FBQ04sSUFBSSxFQUFFLEVBQUU7UUFDUixPQUFPLEVBQUUsQ0FBQztLQUNiO0lBQ0Q7UUFDSSxHQUFHLEVBQUUsQ0FBQztRQUNOLElBQUksRUFBRSxFQUFFO1FBQ1IsT0FBTyxFQUFFLENBQUM7S0FDYjtJQUNEO1FBQ0ksR0FBRyxFQUFFLENBQUM7UUFDTixJQUFJLEVBQUUsRUFBRTtRQUNSLE9BQU8sRUFBRSxDQUFDO0tBQ2I7SUFDRDtRQUNJLEdBQUcsRUFBRSxDQUFDO1FBQ04sSUFBSSxFQUFFLEVBQUU7UUFDUixPQUFPLEVBQUUsQ0FBQztLQUNiO0NBQ0osQ0FBQTtBQUdELHdFQUE4QztBQUM5Qyx5REFBcUQ7QUFDckQsOEVBQXFEO0FBRTlDLEtBQUssVUFBVSxrQkFBa0IsQ0FBQyxFQUFFLEdBQUcsRUFBRSxHQUFHLEVBQWlEO0lBQ2hHLDBGQUEwRjtJQUMxRixzQ0FBc0M7SUFDdEMseUVBQXlFO0lBQ3pFLDBCQUFlLENBQUMsSUFBSSxDQUFDLElBQUEsNkJBQWEsR0FBRSxDQUFDLENBQUE7SUFDckMsSUFBSSxPQUFPLENBQUE7SUFDWCxJQUFJLENBQUM7UUFDRCxPQUFPLEdBQUcsTUFBTSxpQkFBTyxDQUFDLFVBQVUsQ0FBQyxHQUFHLEVBQUUsR0FBRyxFQUFFO1lBQ3pDLDZCQUE2QixFQUFFLEtBQUs7Z0JBQ2hDLE9BQU8sRUFBRSxDQUFBO1lBQ2IsQ0FBQztTQUNKLENBQUMsQ0FBQTtJQUNOLENBQUM7SUFBQyxPQUFPLEdBQVEsRUFBRSxDQUFDO1FBQ2hCLElBQUksR0FBRyxDQUFDLElBQUksS0FBSyxpQkFBTyxDQUFDLEtBQUssQ0FBQyxpQkFBaUIsRUFBRSxDQUFDO1lBQy9DLE9BQU8sRUFBRSxLQUFLLEVBQUUsRUFBRSxlQUFlLEVBQUUsZUFBZSxFQUFFLEVBQUUsQ0FBQTtRQUMxRCxDQUFDO2FBQU0sSUFBSSxHQUFHLENBQUMsSUFBSSxLQUFLLGlCQUFPLENBQUMsS0FBSyxDQUFDLFlBQVksRUFBRSxDQUFDO1lBQ2pELGtFQUFrRTtZQUNsRSxxRUFBcUU7WUFDckUsT0FBTyxFQUFFLEtBQUssRUFBRSxFQUFFLGVBQWUsRUFBRSxlQUFlLEVBQUUsRUFBRSxDQUFBO1FBQzFELENBQUM7UUFDRCxNQUFNLEdBQUcsQ0FBQTtJQUNiLENBQUM7SUFFRCxJQUFJLENBQUMsT0FBTyxFQUFFLFNBQVMsRUFBRSxFQUFFLENBQUM7UUFDeEIsT0FBTztZQUNILFFBQVEsRUFBRTtnQkFDTixXQUFXLEVBQUUsdUJBQXVCO2dCQUNwQyxTQUFTLEVBQUUsS0FBSzthQUNuQjtTQUNKLENBQUE7SUFDTCxDQUFDO0lBRUQsT0FBTztRQUNILEtBQUssRUFBRTtZQUNQLEdBQUcsRUFBRSxPQUFPLENBQUMsU0FBUyxFQUFFO1NBQ3ZCO0tBQ0osQ0FBQTtBQUNMLENBQUM7QUFFRCxTQUFTLHVCQUF1QjtJQUM1QixNQUFNLENBQUMsU0FBUyxFQUFFLFlBQVksQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBVyxFQUFFLENBQUMsQ0FBQTtJQUN4RCxNQUFNLENBQUMsVUFBVSxFQUFFLGFBQWEsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBa0IsRUFBRSxDQUFDLENBQUE7SUFDakUsTUFBTSxDQUFDLFFBQVEsRUFBRSxXQUFXLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQWdCLEVBQUUsQ0FBQyxDQUFBO0lBQzNELE1BQU0sQ0FBQyxnQkFBZ0IsRUFBRSxtQkFBbUIsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBVSxLQUFLLENBQUMsQ0FBQTtJQUN4RSxNQUFNLENBQUMsZ0JBQWdCLEVBQUUsbUJBQW1CLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQVUsS0FBSyxDQUFDLENBQUE7SUFDeEUsTUFBTSxDQUFDLGtCQUFrQixFQUFFLHFCQUFxQixDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFVLEtBQUssQ0FBQyxDQUFBO0lBQzVFLE1BQU0sQ0FBQyxhQUFhLEVBQUUsZ0JBQWdCLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQVUsS0FBSyxDQUFDLENBQUE7SUFDbEUsTUFBTSxDQUFDLGlCQUFpQixFQUFFLG9CQUFvQixDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFVLEtBQUssQ0FBQyxDQUFBO0lBQzFFLE1BQU0sQ0FBQyxjQUFjLEVBQUUsaUJBQWlCLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQVUsS0FBSyxDQUFDLENBQUE7SUFDcEUsTUFBTSxDQUFDLGNBQWMsRUFBRSxpQkFBaUIsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBVSxLQUFLLENBQUMsQ0FBQTtJQUNwRSxNQUFNLENBQUMsV0FBVyxFQUFFLGNBQWMsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBVSxLQUFLLENBQUMsQ0FBQTtJQUM5RCxNQUFNLENBQUMsa0JBQWtCLEVBQUUscUJBQXFCLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQVMsRUFBRSxDQUFDLENBQUE7SUFDeEUsTUFBTSxDQUFDLGlCQUFpQixFQUFFLG9CQUFvQixDQUFDLEdBQUcsSUFBQSxnQkFBUSxHQUFVLENBQUE7SUFDcEUsTUFBTSxDQUFDLFdBQVcsRUFBRSxjQUFjLENBQUMsR0FBRyxJQUFBLGdCQUFRLEdBQVUsQ0FBQTtJQUN4RCxNQUFNLENBQUMsa0JBQWtCLEVBQUUscUJBQXFCLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQVUsS0FBSyxDQUFDLENBQUE7SUFDNUUsTUFBTSxDQUFDLG1CQUFtQixFQUFFLHNCQUFzQixDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFTLENBQUMsQ0FBQyxDQUFBO0lBQ3pFLE1BQU0sQ0FBQyxhQUFhLEVBQUUsZ0JBQWdCLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQVUsS0FBSyxDQUFDLENBQUE7SUFDbEUsTUFBTSxDQUFDLHFCQUFxQixFQUFFLHdCQUF3QixDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFVLEtBQUssQ0FBQyxDQUFBO0lBQ2xGLE1BQU0sQ0FBQyxTQUFTLEVBQUUsWUFBWSxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFVLEtBQUssQ0FBQyxDQUFBO0lBQzFELE1BQU0sQ0FBQyxXQUFXLEVBQUUsY0FBYyxDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFTLENBQUMsQ0FBQyxDQUFBO0lBQ3pELE1BQU0sQ0FBQyxhQUFhLEVBQUUsZ0JBQWdCLENBQUMsR0FBRyxJQUFBLGdCQUFRLEdBQXNCLENBQUE7SUFDeEUsTUFBTSxDQUFDLFVBQVUsRUFBRSxhQUFhLENBQUMsR0FBRyxJQUFBLGdCQUFRLEdBQVUsQ0FBQTtJQUV0RCxNQUFNLE1BQU0sR0FBRyxJQUFBLGtCQUFTLEdBQUUsQ0FBQTtJQUMxQixNQUFNLEVBQUUsR0FBRyxFQUFFLE1BQU0sRUFBRSxHQUFHLElBQUEsNEJBQWEsR0FBRSxDQUFBO0lBQ3ZDLE1BQU0sTUFBTSxHQUFHLEdBQUcsQ0FBQTtJQUNsQixNQUFNLEtBQUssR0FBRyxJQUFBLGdCQUFRLEdBQUUsQ0FBQTtJQUV4Qix1QkFBdUI7SUFDdkIsSUFBQSxpQkFBUyxFQUFDLEdBQUcsRUFBRTtRQUNYLENBQUMsS0FBSyxJQUFJLEVBQUU7WUFDUixJQUFJLENBQUM7Z0JBQ0QsTUFBTSx3QkFBd0IsR0FBRyxNQUFNLElBQUEsa0NBQWlCLEVBQUMsTUFBTSxFQUFFLE1BQU0sQ0FBQyxDQUFBO2dCQUN4RSxZQUFZLENBQUMsd0JBQXdCLEVBQUUsU0FBUyxDQUFDLENBQUE7Z0JBQ2pELGFBQWEsQ0FBRSx3QkFBd0IsRUFBRSxVQUE4QixJQUFLLG1CQUF1QyxDQUFDLENBQUE7Z0JBQ3BILFdBQVcsQ0FBRSx3QkFBd0IsRUFBRSxRQUEwQixJQUFLLGlCQUFtQyxDQUFDLENBQUE7Z0JBQzFHLG1CQUFtQixDQUFDLHdCQUF3QixFQUFFLGdCQUFnQixDQUFDLENBQUE7Z0JBQy9ELG1CQUFtQixDQUFDLHdCQUF3QixFQUFFLGdCQUFnQixDQUFDLENBQUE7Z0JBQy9ELHFCQUFxQixDQUFDLHdCQUF3QixFQUFFLGtCQUFrQixDQUFDLENBQUE7Z0JBQ25FLGdCQUFnQixDQUFDLHdCQUF3QixFQUFFLGFBQWEsQ0FBQyxDQUFBO2dCQUN6RCxvQkFBb0IsQ0FBQyx3QkFBd0IsRUFBRSxpQkFBaUIsQ0FBQyxDQUFBO2dCQUNqRSxpQkFBaUIsQ0FBQyx3QkFBd0IsRUFBRSxjQUFjLENBQUMsQ0FBQTtnQkFDM0QsaUJBQWlCLENBQUMsd0JBQXdCLEVBQUUsY0FBYyxDQUFDLENBQUE7Z0JBQzNELGNBQWMsQ0FBQyx3QkFBd0IsRUFBRSxXQUFXLENBQUMsQ0FBQTtnQkFDckQscUJBQXFCLENBQUMsd0JBQXdCLEVBQUUsa0JBQWtCLElBQUksRUFBRSxDQUFDLENBQUE7Z0JBQ3pFLG9CQUFvQixDQUFDLHdCQUF3QixFQUFFLGlCQUFpQixJQUFJLENBQUMsQ0FBQyxDQUFBO2dCQUN0RSxjQUFjLENBQUMsd0JBQXdCLEVBQUUsV0FBVyxJQUFJLEVBQUUsQ0FBQyxDQUFBO2dCQUMzRCxxQkFBcUIsQ0FBQyx3QkFBd0IsRUFBRSxrQkFBa0IsQ0FBQyxDQUFBO2dCQUNuRSxzQkFBc0IsQ0FBQyx3QkFBd0IsRUFBRSxtQkFBbUIsQ0FBQyxDQUFBO2dCQUNyRSxnQkFBZ0IsQ0FBQyx3QkFBd0IsRUFBRSxhQUFhLENBQUMsQ0FBQTtnQkFDekQsd0JBQXdCLENBQUMsd0JBQXdCLEVBQUUscUJBQXFCLENBQUMsQ0FBQTtnQkFDekUsWUFBWSxDQUFDLHdCQUF3QixFQUFFLFNBQVMsQ0FBQyxDQUFBO2dCQUNqRCxhQUFhLENBQUMsd0JBQXdCLEVBQUUsVUFBVSxJQUFJLFNBQVMsQ0FBQyxDQUFBO1lBQ3BFLENBQUM7WUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO2dCQUNULE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLGlEQUFpRCxDQUFDLENBQUE7WUFDckUsQ0FBQztRQUNMLENBQUMsQ0FBQyxFQUFFLENBQUE7SUFDUixDQUFDLEVBQUUsQ0FBQyxNQUFNLEVBQUUsTUFBTSxDQUFDLENBQUMsQ0FBQTtJQUVwQix3QkFBd0I7SUFDeEIsTUFBTSxvQkFBb0IsR0FBRyxLQUFLLElBQUksRUFBRTtRQUNwQyxJQUFJLENBQUM7WUFDRCxXQUFXO1lBQ1gsSUFBSSxrQkFBa0IsR0FBRyxDQUFDLElBQUksa0JBQWtCLEdBQUcsR0FBRyxFQUFFLENBQUM7Z0JBQ3JELEtBQUssQ0FBQztvQkFDRixLQUFLLEVBQUUsK0JBQStCO29CQUN0QyxXQUFXLEVBQUUsaURBQWlEO29CQUM5RCxNQUFNLEVBQUUsT0FBTztvQkFDZixRQUFRLEVBQUUsSUFBSTtvQkFDZCxVQUFVLEVBQUUsSUFBSTtpQkFDbkIsQ0FBQyxDQUFBO2dCQUNGLE9BQU07WUFDVixDQUFDO1lBRUQsSUFBSSxpQkFBaUIsR0FBRyxDQUFDLEVBQUUsQ0FBQztnQkFDeEIsS0FBSyxDQUFDO29CQUNGLEtBQUssRUFBRSw4QkFBOEI7b0JBQ3JDLFdBQVcsRUFBRSw2Q0FBNkM7b0JBQzFELE1BQU0sRUFBRSxPQUFPO29CQUNmLFFBQVEsRUFBRSxJQUFJO29CQUNkLFVBQVUsRUFBRSxJQUFJO2lCQUNuQixDQUFDLENBQUE7Z0JBQ0YsT0FBTTtZQUNWLENBQUM7WUFFRCxJQUFJLENBQUMsaUJBQWlCLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQyxXQUFXLElBQUksQ0FBQyxDQUFDLEVBQUUsQ0FBQztnQkFDaEQsS0FBSyxDQUFDO29CQUNGLEtBQUssRUFBRSxzQkFBc0I7b0JBQzdCLFdBQVcsRUFBRSxxQ0FBcUM7b0JBQ2xELE1BQU0sRUFBRSxPQUFPO29CQUNmLFFBQVEsRUFBRSxJQUFJO29CQUNkLFVBQVUsRUFBRSxJQUFJO2lCQUNuQixDQUFDLENBQUE7Z0JBQ0YsT0FBTTtZQUNWLENBQUM7WUFFRCxJQUFJLG1CQUFtQixHQUFHLENBQUMsRUFBRSxDQUFDO2dCQUMxQixLQUFLLENBQUM7b0JBQ0YsS0FBSyxFQUFFLGdDQUFnQztvQkFDdkMsV0FBVyxFQUFFLCtDQUErQztvQkFDNUQsTUFBTSxFQUFFLE9BQU87b0JBQ2YsUUFBUSxFQUFFLElBQUk7b0JBQ2QsVUFBVSxFQUFFLElBQUk7aUJBQ25CLENBQUMsQ0FBQTtnQkFDRixPQUFNO1lBQ1YsQ0FBQztZQUVELE9BQU87WUFDUCxNQUFNLHdCQUF3QixHQUFHLE1BQU0sSUFBQSxrQ0FBaUIsRUFBQyxNQUFNLEVBQUUsTUFBTSxDQUFDLENBQUE7WUFDeEUsSUFBSSxDQUFDLHdCQUF3QixFQUFFLENBQUM7Z0JBQzVCLEtBQUssQ0FBQztvQkFDRixLQUFLLEVBQUUsT0FBTztvQkFDZCxXQUFXLEVBQUUsK0JBQStCO29CQUM1QyxNQUFNLEVBQUUsT0FBTztvQkFDZixRQUFRLEVBQUUsSUFBSTtvQkFDZCxVQUFVLEVBQUUsSUFBSTtpQkFDbkIsQ0FBQyxDQUFBO2dCQUNGLE9BQU07WUFDVixDQUFDO1lBRUQsTUFBTSw0QkFBNEIsR0FBRyxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs4QkFPdEIsQ0FBQyxTQUFTLEVBQUUsTUFBTSxHQUFHLENBQUMsQ0FBQzttQkFDbEIsQ0FBQyxnQkFBQyxDQUFDLE9BQU8sQ0FBQyxTQUFTLEVBQUUsd0JBQXdCLEVBQUUsU0FBUyxDQUFDLENBQUMsQ0FBQyxDQUFDLFlBQVksQ0FBQyxDQUFDLENBQUMsRUFBRTs4QkFDbkYsQ0FBQyxVQUFVLEVBQUUsTUFBTSxHQUFHLENBQUMsQ0FBQzttQkFDbkIsQ0FBQyxnQkFBQyxDQUFDLE9BQU8sQ0FBQyxVQUFVLEVBQUUsd0JBQXdCLEVBQUUsVUFBVSxDQUFDLENBQUMsQ0FBQyxDQUFDLGFBQWEsQ0FBQyxDQUFDLENBQUMsRUFBRTs4QkFDdEYsQ0FBQyxRQUFRLEVBQUUsTUFBTSxHQUFHLENBQUMsQ0FBQzttQkFDakIsQ0FBQyxnQkFBQyxDQUFDLE9BQU8sQ0FBQyxRQUFRLEVBQUUsd0JBQXdCLEVBQUUsUUFBUSxDQUFDLENBQUMsQ0FBQyxDQUFDLFdBQVcsQ0FBQyxDQUFDLENBQUMsRUFBRTs4QkFDaEYsZ0JBQWdCLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxtQkFBbUIsQ0FBQyxDQUFDLENBQUMsRUFBRTs4QkFDekQsZ0JBQWdCLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxtQkFBbUIsQ0FBQyxDQUFDLENBQUMsRUFBRTs4QkFDekQsa0JBQWtCLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxxQkFBcUIsQ0FBQyxDQUFDLENBQUMsRUFBRTs4QkFDN0QsYUFBYSxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsZ0JBQWdCLENBQUMsQ0FBQyxDQUFDLEVBQUU7OEJBQ25ELGlCQUFpQixLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsb0JBQW9CLENBQUMsQ0FBQyxDQUFDLEVBQUU7OEJBQzNELGNBQWMsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLGlCQUFpQixDQUFDLENBQUMsQ0FBQyxFQUFFOzhCQUNyRCxjQUFjLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxpQkFBaUIsQ0FBQyxDQUFDLENBQUMsRUFBRTs4QkFDckQsV0FBVyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsY0FBYyxDQUFDLENBQUMsQ0FBQyxFQUFFOzhCQUMvQyxrQkFBa0IsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLHFCQUFxQixDQUFDLENBQUMsQ0FBQyxFQUFFOzhCQUM3RCxtQkFBbUIsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLHNCQUFzQixDQUFDLENBQUMsQ0FBQyxFQUFFOzhCQUMvRCxpQkFBaUIsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLG9CQUFvQixDQUFDLENBQUMsQ0FBQyxFQUFFOzhCQUMzRCxXQUFXLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxjQUFjLENBQUMsQ0FBQyxDQUFDLEVBQUU7OEJBQy9DLFNBQVMsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLFlBQVksQ0FBQyxDQUFDLENBQUMsRUFBRTs4QkFDM0MsYUFBYSxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsZ0JBQWdCLENBQUMsQ0FBQyxDQUFDLEVBQUU7OEJBQ25ELHFCQUFxQixLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsd0JBQXdCLENBQUMsQ0FBQyxDQUFDLEVBQUU7OEJBQ25FLGtCQUFrQixLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMscUJBQXFCLENBQUMsQ0FBQyxDQUFDLEVBQUU7OEJBQzdELFVBQVUsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLGFBQWEsQ0FBQyxDQUFDLENBQUMsRUFBRTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztrQkFrQ3pELENBQUE7WUFFTixNQUFNLGNBQWMsR0FBUTtnQkFDeEIsRUFBRSxFQUFFLHdCQUF3QixFQUFFLEVBQUU7Z0JBQ2hDLE1BQU07YUFDVCxDQUFBO1lBRUQsSUFBSSxDQUFDLFNBQVMsRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDO21CQUNwQixDQUFDLGdCQUFDLENBQUMsT0FBTyxDQUFDLFNBQVMsRUFBRSx3QkFBd0IsRUFBRSxTQUFTLENBQUMsRUFBRSxDQUFDO2dCQUNoRSxjQUFjLENBQUMsU0FBUyxHQUFHLFNBQVMsQ0FBQTtZQUN4QyxDQUFDO1lBRUQsSUFBSSxDQUFDLFVBQVUsRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDO21CQUNyQixDQUFDLGdCQUFDLENBQUMsT0FBTyxDQUFDLFVBQVUsRUFBRSx3QkFBd0IsRUFBRSxVQUFVLENBQUMsRUFBRSxDQUFDO2dCQUNsRSxjQUFjLENBQUMsVUFBVSxHQUFHLFVBQVUsQ0FBQTtZQUMxQyxDQUFDO1lBRUQsSUFBSSxDQUFDLFFBQVEsRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDO21CQUNuQixDQUFDLGdCQUFDLENBQUMsT0FBTyxDQUFDLFFBQVEsRUFBRSx3QkFBd0IsRUFBRSxRQUFRLENBQUMsRUFBRSxDQUFDO2dCQUM5RCxjQUFjLENBQUMsUUFBUSxHQUFHLFFBQVEsQ0FBQTtZQUN0QyxDQUFDO1lBRUQsSUFBSSxnQkFBZ0IsS0FBSyxTQUFTLEVBQUUsQ0FBQztnQkFDakMsY0FBYyxDQUFDLGdCQUFnQixHQUFHLGdCQUFnQixDQUFBO1lBQ3RELENBQUM7WUFFRCxJQUFJLGdCQUFnQixLQUFLLFNBQVMsRUFBRSxDQUFDO2dCQUNqQyxjQUFjLENBQUMsZ0JBQWdCLEdBQUcsZ0JBQWdCLENBQUE7WUFDdEQsQ0FBQztZQUVELElBQUksa0JBQWtCLEtBQUssU0FBUyxFQUFFLENBQUM7Z0JBQ25DLGNBQWMsQ0FBQyxrQkFBa0IsR0FBRyxrQkFBa0IsQ0FBQTtZQUMxRCxDQUFDO1lBRUQsSUFBSSxhQUFhLEtBQUssU0FBUyxFQUFFLENBQUM7Z0JBQzlCLGNBQWMsQ0FBQyxhQUFhLEdBQUcsYUFBYSxDQUFBO1lBQ2hELENBQUM7WUFFRCxJQUFJLGlCQUFpQixLQUFLLFNBQVMsRUFBRSxDQUFDO2dCQUNsQyxjQUFjLENBQUMsaUJBQWlCLEdBQUcsaUJBQWlCLENBQUE7WUFDeEQsQ0FBQztZQUVELElBQUksY0FBYyxLQUFLLFNBQVMsRUFBRSxDQUFDO2dCQUMvQixjQUFjLENBQUMsY0FBYyxHQUFHLGNBQWMsQ0FBQTtZQUNsRCxDQUFDO1lBRUQsSUFBSSxjQUFjLEtBQUssU0FBUyxFQUFFLENBQUM7Z0JBQy9CLGNBQWMsQ0FBQyxjQUFjLEdBQUcsY0FBYyxDQUFBO1lBQ2xELENBQUM7WUFFRCxJQUFJLFdBQVcsS0FBSyxTQUFTLEVBQUUsQ0FBQztnQkFDNUIsY0FBYyxDQUFDLFdBQVcsR0FBRyxXQUFXLENBQUE7WUFDNUMsQ0FBQztZQUVELElBQUksa0JBQWtCLEtBQUssU0FBUyxFQUFFLENBQUM7Z0JBQ25DLGNBQWMsQ0FBQyxrQkFBa0IsR0FBRyxrQkFBa0IsQ0FBQTtZQUMxRCxDQUFDO1lBRUQsSUFBSSxtQkFBbUIsS0FBSyxTQUFTLEVBQUUsQ0FBQztnQkFDcEMsY0FBYyxDQUFDLG1CQUFtQixHQUFHLG1CQUFtQixDQUFBO1lBQzVELENBQUM7WUFFRCxJQUFJLGlCQUFpQixLQUFLLFNBQVMsRUFBRSxDQUFDO2dCQUNsQyxjQUFjLENBQUMsaUJBQWlCLEdBQUcsaUJBQWlCLENBQUE7WUFDeEQsQ0FBQztZQUVELElBQUksV0FBVyxLQUFLLFNBQVMsRUFBRSxDQUFDO2dCQUM1QixjQUFjLENBQUMsV0FBVyxHQUFHLFdBQVcsQ0FBQTtZQUM1QyxDQUFDO1lBRUQsSUFBSSxTQUFTLEtBQUssU0FBUyxFQUFFLENBQUM7Z0JBQzFCLGNBQWMsQ0FBQyxTQUFTLEdBQUcsU0FBUyxDQUFBO1lBQ3hDLENBQUM7WUFFRCxJQUFJLGFBQWEsS0FBSyxTQUFTLEVBQUUsQ0FBQztnQkFDOUIsY0FBYyxDQUFDLGFBQWEsR0FBRyxhQUFhLENBQUE7WUFDaEQsQ0FBQztZQUVELElBQUkscUJBQXFCLEtBQUssU0FBUyxFQUFFLENBQUM7Z0JBQ3RDLGNBQWMsQ0FBQyxxQkFBcUIsR0FBRyxxQkFBcUIsQ0FBQTtZQUNoRSxDQUFDO1lBRUQsSUFBSSxrQkFBa0IsS0FBSyxTQUFTLEVBQUUsQ0FBQztnQkFDbkMsY0FBYyxDQUFDLGtCQUFrQixHQUFHLGtCQUFrQixDQUFBO1lBQzFELENBQUM7WUFFRCxJQUFJLFVBQVUsS0FBSyxTQUFTLEVBQUUsQ0FBQztnQkFDM0IsY0FBYyxDQUFDLFVBQVUsR0FBRyxVQUFVLENBQUE7WUFDMUMsQ0FBQztZQUVELE9BQU8sQ0FBQyxHQUFHLENBQUMsY0FBYyxFQUFFLDBEQUEwRCxFQUFFLE1BQU0sRUFBRSxpQ0FBaUMsQ0FBQyxDQUFBO1lBRWxJLE1BQU0sTUFBTSxDQUFDLE1BQU0sQ0FBQztnQkFDaEIsUUFBUSxFQUFFLDRCQUE0QjtnQkFDdEMsU0FBUyxFQUFFO29CQUNQLGNBQWMsRUFBRSxjQUFjO2lCQUNqQzthQUNKLENBQUMsQ0FBQTtZQUVGLEtBQUssQ0FBQztnQkFDRixLQUFLLEVBQUUsU0FBUztnQkFDaEIsV0FBVyxFQUFFLHdCQUF3QjtnQkFDckMsTUFBTSxFQUFFLFNBQVM7Z0JBQ2pCLFFBQVEsRUFBRSxJQUFJO2dCQUNkLFVBQVUsRUFBRSxJQUFJO2FBQ25CLENBQUMsQ0FBQTtZQUVGLE1BQU0sQ0FBQyxJQUFJLEVBQUUsQ0FBQTtRQUNqQixDQUFDO1FBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztZQUNULE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLGdDQUFnQyxDQUFDLENBQUE7UUFDcEQsQ0FBQztJQUNMLENBQUMsQ0FBQTtJQUdELE1BQU0sWUFBWSxHQUFHLEdBQUcsRUFBRTtRQUN0QixNQUFNLGVBQWUsR0FBRyxXQUFXLENBQUE7UUFDbkMsTUFBTSxjQUFjLEdBQUcsZUFBZSxLQUFLLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxlQUFlLEdBQUcsQ0FBQyxDQUFBO1FBQ3RFLGNBQWMsQ0FBQyxjQUFjLENBQUMsQ0FBQTtJQUNsQyxDQUFDLENBQUE7SUFFRCxNQUFNLGdCQUFnQixHQUFHLEdBQUcsRUFBRTtRQUMxQixJQUFJLFdBQVcsS0FBSyxDQUFDLEVBQUUsQ0FBQztZQUNwQixPQUFPLHVCQUFDLGFBQUcsSUFBQyxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsR0FBRyxFQUFFLE1BQU0sRUFBRSxHQUFHLEVBQUUsR0FBRyxDQUFBO1FBQ2xELENBQUM7UUFFRCxPQUFPLENBQ0gsdUJBQUMsYUFBRyxJQUFDLEVBQUUsRUFBRSxFQUFFLEtBQUssRUFBRSxHQUFHLEVBQUUsTUFBTSxFQUFFLEdBQUcsRUFBRSxZQUNoQyx1QkFBQyxnQkFBTSxJQUFDLE9BQU8sRUFBRSxZQUFZLHFCQUVwQixHQUNQLENBQ1QsQ0FBQTtJQUNMLENBQUMsQ0FBQTtJQUVELE1BQU0sWUFBWSxHQUFHLEdBQUcsRUFBRTtRQUN0Qjs7Ozs7O1VBTUU7UUFFRixNQUFNLGVBQWUsR0FBRyxXQUFXLENBQUE7UUFDbkMsTUFBTSxpQkFBaUIsR0FBRyxhQUFhLENBQUE7UUFFdkMsSUFBSSxlQUFlLEtBQUssQ0FBQyxFQUFFLENBQUM7WUFDeEIsT0FBTTtRQUNWLENBQUM7UUFFRCxJQUFJLGNBQWMsR0FBRyxlQUFlLEdBQUcsQ0FBQyxDQUFBO1FBRXhDLElBQUksQ0FBQyxpQkFBaUIsSUFBSSxDQUFDLGlCQUFpQixHQUFHLGVBQWUsQ0FBQyxFQUFFLENBQUM7WUFDOUQsTUFBTSxnQkFBZ0IsR0FBRyxlQUFlLENBQUE7WUFDeEMsZ0JBQWdCLENBQUMsZ0JBQWdCLENBQUMsQ0FBQTtRQUN0QyxDQUFDO1FBRUQsSUFBSSxjQUFjLEtBQUssZUFBZSxFQUFFLENBQUM7WUFDckMsY0FBYyxDQUFDLGNBQWMsQ0FBQyxDQUFBO1FBQ2xDLENBQUM7SUFDTCxDQUFDLENBQUE7SUFFRCxNQUFNLGdCQUFnQixHQUFHLEdBQUcsRUFBRTtRQUMxQixJQUFJLFdBQVcsS0FBSyxDQUFDLEVBQUUsQ0FBQztZQUN4QixPQUFPLHVCQUFDLGFBQUcsSUFBQyxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsR0FBRyxFQUFFLE1BQU0sRUFBRSxHQUFHLEVBQUUsR0FBRyxDQUFBO1FBQzlDLENBQUM7UUFFRCxPQUFPLENBQ1AsdUJBQUMsYUFBRyxJQUFDLEVBQUUsRUFBRSxFQUFFLEtBQUssRUFBRSxHQUFHLEVBQUUsTUFBTSxFQUFFLEdBQUcsRUFBRSxZQUNoQyx1QkFBQyxnQkFBTSxJQUFDLE9BQU8sRUFBRSxZQUFZLHFCQUVwQixHQUNQLENBQ0wsQ0FBQTtJQUNMLENBQUMsQ0FBQTtJQUVELE1BQU0saUJBQWlCLEdBQUcsR0FBRyxFQUFFO1FBQzNCOzs7Ozs7VUFNRTtRQUVGLFFBQVEsV0FBVyxFQUFFLENBQUM7WUFDbEIsS0FBSyxDQUFDO2dCQUNGLE9BQU8sQ0FDSCx3QkFBQyxhQUFHLElBQUMsS0FBSyxFQUFFLEVBQUUsS0FBSyxFQUFFLE1BQU0sRUFBRSxFQUFFLElBQUksRUFBRSxDQUFDLEVBQUUsVUFBVSxFQUFDLFFBQVEsRUFBQyxjQUFjLEVBQUMsUUFBUSxhQUMvRSx1QkFBQyw2QkFBbUIsSUFDaEIsU0FBUyxFQUFFLFNBQVMsRUFDcEIsa0JBQWtCLEVBQUUsWUFBWSxHQUNsQyxFQUNGLHdCQUFDLGFBQUcsSUFBQyxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsR0FBRyxFQUFFLE1BQU0sRUFBRSxHQUFHLEVBQUUsRUFBRSxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsR0FBRyxFQUFFLE1BQU0sRUFBRSxHQUFHLEVBQUUsRUFBRSxLQUFLLEVBQUUsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLEVBQUUsYUFBYSxFQUFDLEtBQUssRUFBQyxjQUFjLEVBQUMsZUFBZSxFQUFDLFVBQVUsRUFBQyxRQUFRLGFBQ25LLHVCQUFDLGFBQUcsS0FBRyxFQUNOLGdCQUFnQixFQUFFLElBQ2pCLElBQ0osQ0FDVCxDQUFBO1lBQ0wsS0FBSyxDQUFDO2dCQUNGLE9BQU8sQ0FDSCx3QkFBQyxhQUFHLElBQUMsS0FBSyxFQUFFLEVBQUUsS0FBSyxFQUFFLE1BQU0sRUFBRSxFQUFFLElBQUksRUFBRSxDQUFDLEVBQUUsVUFBVSxFQUFDLFFBQVEsRUFBQyxjQUFjLEVBQUMsUUFBUSxhQUMvRSx1QkFBQyw2QkFBbUIsSUFDaEIsVUFBVSxFQUFFLFVBQVUsRUFDdEIsbUJBQW1CLEVBQUUsYUFBYSxFQUNsQyxRQUFRLEVBQUUsUUFBUSxFQUNsQixpQkFBaUIsRUFBRSxXQUFXLEdBQ2hDLEVBQ0Ysd0JBQUMsYUFBRyxJQUFDLEVBQUUsRUFBRSxFQUFFLEtBQUssRUFBRSxHQUFHLEVBQUUsTUFBTSxFQUFFLEdBQUcsRUFBRSxFQUFFLEVBQUUsRUFBRSxFQUFFLEtBQUssRUFBRSxHQUFHLEVBQUUsTUFBTSxFQUFFLEdBQUcsRUFBRSxFQUFFLEtBQUssRUFBRSxFQUFFLEtBQUssRUFBRSxNQUFNLEVBQUUsRUFBRSxhQUFhLEVBQUMsS0FBSyxFQUFDLGNBQWMsRUFBQyxlQUFlLEVBQUMsVUFBVSxFQUFDLFFBQVEsYUFDbEssZ0JBQWdCLEVBQUUsRUFDbEIsZ0JBQWdCLEVBQUUsSUFDakIsSUFDSixDQUNULENBQUE7WUFDTCxLQUFLLENBQUM7Z0JBQ0YsT0FBTyxDQUNILHdCQUFDLGFBQUcsSUFBQyxLQUFLLEVBQUUsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLEVBQUUsSUFBSSxFQUFFLENBQUMsRUFBRSxVQUFVLEVBQUMsUUFBUSxFQUFDLGNBQWMsRUFBQyxRQUFRLGFBQy9FLHVCQUFDLDZCQUFtQixJQUNoQixnQkFBZ0IsRUFBRSxnQkFBZ0IsRUFDbEMseUJBQXlCLEVBQUUsbUJBQW1CLEVBQzlDLGdCQUFnQixFQUFFLGdCQUFnQixFQUNsQyx5QkFBeUIsRUFBRSxtQkFBbUIsRUFDOUMsa0JBQWtCLEVBQUUsa0JBQWtCLEVBQ3RDLDJCQUEyQixFQUFFLHFCQUFxQixFQUNsRCxhQUFhLEVBQUUsYUFBYSxFQUM1QixzQkFBc0IsRUFBRSxnQkFBZ0IsRUFDeEMsaUJBQWlCLEVBQUUsaUJBQWlCLEVBQ3BDLDBCQUEwQixFQUFFLG9CQUFvQixFQUNoRCxjQUFjLEVBQUUsY0FBYyxFQUM5Qix1QkFBdUIsRUFBRSxpQkFBaUIsR0FDNUMsRUFDRix3QkFBQyxhQUFHLElBQUMsRUFBRSxFQUFFLEVBQUUsS0FBSyxFQUFFLEdBQUcsRUFBRSxNQUFNLEVBQUUsR0FBRyxFQUFFLEVBQUUsRUFBRSxFQUFFLEVBQUUsS0FBSyxFQUFFLEdBQUcsRUFBRSxNQUFNLEVBQUUsR0FBRyxFQUFFLEVBQUUsS0FBSyxFQUFFLEVBQUUsS0FBSyxFQUFFLE1BQU0sRUFBRSxFQUFFLGFBQWEsRUFBQyxLQUFLLEVBQUMsY0FBYyxFQUFDLGVBQWUsRUFBQyxVQUFVLEVBQUMsUUFBUSxhQUNsSyxnQkFBZ0IsRUFBRSxFQUNsQixnQkFBZ0IsRUFBRSxJQUNqQixJQUNKLENBQ1QsQ0FBQTtZQUNMLEtBQUssQ0FBQztnQkFDRixPQUFPLENBQ0gsd0JBQUMsYUFBRyxJQUFDLEtBQUssRUFBRSxFQUFFLEtBQUssRUFBRSxNQUFNLEVBQUUsRUFBRSxJQUFJLEVBQUUsQ0FBQyxFQUFFLFVBQVUsRUFBQyxRQUFRLEVBQUMsY0FBYyxFQUFDLFFBQVEsYUFDL0UsdUJBQUMsNkJBQW1CLElBQ2hCLGNBQWMsRUFBRSxjQUFjLEVBQzlCLHVCQUF1QixFQUFFLGlCQUFpQixFQUMxQyxXQUFXLEVBQUUsV0FBVyxFQUN4QixvQkFBb0IsRUFBRSxjQUFjLEVBQ3BDLGtCQUFrQixFQUFFLGtCQUFrQixFQUN0QywyQkFBMkIsRUFBRSxxQkFBcUIsRUFDbEQsaUJBQWlCLEVBQUUsaUJBQWlCLEVBQ3BDLDBCQUEwQixFQUFFLG9CQUFvQixFQUNoRCxXQUFXLEVBQUUsV0FBVyxFQUN4QixvQkFBb0IsRUFBRSxjQUFjLEdBQ3RDLEVBQ0Ysd0JBQUMsYUFBRyxJQUFDLEVBQUUsRUFBRSxFQUFFLEtBQUssRUFBRSxHQUFHLEVBQUUsTUFBTSxFQUFFLEdBQUcsRUFBRSxFQUFFLEVBQUUsRUFBRSxFQUFFLEtBQUssRUFBRSxHQUFHLEVBQUUsTUFBTSxFQUFFLEdBQUcsRUFBRSxFQUFFLEtBQUssRUFBRSxFQUFFLEtBQUssRUFBRSxNQUFNLEVBQUUsRUFBRSxhQUFhLEVBQUMsS0FBSyxFQUFDLGNBQWMsRUFBQyxlQUFlLEVBQUMsVUFBVSxFQUFDLFFBQVEsYUFDbEssZ0JBQWdCLEVBQUUsRUFDbEIsZ0JBQWdCLEVBQUUsSUFDakIsSUFDSixDQUNULENBQUE7WUFDTCxLQUFLLENBQUM7Z0JBQ0YsT0FBTyxDQUNILHdCQUFDLGFBQUcsSUFBQyxLQUFLLEVBQUUsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLEVBQUUsSUFBSSxFQUFFLENBQUMsRUFBRSxVQUFVLEVBQUMsUUFBUSxFQUFDLGNBQWMsRUFBQyxRQUFRLGFBQy9FLHVCQUFDLDZCQUFtQixJQUNoQixrQkFBa0IsRUFBRSxrQkFBa0IsRUFDdEMsMkJBQTJCLEVBQUUscUJBQXFCLEVBQ2xELGFBQWEsRUFBRSxhQUFhLEVBQzVCLHNCQUFzQixFQUFFLGdCQUFnQixFQUN4QyxxQkFBcUIsRUFBRSxxQkFBcUIsRUFDNUMsOEJBQThCLEVBQUUsd0JBQXdCLEVBQ3hELFNBQVMsRUFBRSxTQUFTLEVBQ3BCLGtCQUFrQixFQUFFLFlBQVksRUFDaEMsVUFBVSxFQUFFLFVBQVUsRUFDdEIsbUJBQW1CLEVBQUUsYUFBYSxHQUNwQyxFQUNGLHdCQUFDLGFBQUcsSUFBRSxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsR0FBRyxFQUFFLE1BQU0sRUFBRSxHQUFHLEVBQUUsRUFBRSxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsR0FBRyxFQUFFLE1BQU0sRUFBRSxHQUFHLEVBQUUsRUFBRSxLQUFLLEVBQUUsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLEVBQUUsYUFBYSxFQUFDLEtBQUssRUFBQyxjQUFjLEVBQUMsZUFBZSxFQUFDLFVBQVUsRUFBQyxRQUFRLGFBQ25LLGdCQUFnQixFQUFFLEVBQ2xCLGdCQUFnQixFQUFFLElBQ2pCLElBQ0osQ0FDVCxDQUFBO1lBQ0wsS0FBSyxDQUFDO2dCQUNGLE9BQU8sQ0FDSCx3QkFBQyxhQUFHLElBQUMsS0FBSyxFQUFFLEVBQUUsS0FBSyxFQUFFLE1BQU0sRUFBRSxFQUFFLElBQUksRUFBRSxDQUFDLEVBQUUsVUFBVSxFQUFDLFFBQVEsRUFBQyxjQUFjLEVBQUMsUUFBUSxhQUMvRSx3QkFBQyxhQUFHLElBQUMsY0FBYyxFQUFDLFFBQVEsRUFBQyxVQUFVLEVBQUMsUUFBUSxFQUFDLFNBQVMsRUFBQyxNQUFNLGFBQzdELHVCQUFDLGFBQUcsSUFBQyxLQUFLLEVBQUUsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLEVBQUUsQ0FBQyxFQUFFLEVBQUUsS0FBSyxFQUFFLEdBQUcsRUFBRSxNQUFNLEVBQUUsR0FBRyxFQUFFLEVBQUUsY0FBYyxFQUFDLFFBQVEsRUFBQyxVQUFVLEVBQUMsUUFBUSxZQUN0Ryx1QkFBQyxjQUFJLElBQUMsT0FBTyxFQUFDLGlCQUFpQixzQ0FFeEIsR0FDTCxFQUNOLHVCQUFDLGFBQUcsSUFBQyxjQUFjLEVBQUMsUUFBUSxFQUFDLFVBQVUsRUFBQyxRQUFRLEVBQUUsQ0FBQyxFQUFFLEVBQUUsS0FBSyxFQUFFLEdBQUcsRUFBRSxNQUFNLEVBQUUsR0FBRyxFQUFFLFlBQzVFLHVCQUFDLGdCQUFNLElBQUMsT0FBTyxFQUFFLG9CQUFvQix1QkFFNUIsR0FDUCxJQUNKLEVBQ04sdUJBQUMsYUFBRyxJQUFFLEVBQUUsRUFBRSxFQUFFLEtBQUssRUFBRSxHQUFHLEVBQUUsTUFBTSxFQUFFLEdBQUcsRUFBRSxFQUFFLEVBQUUsRUFBRSxFQUFFLEtBQUssRUFBRSxHQUFHLEVBQUUsTUFBTSxFQUFFLEdBQUcsRUFBRSxFQUFFLGFBQWEsRUFBQyxLQUFLLEVBQUMsY0FBYyxFQUFDLFlBQVksRUFBQyxLQUFLLEVBQUMsTUFBTSxZQUMvSCxnQkFBZ0IsRUFBRSxHQUNqQixJQUNKLENBQ1QsQ0FBQTtZQUNMO2dCQUNJLE9BQU8sQ0FDSCx1QkFBQyxhQUFHLElBQUMsY0FBYyxFQUFDLFFBQVEsRUFBQyxVQUFVLEVBQUMsUUFBUSxZQUM1Qyx1QkFBQyxxQkFBVyxjQUNaLHVCQUFDLGNBQUksSUFBQyxPQUFPLEVBQUMsUUFBUSw2Q0FFZixHQUNPLEdBQ1osQ0FDVCxDQUFBO1FBQ1QsQ0FBQztJQUNMLENBQUMsQ0FBQTtJQUVELE9BQU8sQ0FDSCx3QkFBQyxhQUFHLElBQUMsS0FBSyxFQUFFLEVBQUUsS0FBSyxFQUFFLE1BQU0sRUFBRSxFQUFFLElBQUksRUFBRSxDQUFDLEVBQUUsVUFBVSxFQUFDLFFBQVEsRUFBQyxjQUFjLEVBQUMsUUFBUSxhQUMvRSx1QkFBQyxnQkFBTSxJQUNILEtBQUssRUFBRTtvQkFDSDt3QkFDSSxLQUFLLEVBQUUsQ0FBQzt3QkFDUixLQUFLLEVBQUUsUUFBUTtxQkFDbEI7b0JBQ0Q7d0JBQ0ksS0FBSyxFQUFFLENBQUM7d0JBQ1IsS0FBSyxFQUFFLFFBQVE7cUJBQ2xCO29CQUNEO3dCQUNJLEtBQUssRUFBRSxDQUFDO3dCQUNSLEtBQUssRUFBRSxRQUFRO3FCQUNsQjtvQkFDRDt3QkFDSSxLQUFLLEVBQUUsQ0FBQzt3QkFDUixLQUFLLEVBQUUsUUFBUTtxQkFDbEI7b0JBQ0E7d0JBQ0csS0FBSyxFQUFFLENBQUM7d0JBQ1IsS0FBSyxFQUFFLFFBQVE7cUJBQ2xCO29CQUNBO3dCQUNHLEtBQUssRUFBRSxDQUFDO3dCQUNSLEtBQUssRUFBRSxrQkFBa0I7cUJBQzVCO2lCQUNKLEVBRUQsU0FBUyxFQUFFLGFBQWEsRUFDeEIsV0FBVyxFQUFFLFdBQVcsR0FDMUIsRUFDRCxpQkFBaUIsRUFBRSxJQUNsQixDQUNULENBQUE7QUFDTCxDQUFDO0FBR0Qsa0JBQWUsdUJBQXVCLENBQUEiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgUmVhY3QsIHtcbiAgdXNlU3RhdGUsXG4gIHVzZUVmZmVjdCxcbn0gZnJvbSAncmVhY3QnXG5cbmltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50J1xuaW1wb3J0IHsgdXNlVG9hc3QgfSBmcm9tICdAY2hha3JhLXVpL3JlYWN0J1xuaW1wb3J0IEJveCBmcm9tICdAY29tcG9uZW50cy9jb21tb24vQm94J1xuaW1wb3J0IFRleHQgZnJvbSAnQGNvbXBvbmVudHMvY29tbW9uL1RleHQnXG5pbXBvcnQgeyBFbmRUaW1lVHlwZSwgU3RhcnRUaW1lVHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL1VzZXJfUHJlZmVyZW5jZVR5cGUnXG5cbmltcG9ydCBFZGl0UHJlZmVyZW5jZVN0ZXAxIGZyb20gJ0BwYWdlcy9TZXR0aW5ncy9Vc2VyUHJlZmVyZW5jZVdpemFyZC9FZGl0UHJlZmVyZW5jZVN0ZXAxJ1xuaW1wb3J0IEVkaXRQcmVmZXJlbmNlU3RlcDIgZnJvbSAnQHBhZ2VzL1NldHRpbmdzL1VzZXJQcmVmZXJlbmNlV2l6YXJkL0VkaXRQcmVmZXJlbmNlU3RlcDInXG5pbXBvcnQgRWRpdFByZWZlcmVuY2VTdGVwMyBmcm9tICdAcGFnZXMvU2V0dGluZ3MvVXNlclByZWZlcmVuY2VXaXphcmQvRWRpdFByZWZlcmVuY2VTdGVwMydcbmltcG9ydCBFZGl0UHJlZmVyZW5jZVN0ZXA1IGZyb20gJ0BwYWdlcy9TZXR0aW5ncy9Vc2VyUHJlZmVyZW5jZVdpemFyZC9FZGl0UHJlZmVyZW5jZVN0ZXA1J1xuaW1wb3J0IEVkaXRQcmVmZXJlbmNlU3RlcDYgZnJvbSAnQHBhZ2VzL1NldHRpbmdzL1VzZXJQcmVmZXJlbmNlV2l6YXJkL0VkaXRQcmVmZXJlbmNlU3RlcDYnXG5pbXBvcnQgXyBmcm9tICdsb2Rhc2gnXG5pbXBvcnQgQnV0dG9uIGZyb20gJ0Bjb21wb25lbnRzL0J1dHRvbidcbmltcG9ydCBXaXphcmQgZnJvbSAnQGNvbXBvbmVudHMvV2l6YXJkJ1xuaW1wb3J0IFJlZ3VsYXJDYXJkIGZyb20gJ0Bjb21wb25lbnRzL1JlZ3VsYXJDYXJkJ1xuaW1wb3J0IHsgZ2V0VXNlclByZWZlcmVuY2UgfSBmcm9tICdAbGliL09uQm9hcmQvT25Cb2FyZEhlbHBlcjInXG5pbXBvcnQgeyB1c2VBcHBDb250ZXh0IH0gZnJvbSAnQGxpYi91c2VyLWNvbnRleHQnXG5cbmltcG9ydCB7IHVzZVJvdXRlciB9IGZyb20gJ25leHQvcm91dGVyJ1xuXG5jb25zdCBERUZBVUxUX1NUQVJUX1RJTUVTID0gW1xuICAgIHtcbiAgICAgICAgZGF5OiAxLFxuICAgICAgICBob3VyOiA3LFxuICAgICAgICBtaW51dGVzOiAwLFxuICAgIH0sXG4gICAge1xuICAgICAgICBkYXk6IDIsXG4gICAgICAgIGhvdXI6IDcsXG4gICAgICAgIG1pbnV0ZXM6IDAsXG4gICAgfSxcbiAgICB7XG4gICAgICAgIGRheTogMyxcbiAgICAgICAgaG91cjogNyxcbiAgICAgICAgbWludXRlczogMCxcbiAgICB9LFxuICAgIHtcbiAgICAgICAgZGF5OiA0LFxuICAgICAgICBob3VyOiA3LFxuICAgICAgICBtaW51dGVzOiAwLCAgXG4gICAgfSxcbiAgICB7XG4gICAgICAgIGRheTogNSxcbiAgICAgICAgaG91cjogNyxcbiAgICAgICAgbWludXRlczogMCwgIFxuICAgIH0sXG4gICAge1xuICAgICAgICBkYXk6IDYsXG4gICAgICAgIGhvdXI6IDcsXG4gICAgICAgIG1pbnV0ZXM6IDAsXG4gICAgfSxcbiAgICB7XG4gICAgICAgIGRheTogNyxcbiAgICAgICAgaG91cjogNyxcbiAgICAgICAgbWludXRlczogMCxcbiAgICB9XG5dXG5cbmNvbnN0IERFRkFVTFRfRU5EX1RJTUVTID0gW1xuICAgIHtcbiAgICAgICAgZGF5OiAxLFxuICAgICAgICBob3VyOiAxOSxcbiAgICAgICAgbWludXRlczogMCxcbiAgICB9LFxuICAgIHtcbiAgICAgICAgZGF5OiAyLFxuICAgICAgICBob3VyOiAxOSxcbiAgICAgICAgbWludXRlczogMCxcbiAgICB9LFxuICAgIHtcbiAgICAgICAgZGF5OiAzLFxuICAgICAgICBob3VyOiAxOSxcbiAgICAgICAgbWludXRlczogMCxcbiAgICB9LFxuICAgIHtcbiAgICAgICAgZGF5OiA0LFxuICAgICAgICBob3VyOiAxOSxcbiAgICAgICAgbWludXRlczogMCxcbiAgICB9LFxuICAgIHtcbiAgICAgICAgZGF5OiA1LFxuICAgICAgICBob3VyOiAxOSxcbiAgICAgICAgbWludXRlczogMCxcbiAgICB9LFxuICAgIHtcbiAgICAgICAgZGF5OiA2LFxuICAgICAgICBob3VyOiAxOSxcbiAgICAgICAgbWludXRlczogMCxcbiAgICB9LFxuICAgIHtcbiAgICAgICAgZGF5OiA3LFxuICAgICAgICBob3VyOiAxOSxcbiAgICAgICAgbWludXRlczogMCxcbiAgICB9XG5dXG5cbmltcG9ydCB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCBzdXBlcnRva2Vuc05vZGUgZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZSdcbmltcG9ydCB7IGJhY2tlbmRDb25maWcgfSBmcm9tICdAY29uZmlnL2JhY2tlbmRDb25maWcnXG5pbXBvcnQgU2Vzc2lvbiBmcm9tICdzdXBlcnRva2Vucy1ub2RlL3JlY2lwZS9zZXNzaW9uJ1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0U2VydmVyU2lkZVByb3BzKHsgcmVxLCByZXMgfTogeyByZXE6IE5leHRBcGlSZXF1ZXN0LCByZXM6IE5leHRBcGlSZXNwb25zZSB9KSB7XG4gICAgLy8gTm90aWNlIGhvdyB0aGUgc2VydmVyIHVzZXMgYEFQSWAgZnJvbSBgd2l0aFNTUkNvbnRleHRgLCBpbnN0ZWFkIG9mIHRoZSB0b3AtbGV2ZWwgYEFQSWAuXG4gICAgLy8gY29uc3QgU1NSID0gd2l0aFNTUkNvbnRleHQoeyByZXEgfSlcbiAgICAvLyB0aGlzIHJ1bnMgb24gdGhlIGJhY2tlbmQsIHNvIHdlIG11c3QgY2FsbCBpbml0IG9uIHN1cGVydG9rZW5zLW5vZGUgU0RLXG4gICAgc3VwZXJ0b2tlbnNOb2RlLmluaXQoYmFja2VuZENvbmZpZygpKVxuICAgIGxldCBzZXNzaW9uXG4gICAgdHJ5IHtcbiAgICAgICAgc2Vzc2lvbiA9IGF3YWl0IFNlc3Npb24uZ2V0U2Vzc2lvbihyZXEsIHJlcywge1xuICAgICAgICAgICAgb3ZlcnJpZGVHbG9iYWxDbGFpbVZhbGlkYXRvcnM6IGFzeW5jIGZ1bmN0aW9uICgpIHtcbiAgICAgICAgICAgICAgICByZXR1cm4gW11cbiAgICAgICAgICAgIH0sXG4gICAgICAgIH0pXG4gICAgfSBjYXRjaCAoZXJyOiBhbnkpIHtcbiAgICAgICAgaWYgKGVyci50eXBlID09PSBTZXNzaW9uLkVycm9yLlRSWV9SRUZSRVNIX1RPS0VOKSB7XG4gICAgICAgICAgICByZXR1cm4geyBwcm9wczogeyBmcm9tU3VwZXJ0b2tlbnM6ICduZWVkcy1yZWZyZXNoJyB9IH1cbiAgICAgICAgfSBlbHNlIGlmIChlcnIudHlwZSA9PT0gU2Vzc2lvbi5FcnJvci5VTkFVVEhPUklTRUQpIHtcbiAgICAgICAgICAgIC8vIHRoaXMgd2lsbCBmb3JjZSB0aGUgZnJvbnRlbmQgdG8gdHJ5IGFuZCByZWZyZXNoIHdoaWNoIHdpbGwgZmFpbFxuICAgICAgICAgICAgLy8gY2xlYXJpbmcgYWxsIGNvb2tpZXMgYW5kIHJlZGlyZWN0aW5nIHRoZSB1c2VyIHRvIHRoZSBsb2dpbiBzY3JlZW4uXG4gICAgICAgICAgICByZXR1cm4geyBwcm9wczogeyBmcm9tU3VwZXJ0b2tlbnM6ICduZWVkcy1yZWZyZXNoJyB9IH1cbiAgICAgICAgfVxuICAgICAgICB0aHJvdyBlcnJcbiAgICB9XG5cbiAgICBpZiAoIXNlc3Npb24/LmdldFVzZXJJZCgpKSB7XG4gICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICByZWRpcmVjdDoge1xuICAgICAgICAgICAgICAgIGRlc3RpbmF0aW9uOiAnL1VzZXIvTG9naW4vVXNlckxvZ2luJyxcbiAgICAgICAgICAgICAgICBwZXJtYW5lbnQ6IGZhbHNlLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgfVxuICAgIH1cblxuICAgIHJldHVybiB7XG4gICAgICAgIHByb3BzOiB7XG4gICAgICAgIHN1Yjogc2Vzc2lvbi5nZXRVc2VySWQoKSxcbiAgICAgICAgfVxuICAgIH1cbn1cblxuZnVuY3Rpb24gVXNlckNhbGVuZGFyUHJlZmVyZW5jZXMoKSB7XG4gICAgY29uc3QgW3JlbWluZGVycywgc2V0UmVtaW5kZXJzXSA9IHVzZVN0YXRlPG51bWJlcltdPihbXSlcbiAgICBjb25zdCBbc3RhcnRUaW1lcywgc2V0U3RhcnRUaW1lc10gPSB1c2VTdGF0ZTxTdGFydFRpbWVUeXBlW10+KFtdKVxuICAgIGNvbnN0IFtlbmRUaW1lcywgc2V0RW5kVGltZXNdID0gdXNlU3RhdGU8RW5kVGltZVR5cGVbXT4oW10pXG4gICAgY29uc3QgW2NvcHlBdmFpbGFiaWxpdHksIHNldENvcHlBdmFpbGFiaWxpdHldID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gICAgY29uc3QgW2NvcHlUaW1lQmxvY2tpbmcsIHNldENvcHlUaW1lQmxvY2tpbmddID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gICAgY29uc3QgW2NvcHlUaW1lUHJlZmVyZW5jZSwgc2V0Q29weVRpbWVQcmVmZXJlbmNlXSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKVxuICAgIGNvbnN0IFtjb3B5UmVtaW5kZXJzLCBzZXRDb3B5UmVtaW5kZXJzXSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKVxuICAgIGNvbnN0IFtjb3B5UHJpb3JpdHlMZXZlbCwgc2V0Q29weVByaW9yaXR5TGV2ZWxdID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gICAgY29uc3QgW2NvcHlNb2RpZmlhYmxlLCBzZXRDb3B5TW9kaWZpYWJsZV0gPSB1c2VTdGF0ZTxib29sZWFuPihmYWxzZSlcbiAgICBjb25zdCBbY29weUNhdGVnb3JpZXMsIHNldENvcHlDYXRlZ29yaWVzXSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKVxuICAgIGNvbnN0IFtjb3B5SXNCcmVhaywgc2V0Q29weUlzQnJlYWtdID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gICAgY29uc3QgW21heFdvcmtMb2FkUGVyY2VudCwgc2V0TWF4V29ya0xvYWRQZXJjZW50XSA9IHVzZVN0YXRlPG51bWJlcj4oODUpXG4gICAgY29uc3QgW21pbk51bWJlck9mQnJlYWtzLCBzZXRNaW5OdW1iZXJPZkJyZWFrc10gPSB1c2VTdGF0ZTxudW1iZXI+KClcbiAgICBjb25zdCBbYnJlYWtMZW5ndGgsIHNldEJyZWFrTGVuZ3RoXSA9IHVzZVN0YXRlPG51bWJlcj4oKVxuICAgIGNvbnN0IFtiYWNrVG9CYWNrTWVldGluZ3MsIHNldEJhY2tUb0JhY2tNZWV0aW5nc10gPSB1c2VTdGF0ZTxib29sZWFuPihmYWxzZSlcbiAgICBjb25zdCBbbWF4TnVtYmVyT2ZNZWV0aW5ncywgc2V0TWF4TnVtYmVyT2ZNZWV0aW5nc10gPSB1c2VTdGF0ZTxudW1iZXI+KDYpXG4gICAgY29uc3QgW2NvcHlJc01lZXRpbmcsIHNldENvcHlJc01lZXRpbmddID0gdXNlU3RhdGU8Ym9vbGVhbj4oZmFsc2UpXG4gICAgY29uc3QgW2NvcHlJc0V4dGVybmFsTWVldGluZywgc2V0Q29weUlzRXh0ZXJuYWxNZWV0aW5nXSA9IHVzZVN0YXRlPGJvb2xlYW4+KGZhbHNlKVxuICAgIGNvbnN0IFtjb3B5Q29sb3IsIHNldENvcHlDb2xvcl0gPSB1c2VTdGF0ZTxib29sZWFuPihmYWxzZSlcbiAgICBjb25zdCBbYWN0aXZlSW5kZXgsIHNldEFjdGl2ZUluZGV4XSA9IHVzZVN0YXRlPG51bWJlcj4oMClcbiAgICBjb25zdCBbY29tcGxldGVkU3RlcCwgc2V0Q29tcGxldGVkU3RlcF0gPSB1c2VTdGF0ZTxudW1iZXIgfCB1bmRlZmluZWQ+KClcbiAgICBjb25zdCBbYnJlYWtDb2xvciwgc2V0QnJlYWtDb2xvcl0gPSB1c2VTdGF0ZTxzdHJpbmc+KClcblxuICAgIGNvbnN0IHJvdXRlciA9IHVzZVJvdXRlcigpXG4gICAgY29uc3QgeyBzdWIsIGNsaWVudCB9ID0gdXNlQXBwQ29udGV4dCgpXG4gICAgY29uc3QgdXNlcklkID0gc3ViXG4gICAgY29uc3QgdG9hc3QgPSB1c2VUb2FzdCgpXG4gICAgXG4gICAgLy8gZ2V0IHVzZXIgcHJlZmVyZW5jZXNcbiAgICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgICAgICAoYXN5bmMgKCkgPT4ge1xuICAgICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgICAgICBjb25zdCBleGlzdGluZ3VzZXJfcHJlZmVyZW5jZXMgPSBhd2FpdCBnZXRVc2VyUHJlZmVyZW5jZShjbGllbnQsIHVzZXJJZClcbiAgICAgICAgICAgICAgICBzZXRSZW1pbmRlcnMoZXhpc3Rpbmd1c2VyX3ByZWZlcmVuY2VzPy5yZW1pbmRlcnMpXG4gICAgICAgICAgICAgICAgc2V0U3RhcnRUaW1lcygoZXhpc3Rpbmd1c2VyX3ByZWZlcmVuY2VzPy5zdGFydFRpbWVzIGFzIFN0YXJ0VGltZVR5cGVbXSkgfHwgKERFRkFVTFRfU1RBUlRfVElNRVMgYXMgU3RhcnRUaW1lVHlwZVtdKSlcbiAgICAgICAgICAgICAgICBzZXRFbmRUaW1lcygoZXhpc3Rpbmd1c2VyX3ByZWZlcmVuY2VzPy5lbmRUaW1lcyBhcyBFbmRUaW1lVHlwZVtdKSB8fCAoREVGQVVMVF9FTkRfVElNRVMgYXMgRW5kVGltZVR5cGVbXSkpXG4gICAgICAgICAgICAgICAgc2V0Q29weUF2YWlsYWJpbGl0eShleGlzdGluZ3VzZXJfcHJlZmVyZW5jZXM/LmNvcHlBdmFpbGFiaWxpdHkpXG4gICAgICAgICAgICAgICAgc2V0Q29weVRpbWVCbG9ja2luZyhleGlzdGluZ3VzZXJfcHJlZmVyZW5jZXM/LmNvcHlUaW1lQmxvY2tpbmcpXG4gICAgICAgICAgICAgICAgc2V0Q29weVRpbWVQcmVmZXJlbmNlKGV4aXN0aW5ndXNlcl9wcmVmZXJlbmNlcz8uY29weVRpbWVQcmVmZXJlbmNlKVxuICAgICAgICAgICAgICAgIHNldENvcHlSZW1pbmRlcnMoZXhpc3Rpbmd1c2VyX3ByZWZlcmVuY2VzPy5jb3B5UmVtaW5kZXJzKVxuICAgICAgICAgICAgICAgIHNldENvcHlQcmlvcml0eUxldmVsKGV4aXN0aW5ndXNlcl9wcmVmZXJlbmNlcz8uY29weVByaW9yaXR5TGV2ZWwpXG4gICAgICAgICAgICAgICAgc2V0Q29weU1vZGlmaWFibGUoZXhpc3Rpbmd1c2VyX3ByZWZlcmVuY2VzPy5jb3B5TW9kaWZpYWJsZSlcbiAgICAgICAgICAgICAgICBzZXRDb3B5Q2F0ZWdvcmllcyhleGlzdGluZ3VzZXJfcHJlZmVyZW5jZXM/LmNvcHlDYXRlZ29yaWVzKVxuICAgICAgICAgICAgICAgIHNldENvcHlJc0JyZWFrKGV4aXN0aW5ndXNlcl9wcmVmZXJlbmNlcz8uY29weUlzQnJlYWspXG4gICAgICAgICAgICAgICAgc2V0TWF4V29ya0xvYWRQZXJjZW50KGV4aXN0aW5ndXNlcl9wcmVmZXJlbmNlcz8ubWF4V29ya0xvYWRQZXJjZW50IHx8IDg1KVxuICAgICAgICAgICAgICAgIHNldE1pbk51bWJlck9mQnJlYWtzKGV4aXN0aW5ndXNlcl9wcmVmZXJlbmNlcz8ubWluTnVtYmVyT2ZCcmVha3MgfHwgMSlcbiAgICAgICAgICAgICAgICBzZXRCcmVha0xlbmd0aChleGlzdGluZ3VzZXJfcHJlZmVyZW5jZXM/LmJyZWFrTGVuZ3RoIHx8IDMwKVxuICAgICAgICAgICAgICAgIHNldEJhY2tUb0JhY2tNZWV0aW5ncyhleGlzdGluZ3VzZXJfcHJlZmVyZW5jZXM/LmJhY2tUb0JhY2tNZWV0aW5ncylcbiAgICAgICAgICAgICAgICBzZXRNYXhOdW1iZXJPZk1lZXRpbmdzKGV4aXN0aW5ndXNlcl9wcmVmZXJlbmNlcz8ubWF4TnVtYmVyT2ZNZWV0aW5ncylcbiAgICAgICAgICAgICAgICBzZXRDb3B5SXNNZWV0aW5nKGV4aXN0aW5ndXNlcl9wcmVmZXJlbmNlcz8uY29weUlzTWVldGluZylcbiAgICAgICAgICAgICAgICBzZXRDb3B5SXNFeHRlcm5hbE1lZXRpbmcoZXhpc3Rpbmd1c2VyX3ByZWZlcmVuY2VzPy5jb3B5SXNFeHRlcm5hbE1lZXRpbmcpXG4gICAgICAgICAgICAgICAgc2V0Q29weUNvbG9yKGV4aXN0aW5ndXNlcl9wcmVmZXJlbmNlcz8uY29weUNvbG9yKVxuICAgICAgICAgICAgICAgIHNldEJyZWFrQ29sb3IoZXhpc3Rpbmd1c2VyX3ByZWZlcmVuY2VzPy5icmVha0NvbG9yIHx8ICcjRjdFQkY3JylcbiAgICAgICAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgICAgICAgICBjb25zb2xlLmxvZyhlLCAnIGVycm9yIGluIHVzZUVmZmVjdCBmb3IgVXNlckNhbGVuZGFyUHJlZmVyZW5jZXMnKVxuICAgICAgICAgICAgfVxuICAgICAgICB9KSgpXG4gICAgfSwgW2NsaWVudCwgdXNlcklkXSlcblxuICAgIC8vIHNhdmUgdXNlciBwcmVmZXJlbmNlc1xuICAgIGNvbnN0IHNhdmV1c2VyX3ByZWZlcmVuY2VzID0gYXN5bmMgKCkgPT4ge1xuICAgICAgICB0cnkge1xuICAgICAgICAgICAgLy8gdmFsaWRhdGVcbiAgICAgICAgICAgIGlmIChtYXhXb3JrTG9hZFBlcmNlbnQgPCAwIHx8IG1heFdvcmtMb2FkUGVyY2VudCA+IDEwMCkge1xuICAgICAgICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgICAgICAgICAgdGl0bGU6ICdJbnZhbGlkIG1heCB3b3JrIGxvYWQgcGVyY2VudCcsXG4gICAgICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnTWF4IHdvcmsgbG9hZCBwZXJjZW50IG11c3QgYmUgYmV0d2VlbiAwIGFuZCAxMDAnLFxuICAgICAgICAgICAgICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGlmIChtaW5OdW1iZXJPZkJyZWFrcyA8IDApIHtcbiAgICAgICAgICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgICAgICAgICAgIHRpdGxlOiAnSW52YWxpZCBtaW4gbnVtYmVyIG9mIGJyZWFrcycsXG4gICAgICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnTWluIG51bWJlciBvZiBicmVha3MgbXVzdCBiZSBncmVhdGVyIHRoYW4gMCcsXG4gICAgICAgICAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICAgICAgICAgICAgfSlcbiAgICAgICAgICAgICAgICByZXR1cm5cbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgaWYgKChtaW5OdW1iZXJPZkJyZWFrcyA+IDApICYmIChicmVha0xlbmd0aCA8PSAwKSkge1xuICAgICAgICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgICAgICAgICAgdGl0bGU6ICdJbnZhbGlkIGJyZWFrIGxlbmd0aCcsXG4gICAgICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnQnJlYWsgbGVuZ3RoIG11c3QgYmUgZ3JlYXRlciB0aGFuIDAnLFxuICAgICAgICAgICAgICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGlmIChtYXhOdW1iZXJPZk1lZXRpbmdzIDwgMCkge1xuICAgICAgICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgICAgICAgICAgdGl0bGU6ICdJbnZhbGlkIG1heCBudW1iZXIgb2YgbWVldGluZ3MnLFxuICAgICAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogJ01heCBudW1iZXIgb2YgbWVldGluZ3MgbXVzdCBiZSBncmVhdGVyIHRoYW4gMCcsXG4gICAgICAgICAgICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICAgICAgICAgICAgfSlcbiAgICAgICAgICAgICAgICByZXR1cm5cbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgLy8gc2F2ZVxuICAgICAgICAgICAgY29uc3QgZXhpc3Rpbmd1c2VyX3ByZWZlcmVuY2VzID0gYXdhaXQgZ2V0VXNlclByZWZlcmVuY2UoY2xpZW50LCB1c2VySWQpXG4gICAgICAgICAgICBpZiAoIWV4aXN0aW5ndXNlcl9wcmVmZXJlbmNlcykge1xuICAgICAgICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgICAgICAgICAgdGl0bGU6ICdFcnJvcicsXG4gICAgICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnRXJyb3Igc2F2aW5nIHVzZXIgcHJlZmVyZW5jZXMnLFxuICAgICAgICAgICAgICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICAgICAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGNvbnN0IHVwc2VydFVzZXJQcmVmZXJlbmNlTXV0YXRpb24gPSBncWxgXG4gICAgICAgICAgICAgICAgbXV0YXRpb24gSW5zZXJ0VXNlclByZWZlcmVuY2UoJHVzZXJQcmVmZXJlbmNlOiBVc2VyX1ByZWZlcmVuY2VfaW5zZXJ0X2lucHV0ISkge1xuICAgICAgICAgICAgICAgICAgICBpbnNlcnRfVXNlcl9QcmVmZXJlbmNlX29uZShcbiAgICAgICAgICAgICAgICAgICAgICAgIG9iamVjdDogJHVzZXJQcmVmZXJlbmNlLFxuICAgICAgICAgICAgICAgICAgICAgICAgb25fY29uZmxpY3Q6IHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvbnN0cmFpbnQ6IFVzZXJQcmVmZXJlbmNlX3BrZXksXG4gICAgICAgICAgICAgICAgICAgICAgICB1cGRhdGVfY29sdW1uczogW1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICR7KHJlbWluZGVycz8ubGVuZ3RoID4gMClcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgJiYgIV8uaXNFcXVhbChyZW1pbmRlcnMsIGV4aXN0aW5ndXNlcl9wcmVmZXJlbmNlcz8ucmVtaW5kZXJzKSA/ICdyZW1pbmRlcnMsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICR7KHN0YXJ0VGltZXM/Lmxlbmd0aCA+IDApXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICYmICFfLmlzRXF1YWwoc3RhcnRUaW1lcywgZXhpc3Rpbmd1c2VyX3ByZWZlcmVuY2VzPy5zdGFydFRpbWVzKSA/ICdzdGFydFRpbWVzLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAkeyhlbmRUaW1lcz8ubGVuZ3RoID4gMClcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgJiYgIV8uaXNFcXVhbChlbmRUaW1lcywgZXhpc3Rpbmd1c2VyX3ByZWZlcmVuY2VzPy5lbmRUaW1lcykgPyAnZW5kVGltZXMsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICR7Y29weUF2YWlsYWJpbGl0eSAhPT0gdW5kZWZpbmVkID8gJ2NvcHlBdmFpbGFiaWxpdHksJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICR7Y29weVRpbWVCbG9ja2luZyAhPT0gdW5kZWZpbmVkID8gJ2NvcHlUaW1lQmxvY2tpbmcsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICR7Y29weVRpbWVQcmVmZXJlbmNlICE9PSB1bmRlZmluZWQgPyAnY29weVRpbWVQcmVmZXJlbmNlLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAke2NvcHlSZW1pbmRlcnMgIT09IHVuZGVmaW5lZCA/ICdjb3B5UmVtaW5kZXJzLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAke2NvcHlQcmlvcml0eUxldmVsICE9PSB1bmRlZmluZWQgPyAnY29weVByaW9yaXR5TGV2ZWwsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICR7Y29weU1vZGlmaWFibGUgIT09IHVuZGVmaW5lZCA/ICdjb3B5TW9kaWZpYWJsZSwnIDogJyd9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgJHtjb3B5Q2F0ZWdvcmllcyAhPT0gdW5kZWZpbmVkID8gJ2NvcHlDYXRlZ29yaWVzLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAke2NvcHlJc0JyZWFrICE9PSB1bmRlZmluZWQgPyAnY29weUlzQnJlYWssJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICR7bWF4V29ya0xvYWRQZXJjZW50ICE9PSB1bmRlZmluZWQgPyAnbWF4V29ya0xvYWRQZXJjZW50LCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAke21heE51bWJlck9mTWVldGluZ3MgIT09IHVuZGVmaW5lZCA/ICdtYXhOdW1iZXJPZk1lZXRpbmdzLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAke21pbk51bWJlck9mQnJlYWtzICE9PSB1bmRlZmluZWQgPyAnbWluTnVtYmVyT2ZCcmVha3MsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICR7YnJlYWtMZW5ndGggIT09IHVuZGVmaW5lZCA/ICdicmVha0xlbmd0aCwnIDogJyd9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgJHtjb3B5Q29sb3IgIT09IHVuZGVmaW5lZCA/ICdjb3B5Q29sb3IsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICR7Y29weUlzTWVldGluZyAhPT0gdW5kZWZpbmVkID8gJ2NvcHlJc01lZXRpbmcsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICR7Y29weUlzRXh0ZXJuYWxNZWV0aW5nICE9PSB1bmRlZmluZWQgPyAnY29weUlzRXh0ZXJuYWxNZWV0aW5nLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAke2JhY2tUb0JhY2tNZWV0aW5ncyAhPT0gdW5kZWZpbmVkID8gJ2JhY2tUb0JhY2tNZWV0aW5ncywnIDogJyd9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgJHticmVha0NvbG9yICE9PSB1bmRlZmluZWQgPyAnYnJlYWtDb2xvciwnIDogJyd9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0LFxuICAgICAgICAgICAgICAgICAgICAgICAgXVxuICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICApIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgICAgICByZW1pbmRlcnNcbiAgICAgICAgICAgICAgICAgICAgICAgIGZvbGxvd1VwXG4gICAgICAgICAgICAgICAgICAgICAgICBpc1B1YmxpY0NhbGVuZGFyXG4gICAgICAgICAgICAgICAgICAgICAgICBwdWJsaWNDYWxlbmRhckNhdGVnb3JpZXNcbiAgICAgICAgICAgICAgICAgICAgICAgIHN0YXJ0VGltZXNcbiAgICAgICAgICAgICAgICAgICAgICAgIGVuZFRpbWVzXG4gICAgICAgICAgICAgICAgICAgICAgICBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICAgICAgICAgICAgICAgICAgICBjb3B5VGltZUJsb2NraW5nXG4gICAgICAgICAgICAgICAgICAgICAgICBjb3B5VGltZVByZWZlcmVuY2VcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlSZW1pbmRlcnNcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlQcmlvcml0eUxldmVsXG4gICAgICAgICAgICAgICAgICAgICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICAgICAgY29weUNhdGVnb3JpZXNcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlJc0JyZWFrXG4gICAgICAgICAgICAgICAgICAgICAgICBtYXhXb3JrTG9hZFBlcmNlbnRcbiAgICAgICAgICAgICAgICAgICAgICAgIGJhY2tUb0JhY2tNZWV0aW5nc1xuICAgICAgICAgICAgICAgICAgICAgICAgbWF4TnVtYmVyT2ZNZWV0aW5nc1xuICAgICAgICAgICAgICAgICAgICAgICAgbWluTnVtYmVyT2ZCcmVha3NcbiAgICAgICAgICAgICAgICAgICAgICAgIGJyZWFrTGVuZ3RoXG4gICAgICAgICAgICAgICAgICAgICAgICBicmVha0NvbG9yXG4gICAgICAgICAgICAgICAgICAgICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgICAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlDb2xvclxuICAgICAgICAgICAgICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9YFxuICAgICAgICAgICAgXG4gICAgICAgICAgICBjb25zdCB2YWx1ZXNUb1Vwc2VydDogYW55ID0ge1xuICAgICAgICAgICAgICAgIGlkOiBleGlzdGluZ3VzZXJfcHJlZmVyZW5jZXM/LmlkLFxuICAgICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgaWYgKChyZW1pbmRlcnM/Lmxlbmd0aCA+IDApXG4gICAgICAgICAgICAgICAgJiYgIV8uaXNFcXVhbChyZW1pbmRlcnMsIGV4aXN0aW5ndXNlcl9wcmVmZXJlbmNlcz8ucmVtaW5kZXJzKSkge1xuICAgICAgICAgICAgICAgIHZhbHVlc1RvVXBzZXJ0LnJlbWluZGVycyA9IHJlbWluZGVyc1xuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBpZiAoKHN0YXJ0VGltZXM/Lmxlbmd0aCA+IDApXG4gICAgICAgICAgICAgICAgJiYgIV8uaXNFcXVhbChzdGFydFRpbWVzLCBleGlzdGluZ3VzZXJfcHJlZmVyZW5jZXM/LnN0YXJ0VGltZXMpKSB7XG4gICAgICAgICAgICAgICAgdmFsdWVzVG9VcHNlcnQuc3RhcnRUaW1lcyA9IHN0YXJ0VGltZXNcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgaWYgKChlbmRUaW1lcz8ubGVuZ3RoID4gMClcbiAgICAgICAgICAgICAgICAmJiAhXy5pc0VxdWFsKGVuZFRpbWVzLCBleGlzdGluZ3VzZXJfcHJlZmVyZW5jZXM/LmVuZFRpbWVzKSkge1xuICAgICAgICAgICAgICAgIHZhbHVlc1RvVXBzZXJ0LmVuZFRpbWVzID0gZW5kVGltZXNcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgaWYgKGNvcHlBdmFpbGFiaWxpdHkgIT09IHVuZGVmaW5lZCkge1xuICAgICAgICAgICAgICAgIHZhbHVlc1RvVXBzZXJ0LmNvcHlBdmFpbGFiaWxpdHkgPSBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGlmIChjb3B5VGltZUJsb2NraW5nICE9PSB1bmRlZmluZWQpIHtcbiAgICAgICAgICAgICAgICB2YWx1ZXNUb1Vwc2VydC5jb3B5VGltZUJsb2NraW5nID0gY29weVRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBpZiAoY29weVRpbWVQcmVmZXJlbmNlICE9PSB1bmRlZmluZWQpIHtcbiAgICAgICAgICAgICAgICB2YWx1ZXNUb1Vwc2VydC5jb3B5VGltZVByZWZlcmVuY2UgPSBjb3B5VGltZVByZWZlcmVuY2VcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgaWYgKGNvcHlSZW1pbmRlcnMgIT09IHVuZGVmaW5lZCkge1xuICAgICAgICAgICAgICAgIHZhbHVlc1RvVXBzZXJ0LmNvcHlSZW1pbmRlcnMgPSBjb3B5UmVtaW5kZXJzXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGlmIChjb3B5UHJpb3JpdHlMZXZlbCAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICAgICAgICAgICAgdmFsdWVzVG9VcHNlcnQuY29weVByaW9yaXR5TGV2ZWwgPSBjb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBpZiAoY29weU1vZGlmaWFibGUgIT09IHVuZGVmaW5lZCkge1xuICAgICAgICAgICAgICAgIHZhbHVlc1RvVXBzZXJ0LmNvcHlNb2RpZmlhYmxlID0gY29weU1vZGlmaWFibGVcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgaWYgKGNvcHlDYXRlZ29yaWVzICE9PSB1bmRlZmluZWQpIHtcbiAgICAgICAgICAgICAgICB2YWx1ZXNUb1Vwc2VydC5jb3B5Q2F0ZWdvcmllcyA9IGNvcHlDYXRlZ29yaWVzXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGlmIChjb3B5SXNCcmVhayAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICAgICAgICAgICAgdmFsdWVzVG9VcHNlcnQuY29weUlzQnJlYWsgPSBjb3B5SXNCcmVha1xuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBpZiAobWF4V29ya0xvYWRQZXJjZW50ICE9PSB1bmRlZmluZWQpIHtcbiAgICAgICAgICAgICAgICB2YWx1ZXNUb1Vwc2VydC5tYXhXb3JrTG9hZFBlcmNlbnQgPSBtYXhXb3JrTG9hZFBlcmNlbnRcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgaWYgKG1heE51bWJlck9mTWVldGluZ3MgIT09IHVuZGVmaW5lZCkge1xuICAgICAgICAgICAgICAgIHZhbHVlc1RvVXBzZXJ0Lm1heE51bWJlck9mTWVldGluZ3MgPSBtYXhOdW1iZXJPZk1lZXRpbmdzXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGlmIChtaW5OdW1iZXJPZkJyZWFrcyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICAgICAgICAgICAgdmFsdWVzVG9VcHNlcnQubWluTnVtYmVyT2ZCcmVha3MgPSBtaW5OdW1iZXJPZkJyZWFrc1xuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBpZiAoYnJlYWtMZW5ndGggIT09IHVuZGVmaW5lZCkge1xuICAgICAgICAgICAgICAgIHZhbHVlc1RvVXBzZXJ0LmJyZWFrTGVuZ3RoID0gYnJlYWtMZW5ndGhcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgaWYgKGNvcHlDb2xvciAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICAgICAgICAgICAgdmFsdWVzVG9VcHNlcnQuY29weUNvbG9yID0gY29weUNvbG9yXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGlmIChjb3B5SXNNZWV0aW5nICE9PSB1bmRlZmluZWQpIHtcbiAgICAgICAgICAgICAgICB2YWx1ZXNUb1Vwc2VydC5jb3B5SXNNZWV0aW5nID0gY29weUlzTWVldGluZ1xuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBpZiAoY29weUlzRXh0ZXJuYWxNZWV0aW5nICE9PSB1bmRlZmluZWQpIHtcbiAgICAgICAgICAgICAgICB2YWx1ZXNUb1Vwc2VydC5jb3B5SXNFeHRlcm5hbE1lZXRpbmcgPSBjb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgaWYgKGJhY2tUb0JhY2tNZWV0aW5ncyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICAgICAgICAgICAgdmFsdWVzVG9VcHNlcnQuYmFja1RvQmFja01lZXRpbmdzID0gYmFja1RvQmFja01lZXRpbmdzXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGlmIChicmVha0NvbG9yICE9PSB1bmRlZmluZWQpIHtcbiAgICAgICAgICAgICAgICB2YWx1ZXNUb1Vwc2VydC5icmVha0NvbG9yID0gYnJlYWtDb2xvclxuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBjb25zb2xlLmxvZyh2YWx1ZXNUb1Vwc2VydCwgJyB2YWx1ZXNUb1Vwc2VydCBpbnNpZGUgdXBzZXJ0VXNlclByZWZlcmVuY2UgZm9yIHVzZXJJZDogJywgdXNlcklkLCAncGFydCBvZiBVc2VyQ2FsZW5kYXJQcmVmZXJlbmNlcycpXG5cbiAgICAgICAgICAgIGF3YWl0IGNsaWVudC5tdXRhdGUoe1xuICAgICAgICAgICAgICAgIG11dGF0aW9uOiB1cHNlcnRVc2VyUHJlZmVyZW5jZU11dGF0aW9uLFxuICAgICAgICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgICAgICAgICB1c2VyUHJlZmVyZW5jZTogdmFsdWVzVG9VcHNlcnQsXG4gICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIH0pXG5cbiAgICAgICAgICAgIHRvYXN0KHtcbiAgICAgICAgICAgICAgICB0aXRsZTogJ1N1Y2Nlc3MnLFxuICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVXNlciBwcmVmZXJlbmNlcyBzYXZlZCcsXG4gICAgICAgICAgICAgICAgc3RhdHVzOiAnc3VjY2VzcycsXG4gICAgICAgICAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgICAgICAgICAgaXNDbG9zYWJsZTogdHJ1ZSxcbiAgICAgICAgICAgIH0pXG5cbiAgICAgICAgICAgIHJvdXRlci5iYWNrKClcbiAgICAgICAgfSBjYXRjaCAoZSkge1xuICAgICAgICAgICAgY29uc29sZS5sb2coZSwgJyBlcnJvciBpbiBzYXZldXNlcl9wcmVmZXJlbmNlcycpXG4gICAgICAgIH1cbiAgICB9XG5cbiAgICBcbiAgICBjb25zdCBnb1RvUHJldlN0ZXAgPSAoKSA9PiB7XG4gICAgICAgIGNvbnN0IHByZXZBY3RpdmVJbmRleCA9IGFjdGl2ZUluZGV4XG4gICAgICAgIGNvbnN0IG5ld0FjdGl2ZUluZGV4ID0gcHJldkFjdGl2ZUluZGV4ID09PSAwID8gMCA6IHByZXZBY3RpdmVJbmRleCAtIDFcbiAgICAgICAgc2V0QWN0aXZlSW5kZXgobmV3QWN0aXZlSW5kZXgpXG4gICAgfVxuXG4gICAgY29uc3QgcmVuZGVyUHJldkJ1dHRvbiA9ICgpID0+IHtcbiAgICAgICAgaWYgKGFjdGl2ZUluZGV4ID09PSAwKSB7XG4gICAgICAgICAgICByZXR1cm4gPEJveCBtbD17eyBwaG9uZTogJ3MnLCB0YWJsZXQ6ICdtJyB9fS8+XG4gICAgICAgIH1cblxuICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgPEJveCBtbD17eyBwaG9uZTogJ3MnLCB0YWJsZXQ6ICdtJyB9fT5cbiAgICAgICAgICAgICAgICA8QnV0dG9uIG9uQ2xpY2s9e2dvVG9QcmV2U3RlcH0+XG4gICAgICAgICAgICAgICAgICAgIEJhY2tcbiAgICAgICAgICAgICAgICA8L0J1dHRvbj5cbiAgICAgICAgICAgIDwvQm94PlxuICAgICAgICApXG4gICAgfVxuXG4gICAgY29uc3QgZ29Ub05leHRTdGVwID0gKCkgPT4ge1xuICAgICAgICAvKlxuICAgICAgICAgICAgMCAtIEVkaXRQcmVmZXJlbmNlU3RlcDFcbiAgICAgICAgICAgIDEgLSBFZGl0UHJlZmVyZW5jZVN0ZXAyXG4gICAgICAgICAgICAyIC0gRWRpdFByZWZlcmVuY2VTdGVwM1xuICAgICAgICAgICAgMyAtIEVkaXRQcmVmZXJlbmNlU3RlcDRcbiAgICAgICAgICAgIDQgLSBFZGl0UHJlZmVyZW5jZVN0ZXA1XG4gICAgICAgICovXG4gICAgICAgIFxuICAgICAgICBjb25zdCBwcmV2QWN0aXZlSW5kZXggPSBhY3RpdmVJbmRleFxuICAgICAgICBjb25zdCBwcmV2Q29tcGxldGVkU3RlcCA9IGNvbXBsZXRlZFN0ZXBcblxuICAgICAgICBpZiAocHJldkFjdGl2ZUluZGV4ID09PSA1KSB7XG4gICAgICAgICAgICByZXR1cm5cbiAgICAgICAgfVxuXG4gICAgICAgIGxldCBuZXdBY3RpdmVJbmRleCA9IHByZXZBY3RpdmVJbmRleCArIDFcblxuICAgICAgICBpZiAoIXByZXZDb21wbGV0ZWRTdGVwIHx8IChwcmV2Q29tcGxldGVkU3RlcCA8IHByZXZBY3RpdmVJbmRleCkpIHtcbiAgICAgICAgICAgIGNvbnN0IG5ld0NvbXBsZXRlZFN0ZXAgPSBwcmV2QWN0aXZlSW5kZXhcbiAgICAgICAgICAgIHNldENvbXBsZXRlZFN0ZXAobmV3Q29tcGxldGVkU3RlcClcbiAgICAgICAgfVxuXG4gICAgICAgIGlmIChuZXdBY3RpdmVJbmRleCAhPT0gcHJldkFjdGl2ZUluZGV4KSB7XG4gICAgICAgICAgICBzZXRBY3RpdmVJbmRleChuZXdBY3RpdmVJbmRleClcbiAgICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IHJlbmRlck5leHRCdXR0b24gPSAoKSA9PiB7XG4gICAgICAgIGlmIChhY3RpdmVJbmRleCA9PT0gNSkge1xuICAgICAgICByZXR1cm4gPEJveCBtcj17eyBwaG9uZTogJ3MnLCB0YWJsZXQ6ICdtJyB9fS8+XG4gICAgICAgIH1cblxuICAgICAgICByZXR1cm4gKFxuICAgICAgICA8Qm94IG1yPXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19PlxuICAgICAgICAgICAgPEJ1dHRvbiBvbkNsaWNrPXtnb1RvTmV4dFN0ZXB9PlxuICAgICAgICAgICAgTmV4dFxuICAgICAgICAgICAgPC9CdXR0b24+XG4gICAgICAgIDwvQm94PlxuICAgICAgICApXG4gICAgfVxuXG4gICAgY29uc3QgcmVuZGVyQ3VycmVudFN0ZXAgPSAoKSA9PiB7XG4gICAgICAgIC8qXG4gICAgICAgICAgICAwIC0gRWRpdFByZWZlcmVuY2VTdGVwMVxuICAgICAgICAgICAgMSAtIEVkaXRQcmVmZXJlbmNlU3RlcDJcbiAgICAgICAgICAgIDIgLSBFZGl0UHJlZmVyZW5jZVN0ZXAzXG4gICAgICAgICAgICAzIC0gRWRpdFByZWZlcmVuY2VTdGVwNFxuICAgICAgICAgICAgNCAtIEVkaXRQcmVmZXJlbmNlU3RlcDVcbiAgICAgICAgKi9cbiAgICAgICAgXG4gICAgICAgIHN3aXRjaCAoYWN0aXZlSW5kZXgpIHtcbiAgICAgICAgICAgIGNhc2UgMDpcbiAgICAgICAgICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgICAgICAgICA8Qm94IHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0gZmxleD17MX0gYWxpZ25JdGVtcz1cImNlbnRlclwiIGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICA8RWRpdFByZWZlcmVuY2VTdGVwMVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJlbWluZGVycz17cmVtaW5kZXJzfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNldFBhcmVudFJlbWluZGVycz17c2V0UmVtaW5kZXJzfVxuICAgICAgICAgICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICAgICAgICAgIDxCb3ggcHQ9e3sgcGhvbmU6ICdtJywgdGFibGV0OiAncycgfX0gbWI9e3sgcGhvbmU6ICdzJywgdGFibGV0OiAnbScgfX0gc3R5bGU9e3sgd2lkdGg6ICcxMDAlJyB9fSBmbGV4RGlyZWN0aW9uPVwicm93XCIganVzdGlmeUNvbnRlbnQ9XCJzcGFjZS1iZXR3ZWVuXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxCb3ggLz5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB7cmVuZGVyTmV4dEJ1dHRvbigpfVxuICAgICAgICAgICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgIClcbiAgICAgICAgICAgIGNhc2UgMTpcbiAgICAgICAgICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgICAgICAgICA8Qm94IHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0gZmxleD17MX0gYWxpZ25JdGVtcz1cImNlbnRlclwiIGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICA8RWRpdFByZWZlcmVuY2VTdGVwMlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHN0YXJ0VGltZXM9e3N0YXJ0VGltZXN9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc2V0UGFyZW50U3RhcnRUaW1lcz17c2V0U3RhcnRUaW1lc31cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBlbmRUaW1lcz17ZW5kVGltZXN9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc2V0UGFyZW50RW5kVGltZXM9e3NldEVuZFRpbWVzfVxuICAgICAgICAgICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICAgICAgICAgICAgICAgIDxCb3ggcHQ9e3sgcGhvbmU6ICdtJywgdGFibGV0OiAncycgfX0gbWI9e3sgcGhvbmU6ICdzJywgdGFibGV0OiAnbScgfX0gc3R5bGU9e3sgd2lkdGg6ICcxMDAlJyB9fSBmbGV4RGlyZWN0aW9uPVwicm93XCIganVzdGlmeUNvbnRlbnQ9XCJzcGFjZS1iZXR3ZWVuXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHtyZW5kZXJQcmV2QnV0dG9uKCl9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAge3JlbmRlck5leHRCdXR0b24oKX1cbiAgICAgICAgICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgICAgICA8L0JveD4gICBcbiAgICAgICAgICAgICAgICApXG4gICAgICAgICAgICBjYXNlIDI6XG4gICAgICAgICAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgICAgICAgICAgPEJveCBzdHlsZT17eyB3aWR0aDogJzEwMCUnIH19IGZsZXg9ezF9IGFsaWduSXRlbXM9XCJjZW50ZXJcIiBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiPlxuICAgICAgICAgICAgICAgICAgICAgICAgPEVkaXRQcmVmZXJlbmNlU3RlcDNcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb3B5QXZhaWxhYmlsaXR5PXtjb3B5QXZhaWxhYmlsaXR5fVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNldFBhcmVudENvcHlBdmFpbGFiaWxpdHk9e3NldENvcHlBdmFpbGFiaWxpdHl9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY29weVRpbWVCbG9ja2luZz17Y29weVRpbWVCbG9ja2luZ31cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzZXRQYXJlbnRDb3B5VGltZUJsb2NraW5nPXtzZXRDb3B5VGltZUJsb2NraW5nfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZT17Y29weVRpbWVQcmVmZXJlbmNlfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNldFBhcmVudENvcHlUaW1lUHJlZmVyZW5jZT17c2V0Q29weVRpbWVQcmVmZXJlbmNlfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlSZW1pbmRlcnM9e2NvcHlSZW1pbmRlcnN9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc2V0UGFyZW50Q29weVJlbWluZGVycz17c2V0Q29weVJlbWluZGVyc31cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb3B5UHJpb3JpdHlMZXZlbD17Y29weVByaW9yaXR5TGV2ZWx9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc2V0UGFyZW50Q29weVByaW9yaXR5TGV2ZWw9e3NldENvcHlQcmlvcml0eUxldmVsfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlNb2RpZmlhYmxlPXtjb3B5TW9kaWZpYWJsZX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzZXRQYXJlbnRDb3B5TW9kaWZpYWJsZT17c2V0Q29weU1vZGlmaWFibGV9XG4gICAgICAgICAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgICAgICAgICAgPEJveCBwdD17eyBwaG9uZTogJ20nLCB0YWJsZXQ6ICdzJyB9fSBtYj17eyBwaG9uZTogJ3MnLCB0YWJsZXQ6ICdtJyB9fSBzdHlsZT17eyB3aWR0aDogJzEwMCUnIH19IGZsZXhEaXJlY3Rpb249XCJyb3dcIiBqdXN0aWZ5Q29udGVudD1cInNwYWNlLWJldHdlZW5cIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAge3JlbmRlclByZXZCdXR0b24oKX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB7cmVuZGVyTmV4dEJ1dHRvbigpfVxuICAgICAgICAgICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgIClcbiAgICAgICAgICAgIGNhc2UgMzpcbiAgICAgICAgICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgICAgICAgICA8Qm94IHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0gZmxleD17MX0gYWxpZ25JdGVtcz1cImNlbnRlclwiIGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICA8RWRpdFByZWZlcmVuY2VTdGVwNVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlDYXRlZ29yaWVzPXtjb3B5Q2F0ZWdvcmllc31cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzZXRQYXJlbnRDb3B5Q2F0ZWdvcmllcz17c2V0Q29weUNhdGVnb3JpZXN9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY29weUlzQnJlYWs9e2NvcHlJc0JyZWFrfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNldFBhcmVudENvcHlJc0JyZWFrPXtzZXRDb3B5SXNCcmVha31cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBtYXhXb3JrTG9hZFBlcmNlbnQ9e21heFdvcmtMb2FkUGVyY2VudH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzZXRQYXJlbnRNYXhXb3JrTG9hZFBlcmNlbnQ9e3NldE1heFdvcmtMb2FkUGVyY2VudH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBtaW5OdW1iZXJPZkJyZWFrcz17bWluTnVtYmVyT2ZCcmVha3N9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc2V0UGFyZW50TWluTnVtYmVyT2ZCcmVha3M9e3NldE1pbk51bWJlck9mQnJlYWtzfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGJyZWFrTGVuZ3RoPXticmVha0xlbmd0aH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzZXRQYXJlbnRCcmVha0xlbmd0aD17c2V0QnJlYWtMZW5ndGh9XG4gICAgICAgICAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgICAgICAgICAgPEJveCBwdD17eyBwaG9uZTogJ20nLCB0YWJsZXQ6ICdzJyB9fSBtYj17eyBwaG9uZTogJ3MnLCB0YWJsZXQ6ICdtJyB9fSBzdHlsZT17eyB3aWR0aDogJzEwMCUnIH19IGZsZXhEaXJlY3Rpb249XCJyb3dcIiBqdXN0aWZ5Q29udGVudD1cInNwYWNlLWJldHdlZW5cIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAge3JlbmRlclByZXZCdXR0b24oKX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB7cmVuZGVyTmV4dEJ1dHRvbigpfVxuICAgICAgICAgICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgIClcbiAgICAgICAgICAgIGNhc2UgNDpcbiAgICAgICAgICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgICAgICAgICA8Qm94IHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0gZmxleD17MX0gYWxpZ25JdGVtcz1cImNlbnRlclwiIGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICA8RWRpdFByZWZlcmVuY2VTdGVwNlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGJhY2tUb0JhY2tNZWV0aW5ncz17YmFja1RvQmFja01lZXRpbmdzfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNldFBhcmVudEJhY2tUb0JhY2tNZWV0aW5ncz17c2V0QmFja1RvQmFja01lZXRpbmdzfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlJc01lZXRpbmc9e2NvcHlJc01lZXRpbmd9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc2V0UGFyZW50Q29weUlzTWVldGluZz17c2V0Q29weUlzTWVldGluZ31cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmc9e2NvcHlJc0V4dGVybmFsTWVldGluZ31cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzZXRQYXJlbnRDb3B5SXNFeHRlcm5hbE1lZXRpbmc9e3NldENvcHlJc0V4dGVybmFsTWVldGluZ31cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb3B5Q29sb3I9e2NvcHlDb2xvcn1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzZXRQYXJlbnRDb3B5Q29sb3I9e3NldENvcHlDb2xvcn1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBicmVha0NvbG9yPXticmVha0NvbG9yfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNldFBhcmVudEJyZWFrQ29sb3I9e3NldEJyZWFrQ29sb3J9XG4gICAgICAgICAgICAgICAgICAgICAgICAvPlxuICAgICAgICAgICAgICAgICAgICAgICAgPEJveCAgcHQ9e3sgcGhvbmU6ICdtJywgdGFibGV0OiAncycgfX0gbWI9e3sgcGhvbmU6ICdzJywgdGFibGV0OiAnbScgfX0gc3R5bGU9e3sgd2lkdGg6ICcxMDAlJyB9fSBmbGV4RGlyZWN0aW9uPVwicm93XCIganVzdGlmeUNvbnRlbnQ9XCJzcGFjZS1iZXR3ZWVuXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHtyZW5kZXJQcmV2QnV0dG9uKCl9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAge3JlbmRlck5leHRCdXR0b24oKX1cbiAgICAgICAgICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgICAgICApXG4gICAgICAgICAgICBjYXNlIDU6XG4gICAgICAgICAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICAgICAgICAgICAgPEJveCBzdHlsZT17eyB3aWR0aDogJzEwMCUnIH19IGZsZXg9ezF9IGFsaWduSXRlbXM9XCJjZW50ZXJcIiBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiPlxuICAgICAgICAgICAgICAgICAgICAgICAgPEJveCBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiBtaW5IZWlnaHQ9XCI2MHZoXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPEJveCBzdHlsZT17eyB3aWR0aDogJzEwMCUnIH19IHA9e3sgcGhvbmU6ICdzJywgdGFibGV0OiAnbScgfX0ganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIDxUZXh0IHZhcmlhbnQ9XCJzdWJoZWFkZXJOb3JtYWxcIj5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIFNhdmUgVXNlciBQcmVmZXJlbmNlc1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA8L1RleHQ+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPEJveCBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIiAgcD17eyBwaG9uZTogJ3MnLCB0YWJsZXQ6ICdtJyB9fT5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPEJ1dHRvbiBvbkNsaWNrPXtzYXZldXNlcl9wcmVmZXJlbmNlc30+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBTdWJtaXRcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgPC9CdXR0b24+XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgICAgICAgICAgICAgIDxCb3ggIHB0PXt7IHBob25lOiAnbScsIHRhYmxldDogJ3MnIH19IG1iPXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19IGZsZXhEaXJlY3Rpb249XCJyb3dcIiBqdXN0aWZ5Q29udGVudD1cImZsZXgtc3RhcnRcIiB3aWR0aD1cIjEwMCVcIj5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB7cmVuZGVyUHJldkJ1dHRvbigpfVxuICAgICAgICAgICAgICAgICAgICAgICAgPC9Cb3g+ICBcbiAgICAgICAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgICAgKVxuICAgICAgICAgICAgZGVmYXVsdDpcbiAgICAgICAgICAgICAgICByZXR1cm4gKFxuICAgICAgICAgICAgICAgICAgICA8Qm94IGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgICAgICAgICAgICAgPFJlZ3VsYXJDYXJkPlxuICAgICAgICAgICAgICAgICAgICAgICAgPFRleHQgdmFyaWFudD1cImhlYWRlclwiPlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIE9vcHMuLi4gc29tZXRoaW5nIHdlbnQgd3JvbmdcbiAgICAgICAgICAgICAgICAgICAgICAgIDwvVGV4dD5cbiAgICAgICAgICAgICAgICAgICAgICAgIDwvUmVndWxhckNhcmQ+XG4gICAgICAgICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICAgIClcbiAgICAgICAgfSAgICAgICAgICAgICAgICAgICAgXG4gICAgfVxuICAgIFxuICAgIHJldHVybiAoXG4gICAgICAgIDxCb3ggc3R5bGU9e3sgd2lkdGg6ICcxMDAlJyB9fSBmbGV4PXsxfSBhbGlnbkl0ZW1zPVwiY2VudGVyXCIganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgIDxXaXphcmRcbiAgICAgICAgICAgICAgICBpdGVtcz17W1xuICAgICAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICAgICAgICBpbmRleDogMCxcbiAgICAgICAgICAgICAgICAgICAgICAgIGxhYmVsOiAnU3RlcCAxJyxcbiAgICAgICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgICAgICAgICAgaW5kZXg6IDEsXG4gICAgICAgICAgICAgICAgICAgICAgICBsYWJlbDogJ1N0ZXAgMicsXG4gICAgICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGluZGV4OiAyLFxuICAgICAgICAgICAgICAgICAgICAgICAgbGFiZWw6ICdTdGVwIDMnLFxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICAgICAgICBpbmRleDogMyxcbiAgICAgICAgICAgICAgICAgICAgICAgIGxhYmVsOiAnU3RlcCA0JyxcbiAgICAgICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGluZGV4OiA0LFxuICAgICAgICAgICAgICAgICAgICAgICAgbGFiZWw6ICdTdGVwIDUnLFxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgICAgICAgICAgaW5kZXg6IDUsXG4gICAgICAgICAgICAgICAgICAgICAgICBsYWJlbDogJ1NhdmUgUHJlZmVyZW5jZXMnLFxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgIF19XG5cbiAgICAgICAgICAgICAgICBjb21wbGV0ZWQ9e2NvbXBsZXRlZFN0ZXB9XG4gICAgICAgICAgICAgICAgYWN0aXZlSW5kZXg9e2FjdGl2ZUluZGV4fVxuICAgICAgICAgICAgLz5cbiAgICAgICAgICAgIHtyZW5kZXJDdXJyZW50U3RlcCgpfVxuICAgICAgICA8L0JveD5cbiAgICApXG59XG5cblxuZXhwb3J0IGRlZmF1bHQgVXNlckNhbGVuZGFyUHJlZmVyZW5jZXNcbiJdfQ==