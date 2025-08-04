"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createInitialSelectedCalendar = exports.createDefaultUser = exports.createDefaultPrimaryCalendar = exports.createUserPreference = exports.updateUserPreferenceOnBoarded = exports.updateUserForPreferenceId = exports.getUserPreference = exports.generateDefaultCategories = exports.setPrimaryCalendar = exports.dropPrimaryLabelForCalendar = exports.dropPrimaryLabelForCalendars = exports.listEventsForCalendar = void 0;
const uuid_1 = require("uuid");
const date_utils_1 = require("@lib/date-utils");
const theme_1 = require("@lib/theme/theme");
const thirdpartyemailpassword_1 = __importDefault(require("supertokens-web-js/recipe/thirdpartyemailpassword"));
const updateCalendarToGlobalPrimary_1 = __importDefault(require("@lib/apollo/gql/updateCalendarToGlobalPrimary"));
const CategoryHelper_1 = require("@lib/Category/CategoryHelper");
const upsertUserPreference_1 = __importDefault(require("@lib/apollo/gql/upsertUserPreference"));
const getGlobalPrimaryCalendar_1 = __importDefault(require("@lib/apollo/gql/getGlobalPrimaryCalendar"));
const getAnyCalendar_1 = __importDefault(require("@lib/apollo/gql/getAnyCalendar"));
const getUserById_1 = __importDefault(require("@lib/apollo/gql/getUserById"));
const upsertUser_1 = __importDefault(require("@lib/apollo/gql/upsertUser"));
const updateUserForUserPreferenceId_1 = __importDefault(require("@lib/apollo/gql/updateUserForUserPreferenceId"));
const listEventsForCalendarId_1 = __importDefault(require("@lib/apollo/gql/listEventsForCalendarId"));
const updateUserPreferenceOnBoardedMutation_1 = __importDefault(require("@lib/apollo/gql/updateUserPreferenceOnBoardedMutation"));
const updateCalendarDropGlobalPrimary_1 = __importDefault(require("@lib/apollo/gql/updateCalendarDropGlobalPrimary"));
const getUserPreferenceForUser_1 = __importDefault(require("@lib/apollo/gql/getUserPreferenceForUser"));
const updateCalendarsDropGlobalPrimary_1 = __importDefault(require("@lib/apollo/gql/updateCalendarsDropGlobalPrimary"));
const DEFAULTCATEGORIES = [
    {
        id: (0, uuid_1.v4)(),
        name: 'External Meeting',
        createdDate: (0, date_utils_1.dayjs)().toISOString(),
        updatedAt: (0, date_utils_1.dayjs)().toISOString(),
        deleted: false,
        userId: '',
    },
    {
        id: (0, uuid_1.v4)(),
        name: 'Meeting',
        createdDate: (0, date_utils_1.dayjs)().toISOString(),
        updatedAt: (0, date_utils_1.dayjs)().toISOString(),
        deleted: false,
        userId: '',
    },
    {
        id: (0, uuid_1.v4)(),
        name: 'Life Milestone',
        createdDate: (0, date_utils_1.dayjs)().toISOString(),
        updatedAt: (0, date_utils_1.dayjs)().toISOString(),
        deleted: false,
        userId: '',
    },
    {
        id: (0, uuid_1.v4)(),
        name: 'Sports',
        createdDate: (0, date_utils_1.dayjs)().toISOString(),
        updatedAt: (0, date_utils_1.dayjs)().toISOString(),
        deleted: false,
        userId: '',
    },
    {
        id: (0, uuid_1.v4)(),
        name: 'Social Meetup',
        createdDate: (0, date_utils_1.dayjs)().toISOString(),
        updatedAt: (0, date_utils_1.dayjs)().toISOString(),
        deleted: false,
        userId: '',
    },
    {
        id: (0, uuid_1.v4)(),
        name: 'Break',
        createdDate: (0, date_utils_1.dayjs)().toISOString(),
        updatedAt: (0, date_utils_1.dayjs)().toISOString(),
        deleted: false,
        userId: '',
    },
];
const STARTTIMES = [
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
    },
];
const ENDTIMES = [
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
    },
];
const listEventsForCalendar = async (client, calendarId) => {
    try {
        const { data } = await client.query({
            query: listEventsForCalendarId_1.default,
            variables: {
                calendarId,
            },
        });
        console.log(data, ' successfully listed events for Calendar');
        return data?.Event;
    }
    catch (e) {
        console.log(e, ' unable to listEventsForCalendar');
    }
};
exports.listEventsForCalendar = listEventsForCalendar;
const dropPrimaryLabelForCalendars = async (client, calendarIds) => {
    try {
        // validate
        if (!(calendarIds?.length > 0)) {
            console.log('no calendarIds inside dropPrimaryLableForCalendars');
            return null;
        }
        const { data } = await client.mutate({
            mutation: updateCalendarsDropGlobalPrimary_1.default,
            variables: {
                ids: calendarIds,
            },
            update(cache, { data }) {
                const deletedCalendars = data?.update_Calendar?.returning;
                const normalizedIds = deletedCalendars?.map((c) => cache.identify({ id: c.id, __typename: c.__typename }));
                normalizedIds?.forEach((id) => cache.evict({ id }));
                cache.gc();
            },
        });
        console.log(data, ' successfully dropped primary calendar');
    }
    catch (e) {
        console.log(e, ' unable to dropPrimaryCalendar');
    }
};
exports.dropPrimaryLabelForCalendars = dropPrimaryLabelForCalendars;
const dropPrimaryLabelForCalendar = async (client, calendarId) => {
    try {
        // validate
        if (!calendarId) {
            console.log('no calendarId inside dropPrimaryLabelForCalendar');
            return null;
        }
        const { data } = await client.mutate({
            mutation: updateCalendarDropGlobalPrimary_1.default,
            variables: {
                id: calendarId,
            },
        });
        console.log(data, ' successfully dropped primary calendar');
    }
    catch (e) {
        console.log(e, ' unable to dropPrimaryCalendar');
    }
};
exports.dropPrimaryLabelForCalendar = dropPrimaryLabelForCalendar;
const setPrimaryCalendar = async (client, calendar) => {
    try {
        const { data } = await client.mutate({
            mutation: updateCalendarToGlobalPrimary_1.default,
            variables: {
                id: calendar.id,
            },
        });
        console.log('setPrimaryCalendar', data);
    }
    catch (e) {
        console.error(e, ' setPrimaryCalendar');
    }
};
exports.setPrimaryCalendar = setPrimaryCalendar;
const generateDefaultCategories = async (client, userId) => {
    try {
        const existingCategories = await (0, CategoryHelper_1.listUserCategories)(client, userId);
        if (existingCategories?.length === 0) {
            DEFAULTCATEGORIES.forEach(async (category) => {
                await (0, CategoryHelper_1.createCategory)(client, category?.name, userId);
            });
        }
    }
    catch (e) {
        console.error(e, ' generateDefaultCategories');
    }
};
exports.generateDefaultCategories = generateDefaultCategories;
const getUserPreference = async (client, userId) => {
    try {
        const { data } = await client.query({
            query: getUserPreferenceForUser_1.default,
            variables: {
                userId,
            },
            fetchPolicy: 'no-cache',
        });
        console.log(data, ' data getUserPreference');
        if (data?.User_Preference?.length > 0) {
            console.log(data.User_Preference[0], ' data.User_Preference[0]');
            return data.User_Preference[0];
        }
        return null;
    }
    catch (e) {
        console.error(e, ' getUserPreference');
    }
};
exports.getUserPreference = getUserPreference;
const updateUserForPreferenceId = async (client, userId, preferenceId) => {
    try {
        const { data } = await client.mutate({
            mutation: updateUserForUserPreferenceId_1.default,
            variables: {
                id: userId,
                userPreferenceId: preferenceId,
            },
        });
        console.log('updateUserForPreferenceId', data);
    }
    catch (e) {
        console.error(e, ' updateUserForPreferenceId');
    }
};
exports.updateUserForPreferenceId = updateUserForPreferenceId;
const updateUserPreferenceOnBoarded = async (client, userId, onBoarded) => {
    try {
        const { data } = await client.mutate({
            mutation: updateUserPreferenceOnBoardedMutation_1.default,
            variables: {
                userId,
                onBoarded,
            },
            // refetchQueries: [
            //     getUserPreferenceForUser, // DocumentNode object parsed with gql
            //     'getUserPreferenceForUser' // Query name
            // ],
            update(cache, { data }) {
                if (data && data?.update_User_Preference?.affected_rows > 0) {
                    console.log('updateUserPreferenceOnBoarded', data);
                }
                cache.modify({
                    fields: {
                        User_Preference(existingUserPreferences = []) {
                            //     const newUserPreferenceRef = cache.writeFragment({
                            //         data: data?.update_User_Preference?.returning?.[0],
                            //         fragment: gql`
                            //     fragment NewUser_Preference on User_Preference {
                            //         id
                            //         onBoarded
                            //     }
                            //   `
                            //     });
                            return [
                                {
                                    ...existingUserPreferences?.[0],
                                    onBoarded: data?.update_User_Preference?.returning?.[0]?.onBoarded,
                                },
                            ];
                        },
                    },
                });
            },
        });
        console.log('updateUserPreferenceOnBoarded', data);
    }
    catch (e) {
        console.log(e, ' error in updateUserPreferenceOnboarded');
    }
};
exports.updateUserPreferenceOnBoarded = updateUserPreferenceOnBoarded;
const createUserPreference = async (client, userId) => {
    try {
        const existinguser_preference = await (0, exports.getUserPreference)(client, userId);
        const id = (0, uuid_1.v4)();
        if (!existinguser_preference) {
            const userPreferenceValues = {
                id,
                userId,
                createdDate: (0, date_utils_1.dayjs)().toISOString(),
                updatedAt: (0, date_utils_1.dayjs)().toISOString(),
                deleted: false,
                maxWorkLoadPercent: 85,
                backToBackMeetings: false,
                minNumberOfBreaks: 1,
                maxNumberOfMeetings: 4,
                breakLength: 15,
                startTimes: STARTTIMES,
                endTimes: ENDTIMES,
                breakColor: theme_1.palette.greenPrimary,
                onBoarded: false,
                copyAvailability: true,
                copyTimeBlocking: true,
                copyTimePreference: true,
                copyReminders: true,
                copyPriorityLevel: true,
                copyModifiable: true,
                copyCategories: true,
                copyIsBreak: true,
                copyIsMeeting: true,
                copyIsExternalMeeting: true,
                copyColor: true,
            };
            const { data } = await client.mutate({
                mutation: upsertUserPreference_1.default,
                variables: {
                    userPreference: userPreferenceValues,
                },
            });
            await (0, exports.updateUserForPreferenceId)(client, userId, id);
            console.log('createUserPreference', data);
        }
    }
    catch (e) {
        console.error(e, ' createuser_preference');
    }
};
exports.createUserPreference = createUserPreference;
const createDefaultPrimaryCalendar = async (client, userId) => {
    try {
        const existingCalendar = (await client.query({
            query: getGlobalPrimaryCalendar_1.default,
            variables: {
                userId,
            },
        })).data?.Calendar?.[0];
        if (!existingCalendar) {
            // make any calendar the primary
            const calendarDoc = (await client.query({
                query: getAnyCalendar_1.default,
                variables: {
                    userId,
                },
            })).data?.Calendar?.[0];
            if (calendarDoc) {
                await client.mutate({
                    mutation: updateCalendarToGlobalPrimary_1.default,
                    variables: {
                        id: calendarDoc?.id,
                    },
                });
            }
        }
    }
    catch (e) {
        console.error(e, ' createDefaultPrimaryCalendar');
    }
};
exports.createDefaultPrimaryCalendar = createDefaultPrimaryCalendar;
const createDefaultUser = async (client, userId) => {
    try {
        const existingUser = (await client.query({
            query: getUserById_1.default,
            variables: {
                id: userId,
            },
        }))?.data?.User_by_pk;
        if (!existingUser) {
            const userInfo = await thirdpartyemailpassword_1.default.getUserById(userId);
            const email = userInfo?.email;
            const valuesToUpsert = {
                id: userId,
                createdDate: (0, date_utils_1.dayjs)().toISOString(),
                updatedAt: (0, date_utils_1.dayjs)().toISOString(),
                deleted: false,
                email,
                name: userInfos?.name || '',
            };
            await client.mutate({
                mutation: upsertUser_1.default,
                variables: {
                    user: valuesToUpsert,
                },
            });
            console.log('createDefaultUser', valuesToUpsert);
        }
    }
    catch (e) {
        console.error(e, ' createDefaultUser');
    }
};
exports.createDefaultUser = createDefaultUser;
// create initial selected calendar
const createInitialSelectedCalendar = async (client, userId, setSelectedCalendar) => {
    try {
        const existingCalendar = (await client.query({
            query: getGlobalPrimaryCalendar_1.default,
            variables: {
                userId,
            },
        })).data?.Calendar?.[0];
        if (!existingCalendar) {
            const oldCalendarDoc = (await client.query({
                query: getAnyCalendar_1.default,
                variables: {
                    userId,
                },
            })).data?.Calendar?.[0];
            if (oldCalendarDoc) {
                await client.mutate({
                    mutation: updateCalendarToGlobalPrimary_1.default,
                    variables: {
                        id: oldCalendarDoc?.id,
                    },
                });
                setSelectedCalendar(oldCalendarDoc?.id);
            }
        }
        else {
            setSelectedCalendar(existingCalendar?.id);
        }
    }
    catch (e) {
        console.error(e, ' createInitialSelectedCalendar');
    }
};
exports.createInitialSelectedCalendar = createInitialSelectedCalendar;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiT25Cb2FyZEhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIk9uQm9hcmRIZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBQ0EsK0JBQWtDO0FBR2xDLGdEQUF3QztBQUV4Qyw0Q0FBMkM7QUFTM0MsZ0hBQXdGO0FBS3hGLGtIQUEwRjtBQUMxRixpRUFHc0M7QUFFdEMsZ0dBQXdFO0FBQ3hFLHdHQUFnRjtBQUNoRixvRkFBNEQ7QUFFNUQsOEVBQXNEO0FBQ3RELDRFQUFvRDtBQUNwRCxrSEFBMEY7QUFHMUYsc0dBQThFO0FBQzlFLGtJQUEwRztBQUMxRyxzSEFBOEY7QUFDOUYsd0dBQWdGO0FBQ2hGLHdIQUFnRztBQUVoRyxNQUFNLGlCQUFpQixHQUFtQjtJQUN4QztRQUNFLEVBQUUsRUFBRSxJQUFBLFNBQUksR0FBRTtRQUNWLElBQUksRUFBRSxrQkFBa0I7UUFDeEIsV0FBVyxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLFdBQVcsRUFBRTtRQUNsQyxTQUFTLEVBQUUsSUFBQSxrQkFBSyxHQUFFLENBQUMsV0FBVyxFQUFFO1FBQ2hDLE9BQU8sRUFBRSxLQUFLO1FBQ2QsTUFBTSxFQUFFLEVBQUU7S0FDWDtJQUNEO1FBQ0UsRUFBRSxFQUFFLElBQUEsU0FBSSxHQUFFO1FBQ1YsSUFBSSxFQUFFLFNBQVM7UUFDZixXQUFXLEVBQUUsSUFBQSxrQkFBSyxHQUFFLENBQUMsV0FBVyxFQUFFO1FBQ2xDLFNBQVMsRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxXQUFXLEVBQUU7UUFDaEMsT0FBTyxFQUFFLEtBQUs7UUFDZCxNQUFNLEVBQUUsRUFBRTtLQUNYO0lBQ0Q7UUFDRSxFQUFFLEVBQUUsSUFBQSxTQUFJLEdBQUU7UUFDVixJQUFJLEVBQUUsZ0JBQWdCO1FBQ3RCLFdBQVcsRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxXQUFXLEVBQUU7UUFDbEMsU0FBUyxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLFdBQVcsRUFB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RUFBRTtvQkFDVCxNQUFNO2lCQUNQO2FBQ0YsQ0FBQyxDQUNILENBQUMsSUFBSSxFQUFFLFFBQVEsRUFBRSxDQUFDLENBQUMsQ0FBQyxDQUFDO1lBRXRCLElBQUksY0FBYyxFQUFFLENBQUM7Z0JBQ25CLE1BQU0sTUFBTSxDQUFDLE1BQU0sQ0FBMEM7b0JBQzNELFFBQVEsRUFBRSx1Q0FBNkI7b0JBQ3ZDLFNBQVMsRUFBRTt3QkFDVCxFQUFFLEVBQUUsY0FBYyxFQUFFLEVBQUU7cUJBQ3ZCO2lCQUNGLENBQUMsQ0FBQztnQkFDSCxtQkFBbUIsQ0FBQyxjQUFjLEVBQUUsRUFBRSxDQUFDLENBQUM7WUFDMUMsQ0FBQztRQUNILENBQUM7YUFBTSxDQUFDO1lBQ04sbUJBQW1CLENBQUMsZ0JBQWdCLEVBQUUsRUFBRSxDQUFDLENBQUM7UUFDNUMsQ0FBQztJQUNILENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsZ0NBQWdDLENBQUMsQ0FBQztJQUNyRCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBeENXLFFBQUEsNkJBQTZCLGlDQXdDeEMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgXyBmcm9tICdsb2Rhc2gnO1xuaW1wb3J0IHsgdjQgYXMgdXVpZCB9IGZyb20gJ3V1aWQnO1xuaW1wb3J0IHsgRGlzcGF0Y2ggfSBmcm9tICdyZWFjdCc7XG5cbmltcG9ydCB7IGRheWpzIH0gZnJvbSAnQGxpYi9kYXRlLXV0aWxzJztcblxuaW1wb3J0IHsgcGFsZXR0ZSB9IGZyb20gJ0BsaWIvdGhlbWUvdGhlbWUnO1xuaW1wb3J0IHsgQ2FsZW5kYXJUeXBlIH0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvQ2FsZW5kYXJUeXBlJztcbmltcG9ydCB7IENhdGVnb3J5VHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL0NhdGVnb3J5VHlwZSc7XG5pbXBvcnQge1xuICBFbmRUaW1lVHlwZSxcbiAgU3RhcnRUaW1lVHlwZSxcbiAgVXNlclByZWZlcmVuY2VUeXBlLFxufSBmcm9tICdAbGliL2RhdGFUeXBlcy9Vc2VyX1ByZWZlcmVuY2VUeXBlJztcblxuaW1wb3J0IFRoaXJkUGFydHlFbWFpbFBhc3N3b3JkIGZyb20gJ3N1cGVydG9rZW5zLXdlYi1qcy9yZWNpcGUvdGhpcmRwYXJ0eWVtYWlscGFzc3dvcmQnO1xuXG5pbXBvcnQgeyBQbGF0Zm9ybSB9IGZyb20gJ3JlYWN0LW5hdGl2ZSc7XG5pbXBvcnQgeyBsb2NhbENhbGVuZGFyUmVzb3VyY2UgfSBmcm9tICdAbGliL2NhbGVuZGFyTGliL2NvbnN0YW50cyc7XG5pbXBvcnQgeyBBcG9sbG9DbGllbnQsIE5vcm1hbGl6ZWRDYWNoZU9iamVjdCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcbmltcG9ydCB1cGRhdGVDYWxlbmRhclRvR2xvYmFsUHJpbWFyeSBmcm9tICdAbGliL2Fwb2xsby9ncWwvdXBkYXRlQ2FsZW5kYXJUb0dsb2JhbFByaW1hcnknO1xuaW1wb3J0IHtcbiAgY3JlYXRlQ2F0ZWdvcnksXG4gIGxpc3RVc2VyQ2F0ZWdvcmllcyxcbn0gZnJvbSAnQGxpYi9DYXRlZ29yeS9DYXRlZ29yeUhlbHBlcic7XG5cbmltcG9ydCB1cHNlcnRVc2VyUHJlZmVyZW5jZSBmcm9tICdAbGliL2Fwb2xsby9ncWwvdXBzZXJ0VXNlclByZWZlcmVuY2UnO1xuaW1wb3J0IGdldEdsb2JhbFByaW1hcnlDYWxlbmRhciBmcm9tICdAbGliL2Fwb2xsby9ncWwvZ2V0R2xvYmFsUHJpbWFyeUNhbGVuZGFyJztcbmltcG9ydCBnZXRBbnlDYWxlbmRhciBmcm9tICdAbGliL2Fwb2xsby9ncWwvZ2V0QW55Q2FsZW5kYXInO1xuaW1wb3J0IHsgVXNlclR5cGUgfSBmcm9tICdAbGliL2RhdGFUeXBlcy9Vc2VyVHlwZSc7XG5pbXBvcnQgZ2V0VXNlckJ5SWQgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2dldFVzZXJCeUlkJztcbmltcG9ydCB1cHNlcnRVc2VyIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC91cHNlcnRVc2VyJztcbmltcG9ydCB1cGRhdGVVc2VyRm9yVXNlclByZWZlcmVuY2VJZCBmcm9tICdAbGliL2Fwb2xsby9ncWwvdXBkYXRlVXNlckZvclVzZXJQcmVmZXJlbmNlSWQnO1xuaW1wb3J0IHVwc2VydENhbGVuZGFyIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC91cHNlcnRDYWxlbmRhcic7XG5pbXBvcnQgeyBFdmVudFR5cGUgfSBmcm9tICdAbGliL2RhdGFUeXBlcy9FdmVudFR5cGUnO1xuaW1wb3J0IGxpc3RFdmVudHNGb3JDYWxlbmRhcklkIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9saXN0RXZlbnRzRm9yQ2FsZW5kYXJJZCc7XG5pbXBvcnQgdXBkYXRlVXNlclByZWZlcmVuY2VPbkJvYXJkZWRNdXRhdGlvbiBmcm9tICdAbGliL2Fwb2xsby9ncWwvdXBkYXRlVXNlclByZWZlcmVuY2VPbkJvYXJkZWRNdXRhdGlvbic7XG5pbXBvcnQgdXBkYXRlQ2FsZW5kYXJEcm9wR2xvYmFsUHJpbWFyeSBmcm9tICdAbGliL2Fwb2xsby9ncWwvdXBkYXRlQ2FsZW5kYXJEcm9wR2xvYmFsUHJpbWFyeSc7XG5pbXBvcnQgZ2V0VXNlclByZWZlcmVuY2VGb3JVc2VyIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9nZXRVc2VyUHJlZmVyZW5jZUZvclVzZXInO1xuaW1wb3J0IHVwZGF0ZUNhbGVuZGFyc0Ryb3BHbG9iYWxQcmltYXJ5IGZyb20gJ0BsaWIvYXBvbGxvL2dxbC91cGRhdGVDYWxlbmRhcnNEcm9wR2xvYmFsUHJpbWFyeSc7XG5cbmNvbnN0IERFRkFVTFRDQVRFR09SSUVTOiBDYXRlZ29yeVR5cGVbXSA9IFtcbiAge1xuICAgIGlkOiB1dWlkKCksXG4gICAgbmFtZTogJ0V4dGVybmFsIE1lZXRpbmcnLFxuICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgZGVsZXRlZDogZmFsc2UsXG4gICAgdXNlcklkOiAnJyxcbiAgfSxcbiAge1xuICAgIGlkOiB1dWlkKCksXG4gICAgbmFtZTogJ01lZXRpbmcnLFxuICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgZGVsZXRlZDogZmFsc2UsXG4gICAgdXNlcklkOiAnJyxcbiAgfSxcbiAge1xuICAgIGlkOiB1dWlkKCksXG4gICAgbmFtZTogJ0xpZmUgTWlsZXN0b25lJyxcbiAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgIHVzZXJJZDogJycsXG4gIH0sXG4gIHtcbiAgICBpZDogdXVpZCgpLFxuICAgIG5hbWU6ICdTcG9ydHMnLFxuICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgZGVsZXRlZDogZmFsc2UsXG4gICAgdXNlcklkOiAnJyxcbiAgfSxcbiAge1xuICAgIGlkOiB1dWlkKCksXG4gICAgbmFtZTogJ1NvY2lhbCBNZWV0dXAnLFxuICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgZGVsZXRlZDogZmFsc2UsXG4gICAgdXNlcklkOiAnJyxcbiAgfSxcbiAge1xuICAgIGlkOiB1dWlkKCksXG4gICAgbmFtZTogJ0JyZWFrJyxcbiAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgIHVzZXJJZDogJycsXG4gIH0sXG5dO1xuXG5jb25zdCBTVEFSVFRJTUVTOiBTdGFydFRpbWVUeXBlW10gPSBbXG4gIHtcbiAgICBkYXk6IDEsXG4gICAgaG91cjogNyxcbiAgICBtaW51dGVzOiAwLFxuICB9LFxuICB7XG4gICAgZGF5OiAyLFxuICAgIGhvdXI6IDcsXG4gICAgbWludXRlczogMCxcbiAgfSxcbiAge1xuICAgIGRheTogMyxcbiAgICBob3VyOiA3LFxuICAgIG1pbnV0ZXM6IDAsXG4gIH0sXG4gIHtcbiAgICBkYXk6IDQsXG4gICAgaG91cjogNyxcbiAgICBtaW51dGVzOiAwLFxuICB9LFxuICB7XG4gICAgZGF5OiA1LFxuICAgIGhvdXI6IDcsXG4gICAgbWludXRlczogMCxcbiAgfSxcbiAge1xuICAgIGRheTogNixcbiAgICBob3VyOiA3LFxuICAgIG1pbnV0ZXM6IDAsXG4gIH0sXG4gIHtcbiAgICBkYXk6IDcsXG4gICAgaG91cjogNyxcbiAgICBtaW51dGVzOiAwLFxuICB9LFxuXTtcblxuY29uc3QgRU5EVElNRVM6IEVuZFRpbWVUeXBlW10gPSBbXG4gIHtcbiAgICBkYXk6IDEsXG4gICAgaG91cjogMTksXG4gICAgbWludXRlczogMCxcbiAgfSxcbiAge1xuICAgIGRheTogMixcbiAgICBob3VyOiAxOSxcbiAgICBtaW51dGVzOiAwLFxuICB9LFxuICB7XG4gICAgZGF5OiAzLFxuICAgIGhvdXI6IDE5LFxuICAgIG1pbnV0ZXM6IDAsXG4gIH0sXG4gIHtcbiAgICBkYXk6IDQsXG4gICAgaG91cjogMTksXG4gICAgbWludXRlczogMCxcbiAgfSxcbiAge1xuICAgIGRheTogNSxcbiAgICBob3VyOiAxOSxcbiAgICBtaW51dGVzOiAwLFxuICB9LFxuICB7XG4gICAgZGF5OiA2LFxuICAgIGhvdXI6IDE5LFxuICAgIG1pbnV0ZXM6IDAsXG4gIH0sXG4gIHtcbiAgICBkYXk6IDcsXG4gICAgaG91cjogMTksXG4gICAgbWludXRlczogMCxcbiAgfSxcbl07XG5cbmV4cG9ydCBjb25zdCBsaXN0RXZlbnRzRm9yQ2FsZW5kYXIgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIGNhbGVuZGFySWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQucXVlcnk8e1xuICAgICAgRXZlbnQ6IEV2ZW50VHlwZVtdO1xuICAgIH0+KHtcbiAgICAgIHF1ZXJ5OiBsaXN0RXZlbnRzRm9yQ2FsZW5kYXJJZCxcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICBjYWxlbmRhcklkLFxuICAgICAgfSxcbiAgICB9KTtcblxuICAgIGNvbnNvbGUubG9nKGRhdGEsICcgc3VjY2Vzc2Z1bGx5IGxpc3RlZCBldmVudHMgZm9yIENhbGVuZGFyJyk7XG4gICAgcmV0dXJuIGRhdGE/LkV2ZW50O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gbGlzdEV2ZW50c0ZvckNhbGVuZGFyJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBkcm9wUHJpbWFyeUxhYmVsRm9yQ2FsZW5kYXJzID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBjYWxlbmRhcklkczogc3RyaW5nW11cbik6IFByb21pc2U8dm9pZCB8IG51bGw+ID0+IHtcbiAgdHJ5IHtcbiAgICAvLyB2YWxpZGF0ZVxuICAgIGlmICghKGNhbGVuZGFySWRzPy5sZW5ndGggPiAwKSkge1xuICAgICAgY29uc29sZS5sb2coJ25vIGNhbGVuZGFySWRzIGluc2lkZSBkcm9wUHJpbWFyeUxhYmxlRm9yQ2FsZW5kYXJzJyk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQubXV0YXRlPHtcbiAgICAgIHVwZGF0ZV9DYWxlbmRhcjogeyBhZmZlY3RlZF9yb3dzOiBudW1iZXI7IHJldHVybmluZzogQ2FsZW5kYXJUeXBlW10gfTtcbiAgICB9Pih7XG4gICAgICBtdXRhdGlvbjogdXBkYXRlQ2FsZW5kYXJzRHJvcEdsb2JhbFByaW1hcnksXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgaWRzOiBjYWxlbmRhcklkcyxcbiAgICAgIH0sXG4gICAgICB1cGRhdGUoY2FjaGUsIHsgZGF0YSB9KSB7XG4gICAgICAgIGNvbnN0IGRlbGV0ZWRDYWxlbmRhcnMgPSBkYXRhPy51cGRhdGVfQ2FsZW5kYXI/LnJldHVybmluZztcbiAgICAgICAgY29uc3Qgbm9ybWFsaXplZElkcyA9IGRlbGV0ZWRDYWxlbmRhcnM/Lm1hcCgoYykgPT5cbiAgICAgICAgICBjYWNoZS5pZGVudGlmeSh7IGlkOiBjLmlkLCBfX3R5cGVuYW1lOiBjLl9fdHlwZW5hbWUgfSlcbiAgICAgICAgKTtcbiAgICAgICAgbm9ybWFsaXplZElkcz8uZm9yRWFjaCgoaWQpID0+IGNhY2hlLmV2aWN0KHsgaWQgfSkpO1xuICAgICAgICBjYWNoZS5nYygpO1xuICAgICAgfSxcbiAgICB9KTtcblxuICAgIGNvbnNvbGUubG9nKGRhdGEsICcgc3VjY2Vzc2Z1bGx5IGRyb3BwZWQgcHJpbWFyeSBjYWxlbmRhcicpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZHJvcFByaW1hcnlDYWxlbmRhcicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZHJvcFByaW1hcnlMYWJlbEZvckNhbGVuZGFyID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBjYWxlbmRhcklkOiBzdHJpbmdcbik6IFByb21pc2U8dm9pZCB8IG51bGw+ID0+IHtcbiAgdHJ5IHtcbiAgICAvLyB2YWxpZGF0ZVxuICAgIGlmICghY2FsZW5kYXJJZCkge1xuICAgICAgY29uc29sZS5sb2coJ25vIGNhbGVuZGFySWQgaW5zaWRlIGRyb3BQcmltYXJ5TGFiZWxGb3JDYWxlbmRhcicpO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7XG4gICAgICB1cGRhdGVfQ2FsZW5kYXJfYnlfcGs6IENhbGVuZGFyVHlwZTtcbiAgICB9Pih7XG4gICAgICBtdXRhdGlvbjogdXBkYXRlQ2FsZW5kYXJEcm9wR2xvYmFsUHJpbWFyeSxcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICBpZDogY2FsZW5kYXJJZCxcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICBjb25zb2xlLmxvZyhkYXRhLCAnIHN1Y2Nlc3NmdWxseSBkcm9wcGVkIHByaW1hcnkgY2FsZW5kYXInKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGRyb3BQcmltYXJ5Q2FsZW5kYXInKTtcbiAgfVxufTtcbmV4cG9ydCBjb25zdCBzZXRQcmltYXJ5Q2FsZW5kYXIgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIGNhbGVuZGFyOiBDYWxlbmRhclR5cGVcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7XG4gICAgICB1cGRhdGVfQ2FsZW5kYXJfYnlfcGs6IENhbGVuZGFyVHlwZTtcbiAgICB9Pih7XG4gICAgICBtdXRhdGlvbjogdXBkYXRlQ2FsZW5kYXJUb0dsb2JhbFByaW1hcnksXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgaWQ6IGNhbGVuZGFyLmlkLFxuICAgICAgfSxcbiAgICB9KTtcblxuICAgIGNvbnNvbGUubG9nKCdzZXRQcmltYXJ5Q2FsZW5kYXInLCBkYXRhKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUuZXJyb3IoZSwgJyBzZXRQcmltYXJ5Q2FsZW5kYXInKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlRGVmYXVsdENhdGVnb3JpZXMgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHVzZXJJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBleGlzdGluZ0NhdGVnb3JpZXMgPSBhd2FpdCBsaXN0VXNlckNhdGVnb3JpZXMoY2xpZW50LCB1c2VySWQpO1xuXG4gICAgaWYgKGV4aXN0aW5nQ2F0ZWdvcmllcz8ubGVuZ3RoID09PSAwKSB7XG4gICAgICBERUZBVUxUQ0FURUdPUklFUy5mb3JFYWNoKGFzeW5jIChjYXRlZ29yeSkgPT4ge1xuICAgICAgICBhd2FpdCBjcmVhdGVDYXRlZ29yeShjbGllbnQsIGNhdGVnb3J5Py5uYW1lLCB1c2VySWQpO1xuICAgICAgfSk7XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5lcnJvcihlLCAnIGdlbmVyYXRlRGVmYXVsdENhdGVnb3JpZXMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldFVzZXJQcmVmZXJlbmNlID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICB1c2VySWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQucXVlcnk8e1xuICAgICAgVXNlcl9QcmVmZXJlbmNlOiBVc2VyUHJlZmVyZW5jZVR5cGVbXTtcbiAgICB9Pih7XG4gICAgICBxdWVyeTogZ2V0VXNlclByZWZlcmVuY2VGb3JVc2VyLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIHVzZXJJZCxcbiAgICAgIH0sXG4gICAgICBmZXRjaFBvbGljeTogJ25vLWNhY2hlJyxcbiAgICB9KTtcbiAgICBjb25zb2xlLmxvZyhkYXRhLCAnIGRhdGEgZ2V0VXNlclByZWZlcmVuY2UnKTtcbiAgICBpZiAoZGF0YT8uVXNlcl9QcmVmZXJlbmNlPy5sZW5ndGggPiAwKSB7XG4gICAgICBjb25zb2xlLmxvZyhkYXRhLlVzZXJfUHJlZmVyZW5jZVswXSwgJyBkYXRhLlVzZXJfUHJlZmVyZW5jZVswXScpO1xuICAgICAgcmV0dXJuIGRhdGEuVXNlcl9QcmVmZXJlbmNlWzBdO1xuICAgIH1cbiAgICByZXR1cm4gbnVsbDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUuZXJyb3IoZSwgJyBnZXRVc2VyUHJlZmVyZW5jZScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdXBkYXRlVXNlckZvclByZWZlcmVuY2VJZCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHByZWZlcmVuY2VJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IGRhdGEgfSA9IGF3YWl0IGNsaWVudC5tdXRhdGU8eyB1cGRhdGVfVXNlcl9ieV9wazogVXNlclR5cGUgfT4oe1xuICAgICAgbXV0YXRpb246IHVwZGF0ZVVzZXJGb3JVc2VyUHJlZmVyZW5jZUlkLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIGlkOiB1c2VySWQsXG4gICAgICAgIHVzZXJQcmVmZXJlbmNlSWQ6IHByZWZlcmVuY2VJZCxcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICBjb25zb2xlLmxvZygndXBkYXRlVXNlckZvclByZWZlcmVuY2VJZCcsIGRhdGEpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5lcnJvcihlLCAnIHVwZGF0ZVVzZXJGb3JQcmVmZXJlbmNlSWQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZVVzZXJQcmVmZXJlbmNlT25Cb2FyZGVkID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICB1c2VySWQ6IHN0cmluZyxcbiAgb25Cb2FyZGVkOiBib29sZWFuXG4pOiBQcm9taXNlPHZvaWQ+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IGRhdGEgfSA9IGF3YWl0IGNsaWVudC5tdXRhdGU8e1xuICAgICAgdXBkYXRlX1VzZXJfUHJlZmVyZW5jZToge1xuICAgICAgICBhZmZlY3RlZF9yb3dzOiBudW1iZXI7XG4gICAgICAgIHJldHVybmluZzogVXNlclByZWZlcmVuY2VUeXBlW107XG4gICAgICB9O1xuICAgIH0+KHtcbiAgICAgIG11dGF0aW9uOiB1cGRhdGVVc2VyUHJlZmVyZW5jZU9uQm9hcmRlZE11dGF0aW9uLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgb25Cb2FyZGVkLFxuICAgICAgfSxcbiAgICAgIC8vIHJlZmV0Y2hRdWVyaWVzOiBbXG4gICAgICAvLyAgICAgZ2V0VXNlclByZWZlcmVuY2VGb3JVc2VyLCAvLyBEb2N1bWVudE5vZGUgb2JqZWN0IHBhcnNlZCB3aXRoIGdxbFxuICAgICAgLy8gICAgICdnZXRVc2VyUHJlZmVyZW5jZUZvclVzZXInIC8vIFF1ZXJ5IG5hbWVcbiAgICAgIC8vIF0sXG4gICAgICB1cGRhdGUoY2FjaGUsIHsgZGF0YSB9KSB7XG4gICAgICAgIGlmIChkYXRhICYmIGRhdGE/LnVwZGF0ZV9Vc2VyX1ByZWZlcmVuY2U/LmFmZmVjdGVkX3Jvd3MgPiAwKSB7XG4gICAgICAgICAgY29uc29sZS5sb2coJ3VwZGF0ZVVzZXJQcmVmZXJlbmNlT25Cb2FyZGVkJywgZGF0YSk7XG4gICAgICAgIH1cblxuICAgICAgICBjYWNoZS5tb2RpZnkoe1xuICAgICAgICAgIGZpZWxkczoge1xuICAgICAgICAgICAgVXNlcl9QcmVmZXJlbmNlKGV4aXN0aW5nVXNlclByZWZlcmVuY2VzID0gW10pIHtcbiAgICAgICAgICAgICAgLy8gICAgIGNvbnN0IG5ld1VzZXJQcmVmZXJlbmNlUmVmID0gY2FjaGUud3JpdGVGcmFnbWVudCh7XG4gICAgICAgICAgICAgIC8vICAgICAgICAgZGF0YTogZGF0YT8udXBkYXRlX1VzZXJfUHJlZmVyZW5jZT8ucmV0dXJuaW5nPy5bMF0sXG4gICAgICAgICAgICAgIC8vICAgICAgICAgZnJhZ21lbnQ6IGdxbGBcbiAgICAgICAgICAgICAgLy8gICAgIGZyYWdtZW50IE5ld1VzZXJfUHJlZmVyZW5jZSBvbiBVc2VyX1ByZWZlcmVuY2Uge1xuICAgICAgICAgICAgICAvLyAgICAgICAgIGlkXG4gICAgICAgICAgICAgIC8vICAgICAgICAgb25Cb2FyZGVkXG4gICAgICAgICAgICAgIC8vICAgICB9XG4gICAgICAgICAgICAgIC8vICAgYFxuICAgICAgICAgICAgICAvLyAgICAgfSk7XG4gICAgICAgICAgICAgIHJldHVybiBbXG4gICAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgICAgLi4uZXhpc3RpbmdVc2VyUHJlZmVyZW5jZXM/LlswXSxcbiAgICAgICAgICAgICAgICAgIG9uQm9hcmRlZDpcbiAgICAgICAgICAgICAgICAgICAgZGF0YT8udXBkYXRlX1VzZXJfUHJlZmVyZW5jZT8ucmV0dXJuaW5nPy5bMF0/Lm9uQm9hcmRlZCxcbiAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICBdO1xuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9LFxuICAgICAgICB9KTtcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICBjb25zb2xlLmxvZygndXBkYXRlVXNlclByZWZlcmVuY2VPbkJvYXJkZWQnLCBkYXRhKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgZXJyb3IgaW4gdXBkYXRlVXNlclByZWZlcmVuY2VPbmJvYXJkZWQnKTtcbiAgfVxufTtcbmV4cG9ydCBjb25zdCBjcmVhdGVVc2VyUHJlZmVyZW5jZSA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGV4aXN0aW5ndXNlcl9wcmVmZXJlbmNlID0gYXdhaXQgZ2V0VXNlclByZWZlcmVuY2UoY2xpZW50LCB1c2VySWQpO1xuICAgIGNvbnN0IGlkID0gdXVpZCgpO1xuICAgIGlmICghZXhpc3Rpbmd1c2VyX3ByZWZlcmVuY2UpIHtcbiAgICAgIGNvbnN0IHVzZXJQcmVmZXJlbmNlVmFsdWVzID0ge1xuICAgICAgICBpZCxcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICAgIG1heFdvcmtMb2FkUGVyY2VudDogODUsXG4gICAgICAgIGJhY2tUb0JhY2tNZWV0aW5nczogZmFsc2UsXG4gICAgICAgIG1pbk51bWJlck9mQnJlYWtzOiAxLFxuICAgICAgICBtYXhOdW1iZXJPZk1lZXRpbmdzOiA0LFxuICAgICAgICBicmVha0xlbmd0aDogMTUsXG4gICAgICAgIHN0YXJ0VGltZXM6IFNUQVJUVElNRVMsXG4gICAgICAgIGVuZFRpbWVzOiBFTkRUSU1FUyxcbiAgICAgICAgYnJlYWtDb2xvcjogcGFsZXR0ZS5ncmVlblByaW1hcnksXG4gICAgICAgIG9uQm9hcmRlZDogZmFsc2UsXG4gICAgICAgIGNvcHlBdmFpbGFiaWxpdHk6IHRydWUsXG4gICAgICAgIGNvcHlUaW1lQmxvY2tpbmc6IHRydWUsXG4gICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZTogdHJ1ZSxcbiAgICAgICAgY29weVJlbWluZGVyczogdHJ1ZSxcbiAgICAgICAgY29weVByaW9yaXR5TGV2ZWw6IHRydWUsXG4gICAgICAgIGNvcHlNb2RpZmlhYmxlOiB0cnVlLFxuICAgICAgICBjb3B5Q2F0ZWdvcmllczogdHJ1ZSxcbiAgICAgICAgY29weUlzQnJlYWs6IHRydWUsXG4gICAgICAgIGNvcHlJc01lZXRpbmc6IHRydWUsXG4gICAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZzogdHJ1ZSxcbiAgICAgICAgY29weUNvbG9yOiB0cnVlLFxuICAgICAgfTtcblxuICAgICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQubXV0YXRlPHtcbiAgICAgICAgaW5zZXJ0X1VzZXJfUHJlZmVyZW5jZV9vbmU6IFVzZXJQcmVmZXJlbmNlVHlwZTtcbiAgICAgIH0+KHtcbiAgICAgICAgbXV0YXRpb246IHVwc2VydFVzZXJQcmVmZXJlbmNlLFxuICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICB1c2VyUHJlZmVyZW5jZTogdXNlclByZWZlcmVuY2VWYWx1ZXMsXG4gICAgICAgIH0sXG4gICAgICB9KTtcblxuICAgICAgYXdhaXQgdXBkYXRlVXNlckZvclByZWZlcmVuY2VJZChjbGllbnQsIHVzZXJJZCwgaWQpO1xuXG4gICAgICBjb25zb2xlLmxvZygnY3JlYXRlVXNlclByZWZlcmVuY2UnLCBkYXRhKTtcbiAgICB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmVycm9yKGUsICcgY3JlYXRldXNlcl9wcmVmZXJlbmNlJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBjcmVhdGVEZWZhdWx0UHJpbWFyeUNhbGVuZGFyID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICB1c2VySWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgZXhpc3RpbmdDYWxlbmRhciA9IChcbiAgICAgIGF3YWl0IGNsaWVudC5xdWVyeTx7IENhbGVuZGFyOiBDYWxlbmRhclR5cGVbXSB9Pih7XG4gICAgICAgIHF1ZXJ5OiBnZXRHbG9iYWxQcmltYXJ5Q2FsZW5kYXIsXG4gICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgKS5kYXRhPy5DYWxlbmRhcj8uWzBdO1xuXG4gICAgaWYgKCFleGlzdGluZ0NhbGVuZGFyKSB7XG4gICAgICAvLyBtYWtlIGFueSBjYWxlbmRhciB0aGUgcHJpbWFyeVxuICAgICAgY29uc3QgY2FsZW5kYXJEb2MgPSAoXG4gICAgICAgIGF3YWl0IGNsaWVudC5xdWVyeTx7IENhbGVuZGFyOiBDYWxlbmRhclR5cGVbXSB9Pih7XG4gICAgICAgICAgcXVlcnk6IGdldEFueUNhbGVuZGFyLFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pXG4gICAgICApLmRhdGE/LkNhbGVuZGFyPy5bMF07XG5cbiAgICAgIGlmIChjYWxlbmRhckRvYykge1xuICAgICAgICBhd2FpdCBjbGllbnQubXV0YXRlPHsgdXBkYXRlX0NhbGVuZGFyX2J5X3BrOiBDYWxlbmRhclR5cGUgfT4oe1xuICAgICAgICAgIG11dGF0aW9uOiB1cGRhdGVDYWxlbmRhclRvR2xvYmFsUHJpbWFyeSxcbiAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIGlkOiBjYWxlbmRhckRvYz8uaWQsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSk7XG4gICAgICB9XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5lcnJvcihlLCAnIGNyZWF0ZURlZmF1bHRQcmltYXJ5Q2FsZW5kYXInKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGNyZWF0ZURlZmF1bHRVc2VyID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICB1c2VySWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgZXhpc3RpbmdVc2VyID0gKFxuICAgICAgYXdhaXQgY2xpZW50LnF1ZXJ5PHsgVXNlcl9ieV9wazogVXNlclR5cGUgfT4oe1xuICAgICAgICBxdWVyeTogZ2V0VXNlckJ5SWQsXG4gICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgIGlkOiB1c2VySWQsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICk/LmRhdGE/LlVzZXJfYnlfcGs7XG5cbiAgICBpZiAoIWV4aXN0aW5nVXNlcikge1xuICAgICAgY29uc3QgdXNlckluZm8gPSBhd2FpdCBUaGlyZFBhcnR5RW1haWxQYXNzd29yZC5nZXRVc2VyQnlJZCh1c2VySWQpO1xuICAgICAgY29uc3QgZW1haWwgPSB1c2VySW5mbz8uZW1haWw7XG4gICAgICBjb25zdCB2YWx1ZXNUb1Vwc2VydCA9IHtcbiAgICAgICAgaWQ6IHVzZXJJZCxcbiAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgICBlbWFpbCxcbiAgICAgICAgbmFtZTogdXNlckluZm9zPy5uYW1lIHx8ICcnLFxuICAgICAgfTtcbiAgICAgIGF3YWl0IGNsaWVudC5tdXRhdGU8eyBpbnNlcnRfVXNlcl9vbmU6IFVzZXJUeXBlIH0+KHtcbiAgICAgICAgbXV0YXRpb246IHVwc2VydFVzZXIsXG4gICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgIHVzZXI6IHZhbHVlc1RvVXBzZXJ0LFxuICAgICAgICB9LFxuICAgICAgfSk7XG4gICAgICBjb25zb2xlLmxvZygnY3JlYXRlRGVmYXVsdFVzZXInLCB2YWx1ZXNUb1Vwc2VydCk7XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5lcnJvcihlLCAnIGNyZWF0ZURlZmF1bHRVc2VyJyk7XG4gIH1cbn07XG5cbi8vIGNyZWF0ZSBpbml0aWFsIHNlbGVjdGVkIGNhbGVuZGFyXG5leHBvcnQgY29uc3QgY3JlYXRlSW5pdGlhbFNlbGVjdGVkQ2FsZW5kYXIgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHVzZXJJZDogc3RyaW5nLFxuICBzZXRTZWxlY3RlZENhbGVuZGFyOiBEaXNwYXRjaDxzdHJpbmc+XG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBleGlzdGluZ0NhbGVuZGFyID0gKFxuICAgICAgYXdhaXQgY2xpZW50LnF1ZXJ5PHsgQ2FsZW5kYXI6IENhbGVuZGFyVHlwZVtdIH0+KHtcbiAgICAgICAgcXVlcnk6IGdldEdsb2JhbFByaW1hcnlDYWxlbmRhcixcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICApLmRhdGE/LkNhbGVuZGFyPy5bMF07XG5cbiAgICBpZiAoIWV4aXN0aW5nQ2FsZW5kYXIpIHtcbiAgICAgIGNvbnN0IG9sZENhbGVuZGFyRG9jID0gKFxuICAgICAgICBhd2FpdCBjbGllbnQucXVlcnk8eyBDYWxlbmRhcjogQ2FsZW5kYXJUeXBlW10gfT4oe1xuICAgICAgICAgIHF1ZXJ5OiBnZXRBbnlDYWxlbmRhcixcbiAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICB9LFxuICAgICAgICB9KVxuICAgICAgKS5kYXRhPy5DYWxlbmRhcj8uWzBdO1xuXG4gICAgICBpZiAob2xkQ2FsZW5kYXJEb2MpIHtcbiAgICAgICAgYXdhaXQgY2xpZW50Lm11dGF0ZTx7IHVwZGF0ZV9DYWxlbmRhcl9ieV9wazogQ2FsZW5kYXJUeXBlIH0+KHtcbiAgICAgICAgICBtdXRhdGlvbjogdXBkYXRlQ2FsZW5kYXJUb0dsb2JhbFByaW1hcnksXG4gICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICBpZDogb2xkQ2FsZW5kYXJEb2M/LmlkLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pO1xuICAgICAgICBzZXRTZWxlY3RlZENhbGVuZGFyKG9sZENhbGVuZGFyRG9jPy5pZCk7XG4gICAgICB9XG4gICAgfSBlbHNlIHtcbiAgICAgIHNldFNlbGVjdGVkQ2FsZW5kYXIoZXhpc3RpbmdDYWxlbmRhcj8uaWQpO1xuICAgIH1cbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUuZXJyb3IoZSwgJyBjcmVhdGVJbml0aWFsU2VsZWN0ZWRDYWxlbmRhcicpO1xuICB9XG59O1xuIl19