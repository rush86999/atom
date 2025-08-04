import { ApolloClient, gql, NormalizedCacheObject } from '@apollo/client';
import insertMeetingAssistPreferredTimeRangesMutation from '@lib/apollo/gql/insertMeetingAssistPreferredTimeRangesMutation';
import { MeetingAssistInviteType } from '@lib/dataTypes/MeetingAssistInviteType';
import { MeetingAssistPreferredTimeRangeType } from '@lib/dataTypes/MeetingAssistPreferredTimeRangeType';
import { MeetingAssistType } from '@lib/dataTypes/MeetingAssistType';
import { RRule } from 'rrule';
import { dayjs } from '@lib/date-utils';

// lib/Calendar/UserCreateCalendarHelper.ts
import {
  getRRuleDay,
  getRruleFreq,
} from '@lib/Calendar/UserCreateCalendarHelper';
import {
  AttendeeDetailsForBulkMeetingCancelledType,
  AttendeeDetailsForBulkMeetingInviteType,
  AttendeeDetailsType,
  MeetingInviteDetailsToHostType,
} from '@lib/Assist/types';
import Session from 'supertokens-web-js/recipe/session';
import {
  emailMeetingCancelUrl,
  emailMeetingInfoToHostUrl,
  emailMeetingInviteUrl,
  handshakeUrl,
} from '@lib/Assist/constants';
import axios from 'axios';
import qs from 'qs';
import upsertMeetingAssistInvitesMutation from '@lib/apollo/gql/upsertMeetingAssistInvitesMutation';
import { MeetingAssistAttendeeType } from '@lib/dataTypes/MeetingAssistAttendeeType';
import insertAttendeeMutation from '@lib/apollo/gql/insertAttendeeMutation';
import getUserById from '@lib/apollo/gql/getUserById';
import { UserType } from '@lib/dataTypes/UserType';

import { SelectedContactType } from '@pages/Calendar/CreateEventWizard/CreateEventAttendees';
import { Person, RecurrenceFrequencyType } from '@lib/Calendar/types';
import { Dispatch, SetStateAction } from 'react';
import { v4 as uuid } from 'uuid';
import _ from 'lodash';
import { AttendeeEmailType } from '@lib/dataTypes/AttendeeType';
import updateUserForName from '@lib/apollo/gql/updateUserForName';
import listMeetingAssists from '@lib/apollo/gql/listMeetingAssists';
import deleteMeetingAssistById from '@lib/apollo/gql/deleteMeetingAssistById';
import listMeetingAssistInvites from '@lib/apollo/gql/listMeetingAssistInvites';
import insertMeetingAssistAttendeeOne from '@lib/apollo/gql/insertMeetingAssistAttendeeOne';
import getMeetingAssistById from '@lib/apollo/gql/getMeetingAssistById';
import searchMeetingAssistsQuery from '@lib/apollo/gql/searchMeetingAssistsQuery';

export const listMeetingAssistInvitesGivenMeetingId = async (
  client: ApolloClient<NormalizedCacheObject>,
  meetingId: string
) => {
  try {
    const meetingAssistInvitesDoc = (
      await client.query<{ Meeting_Assist_Invite: MeetingAssistInviteType[] }>({
        query: listMeetingAssistInvites,
        variables: {
          meetingId,
        },
      })
    )?.data?.Meeting_Assist_Invite;

    console.log(
      meetingAssistInvitesDoc,
      ' successfully listed meeting assist invites given meetingId'
    );

    return meetingAssistInvitesDoc;
  } catch (e) {
    console.log(e, ' unable to list meeting assist invites given meetingId');
  }
};

export const getMeetingAssistGivenId = async (
  client: ApolloClient<NormalizedCacheObject>,
  meetingId: string
) => {
  try {
    const meetingAssistDoc = (
      await client.query<{ Meeting_Assist_by_pk: MeetingAssistType }>({
        query: getMeetingAssistById,
        variables: {
          id: meetingId,
        },
      })
    )?.data?.Meeting_Assist_by_pk;

    console.log(meetingAssistDoc, ' successfully got meetingAssistDoc');
    return meetingAssistDoc;
  } catch (e) {
    console.log(e, ' unable to get meeting assist given Id');
  }
};

