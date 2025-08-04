"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.updateEntryInManualEntries = exports.updateSearchContactSelection = exports.updateContactSelection = exports.removeEntryFromManualEntries = exports.removeContactFromSearchInvitee = exports.removeContactFromInvitee = exports.addOneToManualEntries = exports.addContactToInvitees = exports.generateInviteLink = exports.sendMeetingInfoToHostEmail = exports.convertInviteeTypeToInviteEmailRecipients = exports.convertInviteeTypeToCancelEmailRecipients = exports.sendBulkMeetingInviteEmail = exports.sendBulkMeetingCancelEmail = exports.searchMeetingAssists = exports.generateDatesForFutureMeetingAssistsUsingRrule = exports.insertMeetingAssistPreferredTimeRanges = exports.upsertMeetingAssistInviteMany = exports.upsertMeetingAssistOne = exports.upsertMeetingAssistMany = exports.insertMeetingAssistAttendee = exports.updateUserNameGivenId = exports.deleteMeetingAssistGivenId = exports.getUserGivenId = exports.listUserMeetingAssistsGivenUserId = exports.getMeetingAssistGivenId = exports.listMeetingAssistInvitesGivenMeetingId = void 0;
const client_1 = require("@apollo/client");
const insertMeetingAssistPreferredTimeRangesMutation_1 = __importDefault(require("@lib/apollo/gql/insertMeetingAssistPreferredTimeRangesMutation"));
const rrule_1 = require("rrule");
const date_utils_1 = require("@lib/date-utils");
// lib/Calendar/UserCreateCalendarHelper.ts
const UserCreateCalendarHelper_1 = require("@lib/Calendar/UserCreateCalendarHelper");
const session_1 = __importDefault(require("supertokens-web-js/recipe/session"));
const constants_1 = require("@lib/Assist/constants");
const axios_1 = __importDefault(require("axios"));
const qs_1 = __importDefault(require("qs"));
const getUserById_1 = __importDefault(require("@lib/apollo/gql/getUserById"));
const uuid_1 = require("uuid");
const lodash_1 = __importDefault(require("lodash"));
const updateUserForName_1 = __importDefault(require("@lib/apollo/gql/updateUserForName"));
const listMeetingAssists_1 = __importDefault(require("@lib/apollo/gql/listMeetingAssists"));
const deleteMeetingAssistById_1 = __importDefault(require("@lib/apollo/gql/deleteMeetingAssistById"));
const listMeetingAssistInvites_1 = __importDefault(require("@lib/apollo/gql/listMeetingAssistInvites"));
const insertMeetingAssistAttendeeOne_1 = __importDefault(require("@lib/apollo/gql/insertMeetingAssistAttendeeOne"));
const getMeetingAssistById_1 = __importDefault(require("@lib/apollo/gql/getMeetingAssistById"));
const searchMeetingAssistsQuery_1 = __importDefault(require("@lib/apollo/gql/searchMeetingAssistsQuery"));
const listMeetingAssistInvitesGivenMeetingId = async (client, meetingId) => {
    try {
        const meetingAssistInvitesDoc = (await client.query({
            query: listMeetingAssistInvites_1.default,
            variables: {
                meetingId,
            },
        }))?.data?.Meeting_Assist_Invite;
        console.log(meetingAssistInvitesDoc, ' successfully listed meeting assist invites given meetingId');
        return meetingAssistInvitesDoc;
    }
    catch (e) {
        console.log(e, ' unable to list meeting assist invites given meetingId');
    }
};
exports.listMeetingAssistInvitesGivenMeetingId = listMeetingAssistInvitesGivenMeetingId;
const getMeetingAssistGivenId = async (client, meetingId) => {
    try {
        const meetingAssistDoc = (await client.query({
            query: getMeetingAssistById_1.default,
            variables: {
                id: meetingId,
            },
        }))?.data?.Meeting_Assist_by_pk;
        console.log(meetingAssistDoc, ' successfully got meetingAssistDoc');
        return meetingAssistDoc;
    }
    catch (e) {
        console.log(e, ' unable to get meeting assist given Id');
    }
};
exports.getMeetingAssistGivenId = getMeetingAssistGivenId;
const listUserMeetingAssistsGivenUserId = async (client, userId) => {
    try {
        const meetingAssists = (await client.query({
            query: listMeetingAssists_1.default,
            variables: {
                userId,
            },
        }))?.data?.Meeting_Assist;
        console.log(meetingAssists, ' successfully returned meeting assists');
        return meetingAssists;
    }
    catch (e) {
        console.log(e, ' unable to list user meeting assists given userId');
    }
};
exports.listUserMeetingAssistsGivenUserId = listUserMeetingAssistsGivenUserId;
const getUserGivenId = async (client, userId) => {
    try {
        const existingUser = (await client.query({
            query: getUserById_1.default,
            variables: {
                id: userId,
            },
        }))?.data?.User_by_pk;
        console.log(existingUser, ' successfully gotten userId');
        return existingUser;
    }
    catch (e) {
        console.log(e, ' unable to get user given Id inside getUserGivenId');
    }
};
exports.getUserGivenId = getUserGivenId;
const deleteMeetingAssistGivenId = async (client, id) => {
    try {
        const deletedMeetingAssistDoc = (await client.mutate({
            mutation: deleteMeetingAssistById_1.default,
            variables: {
                id,
            },
        }))?.data?.delete_Meeting_Assist_by_pk;
        console.log(deletedMeetingAssistDoc, ' successfully deleted meeting assist doc');
    }
    catch (e) {
        console.log(e, ' unable to delete meeting assist given id');
    }
};
exports.deleteMeetingAssistGivenId = deleteMeetingAssistGivenId;
const updateUserNameGivenId = async (client, userId, name) => {
    try {
        const userDoc = (await client.mutate({
            mutation: updateUserForName_1.default,
            variables: {
                id: userId,
                name,
            },
        }))?.data?.update_User_by_pk;
        console.log(userDoc, ' successfully updated userDoc');
    }
    catch (e) {
        console.log(e, ' uanble to update user name given id');
    }
};
exports.updateUserNameGivenId = updateUserNameGivenId;
const insertMeetingAssistAttendee = async (client, attendee) => {
    try {
        const meetingAssistAttendeeDoc = (await client.mutate({
            mutation: insertMeetingAssistAttendeeOne_1.default,
            variables: {
                attendee,
            },
        }))?.data?.insert_Meeting_Assist_Attendee_one;
        console.log(meetingAssistAttendeeDoc, ' successfully inserted meeting assist attendee');
        return meetingAssistAttendeeDoc;
    }
    catch (e) {
        console.log(e, ' unable to insert attendee one');
    }
};
exports.insertMeetingAssistAttendee = insertMeetingAssistAttendee;
const upsertMeetingAssistMany = async (client, meetingAssists) => {
    try {
        console.log(meetingAssists, ' meetingAssistsinside upsertMeetingAssistMany');
        // ASSUMPTION: A custom mutation 'bulkUpsertMeetingAssists' is defined in PostGraphile (e.g., via a PG function)
        // that takes an array of MeetingAssistInput and handles the upsert logic.
        // The return type will also depend on the custom function's definition.
        // The list of columns in on_conflict is now implicit in the PG function.
        const upsertMeetingAssistsMutation = (0, client_1.gql) `
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
        const meetingAssistsDataDoc = (await client.mutate({
            mutation: upsertMeetingAssistsMutation,
            variables: {
                assists: meetingAssists, // Variable name changed
            },
        }))?.data?.bulkUpsertMeetingAssists;
        // This access will likely need to change:
        console.log(meetingAssistsDataDoc?.results?.length, ' successfully created multiple meeting assists');
        return meetingAssistsDataDoc?.results?.length; // Or however the count/results are returned
    }
    catch (e) {
        console.log(e, ' unable to upsert meeting assist many');
    }
};
exports.upsertMeetingAssistMany = upsertMeetingAssistMany;
const upsertMeetingAssistOne = async (client, meetingAssist // This might need to be MeetingAssistInput
) => {
    try {
        console.log(meetingAssist, ' meetingAssist inside upsertMeetingAssistOne');
        // ASSUMPTION: A custom mutation 'upsertMeetingAssist' is defined in PostGraphile (e.g., via a PG function)
        // OR we use separate createMeetingAssist and updateMeetingAssist mutations.
        // Given 'on_conflict', an upsert is intended.
        // PostGraphile input types are typically like `MeetingAssistInput` for create and `MeetingAssistPatch` for update.
        // A custom upsert might take `MeetingAssistInput`.
        const upsertMeetingAssistGraphql = (0, client_1.gql) `
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
        const meetingAssistDoc = (await client.mutate({
            mutation: upsertMeetingAssistGraphql,
            variables: {
                // This structure depends on how the PostGraphile mutation `upsertMeetingAssist` is defined.
                // Assuming it takes an 'input' object which then has a 'meetingAssist' field of the correct input type.
                input: { meetingAssist: meetingAssist },
            },
        }))?.data?.upsertMeetingAssist?.meetingAssist;
        console.log(meetingAssistDoc, ' successfully added meetingAssistDoc');
        return meetingAssistDoc;
    }
    catch (e) {
        console.log(e, ' unable to upsert meeting assist');
    }
};
exports.upsertMeetingAssistOne = upsertMeetingAssistOne;
const upsertMeetingAssistInviteMany = async (client, meetingAssistInvites // This might need to be MeetingAssistInviteInput[]
) => {
    try {
        // ASSUMPTION: A custom mutation 'bulkUpsertMeetingAssistInvites' is defined in PostGraphile
        const upsertMeetingAssistInviteGraphql = (0, client_1.gql) `
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
        const meetingAssistInviteDocData = (await client.mutate({
            mutation: upsertMeetingAssistInviteGraphql,
            variables: {
                invites: meetingAssistInvites,
            },
        }))?.data?.bulkUpsertMeetingAssistInvites;
        console.log(meetingAssistInviteDocData?.results?.length, ' successfully inserted meetingAssistInviteDocs');
        return meetingAssistInviteDocData?.results?.length;
    }
    catch (e) {
        console.log(e, ' unable to upsert meeting assist invite');
    }
};
exports.upsertMeetingAssistInviteMany = upsertMeetingAssistInviteMany;
const insertMeetingAssistPreferredTimeRanges = async (client, meetingAssistPreferredTimeRanges) => {
    try {
        const meetingAssistInviteDocData = (await client.mutate({
            mutation: insertMeetingAssistPreferredTimeRangesMutation_1.default,
            variables: {
                meetingAssistPreferredTimeRanges,
            },
        }))?.data?.insert_Meeting_Assist_Preferred_Time_Range;
        console.log(meetingAssistInviteDocData?.affected_rows, ' successfully inserted meeting assist time ranges ');
        return meetingAssistInviteDocData?.affected_rows;
    }
    catch (e) {
        console.log(e, ' unable to upsert meeting assist preferred time ranges');
    }
};
exports.insertMeetingAssistPreferredTimeRanges = insertMeetingAssistPreferredTimeRanges;
const generateDatesForFutureMeetingAssistsUsingRrule = async (windowStartDate, windowEndDate, frequency, interval, until) => {
    try {
        const ruleStartDate = new rrule_1.RRule({
            dtstart: (0, date_utils_1.dayjs)(windowStartDate).toDate(),
            freq: (0, UserCreateCalendarHelper_1.getRruleFreq)(frequency),
            interval,
            until: (0, date_utils_1.dayjs)(until).toDate(),
        });
        const windowStartDatesForRecurrence = ruleStartDate
            .all()
            ?.map((d) => date_utils_1.dayjs.utc(d).format());
        const ruleEndDate = new rrule_1.RRule({
            dtstart: (0, date_utils_1.dayjs)(windowEndDate).toDate(),
            freq: (0, UserCreateCalendarHelper_1.getRruleFreq)(frequency),
            interval,
            until: (0, date_utils_1.dayjs)(until).toDate(),
        });
        const windowEndDatesForRecurrence = ruleEndDate
            .all()
            ?.map((d) => date_utils_1.dayjs.utc(d).format());
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
    }
    catch (e) {
        console.log(e, ' generate dates for meeting assists recurrence');
    }
};
exports.generateDatesForFutureMeetingAssistsUsingRrule = generateDatesForFutureMeetingAssistsUsingRrule;
const searchMeetingAssists = async (client, userId, summary) => {
    try {
        const formattedSummary = `%${summary}%`;
        const results = (await client.query({
            query: searchMeetingAssistsQuery_1.default,
            variables: {
                userId,
                name: formattedSummary,
            },
            fetchPolicy: 'no-cache',
        }))?.data?.Meeting_Assist;
        console.log(results, ' results inside searchMeetingAssists');
        return results;
    }
    catch (e) {
        console.log(e, ' unable to search meeting assists');
    }
};
exports.searchMeetingAssists = searchMeetingAssists;
const sendBulkMeetingCancelEmail = async (attendees, hostEmail, hostName) => {
    try {
        const url = constants_1.emailMeetingCancelUrl;
        const accessToken = await session_1.default.getAccessToken();
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
        const results = await axios_1.default.post(url, data, config);
        console.log(results, ' succesfully sent cancel notifications for meeting assist');
    }
    catch (e) {
        console.log(e, ' unable to send bulk meeting cancel meeting');
    }
};
exports.sendBulkMeetingCancelEmail = sendBulkMeetingCancelEmail;
const sendBulkMeetingInviteEmail = async (attendees, hostEmail, hostName) => {
    try {
        console.log(attendees, ' AttendeeDetailsForBulkMeetingInviteType inside sendBulkMeetingInviteEmail');
        const url = constants_1.emailMeetingInviteUrl;
        const accessToken = await session_1.default.getAccessToken();
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
        const results = await axios_1.default.post(url, data, config);
        console.log(results, ' successfully sent to email to invites');
    }
    catch (e) {
        console.log(e, ' unable to send bulk meeting invite email');
    }
};
exports.sendBulkMeetingInviteEmail = sendBulkMeetingInviteEmail;
const convertInviteeTypeToCancelEmailRecipients = (invitees) => {
    const cancelEmails = invitees?.map((i) => ({
        email: i?.email || '',
        name: i?.name,
    }));
    return cancelEmails;
};
exports.convertInviteeTypeToCancelEmailRecipients = convertInviteeTypeToCancelEmailRecipients;
const convertInviteeTypeToInviteEmailRecipients = (invitees, meetingId) => {
    const inviteeEmails = invitees?.map((i) => ({
        email: i?.email || '',
        name: i?.name,
        link: (0, exports.generateInviteLink)(meetingId, i?.id, i?.email),
    }));
    return inviteeEmails;
};
exports.convertInviteeTypeToInviteEmailRecipients = convertInviteeTypeToInviteEmailRecipients;
const sendMeetingInfoToHostEmail = async (attendees, hostEmail, hostName, title, notes, windowStartDate, windowEndDate, timezone) => {
    try {
        console.log(attendees, ' AttendeeDetailsType inside sendMeetingInfoToHostEmail');
        const accessToken = await session_1.default.getAccessToken();
        const config = {
            headers: {
                Authorization: `Bearer ${accessToken}`,
                'Content-Type': 'application/json',
            },
        };
        const data = {
            attendees,
            hostEmail,
            hostName,
            title,
            notes,
            windowStartDate,
            windowEndDate,
            timezone,
        };
        const url = constants_1.emailMeetingInfoToHostUrl;
        const results = await axios_1.default.post(url, data, config);
        console.log(results, ' successfully sent email to host');
    }
    catch (e) {
        console.log(e, ' unable to send email to host');
    }
};
exports.sendMeetingInfoToHostEmail = sendMeetingInfoToHostEmail;
const generateInviteLink = (meetingId, attendeeId, primaryEmail) => (primaryEmail &&
    `${constants_1.handshakeUrl}?${qs_1.default.stringify({ meetingId, attendeeId, primaryEmail })}`) ||
    `${constants_1.handshakeUrl}?${qs_1.default.stringify({ meetingId, attendeeId })}`;
exports.generateInviteLink = generateInviteLink;
const addContactToInvitees = (c, invitees, setI, setParentI, hostId, hostName, meetingId) => {
    const formattedC = {
        id: (0, uuid_1.v4)(),
        name: c?.name || '',
        email: c?.emails?.find((e) => e?.primary)?.value,
        hostId,
        hostName,
        meetingId,
        createdDate: (0, date_utils_1.dayjs)().format(),
        updatedAt: (0, date_utils_1.dayjs)().format(),
        userId: c?.userId,
        contactId: c?.id,
    };
    const newInvitees = invitees.concat([formattedC]);
    setI(newInvitees);
    setParentI(newInvitees);
};
exports.addContactToInvitees = addContactToInvitees;
const addOneToManualEntries = (i, setI, invitees, setInvitees, setParentI, hostId, hostName, meetingId) => {
    const newValue = {
        id: (0, uuid_1.v4)(),
        hostId,
        email: '',
        hostName,
        meetingId,
        name: '',
        createdDate: (0, date_utils_1.dayjs)().format(),
        updatedAt: (0, date_utils_1.dayjs)().format(),
    };
    const newMe = lodash_1.default.uniqWith(i.concat([newValue]), lodash_1.default.isEqual);
    setI(newMe);
    const newInvitees = lodash_1.default.uniqWith(invitees.concat([newValue]), lodash_1.default.isEqual);
    setInvitees(newInvitees);
    setParentI(newInvitees);
};
exports.addOneToManualEntries = addOneToManualEntries;
const removeContactFromInvitee = (c, invitees, setInvitees, setParentI) => {
    const foundIndex = invitees.findIndex((a) => a?.id === c?.id);
    if (foundIndex > -1) {
        const newAttendees = invitees
            .slice(0, foundIndex)
            .concat(invitees.slice(foundIndex + 1));
        setInvitees(newAttendees);
        setParentI(newAttendees);
    }
};
exports.removeContactFromInvitee = removeContactFromInvitee;
const removeContactFromSearchInvitee = (c, invitees, searchResults, setInvitees, setSearchResults, setParentI) => {
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
exports.removeContactFromSearchInvitee = removeContactFromSearchInvitee;
const removeEntryFromManualEntries = (manualEntries, setManualEntries, invitees, setInvitees, setParentI, index, parentIndex) => {
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
exports.removeEntryFromManualEntries = removeEntryFromManualEntries;
const updateContactSelection = (value, selectedCo, a, setA, index) => {
    const newA = lodash_1.default.cloneDeep(a
        .slice(0, index)
        .concat([{ ...selectedCo, selected: value }])
        .concat(a.slice(index + 1)));
    setA(newA);
};
exports.updateContactSelection = updateContactSelection;
const updateSearchContactSelection = (value, selectedCo, a, searchA, setA, setSearchA, searchIndex) => {
    const findIndex = a?.findIndex((p) => p?.id === selectedCo?.id);
    if (findIndex > -1) {
        const newA = lodash_1.default.cloneDeep(a
            .slice(0, findIndex)
            .concat([{ ...selectedCo, selected: value }])
            .concat(a.slice(findIndex + 1)));
        setA(newA);
    }
    const newSearchA = lodash_1.default.cloneDeep(searchA
        .slice(0, searchIndex)
        .concat([{ ...selectedCo, selected: value }])
        .concat(a.slice(searchIndex + 1)));
    setSearchA(newSearchA);
};
exports.updateSearchContactSelection = updateSearchContactSelection;
const updateEntryInManualEntries = (i, setI, index, invitees, setInviteees, setParentI, parentIndex, email, displayName) => {
    const oldDoc = i[index];
    const newDoc = {
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
exports.updateEntryInManualEntries = updateEntryInManualEntries;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlck1lZXRpbmdBc3Npc3RIZWxwZXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJVc2VyTWVldGluZ0Fzc2lzdEhlbHBlci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7QUFBQSwyQ0FBMEU7QUFDMUUsb0pBQTRIO0FBSTVILGlDQUE4QjtBQUM5QixnREFBd0M7QUFFeEMsMkNBQTJDO0FBQzNDLHFGQUdnRDtBQU9oRCxnRkFBd0Q7QUFDeEQscURBSytCO0FBQy9CLGtEQUEwQjtBQUMxQiw0Q0FBb0I7QUFJcEIsOEVBQXNEO0FBTXRELCtCQUFrQztBQUNsQyxvREFBdUI7QUFFdkIsMEZBQWtFO0FBQ2xFLDRGQUFvRTtBQUNwRSxzR0FBOEU7QUFDOUUsd0dBQWdGO0FBQ2hGLG9IQUE0RjtBQUM1RixnR0FBd0U7QUFDeEUsMEdBQWtGO0FBRTNFLE1BQU0sc0NBQXNDLEdBQUcsS0FBSyxFQUN6RCxNQUEyQyxFQUMzQyxTQUFpQixFQUNqQixFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSx1QkFBdUIsR0FBRyxDQUM5QixNQUFNLE1BQU0sQ0FBQyxLQUFLLENBQXVEO1lBQ3ZFLEtBQUssRUFBRSxrQ0FBd0I7WUFDL0IsU0FBUyxFQUFFO2dCQUNULFNBQVM7YUFDVjtTQUNGLENBQUMsQ0FDSCxFQUFFLElBQUksRUFBRSxxQkFBcUIsQ0FBQztRQUUvQixPQUFPLENBQUMsR0FBRyxDQUNULHVCQUF1QixFQUN2Qiw2REFBNkQsQ0FDOUQsQ0FBQztRQUVGLE9BQU8sdUJBQXVCLENBQUM7SUFDakMsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSx3REFBd0QsQ0FBQyxDQUFDO0lBQzNFLENBQUM7QUFDSCxDQUFDLENBQUM7QUF2QlcsUUFBQSxzQ0FBc0MsMENBdUJqRDtBQUVLLE1BQU0sdUJBQXVCLEdBQUcsS0FBSyxFQUMxQyxNQUEyQyxFQUMzQyxTQUFpQixFQUNqQixFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSxnQkFBZ0IsR0FBRyxDQUN2QixNQUFNLE1BQU0sQ0FBQyxLQUFLLENBQThDO1lBQzlELEtBQUssRUFBRSw4QkFBb0I7WUFDM0IsU0FBUyxFQUFFO2dCQUNULEVBQUUsRUFBRSxTQUFTO2FBQ2Q7U0FDRixDQUFDLENBQ0gsRUFBRSxJQUFJLEVBQUUsb0JBQW9CLENBQUM7UUFFOUIsT0FBTyxDQUFDLEdBQUcsQ0FBQyxnQkFBZ0IsRUFBRSxvQ0FBb0MsQ0FBQyxDQUFDO1FBQ3BFLE9BQU8sZ0JBQWdCLENBQUM7SUFDMUIsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSx3Q0FBd0MsQ0FBQyxDQUFDO0lBQzNELENBQUM7QUFDSCxDQUFDLENBQUM7QUFuQlcsUUFBQSx1QkFBdUIsMkJBbUJsQztBQUVLLE1BQU0saUNBQWlDLEdBQUcsS0FBSyxFQUNwRCxNQUEyQyxFQUMzQyxNQUFjLEVBQ2QsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sY0FBYyxHQUFHLENBQ3JCLE1BQU0sTUFBTSxDQUFDLEtBQUssQ0FBMEM7WUFDMUQsS0FBSyxFQUFFLDRCQUFrQjtZQUN6QixTQUFTLEVBQUU7Z0JBQ1QsTUFBTTthQUNQO1NBQ0YsQ0FBQyxDQUNILEVBQUUsSUFBSSxFQUFFLGNBQWMsQ0FBQztRQUV4QixPQUFPLENBQUMsR0FBRyxDQUFDLGNBQWMsRUFBRSx3Q0FBd0MsQ0FBQyxDQUFDO1FBRXRFLE9BQU8sY0FBYyxDQUFDO0lBQ3hCLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsbURBQW1ELENBQUMsQ0FBQztJQUN0RSxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBcEJXLFFBQUEsaUNBQWlDLHFDQW9CNUM7QUFFSyxNQUFNLGNBQWMsR0FBRyxLQUFLLEVBQ2pDLE1BQTJDLEVBQzNDLE1BQWMsRUFDZCxFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSxZQUFZLEdBQUcsQ0FDbkIsTUFBTSxNQUFNLENBQUMsS0FBSyxDQUEyQjtZQUMzQyxLQUFLLEVBQUUscUJBQVc7WUFDbEIsU0FBUyxFQUFFO2dCQUNULEVBQUUsRUFBRSxNQUFNO2FBQ1g7U0FDRixDQUFDLENBQ0gsRUFBRSxJQUFJLEVBQUUsVUFBVSxDQUFDO1FBRXBCLE9BQU8sQ0FBQyxHQUFHLENBQUMsWUFBWSxFQUFFLDZCQUE2QixDQUFDLENBQUM7UUFFekQsT0FBTyxZQUFZLENBQUM7SUFDdEIsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxvREFBb0QsQ0FBQyxDQUFDO0lBQ3ZFLENBQUM7QUFDSCxDQUFDLENBQUM7QUFwQlcsUUFBQSxjQUFjLGtCQW9CekI7QUFFSyxNQUFNLDBCQUEwQixHQUFHLEtBQUssRUFDN0MsTUFBMkMsRUFDM0MsRUFBVSxFQUNWLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxNQUFNLHVCQUF1QixHQUFHLENBQzlCLE1BQU0sTUFBTSxDQUFDLE1BQU0sQ0FBcUQ7WUFDdEUsUUFBUSxFQUFFLGlDQUF1QjtZQUNqQyxTQUFTLEVBQUU7Z0JBQ1QsRUFBRTthQUNIO1NBQ0YsQ0FBQyxDQUNILEVBQUUsSUFBSSxFQUFFLDJCQUEyQixDQUFDO1FBRXJDLE9BQU8sQ0FBQyxHQUFHLENBQ1QsdUJBQXVCLEVBQ3ZCLDBDQUEwQyxDQUMzQyxDQUFDO0lBQ0osQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSwyQ0FBMkMsQ0FBQyxDQUFDO0lBQzlELENBQUM7QUFDSCxDQUFDLENBQUM7QUFyQlcsUUFBQSwwQkFBMEIsOEJBcUJyQztBQUVLLE1BQU0scUJBQXFCLEdBQUcsS0FBSyxFQUN4QyxNQUEyQyxFQUMzQyxNQUFjLEVBQ2QsSUFBWSxFQUNaLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxNQUFNLE9BQU8sR0FBRyxDQUNkLE1BQU0sTUFBTSxDQUFDLE1BQU0sQ0FBa0M7WUFDbkQsUUFBUSxFQUFFLDJCQUFpQjtZQUMzQixTQUFTLEVBQUU7Z0JBQ1QsRUFBRSxFQUFFLE1BQU07Z0JBQ1YsSUFBSTthQUNMO1NBQ0YsQ0FBQyxDQUNILEVBQUUsSUFBSSxFQUFFLGlCQUFpQixDQUFDO1FBRTNCLE9BQU8sQ0FBQyxHQUFHLENBQUMsT0FBTyxFQUFFLCtCQUErQixDQUFDLENBQUM7SUFDeEQsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxzQ0FBc0MsQ0FBQyxDQUFDO0lBQ3pELENBQUM7QUFDSCxDQUFDLENBQUM7QUFwQlcsUUFBQSxxQkFBcUIseUJBb0JoQztBQUVLLE1BQU0sMkJBQTJCLEdBQUcsS0FBSyxFQUM5QyxNQUEyQyxFQUMzQyxRQUFtQyxFQUNuQyxFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSx3QkFBd0IsR0FBRyxDQUMvQixNQUFNLE1BQU0sQ0FBQyxNQUFNLENBRWhCO1lBQ0QsUUFBUSxFQUFFLHdDQUE4QjtZQUN4QyxTQUFTLEVBQUU7Z0JBQ1QsUUFBUTthQUNUO1NBQ0YsQ0FBQyxDQUNILEVBQUUsSUFBSSxFQUFFLGtDQUFrQyxDQUFDO1FBRTVDLE9BQU8sQ0FBQyxHQUFHLENBQ1Qsd0JBQXdCLEVBQ3hCLGdEQUFnRCxDQUNqRCxDQUFDO1FBRUYsT0FBTyx3QkFBd0IsQ0FBQztJQUNsQyxDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLGdDQUFnQyxDQUFDLENBQUM7SUFDbkQsQ0FBQztBQUNILENBQUMsQ0FBQztBQXpCVyxRQUFBLDJCQUEyQiwrQkF5QnRDO0FBRUssTUFBTSx1QkFBdUIsR0FBRyxLQUFLLEVBQzFDLE1BQTJDLEVBQzNDLGNBQW1DLEVBQ25DLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxPQUFPLENBQUMsR0FBRyxDQUNULGNBQWMsRUFDZCwrQ0FBK0MsQ0FDaEQsQ0FBQztRQUNGLGdIQUFnSDtRQUNoSCwwRUFBMEU7UUFDMUUsd0VBQXdFO1FBQ3hFLHlFQUF5RTtRQUN6RSxNQUFNLDRCQUE0QixHQUFHLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7S0ErRHZDLENBQUM7UUFDRiw0RkFBNEY7UUFDNUYsdUhBQXVIO1FBQ3ZILDBFQUEwRTtRQUMxRSxNQUFNLHFCQUFxQixHQUFHLENBQzVCLE1BQU0sTUFBTSxDQUFDLE1BQU0sQ0FJaEI7WUFDRCxRQUFRLEVBQUUsNEJBQTRCO1lBQ3RDLFNBQVMsRUFBRTtnQkFDVCxPQUFPLEVBQUUsY0FBYyxFQUFFLHdCQUF3QjthQUNsRDtTQUNGLENBQUMsQ0FDSCxFQUFFLElBQUksRUFBRSx3QkFBd0IsQ0FBQztRQUVsQywwQ0FBMEM7UUFDMUMsT0FBTyxDQUFDLEdBQUcsQ0FDVCxxQkFBcUIsRUFBRSxPQUFPLEVBQUUsTUFBTSxFQUN0QyxnREFBZ0QsQ0FDakQsQ0FBQztRQUNGLE9BQU8scUJBQXFCLEVBQUUsT0FBTyxFQUFFLE1BQU0sQ0FBQyxDQUFDLDRDQUE0QztJQUM3RixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLHVDQUF1QyxDQUFDLENBQUM7SUFDMUQsQ0FBQztBQUNILENBQUMsQ0FBQztBQXRHVyxRQUFBLHVCQUF1QiwyQkFzR2xDO0FBRUssTUFBTSxzQkFBc0IsR0FBRyxLQUFLLEVBQ3pDLE1BQTJDLEVBQzNDLGFBQWdDLENBQUMsMkNBQTJDO0VBQzVFLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxPQUFPLENBQUMsR0FBRyxDQUFDLGFBQWEsRUFBRSw4Q0FBOEMsQ0FBQyxDQUFDO1FBQzNFLDJHQUEyRztRQUMzRyw0RUFBNEU7UUFDNUUsOENBQThDO1FBQzlDLG1IQUFtSDtRQUNuSCxtREFBbUQ7UUFDbkQsTUFBTSwwQkFBMEIsR0FBRyxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7S0F3RHJDLENBQUM7UUFDRix5RUFBeUU7UUFDekUsbUZBQW1GO1FBQ25GLHlFQUF5RTtRQUN6RSw4RUFBOEU7UUFDOUUsOEZBQThGO1FBQzlGLE1BQU0sZ0JBQWdCLEdBQUcsQ0FDdkIsTUFBTSxNQUFNLENBQUMsTUFBTSxDQUVoQjtZQUNELFFBQVEsRUFBRSwwQkFBMEI7WUFDcEMsU0FBUyxFQUFFO2dCQUNULDRGQUE0RjtnQkFDNUYsd0dBQXdHO2dCQUN4RyxLQUFLLEVBQUUsRUFBRSxhQUFhLEVBQUUsYUFBYSxFQUFFO2FBQ3hDO1NBQ0YsQ0FBQyxDQUNILEVBQUUsSUFBSSxFQUFFLG1CQUFtQixFQUFFLGFBQWEsQ0FBQztRQUU1QyxPQUFPLENBQUMsR0FBRyxDQUFDLGdCQUFnQixFQUFFLHNDQUFzQyxDQUFDLENBQUM7UUFFdEUsT0FBTyxnQkFBZ0IsQ0FBQztJQUMxQixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLGtDQUFrQyxDQUFDLENBQUM7SUFDckQsQ0FBQztBQUNILENBQUMsQ0FBQztBQTVGVyxRQUFBLHNCQUFzQiwwQkE0RmpDO0FBRUssTUFBTSw2QkFBNkIsR0FBRyxLQUFLLEVBQ2hELE1BQTJDLEVBQzNDLG9CQUErQyxDQUFDLG1EQUFtRDtFQUNuRyxFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsNEZBQTRGO1FBQzVGLE1BQU0sZ0NBQWdDLEdBQUcsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7S0F5QjNDLENBQUM7UUFDRixtRkFBbUY7UUFDbkYsTUFBTSwwQkFBMEIsR0FBRyxDQUNqQyxNQUFNLE1BQU0sQ0FBQyxNQUFNLENBRWhCO1lBQ0QsUUFBUSxFQUFFLGdDQUFnQztZQUMxQyxTQUFTLEVBQUU7Z0JBQ1QsT0FBTyxFQUFFLG9CQUFvQjthQUM5QjtTQUNGLENBQUMsQ0FDSCxFQUFFLElBQUksRUFBRSw4QkFBOEIsQ0FBQztRQUV4QyxPQUFPLENBQUMsR0FBRyxDQUNULDBCQUEwQixFQUFFLE9BQU8sRUFBRSxNQUFNLEVBQzNDLGdEQUFnRCxDQUNqRCxDQUFDO1FBQ0YsT0FBTywwQkFBMEIsRUFBRSxPQUFPLEVBQUUsTUFBTSxDQUFDO0lBQ3JELENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUseUNBQXlDLENBQUMsQ0FBQztJQUM1RCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBcERXLFFBQUEsNkJBQTZCLGlDQW9EeEM7QUFFSyxNQUFNLHNDQUFzQyxHQUFHLEtBQUssRUFDekQsTUFBMkMsRUFDM0MsZ0NBQXVFLEVBQ3ZFLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxNQUFNLDBCQUEwQixHQUFHLENBQ2pDLE1BQU0sTUFBTSxDQUFDLE1BQU0sQ0FLaEI7WUFDRCxRQUFRLEVBQUUsd0RBQThDO1lBQ3hELFNBQVMsRUFBRTtnQkFDVCxnQ0FBZ0M7YUFDakM7U0FDRixDQUFDLENBQ0gsRUFBRSxJQUFJLEVBQUUsMENBQTBDLENBQUM7UUFFcEQsT0FBTyxDQUFDLEdBQUcsQ0FDVCwwQkFBMEIsRUFBRSxhQUFhLEVBQ3pDLG9EQUFvRCxDQUNyRCxDQUFDO1FBRUYsT0FBTywwQkFBMEIsRUFBRSxhQUFhLENBQUM7SUFDbkQsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSx3REFBd0QsQ0FBQyxDQUFDO0lBQzNFLENBQUM7QUFDSCxDQUFDLENBQUM7QUE1QlcsUUFBQSxzQ0FBc0MsMENBNEJqRDtBQUVLLE1BQU0sOENBQThDLEdBQUcsS0FBSyxFQUNqRSxlQUF1QixFQUN2QixhQUFxQixFQUNyQixTQUFrQyxFQUNsQyxRQUFnQixFQUNoQixLQUFhLEVBQ2IsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sYUFBYSxHQUFHLElBQUksYUFBSyxDQUFDO1lBQzlCLE9BQU8sRUFBRSxJQUFBLGtCQUFLLEVBQUMsZUFBZSxDQUFDLENBQUMsTUFBTSxFQUFFO1lBQ3hDLElBQUksRUFBRSxJQUFBLHVDQUFZLEVBQUMsU0FBUyxDQUFDO1lBQzdCLFFBQVE7WUFDUixLQUFLLEVBQUUsSUFBQSxrQkFBSyxFQUFDLEtBQUssQ0FBQyxDQUFDLE1BQU0sRUFBRTtTQUM3QixDQUFDLENBQUM7UUFFSCxNQUFNLDZCQUE2QixHQUFHLGFBQWE7YUFDaEQsR0FBRyxFQUFFO1lBQ04sRUFBRSxHQUFHLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLGtCQUFLLENBQUMsR0FBRyxDQUFDLENBQUMsQ0FBQyxDQUFDLE1BQU0sRUFBRSxDQUFDLENBQUM7UUFFdEMsTUFBTSxXQUFXLEdBQUcsSUFBSSxhQUFLLENBQUM7WUFDNUIsT0FBTyxFQUFFLElBQUEsa0JBQUssRUFBQyxhQUFhLENBQUMsQ0FBQyxNQUFNLEVBQUU7WUFDdEMsSUFBSSxFQUFFLElBQUEsdUNBQVksRUFBQyxTQUFTLENBQUM7WUFDN0IsUUFBUTtZQUNSLEtBQUssRUFBRSxJQUFBLGtCQUFLLEVBQUMsS0FBSyxDQUFDLENBQUMsTUFBTSxFQUFFO1NBQzdCLENBQUMsQ0FBQztRQUVILE1BQU0sMkJBQTJCLEdBQUcsV0FBVzthQUM1QyxHQUFHLEVBQUU7WUFDTixFQUFFLEdBQUcsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsa0JBQUssQ0FBQyxHQUFHLENBQUMsQ0FBQyxDQUFDLENBQUMsTUFBTSxFQUFFLENBQUMsQ0FBQztRQUV0QyxvREFBb0Q7UUFDcEQsTUFBTSxXQUFXLEdBQUcsNkJBQTZCO1lBQy9DLEVBQUUsS0FBSyxDQUFDLENBQUMsRUFBRSwyQkFBMkIsRUFBRSxNQUFNLENBQUM7WUFDL0MsRUFBRSxHQUFHLENBQUMsQ0FBQyxlQUFlLEVBQUUsR0FBRyxFQUFFLEVBQUU7WUFDN0IsT0FBTztnQkFDTCxlQUFlO2dCQUNmLGFBQWEsRUFBRSwyQkFBMkIsRUFBRSxDQUFDLEdBQUcsQ0FBQzthQUNsRCxDQUFDO1FBQ0osQ0FBQyxDQUFDLENBQUM7UUFFTCxPQUFPLFdBQVcsQ0FBQztJQUNyQixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLGdEQUFnRCxDQUFDLENBQUM7SUFDbkUsQ0FBQztBQUNILENBQUMsQ0FBQztBQTVDVyxRQUFBLDhDQUE4QyxrREE0Q3pEO0FBRUssTUFBTSxvQkFBb0IsR0FBRyxLQUFLLEVBQ3ZDLE1BQTJDLEVBQzNDLE1BQWMsRUFDZCxPQUFlLEVBQ2dDLEVBQUU7SUFDakQsSUFBSSxDQUFDO1FBQ0gsTUFBTSxnQkFBZ0IsR0FBRyxJQUFJLE9BQU8sR0FBRyxDQUFDO1FBRXhDLE1BQU0sT0FBTyxHQUFHLENBQ2QsTUFBTSxNQUFNLENBQUMsS0FBSyxDQUEwQztZQUMxRCxLQUFLLEVBQUUsbUNBQXlCO1lBQ2hDLFNBQVMsRUFBRTtnQkFDVCxNQUFNO2dCQUNOLElBQUksRUFBRSxnQkFBZ0I7YUFDdkI7WUFDRCxXQUFXLEVBQUUsVUFBVTtTQUN4QixDQUFDLENBQ0gsRUFBRSxJQUFJLEVBQUUsY0FBYyxDQUFDO1FBRXhCLE9BQU8sQ0FBQyxHQUFHLENBQUMsT0FBTyxFQUFFLHNDQUFzQyxDQUFDLENBQUM7UUFFN0QsT0FBTyxPQUFPLENBQUM7SUFDakIsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxtQ0FBbUMsQ0FBQyxDQUFDO0lBQ3RELENBQUM7QUFDSCxDQUFDLENBQUM7QUF6QlcsUUFBQSxvQkFBb0Isd0JBeUIvQjtBQUVLLE1BQU0sMEJBQTBCLEdBQUcsS0FBSyxFQUM3QyxTQUF1RCxFQUN2RCxTQUFpQixFQUNqQixRQUFnQixFQUNoQixFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSxHQUFHLEdBQUcsaUNBQXFCLENBQUM7UUFFbEMsTUFBTSxXQUFXLEdBQUcsTUFBTSxpQkFBTyxDQUFDLGNBQWMsRUFBRSxDQUFDO1FBRW5ELE1BQU0sTUFBTSxHQUFHO1lBQ2IsT0FBTyxFQUFFO2dCQUNQLGFBQWEsRUFBRSxVQUFVLFdBQVcsRUFBRTtnQkFDdEMsY0FBYyxFQUFFLGtCQUFrQjthQUNuQztTQUNGLENBQUM7UUFFRixNQUFNLElBQUksR0FBRztZQUNYLFNBQVM7WUFDVCxRQUFRO1lBQ1IsU0FBUztTQUNWLENBQUM7UUFFRixNQUFNLE9BQU8sR0FBRyxNQUFNLGVBQUssQ0FBQyxJQUFJLENBQUMsR0FBRyxFQUFFLElBQUksRUFBRSxNQUFNLENBQUMsQ0FBQztRQUVwRCxPQUFPLENBQUMsR0FBRyxDQUNULE9BQU8sRUFDUCwyREFBMkQsQ0FDNUQsQ0FBQztJQUNKLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsNkNBQTZDLENBQUMsQ0FBQztJQUNoRSxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBaENXLFFBQUEsMEJBQTBCLDhCQWdDckM7QUFFSyxNQUFNLDBCQUEwQixHQUFHLEtBQUssRUFDN0MsU0FBb0QsRUFDcEQsU0FBaUIsRUFDakIsUUFBZ0IsRUFDaEIsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE9BQU8sQ0FBQyxHQUFHLENBQ1QsU0FBUyxFQUNULDRFQUE0RSxDQUM3RSxDQUFDO1FBRUYsTUFBTSxHQUFHLEdBQUcsaUNBQXFCLENBQUM7UUFFbEMsTUFBTSxXQUFXLEdBQUcsTUFBTSxpQkFBTyxDQUFDLGNBQWMsRUFBRSxDQUFDO1FBRW5ELE1BQU0sTUFBTSxHQUFHO1lBQ2IsT0FBTyxFQUFFO2dCQUNQLGFBQWEsRUFBRSxVQUFVLFdBQVcsRUFBRTtnQkFDdEMsY0FBYyxFQUFFLGtCQUFrQjthQUNuQztTQUNGLENBQUM7UUFFRixNQUFNLElBQUksR0FBRztZQUNYLFNBQVM7WUFDVCxRQUFRO1lBQ1IsU0FBUztTQUNWLENBQUM7UUFFRixNQUFNLE9BQU8sR0FBRyxNQUFNLGVBQUssQ0FBQyxJQUFJLENBQUMsR0FBRyxFQUFFLElBQUksRUFBRSxNQUFNLENBQUMsQ0FBQztRQUVwRCxPQUFPLENBQUMsR0FBRyxDQUFDLE9BQU8sRUFBRSx3Q0FBd0MsQ0FBQyxDQUFDO0lBQ2pFLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsMkNBQTJDLENBQUMsQ0FBQztJQUM5RCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBbENXLFFBQUEsMEJBQTBCLDhCQWtDckM7QUFFSyxNQUFNLHlDQUF5QyxHQUFHLENBQ3ZELFFBQW1DLEVBQ25DLEVBQUU7SUFDRixNQUFNLFlBQVksR0FBRyxRQUFRLEVBQUUsR0FBRyxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO1FBQ3pDLEtBQUssRUFBRSxDQUFDLEVBQUUsS0FBSyxJQUFJLEVBQUU7UUFDckIsSUFBSSxFQUFFLENBQUMsRUFBRSxJQUFJO0tBQ2QsQ0FBQyxDQUFDLENBQUM7SUFFSixPQUFPLFlBQVksQ0FBQztBQUN0QixDQUFDLENBQUM7QUFUVyxRQUFBLHlDQUF5Qyw2Q0FTcEQ7QUFFSyxNQUFNLHlDQUF5QyxHQUFHLENBQ3ZELFFBQW1DLEVBQ25DLFNBQWlCLEVBQ2pCLEVBQUU7SUFDRixNQUFNLGFBQWEsR0FBRyxRQUFRLEVBQUUsR0FBRyxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO1FBQzFDLEtBQUssRUFBRSxDQUFDLEVBQUUsS0FBSyxJQUFJLEVBQUU7UUFDckIsSUFBSSxFQUFFLENBQUMsRUFBRSxJQUFJO1FBQ2IsSUFBSSxFQUFFLElBQUEsMEJBQWtCLEVBQUMsU0FBUyxFQUFFLENBQUMsRUFBRSxFQUFFLEVBQUUsQ0FBQyxFQUFFLEtBQUssQ0FBQztLQUNyRCxDQUFDLENBQUMsQ0FBQztJQUVKLE9BQU8sYUFBYSxDQUFDO0FBQ3ZCLENBQUMsQ0FBQztBQVhXLFFBQUEseUNBQXlDLDZDQVdwRDtBQUVLLE1BQU0sMEJBQTBCLEdBQUcsS0FBSyxFQUM3QyxTQUFnQyxFQUNoQyxTQUFpQixFQUNqQixRQUFnQixFQUNoQixLQUFhLEVBQ2IsS0FBYSxFQUNiLGVBQXVCLEVBQ3ZCLGFBQXFCLEVBQ3JCLFFBQWdCLEVBQ2hCLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxPQUFPLENBQUMsR0FBRyxDQUNULFNBQVMsRUFDVCx3REFBd0QsQ0FDekQsQ0FBQztRQUNGLE1BQU0sV0FBVyxHQUFHLE1BQU0saUJBQU8sQ0FBQyxjQUFjLEVBQUUsQ0FBQztRQUVuRCxNQUFNLE1BQU0sR0FBRztZQUNiLE9BQU8sRUFBRTtnQkFDUCxhQUFhLEVBQUUsVUFBVSxXQUFXLEVBQUU7Z0JBQ3RDLGNBQWMsRUFBRSxrQkFBa0I7YUFDbkM7U0FDRixDQUFDO1FBRUYsTUFBTSxJQUFJLEdBQW1DO1lBQzNDLFNBQVM7WUFDVCxTQUFTO1lBQ1QsUUFBUTtZQUNSLEtBQUs7WUFDTCxLQUFLO1lBQ0wsZUFBZTtZQUNmLGFBQWE7WUFDYixRQUFRO1NBQ1QsQ0FBQztRQUVGLE1BQU0sR0FBRyxHQUFHLHFDQUF5QixDQUFDO1FBRXRDLE1BQU0sT0FBTyxHQUFHLE1BQU0sZUFBSyxDQUFDLElBQUksQ0FBQyxHQUFHLEVBQUUsSUFBSSxFQUFFLE1BQU0sQ0FBQyxDQUFDO1FBRXBELE9BQU8sQ0FBQyxHQUFHLENBQUMsT0FBTyxFQUFFLGtDQUFrQyxDQUFDLENBQUM7SUFDM0QsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSwrQkFBK0IsQ0FBQyxDQUFDO0lBQ2xELENBQUM7QUFDSCxDQUFDLENBQUM7QUEzQ1csUUFBQSwwQkFBMEIsOEJBMkNyQztBQUVLLE1BQU0sa0JBQWtCLEdBQUcsQ0FDaEMsU0FBaUIsRUFDakIsVUFBa0IsRUFDbEIsWUFBcUIsRUFDckIsRUFBRSxDQUNGLENBQUMsWUFBWTtJQUNYLEdBQUcsd0JBQVksSUFBSSxZQUFFLENBQUMsU0FBUyxDQUFDLEVBQUUsU0FBUyxFQUFFLFVBQVUsRUFBRSxZQUFZLEVBQUUsQ0FBQyxFQUFFLENBQUM7SUFDN0UsR0FBRyx3QkFBWSxJQUFJLFlBQUUsQ0FBQyxTQUFTLENBQUMsRUFBRSxTQUFTLEVBQUUsVUFBVSxFQUFFLENBQUMsRUFBRSxDQUFDO0FBUGxELFFBQUEsa0JBQWtCLHNCQU9nQztBQUV4RCxNQUFNLG9CQUFvQixHQUFHLENBQ2xDLENBQXNCLEVBQ3RCLFFBQW1DLEVBQ25DLElBQXlELEVBQ3pELFVBQStELEVBQy9ELE1BQWMsRUFDZCxRQUFnQixFQUNoQixTQUFpQixFQUNqQixFQUFFO0lBQ0YsTUFBTSxVQUFVLEdBQTRCO1FBQzFDLEVBQUUsRUFBRSxJQUFBLFNBQUksR0FBRTtRQUNWLElBQUksRUFBRSxDQUFDLEVBQUUsSUFBSSxJQUFJLEVBQUU7UUFDbkIsS0FBSyxFQUFFLENBQUMsRUFBRSxNQUFNLEVBQUUsSUFBSSxDQUFDLENBQUMsQ0FBdUIsRUFBRSxFQUFFLENBQUMsQ0FBQyxFQUFFLE9BQU8sQ0FBQyxFQUFFLEtBQUs7UUFDdEUsTUFBTTtRQUNOLFFBQVE7UUFDUixTQUFTO1FBQ1QsV0FBVyxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLE1BQU0sRUFBRTtRQUM3QixTQUFTLEVBQUUsSUFBQSxrQkFBSyxHQUFFLENBQUMsTUFBTSxFQUFFO1FBQzNCLE1BQU0sRUFBRSxDQUFDLEVBQUUsTUFBTTtRQUNqQixTQUFTLEVBQUUsQ0FBQyxFQUFFLEVBQUU7S0FDakIsQ0FBQztJQUVGLE1BQU0sV0FBVyxHQUFHLFFBQVEsQ0FBQyxNQUFNLENBQUMsQ0FBQyxVQUFVLENBQUMsQ0FBQyxDQUFDO0lBQ2xELElBQUksQ0FBQyxXQUFXLENBQUMsQ0FBQztJQUNsQixVQUFVLENBQUMsV0FBVyxDQUFDLENBQUM7QUFDMUIsQ0FBQyxDQUFDO0FBekJXLFFBQUEsb0JBQW9CLHdCQXlCL0I7QUFFSyxNQUFNLHFCQUFxQixHQUFHLENBQ25DLENBQTRCLEVBQzVCLElBQXlELEVBQ3pELFFBQW1DLEVBQ25DLFdBQWdFLEVBQ2hFLFVBQStELEVBQy9ELE1BQWMsRUFDZCxRQUFnQixFQUNoQixTQUFpQixFQUNqQixFQUFFO0lBQ0YsTUFBTSxRQUFRLEdBQTRCO1FBQ3hDLEVBQUUsRUFBRSxJQUFBLFNBQUksR0FBRTtRQUNWLE1BQU07UUFDTixLQUFLLEVBQUUsRUFBRTtRQUNULFFBQVE7UUFDUixTQUFTO1FBQ1QsSUFBSSxFQUFFLEVBQUU7UUFDUixXQUFXLEVBQUUsSUFBQSxrQkFBSyxHQUFFLENBQUMsTUFBTSxFQUFFO1FBQzdCLFNBQVMsRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxNQUFNLEVBQUU7S0FDNUIsQ0FBQztJQUVGLE1BQU0sS0FBSyxHQUFHLGdCQUFDLENBQUMsUUFBUSxDQUFDLENBQUMsQ0FBQyxNQUFNLENBQUMsQ0FBQyxRQUFRLENBQUMsQ0FBQyxFQUFFLGdCQUFDLENBQUMsT0FBTyxDQUFDLENBQUM7SUFDMUQsSUFBSSxDQUFDLEtBQUssQ0FBQyxDQUFDO0lBQ1osTUFBTSxXQUFXLEdBQUcsZ0JBQUMsQ0FBQyxRQUFRLENBQUMsUUFBUSxDQUFDLE1BQU0sQ0FBQyxDQUFDLFFBQVEsQ0FBQyxDQUFDLEVBQUUsZ0JBQUMsQ0FBQyxPQUFPLENBQUMsQ0FBQztJQUN2RSxXQUFXLENBQUMsV0FBVyxDQUFDLENBQUM7SUFDekIsVUFBVSxDQUFDLFdBQVcsQ0FBQyxDQUFDO0FBQzFCLENBQUMsQ0FBQztBQTFCVyxRQUFBLHFCQUFxQix5QkEwQmhDO0FBRUssTUFBTSx3QkFBd0IsR0FBRyxDQUN0QyxDQUFzQixFQUN0QixRQUFtQyxFQUNuQyxXQUFnRSxFQUNoRSxVQUErRCxFQUMvRCxFQUFFO0lBQ0YsTUFBTSxVQUFVLEdBQUcsUUFBUSxDQUFDLFNBQVMsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxFQUFFLEVBQUUsS0FBSyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7SUFFOUQsSUFBSSxVQUFVLEdBQUcsQ0FBQyxDQUFDLEVBQUUsQ0FBQztRQUNwQixNQUFNLFlBQVksR0FBRyxRQUFRO2FBQzFCLEtBQUssQ0FBQyxDQUFDLEVBQUUsVUFBVSxDQUFDO2FBQ3BCLE1BQU0sQ0FBQyxRQUFRLENBQUMsS0FBSyxDQUFDLFVBQVUsR0FBRyxDQUFDLENBQUMsQ0FBQyxDQUFDO1FBRTFDLFdBQVcsQ0FBQyxZQUFZLENBQUMsQ0FBQztRQUMxQixVQUFVLENBQUMsWUFBWSxDQUFDLENBQUM7SUFDM0IsQ0FBQztBQUNILENBQUMsQ0FBQztBQWhCVyxRQUFBLHdCQUF3Qiw0QkFnQm5DO0FBRUssTUFBTSw4QkFBOEIsR0FBRyxDQUM1QyxDQUFzQixFQUN0QixRQUFtQyxFQUNuQyxhQUFvQyxFQUNwQyxXQUFnRSxFQUNoRSxnQkFBaUUsRUFDakUsVUFBK0QsRUFDL0QsRUFBRTtJQUNGLE1BQU0sVUFBVSxHQUFHLFFBQVEsQ0FBQyxTQUFTLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsRUFBRSxFQUFFLEtBQUssQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO0lBRTlELElBQUksVUFBVSxHQUFHLENBQUMsQ0FBQyxFQUFFLENBQUM7UUFDcEIsTUFBTSxXQUFXLEdBQUcsUUFBUTthQUN6QixLQUFLLENBQUMsQ0FBQyxFQUFFLFVBQVUsQ0FBQzthQUNwQixNQUFNLENBQUMsUUFBUSxDQUFDLEtBQUssQ0FBQyxVQUFVLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQztRQUUxQyxXQUFXLENBQUMsV0FBVyxDQUFDLENBQUM7UUFDekIsVUFBVSxDQUFDLFdBQVcsQ0FBQyxDQUFDO0lBQzFCLENBQUM7SUFFRCxNQUFNLGdCQUFnQixHQUFHLGFBQWEsRUFBRSxTQUFTLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsRUFBRSxFQUFFLEtBQUssQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO0lBRTFFLElBQUksZ0JBQWdCLEdBQUcsQ0FBQyxDQUFDLEVBQUUsQ0FBQztRQUMxQixNQUFNLGlCQUFpQixHQUFHLGFBQWE7YUFDcEMsS0FBSyxDQUFDLENBQUMsRUFBRSxVQUFVLENBQUM7YUFDcEIsTUFBTSxDQUFDLGFBQWEsQ0FBQyxLQUFLLENBQUMsVUFBVSxHQUFHLENBQUMsQ0FBQyxDQUFDLENBQUM7UUFFL0MsZ0JBQWdCLENBQUMsaUJBQWlCLENBQUMsQ0FBQztJQUN0QyxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBNUJXLFFBQUEsOEJBQThCLGtDQTRCekM7QUFFSyxNQUFNLDRCQUE0QixHQUFHLENBQzFDLGFBQXdDLEVBQ3hDLGdCQUFxRSxFQUNyRSxRQUFtQyxFQUNuQyxXQUFnRSxFQUNoRSxVQUErRCxFQUMvRCxLQUFhLEVBQ2IsV0FBbUIsRUFDbkIsRUFBRTtJQUNGLE1BQU0sVUFBVSxHQUFHLGFBQWE7U0FDN0IsS0FBSyxDQUFDLENBQUMsRUFBRSxLQUFLLENBQUM7U0FDZixNQUFNLENBQUMsYUFBYSxDQUFDLEtBQUssQ0FBQyxLQUFLLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQztJQUMxQyxnQkFBZ0IsQ0FBQyxVQUFVLENBQUMsQ0FBQztJQUM3QixNQUFNLFlBQVksR0FBRyxRQUFRO1NBQzFCLEtBQUssQ0FBQyxDQUFDLEVBQUUsV0FBVyxDQUFDO1NBQ3JCLE1BQU0sQ0FBQyxRQUFRLENBQUMsS0FBSyxDQUFDLFdBQVcsR0FBRyxDQUFDLENBQUMsQ0FBQyxDQUFDO0lBQzNDLFdBQVcsQ0FBQyxZQUFZLENBQUMsQ0FBQztJQUMxQixVQUFVLENBQUMsWUFBWSxDQUFDLENBQUM7QUFDM0IsQ0FBQyxDQUFDO0FBbEJXLFFBQUEsNEJBQTRCLGdDQWtCdkM7QUFFSyxNQUFNLHNCQUFzQixHQUFHLENBQ3BDLEtBQWMsRUFDZCxVQUErQixFQUMvQixDQUF3QixFQUN4QixJQUFxRCxFQUNyRCxLQUFhLEVBQ2IsRUFBRTtJQUNGLE1BQU0sSUFBSSxHQUFHLGdCQUFDLENBQUMsU0FBUyxDQUN0QixDQUFDO1NBQ0UsS0FBSyxDQUFDLENBQUMsRUFBRSxLQUFLLENBQUM7U0FDZixNQUFNLENBQUMsQ0FBQyxFQUFFLEdBQUcsVUFBVSxFQUFFLFFBQVEsRUFBRSxLQUFLLEVBQUUsQ0FBQyxDQUFDO1NBQzVDLE1BQU0sQ0FBQyxDQUFDLENBQUMsS0FBSyxDQUFDLEtBQUssR0FBRyxDQUFDLENBQUMsQ0FBQyxDQUM5QixDQUFDO0lBQ0YsSUFBSSxDQUFDLElBQUksQ0FBQyxDQUFDO0FBQ2IsQ0FBQyxDQUFDO0FBZFcsUUFBQSxzQkFBc0IsMEJBY2pDO0FBRUssTUFBTSw0QkFBNEIsR0FBRyxDQUMxQyxLQUFjLEVBQ2QsVUFBK0IsRUFDL0IsQ0FBd0IsRUFDeEIsT0FBOEIsRUFDOUIsSUFBcUQsRUFDckQsVUFBMkQsRUFDM0QsV0FBbUIsRUFDbkIsRUFBRTtJQUNGLE1BQU0sU0FBUyxHQUFHLENBQUMsRUFBRSxTQUFTLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsRUFBRSxFQUFFLEtBQUssVUFBVSxFQUFFLEVBQUUsQ0FBQyxDQUFDO0lBRWhFLElBQUksU0FBUyxHQUFHLENBQUMsQ0FBQyxFQUFFLENBQUM7UUFDbkIsTUFBTSxJQUFJLEdBQUcsZ0JBQUMsQ0FBQyxTQUFTLENBQ3RCLENBQUM7YUFDRSxLQUFLLENBQUMsQ0FBQyxFQUFFLFNBQVMsQ0FBQzthQUNuQixNQUFNLENBQUMsQ0FBQyxFQUFFLEdBQUcsVUFBVSxFQUFFLFFBQVEsRUFBRSxLQUFLLEVBQUUsQ0FBQyxDQUFDO2FBQzVDLE1BQU0sQ0FBQyxDQUFDLENBQUMsS0FBSyxDQUFDLFNBQVMsR0FBRyxDQUFDLENBQUMsQ0FBQyxDQUNsQyxDQUFDO1FBQ0YsSUFBSSxDQUFDLElBQUksQ0FBQyxDQUFDO0lBQ2IsQ0FBQztJQUVELE1BQU0sVUFBVSxHQUFHLGdCQUFDLENBQUMsU0FBUyxDQUM1QixPQUFPO1NBQ0osS0FBSyxDQUFDLENBQUMsRUFBRSxXQUFXLENBQUM7U0FDckIsTUFBTSxDQUFDLENBQUMsRUFBRSxHQUFHLFVBQVUsRUFBRSxRQUFRLEVBQUUsS0FBSyxFQUFFLENBQUMsQ0FBQztTQUM1QyxNQUFNLENBQUMsQ0FBQyxDQUFDLEtBQUssQ0FBQyxXQUFXLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FDcEMsQ0FBQztJQUNGLFVBQVUsQ0FBQyxVQUFVLENBQUMsQ0FBQztBQUN6QixDQUFDLENBQUM7QUE1QlcsUUFBQSw0QkFBNEIsZ0NBNEJ2QztBQUVLLE1BQU0sMEJBQTBCLEdBQUcsQ0FDeEMsQ0FBNEIsRUFDNUIsSUFBeUQsRUFDekQsS0FBYSxFQUNiLFFBQW1DLEVBQ25DLFlBQWlFLEVBQ2pFLFVBQStELEVBQy9ELFdBQW1CLEVBQ25CLEtBQWMsRUFDZCxXQUFvQixFQUNwQixFQUFFO0lBQ0YsTUFBTSxNQUFNLEdBQUcsQ0FBQyxDQUFDLEtBQUssQ0FBQyxDQUFDO0lBQ3hCLE1BQU0sTUFBTSxHQUE0QjtRQUN0QyxHQUFHLE1BQU07UUFDVCxJQUFJLEVBQUUsV0FBVyxJQUFJLE1BQU0sRUFBRSxJQUFJO1FBQ2pDLEtBQUssRUFBRSxLQUFLLElBQUksTUFBTSxFQUFFLEtBQUs7S0FDOUIsQ0FBQztJQUVGLE1BQU0sSUFBSSxHQUFHLENBQUM7U0FDWCxLQUFLLENBQUMsQ0FBQyxFQUFFLEtBQUssQ0FBQztTQUNmLE1BQU0sQ0FBQyxDQUFDLE1BQU0sQ0FBQyxDQUFDO1NBQ2hCLE1BQU0sQ0FBQyxDQUFDLENBQUMsS0FBSyxDQUFDLEtBQUssR0FBRyxDQUFDLENBQUMsQ0FBQyxDQUFDO0lBQzlCLElBQUksQ0FBQyxJQUFJLENBQUMsQ0FBQztJQUNYLE1BQU0sV0FBVyxHQUFHLFFBQVE7U0FDekIsS0FBSyxDQUFDLENBQUMsRUFBRSxXQUFXLENBQUM7U0FDckIsTUFBTSxDQUFDLENBQUMsTUFBTSxDQUFDLENBQUM7U0FDaEIsTUFBTSxDQUFDLFFBQVEsQ0FBQyxLQUFLLENBQUMsV0FBVyxHQUFHLENBQUMsQ0FBQyxDQUFDLENBQUM7SUFDM0MsWUFBWSxDQUFDLFdBQVcsQ0FBQyxDQUFDO0lBQzFCLFVBQVUsQ0FBQyxXQUFXLENBQUMsQ0FBQztBQUMxQixDQUFDLENBQUM7QUE3QlcsUUFBQSwwQkFBMEIsOEJBNkJyQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IEFwb2xsb0NsaWVudCwgZ3FsLCBOb3JtYWxpemVkQ2FjaGVPYmplY3QgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5pbXBvcnQgaW5zZXJ0TWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZXNNdXRhdGlvbiBmcm9tICdAbGliL2Fwb2xsby9ncWwvaW5zZXJ0TWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZXNNdXRhdGlvbic7XG5pbXBvcnQgeyBNZWV0aW5nQXNzaXN0SW52aXRlVHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL01lZXRpbmdBc3Npc3RJbnZpdGVUeXBlJztcbmltcG9ydCB7IE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlIH0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGUnO1xuaW1wb3J0IHsgTWVldGluZ0Fzc2lzdFR5cGUgfSBmcm9tICdAbGliL2RhdGFUeXBlcy9NZWV0aW5nQXNzaXN0VHlwZSc7XG5pbXBvcnQgeyBSUnVsZSB9IGZyb20gJ3JydWxlJztcbmltcG9ydCB7IGRheWpzIH0gZnJvbSAnQGxpYi9kYXRlLXV0aWxzJztcblxuLy8gbGliL0NhbGVuZGFyL1VzZXJDcmVhdGVDYWxlbmRhckhlbHBlci50c1xuaW1wb3J0IHtcbiAgZ2V0UlJ1bGVEYXksXG4gIGdldFJydWxlRnJlcSxcbn0gZnJvbSAnQGxpYi9DYWxlbmRhci9Vc2VyQ3JlYXRlQ2FsZW5kYXJIZWxwZXInO1xuaW1wb3J0IHtcbiAgQXR0ZW5kZWVEZXRhaWxzRm9yQnVsa01lZXRpbmdDYW5jZWxsZWRUeXBlLFxuICBBdHRlbmRlZURldGFpbHNGb3JCdWxrTWVldGluZ0ludml0ZVR5cGUsXG4gIEF0dGVuZGVlRGV0YWlsc1R5cGUsXG4gIE1lZXRpbmdJbnZpdGVEZXRhaWxzVG9Ib3N0VHlwZSxcbn0gZnJvbSAnQGxpYi9Bc3Npc3QvdHlwZXMnO1xuaW1wb3J0IFNlc3Npb24gZnJvbSAnc3VwZXJ0b2tlbnMtd2ViLWpzL3JlY2lwZS9zZXNzaW9uJztcbmltcG9ydCB7XG4gIGVtYWlsTWVldGluZ0NhbmNlbFVybCxcbiAgZW1haWxNZWV0aW5nSW5mb1RvSG9zdFVybCxcbiAgZW1haWxNZWV0aW5nSW52aXRlVXJsLFxuICBoYW5kc2hha2VVcmwsXG59IGZyb20gJ0BsaWIvQXNzaXN0L2NvbnN0YW50cyc7XG5pbXBvcnQgYXhpb3MgZnJvbSAnYXhpb3MnO1xuaW1wb3J0IHFzIGZyb20gJ3FzJztcbmltcG9ydCB1cHNlcnRNZWV0aW5nQXNzaXN0SW52aXRlc011dGF0aW9uIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC91cHNlcnRNZWV0aW5nQXNzaXN0SW52aXRlc011dGF0aW9uJztcbmltcG9ydCB7IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGUgfSBmcm9tICdAbGliL2RhdGFUeXBlcy9NZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlJztcbmltcG9ydCBpbnNlcnRBdHRlbmRlZU11dGF0aW9uIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9pbnNlcnRBdHRlbmRlZU11dGF0aW9uJztcbmltcG9ydCBnZXRVc2VyQnlJZCBmcm9tICdAbGliL2Fwb2xsby9ncWwvZ2V0VXNlckJ5SWQnO1xuaW1wb3J0IHsgVXNlclR5cGUgfSBmcm9tICdAbGliL2RhdGFUeXBlcy9Vc2VyVHlwZSc7XG5cbmltcG9ydCB7IFNlbGVjdGVkQ29udGFjdFR5cGUgfSBmcm9tICdAcGFnZXMvQ2FsZW5kYXIvQ3JlYXRlRXZlbnRXaXphcmQvQ3JlYXRlRXZlbnRBdHRlbmRlZXMnO1xuaW1wb3J0IHsgUGVyc29uLCBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZSB9IGZyb20gJ0BsaWIvQ2FsZW5kYXIvdHlwZXMnO1xuaW1wb3J0IHsgRGlzcGF0Y2gsIFNldFN0YXRlQWN0aW9uIH0gZnJvbSAncmVhY3QnO1xuaW1wb3J0IHsgdjQgYXMgdXVpZCB9IGZyb20gJ3V1aWQnO1xuaW1wb3J0IF8gZnJvbSAnbG9kYXNoJztcbmltcG9ydCB7IEF0dGVuZGVlRW1haWxUeXBlIH0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvQXR0ZW5kZWVUeXBlJztcbmltcG9ydCB1cGRhdGVVc2VyRm9yTmFtZSBmcm9tICdAbGliL2Fwb2xsby9ncWwvdXBkYXRlVXNlckZvck5hbWUnO1xuaW1wb3J0IGxpc3RNZWV0aW5nQXNzaXN0cyBmcm9tICdAbGliL2Fwb2xsby9ncWwvbGlzdE1lZXRpbmdBc3Npc3RzJztcbmltcG9ydCBkZWxldGVNZWV0aW5nQXNzaXN0QnlJZCBmcm9tICdAbGliL2Fwb2xsby9ncWwvZGVsZXRlTWVldGluZ0Fzc2lzdEJ5SWQnO1xuaW1wb3J0IGxpc3RNZWV0aW5nQXNzaXN0SW52aXRlcyBmcm9tICdAbGliL2Fwb2xsby9ncWwvbGlzdE1lZXRpbmdBc3Npc3RJbnZpdGVzJztcbmltcG9ydCBpbnNlcnRNZWV0aW5nQXNzaXN0QXR0ZW5kZWVPbmUgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2luc2VydE1lZXRpbmdBc3Npc3RBdHRlbmRlZU9uZSc7XG5pbXBvcnQgZ2V0TWVldGluZ0Fzc2lzdEJ5SWQgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2dldE1lZXRpbmdBc3Npc3RCeUlkJztcbmltcG9ydCBzZWFyY2hNZWV0aW5nQXNzaXN0c1F1ZXJ5IGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9zZWFyY2hNZWV0aW5nQXNzaXN0c1F1ZXJ5JztcblxuZXhwb3J0IGNvbnN0IGxpc3RNZWV0aW5nQXNzaXN0SW52aXRlc0dpdmVuTWVldGluZ0lkID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBtZWV0aW5nSWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgbWVldGluZ0Fzc2lzdEludml0ZXNEb2MgPSAoXG4gICAgICBhd2FpdCBjbGllbnQucXVlcnk8eyBNZWV0aW5nX0Fzc2lzdF9JbnZpdGU6IE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlW10gfT4oe1xuICAgICAgICBxdWVyeTogbGlzdE1lZXRpbmdBc3Npc3RJbnZpdGVzLFxuICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICBtZWV0aW5nSWQsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICk/LmRhdGE/Lk1lZXRpbmdfQXNzaXN0X0ludml0ZTtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgbWVldGluZ0Fzc2lzdEludml0ZXNEb2MsXG4gICAgICAnIHN1Y2Nlc3NmdWxseSBsaXN0ZWQgbWVldGluZyBhc3Npc3QgaW52aXRlcyBnaXZlbiBtZWV0aW5nSWQnXG4gICAgKTtcblxuICAgIHJldHVybiBtZWV0aW5nQXNzaXN0SW52aXRlc0RvYztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGxpc3QgbWVldGluZyBhc3Npc3QgaW52aXRlcyBnaXZlbiBtZWV0aW5nSWQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldE1lZXRpbmdBc3Npc3RHaXZlbklkID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBtZWV0aW5nSWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgbWVldGluZ0Fzc2lzdERvYyA9IChcbiAgICAgIGF3YWl0IGNsaWVudC5xdWVyeTx7IE1lZXRpbmdfQXNzaXN0X2J5X3BrOiBNZWV0aW5nQXNzaXN0VHlwZSB9Pih7XG4gICAgICAgIHF1ZXJ5OiBnZXRNZWV0aW5nQXNzaXN0QnlJZCxcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgaWQ6IG1lZXRpbmdJZCxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgKT8uZGF0YT8uTWVldGluZ19Bc3Npc3RfYnlfcGs7XG5cbiAgICBjb25zb2xlLmxvZyhtZWV0aW5nQXNzaXN0RG9jLCAnIHN1Y2Nlc3NmdWxseSBnb3QgbWVldGluZ0Fzc2lzdERvYycpO1xuICAgIHJldHVybiBtZWV0aW5nQXNzaXN0RG9jO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IG1lZXRpbmcgYXNzaXN0IGdpdmVuIElkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBsaXN0VXNlck1lZXRpbmdBc3Npc3RzR2l2ZW5Vc2VySWQgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHVzZXJJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBtZWV0aW5nQXNzaXN0cyA9IChcbiAgICAgIGF3YWl0IGNsaWVudC5xdWVyeTx7IE1lZXRpbmdfQXNzaXN0OiBNZWV0aW5nQXNzaXN0VHlwZVtdIH0+KHtcbiAgICAgICAgcXVlcnk6IGxpc3RNZWV0aW5nQXNzaXN0cyxcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICApPy5kYXRhPy5NZWV0aW5nX0Fzc2lzdDtcblxuICAgIGNvbnNvbGUubG9nKG1lZXRpbmdBc3Npc3RzLCAnIHN1Y2Nlc3NmdWxseSByZXR1cm5lZCBtZWV0aW5nIGFzc2lzdHMnKTtcblxuICAgIHJldHVybiBtZWV0aW5nQXNzaXN0cztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGxpc3QgdXNlciBtZWV0aW5nIGFzc2lzdHMgZ2l2ZW4gdXNlcklkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRVc2VyR2l2ZW5JZCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGV4aXN0aW5nVXNlciA9IChcbiAgICAgIGF3YWl0IGNsaWVudC5xdWVyeTx7IFVzZXJfYnlfcGs6IFVzZXJUeXBlIH0+KHtcbiAgICAgICAgcXVlcnk6IGdldFVzZXJCeUlkLFxuICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICBpZDogdXNlcklkLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICApPy5kYXRhPy5Vc2VyX2J5X3BrO1xuXG4gICAgY29uc29sZS5sb2coZXhpc3RpbmdVc2VyLCAnIHN1Y2Nlc3NmdWxseSBnb3R0ZW4gdXNlcklkJyk7XG5cbiAgICByZXR1cm4gZXhpc3RpbmdVc2VyO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IHVzZXIgZ2l2ZW4gSWQgaW5zaWRlIGdldFVzZXJHaXZlbklkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBkZWxldGVNZWV0aW5nQXNzaXN0R2l2ZW5JZCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgaWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgZGVsZXRlZE1lZXRpbmdBc3Npc3REb2MgPSAoXG4gICAgICBhd2FpdCBjbGllbnQubXV0YXRlPHsgZGVsZXRlX01lZXRpbmdfQXNzaXN0X2J5X3BrOiBNZWV0aW5nQXNzaXN0VHlwZSB9Pih7XG4gICAgICAgIG11dGF0aW9uOiBkZWxldGVNZWV0aW5nQXNzaXN0QnlJZCxcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgaWQsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICk/LmRhdGE/LmRlbGV0ZV9NZWV0aW5nX0Fzc2lzdF9ieV9waztcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZGVsZXRlZE1lZXRpbmdBc3Npc3REb2MsXG4gICAgICAnIHN1Y2Nlc3NmdWxseSBkZWxldGVkIG1lZXRpbmcgYXNzaXN0IGRvYydcbiAgICApO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZGVsZXRlIG1lZXRpbmcgYXNzaXN0IGdpdmVuIGlkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCB1cGRhdGVVc2VyTmFtZUdpdmVuSWQgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHVzZXJJZDogc3RyaW5nLFxuICBuYW1lOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHVzZXJEb2MgPSAoXG4gICAgICBhd2FpdCBjbGllbnQubXV0YXRlPHsgdXBkYXRlX1VzZXJfYnlfcGs6IFVzZXJUeXBlIH0+KHtcbiAgICAgICAgbXV0YXRpb246IHVwZGF0ZVVzZXJGb3JOYW1lLFxuICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICBpZDogdXNlcklkLFxuICAgICAgICAgIG5hbWUsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICk/LmRhdGE/LnVwZGF0ZV9Vc2VyX2J5X3BrO1xuXG4gICAgY29uc29sZS5sb2codXNlckRvYywgJyBzdWNjZXNzZnVsbHkgdXBkYXRlZCB1c2VyRG9jJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVhbmJsZSB0byB1cGRhdGUgdXNlciBuYW1lIGdpdmVuIGlkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBpbnNlcnRNZWV0aW5nQXNzaXN0QXR0ZW5kZWUgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIGF0dGVuZGVlOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBtZWV0aW5nQXNzaXN0QXR0ZW5kZWVEb2MgPSAoXG4gICAgICBhd2FpdCBjbGllbnQubXV0YXRlPHtcbiAgICAgICAgaW5zZXJ0X01lZXRpbmdfQXNzaXN0X0F0dGVuZGVlX29uZTogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZTtcbiAgICAgIH0+KHtcbiAgICAgICAgbXV0YXRpb246IGluc2VydE1lZXRpbmdBc3Npc3RBdHRlbmRlZU9uZSxcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgYXR0ZW5kZWUsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICk/LmRhdGE/Lmluc2VydF9NZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZV9vbmU7XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIG1lZXRpbmdBc3Npc3RBdHRlbmRlZURvYyxcbiAgICAgICcgc3VjY2Vzc2Z1bGx5IGluc2VydGVkIG1lZXRpbmcgYXNzaXN0IGF0dGVuZGVlJ1xuICAgICk7XG5cbiAgICByZXR1cm4gbWVldGluZ0Fzc2lzdEF0dGVuZGVlRG9jO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gaW5zZXJ0IGF0dGVuZGVlIG9uZScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdXBzZXJ0TWVldGluZ0Fzc2lzdE1hbnkgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIG1lZXRpbmdBc3Npc3RzOiBNZWV0aW5nQXNzaXN0VHlwZVtdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIG1lZXRpbmdBc3Npc3RzLFxuICAgICAgJyBtZWV0aW5nQXNzaXN0c2luc2lkZSB1cHNlcnRNZWV0aW5nQXNzaXN0TWFueSdcbiAgICApO1xuICAgIC8vIEFTU1VNUFRJT046IEEgY3VzdG9tIG11dGF0aW9uICdidWxrVXBzZXJ0TWVldGluZ0Fzc2lzdHMnIGlzIGRlZmluZWQgaW4gUG9zdEdyYXBoaWxlIChlLmcuLCB2aWEgYSBQRyBmdW5jdGlvbilcbiAgICAvLyB0aGF0IHRha2VzIGFuIGFycmF5IG9mIE1lZXRpbmdBc3Npc3RJbnB1dCBhbmQgaGFuZGxlcyB0aGUgdXBzZXJ0IGxvZ2ljLlxuICAgIC8vIFRoZSByZXR1cm4gdHlwZSB3aWxsIGFsc28gZGVwZW5kIG9uIHRoZSBjdXN0b20gZnVuY3Rpb24ncyBkZWZpbml0aW9uLlxuICAgIC8vIFRoZSBsaXN0IG9mIGNvbHVtbnMgaW4gb25fY29uZmxpY3QgaXMgbm93IGltcGxpY2l0IGluIHRoZSBQRyBmdW5jdGlvbi5cbiAgICBjb25zdCB1cHNlcnRNZWV0aW5nQXNzaXN0c011dGF0aW9uID0gZ3FsYFxuICAgICAgbXV0YXRpb24gQnVsa1Vwc2VydE1lZXRpbmdBc3Npc3RzKCRhc3Npc3RzOiBbTWVldGluZ0Fzc2lzdElucHV0IV0hKSB7XG4gICAgICAgIGJ1bGtVcHNlcnRNZWV0aW5nQXNzaXN0cyhpbnB1dDogeyBhc3Npc3RzOiAkYXNzaXN0cyB9KSB7XG4gICAgICAgICAgIyBBc3N1bWluZyB0aGUgY3VzdG9tIGZ1bmN0aW9uIHJldHVybnMgYSBsaXN0IG9mIHRoZSB1cHNlcnRlZCBtZWV0aW5nIGFzc2lzdHNcbiAgICAgICAgICAjIGFuZCBQb3N0R3JhcGhpbGUgd3JhcHMgdGhpcyBpbiBhIHN0YW5kYXJkIHBheWxvYWQgc3RydWN0dXJlLlxuICAgICAgICAgICMgT3IgaXQgbWlnaHQgcmV0dXJuIGEgc2ltcGxlIGxpc3QgZGlyZWN0bHkgaWYgdGhlIGZ1bmN0aW9uIHJldHVybnMgU0VUT0YuXG4gICAgICAgICAgIyBMZXQncyBhc3N1bWUgaXQgcmV0dXJucyBhIGxpc3Qgb2YgbWVldGluZ0Fzc2lzdHMgZm9yIG5vdy5cbiAgICAgICAgICAjIFRoZSBhY3R1YWwgc3RydWN0dXJlIHdpbGwgZGVwZW5kIG9uIHRoZSBQb3N0R3JhcGhpbGUgc2NoZW1hLlxuICAgICAgICAgIHJlc3VsdHM6IG1lZXRpbmdBc3Npc3RzIHtcbiAgICAgICAgICAgICMgT3IganVzdCAnbWVldGluZ0Fzc2lzdHMnIGlmIGZ1bmN0aW9uIHJldHVybnMgU0VUT0YgbWVldGluZ19hc3Npc3RcbiAgICAgICAgICAgIGFsbG93QXR0ZW5kZWVVcGRhdGVQcmVmZXJlbmNlc1xuICAgICAgICAgICAgYW55b25lQ2FuQWRkU2VsZlxuICAgICAgICAgICAgYXR0ZW5kZWVDYW5Nb2RpZnlcbiAgICAgICAgICAgIGF0dGVuZGVlQ291bnRcbiAgICAgICAgICAgIGF0dGVuZGVlUmVzcG9uZGVkQ291bnRcbiAgICAgICAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgICAgICAgYnVmZmVyVGltZVxuICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgY2FuY2VsSWZBbnlSZWZ1c2VcbiAgICAgICAgICAgIGNhbmNlbGxlZFxuICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgY29uZmVyZW5jZUFwcFxuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGR1cmF0aW9uXG4gICAgICAgICAgICBlbmFibGVBdHRlbmRlZVByZWZlcmVuY2VzXG4gICAgICAgICAgICBlbmFibGVDb25mZXJlbmNlXG4gICAgICAgICAgICBlbmFibGVIb3N0UHJlZmVyZW5jZXNcbiAgICAgICAgICAgIGVuZERhdGVcbiAgICAgICAgICAgIGV2ZW50SWRcbiAgICAgICAgICAgIGV4cGlyZURhdGVcbiAgICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgICAgZnJlcXVlbmN5XG4gICAgICAgICAgICBndWFyYW50ZWVBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHNcbiAgICAgICAgICAgIGlkXG4gICAgICAgICAgICBpbnRlcnZhbFxuICAgICAgICAgICAgbG9jYXRpb25cbiAgICAgICAgICAgIG1pblRocmVzaG9sZENvdW50XG4gICAgICAgICAgICBub3Rlc1xuICAgICAgICAgICAgb3JpZ2luYWxNZWV0aW5nSWRcbiAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICByZW1pbmRlcnNcbiAgICAgICAgICAgIHNlbmRVcGRhdGVzXG4gICAgICAgICAgICBzdGFydERhdGVcbiAgICAgICAgICAgIHN1bW1hcnlcbiAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICB0cmFuc3BhcmVuY3lcbiAgICAgICAgICAgIHVudGlsXG4gICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgdmlzaWJpbGl0eVxuICAgICAgICAgICAgd2luZG93RW5kRGF0ZVxuICAgICAgICAgICAgd2luZG93U3RhcnREYXRlXG4gICAgICAgICAgICBsb2NrQWZ0ZXJcbiAgICAgICAgICB9XG4gICAgICAgICAgIyBQb3N0R3JhcGhpbGUgbXV0YXRpb25zIG9mdGVuIHJldHVybiBhIHN0YW5kYXJkIHBheWxvYWQsIGUuZy4sIHsgY2xpZW50TXV0YXRpb25JZCwgZGF0YSB9XG4gICAgICAgICAgIyBGb3Igc2ltcGxpY2l0eSwgYXNzdW1pbmcgdGhlIGZ1bmN0aW9uIHJldHVybnMgZGlyZWN0bHkgb3IgaXMgd3JhcHBlZCB0byByZXR1cm4gdGhlIGxpc3QuXG4gICAgICAgICAgIyBJZiBpdCByZXR1cm5zIGEgY291bnQ6XG4gICAgICAgICAgIyBhZmZlY3RlZENvdW50XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgO1xuICAgIC8vIFRoZSB0eXBlIHBhcmFtZXRlciBmb3IgY2xpZW50Lm11dGF0ZSB3aWxsIG5lZWQgdG8gY2hhbmdlIGJhc2VkIG9uIHRoZSBhY3R1YWwgcmV0dXJuIHR5cGUuXG4gICAgLy8gTGV0J3MgYXNzdW1lIGZvciBub3cgaXQgcmV0dXJucyBhIGxpc3Qgb2YgTWVldGluZ0Fzc2lzdFR5cGUgZGlyZWN0bHkgb3IgdW5kZXIgYSAncmVzdWx0cycgb3IgJ21lZXRpbmdBc3Npc3RzJyBmaWVsZC5cbiAgICAvLyBUaGlzIHBhcnQgaXMgaGlnaGx5IHNwZWN1bGF0aXZlIHdpdGhvdXQgdGhlIGFjdHVhbCBQb3N0R3JhcGhpbGUgc2NoZW1hLlxuICAgIGNvbnN0IG1lZXRpbmdBc3Npc3RzRGF0YURvYyA9IChcbiAgICAgIGF3YWl0IGNsaWVudC5tdXRhdGU8e1xuICAgICAgICBidWxrVXBzZXJ0TWVldGluZ0Fzc2lzdHM6IHtcbiAgICAgICAgICByZXN1bHRzOiBNZWV0aW5nQXNzaXN0VHlwZVtdO1xuICAgICAgICB9IC8qIE9yIHsgbWVldGluZ0Fzc2lzdHM6IE1lZXRpbmdBc3Npc3RUeXBlW10gfSBvciBNZWV0aW5nQXNzaXN0VHlwZVtdIGRpcmVjdGx5ICovO1xuICAgICAgfT4oe1xuICAgICAgICBtdXRhdGlvbjogdXBzZXJ0TWVldGluZ0Fzc2lzdHNNdXRhdGlvbixcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgYXNzaXN0czogbWVldGluZ0Fzc2lzdHMsIC8vIFZhcmlhYmxlIG5hbWUgY2hhbmdlZFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICApPy5kYXRhPy5idWxrVXBzZXJ0TWVldGluZ0Fzc2lzdHM7XG5cbiAgICAvLyBUaGlzIGFjY2VzcyB3aWxsIGxpa2VseSBuZWVkIHRvIGNoYW5nZTpcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIG1lZXRpbmdBc3Npc3RzRGF0YURvYz8ucmVzdWx0cz8ubGVuZ3RoLFxuICAgICAgJyBzdWNjZXNzZnVsbHkgY3JlYXRlZCBtdWx0aXBsZSBtZWV0aW5nIGFzc2lzdHMnXG4gICAgKTtcbiAgICByZXR1cm4gbWVldGluZ0Fzc2lzdHNEYXRhRG9jPy5yZXN1bHRzPy5sZW5ndGg7IC8vIE9yIGhvd2V2ZXIgdGhlIGNvdW50L3Jlc3VsdHMgYXJlIHJldHVybmVkXG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cHNlcnQgbWVldGluZyBhc3Npc3QgbWFueScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdXBzZXJ0TWVldGluZ0Fzc2lzdE9uZSA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgbWVldGluZ0Fzc2lzdDogTWVldGluZ0Fzc2lzdFR5cGUgLy8gVGhpcyBtaWdodCBuZWVkIHRvIGJlIE1lZXRpbmdBc3Npc3RJbnB1dFxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc29sZS5sb2cobWVldGluZ0Fzc2lzdCwgJyBtZWV0aW5nQXNzaXN0IGluc2lkZSB1cHNlcnRNZWV0aW5nQXNzaXN0T25lJyk7XG4gICAgLy8gQVNTVU1QVElPTjogQSBjdXN0b20gbXV0YXRpb24gJ3Vwc2VydE1lZXRpbmdBc3Npc3QnIGlzIGRlZmluZWQgaW4gUG9zdEdyYXBoaWxlIChlLmcuLCB2aWEgYSBQRyBmdW5jdGlvbilcbiAgICAvLyBPUiB3ZSB1c2Ugc2VwYXJhdGUgY3JlYXRlTWVldGluZ0Fzc2lzdCBhbmQgdXBkYXRlTWVldGluZ0Fzc2lzdCBtdXRhdGlvbnMuXG4gICAgLy8gR2l2ZW4gJ29uX2NvbmZsaWN0JywgYW4gdXBzZXJ0IGlzIGludGVuZGVkLlxuICAgIC8vIFBvc3RHcmFwaGlsZSBpbnB1dCB0eXBlcyBhcmUgdHlwaWNhbGx5IGxpa2UgYE1lZXRpbmdBc3Npc3RJbnB1dGAgZm9yIGNyZWF0ZSBhbmQgYE1lZXRpbmdBc3Npc3RQYXRjaGAgZm9yIHVwZGF0ZS5cbiAgICAvLyBBIGN1c3RvbSB1cHNlcnQgbWlnaHQgdGFrZSBgTWVldGluZ0Fzc2lzdElucHV0YC5cbiAgICBjb25zdCB1cHNlcnRNZWV0aW5nQXNzaXN0R3JhcGhxbCA9IGdxbGBcbiAgICAgIG11dGF0aW9uIFVwc2VydE1lZXRpbmdBc3Npc3QoJGlucHV0OiBVcHNlcnRNZWV0aW5nQXNzaXN0SW5wdXQhKSB7XG4gICAgICAgICMgSW5wdXQgdHlwZSBtaWdodCBiZSBVcHNlcnRNZWV0aW5nQXNzaXN0SW5wdXQgb3Igc2ltaWxhclxuICAgICAgICB1cHNlcnRNZWV0aW5nQXNzaXN0KGlucHV0OiAkaW5wdXQpIHtcbiAgICAgICAgICAjIE11dGF0aW9uIG5hbWUgZGVwZW5kcyBvbiBQRyBmdW5jdGlvblxuICAgICAgICAgIG1lZXRpbmdBc3Npc3Qge1xuICAgICAgICAgICAgIyBTdGFuZGFyZCBQb3N0R3JhcGhpbGUgcGF5bG9hZCBzdHJ1Y3R1cmVcbiAgICAgICAgICAgIGFsbG93QXR0ZW5kZWVVcGRhdGVQcmVmZXJlbmNlc1xuICAgICAgICAgICAgYW55b25lQ2FuQWRkU2VsZlxuICAgICAgICAgICAgYXR0ZW5kZWVDYW5Nb2RpZnlcbiAgICAgICAgICAgIGF0dGVuZGVlQ291bnRcbiAgICAgICAgICAgIGF0dGVuZGVlUmVzcG9uZGVkQ291bnRcbiAgICAgICAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgICAgICAgYnVmZmVyVGltZVxuICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgY2FuY2VsSWZBbnlSZWZ1c2VcbiAgICAgICAgICAgIGNhbmNlbGxlZFxuICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgY29uZmVyZW5jZUFwcFxuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGR1cmF0aW9uXG4gICAgICAgICAgICBlbmFibGVBdHRlbmRlZVByZWZlcmVuY2VzXG4gICAgICAgICAgICBlbmFibGVDb25mZXJlbmNlXG4gICAgICAgICAgICBlbmFibGVIb3N0UHJlZmVyZW5jZXNcbiAgICAgICAgICAgIGVuZERhdGVcbiAgICAgICAgICAgIGV2ZW50SWRcbiAgICAgICAgICAgIGV4cGlyZURhdGVcbiAgICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgICAgZnJlcXVlbmN5XG4gICAgICAgICAgICBndWFyYW50ZWVBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHNcbiAgICAgICAgICAgIGlkXG4gICAgICAgICAgICBpbnRlcnZhbFxuICAgICAgICAgICAgbG9jYXRpb25cbiAgICAgICAgICAgIG1pblRocmVzaG9sZENvdW50XG4gICAgICAgICAgICBub3Rlc1xuICAgICAgICAgICAgb3JpZ2luYWxNZWV0aW5nSWRcbiAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICByZW1pbmRlcnNcbiAgICAgICAgICAgIHNlbmRVcGRhdGVzXG4gICAgICAgICAgICBzdGFydERhdGVcbiAgICAgICAgICAgIHN1bW1hcnlcbiAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICB0cmFuc3BhcmVuY3lcbiAgICAgICAgICAgIHVudGlsXG4gICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgdmlzaWJpbGl0eVxuICAgICAgICAgICAgd2luZG93RW5kRGF0ZVxuICAgICAgICAgICAgd2luZG93U3RhcnREYXRlXG4gICAgICAgICAgICBsb2NrQWZ0ZXJcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgO1xuICAgIC8vIFRoZSB2YXJpYWJsZSBwYXNzZWQgdG8gdGhlIG11dGF0aW9uIG5lZWRzIHRvIG1hdGNoIHRoZSBHcmFwaFFMIHNjaGVtYS5cbiAgICAvLyBJZiBgdXBzZXJ0TWVldGluZ0Fzc2lzdGAgZXhwZWN0cyBgaW5wdXQ6IHsgbWVldGluZ0Fzc2lzdDogTWVldGluZ0Fzc2lzdElucHV0ISB9YFxuICAgIC8vIHRoZW4gdmFyaWFibGVzIHNob3VsZCBiZSBgeyBpbnB1dDogeyBtZWV0aW5nQXNzaXN0OiBtZWV0aW5nQXNzaXN0IH0gfWBcbiAgICAvLyBJZiBpdCBleHBlY3RzIGBpbnB1dDogTWVldGluZ0Fzc2lzdElucHV0IWAsIHRoZW4gYHsgaW5wdXQ6IG1lZXRpbmdBc3Npc3QgfWBcbiAgICAvLyBGb3Igbm93LCBhc3N1bWluZyBgaW5wdXQ6IHsgbWVldGluZ0Fzc2lzdDogLi4uIH1gIGlzIGEgY29tbW9uIHBhdHRlcm4gZm9yIGN1c3RvbSBtdXRhdGlvbnMuXG4gICAgY29uc3QgbWVldGluZ0Fzc2lzdERvYyA9IChcbiAgICAgIGF3YWl0IGNsaWVudC5tdXRhdGU8e1xuICAgICAgICB1cHNlcnRNZWV0aW5nQXNzaXN0OiB7IG1lZXRpbmdBc3Npc3Q6IE1lZXRpbmdBc3Npc3RUeXBlIH07XG4gICAgICB9Pih7XG4gICAgICAgIG11dGF0aW9uOiB1cHNlcnRNZWV0aW5nQXNzaXN0R3JhcGhxbCxcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgLy8gVGhpcyBzdHJ1Y3R1cmUgZGVwZW5kcyBvbiBob3cgdGhlIFBvc3RHcmFwaGlsZSBtdXRhdGlvbiBgdXBzZXJ0TWVldGluZ0Fzc2lzdGAgaXMgZGVmaW5lZC5cbiAgICAgICAgICAvLyBBc3N1bWluZyBpdCB0YWtlcyBhbiAnaW5wdXQnIG9iamVjdCB3aGljaCB0aGVuIGhhcyBhICdtZWV0aW5nQXNzaXN0JyBmaWVsZCBvZiB0aGUgY29ycmVjdCBpbnB1dCB0eXBlLlxuICAgICAgICAgIGlucHV0OiB7IG1lZXRpbmdBc3Npc3Q6IG1lZXRpbmdBc3Npc3QgfSxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgKT8uZGF0YT8udXBzZXJ0TWVldGluZ0Fzc2lzdD8ubWVldGluZ0Fzc2lzdDtcblxuICAgIGNvbnNvbGUubG9nKG1lZXRpbmdBc3Npc3REb2MsICcgc3VjY2Vzc2Z1bGx5IGFkZGVkIG1lZXRpbmdBc3Npc3REb2MnKTtcblxuICAgIHJldHVybiBtZWV0aW5nQXNzaXN0RG9jO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gdXBzZXJ0IG1lZXRpbmcgYXNzaXN0Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCB1cHNlcnRNZWV0aW5nQXNzaXN0SW52aXRlTWFueSA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgbWVldGluZ0Fzc2lzdEludml0ZXM6IE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlW10gLy8gVGhpcyBtaWdodCBuZWVkIHRvIGJlIE1lZXRpbmdBc3Npc3RJbnZpdGVJbnB1dFtdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICAvLyBBU1NVTVBUSU9OOiBBIGN1c3RvbSBtdXRhdGlvbiAnYnVsa1Vwc2VydE1lZXRpbmdBc3Npc3RJbnZpdGVzJyBpcyBkZWZpbmVkIGluIFBvc3RHcmFwaGlsZVxuICAgIGNvbnN0IHVwc2VydE1lZXRpbmdBc3Npc3RJbnZpdGVHcmFwaHFsID0gZ3FsYFxuICAgICAgbXV0YXRpb24gQnVsa1Vwc2VydE1lZXRpbmdBc3Npc3RJbnZpdGVzKFxuICAgICAgICAkaW52aXRlczogW01lZXRpbmdBc3Npc3RJbnZpdGVJbnB1dCFdIVxuICAgICAgKSB7XG4gICAgICAgIGJ1bGtVcHNlcnRNZWV0aW5nQXNzaXN0SW52aXRlcyhpbnB1dDogeyBpbnZpdGVzOiAkaW52aXRlcyB9KSB7XG4gICAgICAgICAgIyBPciBzaW1pbGFyIHN0cnVjdHVyZVxuICAgICAgICAgICMgQXNzdW1pbmcgaXQgcmV0dXJucyBhIGxpc3Qgb2YgdGhlIHVwc2VydGVkIGludml0ZXNcbiAgICAgICAgICByZXN1bHRzOiBtZWV0aW5nQXNzaXN0SW52aXRlcyB7XG4gICAgICAgICAgICAjIE9yIGp1c3QgJ21lZXRpbmdBc3Npc3RJbnZpdGVzJ1xuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGVtYWlsXG4gICAgICAgICAgICBob3N0SWRcbiAgICAgICAgICAgIGhvc3ROYW1lXG4gICAgICAgICAgICBpZFxuICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICBuYW1lXG4gICAgICAgICAgICByZXNwb25zZVxuICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgIGNvbnRhY3RJZFxuICAgICAgICAgIH1cbiAgICAgICAgICAjIE9yIGFuIGFmZmVjdGVkIGNvdW50XG4gICAgICAgICAgIyBhZmZlY3RlZENvdW50XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgO1xuICAgIC8vIEFkanVzdCBnZW5lcmljIHR5cGUgYW5kIHZhcmlhYmxlIHN0cnVjdHVyZSBiYXNlZCBvbiBhY3R1YWwgUG9zdEdyYXBoaWxlIG11dGF0aW9uXG4gICAgY29uc3QgbWVldGluZ0Fzc2lzdEludml0ZURvY0RhdGEgPSAoXG4gICAgICBhd2FpdCBjbGllbnQubXV0YXRlPHtcbiAgICAgICAgYnVsa1Vwc2VydE1lZXRpbmdBc3Npc3RJbnZpdGVzOiB7IHJlc3VsdHM6IE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlW10gfTtcbiAgICAgIH0+KHtcbiAgICAgICAgbXV0YXRpb246IHVwc2VydE1lZXRpbmdBc3Npc3RJbnZpdGVHcmFwaHFsLFxuICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICBpbnZpdGVzOiBtZWV0aW5nQXNzaXN0SW52aXRlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgKT8uZGF0YT8uYnVsa1Vwc2VydE1lZXRpbmdBc3Npc3RJbnZpdGVzO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBtZWV0aW5nQXNzaXN0SW52aXRlRG9jRGF0YT8ucmVzdWx0cz8ubGVuZ3RoLFxuICAgICAgJyBzdWNjZXNzZnVsbHkgaW5zZXJ0ZWQgbWVldGluZ0Fzc2lzdEludml0ZURvY3MnXG4gICAgKTtcbiAgICByZXR1cm4gbWVldGluZ0Fzc2lzdEludml0ZURvY0RhdGE/LnJlc3VsdHM/Lmxlbmd0aDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwc2VydCBtZWV0aW5nIGFzc2lzdCBpbnZpdGUnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGluc2VydE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VzID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBtZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlczogTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgbWVldGluZ0Fzc2lzdEludml0ZURvY0RhdGEgPSAoXG4gICAgICBhd2FpdCBjbGllbnQubXV0YXRlPHtcbiAgICAgICAgaW5zZXJ0X01lZXRpbmdfQXNzaXN0X1ByZWZlcnJlZF9UaW1lX1JhbmdlOiB7XG4gICAgICAgICAgYWZmZWN0ZWRfcm93czogbnVtYmVyO1xuICAgICAgICAgIHJldHVybmluZzogTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXTtcbiAgICAgICAgfTtcbiAgICAgIH0+KHtcbiAgICAgICAgbXV0YXRpb246IGluc2VydE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VzTXV0YXRpb24sXG4gICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgIG1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICApPy5kYXRhPy5pbnNlcnRfTWVldGluZ19Bc3Npc3RfUHJlZmVycmVkX1RpbWVfUmFuZ2U7XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIG1lZXRpbmdBc3Npc3RJbnZpdGVEb2NEYXRhPy5hZmZlY3RlZF9yb3dzLFxuICAgICAgJyBzdWNjZXNzZnVsbHkgaW5zZXJ0ZWQgbWVldGluZyBhc3Npc3QgdGltZSByYW5nZXMgJ1xuICAgICk7XG5cbiAgICByZXR1cm4gbWVldGluZ0Fzc2lzdEludml0ZURvY0RhdGE/LmFmZmVjdGVkX3Jvd3M7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cHNlcnQgbWVldGluZyBhc3Npc3QgcHJlZmVycmVkIHRpbWUgcmFuZ2VzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZURhdGVzRm9yRnV0dXJlTWVldGluZ0Fzc2lzdHNVc2luZ1JydWxlID0gYXN5bmMgKFxuICB3aW5kb3dTdGFydERhdGU6IHN0cmluZyxcbiAgd2luZG93RW5kRGF0ZTogc3RyaW5nLFxuICBmcmVxdWVuY3k6IFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlLFxuICBpbnRlcnZhbDogbnVtYmVyLFxuICB1bnRpbDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBydWxlU3RhcnREYXRlID0gbmV3IFJSdWxlKHtcbiAgICAgIGR0c3RhcnQ6IGRheWpzKHdpbmRvd1N0YXJ0RGF0ZSkudG9EYXRlKCksXG4gICAgICBmcmVxOiBnZXRScnVsZUZyZXEoZnJlcXVlbmN5KSxcbiAgICAgIGludGVydmFsLFxuICAgICAgdW50aWw6IGRheWpzKHVudGlsKS50b0RhdGUoKSxcbiAgICB9KTtcblxuICAgIGNvbnN0IHdpbmRvd1N0YXJ0RGF0ZXNGb3JSZWN1cnJlbmNlID0gcnVsZVN0YXJ0RGF0ZVxuICAgICAgLmFsbCgpXG4gICAgICA/Lm1hcCgoZCkgPT4gZGF5anMudXRjKGQpLmZvcm1hdCgpKTtcblxuICAgIGNvbnN0IHJ1bGVFbmREYXRlID0gbmV3IFJSdWxlKHtcbiAgICAgIGR0c3RhcnQ6IGRheWpzKHdpbmRvd0VuZERhdGUpLnRvRGF0ZSgpLFxuICAgICAgZnJlcTogZ2V0UnJ1bGVGcmVxKGZyZXF1ZW5jeSksXG4gICAgICBpbnRlcnZhbCxcbiAgICAgIHVudGlsOiBkYXlqcyh1bnRpbCkudG9EYXRlKCksXG4gICAgfSk7XG5cbiAgICBjb25zdCB3aW5kb3dFbmREYXRlc0ZvclJlY3VycmVuY2UgPSBydWxlRW5kRGF0ZVxuICAgICAgLmFsbCgpXG4gICAgICA/Lm1hcCgoZCkgPT4gZGF5anMudXRjKGQpLmZvcm1hdCgpKTtcblxuICAgIC8vIHJlZm9ybWF0IGludG8gd2luZG93U3RhcnREYXRlcyBhbmQgd2luZG93RW5kRGF0ZXNcbiAgICBjb25zdCB0aW1lV2luZG93cyA9IHdpbmRvd1N0YXJ0RGF0ZXNGb3JSZWN1cnJlbmNlXG4gICAgICA/LnNsaWNlKDAsIHdpbmRvd0VuZERhdGVzRm9yUmVjdXJyZW5jZT8ubGVuZ3RoKVxuICAgICAgPy5tYXAoKHdpbmRvd1N0YXJ0RGF0ZSwgaW54KSA9PiB7XG4gICAgICAgIHJldHVybiB7XG4gICAgICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgICAgIHdpbmRvd0VuZERhdGU6IHdpbmRvd0VuZERhdGVzRm9yUmVjdXJyZW5jZT8uW2lueF0sXG4gICAgICAgIH07XG4gICAgICB9KTtcblxuICAgIHJldHVybiB0aW1lV2luZG93cztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgZ2VuZXJhdGUgZGF0ZXMgZm9yIG1lZXRpbmcgYXNzaXN0cyByZWN1cnJlbmNlJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBzZWFyY2hNZWV0aW5nQXNzaXN0cyA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHN1bW1hcnk6IHN0cmluZ1xuKTogUHJvbWlzZTxNZWV0aW5nQXNzaXN0VHlwZVtdIHwgW10gfCB1bmRlZmluZWQ+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBmb3JtYXR0ZWRTdW1tYXJ5ID0gYCUke3N1bW1hcnl9JWA7XG5cbiAgICBjb25zdCByZXN1bHRzID0gKFxuICAgICAgYXdhaXQgY2xpZW50LnF1ZXJ5PHsgTWVldGluZ19Bc3Npc3Q6IE1lZXRpbmdBc3Npc3RUeXBlW10gfT4oe1xuICAgICAgICBxdWVyeTogc2VhcmNoTWVldGluZ0Fzc2lzdHNRdWVyeSxcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIG5hbWU6IGZvcm1hdHRlZFN1bW1hcnksXG4gICAgICAgIH0sXG4gICAgICAgIGZldGNoUG9saWN5OiAnbm8tY2FjaGUnLFxuICAgICAgfSlcbiAgICApPy5kYXRhPy5NZWV0aW5nX0Fzc2lzdDtcblxuICAgIGNvbnNvbGUubG9nKHJlc3VsdHMsICcgcmVzdWx0cyBpbnNpZGUgc2VhcmNoTWVldGluZ0Fzc2lzdHMnKTtcblxuICAgIHJldHVybiByZXN1bHRzO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gc2VhcmNoIG1lZXRpbmcgYXNzaXN0cycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3Qgc2VuZEJ1bGtNZWV0aW5nQ2FuY2VsRW1haWwgPSBhc3luYyAoXG4gIGF0dGVuZGVlczogQXR0ZW5kZWVEZXRhaWxzRm9yQnVsa01lZXRpbmdDYW5jZWxsZWRUeXBlW10sXG4gIGhvc3RFbWFpbDogc3RyaW5nLFxuICBob3N0TmFtZTogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB1cmwgPSBlbWFpbE1lZXRpbmdDYW5jZWxVcmw7XG5cbiAgICBjb25zdCBhY2Nlc3NUb2tlbiA9IGF3YWl0IFNlc3Npb24uZ2V0QWNjZXNzVG9rZW4oKTtcblxuICAgIGNvbnN0IGNvbmZpZyA9IHtcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke2FjY2Vzc1Rva2VufWAsXG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICB9LFxuICAgIH07XG5cbiAgICBjb25zdCBkYXRhID0ge1xuICAgICAgYXR0ZW5kZWVzLFxuICAgICAgaG9zdE5hbWUsXG4gICAgICBob3N0RW1haWwsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3VsdHMgPSBhd2FpdCBheGlvcy5wb3N0KHVybCwgZGF0YSwgY29uZmlnKTtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgcmVzdWx0cyxcbiAgICAgICcgc3VjY2VzZnVsbHkgc2VudCBjYW5jZWwgbm90aWZpY2F0aW9ucyBmb3IgbWVldGluZyBhc3Npc3QnXG4gICAgKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHNlbmQgYnVsayBtZWV0aW5nIGNhbmNlbCBtZWV0aW5nJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBzZW5kQnVsa01lZXRpbmdJbnZpdGVFbWFpbCA9IGFzeW5jIChcbiAgYXR0ZW5kZWVzOiBBdHRlbmRlZURldGFpbHNGb3JCdWxrTWVldGluZ0ludml0ZVR5cGVbXSxcbiAgaG9zdEVtYWlsOiBzdHJpbmcsXG4gIGhvc3ROYW1lOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYXR0ZW5kZWVzLFxuICAgICAgJyBBdHRlbmRlZURldGFpbHNGb3JCdWxrTWVldGluZ0ludml0ZVR5cGUgaW5zaWRlIHNlbmRCdWxrTWVldGluZ0ludml0ZUVtYWlsJ1xuICAgICk7XG5cbiAgICBjb25zdCB1cmwgPSBlbWFpbE1lZXRpbmdJbnZpdGVVcmw7XG5cbiAgICBjb25zdCBhY2Nlc3NUb2tlbiA9IGF3YWl0IFNlc3Npb24uZ2V0QWNjZXNzVG9rZW4oKTtcblxuICAgIGNvbnN0IGNvbmZpZyA9IHtcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke2FjY2Vzc1Rva2VufWAsXG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICB9LFxuICAgIH07XG5cbiAgICBjb25zdCBkYXRhID0ge1xuICAgICAgYXR0ZW5kZWVzLFxuICAgICAgaG9zdE5hbWUsXG4gICAgICBob3N0RW1haWwsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3VsdHMgPSBhd2FpdCBheGlvcy5wb3N0KHVybCwgZGF0YSwgY29uZmlnKTtcblxuICAgIGNvbnNvbGUubG9nKHJlc3VsdHMsICcgc3VjY2Vzc2Z1bGx5IHNlbnQgdG8gZW1haWwgdG8gaW52aXRlcycpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gc2VuZCBidWxrIG1lZXRpbmcgaW52aXRlIGVtYWlsJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBjb252ZXJ0SW52aXRlZVR5cGVUb0NhbmNlbEVtYWlsUmVjaXBpZW50cyA9IChcbiAgaW52aXRlZXM6IE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlW11cbikgPT4ge1xuICBjb25zdCBjYW5jZWxFbWFpbHMgPSBpbnZpdGVlcz8ubWFwKChpKSA9PiAoe1xuICAgIGVtYWlsOiBpPy5lbWFpbCB8fCAnJyxcbiAgICBuYW1lOiBpPy5uYW1lLFxuICB9KSk7XG5cbiAgcmV0dXJuIGNhbmNlbEVtYWlscztcbn07XG5cbmV4cG9ydCBjb25zdCBjb252ZXJ0SW52aXRlZVR5cGVUb0ludml0ZUVtYWlsUmVjaXBpZW50cyA9IChcbiAgaW52aXRlZXM6IE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlW10sXG4gIG1lZXRpbmdJZDogc3RyaW5nXG4pID0+IHtcbiAgY29uc3QgaW52aXRlZUVtYWlscyA9IGludml0ZWVzPy5tYXAoKGkpID0+ICh7XG4gICAgZW1haWw6IGk/LmVtYWlsIHx8ICcnLFxuICAgIG5hbWU6IGk/Lm5hbWUsXG4gICAgbGluazogZ2VuZXJhdGVJbnZpdGVMaW5rKG1lZXRpbmdJZCwgaT8uaWQsIGk/LmVtYWlsKSxcbiAgfSkpO1xuXG4gIHJldHVybiBpbnZpdGVlRW1haWxzO1xufTtcblxuZXhwb3J0IGNvbnN0IHNlbmRNZWV0aW5nSW5mb1RvSG9zdEVtYWlsID0gYXN5bmMgKFxuICBhdHRlbmRlZXM6IEF0dGVuZGVlRGV0YWlsc1R5cGVbXSxcbiAgaG9zdEVtYWlsOiBzdHJpbmcsXG4gIGhvc3ROYW1lOiBzdHJpbmcsXG4gIHRpdGxlOiBzdHJpbmcsXG4gIG5vdGVzOiBzdHJpbmcsXG4gIHdpbmRvd1N0YXJ0RGF0ZTogc3RyaW5nLFxuICB3aW5kb3dFbmREYXRlOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYXR0ZW5kZWVzLFxuICAgICAgJyBBdHRlbmRlZURldGFpbHNUeXBlIGluc2lkZSBzZW5kTWVldGluZ0luZm9Ub0hvc3RFbWFpbCdcbiAgICApO1xuICAgIGNvbnN0IGFjY2Vzc1Rva2VuID0gYXdhaXQgU2Vzc2lvbi5nZXRBY2Nlc3NUb2tlbigpO1xuXG4gICAgY29uc3QgY29uZmlnID0ge1xuICAgICAgaGVhZGVyczoge1xuICAgICAgICBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7YWNjZXNzVG9rZW59YCxcbiAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgIH0sXG4gICAgfTtcblxuICAgIGNvbnN0IGRhdGE6IE1lZXRpbmdJbnZpdGVEZXRhaWxzVG9Ib3N0VHlwZSA9IHtcbiAgICAgIGF0dGVuZGVlcyxcbiAgICAgIGhvc3RFbWFpbCxcbiAgICAgIGhvc3ROYW1lLFxuICAgICAgdGl0bGUsXG4gICAgICBub3RlcyxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICB0aW1lem9uZSxcbiAgICB9O1xuXG4gICAgY29uc3QgdXJsID0gZW1haWxNZWV0aW5nSW5mb1RvSG9zdFVybDtcblxuICAgIGNvbnN0IHJlc3VsdHMgPSBhd2FpdCBheGlvcy5wb3N0KHVybCwgZGF0YSwgY29uZmlnKTtcblxuICAgIGNvbnNvbGUubG9nKHJlc3VsdHMsICcgc3VjY2Vzc2Z1bGx5IHNlbnQgZW1haWwgdG8gaG9zdCcpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gc2VuZCBlbWFpbCB0byBob3N0Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZUludml0ZUxpbmsgPSAoXG4gIG1lZXRpbmdJZDogc3RyaW5nLFxuICBhdHRlbmRlZUlkOiBzdHJpbmcsXG4gIHByaW1hcnlFbWFpbD86IHN0cmluZ1xuKSA9PlxuICAocHJpbWFyeUVtYWlsICYmXG4gICAgYCR7aGFuZHNoYWtlVXJsfT8ke3FzLnN0cmluZ2lmeSh7IG1lZXRpbmdJZCwgYXR0ZW5kZWVJZCwgcHJpbWFyeUVtYWlsIH0pfWApIHx8XG4gIGAke2hhbmRzaGFrZVVybH0/JHtxcy5zdHJpbmdpZnkoeyBtZWV0aW5nSWQsIGF0dGVuZGVlSWQgfSl9YDtcblxuZXhwb3J0IGNvbnN0IGFkZENvbnRhY3RUb0ludml0ZWVzID0gKFxuICBjOiBTZWxlY3RlZENvbnRhY3RUeXBlLFxuICBpbnZpdGVlczogTWVldGluZ0Fzc2lzdEludml0ZVR5cGVbXSxcbiAgc2V0STogRGlzcGF0Y2g8U2V0U3RhdGVBY3Rpb248TWVldGluZ0Fzc2lzdEludml0ZVR5cGVbXT4+LFxuICBzZXRQYXJlbnRJOiBEaXNwYXRjaDxTZXRTdGF0ZUFjdGlvbjxNZWV0aW5nQXNzaXN0SW52aXRlVHlwZVtdPj4sXG4gIGhvc3RJZDogc3RyaW5nLFxuICBob3N0TmFtZTogc3RyaW5nLFxuICBtZWV0aW5nSWQ6IHN0cmluZ1xuKSA9PiB7XG4gIGNvbnN0IGZvcm1hdHRlZEM6IE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlID0ge1xuICAgIGlkOiB1dWlkKCksXG4gICAgbmFtZTogYz8ubmFtZSB8fCAnJyxcbiAgICBlbWFpbDogYz8uZW1haWxzPy5maW5kKChlOiB7IHByaW1hcnk6IGJvb2xlYW4gfSkgPT4gZT8ucHJpbWFyeSk/LnZhbHVlLFxuICAgIGhvc3RJZCxcbiAgICBob3N0TmFtZSxcbiAgICBtZWV0aW5nSWQsXG4gICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIHVzZXJJZDogYz8udXNlcklkLFxuICAgIGNvbnRhY3RJZDogYz8uaWQsXG4gIH07XG5cbiAgY29uc3QgbmV3SW52aXRlZXMgPSBpbnZpdGVlcy5jb25jYXQoW2Zvcm1hdHRlZENdKTtcbiAgc2V0SShuZXdJbnZpdGVlcyk7XG4gIHNldFBhcmVudEkobmV3SW52aXRlZXMpO1xufTtcblxuZXhwb3J0IGNvbnN0IGFkZE9uZVRvTWFudWFsRW50cmllcyA9IChcbiAgaTogTWVldGluZ0Fzc2lzdEludml0ZVR5cGVbXSxcbiAgc2V0STogRGlzcGF0Y2g8U2V0U3RhdGVBY3Rpb248TWVldGluZ0Fzc2lzdEludml0ZVR5cGVbXT4+LFxuICBpbnZpdGVlczogTWVldGluZ0Fzc2lzdEludml0ZVR5cGVbXSxcbiAgc2V0SW52aXRlZXM6IERpc3BhdGNoPFNldFN0YXRlQWN0aW9uPE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlW10+PixcbiAgc2V0UGFyZW50STogRGlzcGF0Y2g8U2V0U3RhdGVBY3Rpb248TWVldGluZ0Fzc2lzdEludml0ZVR5cGVbXT4+LFxuICBob3N0SWQ6IHN0cmluZyxcbiAgaG9zdE5hbWU6IHN0cmluZyxcbiAgbWVldGluZ0lkOiBzdHJpbmdcbikgPT4ge1xuICBjb25zdCBuZXdWYWx1ZTogTWVldGluZ0Fzc2lzdEludml0ZVR5cGUgPSB7XG4gICAgaWQ6IHV1aWQoKSxcbiAgICBob3N0SWQsXG4gICAgZW1haWw6ICcnLFxuICAgIGhvc3ROYW1lLFxuICAgIG1lZXRpbmdJZCxcbiAgICBuYW1lOiAnJyxcbiAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gIH07XG5cbiAgY29uc3QgbmV3TWUgPSBfLnVuaXFXaXRoKGkuY29uY2F0KFtuZXdWYWx1ZV0pLCBfLmlzRXF1YWwpO1xuICBzZXRJKG5ld01lKTtcbiAgY29uc3QgbmV3SW52aXRlZXMgPSBfLnVuaXFXaXRoKGludml0ZWVzLmNvbmNhdChbbmV3VmFsdWVdKSwgXy5pc0VxdWFsKTtcbiAgc2V0SW52aXRlZXMobmV3SW52aXRlZXMpO1xuICBzZXRQYXJlbnRJKG5ld0ludml0ZWVzKTtcbn07XG5cbmV4cG9ydCBjb25zdCByZW1vdmVDb250YWN0RnJvbUludml0ZWUgPSAoXG4gIGM6IFNlbGVjdGVkQ29udGFjdFR5cGUsXG4gIGludml0ZWVzOiBNZWV0aW5nQXNzaXN0SW52aXRlVHlwZVtdLFxuICBzZXRJbnZpdGVlczogRGlzcGF0Y2g8U2V0U3RhdGVBY3Rpb248TWVldGluZ0Fzc2lzdEludml0ZVR5cGVbXT4+LFxuICBzZXRQYXJlbnRJOiBEaXNwYXRjaDxTZXRTdGF0ZUFjdGlvbjxNZWV0aW5nQXNzaXN0SW52aXRlVHlwZVtdPj5cbikgPT4ge1xuICBjb25zdCBmb3VuZEluZGV4ID0gaW52aXRlZXMuZmluZEluZGV4KChhKSA9PiBhPy5pZCA9PT0gYz8uaWQpO1xuXG4gIGlmIChmb3VuZEluZGV4ID4gLTEpIHtcbiAgICBjb25zdCBuZXdBdHRlbmRlZXMgPSBpbnZpdGVlc1xuICAgICAgLnNsaWNlKDAsIGZvdW5kSW5kZXgpXG4gICAgICAuY29uY2F0KGludml0ZWVzLnNsaWNlKGZvdW5kSW5kZXggKyAxKSk7XG5cbiAgICBzZXRJbnZpdGVlcyhuZXdBdHRlbmRlZXMpO1xuICAgIHNldFBhcmVudEkobmV3QXR0ZW5kZWVzKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHJlbW92ZUNvbnRhY3RGcm9tU2VhcmNoSW52aXRlZSA9IChcbiAgYzogU2VsZWN0ZWRDb250YWN0VHlwZSxcbiAgaW52aXRlZXM6IE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlW10sXG4gIHNlYXJjaFJlc3VsdHM6IFNlbGVjdGVkQ29udGFjdFR5cGVbXSxcbiAgc2V0SW52aXRlZXM6IERpc3BhdGNoPFNldFN0YXRlQWN0aW9uPE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlW10+PixcbiAgc2V0U2VhcmNoUmVzdWx0czogRGlzcGF0Y2g8U2V0U3RhdGVBY3Rpb248U2VsZWN0ZWRDb250YWN0VHlwZVtdPj4sXG4gIHNldFBhcmVudEk6IERpc3BhdGNoPFNldFN0YXRlQWN0aW9uPE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlW10+PlxuKSA9PiB7XG4gIGNvbnN0IGZvdW5kSW5kZXggPSBpbnZpdGVlcy5maW5kSW5kZXgoKGEpID0+IGE/LmlkID09PSBjPy5pZCk7XG5cbiAgaWYgKGZvdW5kSW5kZXggPiAtMSkge1xuICAgIGNvbnN0IG5ld0ludml0ZWVzID0gaW52aXRlZXNcbiAgICAgIC5zbGljZSgwLCBmb3VuZEluZGV4KVxuICAgICAgLmNvbmNhdChpbnZpdGVlcy5zbGljZShmb3VuZEluZGV4ICsgMSkpO1xuXG4gICAgc2V0SW52aXRlZXMobmV3SW52aXRlZXMpO1xuICAgIHNldFBhcmVudEkobmV3SW52aXRlZXMpO1xuICB9XG5cbiAgY29uc3QgZm91bmRTZWFyY2hJbmRleCA9IHNlYXJjaFJlc3VsdHM/LmZpbmRJbmRleCgoYSkgPT4gYT8uaWQgPT09IGM/LmlkKTtcblxuICBpZiAoZm91bmRTZWFyY2hJbmRleCA+IC0xKSB7XG4gICAgY29uc3QgbmV3U2VhcmNoSW52aXRlZXMgPSBzZWFyY2hSZXN1bHRzXG4gICAgICAuc2xpY2UoMCwgZm91bmRJbmRleClcbiAgICAgIC5jb25jYXQoc2VhcmNoUmVzdWx0cy5zbGljZShmb3VuZEluZGV4ICsgMSkpO1xuXG4gICAgc2V0U2VhcmNoUmVzdWx0cyhuZXdTZWFyY2hJbnZpdGVlcyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCByZW1vdmVFbnRyeUZyb21NYW51YWxFbnRyaWVzID0gKFxuICBtYW51YWxFbnRyaWVzOiBNZWV0aW5nQXNzaXN0SW52aXRlVHlwZVtdLFxuICBzZXRNYW51YWxFbnRyaWVzOiBEaXNwYXRjaDxTZXRTdGF0ZUFjdGlvbjxNZWV0aW5nQXNzaXN0SW52aXRlVHlwZVtdPj4sXG4gIGludml0ZWVzOiBNZWV0aW5nQXNzaXN0SW52aXRlVHlwZVtdLFxuICBzZXRJbnZpdGVlczogRGlzcGF0Y2g8U2V0U3RhdGVBY3Rpb248TWVldGluZ0Fzc2lzdEludml0ZVR5cGVbXT4+LFxuICBzZXRQYXJlbnRJOiBEaXNwYXRjaDxTZXRTdGF0ZUFjdGlvbjxNZWV0aW5nQXNzaXN0SW52aXRlVHlwZVtdPj4sXG4gIGluZGV4OiBudW1iZXIsXG4gIHBhcmVudEluZGV4OiBudW1iZXJcbikgPT4ge1xuICBjb25zdCBuZXdFbnRyaWVzID0gbWFudWFsRW50cmllc1xuICAgIC5zbGljZSgwLCBpbmRleClcbiAgICAuY29uY2F0KG1hbnVhbEVudHJpZXMuc2xpY2UoaW5kZXggKyAxKSk7XG4gIHNldE1hbnVhbEVudHJpZXMobmV3RW50cmllcyk7XG4gIGNvbnN0IG5ld0F0dGVuZGVlcyA9IGludml0ZWVzXG4gICAgLnNsaWNlKDAsIHBhcmVudEluZGV4KVxuICAgIC5jb25jYXQoaW52aXRlZXMuc2xpY2UocGFyZW50SW5kZXggKyAxKSk7XG4gIHNldEludml0ZWVzKG5ld0F0dGVuZGVlcyk7XG4gIHNldFBhcmVudEkobmV3QXR0ZW5kZWVzKTtcbn07XG5cbmV4cG9ydCBjb25zdCB1cGRhdGVDb250YWN0U2VsZWN0aW9uID0gKFxuICB2YWx1ZTogYm9vbGVhbixcbiAgc2VsZWN0ZWRDbzogU2VsZWN0ZWRDb250YWN0VHlwZSxcbiAgYTogU2VsZWN0ZWRDb250YWN0VHlwZVtdLFxuICBzZXRBOiBEaXNwYXRjaDxTZXRTdGF0ZUFjdGlvbjxTZWxlY3RlZENvbnRhY3RUeXBlW10+PixcbiAgaW5kZXg6IG51bWJlclxuKSA9PiB7XG4gIGNvbnN0IG5ld0EgPSBfLmNsb25lRGVlcChcbiAgICBhXG4gICAgICAuc2xpY2UoMCwgaW5kZXgpXG4gICAgICAuY29uY2F0KFt7IC4uLnNlbGVjdGVkQ28sIHNlbGVjdGVkOiB2YWx1ZSB9XSlcbiAgICAgIC5jb25jYXQoYS5zbGljZShpbmRleCArIDEpKVxuICApO1xuICBzZXRBKG5ld0EpO1xufTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZVNlYXJjaENvbnRhY3RTZWxlY3Rpb24gPSAoXG4gIHZhbHVlOiBib29sZWFuLFxuICBzZWxlY3RlZENvOiBTZWxlY3RlZENvbnRhY3RUeXBlLFxuICBhOiBTZWxlY3RlZENvbnRhY3RUeXBlW10sXG4gIHNlYXJjaEE6IFNlbGVjdGVkQ29udGFjdFR5cGVbXSxcbiAgc2V0QTogRGlzcGF0Y2g8U2V0U3RhdGVBY3Rpb248U2VsZWN0ZWRDb250YWN0VHlwZVtdPj4sXG4gIHNldFNlYXJjaEE6IERpc3BhdGNoPFNldFN0YXRlQWN0aW9uPFNlbGVjdGVkQ29udGFjdFR5cGVbXT4+LFxuICBzZWFyY2hJbmRleDogbnVtYmVyXG4pID0+IHtcbiAgY29uc3QgZmluZEluZGV4ID0gYT8uZmluZEluZGV4KChwKSA9PiBwPy5pZCA9PT0gc2VsZWN0ZWRDbz8uaWQpO1xuXG4gIGlmIChmaW5kSW5kZXggPiAtMSkge1xuICAgIGNvbnN0IG5ld0EgPSBfLmNsb25lRGVlcChcbiAgICAgIGFcbiAgICAgICAgLnNsaWNlKDAsIGZpbmRJbmRleClcbiAgICAgICAgLmNvbmNhdChbeyAuLi5zZWxlY3RlZENvLCBzZWxlY3RlZDogdmFsdWUgfV0pXG4gICAgICAgIC5jb25jYXQoYS5zbGljZShmaW5kSW5kZXggKyAxKSlcbiAgICApO1xuICAgIHNldEEobmV3QSk7XG4gIH1cblxuICBjb25zdCBuZXdTZWFyY2hBID0gXy5jbG9uZURlZXAoXG4gICAgc2VhcmNoQVxuICAgICAgLnNsaWNlKDAsIHNlYXJjaEluZGV4KVxuICAgICAgLmNvbmNhdChbeyAuLi5zZWxlY3RlZENvLCBzZWxlY3RlZDogdmFsdWUgfV0pXG4gICAgICAuY29uY2F0KGEuc2xpY2Uoc2VhcmNoSW5kZXggKyAxKSlcbiAgKTtcbiAgc2V0U2VhcmNoQShuZXdTZWFyY2hBKTtcbn07XG5cbmV4cG9ydCBjb25zdCB1cGRhdGVFbnRyeUluTWFudWFsRW50cmllcyA9IChcbiAgaTogTWVldGluZ0Fzc2lzdEludml0ZVR5cGVbXSxcbiAgc2V0STogRGlzcGF0Y2g8U2V0U3RhdGVBY3Rpb248TWVldGluZ0Fzc2lzdEludml0ZVR5cGVbXT4+LFxuICBpbmRleDogbnVtYmVyLFxuICBpbnZpdGVlczogTWVldGluZ0Fzc2lzdEludml0ZVR5cGVbXSxcbiAgc2V0SW52aXRlZWVzOiBEaXNwYXRjaDxTZXRTdGF0ZUFjdGlvbjxNZWV0aW5nQXNzaXN0SW52aXRlVHlwZVtdPj4sXG4gIHNldFBhcmVudEk6IERpc3BhdGNoPFNldFN0YXRlQWN0aW9uPE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlW10+PixcbiAgcGFyZW50SW5kZXg6IG51bWJlcixcbiAgZW1haWw/OiBzdHJpbmcsXG4gIGRpc3BsYXlOYW1lPzogc3RyaW5nXG4pID0+IHtcbiAgY29uc3Qgb2xkRG9jID0gaVtpbmRleF07XG4gIGNvbnN0IG5ld0RvYzogTWVldGluZ0Fzc2lzdEludml0ZVR5cGUgPSB7XG4gICAgLi4ub2xkRG9jLFxuICAgIG5hbWU6IGRpc3BsYXlOYW1lIHx8IG9sZERvYz8ubmFtZSxcbiAgICBlbWFpbDogZW1haWwgfHwgb2xkRG9jPy5lbWFpbCxcbiAgfTtcblxuICBjb25zdCBuZXdJID0gaVxuICAgIC5zbGljZSgwLCBpbmRleClcbiAgICAuY29uY2F0KFtuZXdEb2NdKVxuICAgIC5jb25jYXQoaS5zbGljZShpbmRleCArIDEpKTtcbiAgc2V0SShuZXdJKTtcbiAgY29uc3QgbmV3SW52aXRlZXMgPSBpbnZpdGVlc1xuICAgIC5zbGljZSgwLCBwYXJlbnRJbmRleClcbiAgICAuY29uY2F0KFtuZXdEb2NdKVxuICAgIC5jb25jYXQoaW52aXRlZXMuc2xpY2UocGFyZW50SW5kZXggKyAxKSk7XG4gIHNldEludml0ZWVlcyhuZXdJbnZpdGVlcyk7XG4gIHNldFBhcmVudEkobmV3SW52aXRlZXMpO1xufTtcbiJdfQ==