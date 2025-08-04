"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getServerSideProps = getServerSideProps;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const react_2 = require("@chakra-ui/react");
const Wizard_1 = __importDefault(require("@components/Wizard"));
const TextField_1 = __importDefault(require("@components/TextField"));
const uuid_1 = require("uuid");
const date_utils_1 = require("@lib/date-utils");
const react_3 = require("@chakra-ui/react");
const Box_1 = __importDefault(require("@components/common/Box"));
const Text_1 = __importDefault(require("@components/common/Text"));
const Button_1 = __importDefault(require("@components/Button"));
const UserTaskHelper2_1 = require("@lib/Progress/Todo/UserTaskHelper2");
const lodash_1 = __importDefault(require("lodash"));
const ScheduleHelper_1 = require("@lib/Schedule/ScheduleHelper");
const calendarDbHelper_1 = require("@lib/calendarLib/calendarDbHelper");
const user_context_1 = require("@lib/user-context");
const router_1 = require("next/router");
const UserTaskHelper3_1 = require("@lib/Progress/Todo/UserTaskHelper3");
const constants_1 = require("@lib/Progress/Todo/constants");
const styles = {
    inputField: {
        fontSize: '21px',
        lineHeight: '28px',
        color: '#221D23',
        // borderColor: palette.textBlack,
        // borderWidth: 1,
        width: '100%',
        // height: 40,
    },
    container: {
        flex: 1,
    },
};
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
const deadlineOptions = [
    {
        label: 'Soft Deadline',
        value: 'soft',
    },
    {
        label: 'Hard Deadline',
        value: 'hard',
    }
];
function UserTaskDeadline() {
    const router = (0, router_1.useRouter)();
    const { sub, client } = (0, user_context_1.useAppContext)();
    const taskType = router.query?.taskType;
    const taskId = router.query?.taskId;
    const isUpdate = router.query?.isUpdate;
    const deadlineType = router.query?.deadlineType;
    const [activeIndex, setActiveIndex] = (0, react_1.useState)(0);
    const [completedStep, setCompletedStep] = (0, react_1.useState)();
    const [newPriority, setNewPriority] = (0, react_1.useState)(1);
    const [newDeadline, setNewDeadline] = (0, react_1.useState)(new Date());
    const [newDeadlineType, setNewDeadlineType] = (0, react_1.useState)(deadlineType || 'soft');
    const [newDuration, setNewDuration] = (0, react_1.useState)(30);
    const [calendar, setCalendar] = (0, react_1.useState)();
    const [event, setEvent] = (0, react_1.useState)();
    const [task, setTask] = (0, react_1.useState)();
    // const dark = useColorScheme() === 'dark'
    const userId = sub;
    const toast = (0, react_3.useToast)();
    // get task
    (0, react_1.useEffect)(() => {
        (async () => {
            try {
                if (!taskId || !client) {
                    return;
                }
                const oldTask = await (0, UserTaskHelper3_1.getTaskGivenId)(client, taskId);
                setTask(oldTask);
            }
            catch (e) {
                console.log(e, ' unable to get task by id');
            }
        })();
    }, [client, taskId]);
    // get global primary calendar
    (0, react_1.useEffect)(() => {
        (async () => {
            if (!userId || !client) {
                return;
            }
            const result = await (0, ScheduleHelper_1.getGlobalPrimaryCalendarFunction)(client, userId);
            if (!result?.id) {
                console.log(' no primary calendar available');
                return;
            }
            setCalendar(result);
        })();
    }, [client, userId]);
    // get Event
    (0, react_1.useEffect)(() => {
        (async () => {
            if (!taskId || !client) {
                return;
            }
            if (task?.id) {
                const oldEvent = await (0, calendarDbHelper_1.getEventWithId)(client, task?.eventId);
                if (!oldEvent?.id) {
                    console.log(' no event available');
                    return;
                }
                console.log(oldEvent?.id, ' oldEvent?.id inside UserTaskDeadline');
                console.log(oldEvent?.softDeadline, ' oldEvent?.softDeadline inside UserTaskDeadline');
                console.log(oldEvent?.hardDeadline, ' oldEvent?.hardDeadline inside UserTaskDeadline');
                setEvent(oldEvent);
                setNewPriority(oldEvent.priority);
                setNewDeadline((oldEvent?.softDeadline && (0, date_utils_1.dayjs)(oldEvent?.softDeadline).tz(oldEvent?.timezone || date_utils_1.dayjs.tz.guess(), true).toDate()) || (oldEvent?.hardDeadline && (0, date_utils_1.dayjs)(oldEvent?.hardDeadline).tz(oldEvent?.timezone || date_utils_1.dayjs.tz.guess()).toDate()) || new Date());
                setNewDeadlineType(oldEvent?.softDeadline ? 'soft' : 'hard');
                setNewDuration(oldEvent?.duration || 0);
                // get tags for event
            }
        })();
    }, [client, task?.eventId, task?.id, taskId, taskType]);
    const onChangePriority = (value = '1') => {
        const intValue = parseInt(value.replace(/[^0-9.]/g, ''), 10);
        // validate
        if (intValue < 1) {
            setNewPriority(1);
            return;
        }
        if (isNaN(intValue)) {
            setNewPriority(1);
            return;
        }
        setNewPriority(parseInt(value.replace(/[^0-9.]/g, ''), 10) || 1);
    };
    // update to Datasore
    const updateTaskInDb = async (duration, softDeadline, hardDeadline, eventId) => {
        try {
            if (!taskId) {
                return; // console.log(' not available in the id array')
            }
            const toUpdateTask = lodash_1.default.cloneDeep(task);
            // validate
            if (!toUpdateTask) {
                console.log('no toUpdateTask provided inside updateTaskinDb');
                return;
            }
            if (duration !== undefined) {
                toUpdateTask.duration = duration;
            }
            if (softDeadline !== undefined) {
                toUpdateTask.softDeadline = softDeadline;
            }
            if (hardDeadline !== undefined) {
                toUpdateTask.hardDeadline = hardDeadline;
            }
            if (eventId !== undefined) {
                toUpdateTask.eventId = `${eventId}#${calendar?.id}`;
            }
            await (0, UserTaskHelper3_1.updateTaskByIdInDb)(client, toUpdateTask);
            setTask(toUpdateTask);
        }
        catch (e) {
            console.log(e, ' unable to update task in db');
        }
    };
    // create taskDeadline
    const onReceiveCreateDeadline = async () => {
        /**
        overrides auto generated start and end dates
         */
        try {
            if (!taskId || !task) {
                // console.log('no taskId present inside onReceiveCreateTaskScheduleInfo')
                return;
            }
            const eventId = await (0, UserTaskHelper2_1.createDeadlineForTask)(client, userId, task?.notes, newDuration, taskId, taskType, newPriority, newDeadlineType === 'soft' ? (0, date_utils_1.dayjs)(newDeadline).format() : undefined, newDeadlineType === 'hard' ? (0, date_utils_1.dayjs)(newDeadline).format() : undefined, undefined, undefined, calendar.colorId, undefined, task?.notes);
            await updateTaskInDb(newDuration, newDeadlineType === 'soft' ? (0, date_utils_1.dayjs)(newDeadline).format() : undefined, newDeadlineType === 'hard' ? (0, date_utils_1.dayjs)(newDeadline).format() : undefined, eventId ? `${eventId}#${calendar?.id}` : undefined);
            if (taskType === constants_1.WeeklyTask) {
                await (0, UserTaskHelper2_1.submitCalendarForQueue)(client, userId, (0, date_utils_1.dayjs)().hour(7).format(), (0, date_utils_1.dayjs)().add(6, 'day').hour(23).minute(59).format(), toast);
            }
            else if (taskType === constants_1.DailyTask) {
                await (0, UserTaskHelper2_1.submitCalendarForQueue)(client, userId, (0, date_utils_1.dayjs)().hour(7).format(), (0, date_utils_1.dayjs)().hour(23).minute(59).format(), toast);
            }
            toast({
                status: 'success',
                title: 'Task deadline created',
                description: 'Task deadline is succesfully created',
                duration: 9000,
                isClosable: true,
            });
            router.push({ pathname: '/Progress/Todo/UserTask', query: {
                    taskType,
                    isUpdate: (0, uuid_1.v4)(),
                } });
        }
        catch (e) {
            // console.log(e, ' unable to create task deadline')
            toast({
                status: 'error',
                title: 'No deadline created',
                description: 'We are not able to create the deadline due to an internal error.',
                duration: 9000,
                isClosable: true,
            });
            router.push({ pathname: '/Progress/Todo/UserTask', query: {
                    taskType,
                    isUpdate: undefined,
                } });
            // setIsDeadlineOverlay(false)
            // setActiveDeadlineIndex(-1)
        }
    };
    const onReceiveUpdateDeadline = async () => {
        try {
            if (task) {
                console.log(newDeadlineType, ' newDeadlineType before editEventForTask');
                const eventDoc = await (0, calendarDbHelper_1.getEventWithId)(client, task.eventId);
                await (0, UserTaskHelper2_1.editEventForTask)(task?.eventId, eventDoc?.startDate, eventDoc?.endDate, userId, client, eventDoc?.calendarId, undefined, task.notes, undefined, undefined, undefined, undefined, undefined, task.notes, undefined, undefined, undefined, undefined, true, false, false, false, false, undefined, taskId, taskType, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, task.notes, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, taskType === 'Daily', taskType === 'Weekly', undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, true, undefined, true, true, true, newDeadlineType === 'hard' ? (0, date_utils_1.dayjs)(newDeadline).format() : null, newDeadlineType === 'soft' ? (0, date_utils_1.dayjs)(newDeadline).format() : null, undefined, undefined, undefined, undefined, newDuration, undefined, true, 'update', undefined, undefined, undefined);
                await updateTaskInDb(newDuration, newDeadlineType === 'soft' ? (0, date_utils_1.dayjs)(newDeadline).format() : null, newDeadlineType === 'hard' ? (0, date_utils_1.dayjs)(newDeadline).format() : null);
            }
            if (event.softDeadline && (newDeadlineType === 'hard')) {
                console.log(`event.softDeadline && (newDeadlineType === 'hard')`);
                if (taskType === constants_1.WeeklyTask) {
                    await (0, UserTaskHelper2_1.submitCalendarForQueue)(client, userId, (0, date_utils_1.dayjs)().hour(7).format(), (0, date_utils_1.dayjs)().add(6, 'day').hour(23).minute(59).format(), toast);
                }
                else if (taskType === constants_1.DailyTask) {
                    await (0, UserTaskHelper2_1.submitCalendarForQueue)(client, userId, (0, date_utils_1.dayjs)().hour(7).format(), (0, date_utils_1.dayjs)().hour(23).minute(59).format(), toast);
                }
            }
            else if (event.hardDeadline && (newDeadlineType === 'soft')) {
                console.log(`event.hardDeadline && (newDeadlineType === 'soft')`);
                if (taskType === constants_1.WeeklyTask) {
                    await (0, UserTaskHelper2_1.submitCalendarForQueue)(client, userId, (0, date_utils_1.dayjs)().hour(7).format(), (0, date_utils_1.dayjs)().add(6, 'day').hour(23).minute(59).format(), toast);
                }
                else if (taskType === constants_1.DailyTask) {
                    await (0, UserTaskHelper2_1.submitCalendarForQueue)(client, userId, (0, date_utils_1.dayjs)().hour(7).format(), (0, date_utils_1.dayjs)().hour(23).minute(59).format(), toast);
                }
            }
            else if (event.softDeadline
                && (deadlineType === 'soft')
                && !((0, date_utils_1.dayjs)(event.softDeadline?.slice(0, 19)).tz(event?.timezone || date_utils_1.dayjs.tz.guess(), true).isSame((0, date_utils_1.dayjs)(newDeadline).format(), 'minute'))) {
                if (taskType === constants_1.WeeklyTask) {
                    await (0, UserTaskHelper2_1.submitCalendarForQueue)(client, userId, (0, date_utils_1.dayjs)().hour(7).format(), (0, date_utils_1.dayjs)().add(6, 'day').hour(23).minute(59).format(), toast);
                }
                else if (taskType === constants_1.DailyTask) {
                    await (0, UserTaskHelper2_1.submitCalendarForQueue)(client, userId, (0, date_utils_1.dayjs)().hour(7).format(), (0, date_utils_1.dayjs)().hour(23).minute(59).format(), toast);
                }
            }
            else if (event.hardDeadline
                && (deadlineType === 'hard')
                && !((0, date_utils_1.dayjs)(event.hardDeadline?.slice(0, 19)).tz(event?.timezone || date_utils_1.dayjs.tz.guess(), true).isSame((0, date_utils_1.dayjs)(newDeadline).format()))) {
                if (taskType === 'Weekly') {
                    await (0, UserTaskHelper2_1.submitCalendarForQueue)(client, userId, (0, date_utils_1.dayjs)().hour(7).format(), (0, date_utils_1.dayjs)().add(6, 'day').hour(23).minute(59).format(), toast);
                }
                else if (taskType === 'Daily') {
                    await (0, UserTaskHelper2_1.submitCalendarForQueue)(client, userId, (0, date_utils_1.dayjs)().hour(7).format(), (0, date_utils_1.dayjs)().hour(23).minute(59).format(), toast);
                }
            }
            toast({
                status: 'success',
                title: 'Successfully updated',
                description: 'Task is successfully updated',
                duration: 9000,
                isClosable: true,
            });
            router.push({ pathname: '/Progress/Todo/UserTask', query: {
                    taskType,
                    isUpdate: (0, uuid_1.v4)(),
                } });
        }
        catch (e) {
            console.log(e, ' unable to update deadline');
            toast({
                status: 'error',
                title: 'Unable to update',
                description: 'Unable to update deadline due to an internal error',
                duration: 9000,
                isClosable: true,
            });
            //  navigation.navigate('UserTask', {
            //    taskType,
            //    isUpdate: undefined,
            //  })
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
            return (0, jsx_runtime_1.jsx)(Box_1.default, { p: { phone: 's', tablet: 'm' } });
        }
        return ((0, jsx_runtime_1.jsx)(Box_1.default, { ml: { phone: 's', tablet: 'm' }, mb: { phone: 's', tablet: 'm' }, children: (0, jsx_runtime_1.jsx)(Button_1.default, { onClick: goToPrevStep, children: "Back" }) }));
    };
    const renderNextButton = () => {
        if (activeIndex === 4) {
            return (0, jsx_runtime_1.jsx)(Box_1.default, { mr: { phone: 's', tablet: 'm' } });
        }
        return ((0, jsx_runtime_1.jsx)(Box_1.default, { mr: { phone: 's', tablet: 'm' }, mb: { phone: 's', tablet: 'm' }, children: (0, jsx_runtime_1.jsx)(Button_1.default, { onClick: goToNextStep, children: "Next" }) }));
    };
    const goToNextStep = () => {
        const prevActiveIndex = activeIndex;
        const prevCompletedStep = completedStep;
        if (prevActiveIndex === 3) {
            return;
        }
        const newActiveIndex = prevActiveIndex + 1;
        if (!prevCompletedStep || (prevCompletedStep < prevActiveIndex)) {
            const newCompletedStep = prevActiveIndex;
            setCompletedStep(newCompletedStep);
        }
        if (newActiveIndex !== prevActiveIndex) {
            setActiveIndex(newActiveIndex);
        }
    };
    const onSubmitPress = () => {
        try {
            return isUpdate
                ? onReceiveUpdateDeadline()
                : onReceiveCreateDeadline();
        }
        catch (e) {
            console.log(e, ' unable to submit press inside UserTaskDeadline');
        }
    };
    const renderCurrentStep = () => {
        switch (activeIndex) {
            case 0:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { justifyContent: "center", alignItems: "center", children: [(0, jsx_runtime_1.jsx)(Text_1.default, { textAlign: "center", variant: "subheader", mt: { phone: 's', tablet: 'm' }, children: "Deadline" }), (0, jsx_runtime_1.jsxs)("div", { className: "flex-1 flex flex-col justify-center items-start", style: { minHeight: '50vh' }, children: [(0, jsx_runtime_1.jsx)(Box_1.default, { mt: { phone: 's', tablet: 'm' }, justifyContent: "center", alignItems: "center", style: { width: '100%' }, children: (0, jsx_runtime_1.jsx)(react_2.Input, { placeholder: "Select Date and Time", size: "md", type: "datetime-local", onChange: (e) => {
                                            setNewDeadline((0, date_utils_1.dayjs)(e?.target?.value, "YYYY-MM-DDTHH:mm").toDate());
                                        }, value: (0, date_utils_1.dayjs)(newDeadline).format("YYYY-MM-DDTHH:mm") }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { mt: { phone: 's', tablet: 'm' }, justifyContent: "center", alignItems: "center", children: (0, jsx_runtime_1.jsxs)("select", { value: newDeadlineType, onChange: (e) => setNewDeadlineType(e?.target?.value), className: "select select-primary w-full max-w-xs", children: [(0, jsx_runtime_1.jsx)("option", { disabled: true, selected: true, children: "Pick a deadline" }), lodash_1.default.map(deadlineOptions, option => ((0, jsx_runtime_1.jsx)("option", { value: option.value, children: option.label }, option.value)))] }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { mt: { phone: 's', tablet: 'm' }, justifyContent: "center", alignItems: "center", style: { width: '100%' }, children: (0, jsx_runtime_1.jsx)(TextField_1.default, { label: "Duration (minutes)", type: "number", onChange: (e) => setNewDuration(parseInt(e?.target?.value.replace(/[^0-9.]/g, ''), 10)), value: `${newDuration}`, placeholder: "1", style: { ...(styles?.inputField) } }) }), (0, jsx_runtime_1.jsx)(Box_1.default, { mt: { phone: 's', tablet: 'm' }, justifyContent: "center", alignItems: "center", style: { width: '100%' }, children: (0, jsx_runtime_1.jsx)(TextField_1.default, { label: "Priority ( > 0)", type: "number", onChange: (e) => onChangePriority(e?.target?.value), value: `${newPriority}`, placeholder: "1", style: { ...(styles?.inputField) } }) })] }), (0, jsx_runtime_1.jsxs)(Box_1.default, { flexDirection: "row", justifyContent: "space-between", style: { width: '100%' }, children: [(0, jsx_runtime_1.jsx)(Box_1.default, {}), renderNextButton()] })] }));
            case 1:
                return ((0, jsx_runtime_1.jsxs)(Box_1.default, { justifyContent: "center", alignItems: "center", children: [(0, jsx_runtime_1.jsxs)(Box_1.default, { justifyContent: "center", alignItems: "center", minHeight: "60vh", children: [(0, jsx_runtime_1.jsx)(Text_1.default, { variant: "subheader", mt: { phone: 'm', tablet: 'l' }, children: isUpdate ? 'Update task deadline' : 'Create task deadline?' }), (0, jsx_runtime_1.jsx)(Box_1.default, { mt: { phone: 'm', tablet: 'l' }, children: (0, jsx_runtime_1.jsx)(Button_1.default, { onClick: onSubmitPress, children: isUpdate ? 'Update' : 'Create' }) })] }), (0, jsx_runtime_1.jsx)(Box_1.default, { flexDirection: "row", justifyContent: "flex-start", width: "100%", children: renderPrevButton() })] }));
        }
    };
    return ((0, jsx_runtime_1.jsxs)(Box_1.default, { flex: 1, children: [(0, jsx_runtime_1.jsx)(Wizard_1.default, { items: [
                    {
                        index: 0,
                        label: 'Add a Period',
                    },
                    {
                        index: 1,
                        label: 'Create Deadline',
                    },
                ], completed: completedStep, activeIndex: activeIndex }), renderCurrentStep()] }));
}
exports.default = UserTaskDeadline;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlclRhc2tEZWFkbGluZS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIlVzZXJUYXNrRGVhZGxpbmUudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7O0FBNkNBLGdEQXFDQzs7QUFsRkQsaUNBQWtEO0FBQ2xELDRDQUF3QztBQUN4QyxnRUFBdUM7QUFDdkMsc0VBQTZDO0FBQzdDLCtCQUFpQztBQUNqQyxnREFBdUM7QUFDdkMsNENBQTJDO0FBQzNDLGlFQUF3QztBQUN4QyxtRUFBMEM7QUFDMUMsZ0VBQXVDO0FBRXZDLHdFQUFvSDtBQUVwSCxvREFBc0I7QUFDdEIsaUVBQStFO0FBQy9FLHdFQUFrRTtBQUVsRSxvREFBaUQ7QUFDakQsd0NBQXVDO0FBQ3ZDLHdFQUF1RjtBQUV2Riw0REFBb0U7QUFFcEUsTUFBTSxNQUFNLEdBQUc7SUFDYixVQUFVLEVBQUU7UUFDVixRQUFRLEVBQUUsTUFBTTtRQUNoQixVQUFVLEVBQUUsTUFBTTtRQUNsQixLQUFLLEVBQUUsU0FBUztRQUNoQixrQ0FBa0M7UUFDbEMsa0JBQWtCO1FBQ2xCLEtBQUssRUFBRSxNQUFNO1FBQ2IsY0FBYztLQUNRO0lBQ3hCLFNBQVMsRUFBRTtRQUNULElBQUksRUFBRSxDQUFDO0tBQ2U7Q0FDekIsQ0FBQTtBQUtELHdFQUE4QztBQUM5Qyx5REFBcUQ7QUFDckQsOEVBQXFEO0FBRTlDLEtBQUssVUFBVSxrQkFBa0IsQ0FBQyxFQUFFLEdBQUcsRUFBRSxHQUFHLEVBQWlEO0lBQ2hHLDBGQUEwRjtJQUMxRixzQ0FBc0M7SUFDdEMseUVBQXlFO0lBQ3pFLDBCQUFlLENBQUMsSUFBSSxDQUFDLElBQUEsNkJBQWEsR0FBRSxDQUFDLENBQUE7SUFDckMsSUFBSSxPQUFPLENBQUE7SUFDWCxJQUFJLENBQUM7UUFDRCxPQUFPLEdBQUcsTUFBTSxpQkFBTyxDQUFDLFVBQVUsQ0FBQyxHQUFHLEVBQUUsR0FBRyxFQUFFO1lBQ3pDLDZCQUE2QixFQUFFLEtBQUs7Z0JBQ2hDLE9BQU8sRUFBRSxDQUFBO1lBQ2IsQ0FBQztTQUNKLENBQUMsQ0FBQTtJQUNOLENBQUM7SUFBQyxPQUFPLEdBQVEsRUFBRSxDQUFDO1FBQ2hCLElBQUksR0FBRyxDQUFDLElBQUksS0FBSyxpQkFBTyxDQUFDLEtBQUssQ0FBQyxpQkFBaUIsRUFBRSxDQUFDO1lBQy9DLE9BQU8sRUFBRSxLQUFLLEVBQUUsRUFBRSxlQUFlLEVBQUUsZUFBZSxFQUFFLEVBQUUsQ0FBQTtRQUMxRCxDQUFDO2FBQU0sSUFBSSxHQUFHLENBQUMsSUFBSSxLQUFLLGlCQUFPLENBQUMsS0FBSyxDQUFDLFlBQVksRUFBRSxDQUFDO1lBQ2pELGtFQUFrRTtZQUNsRSxxRUFBcUU7WUFDckUsT0FBTyxFQUFFLEtBQUssRUFBRSxFQUFFLGVBQWUsRUFBRSxlQUFlLEVBQUUsRUFBRSxDQUFBO1FBQzFELENBQUM7UUFDRCxNQUFNLEdBQUcsQ0FBQTtJQUNiLENBQUM7SUFFRCxJQUFJLENBQUMsT0FBTyxFQUFFLFNBQVMsRUFBRSxFQUFFLENBQUM7UUFDeEIsT0FBTztZQUNILFFBQVEsRUFBRTtnQkFDTixXQUFXLEVBQUUsdUJBQXVCO2dCQUNwQyxTQUFTLEVBQUUsS0FBSzthQUNuQjtTQUNKLENBQUE7SUFDTCxDQUFDO0lBRUQsT0FBTztRQUNILEtBQUssRUFBRTtZQUNQLEdBQUcsRUFBRSxPQUFPLENBQUMsU0FBUyxFQUFFO1NBQ3ZCO0tBQ0osQ0FBQTtBQUNMLENBQUM7QUFFRCxNQUFNLGVBQWUsR0FBRztJQUN0QjtRQUNFLEtBQUssRUFBRSxlQUFlO1FBQ3RCLEtBQUssRUFBRSxNQUFNO0tBQ2Q7SUFDRDtRQUNFLEtBQUssRUFBRSxlQUFlO1FBQ3RCLEtBQUssRUFBRSxNQUFNO0tBQ2Q7Q0FDRixDQUFBO0FBRUQsU0FBUyxnQkFBZ0I7SUFDdkIsTUFBTSxNQUFNLEdBQUcsSUFBQSxrQkFBUyxHQUFFLENBQUE7SUFDMUIsTUFBTSxFQUFFLEdBQUcsRUFBRSxNQUFNLEVBQUUsR0FBRyxJQUFBLDRCQUFhLEdBQUUsQ0FBQTtJQUV2QyxNQUFNLFFBQVEsR0FBRyxNQUFNLENBQUMsS0FBSyxFQUFFLFFBQW9CLENBQUE7SUFDbkQsTUFBTSxNQUFNLEdBQUcsTUFBTSxDQUFDLEtBQUssRUFBRSxNQUFnQixDQUFBO0lBQzdDLE1BQU0sUUFBUSxHQUFHLE1BQU0sQ0FBQyxLQUFLLEVBQUUsUUFBa0IsQ0FBQTtJQUNqRCxNQUFNLFlBQVksR0FBRyxNQUFNLENBQUMsS0FBSyxFQUFFLFlBQTRCLENBQUE7SUFFL0QsTUFBTSxDQUFDLFdBQVcsRUFBRSxjQUFjLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQVMsQ0FBQyxDQUFDLENBQUE7SUFDekQsTUFBTSxDQUFDLGFBQWEsRUFBRSxnQkFBZ0IsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsR0FBc0IsQ0FBQTtJQUV4RSxNQUFNLENBQUMsV0FBVyxFQUFFLGNBQWMsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBUyxDQUFDLENBQUMsQ0FBQTtJQUN6RCxNQUFNLENBQUMsV0FBVyxFQUFFLGNBQWMsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBTyxJQUFJLElBQUksRUFBRSxDQUFDLENBQUE7SUFDaEUsTUFBTSxDQUFDLGVBQWUsRUFBRSxrQkFBa0IsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBZSxZQUFZLElBQUksTUFBTSxDQUFDLENBQUE7SUFDNUYsTUFBTSxDQUFDLFdBQVcsRUFBRSxjQUFjLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQVMsRUFBRSxDQUFDLENBQUE7SUFDMUQsTUFBTSxDQUFDLFFBQVEsRUFBRSxXQUFXLENBQUMsR0FBRyxJQUFBLGdCQUFRLEdBQWdCLENBQUE7SUFFeEQsTUFBTSxDQUFDLEtBQUssRUFBRSxRQUFRLENBQUMsR0FBRyxJQUFBLGdCQUFRLEdBQWEsQ0FBQTtJQUMvQyxNQUFNLENBQUMsSUFBSSxFQUFFLE9BQU8sQ0FBQyxHQUFHLElBQUEsZ0JBQVEsR0FBWSxDQUFBO0lBRTVDLDJDQUEyQztJQUMzQyxNQUFNLE1BQU0sR0FBRyxHQUFHLENBQUE7SUFDbEIsTUFBTSxLQUFLLEdBQUcsSUFBQSxnQkFBUSxHQUFFLENBQUE7SUFJeEIsV0FBVztJQUNYLElBQUEsaUJBQVMsRUFBQyxHQUFHLEVBQUU7UUFDYixDQUFDLEtBQUssSUFBSSxFQUFFO1lBQ1YsSUFBSSxDQUFDO2dCQUNILElBQUksQ0FBQyxNQUFNLElBQUksQ0FBQyxNQUFNLEVBQUUsQ0FBQztvQkFDdkIsT0FBTTtnQkFDUixDQUFDO2dCQUVELE1BQU0sT0FBTyxHQUFHLE1BQU0sSUFBQSxnQ0FBYyxFQUFDLE1BQU0sRUFBRSxNQUFNLENBQUMsQ0FBQTtnQkFDcEQsT0FBTyxDQUFDLE9BQU8sQ0FBQyxDQUFBO1lBQ2xCLENBQUM7WUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO2dCQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLDJCQUEyQixDQUFDLENBQUE7WUFDN0MsQ0FBQztRQUNILENBQUMsQ0FBQyxFQUFFLENBQUE7SUFDTixDQUFDLEVBQUUsQ0FBQyxNQUFNLEVBQUUsTUFBTSxDQUFDLENBQUMsQ0FBQTtJQUlwQiw4QkFBOEI7SUFDOUIsSUFBQSxpQkFBUyxFQUFDLEdBQUcsRUFBRTtRQUNiLENBQUMsS0FBSyxJQUFJLEVBQUU7WUFDVixJQUFJLENBQUMsTUFBTSxJQUFJLENBQUMsTUFBTSxFQUFFLENBQUM7Z0JBQ3ZCLE9BQU07WUFDUixDQUFDO1lBQ0QsTUFBTSxNQUFNLEdBQUcsTUFBTSxJQUFBLGlEQUFnQyxFQUFDLE1BQU0sRUFBRSxNQUFNLENBQUMsQ0FBQTtZQUNyRSxJQUFJLENBQUMsTUFBTSxFQUFFLEVBQUUsRUFBRSxDQUFDO2dCQUNoQixPQUFPLENBQUMsR0FBRyxDQUFDLGdDQUFnQyxDQUFDLENBQUE7Z0JBQzdDLE9BQU07WUFDUixDQUFDO1lBQ0QsV0FBVyxDQUFDLE1BQU0sQ0FBQyxDQUFBO1FBQ3JCLENBQUMsQ0FBQyxFQUFFLENBQUE7SUFDTixDQUFDLEVBQUUsQ0FBQyxNQUFNLEVBQUUsTUFBTSxDQUFDLENBQUMsQ0FBQTtJQUVwQixZQUFZO0lBQ1osSUFBQSxpQkFBUyxFQUFDLEdBQUcsRUFBRTtRQUNiLENBQUMsS0FBSyxJQUFJLEVBQUU7WUFDVixJQUFJLENBQUMsTUFBTSxJQUFJLENBQUMsTUFBTSxFQUFFLENBQUM7Z0JBQ3ZCLE9BQU07WUFDUixDQUFDO1lBQ0QsSUFBSSxJQUFJLEVBQUUsRUFBRSxFQUFFLENBQUM7Z0JBQ2IsTUFBTSxRQUFRLEdBQUcsTUFBTSxJQUFBLGlDQUFjLEVBQUMsTUFBTSxFQUFFLElBQUksRUFBRSxPQUFPLENBQUMsQ0FBQTtnQkFDNUQsSUFBSSxDQUFDLFFBQVEsRUFBRSxFQUFFLEVBQUUsQ0FBQztvQkFDbEIsT0FBTyxDQUFDLEdBQUcsQ0FBQyxxQkFBcUIsQ0FBQyxDQUFBO29CQUNsQyxPQUFNO2dCQUNSLENBQUM7Z0JBQ0QsT0FBTyxDQUFDLEdBQUcsQ0FBQyxRQUFRLEVBQUUsRUFBRSxFQUFFLHVDQUF1QyxDQUFDLENBQUE7Z0JBQ2xFLE9BQU8sQ0FBQyxHQUFHLENBQUMsUUFBUSxFQUFFLFlBQVksRUFBRSxpREFBaUQsQ0FBQyxDQUFBO2dCQUN0RixPQUFPLENBQUMsR0FBRyxDQUFDLFFBQVEsRUFBRSxZQUFZLEVBQUUsaURBQWlELENBQUMsQ0FBQTtnQkFDdEYsUUFBUSxDQUFDLFFBQVEsQ0FBQyxDQUFBO2dCQUNsQixjQUFjLENBQUMsUUFBUSxDQUFDLFFBQVEsQ0FBQyxDQUFBO2dCQUNqQyxjQUFjLENBQUMsQ0FBQyxRQUFRLEVBQUUsWUFBWSxJQUFJLElBQUEsa0JBQUssRUFBQyxRQUFRLEVBQUUsWUFBWSxDQUFDLENBQUMsRUFBRSxDQUFDLFFBQVEsRUFBRSxRQUFRLElBQUksa0JBQUssQ0FBQyxFQUFFLENBQUMsS0FBSyxFQUFFLEVBQUUsSUFBSSxDQUFDLENBQUMsTUFBTSxFQUFFLENBQUMsSUFBSSxDQUFDLFFBQVEsRUFBRSxZQUFZLElBQUksSUFBQSxrQkFBSyxFQUFDLFFBQVEsRUFBRSxZQUFZLENBQUMsQ0FBQyxFQUFFLENBQUMsUUFBUSxFQUFFLFFBQVEsSUFBSSxrQkFBSyxDQUFDLEVBQUUsQ0FBQyxLQUFLLEVBQUUsQ0FBQyxDQUFDLE1BQU0sRUFBRSxDQUFDLElBQUksSUFBSSxJQUFJLEVBQUUsQ0FBQyxDQUFBO2dCQUNsUSxrQkFBa0IsQ0FBQyxRQUFRLEVBQUUsWUFBWSxDQUFDLENBQUMsQ0FBQyxNQUFNLENBQUMsQ0FBQyxDQUFDLE1BQU0sQ0FBQyxDQUFBO2dCQUM1RCxjQUFjLENBQUMsUUFBUSxFQUFFLFFBQVEsSUFBSSxDQUFDLENBQUMsQ0FBQTtnQkFDdkMscUJBQXFCO1lBR3ZCLENBQUM7UUFDSCxDQUFDLENBQUMsRUFBRSxDQUFBO0lBQ04sQ0FBQyxFQUFFLENBQUMsTUFBTSxFQUFFLElBQUksRUFBRSxPQUFPLEVBQUUsSUFBSSxFQUFFLEVBQUUsRUFBRSxNQUFNLEVBQUUsUUFBUSxDQUFDLENBQUMsQ0FBQTtJQUV2RCxNQUFNLGdCQUFnQixHQUFHLENBQUMsUUFBZ0IsR0FBRyxFQUFFLEVBQUU7UUFDM0MsTUFBTSxRQUFRLEdBQUcsUUFBUSxDQUFDLEtBQUssQ0FBQyxPQUFPLENBQUMsVUFBVSxFQUFFLEVBQUUsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFBO1FBQzVELFdBQVc7UUFDWCxJQUFJLFFBQVEsR0FBRyxDQUFDLEVBQUUsQ0FBQztZQUNuQixjQUFjLENBQUMsQ0FBQyxDQUFDLENBQUE7WUFDakIsT0FBTTtRQUNOLENBQUM7UUFFRCxJQUFJLEtBQUssQ0FBQyxRQUFRLENBQUMsRUFBRSxDQUFDO1lBQ3RCLGNBQWMsQ0FBQyxDQUFDLENBQUMsQ0FBQTtZQUNqQixPQUFNO1FBQ04sQ0FBQztRQUVELGNBQWMsQ0FBQyxRQUFRLENBQUMsS0FBSyxDQUFDLE9BQU8sQ0FBQyxVQUFVLEVBQUUsRUFBRSxDQUFDLEVBQUUsRUFBRSxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUE7SUFDcEUsQ0FBQyxDQUFBO0lBRUgscUJBQXFCO0lBQ3JCLE1BQU0sY0FBYyxHQUFHLEtBQUssRUFDMUIsUUFBaUIsRUFDakIsWUFBcUIsRUFDckIsWUFBcUIsRUFDckIsT0FBZ0IsRUFDaEIsRUFBRTtRQUNGLElBQUksQ0FBQztZQUNILElBQUksQ0FBQyxNQUFNLEVBQUUsQ0FBQztnQkFDWixPQUFNLENBQUMsZ0RBQWdEO1lBQ3pELENBQUM7WUFFRCxNQUFNLFlBQVksR0FBRyxnQkFBQyxDQUFDLFNBQVMsQ0FBQyxJQUFJLENBQUMsQ0FBQTtZQUV0QyxXQUFXO1lBQ1gsSUFBSSxDQUFDLFlBQVksRUFBRSxDQUFDO2dCQUNsQixPQUFPLENBQUMsR0FBRyxDQUFDLGdEQUFnRCxDQUFDLENBQUE7Z0JBQzdELE9BQU07WUFDUixDQUFDO1lBRUQsSUFBSSxRQUFRLEtBQUssU0FBUyxFQUFFLENBQUM7Z0JBQzNCLFlBQVksQ0FBQyxRQUFRLEdBQUcsUUFBUSxDQUFBO1lBQ2xDLENBQUM7WUFFRCxJQUFJLFlBQVksS0FBSyxTQUFTLEVBQUUsQ0FBQztnQkFDL0IsWUFBWSxDQUFDLFlBQVksR0FBRyxZQUFZLENBQUE7WUFDMUMsQ0FBQztZQUVELElBQUksWUFBWSxLQUFLLFNBQVMsRUFBRSxDQUFDO2dCQUMvQixZQUFZLENBQUMsWUFBWSxHQUFHLFlBQVksQ0FBQTtZQUMxQyxDQUFDO1lBRUQsSUFBSSxPQUFPLEtBQUssU0FBUyxFQUFFLENBQUM7Z0JBQ3hCLFlBQVksQ0FBQyxPQUFPLEdBQUcsR0FBRyxPQUFPLElBQUksUUFBUSxFQUFFLEVBQUUsRUFBRSxDQUFBO1lBQ3ZELENBQUM7WUFFRCxNQUFNLElBQUEsb0NBQWtCLEVBQUMsTUFBTSxFQUFFLFlBQVksQ0FBQyxDQUFBO1lBRTlDLE9BQU8sQ0FBQyxZQUFZLENBQUMsQ0FBQTtRQUV2QixDQUFDO1FBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztZQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLDhCQUE4QixDQUFDLENBQUE7UUFDaEQsQ0FBQztJQUNILENBQUMsQ0FBQTtJQUdELHNCQUFzQjtJQUN0QixNQUFNLHVCQUF1QixHQUFHLEtBQUssSUFBSSxFQUFFO1FBQ3pDOztXQUVHO1FBQ0gsSUFBSSxDQUFDO1lBRUgsSUFBSSxDQUFDLE1BQU0sSUFBSSxDQUFDLElBQUksRUFBRSxDQUFDO2dCQUNyQiwwRUFBMEU7Z0JBQzFFLE9BQU07WUFDUixDQUFDO1lBRUQsTUFBTSxPQUFPLEdBQUcsTUFBTSxJQUFBLHVDQUFxQixFQUN6QyxNQUFNLEVBQ04sTUFBTSxFQUNOLElBQUksRUFBRSxLQUFLLEVBQ1gsV0FBVyxFQUNYLE1BQU0sRUFDTixRQUFRLEVBQ1IsV0FBVyxFQUNYLGVBQWUsS0FBSyxNQUFNLENBQUMsQ0FBQyxDQUFDLElBQUEsa0JBQUssRUFBQyxXQUFXLENBQUMsQ0FBQyxNQUFNLEVBQUUsQ0FBQyxDQUFDLENBQUMsU0FBUyxFQUNwRSxlQUFlLEtBQUssTUFBTSxDQUFDLENBQUMsQ0FBQyxJQUFBLGtCQUFLLEVBQUMsV0FBVyxDQUFDLENBQUMsTUFBTSxFQUFFLENBQUMsQ0FBQyxDQUFDLFNBQVMsRUFDcEUsU0FBUyxFQUNULFNBQVMsRUFDVCxRQUFRLENBQUMsT0FBTyxFQUNoQixTQUFTLEVBQ1QsSUFBSSxFQUFFLEtBQUssQ0FDWixDQUFBO1lBRUQsTUFBTSxjQUFjLENBQ2xCLFdBQVcsRUFDWCxlQUFlLEtBQUssTUFBTSxDQUFDLENBQUMsQ0FBQyxJQUFBLGtCQUFLLEVBQUMsV0FBVyxDQUFDLENBQUMsTUFBTSxFQUFFLENBQUMsQ0FBQyxDQUFDLFNBQVMsRUFDcEUsZUFBZSxLQUFLLE1BQU0sQ0FBQyxDQUFDLENBQUMsSUFBQSxrQkFBSyxFQUFDLFdBQVcsQ0FBQyxDQUFDLE1BQU0sRUFBRSxDQUFDLENBQUMsQ0FBQyxTQUFTLEVBQ3BFLE9BQU8sQ0FBQyxDQUFDLENBQUMsR0FBRyxPQUFPLElBQUksUUFBUSxFQUFFLEVBQUUsRUFBRSxDQUFDLENBQUMsQ0FBQyxTQUFTLENBQ25ELENBQUE7WUFFRCxJQUFJLFFBQVEsS0FBSyxzQkFBVSxFQUFFLENBQUM7Z0JBRTFCLE1BQU0sSUFBQSx3Q0FBc0IsRUFBQyxNQUFNLEVBQUUsTUFBTSxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQyxNQUFNLEVBQUUsRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLEtBQUssQ0FBQyxDQUFDLElBQUksQ0FBQyxFQUFFLENBQUMsQ0FBQyxNQUFNLENBQUMsRUFBRSxDQUFDLENBQUMsTUFBTSxFQUFFLEVBQUUsS0FBSyxDQUFDLENBQUE7WUFHckksQ0FBQztpQkFBTSxJQUFJLFFBQVEsS0FBSyxxQkFBUyxFQUFFLENBQUM7Z0JBRWxDLE1BQU0sSUFBQSx3Q0FBc0IsRUFBQyxNQUFNLEVBQUUsTUFBTSxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQyxNQUFNLEVBQUUsRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxJQUFJLENBQUMsRUFBRSxDQUFDLENBQUMsTUFBTSxDQUFDLEVBQUUsQ0FBQyxDQUFDLE1BQU0sRUFBRSxFQUFFLEtBQUssQ0FBQyxDQUFBO1lBRXJILENBQUM7WUFFRCxLQUFLLENBQUM7Z0JBQ0osTUFBTSxFQUFFLFNBQVM7Z0JBQ2pCLEtBQUssRUFBRSx1QkFBdUI7Z0JBQzlCLFdBQVcsRUFBRSxzQ0FBc0M7Z0JBQ25ELFFBQVEsRUFBRSxJQUFJO2dCQUNkLFVBQVUsRUFBRSxJQUFJO2FBQ2pCLENBQUMsQ0FBQTtZQUVGLE1BQU0sQ0FBQyxJQUFJLENBQUMsRUFBRSxRQUFRLEVBQUUseUJBQXlCLEVBQUUsS0FBSyxFQUFFO29CQUN4RCxRQUFRO29CQUNSLFFBQVEsRUFBRSxJQUFBLFNBQUksR0FBRTtpQkFDakIsRUFBQyxDQUFDLENBQUE7UUFDTCxDQUFDO1FBQUMsT0FBTSxDQUFDLEVBQUUsQ0FBQztZQUNWLG9EQUFvRDtZQUNwRCxLQUFLLENBQUM7Z0JBQ0osTUFBTSxFQUFFLE9BQU87Z0JBQ2YsS0FBSyxFQUFFLHFCQUFxQjtnQkFDNUIsV0FBVyxFQUFFLGtFQUFrRTtnQkFDL0UsUUFBUSxFQUFFLElBQUk7Z0JBQ2QsVUFBVSxFQUFFLElBQUk7YUFDakIsQ0FBQyxDQUFBO1lBQ0YsTUFBTSxDQUFDLElBQUksQ0FBQyxFQUFFLFFBQVEsRUFBRSx5QkFBeUIsRUFBRSxLQUFLLEVBQUU7b0JBQ3hELFFBQVE7b0JBQ1IsUUFBUSxFQUFFLFNBQVM7aUJBQ3BCLEVBQUMsQ0FBQyxDQUFBO1lBQ0gsOEJBQThCO1lBQzlCLDZCQUE2QjtRQUMvQixDQUFDO0lBQ0gsQ0FBQyxDQUFBO0lBRUQsTUFBTSx1QkFBdUIsR0FBRyxLQUFLLElBQUksRUFBRTtRQUMxQyxJQUFJLENBQUM7WUFFSCxJQUFJLElBQUksRUFBRSxDQUFDO2dCQUVSLE9BQU8sQ0FBQyxHQUFHLENBQUMsZUFBZSxFQUFFLDBDQUEwQyxDQUFDLENBQUE7Z0JBRXhFLE1BQU0sUUFBUSxHQUFHLE1BQU0sSUFBQSxpQ0FBYyxFQUFDLE1BQU0sRUFBRSxJQUFJLENBQUMsT0FBTyxDQUFDLENBQUE7Z0JBRTNELE1BQU0sSUFBQSxrQ0FBZ0IsRUFDcEIsSUFBSSxFQUFFLE9BQU8sRUFDYixRQUFRLEVBQUUsU0FBUyxFQUNuQixRQUFRLEVBQUUsT0FBTyxFQUNqQixNQUFNLEVBQ04sTUFBTSxFQUNOLFFBQVEsRUFBRSxVQUFVLEVBQ3BCLFNBQVMsRUFDVCxJQUFJLENBQUMsS0FBSyxFQUNWLFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsSUFBSSxDQUFDLEtBQUssRUFDVixTQUFTLEVBQ1QsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsSUFBSSxFQUNKLEtBQUssRUFDTCxLQUFLLEVBQ0wsS0FBSyxFQUNMLEtBQUssRUFDTCxTQUFTLEVBQ1QsTUFBTSxFQUNOLFFBQVEsRUFDUixTQUFTLEVBQ1QsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxFQUNULElBQUksQ0FBQyxLQUFLLEVBQ1YsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxFQUNULFFBQVEsS0FBSyxPQUFPLEVBQ3BCLFFBQVEsS0FBSyxRQUFRLEVBQ3JCLFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxFQUNULElBQUksRUFDSixTQUFTLEVBQ1QsSUFBSSxFQUNKLElBQUksRUFDSixJQUFJLEVBQ0osZUFBZSxLQUFLLE1BQU0sQ0FBQyxDQUFDLENBQUMsSUFBQSxrQkFBSyxFQUFDLFdBQVcsQ0FBQyxDQUFDLE1BQU0sRUFBRSxDQUFDLENBQUMsQ0FBQyxJQUFJLEVBQy9ELGVBQWUsS0FBSyxNQUFNLENBQUMsQ0FBQyxDQUFDLElBQUEsa0JBQUssRUFBQyxXQUFXLENBQUMsQ0FBQyxNQUFNLEVBQUUsQ0FBQyxDQUFDLENBQUMsSUFBSSxFQUMvRCxTQUFTLEVBQ1QsU0FBUyxFQUNULFNBQVMsRUFDVCxTQUFTLEVBQ1QsV0FBVyxFQUNYLFNBQVMsRUFDVCxJQUFJLEVBQ0osUUFBUSxFQUNSLFNBQVMsRUFDVCxTQUFTLEVBQ1QsU0FBUyxDQUNWLENBQUE7Z0JBRUQsTUFBTSxjQUFjLENBQ2xCLFdBQVcsRUFDWCxlQUFlLEtBQUssTUFBTSxDQUFDLENBQUMsQ0FBQyxJQUFBLGtCQUFLLEVBQUMsV0FBVyxDQUFDLENBQUMsTUFBTSxFQUFFLENBQUMsQ0FBQyxDQUFDLElBQUksRUFDL0QsZUFBZSxLQUFLLE1BQU0sQ0FBQyxDQUFDLENBQUMsSUFBQSxrQkFBSyxFQUFDLFdBQVcsQ0FBQyxDQUFDLE1BQU0sRUFBRSxDQUFDLENBQUMsQ0FBQyxJQUFJLENBQ2hFLENBQUE7WUFFSCxDQUFDO1lBRUYsSUFBSSxLQUFLLENBQUMsWUFBWSxJQUFJLENBQUMsZUFBZSxLQUFLLE1BQU0sQ0FBQyxFQUFFLENBQUM7Z0JBQ3hELE9BQU8sQ0FBQyxHQUFHLENBQUMsb0RBQW9ELENBQUMsQ0FBQTtnQkFDaEUsSUFBSSxRQUFRLEtBQUssc0JBQVUsRUFBRSxDQUFDO29CQUV6QixNQUFNLElBQUEsd0NBQXNCLEVBQUMsTUFBTSxFQUFFLE1BQU0sRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUMsTUFBTSxFQUFFLEVBQUUsSUFBQSxrQkFBSyxHQUFFLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxLQUFLLENBQUMsQ0FBQyxJQUFJLENBQUMsRUFBRSxDQUFDLENBQUMsTUFBTSxDQUFDLEVBQUUsQ0FBQyxDQUFDLE1BQU0sRUFBRSxFQUFFLEtBQUssQ0FBQyxDQUFBO2dCQUV0SSxDQUFDO3FCQUFNLElBQUksUUFBUSxLQUFLLHFCQUFTLEVBQUUsQ0FBQztvQkFFakMsTUFBTSxJQUFBLHdDQUFzQixFQUFDLE1BQU0sRUFBRSxNQUFNLEVBQUUsSUFBQSxrQkFBSyxHQUFFLENBQUMsSUFBSSxDQUFDLENBQUMsQ0FBQyxDQUFDLE1BQU0sRUFBRSxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLElBQUksQ0FBQyxFQUFFLENBQUMsQ0FBQyxNQUFNLENBQUMsRUFBRSxDQUFDLENBQUMsTUFBTSxFQUFFLEVBQUUsS0FBSyxDQUFDLENBQUE7Z0JBRXZILENBQUM7WUFDRixDQUFDO2lCQUFNLElBQUksS0FBSyxDQUFDLFlBQVksSUFBSSxDQUFDLGVBQWUsS0FBSyxNQUFNLENBQUMsRUFBRSxDQUFDO2dCQUM5RCxPQUFPLENBQUMsR0FBRyxDQUFDLG9EQUFvRCxDQUFDLENBQUE7Z0JBQ2xFLElBQUksUUFBUSxLQUFLLHNCQUFVLEVBQUUsQ0FBQztvQkFFMUIsTUFBTSxJQUFBLHdDQUFzQixFQUFDLE1BQU0sRUFBRSxNQUFNLEVBQUUsSUFBQSxrQkFBSyxHQUFFLENBQUMsSUFBSSxDQUFDLENBQUMsQ0FBQyxDQUFDLE1BQU0sRUFBRSxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsS0FBSyxDQUFDLENBQUMsSUFBSSxDQUFDLEVBQUUsQ0FBQyxDQUFDLE1BQU0sQ0FBQyxFQUFFLENBQUMsQ0FBQyxNQUFNLEVBQUUsRUFBRSxLQUFLLENBQUMsQ0FBQTtnQkFFckksQ0FBQztxQkFBTSxJQUFJLFFBQVEsS0FBSyxxQkFBUyxFQUFFLENBQUM7b0JBRWhDLE1BQU0sSUFBQSx3Q0FBc0IsRUFBQyxNQUFNLEVBQUUsTUFBTSxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQyxNQUFNLEVBQUUsRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxJQUFJLENBQUMsRUFBRSxDQUFDLENBQUMsTUFBTSxDQUFDLEVBQUUsQ0FBQyxDQUFDLE1BQU0sRUFBRSxFQUFFLEtBQUssQ0FBQyxDQUFBO2dCQUV2SCxDQUFDO1lBQ0YsQ0FBQztpQkFBTSxJQUFJLEtBQUssQ0FBQyxZQUFZO21CQUN4QixDQUFDLFlBQVksS0FBSyxNQUFNLENBQUM7bUJBQ3pCLENBQUMsQ0FBQyxJQUFBLGtCQUFLLEVBQUMsS0FBSyxDQUFDLFlBQVksRUFBRSxLQUFLLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMsRUFBRSxDQUFDLEtBQUssRUFBRSxRQUFRLElBQUksa0JBQUssQ0FBQyxFQUFFLENBQUMsS0FBSyxFQUFFLEVBQUUsSUFBSSxDQUFDLENBQUMsTUFBTSxDQUFDLElBQUEsa0JBQUssRUFBQyxXQUFXLENBQUMsQ0FBQyxNQUFNLEVBQUUsRUFBRSxRQUFRLENBQUMsQ0FBQyxFQUFFLENBQUM7Z0JBRTdJLElBQUksUUFBUSxLQUFLLHNCQUFVLEVBQUUsQ0FBQztvQkFDMUIsTUFBTSxJQUFBLHdDQUFzQixFQUFDLE1BQU0sRUFBRSxNQUFNLEVBQUUsSUFBQSxrQkFBSyxHQUFFLENBQUMsSUFBSSxDQUFDLENBQUMsQ0FBQyxDQUFDLE1BQU0sRUFBRSxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsS0FBSyxDQUFDLENBQUMsSUFBSSxDQUFDLEVBQUUsQ0FBQyxDQUFDLE1BQU0sQ0FBQyxFQUFFLENBQUMsQ0FBQyxNQUFNLEVBQUUsRUFBRSxLQUFLLENBQUMsQ0FBQTtnQkFDckksQ0FBQztxQkFBTSxJQUFJLFFBQVEsS0FBSyxxQkFBUyxFQUFFLENBQUM7b0JBRWhDLE1BQU0sSUFBQSx3Q0FBc0IsRUFBQyxNQUFNLEVBQUUsTUFBTSxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQyxNQUFNLEVBQUUsRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxJQUFJLENBQUMsRUFBRSxDQUFDLENBQUMsTUFBTSxDQUFDLEVBQUUsQ0FBQyxDQUFDLE1BQU0sRUFBRSxFQUFFLEtBQUssQ0FBQyxDQUFBO2dCQUV2SCxDQUFDO1lBQ0YsQ0FBQztpQkFBTyxJQUFJLEtBQUssQ0FBQyxZQUFZO21CQUN4QixDQUFDLFlBQVksS0FBSyxNQUFNLENBQUM7bUJBQ3pCLENBQUMsQ0FBQyxJQUFBLGtCQUFLLEVBQUMsS0FBSyxDQUFDLFlBQVksRUFBRSxLQUFLLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMsRUFBRSxDQUFDLEtBQUssRUFBRSxRQUFRLElBQUksa0JBQUssQ0FBQyxFQUFFLENBQUMsS0FBSyxFQUFFLEVBQUUsSUFBSSxDQUFDLENBQUMsTUFBTSxDQUFDLElBQUEsa0JBQUssRUFBQyxXQUFXLENBQUMsQ0FBQyxNQUFNLEVBQUUsQ0FBQyxDQUFDLEVBQUUsQ0FBQztnQkFFbEksSUFBSSxRQUFRLEtBQUssUUFBUSxFQUFFLENBQUM7b0JBRXhCLE1BQU0sSUFBQSx3Q0FBc0IsRUFBQyxNQUFNLEVBQUUsTUFBTSxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQyxNQUFNLEVBQUUsRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLEtBQUssQ0FBQyxDQUFDLElBQUksQ0FBQyxFQUFFLENBQUMsQ0FBQyxNQUFNLENBQUMsRUFBRSxDQUFDLENBQUMsTUFBTSxFQUFFLEVBQUUsS0FBSyxDQUFDLENBQUE7Z0JBRXJJLENBQUM7cUJBQU0sSUFBSSxRQUFRLEtBQUssT0FBTyxFQUFFLENBQUM7b0JBRTlCLE1BQU0sSUFBQSx3Q0FBc0IsRUFBQyxNQUFNLEVBQUUsTUFBTSxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQyxNQUFNLEVBQUUsRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxJQUFJLENBQUMsRUFBRSxDQUFDLENBQUMsTUFBTSxDQUFDLEVBQUUsQ0FBQyxDQUFDLE1BQU0sRUFBRSxFQUFFLEtBQUssQ0FBQyxDQUFBO2dCQUV2SCxDQUFDO1lBQ0osQ0FBQztZQUVELEtBQUssQ0FBQztnQkFDSCxNQUFNLEVBQUUsU0FBUztnQkFDakIsS0FBSyxFQUFFLHNCQUFzQjtnQkFDN0IsV0FBVyxFQUFFLDhCQUE4QjtnQkFDM0MsUUFBUSxFQUFFLElBQUk7Z0JBQ2QsVUFBVSxFQUFFLElBQUk7YUFDbEIsQ0FBQyxDQUFBO1lBQ0QsTUFBTSxDQUFDLElBQUksQ0FBQyxFQUFFLFFBQVEsRUFBRSx5QkFBeUIsRUFBRSxLQUFLLEVBQUU7b0JBQ3hELFFBQVE7b0JBQ1IsUUFBUSxFQUFFLElBQUEsU0FBSSxHQUFFO2lCQUNqQixFQUFDLENBQUMsQ0FBQTtRQUNOLENBQUM7UUFBQyxPQUFNLENBQUMsRUFBRSxDQUFDO1lBQ1YsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsNEJBQTRCLENBQUMsQ0FBQTtZQUM1QyxLQUFLLENBQUM7Z0JBQ0gsTUFBTSxFQUFFLE9BQU87Z0JBQ2YsS0FBSyxFQUFFLGtCQUFrQjtnQkFDekIsV0FBVyxFQUFFLG9EQUFvRDtnQkFDakUsUUFBUSxFQUFFLElBQUk7Z0JBQ2QsVUFBVSxFQUFFLElBQUk7YUFDbEIsQ0FBQyxDQUFBO1lBQ0gscUNBQXFDO1lBQ3JDLGVBQWU7WUFDZiwwQkFBMEI7WUFDMUIsTUFBTTtRQUNQLENBQUM7SUFDRixDQUFDLENBQUE7SUFFRCxNQUFNLG9CQUFvQixHQUFHLENBQUMsS0FBYSxFQUFFLEVBQUUsQ0FBQyxjQUFjLENBQUMsS0FBSyxDQUFDLENBQUE7SUFFckUsTUFBTSxZQUFZLEdBQUcsR0FBRyxFQUFFO1FBQ3hCLE1BQU0sZUFBZSxHQUFHLFdBQVcsQ0FBQTtRQUNuQyxNQUFNLGNBQWMsR0FBRyxlQUFlLEtBQUssQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLGVBQWUsR0FBRyxDQUFDLENBQUE7UUFDdEUsY0FBYyxDQUFDLGNBQWMsQ0FBQyxDQUFBO0lBQ2hDLENBQUMsQ0FBQTtJQUVELE1BQU0sZ0JBQWdCLEdBQUcsR0FBRyxFQUFFO1FBQzVCLElBQUksV0FBVyxLQUFLLENBQUMsRUFBRSxDQUFDO1lBQ3RCLE9BQU8sdUJBQUMsYUFBRyxJQUFFLENBQUMsRUFBRSxFQUFFLEtBQUssRUFBRSxHQUFHLEVBQUUsTUFBTSxFQUFFLEdBQUcsRUFBRSxHQUFJLENBQUE7UUFDakQsQ0FBQztRQUVELE9BQU8sQ0FDTCx1QkFBQyxhQUFHLElBQUUsRUFBRSxFQUFFLEVBQUUsS0FBSyxFQUFFLEdBQUcsRUFBRSxNQUFNLEVBQUUsR0FBRyxFQUFFLEVBQUUsRUFBRSxFQUFFLEVBQUUsS0FBSyxFQUFFLEdBQUcsRUFBRSxNQUFNLEVBQUUsR0FBRyxFQUFFLFlBQ3BFLHVCQUFDLGdCQUFNLElBQUMsT0FBTyxFQUFFLFlBQVkscUJBRXBCLEdBQ0wsQ0FDUCxDQUFBO0lBQ0gsQ0FBQyxDQUFBO0lBRUQsTUFBTSxnQkFBZ0IsR0FBRyxHQUFHLEVBQUU7UUFDNUIsSUFBSSxXQUFXLEtBQUssQ0FBQyxFQUFFLENBQUM7WUFDdEIsT0FBTyx1QkFBQyxhQUFHLElBQUMsRUFBRSxFQUFFLEVBQUUsS0FBSyxFQUFFLEdBQUcsRUFBRSxNQUFNLEVBQUUsR0FBRyxFQUFFLEdBQUksQ0FBQTtRQUNqRCxDQUFDO1FBRUQsT0FBTyxDQUNMLHVCQUFDLGFBQUcsSUFBQyxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsR0FBRyxFQUFFLE1BQU0sRUFBRSxHQUFHLEVBQUUsRUFBRSxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsR0FBRyxFQUFFLE1BQU0sRUFBRSxHQUFHLEVBQUUsWUFDbkUsdUJBQUMsZ0JBQU0sSUFBQyxPQUFPLEVBQUUsWUFBWSxxQkFFcEIsR0FDTCxDQUNQLENBQUE7SUFDSCxDQUFDLENBQUE7SUFFRCxNQUFNLFlBQVksR0FBRyxHQUFHLEVBQUU7UUFDeEIsTUFBTSxlQUFlLEdBQUcsV0FBVyxDQUFBO1FBQ25DLE1BQU0saUJBQWlCLEdBQUcsYUFBYSxDQUFBO1FBRXZDLElBQUksZUFBZSxLQUFLLENBQUMsRUFBRSxDQUFDO1lBQzFCLE9BQU07UUFDUixDQUFDO1FBRUQsTUFBTSxjQUFjLEdBQUcsZUFBZSxHQUFHLENBQUMsQ0FBQTtRQUUxQyxJQUFJLENBQUMsaUJBQWlCLElBQUksQ0FBQyxpQkFBaUIsR0FBRyxlQUFlLENBQUMsRUFBRSxDQUFDO1lBQ2hFLE1BQU0sZ0JBQWdCLEdBQUcsZUFBZSxDQUFBO1lBQ3hDLGdCQUFnQixDQUFDLGdCQUFnQixDQUFDLENBQUE7UUFDcEMsQ0FBQztRQUVELElBQUksY0FBYyxLQUFLLGVBQWUsRUFBRSxDQUFDO1lBQ3ZDLGNBQWMsQ0FBQyxjQUFjLENBQUMsQ0FBQTtRQUNoQyxDQUFDO0lBQ0gsQ0FBQyxDQUFBO0lBRUQsTUFBTSxhQUFhLEdBQUcsR0FBRyxFQUFFO1FBQ3pCLElBQUksQ0FBQztZQUNILE9BQU8sUUFBUTtnQkFDYixDQUFDLENBQUMsdUJBQXVCLEVBQUU7Z0JBQzNCLENBQUMsQ0FBQyx1QkFBdUIsRUFBRSxDQUFBO1FBQy9CLENBQUM7UUFBQyxPQUFNLENBQUMsRUFBRSxDQUFDO1lBQ1YsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsaURBQWlELENBQUMsQ0FBQTtRQUNuRSxDQUFDO0lBQ0gsQ0FBQyxDQUFBO0lBSUQsTUFBTSxpQkFBaUIsR0FBRyxHQUFHLEVBQUU7UUFFN0IsUUFBTyxXQUFXLEVBQUUsQ0FBQztZQUNuQixLQUFLLENBQUM7Z0JBQ0osT0FBTyxDQUNMLHdCQUFDLGFBQUcsSUFBQyxjQUFjLEVBQUMsUUFBUSxFQUFDLFVBQVUsRUFBQyxRQUFRLGFBQzlDLHVCQUFDLGNBQUksSUFBQyxTQUFTLEVBQUMsUUFBUSxFQUFDLE9BQU8sRUFBQyxXQUFXLEVBQUMsRUFBRSxFQUFFLEVBQUUsS0FBSyxFQUFFLEdBQUcsRUFBRSxNQUFNLEVBQUUsR0FBRyxFQUFFLHlCQUVyRSxFQUNQLGlDQUFLLFNBQVMsRUFBQyxpREFBaUQsRUFBQyxLQUFLLEVBQUUsRUFBRSxTQUFTLEVBQUUsTUFBTSxFQUFDLGFBQzFGLHVCQUFDLGFBQUcsSUFBRSxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsR0FBRyxFQUFFLE1BQU0sRUFBRSxHQUFHLEVBQUUsRUFBRSxjQUFjLEVBQUMsUUFBUSxFQUFDLFVBQVUsRUFBQyxRQUFRLEVBQUMsS0FBSyxFQUFFLEVBQUUsS0FBSyxFQUFFLE1BQU0sRUFBRSxZQUV6Ryx1QkFBQyxhQUFLLElBQ0osV0FBVyxFQUFDLHNCQUFzQixFQUNsQyxJQUFJLEVBQUMsSUFBSSxFQUNULElBQUksRUFBQyxnQkFBZ0IsRUFDckIsUUFBUSxFQUFFLENBQUMsQ0FBQyxFQUFFLEVBQUU7NENBQ1YsY0FBYyxDQUFDLElBQUEsa0JBQUssRUFBQyxDQUFDLEVBQUUsTUFBTSxFQUFFLEtBQUssRUFBRSxrQkFBa0IsQ0FBQyxDQUFDLE1BQU0sRUFBRSxDQUFDLENBQUE7d0NBQzFFLENBQUMsRUFDRCxLQUFLLEVBQUUsSUFBQSxrQkFBSyxFQUFDLFdBQVcsQ0FBQyxDQUFDLE1BQU0sQ0FBQyxrQkFBa0IsQ0FBQyxHQUNwRCxHQUNFLEVBQ04sdUJBQUMsYUFBRyxJQUFFLEVBQUUsRUFBRSxFQUFFLEtBQUssRUFBRSxHQUFHLEVBQUUsTUFBTSxFQUFFLEdBQUcsRUFBRSxFQUFFLGNBQWMsRUFBQyxRQUFRLEVBQUMsVUFBVSxFQUFDLFFBQVEsWUFDaEYsb0NBQVEsS0FBSyxFQUFFLGVBQWUsRUFBRSxRQUFRLEVBQUUsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLGtCQUFrQixDQUFDLENBQUMsRUFBRSxNQUFNLEVBQUUsS0FBcUIsQ0FBQyxFQUFFLFNBQVMsRUFBQyx1Q0FBdUMsYUFDdEosbUNBQVEsUUFBUSxRQUFDLFFBQVEsc0NBQXlCLEVBQ2pELGdCQUFDLENBQUMsR0FBRyxDQUFDLGVBQWUsRUFBRSxNQUFNLENBQUMsRUFBRSxDQUFDLENBQzlCLG1DQUVJLEtBQUssRUFBRSxNQUFNLENBQUMsS0FBSyxZQUNyQixNQUFNLENBQUMsS0FBSyxJQUZMLE1BQU0sQ0FBQyxLQUFLLENBRUcsQ0FDdkIsQ0FBQyxJQUNDLEdBQ0wsRUFDTix1QkFBQyxhQUFHLElBQUUsRUFBRSxFQUFFLEVBQUUsS0FBSyxFQUFFLEdBQUcsRUFBRSxNQUFNLEVBQUUsR0FBRyxFQUFFLEVBQUUsY0FBYyxFQUFDLFFBQVEsRUFBQyxVQUFVLEVBQUMsUUFBUSxFQUFDLEtBQUssRUFBRSxFQUFFLEtBQUssRUFBRSxNQUFNLEVBQUUsWUFFdkcsdUJBQUMsbUJBQVMsSUFDUixLQUFLLEVBQUMsb0JBQW9CLEVBQzFCLElBQUksRUFBQyxRQUFRLEVBQ2IsUUFBUSxFQUFFLENBQUMsQ0FBZ0MsRUFBRSxFQUFFLENBQUMsY0FBYyxDQUFDLFFBQVEsQ0FBQyxDQUFDLEVBQUUsTUFBTSxFQUFFLEtBQUssQ0FBQyxPQUFPLENBQUMsVUFBVSxFQUFFLEVBQUUsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQ3RILEtBQUssRUFBRSxHQUFHLFdBQVcsRUFBRSxFQUN2QixXQUFXLEVBQUMsR0FBRyxFQUNmLEtBQUssRUFBRSxFQUFDLEdBQUcsQ0FBQyxNQUFNLEVBQUUsVUFBVSxDQUFDLEVBQUMsR0FDaEMsR0FFQSxFQUNOLHVCQUFDLGFBQUcsSUFBRSxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsR0FBRyxFQUFFLE1BQU0sRUFBRSxHQUFHLEVBQUUsRUFBRSxjQUFjLEVBQUMsUUFBUSxFQUFDLFVBQVUsRUFBQyxRQUFRLEVBQUMsS0FBSyxFQUFFLEVBQUUsS0FBSyxFQUFFLE1BQU0sRUFBRSxZQUN6Ryx1QkFBQyxtQkFBUyxJQUNSLEtBQUssRUFBQyxpQkFBaUIsRUFDdkIsSUFBSSxFQUFDLFFBQVEsRUFDYixRQUFRLEVBQUUsQ0FBQyxDQUFnQyxFQUFFLEVBQUUsQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDLEVBQUUsTUFBTSxFQUFFLEtBQUssQ0FBQyxFQUNsRixLQUFLLEVBQUUsR0FBRyxXQUFXLEVBQUUsRUFDdkIsV0FBVyxFQUFDLEdBQUcsRUFDZixLQUFLLEVBQUUsRUFBRSxHQUFHLENBQUMsTUFBTSxFQUFFLFVBQVUsQ0FBQyxFQUFDLEdBQ2pDLEdBRUUsSUFDRixFQUNOLHdCQUFDLGFBQUcsSUFBQyxhQUFhLEVBQUMsS0FBSyxFQUFDLGNBQWMsRUFBQyxlQUFlLEVBQUMsS0FBSyxFQUFFLEVBQUUsS0FBSyxFQUFFLE1BQU0sRUFBRSxhQUM5RSx1QkFBQyxhQUFHLEtBQUcsRUFDTixnQkFBZ0IsRUFBRSxJQUNmLElBQ0YsQ0FDUCxDQUFBO1lBQ0gsS0FBSyxDQUFDO2dCQUNKLE9BQU8sQ0FDTCx3QkFBQyxhQUFHLElBQUUsY0FBYyxFQUFDLFFBQVEsRUFBQyxVQUFVLEVBQUMsUUFBUSxhQUUvQyx3QkFBQyxhQUFHLElBQUMsY0FBYyxFQUFDLFFBQVEsRUFBQyxVQUFVLEVBQUMsUUFBUSxFQUFDLFNBQVMsRUFBQyxNQUFNLGFBQy9ELHVCQUFDLGNBQUksSUFBQyxPQUFPLEVBQUMsV0FBVyxFQUFDLEVBQUUsRUFBRSxFQUFFLEtBQUssRUFBRSxHQUFHLEVBQUUsTUFBTSxFQUFFLEdBQUcsRUFBRSxZQUNwRCxRQUFRLENBQUMsQ0FBQyxDQUFDLHNCQUFzQixDQUFDLENBQUMsQ0FBQyx1QkFBdUIsR0FDekQsRUFDUCx1QkFBQyxhQUFHLElBQUMsRUFBRSxFQUFFLEVBQUUsS0FBSyxFQUFFLEdBQUcsRUFBRSxNQUFNLEVBQUUsR0FBRyxFQUFFLFlBQ2xDLHVCQUFDLGdCQUFNLElBQUMsT0FBTyxFQUFFLGFBQWEsWUFDM0IsUUFBUSxDQUFDLENBQUMsQ0FBQyxRQUFRLENBQUMsQ0FBQyxDQUFDLFFBQVEsR0FDeEIsR0FDTCxJQUNGLEVBQ04sdUJBQUMsYUFBRyxJQUFDLGFBQWEsRUFBQyxLQUFLLEVBQUMsY0FBYyxFQUFDLFlBQVksRUFBQyxLQUFLLEVBQUMsTUFBTSxZQUM1RCxnQkFBZ0IsRUFBRSxHQUNqQixJQUNGLENBQ1AsQ0FBQTtRQUNMLENBQUM7SUFDSCxDQUFDLENBQUE7SUFFRCxPQUFPLENBQ0wsd0JBQUMsYUFBRyxJQUFDLElBQUksRUFBRSxDQUFDLGFBQ1YsdUJBQUMsZ0JBQU0sSUFDTCxLQUFLLEVBQUU7b0JBQ0g7d0JBQ0ksS0FBSyxFQUFFLENBQUM7d0JBQ1IsS0FBSyxFQUFFLGNBQWM7cUJBQ3hCO29CQUNEO3dCQUNJLEtBQUssRUFBRSxDQUFDO3dCQUNSLEtBQUssRUFBRSxpQkFBaUI7cUJBQzNCO2lCQUNKLEVBRUQsU0FBUyxFQUFFLGFBQWEsRUFDeEIsV0FBVyxFQUFFLFdBQVcsR0FDeEIsRUFDRCxpQkFBaUIsRUFBRSxJQUNoQixDQUNQLENBQUE7QUFDSCxDQUFDO0FBRUQsa0JBQWUsZ0JBQWdCLENBQUEiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgUmVhY3QsIHsgdXNlU3RhdGUsIHVzZUVmZmVjdCB9IGZyb20gJ3JlYWN0J1xuaW1wb3J0IHsgSW5wdXQgfSBmcm9tICdAY2hha3JhLXVpL3JlYWN0J1xuaW1wb3J0IFdpemFyZCBmcm9tICdAY29tcG9uZW50cy9XaXphcmQnXG5pbXBvcnQgVGV4dEZpZWxkIGZyb20gJ0Bjb21wb25lbnRzL1RleHRGaWVsZCdcbmltcG9ydCB7IHY0IGFzIHV1aWQgfSBmcm9tICd1dWlkJ1xuaW1wb3J0IHsgZGF5anMgfSBmcm9tICdAbGliL2RhdGUtdXRpbHMnXG5pbXBvcnQgeyB1c2VUb2FzdCB9IGZyb20gJ0BjaGFrcmEtdWkvcmVhY3QnXG5pbXBvcnQgQm94IGZyb20gJ0Bjb21wb25lbnRzL2NvbW1vbi9Cb3gnXG5pbXBvcnQgVGV4dCBmcm9tICdAY29tcG9uZW50cy9jb21tb24vVGV4dCdcbmltcG9ydCBCdXR0b24gZnJvbSAnQGNvbXBvbmVudHMvQnV0dG9uJ1xuaW1wb3J0IHsgRGVhZGxpbmVUeXBlIH0gZnJvbSAnQHBhZ2VzL1Byb2dyZXNzL1RvZG8vVXNlclRhc2snXG5pbXBvcnQgeyBjcmVhdGVEZWFkbGluZUZvclRhc2ssIGVkaXRFdmVudEZvclRhc2ssIHN1Ym1pdENhbGVuZGFyRm9yUXVldWUgfSBmcm9tICdAbGliL1Byb2dyZXNzL1RvZG8vVXNlclRhc2tIZWxwZXIyJ1xuaW1wb3J0IHsgQ2FsZW5kYXJUeXBlIH0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvQ2FsZW5kYXJUeXBlJ1xuaW1wb3J0IF8gZnJvbSAnbG9kYXNoJ1xuaW1wb3J0IHsgZ2V0R2xvYmFsUHJpbWFyeUNhbGVuZGFyRnVuY3Rpb24gfSBmcm9tICdAbGliL1NjaGVkdWxlL1NjaGVkdWxlSGVscGVyJ1xuaW1wb3J0IHsgZ2V0RXZlbnRXaXRoSWQgfSBmcm9tICdAbGliL2NhbGVuZGFyTGliL2NhbGVuZGFyRGJIZWxwZXInXG5pbXBvcnQgeyBFdmVudFR5cGUgfSBmcm9tICdAbGliL2RhdGFUeXBlcy9FdmVudFR5cGUnO1xuaW1wb3J0IHsgdXNlQXBwQ29udGV4dCB9IGZyb20gJ0BsaWIvdXNlci1jb250ZXh0J1xuaW1wb3J0IHsgdXNlUm91dGVyIH0gZnJvbSAnbmV4dC9yb3V0ZXInXG5pbXBvcnQgeyBnZXRUYXNrR2l2ZW5JZCwgdXBkYXRlVGFza0J5SWRJbkRiIH0gZnJvbSAnQGxpYi9Qcm9ncmVzcy9Ub2RvL1VzZXJUYXNrSGVscGVyMydcbmltcG9ydCB7IFRhc2tUeXBlIH0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvVGFza1R5cGUnXG5pbXBvcnQgeyBXZWVrbHlUYXNrLCBEYWlseVRhc2sgfSBmcm9tICdAbGliL1Byb2dyZXNzL1RvZG8vY29uc3RhbnRzJ1xuXG5jb25zdCBzdHlsZXMgPSB7XG4gIGlucHV0RmllbGQ6IHtcbiAgICBmb250U2l6ZTogJzIxcHgnLFxuICAgIGxpbmVIZWlnaHQ6ICcyOHB4JyxcbiAgICBjb2xvcjogJyMyMjFEMjMnLFxuICAgIC8vIGJvcmRlckNvbG9yOiBwYWxldHRlLnRleHRCbGFjayxcbiAgICAvLyBib3JkZXJXaWR0aDogMSxcbiAgICB3aWR0aDogJzEwMCUnLFxuICAgIC8vIGhlaWdodDogNDAsXG4gIH0gYXMgUmVhY3QuQ1NTUHJvcGVydGllcyxcbiAgY29udGFpbmVyOiB7XG4gICAgZmxleDogMSxcbiAgfSBhcyBSZWFjdC5DU1NQcm9wZXJ0aWVzLFxufVxuXG5leHBvcnQgdHlwZSB0YXNrVHlwZSA9ICdEYWlseSd8J1dlZWtseSdcblxuaW1wb3J0IHsgTmV4dEFwaVJlcXVlc3QsIE5leHRBcGlSZXNwb25zZSB9IGZyb20gJ25leHQnO1xuaW1wb3J0IHN1cGVydG9rZW5zTm9kZSBmcm9tICdzdXBlcnRva2Vucy1ub2RlJ1xuaW1wb3J0IHsgYmFja2VuZENvbmZpZyB9IGZyb20gJ0Bjb25maWcvYmFja2VuZENvbmZpZydcbmltcG9ydCBTZXNzaW9uIGZyb20gJ3N1cGVydG9rZW5zLW5vZGUvcmVjaXBlL3Nlc3Npb24nXG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRTZXJ2ZXJTaWRlUHJvcHMoeyByZXEsIHJlcyB9OiB7IHJlcTogTmV4dEFwaVJlcXVlc3QsIHJlczogTmV4dEFwaVJlc3BvbnNlIH0pIHtcbiAgICAvLyBOb3RpY2UgaG93IHRoZSBzZXJ2ZXIgdXNlcyBgQVBJYCBmcm9tIGB3aXRoU1NSQ29udGV4dGAsIGluc3RlYWQgb2YgdGhlIHRvcC1sZXZlbCBgQVBJYC5cbiAgICAvLyBjb25zdCBTU1IgPSB3aXRoU1NSQ29udGV4dCh7IHJlcSB9KVxuICAgIC8vIHRoaXMgcnVucyBvbiB0aGUgYmFja2VuZCwgc28gd2UgbXVzdCBjYWxsIGluaXQgb24gc3VwZXJ0b2tlbnMtbm9kZSBTREtcbiAgICBzdXBlcnRva2Vuc05vZGUuaW5pdChiYWNrZW5kQ29uZmlnKCkpXG4gICAgbGV0IHNlc3Npb25cbiAgICB0cnkge1xuICAgICAgICBzZXNzaW9uID0gYXdhaXQgU2Vzc2lvbi5nZXRTZXNzaW9uKHJlcSwgcmVzLCB7XG4gICAgICAgICAgICBvdmVycmlkZUdsb2JhbENsYWltVmFsaWRhdG9yczogYXN5bmMgZnVuY3Rpb24gKCkge1xuICAgICAgICAgICAgICAgIHJldHVybiBbXVxuICAgICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICB9IGNhdGNoIChlcnI6IGFueSkge1xuICAgICAgICBpZiAoZXJyLnR5cGUgPT09IFNlc3Npb24uRXJyb3IuVFJZX1JFRlJFU0hfVE9LRU4pIHtcbiAgICAgICAgICAgIHJldHVybiB7IHByb3BzOiB7IGZyb21TdXBlcnRva2VuczogJ25lZWRzLXJlZnJlc2gnIH0gfVxuICAgICAgICB9IGVsc2UgaWYgKGVyci50eXBlID09PSBTZXNzaW9uLkVycm9yLlVOQVVUSE9SSVNFRCkge1xuICAgICAgICAgICAgLy8gdGhpcyB3aWxsIGZvcmNlIHRoZSBmcm9udGVuZCB0byB0cnkgYW5kIHJlZnJlc2ggd2hpY2ggd2lsbCBmYWlsXG4gICAgICAgICAgICAvLyBjbGVhcmluZyBhbGwgY29va2llcyBhbmQgcmVkaXJlY3RpbmcgdGhlIHVzZXIgdG8gdGhlIGxvZ2luIHNjcmVlbi5cbiAgICAgICAgICAgIHJldHVybiB7IHByb3BzOiB7IGZyb21TdXBlcnRva2VuczogJ25lZWRzLXJlZnJlc2gnIH0gfVxuICAgICAgICB9XG4gICAgICAgIHRocm93IGVyclxuICAgIH1cblxuICAgIGlmICghc2Vzc2lvbj8uZ2V0VXNlcklkKCkpIHtcbiAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICAgIHJlZGlyZWN0OiB7XG4gICAgICAgICAgICAgICAgZGVzdGluYXRpb246ICcvVXNlci9Mb2dpbi9Vc2VyTG9naW4nLFxuICAgICAgICAgICAgICAgIHBlcm1hbmVudDogZmFsc2UsXG4gICAgICAgICAgICB9LFxuICAgICAgICB9XG4gICAgfVxuXG4gICAgcmV0dXJuIHtcbiAgICAgICAgcHJvcHM6IHtcbiAgICAgICAgc3ViOiBzZXNzaW9uLmdldFVzZXJJZCgpLFxuICAgICAgICB9XG4gICAgfVxufVxuXG5jb25zdCBkZWFkbGluZU9wdGlvbnMgPSBbXG4gIHtcbiAgICBsYWJlbDogJ1NvZnQgRGVhZGxpbmUnLFxuICAgIHZhbHVlOiAnc29mdCcsXG4gIH0sXG4gIHtcbiAgICBsYWJlbDogJ0hhcmQgRGVhZGxpbmUnLFxuICAgIHZhbHVlOiAnaGFyZCcsXG4gIH1cbl1cblxuZnVuY3Rpb24gVXNlclRhc2tEZWFkbGluZSgpIHtcbiAgY29uc3Qgcm91dGVyID0gdXNlUm91dGVyKClcbiAgY29uc3QgeyBzdWIsIGNsaWVudCB9ID0gdXNlQXBwQ29udGV4dCgpXG5cbiAgY29uc3QgdGFza1R5cGUgPSByb3V0ZXIucXVlcnk/LnRhc2tUeXBlIGFzIHRhc2tUeXBlXG4gIGNvbnN0IHRhc2tJZCA9IHJvdXRlci5xdWVyeT8udGFza0lkIGFzIHN0cmluZ1xuICBjb25zdCBpc1VwZGF0ZSA9IHJvdXRlci5xdWVyeT8uaXNVcGRhdGUgYXMgc3RyaW5nXG4gIGNvbnN0IGRlYWRsaW5lVHlwZSA9IHJvdXRlci5xdWVyeT8uZGVhZGxpbmVUeXBlIGFzIERlYWRsaW5lVHlwZVxuIFxuICBjb25zdCBbYWN0aXZlSW5kZXgsIHNldEFjdGl2ZUluZGV4XSA9IHVzZVN0YXRlPG51bWJlcj4oMClcbiAgY29uc3QgW2NvbXBsZXRlZFN0ZXAsIHNldENvbXBsZXRlZFN0ZXBdID0gdXNlU3RhdGU8bnVtYmVyIHwgdW5kZWZpbmVkPigpXG5cbiAgY29uc3QgW25ld1ByaW9yaXR5LCBzZXROZXdQcmlvcml0eV0gPSB1c2VTdGF0ZTxudW1iZXI+KDEpXG4gIGNvbnN0IFtuZXdEZWFkbGluZSwgc2V0TmV3RGVhZGxpbmVdID0gdXNlU3RhdGU8RGF0ZT4obmV3IERhdGUoKSlcbiAgY29uc3QgW25ld0RlYWRsaW5lVHlwZSwgc2V0TmV3RGVhZGxpbmVUeXBlXSA9IHVzZVN0YXRlPERlYWRsaW5lVHlwZT4oZGVhZGxpbmVUeXBlIHx8ICdzb2Z0JylcbiAgY29uc3QgW25ld0R1cmF0aW9uLCBzZXROZXdEdXJhdGlvbl0gPSB1c2VTdGF0ZTxudW1iZXI+KDMwKVxuICBjb25zdCBbY2FsZW5kYXIsIHNldENhbGVuZGFyXSA9IHVzZVN0YXRlPENhbGVuZGFyVHlwZT4oKVxuXG4gIGNvbnN0IFtldmVudCwgc2V0RXZlbnRdID0gdXNlU3RhdGU8RXZlbnRUeXBlPigpXG4gIGNvbnN0IFt0YXNrLCBzZXRUYXNrXSA9IHVzZVN0YXRlPFRhc2tUeXBlPigpXG4gIFxuICAvLyBjb25zdCBkYXJrID0gdXNlQ29sb3JTY2hlbWUoKSA9PT0gJ2RhcmsnXG4gIGNvbnN0IHVzZXJJZCA9IHN1YlxuICBjb25zdCB0b2FzdCA9IHVzZVRvYXN0KClcblxuXG4gIFxuICAvLyBnZXQgdGFza1xuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIChhc3luYyAoKSA9PiB7XG4gICAgICB0cnkge1xuICAgICAgICBpZiAoIXRhc2tJZCB8fCAhY2xpZW50KSB7XG4gICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCBvbGRUYXNrID0gYXdhaXQgZ2V0VGFza0dpdmVuSWQoY2xpZW50LCB0YXNrSWQpXG4gICAgICAgIHNldFRhc2sob2xkVGFzaylcbiAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IHRhc2sgYnkgaWQnKVxuICAgICAgfVxuICAgIH0pKClcbiAgfSwgW2NsaWVudCwgdGFza0lkXSlcbiAgXG5cbiAgXG4gIC8vIGdldCBnbG9iYWwgcHJpbWFyeSBjYWxlbmRhclxuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIChhc3luYyAoKSA9PiB7ICBcbiAgICAgIGlmICghdXNlcklkIHx8ICFjbGllbnQpIHtcbiAgICAgICAgcmV0dXJuXG4gICAgICB9XG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBnZXRHbG9iYWxQcmltYXJ5Q2FsZW5kYXJGdW5jdGlvbihjbGllbnQsIHVzZXJJZClcbiAgICAgIGlmICghcmVzdWx0Py5pZCkge1xuICAgICAgICBjb25zb2xlLmxvZygnIG5vIHByaW1hcnkgY2FsZW5kYXIgYXZhaWxhYmxlJylcbiAgICAgICAgcmV0dXJuXG4gICAgICB9XG4gICAgICBzZXRDYWxlbmRhcihyZXN1bHQpXG4gICAgfSkoKVxuICB9LCBbY2xpZW50LCB1c2VySWRdKVxuXG4gIC8vIGdldCBFdmVudFxuICB1c2VFZmZlY3QoKCkgPT4ge1xuICAgIChhc3luYyAoKSA9PiB7XG4gICAgICBpZiAoIXRhc2tJZCB8fCAhY2xpZW50KSB7XG4gICAgICAgIHJldHVyblxuICAgICAgfVxuICAgICAgaWYgKHRhc2s/LmlkKSB7XG4gICAgICAgIGNvbnN0IG9sZEV2ZW50ID0gYXdhaXQgZ2V0RXZlbnRXaXRoSWQoY2xpZW50LCB0YXNrPy5ldmVudElkKVxuICAgICAgICBpZiAoIW9sZEV2ZW50Py5pZCkge1xuICAgICAgICAgIGNvbnNvbGUubG9nKCcgbm8gZXZlbnQgYXZhaWxhYmxlJylcbiAgICAgICAgICByZXR1cm5cbiAgICAgICAgfVxuICAgICAgICBjb25zb2xlLmxvZyhvbGRFdmVudD8uaWQsICcgb2xkRXZlbnQ/LmlkIGluc2lkZSBVc2VyVGFza0RlYWRsaW5lJylcbiAgICAgICAgY29uc29sZS5sb2cob2xkRXZlbnQ/LnNvZnREZWFkbGluZSwgJyBvbGRFdmVudD8uc29mdERlYWRsaW5lIGluc2lkZSBVc2VyVGFza0RlYWRsaW5lJylcbiAgICAgICAgY29uc29sZS5sb2cob2xkRXZlbnQ/LmhhcmREZWFkbGluZSwgJyBvbGRFdmVudD8uaGFyZERlYWRsaW5lIGluc2lkZSBVc2VyVGFza0RlYWRsaW5lJylcbiAgICAgICAgc2V0RXZlbnQob2xkRXZlbnQpXG4gICAgICAgIHNldE5ld1ByaW9yaXR5KG9sZEV2ZW50LnByaW9yaXR5KVxuICAgICAgICBzZXROZXdEZWFkbGluZSgob2xkRXZlbnQ/LnNvZnREZWFkbGluZSAmJiBkYXlqcyhvbGRFdmVudD8uc29mdERlYWRsaW5lKS50eihvbGRFdmVudD8udGltZXpvbmUgfHwgZGF5anMudHouZ3Vlc3MoKSwgdHJ1ZSkudG9EYXRlKCkpIHx8IChvbGRFdmVudD8uaGFyZERlYWRsaW5lICYmIGRheWpzKG9sZEV2ZW50Py5oYXJkRGVhZGxpbmUpLnR6KG9sZEV2ZW50Py50aW1lem9uZSB8fCBkYXlqcy50ei5ndWVzcygpKS50b0RhdGUoKSkgfHwgbmV3IERhdGUoKSlcbiAgICAgICAgc2V0TmV3RGVhZGxpbmVUeXBlKG9sZEV2ZW50Py5zb2Z0RGVhZGxpbmUgPyAnc29mdCcgOiAnaGFyZCcpXG4gICAgICAgIHNldE5ld0R1cmF0aW9uKG9sZEV2ZW50Py5kdXJhdGlvbiB8fCAwKVxuICAgICAgICAvLyBnZXQgdGFncyBmb3IgZXZlbnRcbiAgICAgICAgXG4gICAgICAgIFxuICAgICAgfVxuICAgIH0pKClcbiAgfSwgW2NsaWVudCwgdGFzaz8uZXZlbnRJZCwgdGFzaz8uaWQsIHRhc2tJZCwgdGFza1R5cGVdKVxuXG4gIGNvbnN0IG9uQ2hhbmdlUHJpb3JpdHkgPSAodmFsdWU6IHN0cmluZyA9ICcxJykgPT4ge1xuICAgICAgICBjb25zdCBpbnRWYWx1ZSA9IHBhcnNlSW50KHZhbHVlLnJlcGxhY2UoL1teMC05Ll0vZywgJycpLCAxMClcbiAgICAgICAgLy8gdmFsaWRhdGVcbiAgICAgICAgaWYgKGludFZhbHVlIDwgMSkge1xuICAgICAgICBzZXROZXdQcmlvcml0eSgxKVxuICAgICAgICByZXR1cm5cbiAgICAgICAgfVxuXG4gICAgICAgIGlmIChpc05hTihpbnRWYWx1ZSkpIHtcbiAgICAgICAgc2V0TmV3UHJpb3JpdHkoMSlcbiAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cblxuICAgICAgICBzZXROZXdQcmlvcml0eShwYXJzZUludCh2YWx1ZS5yZXBsYWNlKC9bXjAtOS5dL2csICcnKSwgMTApIHx8IDEpXG4gICAgfVxuXG4gIC8vIHVwZGF0ZSB0byBEYXRhc29yZVxuICBjb25zdCB1cGRhdGVUYXNrSW5EYiA9IGFzeW5jIChcbiAgICBkdXJhdGlvbj86IG51bWJlcixcbiAgICBzb2Z0RGVhZGxpbmU/OiBzdHJpbmcsXG4gICAgaGFyZERlYWRsaW5lPzogc3RyaW5nLFxuICAgIGV2ZW50SWQ/OiBzdHJpbmcsXG4gICkgPT4ge1xuICAgIHRyeSB7XG4gICAgICBpZiAoIXRhc2tJZCkge1xuICAgICAgICByZXR1cm4gLy8gY29uc29sZS5sb2coJyBub3QgYXZhaWxhYmxlIGluIHRoZSBpZCBhcnJheScpXG4gICAgICB9XG5cbiAgICAgIGNvbnN0IHRvVXBkYXRlVGFzayA9IF8uY2xvbmVEZWVwKHRhc2spXG5cbiAgICAgIC8vIHZhbGlkYXRlXG4gICAgICBpZiAoIXRvVXBkYXRlVGFzaykge1xuICAgICAgICBjb25zb2xlLmxvZygnbm8gdG9VcGRhdGVUYXNrIHByb3ZpZGVkIGluc2lkZSB1cGRhdGVUYXNraW5EYicpXG4gICAgICAgIHJldHVyblxuICAgICAgfVxuXG4gICAgICBpZiAoZHVyYXRpb24gIT09IHVuZGVmaW5lZCkge1xuICAgICAgICB0b1VwZGF0ZVRhc2suZHVyYXRpb24gPSBkdXJhdGlvblxuICAgICAgfVxuXG4gICAgICBpZiAoc29mdERlYWRsaW5lICE9PSB1bmRlZmluZWQpIHtcbiAgICAgICAgdG9VcGRhdGVUYXNrLnNvZnREZWFkbGluZSA9IHNvZnREZWFkbGluZVxuICAgICAgfVxuXG4gICAgICBpZiAoaGFyZERlYWRsaW5lICE9PSB1bmRlZmluZWQpIHtcbiAgICAgICAgdG9VcGRhdGVUYXNrLmhhcmREZWFkbGluZSA9IGhhcmREZWFkbGluZVxuICAgICAgfVxuXG4gICAgICBpZiAoZXZlbnRJZCAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICAgICAgdG9VcGRhdGVUYXNrLmV2ZW50SWQgPSBgJHtldmVudElkfSMke2NhbGVuZGFyPy5pZH1gXG4gICAgICB9XG5cbiAgICAgIGF3YWl0IHVwZGF0ZVRhc2tCeUlkSW5EYihjbGllbnQsIHRvVXBkYXRlVGFzaylcblxuICAgICAgc2V0VGFzayh0b1VwZGF0ZVRhc2spXG5cbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cGRhdGUgdGFzayBpbiBkYicpXG4gICAgfVxuICB9XG5cblxuICAvLyBjcmVhdGUgdGFza0RlYWRsaW5lXG4gIGNvbnN0IG9uUmVjZWl2ZUNyZWF0ZURlYWRsaW5lID0gYXN5bmMgKCkgPT4ge1xuICAgIC8qKlxuICAgIG92ZXJyaWRlcyBhdXRvIGdlbmVyYXRlZCBzdGFydCBhbmQgZW5kIGRhdGVzXG4gICAgICovXG4gICAgdHJ5IHtcblxuICAgICAgaWYgKCF0YXNrSWQgfHwgIXRhc2spIHtcbiAgICAgICAgLy8gY29uc29sZS5sb2coJ25vIHRhc2tJZCBwcmVzZW50IGluc2lkZSBvblJlY2VpdmVDcmVhdGVUYXNrU2NoZWR1bGVJbmZvJylcbiAgICAgICAgcmV0dXJuXG4gICAgICB9XG5cbiAgICAgIGNvbnN0IGV2ZW50SWQgPSBhd2FpdCBjcmVhdGVEZWFkbGluZUZvclRhc2soXG4gICAgICAgIGNsaWVudCxcbiAgICAgICAgdXNlcklkLFxuICAgICAgICB0YXNrPy5ub3RlcyxcbiAgICAgICAgbmV3RHVyYXRpb24sXG4gICAgICAgIHRhc2tJZCxcbiAgICAgICAgdGFza1R5cGUsXG4gICAgICAgIG5ld1ByaW9yaXR5LFxuICAgICAgICBuZXdEZWFkbGluZVR5cGUgPT09ICdzb2Z0JyA/IGRheWpzKG5ld0RlYWRsaW5lKS5mb3JtYXQoKSA6IHVuZGVmaW5lZCxcbiAgICAgICAgbmV3RGVhZGxpbmVUeXBlID09PSAnaGFyZCcgPyBkYXlqcyhuZXdEZWFkbGluZSkuZm9ybWF0KCkgOiB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICBjYWxlbmRhci5jb2xvcklkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHRhc2s/Lm5vdGVzLFxuICAgICAgKVxuXG4gICAgICBhd2FpdCB1cGRhdGVUYXNrSW5EYihcbiAgICAgICAgbmV3RHVyYXRpb24sXG4gICAgICAgIG5ld0RlYWRsaW5lVHlwZSA9PT0gJ3NvZnQnID8gZGF5anMobmV3RGVhZGxpbmUpLmZvcm1hdCgpIDogdW5kZWZpbmVkLFxuICAgICAgICBuZXdEZWFkbGluZVR5cGUgPT09ICdoYXJkJyA/IGRheWpzKG5ld0RlYWRsaW5lKS5mb3JtYXQoKSA6IHVuZGVmaW5lZCxcbiAgICAgICAgZXZlbnRJZCA/IGAke2V2ZW50SWR9IyR7Y2FsZW5kYXI/LmlkfWAgOiB1bmRlZmluZWQsXG4gICAgICApXG5cbiAgICAgIGlmICh0YXNrVHlwZSA9PT0gV2Vla2x5VGFzaykge1xuXG4gICAgICAgICAgYXdhaXQgc3VibWl0Q2FsZW5kYXJGb3JRdWV1ZShjbGllbnQsIHVzZXJJZCwgZGF5anMoKS5ob3VyKDcpLmZvcm1hdCgpLCBkYXlqcygpLmFkZCg2LCAnZGF5JykuaG91cigyMykubWludXRlKDU5KS5mb3JtYXQoKSwgdG9hc3QpXG4gICAgICAgIFxuICAgICAgICBcbiAgICAgIH0gZWxzZSBpZiAodGFza1R5cGUgPT09IERhaWx5VGFzaykge1xuXG4gICAgICAgIGF3YWl0IHN1Ym1pdENhbGVuZGFyRm9yUXVldWUoY2xpZW50LCB1c2VySWQsIGRheWpzKCkuaG91cig3KS5mb3JtYXQoKSwgZGF5anMoKS5ob3VyKDIzKS5taW51dGUoNTkpLmZvcm1hdCgpLCB0b2FzdClcblxuICAgICAgfVxuXG4gICAgICB0b2FzdCh7XG4gICAgICAgIHN0YXR1czogJ3N1Y2Nlc3MnLFxuICAgICAgICB0aXRsZTogJ1Rhc2sgZGVhZGxpbmUgY3JlYXRlZCcsXG4gICAgICAgIGRlc2NyaXB0aW9uOiAnVGFzayBkZWFkbGluZSBpcyBzdWNjZXNmdWxseSBjcmVhdGVkJyxcbiAgICAgICAgZHVyYXRpb246IDkwMDAsXG4gICAgICAgIGlzQ2xvc2FibGU6IHRydWUsXG4gICAgICB9KVxuXG4gICAgICByb3V0ZXIucHVzaCh7IHBhdGhuYW1lOiAnL1Byb2dyZXNzL1RvZG8vVXNlclRhc2snLCBxdWVyeToge1xuICAgICAgICB0YXNrVHlwZSxcbiAgICAgICAgaXNVcGRhdGU6IHV1aWQoKSxcbiAgICAgIH19KVxuICAgIH0gY2F0Y2goZSkge1xuICAgICAgLy8gY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gY3JlYXRlIHRhc2sgZGVhZGxpbmUnKVxuICAgICAgdG9hc3Qoe1xuICAgICAgICBzdGF0dXM6ICdlcnJvcicsXG4gICAgICAgIHRpdGxlOiAnTm8gZGVhZGxpbmUgY3JlYXRlZCcsXG4gICAgICAgIGRlc2NyaXB0aW9uOiAnV2UgYXJlIG5vdCBhYmxlIHRvIGNyZWF0ZSB0aGUgZGVhZGxpbmUgZHVlIHRvIGFuIGludGVybmFsIGVycm9yLicsXG4gICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgfSlcbiAgICAgIHJvdXRlci5wdXNoKHsgcGF0aG5hbWU6ICcvUHJvZ3Jlc3MvVG9kby9Vc2VyVGFzaycsIHF1ZXJ5OiB7XG4gICAgICAgIHRhc2tUeXBlLFxuICAgICAgICBpc1VwZGF0ZTogdW5kZWZpbmVkLFxuICAgICAgfX0pXG4gICAgICAvLyBzZXRJc0RlYWRsaW5lT3ZlcmxheShmYWxzZSlcbiAgICAgIC8vIHNldEFjdGl2ZURlYWRsaW5lSW5kZXgoLTEpXG4gICAgfVxuICB9XG5cbiAgY29uc3Qgb25SZWNlaXZlVXBkYXRlRGVhZGxpbmUgPSBhc3luYyAoKSA9PiB7XG4gICB0cnkge1xuXG4gICAgIGlmICh0YXNrKSB7XG4gICAgICBcbiAgICAgICAgY29uc29sZS5sb2cobmV3RGVhZGxpbmVUeXBlLCAnIG5ld0RlYWRsaW5lVHlwZSBiZWZvcmUgZWRpdEV2ZW50Rm9yVGFzaycpXG4gICAgICBcbiAgICAgICAgY29uc3QgZXZlbnREb2MgPSBhd2FpdCBnZXRFdmVudFdpdGhJZChjbGllbnQsIHRhc2suZXZlbnRJZClcbiAgICAgICAgICBcbiAgICAgICAgYXdhaXQgZWRpdEV2ZW50Rm9yVGFzayhcbiAgICAgICAgICB0YXNrPy5ldmVudElkLFxuICAgICAgICAgIGV2ZW50RG9jPy5zdGFydERhdGUsXG4gICAgICAgICAgZXZlbnREb2M/LmVuZERhdGUsXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIGNsaWVudCxcbiAgICAgICAgICBldmVudERvYz8uY2FsZW5kYXJJZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdGFzay5ub3RlcyxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHRhc2subm90ZXMsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHRydWUsXG4gICAgICAgICAgZmFsc2UsXG4gICAgICAgICAgZmFsc2UsXG4gICAgICAgICAgZmFsc2UsXG4gICAgICAgICAgZmFsc2UsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHRhc2tJZCxcbiAgICAgICAgICB0YXNrVHlwZSxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHRhc2subm90ZXMsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHRhc2tUeXBlID09PSAnRGFpbHknLFxuICAgICAgICAgIHRhc2tUeXBlID09PSAnV2Vla2x5JyxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB0cnVlLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB0cnVlLFxuICAgICAgICAgIHRydWUsXG4gICAgICAgICAgdHJ1ZSxcbiAgICAgICAgICBuZXdEZWFkbGluZVR5cGUgPT09ICdoYXJkJyA/IGRheWpzKG5ld0RlYWRsaW5lKS5mb3JtYXQoKSA6IG51bGwsXG4gICAgICAgICAgbmV3RGVhZGxpbmVUeXBlID09PSAnc29mdCcgPyBkYXlqcyhuZXdEZWFkbGluZSkuZm9ybWF0KCkgOiBudWxsLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICBuZXdEdXJhdGlvbixcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdHJ1ZSxcbiAgICAgICAgICAndXBkYXRlJyxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgKVxuXG4gICAgICAgIGF3YWl0IHVwZGF0ZVRhc2tJbkRiKFxuICAgICAgICAgIG5ld0R1cmF0aW9uLFxuICAgICAgICAgIG5ld0RlYWRsaW5lVHlwZSA9PT0gJ3NvZnQnID8gZGF5anMobmV3RGVhZGxpbmUpLmZvcm1hdCgpIDogbnVsbCxcbiAgICAgICAgICBuZXdEZWFkbGluZVR5cGUgPT09ICdoYXJkJyA/IGRheWpzKG5ld0RlYWRsaW5lKS5mb3JtYXQoKSA6IG51bGwsXG4gICAgICAgIClcblxuICAgICAgfVxuXG4gICAgIGlmIChldmVudC5zb2Z0RGVhZGxpbmUgJiYgKG5ld0RlYWRsaW5lVHlwZSA9PT0gJ2hhcmQnKSkge1xuICAgICAgY29uc29sZS5sb2coYGV2ZW50LnNvZnREZWFkbGluZSAmJiAobmV3RGVhZGxpbmVUeXBlID09PSAnaGFyZCcpYClcbiAgICAgICBpZiAodGFza1R5cGUgPT09IFdlZWtseVRhc2spIHtcblxuICAgICAgICAgICAgYXdhaXQgc3VibWl0Q2FsZW5kYXJGb3JRdWV1ZShjbGllbnQsIHVzZXJJZCwgZGF5anMoKS5ob3VyKDcpLmZvcm1hdCgpLCBkYXlqcygpLmFkZCg2LCAnZGF5JykuaG91cigyMykubWludXRlKDU5KS5mb3JtYXQoKSwgdG9hc3QpXG4gICAgICAgICBcbiAgICAgICB9IGVsc2UgaWYgKHRhc2tUeXBlID09PSBEYWlseVRhc2spIHtcblxuICAgICAgICAgIGF3YWl0IHN1Ym1pdENhbGVuZGFyRm9yUXVldWUoY2xpZW50LCB1c2VySWQsIGRheWpzKCkuaG91cig3KS5mb3JtYXQoKSwgZGF5anMoKS5ob3VyKDIzKS5taW51dGUoNTkpLmZvcm1hdCgpLCB0b2FzdClcbiAgICAgICAgXG4gICAgICB9XG4gICAgIH0gZWxzZSBpZiAoZXZlbnQuaGFyZERlYWRsaW5lICYmIChuZXdEZWFkbGluZVR5cGUgPT09ICdzb2Z0JykpIHtcbiAgICAgICBjb25zb2xlLmxvZyhgZXZlbnQuaGFyZERlYWRsaW5lICYmIChuZXdEZWFkbGluZVR5cGUgPT09ICdzb2Z0JylgKVxuICAgICAgaWYgKHRhc2tUeXBlID09PSBXZWVrbHlUYXNrKSB7XG5cbiAgICAgICAgICBhd2FpdCBzdWJtaXRDYWxlbmRhckZvclF1ZXVlKGNsaWVudCwgdXNlcklkLCBkYXlqcygpLmhvdXIoNykuZm9ybWF0KCksIGRheWpzKCkuYWRkKDYsICdkYXknKS5ob3VyKDIzKS5taW51dGUoNTkpLmZvcm1hdCgpLCB0b2FzdClcbiAgICAgICAgXG4gICAgICB9IGVsc2UgaWYgKHRhc2tUeXBlID09PSBEYWlseVRhc2spIHtcblxuICAgICAgICAgIGF3YWl0IHN1Ym1pdENhbGVuZGFyRm9yUXVldWUoY2xpZW50LCB1c2VySWQsIGRheWpzKCkuaG91cig3KS5mb3JtYXQoKSwgZGF5anMoKS5ob3VyKDIzKS5taW51dGUoNTkpLmZvcm1hdCgpLCB0b2FzdClcbiAgICAgICAgXG4gICAgICB9XG4gICAgIH0gZWxzZSBpZiAoZXZlbnQuc29mdERlYWRsaW5lXG4gICAgICAgJiYgKGRlYWRsaW5lVHlwZSA9PT0gJ3NvZnQnKVxuICAgICAgICYmICEoZGF5anMoZXZlbnQuc29mdERlYWRsaW5lPy5zbGljZSgwLCAxOSkpLnR6KGV2ZW50Py50aW1lem9uZSB8fCBkYXlqcy50ei5ndWVzcygpLCB0cnVlKS5pc1NhbWUoZGF5anMobmV3RGVhZGxpbmUpLmZvcm1hdCgpLCAnbWludXRlJykpKSB7XG5cbiAgICAgIGlmICh0YXNrVHlwZSA9PT0gV2Vla2x5VGFzaykge1xuICAgICAgICAgIGF3YWl0IHN1Ym1pdENhbGVuZGFyRm9yUXVldWUoY2xpZW50LCB1c2VySWQsIGRheWpzKCkuaG91cig3KS5mb3JtYXQoKSwgZGF5anMoKS5hZGQoNiwgJ2RheScpLmhvdXIoMjMpLm1pbnV0ZSg1OSkuZm9ybWF0KCksIHRvYXN0KVxuICAgICAgfSBlbHNlIGlmICh0YXNrVHlwZSA9PT0gRGFpbHlUYXNrKSB7XG5cbiAgICAgICAgICBhd2FpdCBzdWJtaXRDYWxlbmRhckZvclF1ZXVlKGNsaWVudCwgdXNlcklkLCBkYXlqcygpLmhvdXIoNykuZm9ybWF0KCksIGRheWpzKCkuaG91cigyMykubWludXRlKDU5KS5mb3JtYXQoKSwgdG9hc3QpXG5cbiAgICAgIH0gXG4gICAgIH0gIGVsc2UgaWYgKGV2ZW50LmhhcmREZWFkbGluZVxuICAgICAgICAmJiAoZGVhZGxpbmVUeXBlID09PSAnaGFyZCcpXG4gICAgICAgICYmICEoZGF5anMoZXZlbnQuaGFyZERlYWRsaW5lPy5zbGljZSgwLCAxOSkpLnR6KGV2ZW50Py50aW1lem9uZSB8fCBkYXlqcy50ei5ndWVzcygpLCB0cnVlKS5pc1NhbWUoZGF5anMobmV3RGVhZGxpbmUpLmZvcm1hdCgpKSkpIHtcblxuICAgICAgICBpZiAodGFza1R5cGUgPT09ICdXZWVrbHknKSB7XG5cbiAgICAgICAgICAgIGF3YWl0IHN1Ym1pdENhbGVuZGFyRm9yUXVldWUoY2xpZW50LCB1c2VySWQsIGRheWpzKCkuaG91cig3KS5mb3JtYXQoKSwgZGF5anMoKS5hZGQoNiwgJ2RheScpLmhvdXIoMjMpLm1pbnV0ZSg1OSkuZm9ybWF0KCksIHRvYXN0KVxuXG4gICAgICAgIH0gZWxzZSBpZiAodGFza1R5cGUgPT09ICdEYWlseScpIHtcblxuICAgICAgICAgICAgYXdhaXQgc3VibWl0Q2FsZW5kYXJGb3JRdWV1ZShjbGllbnQsIHVzZXJJZCwgZGF5anMoKS5ob3VyKDcpLmZvcm1hdCgpLCBkYXlqcygpLmhvdXIoMjMpLm1pbnV0ZSg1OSkuZm9ybWF0KCksIHRvYXN0KVxuXG4gICAgICAgIH1cbiAgICAgfVxuICAgICBcbiAgICAgdG9hc3Qoe1xuICAgICAgICBzdGF0dXM6ICdzdWNjZXNzJyxcbiAgICAgICAgdGl0bGU6ICdTdWNjZXNzZnVsbHkgdXBkYXRlZCcsXG4gICAgICAgIGRlc2NyaXB0aW9uOiAnVGFzayBpcyBzdWNjZXNzZnVsbHkgdXBkYXRlZCcsXG4gICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICB9KVxuICAgICAgcm91dGVyLnB1c2goeyBwYXRobmFtZTogJy9Qcm9ncmVzcy9Ub2RvL1VzZXJUYXNrJywgcXVlcnk6IHtcbiAgICAgICAgdGFza1R5cGUsXG4gICAgICAgIGlzVXBkYXRlOiB1dWlkKCksXG4gICAgICB9fSlcbiAgIH0gY2F0Y2goZSkge1xuICAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cGRhdGUgZGVhZGxpbmUnKVxuICAgICB0b2FzdCh7XG4gICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgdGl0bGU6ICdVbmFibGUgdG8gdXBkYXRlJyxcbiAgICAgICAgZGVzY3JpcHRpb246ICdVbmFibGUgdG8gdXBkYXRlIGRlYWRsaW5lIGR1ZSB0byBhbiBpbnRlcm5hbCBlcnJvcicsXG4gICAgICAgIGR1cmF0aW9uOiA5MDAwLFxuICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICB9KVxuICAgIC8vICBuYXZpZ2F0aW9uLm5hdmlnYXRlKCdVc2VyVGFzaycsIHtcbiAgICAvLyAgICB0YXNrVHlwZSxcbiAgICAvLyAgICBpc1VwZGF0ZTogdW5kZWZpbmVkLFxuICAgIC8vICB9KVxuICAgfVxuICB9XG5cbiAgY29uc3Qgb25BY3RpdmVJbmRleENoYW5nZWQgPSAoaW5kZXg6IG51bWJlcikgPT4gc2V0QWN0aXZlSW5kZXgoaW5kZXgpXG5cbiAgY29uc3QgZ29Ub1ByZXZTdGVwID0gKCkgPT4ge1xuICAgIGNvbnN0IHByZXZBY3RpdmVJbmRleCA9IGFjdGl2ZUluZGV4XG4gICAgY29uc3QgbmV3QWN0aXZlSW5kZXggPSBwcmV2QWN0aXZlSW5kZXggPT09IDAgPyAwIDogcHJldkFjdGl2ZUluZGV4IC0gMVxuICAgIHNldEFjdGl2ZUluZGV4KG5ld0FjdGl2ZUluZGV4KVxuICB9XG5cbiAgY29uc3QgcmVuZGVyUHJldkJ1dHRvbiA9ICgpID0+IHtcbiAgICBpZiAoYWN0aXZlSW5kZXggPT09IDApIHtcbiAgICAgIHJldHVybiA8Qm94ICBwPXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19IC8+XG4gICAgfVxuXG4gICAgcmV0dXJuIChcbiAgICAgIDxCb3ggIG1sPXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19IG1iPXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19PlxuICAgICAgICA8QnV0dG9uIG9uQ2xpY2s9e2dvVG9QcmV2U3RlcH0+XG4gICAgICAgICAgQmFja1xuICAgICAgICA8L0J1dHRvbj5cbiAgICAgIDwvQm94PlxuICAgIClcbiAgfVxuXG4gIGNvbnN0IHJlbmRlck5leHRCdXR0b24gPSAoKSA9PiB7XG4gICAgaWYgKGFjdGl2ZUluZGV4ID09PSA0KSB7XG4gICAgICByZXR1cm4gPEJveCBtcj17eyBwaG9uZTogJ3MnLCB0YWJsZXQ6ICdtJyB9fSAvPlxuICAgIH1cblxuICAgIHJldHVybiAoXG4gICAgICA8Qm94IG1yPXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19IG1iPXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19PlxuICAgICAgICA8QnV0dG9uIG9uQ2xpY2s9e2dvVG9OZXh0U3RlcH0+XG4gICAgICAgICAgTmV4dFxuICAgICAgICA8L0J1dHRvbj5cbiAgICAgIDwvQm94PlxuICAgIClcbiAgfVxuXG4gIGNvbnN0IGdvVG9OZXh0U3RlcCA9ICgpID0+IHtcbiAgICBjb25zdCBwcmV2QWN0aXZlSW5kZXggPSBhY3RpdmVJbmRleFxuICAgIGNvbnN0IHByZXZDb21wbGV0ZWRTdGVwID0gY29tcGxldGVkU3RlcFxuXG4gICAgaWYgKHByZXZBY3RpdmVJbmRleCA9PT0gMykge1xuICAgICAgcmV0dXJuXG4gICAgfVxuXG4gICAgY29uc3QgbmV3QWN0aXZlSW5kZXggPSBwcmV2QWN0aXZlSW5kZXggKyAxXG5cbiAgICBpZiAoIXByZXZDb21wbGV0ZWRTdGVwIHx8IChwcmV2Q29tcGxldGVkU3RlcCA8IHByZXZBY3RpdmVJbmRleCkpIHtcbiAgICAgIGNvbnN0IG5ld0NvbXBsZXRlZFN0ZXAgPSBwcmV2QWN0aXZlSW5kZXhcbiAgICAgIHNldENvbXBsZXRlZFN0ZXAobmV3Q29tcGxldGVkU3RlcClcbiAgICB9XG5cbiAgICBpZiAobmV3QWN0aXZlSW5kZXggIT09IHByZXZBY3RpdmVJbmRleCkge1xuICAgICAgc2V0QWN0aXZlSW5kZXgobmV3QWN0aXZlSW5kZXgpXG4gICAgfVxuICB9XG5cbiAgY29uc3Qgb25TdWJtaXRQcmVzcyA9ICgpID0+IHtcbiAgICB0cnkge1xuICAgICAgcmV0dXJuIGlzVXBkYXRlXG4gICAgICAgID8gb25SZWNlaXZlVXBkYXRlRGVhZGxpbmUoKVxuICAgICAgICA6IG9uUmVjZWl2ZUNyZWF0ZURlYWRsaW5lKClcbiAgICB9IGNhdGNoKGUpIHtcbiAgICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHN1Ym1pdCBwcmVzcyBpbnNpZGUgVXNlclRhc2tEZWFkbGluZScpXG4gICAgfVxuICB9XG5cblxuXG4gIGNvbnN0IHJlbmRlckN1cnJlbnRTdGVwID0gKCkgPT4ge1xuICBcbiAgICBzd2l0Y2goYWN0aXZlSW5kZXgpIHtcbiAgICAgIGNhc2UgMDpcbiAgICAgICAgcmV0dXJuIChcbiAgICAgICAgICA8Qm94IGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiPlxuICAgICAgICAgICAgPFRleHQgdGV4dEFsaWduPVwiY2VudGVyXCIgdmFyaWFudD1cInN1YmhlYWRlclwiIG10PXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19PlxuICAgICAgICAgICAgICBEZWFkbGluZVxuICAgICAgICAgICAgPC9UZXh0PlxuICAgICAgICAgICAgPGRpdiBjbGFzc05hbWU9XCJmbGV4LTEgZmxleCBmbGV4LWNvbCBqdXN0aWZ5LWNlbnRlciBpdGVtcy1zdGFydFwiIHN0eWxlPXt7IG1pbkhlaWdodDogJzUwdmgnfX0+XG4gICAgICAgICAgICAgIDxCb3ggIG10PXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19IGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiIHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0+XG4gICAgICAgICAgICAgICAgXG4gICAgICAgICAgICAgICAgPElucHV0XG4gICAgICAgICAgICAgICAgICBwbGFjZWhvbGRlcj1cIlNlbGVjdCBEYXRlIGFuZCBUaW1lXCJcbiAgICAgICAgICAgICAgICAgIHNpemU9XCJtZFwiXG4gICAgICAgICAgICAgICAgICB0eXBlPVwiZGF0ZXRpbWUtbG9jYWxcIlxuICAgICAgICAgICAgICAgICAgb25DaGFuZ2U9eyhlKSA9PiB7XG4gICAgICAgICAgICAgICAgICAgICAgICBzZXROZXdEZWFkbGluZShkYXlqcyhlPy50YXJnZXQ/LnZhbHVlLCBcIllZWVktTU0tRERUSEg6bW1cIikudG9EYXRlKCkpXG4gICAgICAgICAgICAgICAgICB9fVxuICAgICAgICAgICAgICAgICAgdmFsdWU9e2RheWpzKG5ld0RlYWRsaW5lKS5mb3JtYXQoXCJZWVlZLU1NLUREVEhIOm1tXCIpfVxuICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgICAgICA8Qm94ICBtdD17eyBwaG9uZTogJ3MnLCB0YWJsZXQ6ICdtJyB9fSBqdXN0aWZ5Q29udGVudD1cImNlbnRlclwiIGFsaWduSXRlbXM9XCJjZW50ZXJcIj5cbiAgICAgICAgICAgICAgICA8c2VsZWN0IHZhbHVlPXtuZXdEZWFkbGluZVR5cGV9IG9uQ2hhbmdlPXsoZSkgPT4gc2V0TmV3RGVhZGxpbmVUeXBlKGU/LnRhcmdldD8udmFsdWUgYXMgRGVhZGxpbmVUeXBlKX0gY2xhc3NOYW1lPVwic2VsZWN0IHNlbGVjdC1wcmltYXJ5IHctZnVsbCBtYXgtdy14c1wiPlxuICAgICAgICAgICAgICAgICAgPG9wdGlvbiBkaXNhYmxlZCBzZWxlY3RlZD5QaWNrIGEgZGVhZGxpbmU8L29wdGlvbj5cbiAgICAgICAgICAgICAgICAgIHtfLm1hcChkZWFkbGluZU9wdGlvbnMsIG9wdGlvbiA9PiAoXG4gICAgICAgICAgICAgICAgICAgICAgPG9wdGlvblxuICAgICAgICAgICAgICAgICAgICAgICAgICBrZXk9e29wdGlvbi52YWx1ZX1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgdmFsdWU9e29wdGlvbi52YWx1ZX1cbiAgICAgICAgICAgICAgICAgICAgICA+e29wdGlvbi5sYWJlbH08L29wdGlvbj5cbiAgICAgICAgICAgICAgICAgICAgICApKX1cbiAgICAgICAgICAgICAgICA8L3NlbGVjdD5cbiAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgIDxCb3ggIG10PXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19IGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiIHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0+XG5cbiAgICAgICAgICAgICAgICAgIDxUZXh0RmllbGRcbiAgICAgICAgICAgICAgICAgICAgbGFiZWw9XCJEdXJhdGlvbiAobWludXRlcylcIlxuICAgICAgICAgICAgICAgICAgICB0eXBlPVwibnVtYmVyXCJcbiAgICAgICAgICAgICAgICAgICAgb25DaGFuZ2U9eyhlOiB7IHRhcmdldDogeyB2YWx1ZTogc3RyaW5nIH0gfSkgPT4gc2V0TmV3RHVyYXRpb24ocGFyc2VJbnQoZT8udGFyZ2V0Py52YWx1ZS5yZXBsYWNlKC9bXjAtOS5dL2csICcnKSwgMTApKX1cbiAgICAgICAgICAgICAgICAgICAgdmFsdWU9e2Ake25ld0R1cmF0aW9ufWB9XG4gICAgICAgICAgICAgICAgICAgIHBsYWNlaG9sZGVyPVwiMVwiXG4gICAgICAgICAgICAgICAgICAgIHN0eWxlPXt7Li4uKHN0eWxlcz8uaW5wdXRGaWVsZCl9fVxuICAgICAgICAgICAgICAgICAgLz5cbiAgICAgICAgICBcbiAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICAgIDxCb3ggIG10PXt7IHBob25lOiAncycsIHRhYmxldDogJ20nIH19IGp1c3RpZnlDb250ZW50PVwiY2VudGVyXCIgYWxpZ25JdGVtcz1cImNlbnRlclwiIHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0+XG4gICAgICAgICAgICAgICAgPFRleHRGaWVsZFxuICAgICAgICAgICAgICAgICAgbGFiZWw9XCJQcmlvcml0eSAoID4gMClcIlxuICAgICAgICAgICAgICAgICAgdHlwZT1cIm51bWJlclwiXG4gICAgICAgICAgICAgICAgICBvbkNoYW5nZT17KGU6IHsgdGFyZ2V0OiB7IHZhbHVlOiBzdHJpbmcgfSB9KSA9PiBvbkNoYW5nZVByaW9yaXR5KGU/LnRhcmdldD8udmFsdWUpfVxuICAgICAgICAgICAgICAgICAgdmFsdWU9e2Ake25ld1ByaW9yaXR5fWB9XG4gICAgICAgICAgICAgICAgICBwbGFjZWhvbGRlcj1cIjFcIlxuICAgICAgICAgICAgICAgICAgc3R5bGU9e3sgLi4uKHN0eWxlcz8uaW5wdXRGaWVsZCl9fVxuICAgICAgICAgICAgICAgIC8+XG4gICAgICAgICAgICBcbiAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICAgICAgICAgIDxCb3ggZmxleERpcmVjdGlvbj1cInJvd1wiIGp1c3RpZnlDb250ZW50PVwic3BhY2UtYmV0d2VlblwiIHN0eWxlPXt7IHdpZHRoOiAnMTAwJScgfX0+XG4gICAgICAgICAgICAgIDxCb3ggLz5cbiAgICAgICAgICAgICAge3JlbmRlck5leHRCdXR0b24oKX1cbiAgICAgICAgICAgIDwvQm94PlxuICAgICAgICAgIDwvQm94PlxuICAgICAgICApXG4gICAgICBjYXNlIDE6XG4gICAgICAgIHJldHVybiAoXG4gICAgICAgICAgPEJveCAganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCI+XG4gICAgICAgICAgICBcbiAgICAgICAgICAgIDxCb3gganVzdGlmeUNvbnRlbnQ9XCJjZW50ZXJcIiBhbGlnbkl0ZW1zPVwiY2VudGVyXCIgbWluSGVpZ2h0PVwiNjB2aFwiPlxuICAgICAgICAgICAgICA8VGV4dCB2YXJpYW50PVwic3ViaGVhZGVyXCIgbXQ9e3sgcGhvbmU6ICdtJywgdGFibGV0OiAnbCcgfX0+XG4gICAgICAgICAgICAgICAgICB7aXNVcGRhdGUgPyAnVXBkYXRlIHRhc2sgZGVhZGxpbmUnIDogJ0NyZWF0ZSB0YXNrIGRlYWRsaW5lPyd9XG4gICAgICAgICAgICAgIDwvVGV4dD5cbiAgICAgICAgICAgICAgPEJveCBtdD17eyBwaG9uZTogJ20nLCB0YWJsZXQ6ICdsJyB9fT5cbiAgICAgICAgICAgICAgICA8QnV0dG9uIG9uQ2xpY2s9e29uU3VibWl0UHJlc3N9PlxuICAgICAgICAgICAgICAgICAge2lzVXBkYXRlID8gJ1VwZGF0ZScgOiAnQ3JlYXRlJ31cbiAgICAgICAgICAgICAgICA8L0J1dHRvbj5cbiAgICAgICAgICAgICAgPC9Cb3g+XG4gICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICAgIDxCb3ggZmxleERpcmVjdGlvbj1cInJvd1wiIGp1c3RpZnlDb250ZW50PVwiZmxleC1zdGFydFwiIHdpZHRoPVwiMTAwJVwiPlxuICAgICAgICAgICAgICAgIHtyZW5kZXJQcmV2QnV0dG9uKCl9XG4gICAgICAgICAgICA8L0JveD5cbiAgICAgICAgICA8L0JveD5cbiAgICAgICAgKVxuICAgIH1cbiAgfVxuXG4gIHJldHVybiAoXG4gICAgPEJveCBmbGV4PXsxfT5cbiAgICAgIDxXaXphcmRcbiAgICAgICAgaXRlbXM9e1tcbiAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBpbmRleDogMCxcbiAgICAgICAgICAgICAgICBsYWJlbDogJ0FkZCBhIFBlcmlvZCcsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgIGluZGV4OiAxLFxuICAgICAgICAgICAgICAgIGxhYmVsOiAnQ3JlYXRlIERlYWRsaW5lJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgIF19XG5cbiAgICAgICAgY29tcGxldGVkPXtjb21wbGV0ZWRTdGVwfVxuICAgICAgICBhY3RpdmVJbmRleD17YWN0aXZlSW5kZXh9XG4gICAgICAvPlxuICAgICAge3JlbmRlckN1cnJlbnRTdGVwKCl9XG4gICAgPC9Cb3g+XG4gIClcbn1cblxuZXhwb3J0IGRlZmF1bHQgVXNlclRhc2tEZWFkbGluZVxuXG4iXX0=