export const listUserMeetingAssistsGivenUserId = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string
) => {
  try {
    const meetingAssists = (
      await client.query<{ Meeting_Assist: MeetingAssistType[] }>({
        query: listMeetingAssists,
        variables: {
          userId,
        },
      })
    )?.data?.Meeting_Assist;

    console.log(meetingAssists, ' successfully returned meeting assists');

    return meetingAssists;
  } catch (e) {
    console.log(e, ' unable to list user meeting assists given userId');
  }
};

export const getUserGivenId = async (
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

    console.log(existingUser, ' successfully gotten userId');

    return existingUser;
  } catch (e) {
    console.log(e, ' unable to get user given Id inside getUserGivenId');
  }
};

export const deleteMeetingAssistGivenId = async (
  client: ApolloClient<NormalizedCacheObject>,
  id: string
) => {
  try {
    const deletedMeetingAssistDoc = (
      await client.mutate<{ delete_Meeting_Assist_by_pk: MeetingAssistType }>({
        mutation: deleteMeetingAssistById,
        variables: {
          id,
        },
      })
    )?.data?.delete_Meeting_Assist_by_pk;

    console.log(
      deletedMeetingAssistDoc,
      ' successfully deleted meeting assist doc'
    );
  } catch (e) {
    console.log(e, ' unable to delete meeting assist given id');
  }
};

export const updateUserNameGivenId = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  name: string
) => {
  try {
    const userDoc = (
      await client.mutate<{ update_User_by_pk: UserType }>({
        mutation: updateUserForName,
        variables: {
          id: userId,
          name,
        },
      })
    )?.data?.update_User_by_pk;

    console.log(userDoc, ' successfully updated userDoc');
  } catch (e) {
    console.log(e, ' uanble to update user name given id');
  }
};

export const insertMeetingAssistAttendee = async (
  client: ApolloClient<NormalizedCacheObject>,
  attendee: MeetingAssistAttendeeType
) => {
  try {
    const meetingAssistAttendeeDoc = (
      await client.mutate<{
        insert_Meeting_Assist_Attendee_one: MeetingAssistAttendeeType;
      }>({
        mutation: insertMeetingAssistAttendeeOne,
        variables: {
          attendee,
        },
      })
    )?.data?.insert_Meeting_Assist_Attendee_one;

    console.log(
      meetingAssistAttendeeDoc,
      ' successfully inserted meeting assist attendee'
    );

    return meetingAssistAttendeeDoc;
  } catch (e) {
    console.log(e, ' unable to insert attendee one');
  }
};

