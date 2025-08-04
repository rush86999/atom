import _ from 'lodash';
import { v4 as uuid } from 'uuid';
import { Dispatch } from 'react';

import { dayjs } from '@lib/date-utils';

import { palette } from '@lib/theme/theme';
import { CalendarType } from '@lib/dataTypes/CalendarType';
import { CategoryType } from '@lib/dataTypes/CategoryType';
import {
  EndTimeType,
  StartTimeType,
  UserPreferenceType,
} from '@lib/dataTypes/User_PreferenceType';

import ThirdPartyEmailPassword from 'supertokens-web-js/recipe/thirdpartyemailpassword';

import { Platform } from 'react-native';
import { localCalendarResource } from '@lib/calendarLib/constants';
import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import updateCalendarToGlobalPrimary from '@lib/apollo/gql/updateCalendarToGlobalPrimary';
import {
  createCategory,
  listUserCategories,
} from '@lib/Category/CategoryHelper';

import upsertUserPreference from '@lib/apollo/gql/upsertUserPreference';
import getGlobalPrimaryCalendar from '@lib/apollo/gql/getGlobalPrimaryCalendar';
import getAnyCalendar from '@lib/apollo/gql/getAnyCalendar';
import { UserType } from '@lib/dataTypes/UserType';
import getUserById from '@lib/apollo/gql/getUserById';
import upsertUser from '@lib/apollo/gql/upsertUser';
import updateUserForUserPreferenceId from '@lib/apollo/gql/updateUserForUserPreferenceId';
import upsertCalendar from '@lib/apollo/gql/upsertCalendar';
import { EventType } from '@lib/dataTypes/EventType';
import listEventsForCalendarId from '@lib/apollo/gql/listEventsForCalendarId';
import updateUserPreferenceOnBoardedMutation from '@lib/apollo/gql/updateUserPreferenceOnBoardedMutation';
import updateCalendarDropGlobalPrimary from '@lib/apollo/gql/updateCalendarDropGlobalPrimary';
import getUserPreferenceForUser from '@lib/apollo/gql/getUserPreferenceForUser';
import updateCalendarsDropGlobalPrimary from '@lib/apollo/gql/updateCalendarsDropGlobalPrimary';

const DEFAULTCATEGORIES: CategoryType[] = [
  {
    id: uuid(),
    name: 'External Meeting',
    createdDate: dayjs().toISOString(),
    updatedAt: dayjs().toISOString(),
    deleted: false,
    userId: '',
  },
  {
    id: uuid(),
    name: 'Meeting',
    createdDate: dayjs().toISOString(),
    updatedAt: dayjs().toISOString(),
    deleted: false,
    userId: '',
  },
  {
    id: uuid(),
    name: 'Life Milestone',
    createdDate: dayjs().toISOString(),
    updatedAt: dayjs().toISOString(),
    deleted: false,
    userId: '',
  },
  {
    id: uuid(),
    name: 'Sports',
    createdDate: dayjs().toISOString(),
    updatedAt: dayjs().toISOString(),
    deleted: false,
    userId: '',
  },
  {
    id: uuid(),
    name: 'Social Meetup',
    createdDate: dayjs().toISOString(),
    updatedAt: dayjs().toISOString(),
    deleted: false,
    userId: '',
  },
  {
    id: uuid(),
    name: 'Break',
    createdDate: dayjs().toISOString(),
    updatedAt: dayjs().toISOString(),
    deleted: false,
    userId: '',
  },
];

