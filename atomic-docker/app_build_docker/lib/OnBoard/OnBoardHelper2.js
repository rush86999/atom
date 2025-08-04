"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createInitialSelectedCalendar = exports.createDefaultUser = exports.createDefaultPrimaryCalendar = exports.createUserPreference = exports.updateUserPreferenceOnBoarded = exports.updateUserForPreferenceId = exports.getUserPreference = exports.generateDefaultCategories = exports.setPrimaryCalendar = exports.dropPrimaryLabelForCalendar = exports.dropPrimaryLabelForCalendars = exports.listEventsForCalendar = void 0;
const uuid_1 = require("uuid");
const date_utils_1 = require("@lib/date-utils");
const theme_1 = require("@lib/theme/theme");
const updateCalendarToGlobalPrimary_1 = __importDefault(require("@lib/apollo/gql/updateCalendarToGlobalPrimary"));
const CategoryHelper_1 = require("@lib/Category/CategoryHelper");
// import getUserPreferenceForUser from '@lib/apollo/gql/getUserPreferenceForUser'
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
                const normalizedIds = deletedCalendars.map((c) => cache.identify({ id: c.id, __typename: c.__typename }));
                normalizedIds.forEach((id) => cache.evict({ id }));
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
        if (existingCategories.length === 0) {
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
                if (data?.update_User_Preference?.affected_rows > 0) {
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
                maxNumberOfMeetings: 10,
                breakLength: 30,
                startTimes: STARTTIMES,
                endTimes: ENDTIMES,
                breakColor: theme_1.palette.greenPrimary,
                onBoarded: false,
                copyAvailability: true,
                copyTimeBlocking: true,
                copyTimePreference: true,
                copyReminders: true,
                copyPriorityLevel: false,
                copyModifiable: false,
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
const createDefaultUser = async (client, userId, email, name) => {
    try {
        const existingUser = (await client.query({
            query: getUserById_1.default,
            variables: {
                id: userId,
            },
        }))?.data?.User_by_pk;
        if (!existingUser) {
            const valuesToUpsert = {
                id: userId,
                createdDate: (0, date_utils_1.dayjs)().toISOString(),
                updatedAt: (0, date_utils_1.dayjs)().toISOString(),
                deleted: false,
                email,
                name: email,
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiT25Cb2FyZEhlbHBlcjIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJPbkJvYXJkSGVscGVyMi50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7QUFDQSwrQkFBa0M7QUFHbEMsZ0RBQXdDO0FBRXhDLDRDQUEyQztBQVczQyxrSEFBMEY7QUFDMUYsaUVBR3NDO0FBQ3RDLGtGQUFrRjtBQUNsRixnR0FBd0U7QUFDeEUsd0dBQWdGO0FBQ2hGLG9GQUE0RDtBQUU1RCw4RUFBc0Q7QUFDdEQsNEVBQW9EO0FBQ3BELGtIQUEwRjtBQUcxRixzR0FBOEU7QUFDOUUsa0lBQTBHO0FBQzFHLHNIQUE4RjtBQUM5Rix3R0FBZ0Y7QUFDaEYsd0hBQWdHO0FBRWhHLE1BQU0saUJBQWlCLEdBQW1CO0lBQ3hDO1FBQ0UsRUFBRSxFQUFFLElBQUEsU0FBSSxHQUFFO1FBQ1YsSUFBSSxFQUFFLGtCQUFrQjtRQUN4QixXQUFXLEVBQUUsSUFBQSxrQkFBSyxHQUFFLENBQUMsV0FBVyxFQUFFO1FBQ2xDLFNBQVMsRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxXQUFXLEVBQUU7UUFDaEMsT0FBTyxFQUFFLEtBQUs7UUFDZCxNQUFNLEVBQUUsRUFBRTtLQUNYO0lBQ0Q7UUFDRSxFQUFFLEVBQUUsSUFBQSxTQUFJLEdBQUU7UUFDVixJQUFJLEVBQUUsU0FBUztRQUNmLFdBQVcsRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxXQUFXLEVBQUU7UUFDbEMsU0FBUyxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLFdBQVcsRUFBRTtRQUNoQyxPQUFPLEVBQUUsS0FBSztRQUNkLE1BQU0sRUFBRSxFQUFFO0tBQ1g7SUFDRDtRQUNFLEVBQUUsRUFBRSxJQUFBLFNBQUksR0FBRTtRQUNWLElBQUksRUFBRSxnQkFBZ0I7UUFDdEIsV0FBVyxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLFdBQVcsRUFBRTtRQUNsQyxTQUFTLEVBQUUsSUFBQSxrQkFBSyxHQUFFLENBQUMsV0FBVyxF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QixNQUFNLE1BQU0sQ0FBQyxNQUFNLENBQTBDO29CQUMzRCxRQUFRLEVBQUUsdUNBQTZCO29CQUN2QyxTQUFTLEVBQUU7d0JBQ1QsRUFBRSxFQUFFLGNBQWMsRUFBRSxFQUFFO3FCQUN2QjtpQkFDRixDQUFDLENBQUM7Z0JBQ0gsbUJBQW1CLENBQUMsY0FBYyxFQUFFLEVBQUUsQ0FBQyxDQUFDO1lBQzFDLENBQUM7UUFDSCxDQUFDO2FBQU0sQ0FBQztZQUNOLG1CQUFtQixDQUFDLGdCQUFnQixFQUFFLEVBQUUsQ0FBQyxDQUFDO1FBQzVDLENBQUM7SUFDSCxDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxLQUFLLENBQUMsQ0FBQyxFQUFFLGdDQUFnQyxDQUFDLENBQUM7SUFDckQsQ0FBQztBQUNILENBQUMsQ0FBQztBQXhDVyxRQUFBLDZCQUE2QixpQ0F3Q3hDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IF8gZnJvbSAnbG9kYXNoJztcbmltcG9ydCB7IHY0IGFzIHV1aWQgfSBmcm9tICd1dWlkJztcbmltcG9ydCB7IERpc3BhdGNoIH0gZnJvbSAncmVhY3QnO1xuXG5pbXBvcnQgeyBkYXlqcyB9IGZyb20gJ0BsaWIvZGF0ZS11dGlscyc7XG5cbmltcG9ydCB7IHBhbGV0dGUgfSBmcm9tICdAbGliL3RoZW1lL3RoZW1lJztcbmltcG9ydCB7IENhbGVuZGFyVHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL0NhbGVuZGFyVHlwZSc7XG5pbXBvcnQgeyBDYXRlZ29yeVR5cGUgfSBmcm9tICdAbGliL2RhdGFUeXBlcy9DYXRlZ29yeVR5cGUnO1xuaW1wb3J0IHtcbiAgRW5kVGltZVR5cGUsXG4gIFN0YXJ0VGltZVR5cGUsXG4gIFVzZXJQcmVmZXJlbmNlVHlwZSxcbn0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvVXNlcl9QcmVmZXJlbmNlVHlwZSc7XG5pbXBvcnQgVGhpcmRQYXJ0eUVtYWlsUGFzc3dvcmQgZnJvbSAnc3VwZXJ0b2tlbnMtd2ViLWpzL3JlY2lwZS90aGlyZHBhcnR5ZW1haWxwYXNzd29yZCc7XG5pbXBvcnQgeyBsb2NhbENhbGVuZGFyUmVzb3VyY2UgfSBmcm9tICdAbGliL2NhbGVuZGFyTGliL2NvbnN0YW50cyc7XG5pbXBvcnQgeyBBcG9sbG9DbGllbnQsIE5vcm1hbGl6ZWRDYWNoZU9iamVjdCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcbmltcG9ydCB1cGRhdGVDYWxlbmRhclRvR2xvYmFsUHJpbWFyeSBmcm9tICdAbGliL2Fwb2xsby9ncWwvdXBkYXRlQ2FsZW5kYXJUb0dsb2JhbFByaW1hcnknO1xuaW1wb3J0IHtcbiAgY3JlYXRlQ2F0ZWdvcnksXG4gIGxpc3RVc2VyQ2F0ZWdvcmllcyxcbn0gZnJvbSAnQGxpYi9DYXRlZ29yeS9DYXRlZ29yeUhlbHBlcic7XG4vLyBpbXBvcnQgZ2V0VXNlclByZWZlcmVuY2VGb3JVc2VyIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9nZXRVc2VyUHJlZmVyZW5jZUZvclVzZXInXG5pbXBvcnQgdXBzZXJ0VXNlclByZWZlcmVuY2UgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL3Vwc2VydFVzZXJQcmVmZXJlbmNlJztcbmltcG9ydCBnZXRHbG9iYWxQcmltYXJ5Q2FsZW5kYXIgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2dldEdsb2JhbFByaW1hcnlDYWxlbmRhcic7XG5pbXBvcnQgZ2V0QW55Q2FsZW5kYXIgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2dldEFueUNhbGVuZGFyJztcbmltcG9ydCB7IFVzZXJUeXBlIH0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvVXNlclR5cGUnO1xuaW1wb3J0IGdldFVzZXJCeUlkIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9nZXRVc2VyQnlJZCc7XG5pbXBvcnQgdXBzZXJ0VXNlciBmcm9tICdAbGliL2Fwb2xsby9ncWwvdXBzZXJ0VXNlcic7XG5pbXBvcnQgdXBkYXRlVXNlckZvclVzZXJQcmVmZXJlbmNlSWQgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL3VwZGF0ZVVzZXJGb3JVc2VyUHJlZmVyZW5jZUlkJztcbmltcG9ydCB1cHNlcnRDYWxlbmRhciBmcm9tICdAbGliL2Fwb2xsby9ncWwvdXBzZXJ0Q2FsZW5kYXInO1xuaW1wb3J0IHsgRXZlbnRUeXBlIH0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvRXZlbnRUeXBlJztcbmltcG9ydCBsaXN0RXZlbnRzRm9yQ2FsZW5kYXJJZCBmcm9tICdAbGliL2Fwb2xsby9ncWwvbGlzdEV2ZW50c0ZvckNhbGVuZGFySWQnO1xuaW1wb3J0IHVwZGF0ZVVzZXJQcmVmZXJlbmNlT25Cb2FyZGVkTXV0YXRpb24gZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL3VwZGF0ZVVzZXJQcmVmZXJlbmNlT25Cb2FyZGVkTXV0YXRpb24nO1xuaW1wb3J0IHVwZGF0ZUNhbGVuZGFyRHJvcEdsb2JhbFByaW1hcnkgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL3VwZGF0ZUNhbGVuZGFyRHJvcEdsb2JhbFByaW1hcnknO1xuaW1wb3J0IGdldFVzZXJQcmVmZXJlbmNlRm9yVXNlciBmcm9tICdAbGliL2Fwb2xsby9ncWwvZ2V0VXNlclByZWZlcmVuY2VGb3JVc2VyJztcbmltcG9ydCB1cGRhdGVDYWxlbmRhcnNEcm9wR2xvYmFsUHJpbWFyeSBmcm9tICdAbGliL2Fwb2xsby9ncWwvdXBkYXRlQ2FsZW5kYXJzRHJvcEdsb2JhbFByaW1hcnknO1xuXG5jb25zdCBERUZBVUxUQ0FURUdPUklFUzogQ2F0ZWdvcnlUeXBlW10gPSBbXG4gIHtcbiAgICBpZDogdXVpZCgpLFxuICAgIG5hbWU6ICdFeHRlcm5hbCBNZWV0aW5nJyxcbiAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgIHVzZXJJZDogJycsXG4gIH0sXG4gIHtcbiAgICBpZDogdXVpZCgpLFxuICAgIG5hbWU6ICdNZWV0aW5nJyxcbiAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgIHVzZXJJZDogJycsXG4gIH0sXG4gIHtcbiAgICBpZDogdXVpZCgpLFxuICAgIG5hbWU6ICdMaWZlIE1pbGVzdG9uZScsXG4gICAgY3JlYXRlZERhdGU6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICBkZWxldGVkOiBmYWxzZSxcbiAgICB1c2VySWQ6ICcnLFxuICB9LFxuICB7XG4gICAgaWQ6IHV1aWQoKSxcbiAgICBuYW1lOiAnU3BvcnRzJyxcbiAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgIHVzZXJJZDogJycsXG4gIH0sXG4gIHtcbiAgICBpZDogdXVpZCgpLFxuICAgIG5hbWU6ICdTb2NpYWwgTWVldHVwJyxcbiAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgIHVzZXJJZDogJycsXG4gIH0sXG4gIHtcbiAgICBpZDogdXVpZCgpLFxuICAgIG5hbWU6ICdCcmVhaycsXG4gICAgY3JlYXRlZERhdGU6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICBkZWxldGVkOiBmYWxzZSxcbiAgICB1c2VySWQ6ICcnLFxuICB9LFxuXTtcblxuY29uc3QgU1RBUlRUSU1FUzogU3RhcnRUaW1lVHlwZVtdID0gW1xuICB7XG4gICAgZGF5OiAxLFxuICAgIGhvdXI6IDcsXG4gICAgbWludXRlczogMCxcbiAgfSxcbiAge1xuICAgIGRheTogMixcbiAgICBob3VyOiA3LFxuICAgIG1pbnV0ZXM6IDAsXG4gIH0sXG4gIHtcbiAgICBkYXk6IDMsXG4gICAgaG91cjogNyxcbiAgICBtaW51dGVzOiAwLFxuICB9LFxuICB7XG4gICAgZGF5OiA0LFxuICAgIGhvdXI6IDcsXG4gICAgbWludXRlczogMCxcbiAgfSxcbiAge1xuICAgIGRheTogNSxcbiAgICBob3VyOiA3LFxuICAgIG1pbnV0ZXM6IDAsXG4gIH0sXG4gIHtcbiAgICBkYXk6IDYsXG4gICAgaG91cjogNyxcbiAgICBtaW51dGVzOiAwLFxuICB9LFxuICB7XG4gICAgZGF5OiA3LFxuICAgIGhvdXI6IDcsXG4gICAgbWludXRlczogMCxcbiAgfSxcbl07XG5cbmNvbnN0IEVORFRJTUVTOiBFbmRUaW1lVHlwZVtdID0gW1xuICB7XG4gICAgZGF5OiAxLFxuICAgIGhvdXI6IDE5LFxuICAgIG1pbnV0ZXM6IDAsXG4gIH0sXG4gIHtcbiAgICBkYXk6IDIsXG4gICAgaG91cjogMTksXG4gICAgbWludXRlczogMCxcbiAgfSxcbiAge1xuICAgIGRheTogMyxcbiAgICBob3VyOiAxOSxcbiAgICBtaW51dGVzOiAwLFxuICB9LFxuICB7XG4gICAgZGF5OiA0LFxuICAgIGhvdXI6IDE5LFxuICAgIG1pbnV0ZXM6IDAsXG4gIH0sXG4gIHtcbiAgICBkYXk6IDUsXG4gICAgaG91cjogMTksXG4gICAgbWludXRlczogMCxcbiAgfSxcbiAge1xuICAgIGRheTogNixcbiAgICBob3VyOiAxOSxcbiAgICBtaW51dGVzOiAwLFxuICB9LFxuICB7XG4gICAgZGF5OiA3LFxuICAgIGhvdXI6IDE5LFxuICAgIG1pbnV0ZXM6IDAsXG4gIH0sXG5dO1xuXG5leHBvcnQgY29uc3QgbGlzdEV2ZW50c0ZvckNhbGVuZGFyID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBjYWxlbmRhcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50LnF1ZXJ5PHtcbiAgICAgIEV2ZW50OiBFdmVudFR5cGVbXTtcbiAgICB9Pih7XG4gICAgICBxdWVyeTogbGlzdEV2ZW50c0ZvckNhbGVuZGFySWQsXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgY2FsZW5kYXJJZCxcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICBjb25zb2xlLmxvZyhkYXRhLCAnIHN1Y2Nlc3NmdWxseSBsaXN0ZWQgZXZlbnRzIGZvciBDYWxlbmRhcicpO1xuICAgIHJldHVybiBkYXRhPy5FdmVudDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGxpc3RFdmVudHNGb3JDYWxlbmRhcicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZHJvcFByaW1hcnlMYWJlbEZvckNhbGVuZGFycyA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgY2FsZW5kYXJJZHM6IHN0cmluZ1tdXG4pOiBQcm9taXNlPHZvaWQgfCBudWxsPiA9PiB7XG4gIHRyeSB7XG4gICAgLy8gdmFsaWRhdGVcbiAgICBpZiAoIShjYWxlbmRhcklkcz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdubyBjYWxlbmRhcklkcyBpbnNpZGUgZHJvcFByaW1hcnlMYWJsZUZvckNhbGVuZGFycycpO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7XG4gICAgICB1cGRhdGVfQ2FsZW5kYXI6IHsgYWZmZWN0ZWRfcm93czogbnVtYmVyOyByZXR1cm5pbmc6IENhbGVuZGFyVHlwZVtdIH07XG4gICAgfT4oe1xuICAgICAgbXV0YXRpb246IHVwZGF0ZUNhbGVuZGFyc0Ryb3BHbG9iYWxQcmltYXJ5LFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIGlkczogY2FsZW5kYXJJZHMsXG4gICAgICB9LFxuICAgICAgdXBkYXRlKGNhY2hlLCB7IGRhdGEgfSkge1xuICAgICAgICBjb25zdCBkZWxldGVkQ2FsZW5kYXJzID0gZGF0YT8udXBkYXRlX0NhbGVuZGFyPy5yZXR1cm5pbmc7XG4gICAgICAgIGNvbnN0IG5vcm1hbGl6ZWRJZHMgPSBkZWxldGVkQ2FsZW5kYXJzLm1hcCgoYykgPT5cbiAgICAgICAgICBjYWNoZS5pZGVudGlmeSh7IGlkOiBjLmlkLCBfX3R5cGVuYW1lOiBjLl9fdHlwZW5hbWUgfSlcbiAgICAgICAgKTtcbiAgICAgICAgbm9ybWFsaXplZElkcy5mb3JFYWNoKChpZCkgPT4gY2FjaGUuZXZpY3QoeyBpZCB9KSk7XG4gICAgICAgIGNhY2hlLmdjKCk7XG4gICAgICB9LFxuICAgIH0pO1xuXG4gICAgY29uc29sZS5sb2coZGF0YSwgJyBzdWNjZXNzZnVsbHkgZHJvcHBlZCBwcmltYXJ5IGNhbGVuZGFyJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBkcm9wUHJpbWFyeUNhbGVuZGFyJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBkcm9wUHJpbWFyeUxhYmVsRm9yQ2FsZW5kYXIgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIGNhbGVuZGFySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTx2b2lkIHwgbnVsbD4gPT4ge1xuICB0cnkge1xuICAgIC8vIHZhbGlkYXRlXG4gICAgaWYgKCFjYWxlbmRhcklkKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gY2FsZW5kYXJJZCBpbnNpZGUgZHJvcFByaW1hcnlMYWJlbEZvckNhbGVuZGFyJyk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQubXV0YXRlPHtcbiAgICAgIHVwZGF0ZV9DYWxlbmRhcl9ieV9wazogQ2FsZW5kYXJUeXBlO1xuICAgIH0+KHtcbiAgICAgIG11dGF0aW9uOiB1cGRhdGVDYWxlbmRhckRyb3BHbG9iYWxQcmltYXJ5LFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIGlkOiBjYWxlbmRhcklkLFxuICAgICAgfSxcbiAgICB9KTtcblxuICAgIGNvbnNvbGUubG9nKGRhdGEsICcgc3VjY2Vzc2Z1bGx5IGRyb3BwZWQgcHJpbWFyeSBjYWxlbmRhcicpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZHJvcFByaW1hcnlDYWxlbmRhcicpO1xuICB9XG59O1xuZXhwb3J0IGNvbnN0IHNldFByaW1hcnlDYWxlbmRhciA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgY2FsZW5kYXI6IENhbGVuZGFyVHlwZVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQubXV0YXRlPHtcbiAgICAgIHVwZGF0ZV9DYWxlbmRhcl9ieV9wazogQ2FsZW5kYXJUeXBlO1xuICAgIH0+KHtcbiAgICAgIG11dGF0aW9uOiB1cGRhdGVDYWxlbmRhclRvR2xvYmFsUHJpbWFyeSxcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICBpZDogY2FsZW5kYXIuaWQsXG4gICAgICB9LFxuICAgIH0pO1xuXG4gICAgY29uc29sZS5sb2coJ3NldFByaW1hcnlDYWxlbmRhcicsIGRhdGEpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5lcnJvcihlLCAnIHNldFByaW1hcnlDYWxlbmRhcicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVEZWZhdWx0Q2F0ZWdvcmllcyA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGV4aXN0aW5nQ2F0ZWdvcmllcyA9IGF3YWl0IGxpc3RVc2VyQ2F0ZWdvcmllcyhjbGllbnQsIHVzZXJJZCk7XG5cbiAgICBpZiAoZXhpc3RpbmdDYXRlZ29yaWVzLmxlbmd0aCA9PT0gMCkge1xuICAgICAgREVGQVVMVENBVEVHT1JJRVMuZm9yRWFjaChhc3luYyAoY2F0ZWdvcnkpID0+IHtcbiAgICAgICAgYXdhaXQgY3JlYXRlQ2F0ZWdvcnkoY2xpZW50LCBjYXRlZ29yeT8ubmFtZSwgdXNlcklkKTtcbiAgICAgIH0pO1xuICAgIH1cbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUuZXJyb3IoZSwgJyBnZW5lcmF0ZURlZmF1bHRDYXRlZ29yaWVzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRVc2VyUHJlZmVyZW5jZSA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50LnF1ZXJ5PHtcbiAgICAgIFVzZXJfUHJlZmVyZW5jZTogVXNlclByZWZlcmVuY2VUeXBlW107XG4gICAgfT4oe1xuICAgICAgcXVlcnk6IGdldFVzZXJQcmVmZXJlbmNlRm9yVXNlcixcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICB1c2VySWQsXG4gICAgICB9LFxuICAgICAgZmV0Y2hQb2xpY3k6ICduby1jYWNoZScsXG4gICAgfSk7XG4gICAgY29uc29sZS5sb2coZGF0YSwgJyBkYXRhIGdldFVzZXJQcmVmZXJlbmNlJyk7XG4gICAgaWYgKGRhdGE/LlVzZXJfUHJlZmVyZW5jZT8ubGVuZ3RoID4gMCkge1xuICAgICAgY29uc29sZS5sb2coZGF0YS5Vc2VyX1ByZWZlcmVuY2VbMF0sICcgZGF0YS5Vc2VyX1ByZWZlcmVuY2VbMF0nKTtcbiAgICAgIHJldHVybiBkYXRhLlVzZXJfUHJlZmVyZW5jZVswXTtcbiAgICB9XG4gICAgcmV0dXJuIG51bGw7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmVycm9yKGUsICcgZ2V0VXNlclByZWZlcmVuY2UnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZVVzZXJGb3JQcmVmZXJlbmNlSWQgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHVzZXJJZDogc3RyaW5nLFxuICBwcmVmZXJlbmNlSWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQubXV0YXRlPHsgdXBkYXRlX1VzZXJfYnlfcGs6IFVzZXJUeXBlIH0+KHtcbiAgICAgIG11dGF0aW9uOiB1cGRhdGVVc2VyRm9yVXNlclByZWZlcmVuY2VJZCxcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICBpZDogdXNlcklkLFxuICAgICAgICB1c2VyUHJlZmVyZW5jZUlkOiBwcmVmZXJlbmNlSWQsXG4gICAgICB9LFxuICAgIH0pO1xuXG4gICAgY29uc29sZS5sb2coJ3VwZGF0ZVVzZXJGb3JQcmVmZXJlbmNlSWQnLCBkYXRhKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUuZXJyb3IoZSwgJyB1cGRhdGVVc2VyRm9yUHJlZmVyZW5jZUlkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCB1cGRhdGVVc2VyUHJlZmVyZW5jZU9uQm9hcmRlZCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmcsXG4gIG9uQm9hcmRlZDogYm9vbGVhblxuKTogUHJvbWlzZTx2b2lkPiA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQubXV0YXRlPHtcbiAgICAgIHVwZGF0ZV9Vc2VyX1ByZWZlcmVuY2U6IHtcbiAgICAgICAgYWZmZWN0ZWRfcm93czogbnVtYmVyO1xuICAgICAgICByZXR1cm5pbmc6IFVzZXJQcmVmZXJlbmNlVHlwZVtdO1xuICAgICAgfTtcbiAgICB9Pih7XG4gICAgICBtdXRhdGlvbjogdXBkYXRlVXNlclByZWZlcmVuY2VPbkJvYXJkZWRNdXRhdGlvbixcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICB1c2VySWQsXG4gICAgICAgIG9uQm9hcmRlZCxcbiAgICAgIH0sXG4gICAgICAvLyByZWZldGNoUXVlcmllczogW1xuICAgICAgLy8gICAgIGdldFVzZXJQcmVmZXJlbmNlRm9yVXNlciwgLy8gRG9jdW1lbnROb2RlIG9iamVjdCBwYXJzZWQgd2l0aCBncWxcbiAgICAgIC8vICAgICAnZ2V0VXNlclByZWZlcmVuY2VGb3JVc2VyJyAvLyBRdWVyeSBuYW1lXG4gICAgICAvLyBdLFxuICAgICAgdXBkYXRlKGNhY2hlLCB7IGRhdGEgfSkge1xuICAgICAgICBpZiAoZGF0YT8udXBkYXRlX1VzZXJfUHJlZmVyZW5jZT8uYWZmZWN0ZWRfcm93cyA+IDApIHtcbiAgICAgICAgICBjb25zb2xlLmxvZygndXBkYXRlVXNlclByZWZlcmVuY2VPbkJvYXJkZWQnLCBkYXRhKTtcbiAgICAgICAgfVxuXG4gICAgICAgIGNhY2hlLm1vZGlmeSh7XG4gICAgICAgICAgZmllbGRzOiB7XG4gICAgICAgICAgICBVc2VyX1ByZWZlcmVuY2UoZXhpc3RpbmdVc2VyUHJlZmVyZW5jZXMgPSBbXSkge1xuICAgICAgICAgICAgICAvLyAgICAgY29uc3QgbmV3VXNlclByZWZlcmVuY2VSZWYgPSBjYWNoZS53cml0ZUZyYWdtZW50KHtcbiAgICAgICAgICAgICAgLy8gICAgICAgICBkYXRhOiBkYXRhPy51cGRhdGVfVXNlcl9QcmVmZXJlbmNlPy5yZXR1cm5pbmc/LlswXSxcbiAgICAgICAgICAgICAgLy8gICAgICAgICBmcmFnbWVudDogZ3FsYFxuICAgICAgICAgICAgICAvLyAgICAgZnJhZ21lbnQgTmV3VXNlcl9QcmVmZXJlbmNlIG9uIFVzZXJfUHJlZmVyZW5jZSB7XG4gICAgICAgICAgICAgIC8vICAgICAgICAgaWRcbiAgICAgICAgICAgICAgLy8gICAgICAgICBvbkJvYXJkZWRcbiAgICAgICAgICAgICAgLy8gICAgIH1cbiAgICAgICAgICAgICAgLy8gICBgXG4gICAgICAgICAgICAgIC8vICAgICB9KTtcbiAgICAgICAgICAgICAgcmV0dXJuIFtcbiAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICAuLi5leGlzdGluZ1VzZXJQcmVmZXJlbmNlcz8uWzBdLFxuICAgICAgICAgICAgICAgICAgb25Cb2FyZGVkOlxuICAgICAgICAgICAgICAgICAgICBkYXRhPy51cGRhdGVfVXNlcl9QcmVmZXJlbmNlPy5yZXR1cm5pbmc/LlswXT8ub25Cb2FyZGVkLFxuICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgIF07XG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pO1xuICAgICAgfSxcbiAgICB9KTtcblxuICAgIGNvbnNvbGUubG9nKCd1cGRhdGVVc2VyUHJlZmVyZW5jZU9uQm9hcmRlZCcsIGRhdGEpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyBlcnJvciBpbiB1cGRhdGVVc2VyUHJlZmVyZW5jZU9uYm9hcmRlZCcpO1xuICB9XG59O1xuZXhwb3J0IGNvbnN0IGNyZWF0ZVVzZXJQcmVmZXJlbmNlID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICB1c2VySWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgZXhpc3Rpbmd1c2VyX3ByZWZlcmVuY2UgPSBhd2FpdCBnZXRVc2VyUHJlZmVyZW5jZShjbGllbnQsIHVzZXJJZCk7XG4gICAgY29uc3QgaWQgPSB1dWlkKCk7XG4gICAgaWYgKCFleGlzdGluZ3VzZXJfcHJlZmVyZW5jZSkge1xuICAgICAgY29uc3QgdXNlclByZWZlcmVuY2VWYWx1ZXMgPSB7XG4gICAgICAgIGlkLFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgICAgbWF4V29ya0xvYWRQZXJjZW50OiA4NSxcbiAgICAgICAgYmFja1RvQmFja01lZXRpbmdzOiBmYWxzZSxcbiAgICAgICAgbWluTnVtYmVyT2ZCcmVha3M6IDEsXG4gICAgICAgIG1heE51bWJlck9mTWVldGluZ3M6IDEwLFxuICAgICAgICBicmVha0xlbmd0aDogMzAsXG4gICAgICAgIHN0YXJ0VGltZXM6IFNUQVJUVElNRVMsXG4gICAgICAgIGVuZFRpbWVzOiBFTkRUSU1FUyxcbiAgICAgICAgYnJlYWtDb2xvcjogcGFsZXR0ZS5ncmVlblByaW1hcnksXG4gICAgICAgIG9uQm9hcmRlZDogZmFsc2UsXG4gICAgICAgIGNvcHlBdmFpbGFiaWxpdHk6IHRydWUsXG4gICAgICAgIGNvcHlUaW1lQmxvY2tpbmc6IHRydWUsXG4gICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZTogdHJ1ZSxcbiAgICAgICAgY29weVJlbWluZGVyczogdHJ1ZSxcbiAgICAgICAgY29weVByaW9yaXR5TGV2ZWw6IGZhbHNlLFxuICAgICAgICBjb3B5TW9kaWZpYWJsZTogZmFsc2UsXG4gICAgICAgIGNvcHlDYXRlZ29yaWVzOiB0cnVlLFxuICAgICAgICBjb3B5SXNCcmVhazogdHJ1ZSxcbiAgICAgICAgY29weUlzTWVldGluZzogdHJ1ZSxcbiAgICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nOiB0cnVlLFxuICAgICAgICBjb3B5Q29sb3I6IHRydWUsXG4gICAgICB9O1xuXG4gICAgICBjb25zdCB7IGRhdGEgfSA9IGF3YWl0IGNsaWVudC5tdXRhdGU8e1xuICAgICAgICBpbnNlcnRfVXNlcl9QcmVmZXJlbmNlX29uZTogVXNlclByZWZlcmVuY2VUeXBlO1xuICAgICAgfT4oe1xuICAgICAgICBtdXRhdGlvbjogdXBzZXJ0VXNlclByZWZlcmVuY2UsXG4gICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgIHVzZXJQcmVmZXJlbmNlOiB1c2VyUHJlZmVyZW5jZVZhbHVlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pO1xuXG4gICAgICBhd2FpdCB1cGRhdGVVc2VyRm9yUHJlZmVyZW5jZUlkKGNsaWVudCwgdXNlcklkLCBpZCk7XG5cbiAgICAgIGNvbnNvbGUubG9nKCdjcmVhdGVVc2VyUHJlZmVyZW5jZScsIGRhdGEpO1xuICAgIH1cbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUuZXJyb3IoZSwgJyBjcmVhdGV1c2VyX3ByZWZlcmVuY2UnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGNyZWF0ZURlZmF1bHRQcmltYXJ5Q2FsZW5kYXIgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHVzZXJJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBleGlzdGluZ0NhbGVuZGFyID0gKFxuICAgICAgYXdhaXQgY2xpZW50LnF1ZXJ5PHsgQ2FsZW5kYXI6IENhbGVuZGFyVHlwZVtdIH0+KHtcbiAgICAgICAgcXVlcnk6IGdldEdsb2JhbFByaW1hcnlDYWxlbmRhcixcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICApLmRhdGE/LkNhbGVuZGFyPy5bMF07XG5cbiAgICBpZiAoIWV4aXN0aW5nQ2FsZW5kYXIpIHtcbiAgICAgIC8vIG1ha2UgYW55IGNhbGVuZGFyIHRoZSBwcmltYXJ5XG4gICAgICBjb25zdCBjYWxlbmRhckRvYyA9IChcbiAgICAgICAgYXdhaXQgY2xpZW50LnF1ZXJ5PHsgQ2FsZW5kYXI6IENhbGVuZGFyVHlwZVtdIH0+KHtcbiAgICAgICAgICBxdWVyeTogZ2V0QW55Q2FsZW5kYXIsXG4gICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICAgICkuZGF0YT8uQ2FsZW5kYXI/LlswXTtcblxuICAgICAgaWYgKGNhbGVuZGFyRG9jKSB7XG4gICAgICAgIGF3YWl0IGNsaWVudC5tdXRhdGU8eyB1cGRhdGVfQ2FsZW5kYXJfYnlfcGs6IENhbGVuZGFyVHlwZSB9Pih7XG4gICAgICAgICAgbXV0YXRpb246IHVwZGF0ZUNhbGVuZGFyVG9HbG9iYWxQcmltYXJ5LFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgaWQ6IGNhbGVuZGFyRG9jPy5pZCxcbiAgICAgICAgICB9LFxuICAgICAgICB9KTtcbiAgICAgIH1cbiAgICB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmVycm9yKGUsICcgY3JlYXRlRGVmYXVsdFByaW1hcnlDYWxlbmRhcicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgY3JlYXRlRGVmYXVsdFVzZXIgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHVzZXJJZDogc3RyaW5nLFxuICBlbWFpbDogc3RyaW5nLFxuICBuYW1lPzogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBleGlzdGluZ1VzZXIgPSAoXG4gICAgICBhd2FpdCBjbGllbnQucXVlcnk8eyBVc2VyX2J5X3BrOiBVc2VyVHlwZSB9Pih7XG4gICAgICAgIHF1ZXJ5OiBnZXRVc2VyQnlJZCxcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgaWQ6IHVzZXJJZCxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgKT8uZGF0YT8uVXNlcl9ieV9waztcblxuICAgIGlmICghZXhpc3RpbmdVc2VyKSB7XG4gICAgICBjb25zdCB2YWx1ZXNUb1Vwc2VydCA9IHtcbiAgICAgICAgaWQ6IHVzZXJJZCxcbiAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgICBlbWFpbCxcbiAgICAgICAgbmFtZTogZW1haWwsXG4gICAgICB9O1xuICAgICAgYXdhaXQgY2xpZW50Lm11dGF0ZTx7IGluc2VydF9Vc2VyX29uZTogVXNlclR5cGUgfT4oe1xuICAgICAgICBtdXRhdGlvbjogdXBzZXJ0VXNlcixcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgdXNlcjogdmFsdWVzVG9VcHNlcnQsXG4gICAgICAgIH0sXG4gICAgICB9KTtcbiAgICAgIGNvbnNvbGUubG9nKCdjcmVhdGVEZWZhdWx0VXNlcicsIHZhbHVlc1RvVXBzZXJ0KTtcbiAgICB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmVycm9yKGUsICcgY3JlYXRlRGVmYXVsdFVzZXInKTtcbiAgfVxufTtcblxuLy8gY3JlYXRlIGluaXRpYWwgc2VsZWN0ZWQgY2FsZW5kYXJcbmV4cG9ydCBjb25zdCBjcmVhdGVJbml0aWFsU2VsZWN0ZWRDYWxlbmRhciA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHNldFNlbGVjdGVkQ2FsZW5kYXI6IERpc3BhdGNoPHN0cmluZz5cbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGV4aXN0aW5nQ2FsZW5kYXIgPSAoXG4gICAgICBhd2FpdCBjbGllbnQucXVlcnk8eyBDYWxlbmRhcjogQ2FsZW5kYXJUeXBlW10gfT4oe1xuICAgICAgICBxdWVyeTogZ2V0R2xvYmFsUHJpbWFyeUNhbGVuZGFyLFxuICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICkuZGF0YT8uQ2FsZW5kYXI/LlswXTtcblxuICAgIGlmICghZXhpc3RpbmdDYWxlbmRhcikge1xuICAgICAgY29uc3Qgb2xkQ2FsZW5kYXJEb2MgPSAoXG4gICAgICAgIGF3YWl0IGNsaWVudC5xdWVyeTx7IENhbGVuZGFyOiBDYWxlbmRhclR5cGVbXSB9Pih7XG4gICAgICAgICAgcXVlcnk6IGdldEFueUNhbGVuZGFyLFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pXG4gICAgICApLmRhdGE/LkNhbGVuZGFyPy5bMF07XG5cbiAgICAgIGlmIChvbGRDYWxlbmRhckRvYykge1xuICAgICAgICBhd2FpdCBjbGllbnQubXV0YXRlPHsgdXBkYXRlX0NhbGVuZGFyX2J5X3BrOiBDYWxlbmRhclR5cGUgfT4oe1xuICAgICAgICAgIG11dGF0aW9uOiB1cGRhdGVDYWxlbmRhclRvR2xvYmFsUHJpbWFyeSxcbiAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIGlkOiBvbGRDYWxlbmRhckRvYz8uaWQsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSk7XG4gICAgICAgIHNldFNlbGVjdGVkQ2FsZW5kYXIob2xkQ2FsZW5kYXJEb2M/LmlkKTtcbiAgICAgIH1cbiAgICB9IGVsc2Uge1xuICAgICAgc2V0U2VsZWN0ZWRDYWxlbmRhcihleGlzdGluZ0NhbGVuZGFyPy5pZCk7XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5lcnJvcihlLCAnIGNyZWF0ZUluaXRpYWxTZWxlY3RlZENhbGVuZGFyJyk7XG4gIH1cbn07XG4iXX0=