export const upsertMeetingAssistMany = async (
  client: ApolloClient<NormalizedCacheObject>,
  meetingAssists: MeetingAssistType[]
) => {
  try {
    console.log(
      meetingAssists,
      ' meetingAssistsinside upsertMeetingAssistMany'
    );
    // ASSUMPTION: A custom mutation 'bulkUpsertMeetingAssists' is defined in PostGraphile (e.g., via a PG function)
    // that takes an array of MeetingAssistInput and handles the upsert logic.
    // The return type will also depend on the custom function's definition.
    // The list of columns in on_conflict is now implicit in the PG function.
    const upsertMeetingAssistsMutation = gql`
      mutation BulkUpsertMeetingAssists($assists: [MeetingAssistInput!]!) {
        bulkUpsertMeetingAssists(input: { assists: $assists }) {
          # Assuming the custom function returns a list of the upserted meeting assists
          # and PostGraphile wraps this in a standard payload structure.
          # Or it might return a simple list directly if the function returns SETOF.
          # Let's assume it returns a list of meetingAssists for now.
          # The actual structure will depend on the PostGraphile schema.
          results: meetingAssists {
            # Or just 'meetingAssists' if function returns SETOF meeting_assist
            allowAttendeeUpdatePreferences
            anyoneCanAddSelf
            attendeeCanModify
            attendeeCount
            attendeeRespondedCount
            backgroundColor
            bufferTime
            calendarId
            cancelIfAnyRefuse
            cancelled
            colorId
            conferenceApp
            createdDate
            duration
            enableAttendeePreferences
            enableConference
            enableHostPreferences
            endDate
            eventId
            expireDate
            foregroundColor
            frequency
            guaranteeAvailability
            guestsCanInviteOthers
            guestsCanSeeOtherGuests
            id
            interval
            location
            minThresholdCount
            notes
            originalMeetingId
            priority
            reminders
            sendUpdates
            startDate
            summary
            timezone
            transparency
            until
            updatedAt
            useDefaultAlarms
            userId
            visibility
            windowEndDate
            windowStartDate
            lockAfter
          }
          # PostGraphile mutations often return a standard payload, e.g., { clientMutationId, data }
          # For simplicity, assuming the function returns directly or is wrapped to return the list.
          # If it returns a count:
          # affectedCount
        }
      }
    `;
    // The type parameter for client.mutate will need to change based on the actual return type.
    // Let's assume for now it returns a list of MeetingAssistType directly or under a 'results' or 'meetingAssists' field.
    // This part is highly speculative without the actual PostGraphile schema.
    const meetingAssistsDataDoc = (
      await client.mutate<{
        bulkUpsertMeetingAssists: {
          results: MeetingAssistType[];
        } /* Or { meetingAssists: MeetingAssistType[] } or MeetingAssistType[] directly */;
      }>({
        mutation: upsertMeetingAssistsMutation,
        variables: {
          assists: meetingAssists, // Variable name changed
        },
      })
    )?.data?.bulkUpsertMeetingAssists;

    // This access will likely need to change:
    console.log(
      meetingAssistsDataDoc?.results?.length,
      ' successfully created multiple meeting assists'
    );
    return meetingAssistsDataDoc?.results?.length; // Or however the count/results are returned
  } catch (e) {
    console.log(e, ' unable to upsert meeting assist many');
  }
};

export const upsertMeetingAssistOne = async (
  client: ApolloClient<NormalizedCacheObject>,
  meetingAssist: MeetingAssistType // This might need to be MeetingAssistInput
) => {
  try {
    console.log(meetingAssist, ' meetingAssist inside upsertMeetingAssistOne');
    // ASSUMPTION: A custom mutation 'upsertMeetingAssist' is defined in PostGraphile (e.g., via a PG function)
    // OR we use separate createMeetingAssist and updateMeetingAssist mutations.
    // Given 'on_conflict', an upsert is intended.
    // PostGraphile input types are typically like `MeetingAssistInput` for create and `MeetingAssistPatch` for update.
    // A custom upsert might take `MeetingAssistInput`.
    const upsertMeetingAssistGraphql = gql`
      mutation UpsertMeetingAssist($input: UpsertMeetingAssistInput!) {
        # Input type might be UpsertMeetingAssistInput or similar
        upsertMeetingAssist(input: $input) {
          # Mutation name depends on PG function
          meetingAssist {
            # Standard PostGraphile payload structure
            allowAttendeeUpdatePreferences
            anyoneCanAddSelf
            attendeeCanModify
            attendeeCount
            attendeeRespondedCount
            backgroundColor
            bufferTime
            calendarId
            cancelIfAnyRefuse
            cancelled
            colorId
            conferenceApp
            createdDate
            duration
            enableAttendeePreferences
            enableConference
            enableHostPreferences
            endDate
            eventId
            expireDate
            foregroundColor
            frequency
            guaranteeAvailability
            guestsCanInviteOthers
            guestsCanSeeOtherGuests
            id
            interval
            location
            minThresholdCount
            notes
            originalMeetingId
            priority
            reminders
            sendUpdates
            startDate
            summary
            timezone
            transparency
            until
            updatedAt
            useDefaultAlarms
            userId
            visibility
            windowEndDate
            windowStartDate
            lockAfter
          }
        }
      }
    `;
    // The variable passed to the mutation needs to match the GraphQL schema.
    // If `upsertMeetingAssist` expects `input: { meetingAssist: MeetingAssistInput! }`
    // then variables should be `{ input: { meetingAssist: meetingAssist } }`
    // If it expects `input: MeetingAssistInput!`, then `{ input: meetingAssist }`
    // For now, assuming `input: { meetingAssist: ... }` is a common pattern for custom mutations.
    const meetingAssistDoc = (
      await client.mutate<{
        upsertMeetingAssist: { meetingAssist: MeetingAssistType };
      }>({
        mutation: upsertMeetingAssistGraphql,
        variables: {
          // This structure depends on how the PostGraphile mutation `upsertMeetingAssist` is defined.
          // Assuming it takes an 'input' object which then has a 'meetingAssist' field of the correct input type.
          input: { meetingAssist: meetingAssist },
        },
      })
    )?.data?.upsertMeetingAssist?.meetingAssist;

    console.log(meetingAssistDoc, ' successfully added meetingAssistDoc');

    return meetingAssistDoc;
  } catch (e) {
    console.log(e, ' unable to upsert meeting assist');
  }
};