const STARTTIMES: StartTimeType[] = [
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

const ENDTIMES: EndTimeType[] = [
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

export const listEventsForCalendar = async (
  client: ApolloClient<NormalizedCacheObject>,
  calendarId: string
) => {
  try {
    const { data } = await client.query<{
      Event: EventType[];
    }>({
      query: listEventsForCalendarId,
      variables: {
        calendarId,
      },
    });

    console.log(data, ' successfully listed events for Calendar');
    return data?.Event;
  } catch (e) {
    console.log(e, ' unable to listEventsForCalendar');
  }
};

export const dropPrimaryLabelForCalendars = async (
  client: ApolloClient<NormalizedCacheObject>,
  calendarIds: string[]
): Promise<void | null> => {
  try {
    // validate
    if (!(calendarIds?.length > 0)) {
      console.log('no calendarIds inside dropPrimaryLableForCalendars');
      return null;
    }
    const { data } = await client.mutate<{
      update_Calendar: { affected_rows: number; returning: CalendarType[] };
    }>({
      mutation: updateCalendarsDropGlobalPrimary,
      variables: {
        ids: calendarIds,
      },
      update(cache, { data }) {
        const deletedCalendars = data?.update_Calendar?.returning;
        const normalizedIds = deletedCalendars?.map((c) =>
          cache.identify({ id: c.id, __typename: c.__typename })
        );
        normalizedIds?.forEach((id) => cache.evict({ id }));
        cache.gc();
      },
    });

    console.log(data, ' successfully dropped primary calendar');
  } catch (e) {
    console.log(e, ' unable to dropPrimaryCalendar');
  }
};

export const dropPrimaryLabelForCalendar = async (
  client: ApolloClient<NormalizedCacheObject>,
  calendarId: string
): Promise<void | null> => {
  try {
    // validate
    if (!calendarId) {
      console.log('no calendarId inside dropPrimaryLabelForCalendar');
      return null;
    }
    const { data } = await client.mutate<{
      update_Calendar_by_pk: CalendarType;
    }>({
      mutation: updateCalendarDropGlobalPrimary,
      variables: {
        id: calendarId,
      },
    });

    console.log(data, ' successfully dropped primary calendar');
  } catch (e) {
    console.log(e, ' unable to dropPrimaryCalendar');
  }
};
export const setPrimaryCalendar = async (
  client: ApolloClient<NormalizedCacheObject>,
  calendar: CalendarType
) => {
  try {
    const { data } = await client.mutate<{
      update_Calendar_by_pk: CalendarType;
    }>({
      mutation: updateCalendarToGlobalPrimary,
      variables: {
        id: calendar.id,
      },
    });

    console.log('setPrimaryCalendar', data);
  } catch (e) {
    console.error(e, ' setPrimaryCalendar');
  }
};

export const generateDefaultCategories = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string
) => {
  try {
    const existingCategories = await listUserCategories(client, userId);

    if (existingCategories?.length === 0) {
      DEFAULTCATEGORIES.forEach(async (category) => {
        await createCategory(client, category?.name, userId);
      });
    }
  } catch (e) {
    console.error(e, ' generateDefaultCategories');
  }
};

export const getUserPreference = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string
) => {
  try {
    const { data } = await client.query<{
      User_Preference: UserPreferenceType[];
    }>({
      query: getUserPreferenceForUser,
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
  } catch (e) {
    console.error(e, ' getUserPreference');
  }
};

export const updateUserForPreferenceId = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  preferenceId: string
) => {
  try {
    const { data } = await client.mutate<{ update_User_by_pk: UserType }>({
      mutation: updateUserForUserPreferenceId,
      variables: {
        id: userId,
        userPreferenceId: preferenceId,
      },
    });

    console.log('updateUserForPreferenceId', data);
  } catch (e) {
    console.error(e, ' updateUserForPreferenceId');
  }
};

export const updateUserPreferenceOnBoarded = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  onBoarded: boolean
): Promise<void> => {
  try {
    const { data } = await client.mutate<{
      update_User_Preference: {
        affected_rows: number;
        returning: UserPreferenceType[];
      };
    }>({
      mutation: updateUserPreferenceOnBoardedMutation,
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
                  onBoarded:
                    data?.update_User_Preference?.returning?.[0]?.onBoarded,
                },
              ];
            },
          },
        });
      },
    });

    console.log('updateUserPreferenceOnBoarded', data);
  } catch (e) {
    console.log(e, ' error in updateUserPreferenceOnboarded');
  }
};
export const createUserPreference = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string
) => {
  try {
    const existinguser_preference = await getUserPreference(client, userId);
    const id = uuid();
    if (!existinguser_preference) {
      const userPreferenceValues = {
        id,
        userId,
        createdDate: dayjs().toISOString(),
        updatedAt: dayjs().toISOString(),
        deleted: false,
        maxWorkLoadPercent: 85,
        backToBackMeetings: false,
        minNumberOfBreaks: 1,
        maxNumberOfMeetings: 4,
        breakLength: 15,
        startTimes: STARTTIMES,
        endTimes: ENDTIMES,
        breakColor: palette.greenPrimary,
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

      const { data } = await client.mutate<{
        insert_User_Preference_one: UserPreferenceType;
      }>({
        mutation: upsertUserPreference,
        variables: {
          userPreference: userPreferenceValues,
        },
      });

      await updateUserForPreferenceId(client, userId, id);

      console.log('createUserPreference', data);
    }
  } catch (e) {
    console.error(e, ' createuser_preference');
  }
};

export const createDefaultPrimaryCalendar = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string
) => {
  try {
    const existingCalendar = (
      await client.query<{ Calendar: CalendarType[] }>({
        query: getGlobalPrimaryCalendar,
        variables: {
          userId,
        },
      })
    ).data?.Calendar?.[0];

    if (!existingCalendar) {
      // make any calendar the primary
      const calendarDoc = (
        await client.query<{ Calendar: CalendarType[] }>({
          query: getAnyCalendar,
          variables: {
            userId,
          },
        })
      ).data?.Calendar?.[0];

      if (calendarDoc) {
        await client.mutate<{ update_Calendar_by_pk: CalendarType }>({
          mutation: updateCalendarToGlobalPrimary,
          variables: {
            id: calendarDoc?.id,
          },
        });
      }
    }
  } catch (e) {
    console.error(e, ' createDefaultPrimaryCalendar');
  }
};