export const upsertMeetingAssistInviteMany = async (
  client: ApolloClient<NormalizedCacheObject>,
  meetingAssistInvites: MeetingAssistInviteType[] // This might need to be MeetingAssistInviteInput[]
) => {
  try {
    // ASSUMPTION: A custom mutation 'bulkUpsertMeetingAssistInvites' is defined in PostGraphile
    const upsertMeetingAssistInviteGraphql = gql`
      mutation BulkUpsertMeetingAssistInvites(
        $invites: [MeetingAssistInviteInput!]!
      ) {
        bulkUpsertMeetingAssistInvites(input: { invites: $invites }) {
          # Or similar structure
          # Assuming it returns a list of the upserted invites
          results: meetingAssistInvites {
            # Or just 'meetingAssistInvites'
            createdDate
            email
            hostId
            hostName
            id
            meetingId
            name
            response
            updatedAt
            userId
            contactId
          }
          # Or an affected count
          # affectedCount
        }
      }
    `;
    // Adjust generic type and variable structure based on actual PostGraphile mutation
    const meetingAssistInviteDocData = (
      await client.mutate<{
        bulkUpsertMeetingAssistInvites: { results: MeetingAssistInviteType[] };
      }>({
        mutation: upsertMeetingAssistInviteGraphql,
        variables: {
          invites: meetingAssistInvites,
        },
      })
    )?.data?.bulkUpsertMeetingAssistInvites;

    console.log(
      meetingAssistInviteDocData?.results?.length,
      ' successfully inserted meetingAssistInviteDocs'
    );
    return meetingAssistInviteDocData?.results?.length;
  } catch (e) {
    console.log(e, ' unable to upsert meeting assist invite');
  }
};

export const insertMeetingAssistPreferredTimeRanges = async (
  client: ApolloClient<NormalizedCacheObject>,
  meetingAssistPreferredTimeRanges: MeetingAssistPreferredTimeRangeType[]
) => {
  try {
    const meetingAssistInviteDocData = (
      await client.mutate<{
        insert_Meeting_Assist_Preferred_Time_Range: {
          affected_rows: number;
          returning: MeetingAssistPreferredTimeRangeType[];
        };
      }>({
        mutation: insertMeetingAssistPreferredTimeRangesMutation,
        variables: {
          meetingAssistPreferredTimeRanges,
        },
      })
    )?.data?.insert_Meeting_Assist_Preferred_Time_Range;

    console.log(
      meetingAssistInviteDocData?.affected_rows,
      ' successfully inserted meeting assist time ranges '
    );

    return meetingAssistInviteDocData?.affected_rows;
  } catch (e) {
    console.log(e, ' unable to upsert meeting assist preferred time ranges');
  }
};

export const generateDatesForFutureMeetingAssistsUsingRrule = async (
  windowStartDate: string,
  windowEndDate: string,
  frequency: RecurrenceFrequencyType,
  interval: number,
  until: string
) => {
  try {
    const ruleStartDate = new RRule({
      dtstart: dayjs(windowStartDate).toDate(),
      freq: getRruleFreq(frequency),
      interval,
      until: dayjs(until).toDate(),
    });

    const windowStartDatesForRecurrence = ruleStartDate
      .all()
      ?.map((d) => dayjs.utc(d).format());

    const ruleEndDate = new RRule({
      dtstart: dayjs(windowEndDate).toDate(),
      freq: getRruleFreq(frequency),
      interval,
      until: dayjs(until).toDate(),
    });

    const windowEndDatesForRecurrence = ruleEndDate
      .all()
      ?.map((d) => dayjs.utc(d).format());

    // reformat into windowStartDates and windowEndDates
    const timeWindows = windowStartDatesForRecurrence
      ?.slice(0, windowEndDatesForRecurrence?.length)
      ?.map((windowStartDate, inx) => {
        return {
          windowStartDate,
          windowEndDate: windowEndDatesForRecurrence?.[inx],
        };
      });

    return timeWindows;
  } catch (e) {
    console.log(e, ' generate dates for meeting assists recurrence');
  }
};

export const searchMeetingAssists = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  summary: string
): Promise<MeetingAssistType[] | [] | undefined> => {
  try {
    const formattedSummary = `%${summary}%`;

    const results = (
      await client.query<{ Meeting_Assist: MeetingAssistType[] }>({
        query: searchMeetingAssistsQuery,
        variables: {
          userId,
          name: formattedSummary,
        },
        fetchPolicy: 'no-cache',
      })
    )?.data?.Meeting_Assist;

    console.log(results, ' results inside searchMeetingAssists');

    return results;
  } catch (e) {
    console.log(e, ' unable to search meeting assists');
  }
};

export const sendBulkMeetingCancelEmail = async (
  attendees: AttendeeDetailsForBulkMeetingCancelledType[],
  hostEmail: string,
  hostName: string
) => {
  try {
    const url = emailMeetingCancelUrl;

    const accessToken = await Session.getAccessToken();

    const config = {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    };

    const data = {
      attendees,
      hostName,
      hostEmail,
    };

    const results = await axios.post(url, data, config);

    console.log(
      results,
      ' succesfully sent cancel notifications for meeting assist'
    );
  } catch (e) {
    console.log(e, ' unable to send bulk meeting cancel meeting');
  }
};

export const sendBulkMeetingInviteEmail = async (
  attendees: AttendeeDetailsForBulkMeetingInviteType[],
  hostEmail: string,
  hostName: string
) => {
  try {
    console.log(
      attendees,
      ' AttendeeDetailsForBulkMeetingInviteType inside sendBulkMeetingInviteEmail'
    );

    const url = emailMeetingInviteUrl;

    const accessToken = await Session.getAccessToken();

    const config = {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    };

    const data = {
      attendees,
      hostName,
      hostEmail,
    };

    const results = await axios.post(url, data, config);

    console.log(results, ' successfully sent to email to invites');
  } catch (e) {
    console.log(e, ' unable to send bulk meeting invite email');
  }
};

export const convertInviteeTypeToCancelEmailRecipients = (
  invitees: MeetingAssistInviteType[]
) => {
  const cancelEmails = invitees?.map((i) => ({
    email: i?.email || '',
    name: i?.name,
  }));

  return cancelEmails;
};

export const convertInviteeTypeToInviteEmailRecipients = (
  invitees: MeetingAssistInviteType[],
  meetingId: string
) => {
  const inviteeEmails = invitees?.map((i) => ({
    email: i?.email || '',
    name: i?.name,
    link: generateInviteLink(meetingId, i?.id, i?.email),
  }));

  return inviteeEmails;
};