export const createDefaultUser = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string
) => {
  try {
    const existingUser = (
      await client.query<{ User_by_pk: UserType }>({
        query: getUserById,
        variables: {
          id: userId,
        },
      })
    )?.data?.User_by_pk;

    if (!existingUser) {
      const userInfo = await ThirdPartyEmailPassword.getUserById(userId);
      const email = userInfo?.email;
      const valuesToUpsert = {
        id: userId,
        createdDate: dayjs().toISOString(),
        updatedAt: dayjs().toISOString(),
        deleted: false,
        email,
        name: userInfos?.name || '',
      };
      await client.mutate<{ insert_User_one: UserType }>({
        mutation: upsertUser,
        variables: {
          user: valuesToUpsert,
        },
      });
      console.log('createDefaultUser', valuesToUpsert);
    }
  } catch (e) {
    console.error(e, ' createDefaultUser');
  }
};

// create initial selected calendar
export const createInitialSelectedCalendar = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  setSelectedCalendar: Dispatch<string>
) => {
  try {
    const existingCalendar = (
      await client.query<{ Calendar: CalendarType[] }>({
        query: getGlobalPrimaryCalendar,
        variables: {
          userId,
        },
      })
    ).data?.Calendar?.[0];

    if (!existingCalendar) {
      const oldCalendarDoc = (
        await client.query<{ Calendar: CalendarType[] }>({
          query: getAnyCalendar,
          variables: {
            userId,
          },
        })
      ).data?.Calendar?.[0];

      if (oldCalendarDoc) {
        await client.mutate<{ update_Calendar_by_pk: CalendarType }>({
          mutation: updateCalendarToGlobalPrimary,
          variables: {
            id: oldCalendarDoc?.id,
          },
        });
        setSelectedCalendar(oldCalendarDoc?.id);
      }
    } else {
      setSelectedCalendar(existingCalendar?.id);
    }
  } catch (e) {
    console.error(e, ' createInitialSelectedCalendar');
  }
};