export const sendMeetingInfoToHostEmail = async (
  attendees: AttendeeDetailsType[],
  hostEmail: string,
  hostName: string,
  title: string,
  notes: string,
  windowStartDate: string,
  windowEndDate: string,
  timezone: string
) => {
  try {
    console.log(
      attendees,
      ' AttendeeDetailsType inside sendMeetingInfoToHostEmail'
    );
    const accessToken = await Session.getAccessToken();

    const config = {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    };

    const data: MeetingInviteDetailsToHostType = {
      attendees,
      hostEmail,
      hostName,
      title,
      notes,
      windowStartDate,
      windowEndDate,
      timezone,
    };

    const url = emailMeetingInfoToHostUrl;

    const results = await axios.post(url, data, config);

    console.log(results, ' successfully sent email to host');
  } catch (e) {
    console.log(e, ' unable to send email to host');
  }
};

export const generateInviteLink = (
  meetingId: string,
  attendeeId: string,
  primaryEmail?: string
) =>
  (primaryEmail &&
    `${handshakeUrl}?${qs.stringify({ meetingId, attendeeId, primaryEmail })}`) ||
  `${handshakeUrl}?${qs.stringify({ meetingId, attendeeId })}`;

export const addContactToInvitees = (
  c: SelectedContactType,
  invitees: MeetingAssistInviteType[],
  setI: Dispatch<SetStateAction<MeetingAssistInviteType[]>>,
  setParentI: Dispatch<SetStateAction<MeetingAssistInviteType[]>>,
  hostId: string,
  hostName: string,
  meetingId: string
) => {
  const formattedC: MeetingAssistInviteType = {
    id: uuid(),
    name: c?.name || '',
    email: c?.emails?.find((e: { primary: boolean }) => e?.primary)?.value,
    hostId,
    hostName,
    meetingId,
    createdDate: dayjs().format(),
    updatedAt: dayjs().format(),
    userId: c?.userId,
    contactId: c?.id,
  };

  const newInvitees = invitees.concat([formattedC]);
  setI(newInvitees);
  setParentI(newInvitees);
};

export const addOneToManualEntries = (
  i: MeetingAssistInviteType[],
  setI: Dispatch<SetStateAction<MeetingAssistInviteType[]>>,
  invitees: MeetingAssistInviteType[],
  setInvitees: Dispatch<SetStateAction<MeetingAssistInviteType[]>>,
  setParentI: Dispatch<SetStateAction<MeetingAssistInviteType[]>>,
  hostId: string,
  hostName: string,
  meetingId: string
) => {
  const newValue: MeetingAssistInviteType = {
    id: uuid(),
    hostId,
    email: '',
    hostName,
    meetingId,
    name: '',
    createdDate: dayjs().format(),
    updatedAt: dayjs().format(),
  };

  const newMe = _.uniqWith(i.concat([newValue]), _.isEqual);
  setI(newMe);
  const newInvitees = _.uniqWith(invitees.concat([newValue]), _.isEqual);
  setInvitees(newInvitees);
  setParentI(newInvitees);
};

export const removeContactFromInvitee = (
  c: SelectedContactType,
  invitees: MeetingAssistInviteType[],
  setInvitees: Dispatch<SetStateAction<MeetingAssistInviteType[]>>,
  setParentI: Dispatch<SetStateAction<MeetingAssistInviteType[]>>
) => {
  const foundIndex = invitees.findIndex((a) => a?.id === c?.id);

  if (foundIndex > -1) {
    const newAttendees = invitees
      .slice(0, foundIndex)
      .concat(invitees.slice(foundIndex + 1));

    setInvitees(newAttendees);
    setParentI(newAttendees);
  }
};

export const removeContactFromSearchInvitee = (
  c: SelectedContactType,
  invitees: MeetingAssistInviteType[],
  searchResults: SelectedContactType[],
  setInvitees: Dispatch<SetStateAction<MeetingAssistInviteType[]>>,
  setSearchResults: Dispatch<SetStateAction<SelectedContactType[]>>,
  setParentI: Dispatch<SetStateAction<MeetingAssistInviteType[]>>
) => {
  const foundIndex = invitees.findIndex((a) => a?.id === c?.id);

  if (foundIndex > -1) {
    const newInvitees = invitees
      .slice(0, foundIndex)
      .concat(invitees.slice(foundIndex + 1));

    setInvitees(newInvitees);
    setParentI(newInvitees);
  }

  const foundSearchIndex = searchResults?.findIndex((a) => a?.id === c?.id);

  if (foundSearchIndex > -1) {
    const newSearchInvitees = searchResults
      .slice(0, foundIndex)
      .concat(searchResults.slice(foundIndex + 1));

    setSearchResults(newSearchInvitees);
  }
};

export const removeEntryFromManualEntries = (
  manualEntries: MeetingAssistInviteType[],
  setManualEntries: Dispatch<SetStateAction<MeetingAssistInviteType[]>>,
  invitees: MeetingAssistInviteType[],
  setInvitees: Dispatch<SetStateAction<MeetingAssistInviteType[]>>,
  setParentI: Dispatch<SetStateAction<MeetingAssistInviteType[]>>,
  index: number,
  parentIndex: number
) => {
  const newEntries = manualEntries
    .slice(0, index)
    .concat(manualEntries.slice(index + 1));
  setManualEntries(newEntries);
  const newAttendees = invitees
    .slice(0, parentIndex)
    .concat(invitees.slice(parentIndex + 1));
  setInvitees(newAttendees);
  setParentI(newAttendees);
};

export const updateContactSelection = (
  value: boolean,
  selectedCo: SelectedContactType,
  a: SelectedContactType[],
  setA: Dispatch<SetStateAction<SelectedContactType[]>>,
  index: number
) => {
  const newA = _.cloneDeep(
    a
      .slice(0, index)
      .concat([{ ...selectedCo, selected: value }])
      .concat(a.slice(index + 1))
  );
  setA(newA);
};

export const updateSearchContactSelection = (
  value: boolean,
  selectedCo: SelectedContactType,
  a: SelectedContactType[],
  searchA: SelectedContactType[],
  setA: Dispatch<SetStateAction<SelectedContactType[]>>,
  setSearchA: Dispatch<SetStateAction<SelectedContactType[]>>,
  searchIndex: number
) => {
  const findIndex = a?.findIndex((p) => p?.id === selectedCo?.id);

  if (findIndex > -1) {
    const newA = _.cloneDeep(
      a
        .slice(0, findIndex)
        .concat([{ ...selectedCo, selected: value }])
        .concat(a.slice(findIndex + 1))
    );
    setA(newA);
  }

  const newSearchA = _.cloneDeep(
    searchA
      .slice(0, searchIndex)
      .concat([{ ...selectedCo, selected: value }])
      .concat(a.slice(searchIndex + 1))
  );
  setSearchA(newSearchA);
};

export const updateEntryInManualEntries = (
  i: MeetingAssistInviteType[],
  setI: Dispatch<SetStateAction<MeetingAssistInviteType[]>>,
  index: number,
  invitees: MeetingAssistInviteType[],
  setInviteees: Dispatch<SetStateAction<MeetingAssistInviteType[]>>,
  setParentI: Dispatch<SetStateAction<MeetingAssistInviteType[]>>,
  parentIndex: number,
  email?: string,
  displayName?: string
) => {
  const oldDoc = i[index];
  const newDoc: MeetingAssistInviteType = {
    ...oldDoc,
    name: displayName || oldDoc?.name,
    email: email || oldDoc?.email,
  };

  const newI = i
    .slice(0, index)
    .concat([newDoc])
    .concat(i.slice(index + 1));
  setI(newI);
  const newInvitees = invitees
    .slice(0, parentIndex)
    .concat([newDoc])
    .concat(invitees.slice(parentIndex + 1));
  setInviteees(newInvitees);
  setParentI(newInvitees);
};
