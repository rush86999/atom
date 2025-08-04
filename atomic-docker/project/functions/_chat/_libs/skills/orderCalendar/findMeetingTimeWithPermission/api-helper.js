import qs from 'qs';
import { handshakeUrl } from './constants';
import requiredFields from './requiredFields';
import { extrapolateStartDateFromJSONData, findContactByEmailGivenUserId, getCalendarIntegrationByName, getUserContactInfosGivenIds, getGlobalCalendar, listUserContactInfosGivenUserId, getContactByNameWithUserId, upsertMeetingAssistOne, createHostAttendee, getUserGivenId, upsertMeetingAssistInviteMany, generateDateTime, generateJSONDataFromUserInput, generateAssistantMessageFromAPIResponseForUserQuery, generateAssistantMessageToRequestUserForMissingFields, extrapolateEndDateFromJSONData, extrapolateDateFromJSONData, generateMissingFieldsDateTime, generateMissingFieldsJSONDataFromUserInput, } from '@chat/_libs/api-helper';
import { getChatMeetingPreferenceGivenUserId } from '../scheduleMeeting/api-helper';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import { googleCalendarName } from '@chat/_libs/constants';
import { v4 as uuid } from 'uuid';
import { sendEmail } from '@/_utils/email/email';
import { ENV } from '@/_utils/env';
// const client = new LambdaClient({
//     region: 'us-east-1'
// })
export const generateInviteLink = (meetingId, attendeeId, primaryEmail) => (primaryEmail &&
    `${handshakeUrl}?${qs.stringify({ meetingId, attendeeId, primaryEmail })}`) ||
    `${handshakeUrl}?${qs.stringify({ meetingId, attendeeId })}`;
export const convertInviteeTypeToInviteEmailRecipients = (invitees, meetingId) => {
    const inviteeEmails = invitees?.map((i) => ({
        email: i?.email || '',
        name: i?.name,
        link: generateInviteLink(meetingId, i?.id, i?.email),
    }));
    return inviteeEmails;
};
const createMeetingAssistInvitees = async (invitees) => {
    try {
        console.log(invitees, ' invitees');
        await upsertMeetingAssistInviteMany(invitees);
    }
    catch (e) {
        console.log(e, ' unable to create meeting assist invitees');
    }
};
// meeting-info-to-host-auth
export const sendMeetingInfoToHostEmail = async (attendees, hostEmail, hostName, title, notes, windowStartDate, windowEndDate, timezone) => {
    try {
        let attendeeHtmlString = '';
        let attendeeTextString = '';
        for (const attendee of attendees) {
            attendeeHtmlString += '<p>';
            attendeeHtmlString += '<a href=';
            attendeeHtmlString += '"mailto:';
            attendeeHtmlString += attendee?.email;
            attendeeHtmlString += '"';
            attendeeHtmlString += '>';
            attendeeHtmlString += attendee?.name || attendee?.email;
            attendeeHtmlString += '</a>';
            attendeeHtmlString += ' - ';
            attendeeHtmlString += '<a href=';
            attendeeHtmlString += '"';
            attendeeHtmlString += attendee?.link;
            attendeeHtmlString += '"';
            attendeeHtmlString += '>';
            attendeeHtmlString += 'link';
            attendeeHtmlString += '</a>';
            attendeeHtmlString += '</p>';
            attendeeTextString += attendee?.name;
            attendeeTextString += ' ' + '(' + attendee?.email + ')' + ' ';
            attendeeTextString += ' - ';
            attendeeTextString += attendee?.link;
            attendeeTextString += '\r\n';
        }
        const template = 'meeting-invite-details-to-host';
        await sendEmail({
            template,
            locals: {
                hostName,
                title,
                notes,
                windowStartDate: dayjs(windowStartDate)
                    .tz(timezone)
                    .format('dddd, MMMM D, YYYY h:mm A'),
                windowEndDate: dayjs(windowEndDate)
                    .tz(timezone)
                    .format('dddd, MMMM D, YYYY h:mm A'),
                attendeeHtmlString,
                displayName: hostName,
                email: hostEmail,
                locale: ENV.AUTH_LOCALE_DEFAULT,
                serverUrl: ENV.FUNCTION_SERVER_URL,
                clientUrl: ENV.APP_CLIENT_URL,
            },
            message: {
                to: hostEmail,
                headers: {
                    'x-email-template': {
                        prepared: true,
                        value: template,
                    },
                },
            },
        });
    }
    catch (e) {
        console.log(e, ' unable to send email to host');
    }
};
export const sendBulkMeetingInviteEmail = async (attendees, hostEmail, hostName) => {
    try {
        console.log(attendees, ' AttendeeDetailsForBulkMeetingInviteType inside sendBulkMeetingInviteEmail');
        const data = {
            attendees,
            hostName,
            hostEmail,
        };
        const template = 'bulk-meeting-invite';
        for (const attendee of attendees) {
            await sendEmail({
                template,
                locals: {
                    name: attendee?.name,
                    hostEmail,
                    hostName,
                    link: attendee?.link,
                    displayName: attendee?.name,
                    email: attendee?.email,
                    locale: ENV.AUTH_LOCALE_DEFAULT,
                    serverUrl: ENV.FUNCTION_SERVER_URL,
                    clientUrl: ENV.APP_CLIENT_URL,
                },
                message: {
                    to: attendee?.email,
                    headers: {
                        'x-email-template': {
                            prepared: true,
                            value: template,
                        },
                    },
                },
            });
        }
    }
    catch (e) {
        console.log(e, ' unable to send bulk meeting invite email');
    }
};
// FindMeetingTimeWithPermissionType
export const finalStepFMTWP = async (body, primaryHostAttendeeInfo, defaultMeetingPreferences, user, meetingId, windowStartDate, windowEndDate, response) => {
    try {
        // get primary calendar
        const primaryCalendar = await getGlobalCalendar(body?.userId);
        // validate
        if (!primaryCalendar?.id) {
            throw new Error('no primary calendar found inside createAgenda');
        }
        // get client type
        const calIntegration = await getCalendarIntegrationByName(body?.userId, googleCalendarName);
        // validate
        if (!calIntegration?.clientType) {
            throw new Error('no client type inside calendar integration inside create agenda');
        }
        // findContactByEmailGivenUserId
        // get attendees with provided emails
        const aWithEmails = body?.attendees?.filter((a) => !!a?.email);
        const aWithContactInfos = await getUserContactInfosGivenIds(aWithEmails?.map((a) => a?.email));
        const inviteesFromExtractedJSON = body?.attendees;
        const invitees = [];
        for (const i of inviteesFromExtractedJSON) {
            const contact = await findContactByEmailGivenUserId(body?.userId, i.email);
            const userIdFound = aWithContactInfos?.find((b) => b?.id === i?.email);
            const invitee = {
                id: uuid(),
                hostId: body?.userId,
                hostName: primaryHostAttendeeInfo?.name,
                userId: i?.isHost ? body?.userId : userIdFound?.userId || uuid(),
                name: i?.name ||
                    contact?.name ||
                    `${contact?.firstName} ${contact?.lastName}`,
                contactId: contact?.id,
                email: i?.email,
                updatedAt: dayjs().format(),
                createdDate: dayjs().format(),
                meetingId,
            };
            invitees.push(invitee);
        }
        const meetingAssist = {
            id: meetingId,
            userId: body?.userId,
            summary: body?.title,
            notes: body?.description,
            windowStartDate: body?.windowStartDate,
            windowEndDate: body?.windowEndDate,
            timezone: body?.timezone,
            location: { title: body?.location || '' },
            priority: body?.priority || 1,
            enableConference: !!body?.conferenceApp || !!defaultMeetingPreferences?.conferenceApp,
            conferenceApp: body?.conferenceApp || defaultMeetingPreferences?.conferenceApp,
            sendUpdates: defaultMeetingPreferences?.sendUpdates,
            guestsCanInviteOthers: defaultMeetingPreferences?.guestsCanInviteOthers,
            transparency: defaultMeetingPreferences?.transparency,
            visibility: defaultMeetingPreferences?.visibility,
            createdDate: dayjs().format(),
            updatedAt: dayjs().format(),
            useDefaultAlarms: body?.reminders
                ? false
                : defaultMeetingPreferences?.reminders?.length > 0
                    ? false
                    : true,
            reminders: body?.reminders || defaultMeetingPreferences?.reminders,
            cancelIfAnyRefuse: false,
            enableAttendeePreferences: true,
            attendeeCanModify: false,
            expireDate: dayjs(body?.windowEndDate).subtract(1, 'd').format(),
            duration: body?.duration,
            calendarId: primaryCalendar?.id || '',
            bufferTime: body?.bufferTime
                ? {
                    beforeEvent: body?.bufferTime?.beforeEvent,
                    afterEvent: body?.bufferTime?.afterEvent,
                }
                : undefined,
            anyoneCanAddSelf: defaultMeetingPreferences?.anyoneCanAddSelf,
            guestsCanSeeOtherGuests: defaultMeetingPreferences?.guestsCanSeeOtherGuests,
            minThresholdCount: body?.attendees?.length,
            guaranteeAvailability: false,
            attendeeRespondedCount: 1,
            attendeeCount: 1,
            cancelled: false,
            frequency: body?.recur?.frequency,
            interval: body?.recur?.interval,
            until: body?.recur?.endDate && dayjs(body?.recur?.endDate).format(),
            originalMeetingId: body?.recur ? meetingId : undefined,
        };
        await upsertMeetingAssistOne(meetingAssist);
        await createHostAttendee(body?.userId, meetingId, body?.timezone, primaryHostAttendeeInfo?.email, primaryHostAttendeeInfo?.name);
        await createMeetingAssistInvitees(invitees);
        const inviteeEmails = convertInviteeTypeToInviteEmailRecipients(invitees, meetingId);
        await sendMeetingInfoToHostEmail(inviteeEmails, user?.email || '', primaryHostAttendeeInfo?.name || user?.name || '', body?.title, body?.description, dayjs(windowStartDate).format(), dayjs(windowEndDate).format(), body?.timezone);
        const filteredInviteeEmails = inviteeEmails?.filter((i) => !!i?.email);
        await sendBulkMeetingInviteEmail(filteredInviteeEmails, user?.email || '', primaryHostAttendeeInfo?.name || user?.name || '');
        // success response
        response.query = 'completed';
        response.data =
            'Successfully sent an email to invitees to get availability and time preferences for finding a meeting time';
        return response;
    }
    catch (e) {
        console.log(e, ' unable to final step fmtwp');
    }
};
export const processFMTWPPending = async (userId, timezone, jsonBody, dateJSONBody, currentTime) => {
    try {
        let duration = 0;
        const yearStart = dateJSONBody?.findTimeWindowStart?.year;
        const monthStart = dateJSONBody?.findTimeWindowStart?.month;
        const dayStart = dateJSONBody?.findTimeWindowStart?.day;
        const isoWeekdayStart = dateJSONBody?.findTimeWindowStart?.isoWeekday;
        const hourStart = dateJSONBody?.findTimeWindowStart?.hour;
        const minuteStart = dateJSONBody?.findTimeWindowStart?.minute;
        const startTimeStart = dateJSONBody?.findTimeWindowStart?.startTime;
        const yearEnd = dateJSONBody?.findTimeWindowEnd?.year;
        const monthEnd = dateJSONBody?.findTimeWindowEnd?.month;
        const dayEnd = dateJSONBody?.findTimeWindowEnd?.day;
        const isoWeekdayEnd = dateJSONBody?.findTimeWindowEnd?.isoWeekday;
        const hourEnd = dateJSONBody?.findTimeWindowEnd?.hour;
        const minuteEnd = dateJSONBody?.findTimeWindowEnd?.minute;
        const endTimeEnd = dateJSONBody?.findTimeWindowEnd?.startTime;
        const missingFields = {
            required: [],
            dateTime: { required: [] },
        };
        const response = {
            query: '',
            data: {},
            skill: 'findMeetingTimeWithPermission',
        };
        const windowStartDate = extrapolateStartDateFromJSONData(currentTime, timezone, yearStart, monthStart, dayStart, isoWeekdayStart, hourStart, minuteStart, startTimeStart, dateJSONBody?.findTimeWindowStart?.relativeTimeChangeFromNow, dateJSONBody?.findTimeWindowStart?.relativeTimeFromNow);
        const windowEndDate = extrapolateEndDateFromJSONData(currentTime, timezone, yearEnd, monthEnd, dayEnd, isoWeekdayEnd, hourEnd, minuteEnd, endTimeEnd, dateJSONBody?.findTimeWindowEnd?.relativeTimeChangeFromNow, dateJSONBody?.findTimeWindowEnd?.relativeTimeFromNow);
        // get default values
        const defaultMeetingPreferences = await getChatMeetingPreferenceGivenUserId(userId);
        if (dateJSONBody?.duration) {
            duration = dateJSONBody?.duration;
        }
        else if (defaultMeetingPreferences?.duration) {
            duration = defaultMeetingPreferences?.duration;
        }
        else {
            duration = 30;
        }
        // take care of any recurring dates
        let recurObject = {};
        if (dateJSONBody?.recur?.frequency) {
            const recurEndDate = extrapolateDateFromJSONData(currentTime, timezone, dateJSONBody?.recur?.endDate?.year, dateJSONBody?.recur?.endDate?.month, dateJSONBody?.recur?.endDate?.day, dateJSONBody?.recur?.endDate?.isoWeekday, dateJSONBody?.recur?.endDate?.hour, dateJSONBody?.recur?.endDate?.minute, dateJSONBody?.recur?.endDate?.startTime, dateJSONBody?.recur?.endDate?.relativeTimeChangeFromNow, dateJSONBody?.recur?.endDate?.relativeTimeFromNow);
            recurObject = {
                frequency: dateJSONBody?.recur?.frequency ||
                    jsonBody?.params?.recurrence?.frequency,
                interval: dateJSONBody?.recur?.interval ||
                    jsonBody?.params?.recurrence?.interval,
            };
            if (dateJSONBody?.recur?.byWeekDay) {
                recurObject.byWeekDay =
                    dateJSONBody?.recur?.byWeekDay;
            }
            if (dateJSONBody?.recur?.byMonthDay) {
                recurObject.byMonthDay =
                    dateJSONBody?.recur?.byMonthDay;
            }
            if (dateJSONBody?.recur?.occurrence) {
                recurObject.occurrence =
                    dateJSONBody?.recur?.occurrence;
            }
            if (recurEndDate || jsonBody?.params?.recurrence?.endDate) {
                recurObject.endDate =
                    recurEndDate || jsonBody?.params?.recurrence?.endDate;
            }
        }
        const body = {
            userId,
            timezone,
            title: jsonBody?.params?.title ||
                jsonBody?.params?.summary ||
                jsonBody?.params?.description ||
                jsonBody?.params?.taskList?.[0]?.task,
            attendees: jsonBody?.params?.attendees,
            method: dateJSONBody?.method,
            duration,
            description: jsonBody?.params?.description || jsonBody?.params?.notes,
            conferenceApp: jsonBody?.params?.conference?.app ||
                defaultMeetingPreferences?.conferenceApp,
            windowStartDate: jsonBody?.params?.startTime || windowStartDate || currentTime,
            windowEndDate: jsonBody?.params?.endTime ||
                windowEndDate ||
                dayjs(currentTime).add(7, 'd').format(),
            bufferTime: jsonBody?.params?.bufferTime || defaultMeetingPreferences?.bufferTime,
            reminders: jsonBody?.params?.alarms || defaultMeetingPreferences?.reminders || [],
            priority: jsonBody?.params?.priority || 1,
            timePreferences: dateJSONBody?.timePreferences || [],
            location: jsonBody?.params?.location,
            transparency: jsonBody?.params?.transparency,
            visibility: jsonBody?.params.visibility,
        };
        if (recurObject?.frequency) {
            body.recur = recurObject;
        }
        console.log(body, ' body');
        // validate remaining required fields
        if (!body?.title) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[0]);
            response.data = missingFields;
            response.prevData = body;
            // response.prevDataExtra = {
            //     windowStartDate,
            //     windowEndDate,
            // }
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (!(body?.attendees?.length > 0)) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[1]);
            response.data = missingFields;
            response.prevData = body;
            // response.prevDataExtra = {
            //     windowStartDate,
            //     windowEndDate,
            // }
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        // get info of contacts without emails provided and assign values
        const newAttendees = [];
        for (const a of body?.attendees) {
            if (!a?.email) {
                const contact = await getContactByNameWithUserId(userId, `%${a?.name}%`);
                if (contact?.emails?.[0]?.value) {
                    const primaryEmail = contact?.emails?.find((e) => !!e.primary)?.value;
                    const anyEmail = contact?.emails?.[0]?.value;
                    newAttendees.push({ ...a, email: primaryEmail || anyEmail });
                }
                else {
                    response.query = 'missing_fields';
                    missingFields.required.push(requiredFields.required?.[1]?.['and']?.[2]);
                    response.data = missingFields;
                    response.prevData = body;
                    // response.prevDataExtra = {
                    //     windowStartDate,
                    //     windowEndDate,
                    // }
                    response.prevJsonBody = jsonBody;
                    response.prevDateJsonBody = dateJSONBody;
                }
            }
            else {
                newAttendees.push(a);
            }
        }
        body.attendees = newAttendees;
        const meetingId = uuid();
        // get host info
        const userContactInfos = await listUserContactInfosGivenUserId(userId);
        // check if any host info
        const providedHostInfo = body?.attendees?.find((a) => a?.isHost === true);
        const primaryInfoItem = userContactInfos?.find((u) => u.primary && u.type === 'email');
        const user = await getUserGivenId(userId);
        const primaryHostAttendeeInfo = {
            name: primaryInfoItem?.name || user?.name,
            email: primaryInfoItem?.id || user?.email,
            isHost: true,
        };
        if (!providedHostInfo && primaryHostAttendeeInfo?.email) {
            body?.attendees.push(primaryHostAttendeeInfo);
        }
        const hostInfo = providedHostInfo || primaryHostAttendeeInfo;
        if (!hostInfo?.email) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[1]['and'][1]);
            response.data = missingFields;
            response.prevData = body;
            // response.prevDataExtra = {
            //     windowStartDate,
            //     windowEndDate,
            // }
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepFMTWP(body, primaryHostAttendeeInfo, defaultMeetingPreferences, user, meetingId, windowStartDate, windowEndDate, response);
        return response2;
        // get primary calendar
        // const primaryCalendar = await getGlobalCalendar(userId)
    }
    catch (e) {
        console.log(e, ' unable to process find meeting time');
    }
};
export const processFMTWPMissingFieldsReturned = async (userId, timezone, jsonBody, dateJSONBody, currentTime, messageHistoryObject) => {
    try {
        let duration = 0;
        const yearStart = dateJSONBody?.findTimeWindowStart?.year ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.year;
        const monthStart = dateJSONBody?.findTimeWindowStart?.month ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.month;
        const dayStart = dateJSONBody?.findTimeWindowStart?.day ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.day;
        const isoWeekdayStart = dateJSONBody?.findTimeWindowStart?.isoWeekday ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.isoWeekday;
        const hourStart = dateJSONBody?.findTimeWindowStart?.hour ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.hour;
        const minuteStart = dateJSONBody?.findTimeWindowStart?.minute ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.minute;
        const startTimeStart = dateJSONBody?.findTimeWindowStart?.startTime ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.startTime;
        const yearEnd = dateJSONBody?.findTimeWindowEnd?.year ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.year;
        const monthEnd = dateJSONBody?.findTimeWindowEnd?.month ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.month;
        const dayEnd = dateJSONBody?.findTimeWindowEnd?.day ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.day;
        const isoWeekdayEnd = dateJSONBody?.findTimeWindowEnd?.isoWeekday ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.isoWeekday;
        const hourEnd = dateJSONBody?.findTimeWindowEnd?.hour ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.hour;
        const minuteEnd = dateJSONBody?.findTimeWindowEnd?.minute ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.minute;
        const endTimeEnd = dateJSONBody?.findTimeWindowEnd?.startTime ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.startTime;
        const missingFields = {
            required: [],
            dateTime: { required: [] },
        };
        const response = {
            query: '',
            data: {},
            skill: 'findMeetingTimeWithPermission',
        };
        const windowStartDate = extrapolateStartDateFromJSONData(currentTime, timezone, yearStart, monthStart, dayStart, isoWeekdayStart, hourStart, minuteStart, startTimeStart, dateJSONBody?.findTimeWindowStart?.relativeTimeChangeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart
                ?.relativeTimeChangeFromNow, dateJSONBody?.findTimeWindowStart?.relativeTimeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart
                ?.relativeTimeFromNow);
        const windowEndDate = extrapolateEndDateFromJSONData(currentTime, timezone, yearEnd, monthEnd, dayEnd, isoWeekdayEnd, hourEnd, minuteEnd, endTimeEnd, dateJSONBody?.findTimeWindowEnd?.relativeTimeChangeFromNow, dateJSONBody?.findTimeWindowEnd?.relativeTimeFromNow);
        // get default values
        const defaultMeetingPreferences = await getChatMeetingPreferenceGivenUserId(userId);
        if (dateJSONBody?.duration ||
            messageHistoryObject?.prevDateJsonBody?.duration) {
            duration =
                dateJSONBody?.duration ||
                    messageHistoryObject?.prevDateJsonBody?.duration;
        }
        else if (defaultMeetingPreferences?.duration) {
            duration = defaultMeetingPreferences?.duration;
        }
        else {
            duration = 30;
        }
        // take care of any recurring dates
        let recurObject = {};
        if (dateJSONBody?.recur?.frequency ||
            messageHistoryObject?.prevDateJsonBody?.recur?.frequency) {
            const recurEndDate = extrapolateDateFromJSONData(currentTime, timezone, dateJSONBody?.recur?.endDate?.year ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.year, dateJSONBody?.recur?.endDate?.month ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.month, dateJSONBody?.recur?.endDate?.day ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.day, dateJSONBody?.recur?.endDate?.isoWeekday ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.isoWeekday, dateJSONBody?.recur?.endDate?.hour ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.hour, dateJSONBody?.recur?.endDate?.minute ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.minute, dateJSONBody?.recur?.endDate?.startTime ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.startTime, dateJSONBody?.recur?.endDate?.relativeTimeChangeFromNow ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate
                    ?.relativeTimeChangeFromNow, dateJSONBody?.recur?.endDate?.relativeTimeFromNow ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate
                    ?.relativeTimeFromNow);
            recurObject = {
                frequency: dateJSONBody?.recur?.frequency ||
                    messageHistoryObject?.prevDateJsonBody?.recur?.frequency,
                interval: dateJSONBody?.recur?.interval ||
                    messageHistoryObject?.prevDateJsonBody?.recur?.interval,
            };
            if (dateJSONBody?.recur?.byWeekDay ||
                messageHistoryObject?.prevDateJsonBody?.recur?.byWeekDay) {
                recurObject.byWeekDay =
                    dateJSONBody?.recur?.byWeekDay ||
                        messageHistoryObject?.prevDateJsonBody?.recur?.byWeekDay;
            }
            if (dateJSONBody?.recur?.byMonthDay ||
                messageHistoryObject?.prevDateJsonBody?.recur?.byMonthDay) {
                recurObject.byMonthDay =
                    dateJSONBody?.recur?.byMonthDay ||
                        messageHistoryObject?.prevDateJsonBody?.recur?.byMonthDay;
            }
            if (dateJSONBody?.recur?.occurrence ||
                messageHistoryObject?.prevDateJsonBody?.recur?.occurrence) {
                recurObject.occurrence =
                    dateJSONBody?.recur?.occurrence ||
                        messageHistoryObject?.prevDateJsonBody?.recur?.occurrence;
            }
            if (recurEndDate ||
                messageHistoryObject?.prevJsonBody?.params?.recurrence?.endDate ||
                jsonBody?.params?.recurrence?.endDate) {
                recurObject.endDate =
                    recurEndDate ||
                        messageHistoryObject?.prevJsonBody?.params?.recurrence?.endDate ||
                        jsonBody?.params?.recurrence?.endDate;
            }
        }
        const newBody = {
            userId,
            timezone,
            title: jsonBody?.params?.title ||
                jsonBody?.params?.summary ||
                jsonBody?.params?.description ||
                jsonBody?.params?.taskList?.[0]?.task ||
                messageHistoryObject?.prevJsonBody?.params?.title ||
                messageHistoryObject?.prevJsonBody?.params?.summary ||
                messageHistoryObject?.prevJsonBody?.params?.description ||
                messageHistoryObject?.prevJsonBody?.params?.taskList?.[0]?.task,
            attendees: jsonBody?.params?.attendees ||
                messageHistoryObject?.prevJsonBody?.params?.attendees,
            method: dateJSONBody?.method,
            duration,
            description: jsonBody?.params?.description ||
                jsonBody?.params?.notes ||
                messageHistoryObject?.prevJsonBody?.params?.description ||
                messageHistoryObject?.prevJsonBody?.params?.notes,
            conferenceApp: jsonBody?.params?.conference?.app ||
                messageHistoryObject?.prevJsonBody?.params?.conference?.app ||
                defaultMeetingPreferences?.conferenceApp,
            windowStartDate: jsonBody?.params?.startTime ||
                messageHistoryObject?.prevJsonBody?.params?.startTime ||
                windowStartDate ||
                currentTime,
            windowEndDate: jsonBody?.params?.endTime ||
                messageHistoryObject?.prevJsonBody?.params?.endTime ||
                windowEndDate ||
                dayjs(currentTime).add(7, 'd').format(),
            bufferTime: jsonBody?.params?.bufferTime ||
                messageHistoryObject?.prevJsonBody?.params?.bufferTime ||
                defaultMeetingPreferences?.bufferTime,
            reminders: jsonBody?.params?.alarms ||
                messageHistoryObject?.prevJsonBody?.params?.alarms ||
                defaultMeetingPreferences?.reminders ||
                [],
            priority: jsonBody?.params?.priority ||
                messageHistoryObject?.prevJsonBody?.params?.priority ||
                1,
            timePreferences: dateJSONBody?.timePreferences ||
                messageHistoryObject?.prevDateJsonBody?.timePreferences ||
                [],
            location: jsonBody?.params?.location ||
                messageHistoryObject?.prevJsonBody?.params?.location,
            transparency: jsonBody?.params?.transparency ||
                messageHistoryObject?.prevJsonBody?.params?.transparency,
            visibility: jsonBody?.params.visibility ||
                messageHistoryObject?.prevJsonBody?.params?.visibility,
        };
        if (recurObject?.frequency) {
            newBody.recur = recurObject;
        }
        const prevBody = {
            ...messageHistoryObject?.prevData,
        };
        if (!prevBody?.userId) {
            prevBody.userId = userId || newBody?.userId;
        }
        if (!prevBody?.timezone) {
            prevBody.timezone = timezone || newBody?.timezone;
        }
        if (!prevBody?.title) {
            prevBody.title = newBody?.title;
        }
        if (!prevBody?.duration) {
            prevBody.duration = newBody?.duration;
        }
        if (!prevBody?.description) {
            prevBody.description = newBody?.description;
        }
        if (!prevBody?.conferenceApp) {
            prevBody.conferenceApp = newBody?.conferenceApp;
        }
        if (!prevBody?.windowStartDate) {
            prevBody.windowStartDate = newBody?.windowStartDate;
        }
        if (!prevBody?.windowEndDate) {
            prevBody.windowEndDate = newBody?.windowEndDate;
        }
        if (!prevBody?.bufferTime) {
            prevBody.bufferTime = newBody?.bufferTime;
        }
        if (!(prevBody?.reminders?.length > 0)) {
            prevBody.reminders = newBody?.reminders || [];
        }
        if (!prevBody?.priority) {
            prevBody.priority = newBody?.priority;
        }
        if (!(prevBody?.timePreferences?.length > 0)) {
            prevBody.timePreferences = newBody?.timePreferences;
        }
        if (!prevBody?.location) {
            prevBody.location = newBody?.location;
        }
        if (!prevBody?.transparency) {
            prevBody.transparency = newBody?.transparency;
        }
        if (!prevBody?.visibility) {
            prevBody.visibility = newBody?.visibility;
        }
        // validate remaining required fields
        if (!prevBody?.title) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[0]);
            response.data = missingFields;
            response.prevData = prevBody;
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (!(prevBody?.attendees?.length > 0)) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[1]);
            response.data = missingFields;
            response.prevData = prevBody;
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        // get info of contacts without emails provided and assign values
        const newAttendees = [];
        for (const a of newBody?.attendees) {
            if (!a?.email) {
                const contact = await getContactByNameWithUserId(userId, `%${a?.name}%`);
                if (contact?.emails?.[0]?.value) {
                    const primaryEmail = contact?.emails?.find((e) => !!e.primary)?.value;
                    const anyEmail = contact?.emails?.[0]?.value;
                    newAttendees.push({ ...a, email: primaryEmail || anyEmail });
                }
                else {
                    response.query = 'missing_fields';
                    missingFields.required.push(requiredFields.required?.[1]?.['and']?.[2]);
                    response.data = missingFields;
                    response.prevData = prevBody;
                    response.prevJsonBody = jsonBody;
                    response.prevDateJsonBody = dateJSONBody;
                }
            }
            else {
                newAttendees.push(a);
            }
        }
        newBody.attendees = newAttendees;
        if (!(prevBody?.attendees?.length > 0)) {
            prevBody.attendees = newBody?.attendees;
        }
        const meetingId = uuid();
        // get host info
        const userContactInfos = await listUserContactInfosGivenUserId(userId);
        // check if any host info
        const newProvidedHostInfo = newBody?.attendees?.find((a) => a?.isHost === true);
        const prevProvidedHostInfo = prevBody?.attendees?.find((a) => a?.isHost === true);
        const primaryInfoItem = userContactInfos?.find((u) => u.primary && u.type === 'email');
        const user = await getUserGivenId(userId);
        const primaryHostAttendeeInfo = {
            name: primaryInfoItem?.name || user?.name,
            email: primaryInfoItem?.id || user?.email,
            isHost: true,
        };
        if (!newProvidedHostInfo && primaryHostAttendeeInfo?.email) {
            newBody?.attendees.push(primaryHostAttendeeInfo);
        }
        if (!prevProvidedHostInfo && primaryHostAttendeeInfo?.email) {
            prevBody?.attendees.push(primaryHostAttendeeInfo);
        }
        const prevHostInfo = prevProvidedHostInfo || newProvidedHostInfo || primaryHostAttendeeInfo;
        if (!prevHostInfo?.email) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[1]['and'][1]);
            response.data = missingFields;
            response.prevData = prevBody;
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (!prevBody?.recur) {
            prevBody.recur = newBody?.recur;
        }
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepFMTWP(prevBody, primaryHostAttendeeInfo, defaultMeetingPreferences, user, meetingId, prevBody?.windowStartDate, prevBody?.windowEndDate, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process fmtwp MissingFieldsReturned');
    }
};
export const FMTWPControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
    try {
        const messageLength = messageHistoryObject.messages?.length;
        let userMessage = '';
        for (let i = messageLength; i > 0; i--) {
            const message = messageHistoryObject.messages[i - 1];
            if (message.role === 'user') {
                userMessage = message.content;
                break;
            }
        }
        const userInput = userMessage;
        let fmtwpRes = {
            query: 'completed',
            data: '',
            skill: '',
            prevData: {},
            prevDataExtra: {},
        };
        switch (query) {
            case 'pending':
                const jsonBody = await generateJSONDataFromUserInput(userInput, userCurrentTime);
                const dateTime = await generateDateTime(userInput, userCurrentTime, timezone);
                fmtwpRes = await processFMTWPPending(userId, timezone, jsonBody, dateTime, userCurrentTime);
                break;
            case 'missing_fields':
                let priorUserInput = '';
                let priorAssistantOutput = '';
                for (let i = messageLength; i > 0; i--) {
                    const message = messageHistoryObject.messages[i - 1];
                    if (message.role === 'assistant') {
                        priorAssistantOutput = message.content;
                        continue;
                    }
                    if (message.role === 'user') {
                        if (message.content !== userInput) {
                            priorUserInput = message.content;
                            break;
                        }
                    }
                }
                if (!priorUserInput || !priorAssistantOutput) {
                    console.log(priorUserInput, ' priorUserInput');
                    console.log(priorAssistantOutput, ' priorAssistantOutput');
                    throw new Error('no priorUserinput or priorAssistantOutput');
                }
                const jsonMissingFieldsBody = await generateMissingFieldsJSONDataFromUserInput(userInput, priorUserInput, priorAssistantOutput, userCurrentTime);
                const dateMissingFieldsTime = await generateMissingFieldsDateTime(userInput, priorUserInput, priorAssistantOutput, userCurrentTime, timezone);
                fmtwpRes = await processFMTWPMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, dateMissingFieldsTime, userCurrentTime, messageHistoryObject);
                break;
        }
        if (fmtwpRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, fmtwpRes.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (fmtwpRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, fmtwpRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required = fmtwpRes?.data;
            messageHistoryObject.prevData = fmtwpRes?.prevData;
            messageHistoryObject.prevDataExtra = fmtwpRes?.prevDataExtra;
            messageHistoryObject.prevDateJsonBody = fmtwpRes?.prevDateJsonBody;
            messageHistoryObject.prevJsonBody = fmtwpRes?.prevJsonBody;
        }
        else if (fmtwpRes?.query === 'event_not_found') {
            const assistantMessage = {
                role: 'assistant',
                content: 'Oops... something went wrong. Sorry :(',
            };
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'event_not_found';
            messageHistoryObject.required = null;
        }
        return messageHistoryObject;
    }
    catch (e) {
        console.log(e, ' unable to find meeting time with permission control center pending');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUFFLE1BQU0sSUFBSSxDQUFDO0FBQ3BCLE9BQU8sRUFBRSxZQUFZLEVBQUUsTUFBTSxhQUFhLENBQUM7QUFjM0MsT0FBTyxjQUFjLE1BQU0sa0JBQWtCLENBQUM7QUFDOUMsT0FBTyxFQUNMLGdDQUFnQyxFQUNoQyw2QkFBNkIsRUFDN0IsNEJBQTRCLEVBQzVCLDJCQUEyQixFQUMzQixpQkFBaUIsRUFDakIsK0JBQStCLEVBQy9CLDBCQUEwQixFQUMxQixzQkFBc0IsRUFDdEIsa0JBQWtCLEVBQ2xCLGNBQWMsRUFDZCw2QkFBNkIsRUFDN0IsZ0JBQWdCLEVBQ2hCLDZCQUE2QixFQUM3QixtREFBbUQsRUFDbkQscURBQXFELEVBQ3JELDhCQUE4QixFQUM5QiwyQkFBMkIsRUFDM0IsNkJBQTZCLEVBQzdCLDBDQUEwQyxHQUMzQyxNQUFNLHdCQUF3QixDQUFDO0FBQ2hDLE9BQU8sRUFBRSxtQ0FBbUMsRUFBRSxNQUFNLCtCQUErQixDQUFDO0FBQ3BGLE9BQU8sRUFBRSxLQUFLLEVBQUUsTUFBTSxpQ0FBaUMsQ0FBQztBQUV4RCxPQUFPLEVBQUUsa0JBQWtCLEVBQUUsTUFBTSx1QkFBdUIsQ0FBQztBQUMzRCxPQUFPLEVBQUUsRUFBRSxJQUFJLElBQUksRUFBRSxNQUFNLE1BQU0sQ0FBQztBQVVsQyxPQUFPLEVBQUUsU0FBUyxFQUFFLE1BQU0sc0JBQXNCLENBQUM7QUFDakQsT0FBTyxFQUFFLEdBQUcsRUFBRSxNQUFNLGNBQWMsQ0FBQztBQUVuQyxvQ0FBb0M7QUFDcEMsMEJBQTBCO0FBQzFCLEtBQUs7QUFFTCxNQUFNLENBQUMsTUFBTSxrQkFBa0IsR0FBRyxDQUNoQyxTQUFpQixFQUNqQixVQUFrQixFQUNsQixZQUFxQixFQUNyQixFQUFFLENBQ0YsQ0FBQyxZQUFZO0lBQ1gsR0FBRyxZQUFZLElB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QWEsQ0FBQztZQUM3RCxvQkFBb0IsQ0FBQyxnQkFBZ0IsR0FBRyxRQUFRLEVBQUUsZ0JBQWdCLENBQUM7WUFDbkUsb0JBQW9CLENBQUMsWUFBWSxHQUFHLFFBQVEsRUFBRSxZQUFZLENBQUM7UUFDN0QsQ0FBQzthQUFNLElBQUksUUFBUSxFQUFFLEtBQUssS0FBSyxpQkFBaUIsRUFBRSxDQUFDO1lBQ2pELE1BQU0sZ0JBQWdCLEdBQXlCO2dCQUM3QyxJQUFJLEVBQUUsV0FBVztnQkFDakIsT0FBTyxFQUFFLHdDQUF3QzthQUNsRCxDQUFDO1lBRUYsb0JBQW9CLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO1lBQ3JELG9CQUFvQixDQUFDLEtBQUssR0FBRyxpQkFBaUIsQ0FBQztZQUMvQyxvQkFBb0IsQ0FBQyxRQUFRLEdBQUcsSUFBSSxDQUFDO1FBQ3ZDLENBQUM7UUFFRCxPQUFPLG9CQUFvQixDQUFDO0lBQzlCLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FDVCxDQUFDLEVBQ0QscUVBQXFFLENBQ3RFLENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHFzIGZyb20gJ3FzJztcbmltcG9ydCB7IGhhbmRzaGFrZVVybCB9IGZyb20gJy4vY29uc3RhbnRzJztcbmltcG9ydCB7IE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvTWVldGluZ0Fzc2lzdEludml0ZVR5cGUnO1xuaW1wb3J0IHtcbiAgQXR0ZW5kZWVEZXRhaWxzRm9yQnVsa01lZXRpbmdJbnZpdGVUeXBlLFxuICBBdHRlbmRlZURldGFpbHNUeXBlLFxuICBGaW5kTWVldGluZ1RpbWVXaXRoUGVybWlzc2lvblR5cGUsXG4gIE1lZXRpbmdJbnZpdGVEZXRhaWxzVG9Ib3N0VHlwZSxcbiAgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGUsXG59IGZyb20gJy4vdHlwZXMnO1xuaW1wb3J0IERhdGVUaW1lSlNPTlR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvZGF0ZXRpbWUvRGF0ZVRpbWVKU09OSlNPTlR5cGUnO1xuaW1wb3J0IFVzZXJJbnB1dFRvSlNPTlR5cGUsIHtcbiAgTXV0YXRlZENhbGVuZGFyRXh0cmFjdGVkSlNPTkF0dGVuZGVlVHlwZSxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvVXNlcklucHV0VG9KU09OVHlwZSc7XG5pbXBvcnQgUmVxdWlyZWRGaWVsZHNUeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1JlcXVpcmVkRmllbGRzVHlwZSc7XG5pbXBvcnQgcmVxdWlyZWRGaWVsZHMgZnJvbSAnLi9yZXF1aXJlZEZpZWxkcyc7XG5pbXBvcnQge1xuICBleHRyYXBvbGF0ZVN0YXJ0RGF0ZUZyb21KU09ORGF0YSxcbiAgZmluZENvbnRhY3RCeUVtYWlsR2l2ZW5Vc2VySWQsXG4gIGdldENhbGVuZGFySW50ZWdyYXRpb25CeU5hbWUsXG4gIGdldFVzZXJDb250YWN0SW5mb3NHaXZlbklkcyxcbiAgZ2V0R2xvYmFsQ2FsZW5kYXIsXG4gIGxpc3RVc2VyQ29udGFjdEluZm9zR2l2ZW5Vc2VySWQsXG4gIGdldENvbnRhY3RCeU5hbWVXaXRoVXNlcklkLFxuICB1cHNlcnRNZWV0aW5nQXNzaXN0T25lLFxuICBjcmVhdGVIb3N0QXR0ZW5kZWUsXG4gIGdldFVzZXJHaXZlbklkLFxuICB1cHNlcnRNZWV0aW5nQXNzaXN0SW52aXRlTWFueSxcbiAgZ2VuZXJhdGVEYXRlVGltZSxcbiAgZ2VuZXJhdGVKU09ORGF0YUZyb21Vc2VySW5wdXQsXG4gIGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZUZyb21BUElSZXNwb25zZUZvclVzZXJRdWVyeSxcbiAgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlVG9SZXF1ZXN0VXNlckZvck1pc3NpbmdGaWVsZHMsXG4gIGV4dHJhcG9sYXRlRW5kRGF0ZUZyb21KU09ORGF0YSxcbiAgZXh0cmFwb2xhdGVEYXRlRnJvbUpTT05EYXRhLFxuICBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNEYXRlVGltZSxcbiAgZ2VuZXJhdGVNaXNzaW5nRmllbGRzSlNPTkRhdGFGcm9tVXNlcklucHV0LFxufSBmcm9tICdAY2hhdC9fbGlicy9hcGktaGVscGVyJztcbmltcG9ydCB7IGdldENoYXRNZWV0aW5nUHJlZmVyZW5jZUdpdmVuVXNlcklkIH0gZnJvbSAnLi4vc2NoZWR1bGVNZWV0aW5nL2FwaS1oZWxwZXInO1xuaW1wb3J0IHsgZGF5anMgfSBmcm9tICdAY2hhdC9fbGlicy9kYXRldGltZS9kYXRlLXV0aWxzJztcbmltcG9ydCB7IFJlY3VycmVuY2VSdWxlVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0V2ZW50VHlwZSc7XG5pbXBvcnQgeyBnb29nbGVDYWxlbmRhck5hbWUgfSBmcm9tICdAY2hhdC9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IHsgdjQgYXMgdXVpZCB9IGZyb20gJ3V1aWQnO1xuaW1wb3J0IHsgTWVldGluZ0Fzc2lzdFR5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9NZWV0aW5nQXNzaXN0VHlwZSc7XG5pbXBvcnQgUmVzcG9uc2VBY3Rpb25UeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1Jlc3BvbnNlQWN0aW9uVHlwZSc7XG5pbXBvcnQge1xuICBBc3Npc3RhbnRNZXNzYWdlVHlwZSxcbiAgU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGUsXG59IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL01lc3NhZ2luZy9NZXNzYWdpbmdUeXBlcyc7XG5pbXBvcnQgT3BlbkFJIGZyb20gJ29wZW5haSc7XG5pbXBvcnQgeyBDaGF0TWVldGluZ1ByZWZlcmVuY2VzVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0NoYXRNZWV0aW5nUHJlZmVyZW5jZXNUeXBlJztcbmltcG9ydCB7IFVzZXJUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvVXNlclR5cGUnO1xuaW1wb3J0IHsgc2VuZEVtYWlsIH0gZnJvbSAnQC9fdXRpbHMvZW1haWwvZW1haWwnO1xuaW1wb3J0IHsgRU5WIH0gZnJvbSAnQC9fdXRpbHMvZW52JztcblxuLy8gY29uc3QgY2xpZW50ID0gbmV3IExhbWJkYUNsaWVudCh7XG4vLyAgICAgcmVnaW9uOiAndXMtZWFzdC0xJ1xuLy8gfSlcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlSW52aXRlTGluayA9IChcbiAgbWVldGluZ0lkOiBzdHJpbmcsXG4gIGF0dGVuZGVlSWQ6IHN0cmluZyxcbiAgcHJpbWFyeUVtYWlsPzogc3RyaW5nXG4pID0+XG4gIChwcmltYXJ5RW1haWwgJiZcbiAgICBgJHtoYW5kc2hha2VVcmx9PyR7cXMuc3RyaW5naWZ5KHsgbWVldGluZ0lkLCBhdHRlbmRlZUlkLCBwcmltYXJ5RW1haWwgfSl9YCkgfHxcbiAgYCR7aGFuZHNoYWtlVXJsfT8ke3FzLnN0cmluZ2lmeSh7IG1lZXRpbmdJZCwgYXR0ZW5kZWVJZCB9KX1gO1xuXG5leHBvcnQgY29uc3QgY29udmVydEludml0ZWVUeXBlVG9JbnZpdGVFbWFpbFJlY2lwaWVudHMgPSAoXG4gIGludml0ZWVzOiBNZWV0aW5nQXNzaXN0SW52aXRlVHlwZVtdLFxuICBtZWV0aW5nSWQ6IHN0cmluZ1xuKSA9PiB7XG4gIGNvbnN0IGludml0ZWVFbWFpbHMgPSBpbnZpdGVlcz8ubWFwKChpKSA9PiAoe1xuICAgIGVtYWlsOiBpPy5lbWFpbCB8fCAnJyxcbiAgICBuYW1lOiBpPy5uYW1lLFxuICAgIGxpbms6IGdlbmVyYXRlSW52aXRlTGluayhtZWV0aW5nSWQsIGk/LmlkLCBpPy5lbWFpbCksXG4gIH0pKTtcblxuICByZXR1cm4gaW52aXRlZUVtYWlscztcbn07XG5cbmNvbnN0IGNyZWF0ZU1lZXRpbmdBc3Npc3RJbnZpdGVlcyA9IGFzeW5jIChcbiAgaW52aXRlZXM6IE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlW11cbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnNvbGUubG9nKGludml0ZWVzLCAnIGludml0ZWVzJyk7XG4gICAgYXdhaXQgdXBzZXJ0TWVldGluZ0Fzc2lzdEludml0ZU1hbnkoaW52aXRlZXMpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gY3JlYXRlIG1lZXRpbmcgYXNzaXN0IGludml0ZWVzJyk7XG4gIH1cbn07XG5cbi8vIG1lZXRpbmctaW5mby10by1ob3N0LWF1dGhcblxuZXhwb3J0IGNvbnN0IHNlbmRNZWV0aW5nSW5mb1RvSG9zdEVtYWlsID0gYXN5bmMgKFxuICBhdHRlbmRlZXM6IEF0dGVuZGVlRGV0YWlsc1R5cGVbXSxcbiAgaG9zdEVtYWlsOiBzdHJpbmcsXG4gIGhvc3ROYW1lOiBzdHJpbmcsXG4gIHRpdGxlOiBzdHJpbmcsXG4gIG5vdGVzOiBzdHJpbmcsXG4gIHdpbmRvd1N0YXJ0RGF0ZTogc3RyaW5nLFxuICB3aW5kb3dFbmREYXRlOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGxldCBhdHRlbmRlZUh0bWxTdHJpbmcgPSAnJztcbiAgICBsZXQgYXR0ZW5kZWVUZXh0U3RyaW5nID0gJyc7XG5cbiAgICBmb3IgKGNvbnN0IGF0dGVuZGVlIG9mIGF0dGVuZGVlcykge1xuICAgICAgYXR0ZW5kZWVIdG1sU3RyaW5nICs9ICc8cD4nO1xuICAgICAgYXR0ZW5kZWVIdG1sU3RyaW5nICs9ICc8YSBocmVmPSc7XG4gICAgICBhdHRlbmRlZUh0bWxTdHJpbmcgKz0gJ1wibWFpbHRvOic7XG4gICAgICBhdHRlbmRlZUh0bWxTdHJpbmcgKz0gYXR0ZW5kZWU/LmVtYWlsO1xuICAgICAgYXR0ZW5kZWVIdG1sU3RyaW5nICs9ICdcIic7XG4gICAgICBhdHRlbmRlZUh0bWxTdHJpbmcgKz0gJz4nO1xuICAgICAgYXR0ZW5kZWVIdG1sU3RyaW5nICs9IGF0dGVuZGVlPy5uYW1lIHx8IGF0dGVuZGVlPy5lbWFpbDtcbiAgICAgIGF0dGVuZGVlSHRtbFN0cmluZyArPSAnPC9hPic7XG4gICAgICBhdHRlbmRlZUh0bWxTdHJpbmcgKz0gJyAtICc7XG4gICAgICBhdHRlbmRlZUh0bWxTdHJpbmcgKz0gJzxhIGhyZWY9JztcbiAgICAgIGF0dGVuZGVlSHRtbFN0cmluZyArPSAnXCInO1xuICAgICAgYXR0ZW5kZWVIdG1sU3RyaW5nICs9IGF0dGVuZGVlPy5saW5rO1xuICAgICAgYXR0ZW5kZWVIdG1sU3RyaW5nICs9ICdcIic7XG4gICAgICBhdHRlbmRlZUh0bWxTdHJpbmcgKz0gJz4nO1xuICAgICAgYXR0ZW5kZWVIdG1sU3RyaW5nICs9ICdsaW5rJztcbiAgICAgIGF0dGVuZGVlSHRtbFN0cmluZyArPSAnPC9hPic7XG4gICAgICBhdHRlbmRlZUh0bWxTdHJpbmcgKz0gJzwvcD4nO1xuXG4gICAgICBhdHRlbmRlZVRleHRTdHJpbmcgKz0gYXR0ZW5kZWU/Lm5hbWU7XG4gICAgICBhdHRlbmRlZVRleHRTdHJpbmcgKz0gJyAnICsgJygnICsgYXR0ZW5kZWU/LmVtYWlsICsgJyknICsgJyAnO1xuICAgICAgYXR0ZW5kZWVUZXh0U3RyaW5nICs9ICcgLSAnO1xuICAgICAgYXR0ZW5kZWVUZXh0U3RyaW5nICs9IGF0dGVuZGVlPy5saW5rO1xuICAgICAgYXR0ZW5kZWVUZXh0U3RyaW5nICs9ICdcXHJcXG4nO1xuICAgIH1cblxuICAgIGNvbnN0IHRlbXBsYXRlID0gJ21lZXRpbmctaW52aXRlLWRldGFpbHMtdG8taG9zdCc7XG5cbiAgICBhd2FpdCBzZW5kRW1haWwoe1xuICAgICAgdGVtcGxhdGUsXG4gICAgICBsb2NhbHM6IHtcbiAgICAgICAgaG9zdE5hbWUsXG4gICAgICAgIHRpdGxlLFxuICAgICAgICBub3RlcyxcbiAgICAgICAgd2luZG93U3RhcnREYXRlOiBkYXlqcyh3aW5kb3dTdGFydERhdGUpXG4gICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgIC5mb3JtYXQoJ2RkZGQsIE1NTU0gRCwgWVlZWSBoOm1tIEEnKSxcbiAgICAgICAgd2luZG93RW5kRGF0ZTogZGF5anMod2luZG93RW5kRGF0ZSlcbiAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgLmZvcm1hdCgnZGRkZCwgTU1NTSBELCBZWVlZIGg6bW0gQScpLFxuICAgICAgICBhdHRlbmRlZUh0bWxTdHJpbmcsXG4gICAgICAgIGRpc3BsYXlOYW1lOiBob3N0TmFtZSxcbiAgICAgICAgZW1haWw6IGhvc3RFbWFpbCxcbiAgICAgICAgbG9jYWxlOiBFTlYuQVVUSF9MT0NBTEVfREVGQVVMVCxcbiAgICAgICAgc2VydmVyVXJsOiBFTlYuRlVOQ1RJT05fU0VSVkVSX1VSTCxcbiAgICAgICAgY2xpZW50VXJsOiBFTlYuQVBQX0NMSUVOVF9VUkwsXG4gICAgICB9LFxuICAgICAgbWVzc2FnZToge1xuICAgICAgICB0bzogaG9zdEVtYWlsLFxuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ3gtZW1haWwtdGVtcGxhdGUnOiB7XG4gICAgICAgICAgICBwcmVwYXJlZDogdHJ1ZSxcbiAgICAgICAgICAgIHZhbHVlOiB0ZW1wbGF0ZSxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICB9KTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHNlbmQgZW1haWwgdG8gaG9zdCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3Qgc2VuZEJ1bGtNZWV0aW5nSW52aXRlRW1haWwgPSBhc3luYyAoXG4gIGF0dGVuZGVlczogQXR0ZW5kZWVEZXRhaWxzRm9yQnVsa01lZXRpbmdJbnZpdGVUeXBlW10sXG4gIGhvc3RFbWFpbDogc3RyaW5nLFxuICBob3N0TmFtZTogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGF0dGVuZGVlcyxcbiAgICAgICcgQXR0ZW5kZWVEZXRhaWxzRm9yQnVsa01lZXRpbmdJbnZpdGVUeXBlIGluc2lkZSBzZW5kQnVsa01lZXRpbmdJbnZpdGVFbWFpbCdcbiAgICApO1xuXG4gICAgY29uc3QgZGF0YSA9IHtcbiAgICAgIGF0dGVuZGVlcyxcbiAgICAgIGhvc3ROYW1lLFxuICAgICAgaG9zdEVtYWlsLFxuICAgIH07XG5cbiAgICBjb25zdCB0ZW1wbGF0ZSA9ICdidWxrLW1lZXRpbmctaW52aXRlJztcblxuICAgIGZvciAoY29uc3QgYXR0ZW5kZWUgb2YgYXR0ZW5kZWVzKSB7XG4gICAgICBhd2FpdCBzZW5kRW1haWwoe1xuICAgICAgICB0ZW1wbGF0ZSxcbiAgICAgICAgbG9jYWxzOiB7XG4gICAgICAgICAgbmFtZTogYXR0ZW5kZWU/Lm5hbWUsXG4gICAgICAgICAgaG9zdEVtYWlsLFxuICAgICAgICAgIGhvc3ROYW1lLFxuICAgICAgICAgIGxpbms6IGF0dGVuZGVlPy5saW5rLFxuICAgICAgICAgIGRpc3BsYXlOYW1lOiBhdHRlbmRlZT8ubmFtZSxcbiAgICAgICAgICBlbWFpbDogYXR0ZW5kZWU/LmVtYWlsLFxuICAgICAgICAgIGxvY2FsZTogRU5WLkFVVEhfTE9DQUxFX0RFRkFVTFQsXG4gICAgICAgICAgc2VydmVyVXJsOiBFTlYuRlVOQ1RJT05fU0VSVkVSX1VSTCxcbiAgICAgICAgICBjbGllbnRVcmw6IEVOVi5BUFBfQ0xJRU5UX1VSTCxcbiAgICAgICAgfSxcbiAgICAgICAgbWVzc2FnZToge1xuICAgICAgICAgIHRvOiBhdHRlbmRlZT8uZW1haWwsXG4gICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgJ3gtZW1haWwtdGVtcGxhdGUnOiB7XG4gICAgICAgICAgICAgIHByZXBhcmVkOiB0cnVlLFxuICAgICAgICAgICAgICB2YWx1ZTogdGVtcGxhdGUsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9KTtcbiAgICB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBzZW5kIGJ1bGsgbWVldGluZyBpbnZpdGUgZW1haWwnKTtcbiAgfVxufTtcblxuLy8gRmluZE1lZXRpbmdUaW1lV2l0aFBlcm1pc3Npb25UeXBlXG5cbmV4cG9ydCBjb25zdCBmaW5hbFN0ZXBGTVRXUCA9IGFzeW5jIChcbiAgYm9keTogRmluZE1lZXRpbmdUaW1lV2l0aFBlcm1pc3Npb25UeXBlLFxuICBwcmltYXJ5SG9zdEF0dGVuZGVlSW5mbzogTXV0YXRlZENhbGVuZGFyRXh0cmFjdGVkSlNPTkF0dGVuZGVlVHlwZSxcbiAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlczogQ2hhdE1lZXRpbmdQcmVmZXJlbmNlc1R5cGUsXG4gIHVzZXI6IFVzZXJUeXBlLFxuICBtZWV0aW5nSWQ6IHN0cmluZyxcbiAgd2luZG93U3RhcnREYXRlOiBzdHJpbmcsXG4gIHdpbmRvd0VuZERhdGU6IHN0cmluZyxcbiAgcmVzcG9uc2U6IGFueVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgLy8gZ2V0IHByaW1hcnkgY2FsZW5kYXJcbiAgICBjb25zdCBwcmltYXJ5Q2FsZW5kYXIgPSBhd2FpdCBnZXRHbG9iYWxDYWxlbmRhcihib2R5Py51c2VySWQpO1xuXG4gICAgLy8gdmFsaWRhdGVcbiAgICBpZiAoIXByaW1hcnlDYWxlbmRhcj8uaWQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gcHJpbWFyeSBjYWxlbmRhciBmb3VuZCBpbnNpZGUgY3JlYXRlQWdlbmRhJyk7XG4gICAgfVxuXG4gICAgLy8gZ2V0IGNsaWVudCB0eXBlXG4gICAgY29uc3QgY2FsSW50ZWdyYXRpb24gPSBhd2FpdCBnZXRDYWxlbmRhckludGVncmF0aW9uQnlOYW1lKFxuICAgICAgYm9keT8udXNlcklkLFxuICAgICAgZ29vZ2xlQ2FsZW5kYXJOYW1lXG4gICAgKTtcblxuICAgIC8vIHZhbGlkYXRlXG4gICAgaWYgKCFjYWxJbnRlZ3JhdGlvbj8uY2xpZW50VHlwZSkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICAnbm8gY2xpZW50IHR5cGUgaW5zaWRlIGNhbGVuZGFyIGludGVncmF0aW9uIGluc2lkZSBjcmVhdGUgYWdlbmRhJ1xuICAgICAgKTtcbiAgICB9XG5cbiAgICAvLyBmaW5kQ29udGFjdEJ5RW1haWxHaXZlblVzZXJJZFxuICAgIC8vIGdldCBhdHRlbmRlZXMgd2l0aCBwcm92aWRlZCBlbWFpbHNcbiAgICBjb25zdCBhV2l0aEVtYWlscyA9IGJvZHk/LmF0dGVuZGVlcz8uZmlsdGVyKChhKSA9PiAhIWE/LmVtYWlsKTtcblxuICAgIGNvbnN0IGFXaXRoQ29udGFjdEluZm9zID0gYXdhaXQgZ2V0VXNlckNvbnRhY3RJbmZvc0dpdmVuSWRzKFxuICAgICAgYVdpdGhFbWFpbHM/Lm1hcCgoYSkgPT4gYT8uZW1haWwpXG4gICAgKTtcblxuICAgIGNvbnN0IGludml0ZWVzRnJvbUV4dHJhY3RlZEpTT04gPSBib2R5Py5hdHRlbmRlZXM7XG5cbiAgICBjb25zdCBpbnZpdGVlczogTWVldGluZ0Fzc2lzdEludml0ZVR5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBpIG9mIGludml0ZWVzRnJvbUV4dHJhY3RlZEpTT04pIHtcbiAgICAgIGNvbnN0IGNvbnRhY3QgPSBhd2FpdCBmaW5kQ29udGFjdEJ5RW1haWxHaXZlblVzZXJJZChcbiAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICBpLmVtYWlsXG4gICAgICApO1xuICAgICAgY29uc3QgdXNlcklkRm91bmQgPSBhV2l0aENvbnRhY3RJbmZvcz8uZmluZCgoYikgPT4gYj8uaWQgPT09IGk/LmVtYWlsKTtcbiAgICAgIGNvbnN0IGludml0ZWU6IE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlID0ge1xuICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICBob3N0SWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgaG9zdE5hbWU6IHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvPy5uYW1lLFxuICAgICAgICB1c2VySWQ6IGk/LmlzSG9zdCA/IGJvZHk/LnVzZXJJZCA6IHVzZXJJZEZvdW5kPy51c2VySWQgfHwgdXVpZCgpLFxuICAgICAgICBuYW1lOlxuICAgICAgICAgIGk/Lm5hbWUgfHxcbiAgICAgICAgICBjb250YWN0Py5uYW1lIHx8XG4gICAgICAgICAgYCR7Y29udGFjdD8uZmlyc3ROYW1lfSAke2NvbnRhY3Q/Lmxhc3ROYW1lfWAsXG4gICAgICAgIGNvbnRhY3RJZDogY29udGFjdD8uaWQsXG4gICAgICAgIGVtYWlsOiBpPy5lbWFpbCxcbiAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgbWVldGluZ0lkLFxuICAgICAgfTtcblxuICAgICAgaW52aXRlZXMucHVzaChpbnZpdGVlKTtcbiAgICB9XG5cbiAgICBjb25zdCBtZWV0aW5nQXNzaXN0OiBNZWV0aW5nQXNzaXN0VHlwZSA9IHtcbiAgICAgIGlkOiBtZWV0aW5nSWQsXG4gICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgIHN1bW1hcnk6IGJvZHk/LnRpdGxlLFxuICAgICAgbm90ZXM6IGJvZHk/LmRlc2NyaXB0aW9uLFxuICAgICAgd2luZG93U3RhcnREYXRlOiBib2R5Py53aW5kb3dTdGFydERhdGUsXG4gICAgICB3aW5kb3dFbmREYXRlOiBib2R5Py53aW5kb3dFbmREYXRlLFxuICAgICAgdGltZXpvbmU6IGJvZHk/LnRpbWV6b25lLFxuICAgICAgbG9jYXRpb246IHsgdGl0bGU6IGJvZHk/LmxvY2F0aW9uIHx8ICcnIH0sXG4gICAgICBwcmlvcml0eTogYm9keT8ucHJpb3JpdHkgfHwgMSxcbiAgICAgIGVuYWJsZUNvbmZlcmVuY2U6XG4gICAgICAgICEhYm9keT8uY29uZmVyZW5jZUFwcCB8fCAhIWRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LmNvbmZlcmVuY2VBcHAsXG4gICAgICBjb25mZXJlbmNlQXBwOlxuICAgICAgICBib2R5Py5jb25mZXJlbmNlQXBwIHx8IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LmNvbmZlcmVuY2VBcHAsXG4gICAgICBzZW5kVXBkYXRlczogZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uc2VuZFVwZGF0ZXMsXG4gICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnM6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAgIHRyYW5zcGFyZW5jeTogZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8udHJhbnNwYXJlbmN5LFxuICAgICAgdmlzaWJpbGl0eTogZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8udmlzaWJpbGl0eSxcbiAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgdXNlRGVmYXVsdEFsYXJtczogYm9keT8ucmVtaW5kZXJzXG4gICAgICAgID8gZmFsc2VcbiAgICAgICAgOiBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5yZW1pbmRlcnM/Lmxlbmd0aCA+IDBcbiAgICAgICAgICA/IGZhbHNlXG4gICAgICAgICAgOiB0cnVlLFxuICAgICAgcmVtaW5kZXJzOiBib2R5Py5yZW1pbmRlcnMgfHwgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ucmVtaW5kZXJzLFxuICAgICAgY2FuY2VsSWZBbnlSZWZ1c2U6IGZhbHNlLFxuICAgICAgZW5hYmxlQXR0ZW5kZWVQcmVmZXJlbmNlczogdHJ1ZSxcbiAgICAgIGF0dGVuZGVlQ2FuTW9kaWZ5OiBmYWxzZSxcbiAgICAgIGV4cGlyZURhdGU6IGRheWpzKGJvZHk/LndpbmRvd0VuZERhdGUpLnN1YnRyYWN0KDEsICdkJykuZm9ybWF0KCksXG4gICAgICBkdXJhdGlvbjogYm9keT8uZHVyYXRpb24sXG4gICAgICBjYWxlbmRhcklkOiBwcmltYXJ5Q2FsZW5kYXI/LmlkIHx8ICcnLFxuICAgICAgYnVmZmVyVGltZTogYm9keT8uYnVmZmVyVGltZVxuICAgICAgICA/IHtcbiAgICAgICAgICAgIGJlZm9yZUV2ZW50OiBib2R5Py5idWZmZXJUaW1lPy5iZWZvcmVFdmVudCxcbiAgICAgICAgICAgIGFmdGVyRXZlbnQ6IGJvZHk/LmJ1ZmZlclRpbWU/LmFmdGVyRXZlbnQsXG4gICAgICAgICAgfVxuICAgICAgICA6IHVuZGVmaW5lZCxcbiAgICAgIGFueW9uZUNhbkFkZFNlbGY6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LmFueW9uZUNhbkFkZFNlbGYsXG4gICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0czpcbiAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgICBtaW5UaHJlc2hvbGRDb3VudDogYm9keT8uYXR0ZW5kZWVzPy5sZW5ndGgsXG4gICAgICBndWFyYW50ZWVBdmFpbGFiaWxpdHk6IGZhbHNlLFxuICAgICAgYXR0ZW5kZWVSZXNwb25kZWRDb3VudDogMSxcbiAgICAgIGF0dGVuZGVlQ291bnQ6IDEsXG4gICAgICBjYW5jZWxsZWQ6IGZhbHNlLFxuICAgICAgZnJlcXVlbmN5OiBib2R5Py5yZWN1cj8uZnJlcXVlbmN5LFxuICAgICAgaW50ZXJ2YWw6IGJvZHk/LnJlY3VyPy5pbnRlcnZhbCxcbiAgICAgIHVudGlsOiBib2R5Py5yZWN1cj8uZW5kRGF0ZSAmJiBkYXlqcyhib2R5Py5yZWN1cj8uZW5kRGF0ZSkuZm9ybWF0KCksXG4gICAgICBvcmlnaW5hbE1lZXRpbmdJZDogYm9keT8ucmVjdXIgPyBtZWV0aW5nSWQgOiB1bmRlZmluZWQsXG4gICAgfTtcblxuICAgIGF3YWl0IHVwc2VydE1lZXRpbmdBc3Npc3RPbmUobWVldGluZ0Fzc2lzdCk7XG5cbiAgICBhd2FpdCBjcmVhdGVIb3N0QXR0ZW5kZWUoXG4gICAgICBib2R5Py51c2VySWQsXG4gICAgICBtZWV0aW5nSWQsXG4gICAgICBib2R5Py50aW1lem9uZSxcbiAgICAgIHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvPy5lbWFpbCxcbiAgICAgIHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvPy5uYW1lXG4gICAgKTtcblxuICAgIGF3YWl0IGNyZWF0ZU1lZXRpbmdBc3Npc3RJbnZpdGVlcyhpbnZpdGVlcyk7XG5cbiAgICBjb25zdCBpbnZpdGVlRW1haWxzID0gY29udmVydEludml0ZWVUeXBlVG9JbnZpdGVFbWFpbFJlY2lwaWVudHMoXG4gICAgICBpbnZpdGVlcyxcbiAgICAgIG1lZXRpbmdJZFxuICAgICk7XG5cbiAgICBhd2FpdCBzZW5kTWVldGluZ0luZm9Ub0hvc3RFbWFpbChcbiAgICAgIGludml0ZWVFbWFpbHMsXG4gICAgICB1c2VyPy5lbWFpbCB8fCAnJyxcbiAgICAgIHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvPy5uYW1lIHx8IHVzZXI/Lm5hbWUgfHwgJycsXG4gICAgICBib2R5Py50aXRsZSxcbiAgICAgIGJvZHk/LmRlc2NyaXB0aW9uLFxuICAgICAgZGF5anMod2luZG93U3RhcnREYXRlKS5mb3JtYXQoKSxcbiAgICAgIGRheWpzKHdpbmRvd0VuZERhdGUpLmZvcm1hdCgpLFxuICAgICAgYm9keT8udGltZXpvbmVcbiAgICApO1xuXG4gICAgY29uc3QgZmlsdGVyZWRJbnZpdGVlRW1haWxzID0gaW52aXRlZUVtYWlscz8uZmlsdGVyKChpKSA9PiAhIWk/LmVtYWlsKTtcblxuICAgIGF3YWl0IHNlbmRCdWxrTWVldGluZ0ludml0ZUVtYWlsKFxuICAgICAgZmlsdGVyZWRJbnZpdGVlRW1haWxzLFxuICAgICAgdXNlcj8uZW1haWwgfHwgJycsXG4gICAgICBwcmltYXJ5SG9zdEF0dGVuZGVlSW5mbz8ubmFtZSB8fCB1c2VyPy5uYW1lIHx8ICcnXG4gICAgKTtcblxuICAgIC8vIHN1Y2Nlc3MgcmVzcG9uc2VcbiAgICByZXNwb25zZS5xdWVyeSA9ICdjb21wbGV0ZWQnO1xuXG4gICAgcmVzcG9uc2UuZGF0YSA9XG4gICAgICAnU3VjY2Vzc2Z1bGx5IHNlbnQgYW4gZW1haWwgdG8gaW52aXRlZXMgdG8gZ2V0IGF2YWlsYWJpbGl0eSBhbmQgdGltZSBwcmVmZXJlbmNlcyBmb3IgZmluZGluZyBhIG1lZXRpbmcgdGltZSc7XG5cbiAgICByZXR1cm4gcmVzcG9uc2U7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBmaW5hbCBzdGVwIGZtdHdwJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzRk1UV1BQZW5kaW5nID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAganNvbkJvZHk6IFVzZXJJbnB1dFRvSlNPTlR5cGUsXG4gIGRhdGVKU09OQm9keTogRGF0ZVRpbWVKU09OVHlwZSxcbiAgY3VycmVudFRpbWU6IHN0cmluZ1xuKTogUHJvbWlzZTxSZXNwb25zZUFjdGlvblR5cGU+ID0+IHtcbiAgdHJ5IHtcbiAgICBsZXQgZHVyYXRpb24gPSAwO1xuXG4gICAgY29uc3QgeWVhclN0YXJ0ID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py55ZWFyO1xuICAgIGNvbnN0IG1vbnRoU3RhcnQgPSBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/Lm1vbnRoO1xuICAgIGNvbnN0IGRheVN0YXJ0ID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5kYXk7XG4gICAgY29uc3QgaXNvV2Vla2RheVN0YXJ0ID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5pc29XZWVrZGF5O1xuICAgIGNvbnN0IGhvdXJTdGFydCA9IGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8uaG91cjtcbiAgICBjb25zdCBtaW51dGVTdGFydCA9IGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8ubWludXRlO1xuICAgIGNvbnN0IHN0YXJ0VGltZVN0YXJ0ID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5zdGFydFRpbWU7XG5cbiAgICBjb25zdCB5ZWFyRW5kID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8ueWVhcjtcbiAgICBjb25zdCBtb250aEVuZCA9IGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/Lm1vbnRoO1xuICAgIGNvbnN0IGRheUVuZCA9IGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/LmRheTtcbiAgICBjb25zdCBpc29XZWVrZGF5RW5kID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8uaXNvV2Vla2RheTtcbiAgICBjb25zdCBob3VyRW5kID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8uaG91cjtcbiAgICBjb25zdCBtaW51dGVFbmQgPSBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5taW51dGU7XG4gICAgY29uc3QgZW5kVGltZUVuZCA9IGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/LnN0YXJ0VGltZTtcblxuICAgIGNvbnN0IG1pc3NpbmdGaWVsZHM6IFJlcXVpcmVkRmllbGRzVHlwZSA9IHtcbiAgICAgIHJlcXVpcmVkOiBbXSxcbiAgICAgIGRhdGVUaW1lOiB7IHJlcXVpcmVkOiBbXSB9LFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZTogYW55ID0ge1xuICAgICAgcXVlcnk6ICcnLFxuICAgICAgZGF0YToge30sXG4gICAgICBza2lsbDogJ2ZpbmRNZWV0aW5nVGltZVdpdGhQZXJtaXNzaW9uJyxcbiAgICB9O1xuXG4gICAgY29uc3Qgd2luZG93U3RhcnREYXRlID0gZXh0cmFwb2xhdGVTdGFydERhdGVGcm9tSlNPTkRhdGEoXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgeWVhclN0YXJ0LFxuICAgICAgbW9udGhTdGFydCxcbiAgICAgIGRheVN0YXJ0LFxuICAgICAgaXNvV2Vla2RheVN0YXJ0LFxuICAgICAgaG91clN0YXJ0LFxuICAgICAgbWludXRlU3RhcnQsXG4gICAgICBzdGFydFRpbWVTdGFydCxcbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICk7XG5cbiAgICBjb25zdCB3aW5kb3dFbmREYXRlID0gZXh0cmFwb2xhdGVFbmREYXRlRnJvbUpTT05EYXRhKFxuICAgICAgY3VycmVudFRpbWUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHllYXJFbmQsXG4gICAgICBtb250aEVuZCxcbiAgICAgIGRheUVuZCxcbiAgICAgIGlzb1dlZWtkYXlFbmQsXG4gICAgICBob3VyRW5kLFxuICAgICAgbWludXRlRW5kLFxuICAgICAgZW5kVGltZUVuZCxcbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5yZWxhdGl2ZVRpbWVGcm9tTm93XG4gICAgKTtcblxuICAgIC8vIGdldCBkZWZhdWx0IHZhbHVlc1xuICAgIGNvbnN0IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXMgPVxuICAgICAgYXdhaXQgZ2V0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlR2l2ZW5Vc2VySWQodXNlcklkKTtcblxuICAgIGlmIChkYXRlSlNPTkJvZHk/LmR1cmF0aW9uKSB7XG4gICAgICBkdXJhdGlvbiA9IGRhdGVKU09OQm9keT8uZHVyYXRpb247XG4gICAgfSBlbHNlIGlmIChkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5kdXJhdGlvbikge1xuICAgICAgZHVyYXRpb24gPSBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5kdXJhdGlvbjtcbiAgICB9IGVsc2Uge1xuICAgICAgZHVyYXRpb24gPSAzMDtcbiAgICB9XG5cbiAgICAvLyB0YWtlIGNhcmUgb2YgYW55IHJlY3VycmluZyBkYXRlc1xuICAgIGxldCByZWN1ck9iamVjdDogUmVjdXJyZW5jZVJ1bGVUeXBlIHwge30gPSB7fTtcbiAgICBpZiAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5KSB7XG4gICAgICBjb25zdCByZWN1ckVuZERhdGUgPSBleHRyYXBvbGF0ZURhdGVGcm9tSlNPTkRhdGEoXG4gICAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ueWVhcixcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubW9udGgsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LmRheSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaXNvV2Vla2RheSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaG91cixcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubWludXRlLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5zdGFydFRpbWUsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICAgICk7XG5cbiAgICAgIHJlY3VyT2JqZWN0ID0ge1xuICAgICAgICBmcmVxdWVuY3k6XG4gICAgICAgICAgKGRhdGVKU09OQm9keT8ucmVjdXI/LmZyZXF1ZW5jeSBhcyBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZSkgfHxcbiAgICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5mcmVxdWVuY3ksXG4gICAgICAgIGludGVydmFsOlxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmludGVydmFsIHx8XG4gICAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uaW50ZXJ2YWwsXG4gICAgICB9O1xuXG4gICAgICBpZiAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5KSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmJ5V2Vla0RheSA9XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5O1xuICAgICAgfVxuXG4gICAgICBpZiAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlNb250aERheSkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5ieU1vbnRoRGF5ID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5O1xuICAgICAgfVxuXG4gICAgICBpZiAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8ub2NjdXJyZW5jZSkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5vY2N1cnJlbmNlID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlO1xuICAgICAgfVxuXG4gICAgICBpZiAocmVjdXJFbmREYXRlIHx8IGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGUpIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkuZW5kRGF0ZSA9XG4gICAgICAgICAgcmVjdXJFbmREYXRlIHx8IGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGU7XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgYm9keTogRmluZE1lZXRpbmdUaW1lV2l0aFBlcm1pc3Npb25UeXBlID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgdGltZXpvbmUsXG4gICAgICB0aXRsZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGl0bGUgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uc3VtbWFyeSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8uWzBdPy50YXNrLFxuICAgICAgYXR0ZW5kZWVzOiBqc29uQm9keT8ucGFyYW1zPy5hdHRlbmRlZXMsXG4gICAgICBtZXRob2Q6IGRhdGVKU09OQm9keT8ubWV0aG9kIGFzIGFueSxcbiAgICAgIGR1cmF0aW9uLFxuICAgICAgZGVzY3JpcHRpb246IGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8IGpzb25Cb2R5Py5wYXJhbXM/Lm5vdGVzLFxuICAgICAgY29uZmVyZW5jZUFwcDpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uY29uZmVyZW5jZT8uYXBwIHx8XG4gICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LmNvbmZlcmVuY2VBcHAsXG4gICAgICB3aW5kb3dTdGFydERhdGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSB8fCB3aW5kb3dTdGFydERhdGUgfHwgY3VycmVudFRpbWUsXG4gICAgICB3aW5kb3dFbmREYXRlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lIHx8XG4gICAgICAgIHdpbmRvd0VuZERhdGUgfHxcbiAgICAgICAgZGF5anMoY3VycmVudFRpbWUpLmFkZCg3LCAnZCcpLmZvcm1hdCgpLFxuICAgICAgYnVmZmVyVGltZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uYnVmZmVyVGltZSB8fCBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5idWZmZXJUaW1lLFxuICAgICAgcmVtaW5kZXJzOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5hbGFybXMgfHwgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ucmVtaW5kZXJzIHx8IFtdLFxuICAgICAgcHJpb3JpdHk6IGpzb25Cb2R5Py5wYXJhbXM/LnByaW9yaXR5IHx8IDEsXG4gICAgICB0aW1lUHJlZmVyZW5jZXM6IGRhdGVKU09OQm9keT8udGltZVByZWZlcmVuY2VzIHx8IFtdLFxuICAgICAgbG9jYXRpb246IGpzb25Cb2R5Py5wYXJhbXM/LmxvY2F0aW9uLFxuICAgICAgdHJhbnNwYXJlbmN5OiBqc29uQm9keT8ucGFyYW1zPy50cmFuc3BhcmVuY3ksXG4gICAgICB2aXNpYmlsaXR5OiBqc29uQm9keT8ucGFyYW1zLnZpc2liaWxpdHksXG4gICAgfTtcblxuICAgIGlmIChcbiAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpPy5mcmVxdWVuY3kgYXMgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGVcbiAgICApIHtcbiAgICAgIGJvZHkucmVjdXIgPSByZWN1ck9iamVjdCBhcyBhbnk7XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2coYm9keSwgJyBib2R5Jyk7XG5cbiAgICAvLyB2YWxpZGF0ZSByZW1haW5pbmcgcmVxdWlyZWQgZmllbGRzXG4gICAgaWYgKCFib2R5Py50aXRsZSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZC5wdXNoKHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMF0pO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHk7XG4gICAgICAvLyByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgLy8gICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIC8vICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgLy8gfVxuICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgIH1cblxuICAgIGlmICghKGJvZHk/LmF0dGVuZGVlcz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzFdKTtcbiAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBib2R5O1xuICAgICAgLy8gcmVzcG9uc2UucHJldkRhdGFFeHRyYSA9IHtcbiAgICAgIC8vICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICAvLyAgICAgd2luZG93RW5kRGF0ZSxcbiAgICAgIC8vIH1cbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICAvLyBnZXQgaW5mbyBvZiBjb250YWN0cyB3aXRob3V0IGVtYWlscyBwcm92aWRlZCBhbmQgYXNzaWduIHZhbHVlc1xuICAgIGNvbnN0IG5ld0F0dGVuZGVlczogTXV0YXRlZENhbGVuZGFyRXh0cmFjdGVkSlNPTkF0dGVuZGVlVHlwZVtdID0gW107XG5cbiAgICBmb3IgKGNvbnN0IGEgb2YgYm9keT8uYXR0ZW5kZWVzKSB7XG4gICAgICBpZiAoIWE/LmVtYWlsKSB7XG4gICAgICAgIGNvbnN0IGNvbnRhY3QgPSBhd2FpdCBnZXRDb250YWN0QnlOYW1lV2l0aFVzZXJJZChcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgYCUke2E/Lm5hbWV9JWBcbiAgICAgICAgKTtcbiAgICAgICAgaWYgKGNvbnRhY3Q/LmVtYWlscz8uWzBdPy52YWx1ZSkge1xuICAgICAgICAgIGNvbnN0IHByaW1hcnlFbWFpbCA9IGNvbnRhY3Q/LmVtYWlscz8uZmluZCgoZSkgPT4gISFlLnByaW1hcnkpPy52YWx1ZTtcbiAgICAgICAgICBjb25zdCBhbnlFbWFpbCA9IGNvbnRhY3Q/LmVtYWlscz8uWzBdPy52YWx1ZTtcbiAgICAgICAgICBuZXdBdHRlbmRlZXMucHVzaCh7IC4uLmEsIGVtYWlsOiBwcmltYXJ5RW1haWwgfHwgYW55RW1haWwgfSk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChcbiAgICAgICAgICAgIHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMV0/LlsnYW5kJ10/LlsyXVxuICAgICAgICAgICk7XG4gICAgICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBib2R5O1xuICAgICAgICAgIC8vIHJlc3BvbnNlLnByZXZEYXRhRXh0cmEgPSB7XG4gICAgICAgICAgLy8gICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgICAgICAvLyAgICAgd2luZG93RW5kRGF0ZSxcbiAgICAgICAgICAvLyB9XG4gICAgICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICAgICAgfVxuICAgICAgfSBlbHNlIHtcbiAgICAgICAgbmV3QXR0ZW5kZWVzLnB1c2goYSk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgYm9keS5hdHRlbmRlZXMgPSBuZXdBdHRlbmRlZXM7XG5cbiAgICBjb25zdCBtZWV0aW5nSWQgPSB1dWlkKCk7XG5cbiAgICAvLyBnZXQgaG9zdCBpbmZvXG4gICAgY29uc3QgdXNlckNvbnRhY3RJbmZvcyA9IGF3YWl0IGxpc3RVc2VyQ29udGFjdEluZm9zR2l2ZW5Vc2VySWQodXNlcklkKTtcblxuICAgIC8vIGNoZWNrIGlmIGFueSBob3N0IGluZm9cbiAgICBjb25zdCBwcm92aWRlZEhvc3RJbmZvID0gYm9keT8uYXR0ZW5kZWVzPy5maW5kKChhKSA9PiBhPy5pc0hvc3QgPT09IHRydWUpO1xuXG4gICAgY29uc3QgcHJpbWFyeUluZm9JdGVtID0gdXNlckNvbnRhY3RJbmZvcz8uZmluZChcbiAgICAgICh1KSA9PiB1LnByaW1hcnkgJiYgdS50eXBlID09PSAnZW1haWwnXG4gICAgKTtcblxuICAgIGNvbnN0IHVzZXIgPSBhd2FpdCBnZXRVc2VyR2l2ZW5JZCh1c2VySWQpO1xuXG4gICAgY29uc3QgcHJpbWFyeUhvc3RBdHRlbmRlZUluZm86IE11dGF0ZWRDYWxlbmRhckV4dHJhY3RlZEpTT05BdHRlbmRlZVR5cGUgPSB7XG4gICAgICBuYW1lOiBwcmltYXJ5SW5mb0l0ZW0/Lm5hbWUgfHwgdXNlcj8ubmFtZSxcbiAgICAgIGVtYWlsOiBwcmltYXJ5SW5mb0l0ZW0/LmlkIHx8IHVzZXI/LmVtYWlsLFxuICAgICAgaXNIb3N0OiB0cnVlLFxuICAgIH07XG5cbiAgICBpZiAoIXByb3ZpZGVkSG9zdEluZm8gJiYgcHJpbWFyeUhvc3RBdHRlbmRlZUluZm8/LmVtYWlsKSB7XG4gICAgICBib2R5Py5hdHRlbmRlZXMucHVzaChwcmltYXJ5SG9zdEF0dGVuZGVlSW5mbyk7XG4gICAgfVxuXG4gICAgY29uc3QgaG9zdEluZm8gPSBwcm92aWRlZEhvc3RJbmZvIHx8IHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvO1xuXG4gICAgaWYgKCFob3N0SW5mbz8uZW1haWwpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzFdWydhbmQnXVsxXSk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gYm9keTtcbiAgICAgIC8vIHJlc3BvbnNlLnByZXZEYXRhRXh0cmEgPSB7XG4gICAgICAvLyAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgLy8gICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICAvLyB9XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKHJlc3BvbnNlLnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzcG9uc2UyID0gYXdhaXQgZmluYWxTdGVwRk1UV1AoXG4gICAgICBib2R5LFxuICAgICAgcHJpbWFyeUhvc3RBdHRlbmRlZUluZm8sXG4gICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzLFxuICAgICAgdXNlcixcbiAgICAgIG1lZXRpbmdJZCxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICByZXNwb25zZVxuICAgICk7XG5cbiAgICByZXR1cm4gcmVzcG9uc2UyO1xuICAgIC8vIGdldCBwcmltYXJ5IGNhbGVuZGFyXG4gICAgLy8gY29uc3QgcHJpbWFyeUNhbGVuZGFyID0gYXdhaXQgZ2V0R2xvYmFsQ2FsZW5kYXIodXNlcklkKVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcHJvY2VzcyBmaW5kIG1lZXRpbmcgdGltZScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0ZNVFdQTWlzc2luZ0ZpZWxkc1JldHVybmVkID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAganNvbkJvZHk6IFVzZXJJbnB1dFRvSlNPTlR5cGUsXG4gIGRhdGVKU09OQm9keTogRGF0ZVRpbWVKU09OVHlwZSxcbiAgY3VycmVudFRpbWU6IHN0cmluZyxcbiAgbWVzc2FnZUhpc3RvcnlPYmplY3Q6IFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBsZXQgZHVyYXRpb24gPSAwO1xuXG4gICAgY29uc3QgeWVhclN0YXJ0ID1cbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8ueWVhciB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/LnllYXI7XG4gICAgY29uc3QgbW9udGhTdGFydCA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/Lm1vbnRoIHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8ubW9udGg7XG4gICAgY29uc3QgZGF5U3RhcnQgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5kYXkgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5kYXk7XG4gICAgY29uc3QgaXNvV2Vla2RheVN0YXJ0ID1cbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8uaXNvV2Vla2RheSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/Lmlzb1dlZWtkYXk7XG4gICAgY29uc3QgaG91clN0YXJ0ID1cbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8uaG91ciB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/LmhvdXI7XG4gICAgY29uc3QgbWludXRlU3RhcnQgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5taW51dGUgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5taW51dGU7XG4gICAgY29uc3Qgc3RhcnRUaW1lU3RhcnQgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5zdGFydFRpbWUgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5zdGFydFRpbWU7XG5cbiAgICBjb25zdCB5ZWFyRW5kID1cbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/LnllYXIgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8ueWVhcjtcbiAgICBjb25zdCBtb250aEVuZCA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5tb250aCB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5tb250aDtcbiAgICBjb25zdCBkYXlFbmQgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8uZGF5IHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/LmRheTtcbiAgICBjb25zdCBpc29XZWVrZGF5RW5kID1cbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/Lmlzb1dlZWtkYXkgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8uaXNvV2Vla2RheTtcbiAgICBjb25zdCBob3VyRW5kID1cbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/LmhvdXIgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8uaG91cjtcbiAgICBjb25zdCBtaW51dGVFbmQgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8ubWludXRlIHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/Lm1pbnV0ZTtcbiAgICBjb25zdCBlbmRUaW1lRW5kID1cbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/LnN0YXJ0VGltZSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5zdGFydFRpbWU7XG5cbiAgICBjb25zdCBtaXNzaW5nRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gICAgICByZXF1aXJlZDogW10sXG4gICAgICBkYXRlVGltZTogeyByZXF1aXJlZDogW10gfSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IGFueSA9IHtcbiAgICAgIHF1ZXJ5OiAnJyxcbiAgICAgIGRhdGE6IHt9LFxuICAgICAgc2tpbGw6ICdmaW5kTWVldGluZ1RpbWVXaXRoUGVybWlzc2lvbicsXG4gICAgfTtcblxuICAgIGNvbnN0IHdpbmRvd1N0YXJ0RGF0ZSA9IGV4dHJhcG9sYXRlU3RhcnREYXRlRnJvbUpTT05EYXRhKFxuICAgICAgY3VycmVudFRpbWUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHllYXJTdGFydCxcbiAgICAgIG1vbnRoU3RhcnQsXG4gICAgICBkYXlTdGFydCxcbiAgICAgIGlzb1dlZWtkYXlTdGFydCxcbiAgICAgIGhvdXJTdGFydCxcbiAgICAgIG1pbnV0ZVN0YXJ0LFxuICAgICAgc3RhcnRUaW1lU3RhcnQsXG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3cgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnRcbiAgICAgICAgICA/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/LnJlbGF0aXZlVGltZUZyb21Ob3cgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnRcbiAgICAgICAgICA/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICApO1xuXG4gICAgY29uc3Qgd2luZG93RW5kRGF0ZSA9IGV4dHJhcG9sYXRlRW5kRGF0ZUZyb21KU09ORGF0YShcbiAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgdGltZXpvbmUsXG4gICAgICB5ZWFyRW5kLFxuICAgICAgbW9udGhFbmQsXG4gICAgICBkYXlFbmQsXG4gICAgICBpc29XZWVrZGF5RW5kLFxuICAgICAgaG91ckVuZCxcbiAgICAgIG1pbnV0ZUVuZCxcbiAgICAgIGVuZFRpbWVFbmQsXG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93LFxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICk7XG5cbiAgICAvLyBnZXQgZGVmYXVsdCB2YWx1ZXNcbiAgICBjb25zdCBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzID1cbiAgICAgIGF3YWl0IGdldENoYXRNZWV0aW5nUHJlZmVyZW5jZUdpdmVuVXNlcklkKHVzZXJJZCk7XG5cbiAgICBpZiAoXG4gICAgICBkYXRlSlNPTkJvZHk/LmR1cmF0aW9uIHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZHVyYXRpb25cbiAgICApIHtcbiAgICAgIGR1cmF0aW9uID1cbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5kdXJhdGlvbiB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZHVyYXRpb247XG4gICAgfSBlbHNlIGlmIChkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5kdXJhdGlvbikge1xuICAgICAgZHVyYXRpb24gPSBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5kdXJhdGlvbjtcbiAgICB9IGVsc2Uge1xuICAgICAgZHVyYXRpb24gPSAzMDtcbiAgICB9XG5cbiAgICAvLyB0YWtlIGNhcmUgb2YgYW55IHJlY3VycmluZyBkYXRlc1xuICAgIGxldCByZWN1ck9iamVjdDogUmVjdXJyZW5jZVJ1bGVUeXBlIHwge30gPSB7fTtcbiAgICBpZiAoXG4gICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5mcmVxdWVuY3kgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5XG4gICAgKSB7XG4gICAgICBjb25zdCByZWN1ckVuZERhdGUgPSBleHRyYXBvbGF0ZURhdGVGcm9tSlNPTkRhdGEoXG4gICAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ueWVhciB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ueWVhcixcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubW9udGggfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGU/Lm1vbnRoLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5kYXkgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGU/LmRheSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaXNvV2Vla2RheSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaXNvV2Vla2RheSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaG91ciB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaG91cixcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubWludXRlIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy5taW51dGUsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnN0YXJ0VGltZSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uc3RhcnRUaW1lLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlXG4gICAgICAgICAgICA/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnJlbGF0aXZlVGltZUZyb21Ob3cgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGVcbiAgICAgICAgICAgID8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICAgKTtcblxuICAgICAgcmVjdXJPYmplY3QgPSB7XG4gICAgICAgIGZyZXF1ZW5jeTpcbiAgICAgICAgICAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5IGFzIFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlKSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5LFxuICAgICAgICBpbnRlcnZhbDpcbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5pbnRlcnZhbCB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uaW50ZXJ2YWwsXG4gICAgICB9O1xuXG4gICAgICBpZiAoXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmJ5V2Vla0RheSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmJ5V2Vla0RheVxuICAgICAgKSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmJ5V2Vla0RheSA9XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5ieVdlZWtEYXk7XG4gICAgICB9XG5cbiAgICAgIGlmIChcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlNb250aERheSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmJ5TW9udGhEYXlcbiAgICAgICkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5ieU1vbnRoRGF5ID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5O1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/Lm9jY3VycmVuY2UgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlXG4gICAgICApIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkub2NjdXJyZW5jZSA9XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8ub2NjdXJyZW5jZSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8ub2NjdXJyZW5jZTtcbiAgICAgIH1cblxuICAgICAgaWYgKFxuICAgICAgICByZWN1ckVuZERhdGUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5lbmREYXRlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGVcbiAgICAgICkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5lbmREYXRlID1cbiAgICAgICAgICByZWN1ckVuZERhdGUgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGUgfHxcbiAgICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5lbmREYXRlO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IG5ld0JvZHk6IEZpbmRNZWV0aW5nVGltZVdpdGhQZXJtaXNzaW9uVHlwZSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgdGl0bGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uc3VtbWFyeSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayxcbiAgICAgIGF0dGVuZGVlczpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uYXR0ZW5kZWVzIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uYXR0ZW5kZWVzLFxuICAgICAgbWV0aG9kOiBkYXRlSlNPTkJvZHk/Lm1ldGhvZCBhcyBhbnksXG4gICAgICBkdXJhdGlvbixcbiAgICAgIGRlc2NyaXB0aW9uOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5ub3RlcyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8ubm90ZXMsXG4gICAgICBjb25mZXJlbmNlQXBwOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5jb25mZXJlbmNlPy5hcHAgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5jb25mZXJlbmNlPy5hcHAgfHxcbiAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uY29uZmVyZW5jZUFwcCxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lIHx8XG4gICAgICAgIHdpbmRvd1N0YXJ0RGF0ZSB8fFxuICAgICAgICBjdXJyZW50VGltZSxcbiAgICAgIHdpbmRvd0VuZERhdGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmVuZFRpbWUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lIHx8XG4gICAgICAgIHdpbmRvd0VuZERhdGUgfHxcbiAgICAgICAgZGF5anMoY3VycmVudFRpbWUpLmFkZCg3LCAnZCcpLmZvcm1hdCgpLFxuICAgICAgYnVmZmVyVGltZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uYnVmZmVyVGltZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmJ1ZmZlclRpbWUgfHxcbiAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uYnVmZmVyVGltZSxcbiAgICAgIHJlbWluZGVyczpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uYWxhcm1zIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uYWxhcm1zIHx8XG4gICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LnJlbWluZGVycyB8fFxuICAgICAgICBbXSxcbiAgICAgIHByaW9yaXR5OlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5wcmlvcml0eSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnByaW9yaXR5IHx8XG4gICAgICAgIDEsXG4gICAgICB0aW1lUHJlZmVyZW5jZXM6XG4gICAgICAgIGRhdGVKU09OQm9keT8udGltZVByZWZlcmVuY2VzIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py50aW1lUHJlZmVyZW5jZXMgfHxcbiAgICAgICAgW10sXG4gICAgICBsb2NhdGlvbjpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ubG9jYXRpb24gfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5sb2NhdGlvbixcbiAgICAgIHRyYW5zcGFyZW5jeTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udHJhbnNwYXJlbmN5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udHJhbnNwYXJlbmN5LFxuICAgICAgdmlzaWJpbGl0eTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcy52aXNpYmlsaXR5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udmlzaWJpbGl0eSxcbiAgICB9O1xuXG4gICAgaWYgKFxuICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSk/LmZyZXF1ZW5jeSBhcyBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZVxuICAgICkge1xuICAgICAgbmV3Qm9keS5yZWN1ciA9IHJlY3VyT2JqZWN0IGFzIGFueTtcbiAgICB9XG5cbiAgICBjb25zdCBwcmV2Qm9keTogRmluZE1lZXRpbmdUaW1lV2l0aFBlcm1pc3Npb25UeXBlID0ge1xuICAgICAgLi4ubWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRhLFxuICAgIH07XG5cbiAgICBpZiAoIXByZXZCb2R5Py51c2VySWQpIHtcbiAgICAgIHByZXZCb2R5LnVzZXJJZCA9IHVzZXJJZCB8fCBuZXdCb2R5Py51c2VySWQ7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGltZXpvbmUpIHtcbiAgICAgIHByZXZCb2R5LnRpbWV6b25lID0gdGltZXpvbmUgfHwgbmV3Qm9keT8udGltZXpvbmU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGl0bGUpIHtcbiAgICAgIHByZXZCb2R5LnRpdGxlID0gbmV3Qm9keT8udGl0bGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uZHVyYXRpb24pIHtcbiAgICAgIHByZXZCb2R5LmR1cmF0aW9uID0gbmV3Qm9keT8uZHVyYXRpb247XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uZGVzY3JpcHRpb24pIHtcbiAgICAgIHByZXZCb2R5LmRlc2NyaXB0aW9uID0gbmV3Qm9keT8uZGVzY3JpcHRpb247XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uY29uZmVyZW5jZUFwcCkge1xuICAgICAgcHJldkJvZHkuY29uZmVyZW5jZUFwcCA9IG5ld0JvZHk/LmNvbmZlcmVuY2VBcHA7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8ud2luZG93U3RhcnREYXRlKSB7XG4gICAgICBwcmV2Qm9keS53aW5kb3dTdGFydERhdGUgPSBuZXdCb2R5Py53aW5kb3dTdGFydERhdGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8ud2luZG93RW5kRGF0ZSkge1xuICAgICAgcHJldkJvZHkud2luZG93RW5kRGF0ZSA9IG5ld0JvZHk/LndpbmRvd0VuZERhdGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uYnVmZmVyVGltZSkge1xuICAgICAgcHJldkJvZHkuYnVmZmVyVGltZSA9IG5ld0JvZHk/LmJ1ZmZlclRpbWU7XG4gICAgfVxuXG4gICAgaWYgKCEocHJldkJvZHk/LnJlbWluZGVycz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHByZXZCb2R5LnJlbWluZGVycyA9IG5ld0JvZHk/LnJlbWluZGVycyB8fCBbXTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5wcmlvcml0eSkge1xuICAgICAgcHJldkJvZHkucHJpb3JpdHkgPSBuZXdCb2R5Py5wcmlvcml0eTtcbiAgICB9XG5cbiAgICBpZiAoIShwcmV2Qm9keT8udGltZVByZWZlcmVuY2VzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkudGltZVByZWZlcmVuY2VzID0gbmV3Qm9keT8udGltZVByZWZlcmVuY2VzO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LmxvY2F0aW9uKSB7XG4gICAgICBwcmV2Qm9keS5sb2NhdGlvbiA9IG5ld0JvZHk/LmxvY2F0aW9uO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRyYW5zcGFyZW5jeSkge1xuICAgICAgcHJldkJvZHkudHJhbnNwYXJlbmN5ID0gbmV3Qm9keT8udHJhbnNwYXJlbmN5O1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnZpc2liaWxpdHkpIHtcbiAgICAgIHByZXZCb2R5LnZpc2liaWxpdHkgPSBuZXdCb2R5Py52aXNpYmlsaXR5O1xuICAgIH1cblxuICAgIC8vIHZhbGlkYXRlIHJlbWFpbmluZyByZXF1aXJlZCBmaWVsZHNcbiAgICBpZiAoIXByZXZCb2R5Py50aXRsZSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZC5wdXNoKHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMF0pO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IHByZXZCb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgIH1cblxuICAgIGlmICghKHByZXZCb2R5Py5hdHRlbmRlZXM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlsxXSk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gcHJldkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgLy8gZ2V0IGluZm8gb2YgY29udGFjdHMgd2l0aG91dCBlbWFpbHMgcHJvdmlkZWQgYW5kIGFzc2lnbiB2YWx1ZXNcbiAgICBjb25zdCBuZXdBdHRlbmRlZXM6IE11dGF0ZWRDYWxlbmRhckV4dHJhY3RlZEpTT05BdHRlbmRlZVR5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBhIG9mIG5ld0JvZHk/LmF0dGVuZGVlcykge1xuICAgICAgaWYgKCFhPy5lbWFpbCkge1xuICAgICAgICBjb25zdCBjb250YWN0ID0gYXdhaXQgZ2V0Q29udGFjdEJ5TmFtZVdpdGhVc2VySWQoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIGAlJHthPy5uYW1lfSVgXG4gICAgICAgICk7XG4gICAgICAgIGlmIChjb250YWN0Py5lbWFpbHM/LlswXT8udmFsdWUpIHtcbiAgICAgICAgICBjb25zdCBwcmltYXJ5RW1haWwgPSBjb250YWN0Py5lbWFpbHM/LmZpbmQoKGUpID0+ICEhZS5wcmltYXJ5KT8udmFsdWU7XG4gICAgICAgICAgY29uc3QgYW55RW1haWwgPSBjb250YWN0Py5lbWFpbHM/LlswXT8udmFsdWU7XG4gICAgICAgICAgbmV3QXR0ZW5kZWVzLnB1c2goeyAuLi5hLCBlbWFpbDogcHJpbWFyeUVtYWlsIHx8IGFueUVtYWlsIH0pO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2goXG4gICAgICAgICAgICByZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzFdPy5bJ2FuZCddPy5bMl1cbiAgICAgICAgICApO1xuICAgICAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gcHJldkJvZHk7XG4gICAgICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICAgICAgfVxuICAgICAgfSBlbHNlIHtcbiAgICAgICAgbmV3QXR0ZW5kZWVzLnB1c2goYSk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgbmV3Qm9keS5hdHRlbmRlZXMgPSBuZXdBdHRlbmRlZXM7XG5cbiAgICBpZiAoIShwcmV2Qm9keT8uYXR0ZW5kZWVzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkuYXR0ZW5kZWVzID0gbmV3Qm9keT8uYXR0ZW5kZWVzO1xuICAgIH1cblxuICAgIGNvbnN0IG1lZXRpbmdJZDogc3RyaW5nID0gdXVpZCgpO1xuXG4gICAgLy8gZ2V0IGhvc3QgaW5mb1xuICAgIGNvbnN0IHVzZXJDb250YWN0SW5mb3MgPSBhd2FpdCBsaXN0VXNlckNvbnRhY3RJbmZvc0dpdmVuVXNlcklkKHVzZXJJZCk7XG5cbiAgICAvLyBjaGVjayBpZiBhbnkgaG9zdCBpbmZvXG4gICAgY29uc3QgbmV3UHJvdmlkZWRIb3N0SW5mbyA9IG5ld0JvZHk/LmF0dGVuZGVlcz8uZmluZChcbiAgICAgIChhKSA9PiBhPy5pc0hvc3QgPT09IHRydWVcbiAgICApO1xuXG4gICAgY29uc3QgcHJldlByb3ZpZGVkSG9zdEluZm8gPSBwcmV2Qm9keT8uYXR0ZW5kZWVzPy5maW5kKFxuICAgICAgKGEpID0+IGE/LmlzSG9zdCA9PT0gdHJ1ZVxuICAgICk7XG5cbiAgICBjb25zdCBwcmltYXJ5SW5mb0l0ZW0gPSB1c2VyQ29udGFjdEluZm9zPy5maW5kKFxuICAgICAgKHUpID0+IHUucHJpbWFyeSAmJiB1LnR5cGUgPT09ICdlbWFpbCdcbiAgICApO1xuXG4gICAgY29uc3QgdXNlciA9IGF3YWl0IGdldFVzZXJHaXZlbklkKHVzZXJJZCk7XG5cbiAgICBjb25zdCBwcmltYXJ5SG9zdEF0dGVuZGVlSW5mbzogTXV0YXRlZENhbGVuZGFyRXh0cmFjdGVkSlNPTkF0dGVuZGVlVHlwZSA9IHtcbiAgICAgIG5hbWU6IHByaW1hcnlJbmZvSXRlbT8ubmFtZSB8fCB1c2VyPy5uYW1lLFxuICAgICAgZW1haWw6IHByaW1hcnlJbmZvSXRlbT8uaWQgfHwgdXNlcj8uZW1haWwsXG4gICAgICBpc0hvc3Q6IHRydWUsXG4gICAgfTtcblxuICAgIGlmICghbmV3UHJvdmlkZWRIb3N0SW5mbyAmJiBwcmltYXJ5SG9zdEF0dGVuZGVlSW5mbz8uZW1haWwpIHtcbiAgICAgIG5ld0JvZHk/LmF0dGVuZGVlcy5wdXNoKHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvKTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZQcm92aWRlZEhvc3RJbmZvICYmIHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvPy5lbWFpbCkge1xuICAgICAgcHJldkJvZHk/LmF0dGVuZGVlcy5wdXNoKHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvKTtcbiAgICB9XG5cbiAgICBjb25zdCBwcmV2SG9zdEluZm8gPVxuICAgICAgcHJldlByb3ZpZGVkSG9zdEluZm8gfHwgbmV3UHJvdmlkZWRIb3N0SW5mbyB8fCBwcmltYXJ5SG9zdEF0dGVuZGVlSW5mbztcblxuICAgIGlmICghcHJldkhvc3RJbmZvPy5lbWFpbCkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZC5wdXNoKHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMV1bJ2FuZCddWzFdKTtcbiAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5yZWN1cikge1xuICAgICAgcHJldkJvZHkucmVjdXIgPSBuZXdCb2R5Py5yZWN1cjtcbiAgICB9XG5cbiAgICBpZiAocmVzcG9uc2UucXVlcnkgPT09ICdtaXNzaW5nX2ZpZWxkcycpIHtcbiAgICAgIHJldHVybiByZXNwb25zZTtcbiAgICB9XG5cbiAgICBjb25zdCByZXNwb25zZTIgPSBhd2FpdCBmaW5hbFN0ZXBGTVRXUChcbiAgICAgIHByZXZCb2R5LFxuICAgICAgcHJpbWFyeUhvc3RBdHRlbmRlZUluZm8sXG4gICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzLFxuICAgICAgdXNlcixcbiAgICAgIG1lZXRpbmdJZCxcbiAgICAgIHByZXZCb2R5Py53aW5kb3dTdGFydERhdGUsXG4gICAgICBwcmV2Qm9keT8ud2luZG93RW5kRGF0ZSxcbiAgICAgIHJlc3BvbnNlXG4gICAgKTtcblxuICAgIHJldHVybiByZXNwb25zZTI7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIGZtdHdwIE1pc3NpbmdGaWVsZHNSZXR1cm5lZCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgRk1UV1BDb250cm9sQ2VudGVyID0gYXN5bmMgKFxuICBvcGVuYWk6IE9wZW5BSSxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIG1lc3NhZ2VIaXN0b3J5T2JqZWN0OiBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZSxcbiAgdXNlckN1cnJlbnRUaW1lOiBzdHJpbmcsXG4gIHF1ZXJ5OiAnbWlzc2luZ19maWVsZHMnIHwgJ2NvbXBsZXRlZCcgfCAnZXZlbnRfbm90X2ZvdW5kJyB8ICdwZW5kaW5nJ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgbWVzc2FnZUxlbmd0aCA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzPy5sZW5ndGg7XG4gICAgbGV0IHVzZXJNZXNzYWdlID0gJyc7XG4gICAgZm9yIChsZXQgaSA9IG1lc3NhZ2VMZW5ndGg7IGkgPiAwOyBpLS0pIHtcbiAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlc1tpIC0gMV07XG5cbiAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICd1c2VyJykge1xuICAgICAgICB1c2VyTWVzc2FnZSA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgYnJlYWs7XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgdXNlcklucHV0ID0gdXNlck1lc3NhZ2U7XG5cbiAgICBsZXQgZm10d3BSZXM6IFJlc3BvbnNlQWN0aW9uVHlwZSA9IHtcbiAgICAgIHF1ZXJ5OiAnY29tcGxldGVkJyxcbiAgICAgIGRhdGE6ICcnLFxuICAgICAgc2tpbGw6ICcnLFxuICAgICAgcHJldkRhdGE6IHt9LFxuICAgICAgcHJldkRhdGFFeHRyYToge30sXG4gICAgfTtcblxuICAgIHN3aXRjaCAocXVlcnkpIHtcbiAgICAgIGNhc2UgJ3BlbmRpbmcnOlxuICAgICAgICBjb25zdCBqc29uQm9keSA9IGF3YWl0IGdlbmVyYXRlSlNPTkRhdGFGcm9tVXNlcklucHV0KFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgKTtcbiAgICAgICAgY29uc3QgZGF0ZVRpbWUgPSBhd2FpdCBnZW5lcmF0ZURhdGVUaW1lKFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgKTtcbiAgICAgICAgZm10d3BSZXMgPSBhd2FpdCBwcm9jZXNzRk1UV1BQZW5kaW5nKFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICBqc29uQm9keSxcbiAgICAgICAgICBkYXRlVGltZSxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgKTtcbiAgICAgICAgYnJlYWs7XG4gICAgICBjYXNlICdtaXNzaW5nX2ZpZWxkcyc6XG4gICAgICAgIGxldCBwcmlvclVzZXJJbnB1dCA9ICcnO1xuICAgICAgICBsZXQgcHJpb3JBc3Npc3RhbnRPdXRwdXQgPSAnJztcblxuICAgICAgICBmb3IgKGxldCBpID0gbWVzc2FnZUxlbmd0aDsgaSA+IDA7IGktLSkge1xuICAgICAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlc1tpIC0gMV07XG5cbiAgICAgICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAnYXNzaXN0YW50Jykge1xuICAgICAgICAgICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAndXNlcicpIHtcbiAgICAgICAgICAgIGlmIChtZXNzYWdlLmNvbnRlbnQgIT09IHVzZXJJbnB1dCkge1xuICAgICAgICAgICAgICBwcmlvclVzZXJJbnB1dCA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKCFwcmlvclVzZXJJbnB1dCB8fCAhcHJpb3JBc3Npc3RhbnRPdXRwdXQpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZyhwcmlvclVzZXJJbnB1dCwgJyBwcmlvclVzZXJJbnB1dCcpO1xuICAgICAgICAgIGNvbnNvbGUubG9nKHByaW9yQXNzaXN0YW50T3V0cHV0LCAnIHByaW9yQXNzaXN0YW50T3V0cHV0Jyk7XG4gICAgICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBwcmlvclVzZXJpbnB1dCBvciBwcmlvckFzc2lzdGFudE91dHB1dCcpO1xuICAgICAgICB9XG4gICAgICAgIGNvbnN0IGpzb25NaXNzaW5nRmllbGRzQm9keSA9XG4gICAgICAgICAgYXdhaXQgZ2VuZXJhdGVNaXNzaW5nRmllbGRzSlNPTkRhdGFGcm9tVXNlcklucHV0KFxuICAgICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgICAgcHJpb3JVc2VySW5wdXQsXG4gICAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCxcbiAgICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICAgICk7XG4gICAgICAgIGNvbnN0IGRhdGVNaXNzaW5nRmllbGRzVGltZSA9IGF3YWl0IGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0RhdGVUaW1lKFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICBwcmlvclVzZXJJbnB1dCxcbiAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgKTtcblxuICAgICAgICBmbXR3cFJlcyA9IGF3YWl0IHByb2Nlc3NGTVRXUE1pc3NpbmdGaWVsZHNSZXR1cm5lZChcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAganNvbk1pc3NpbmdGaWVsZHNCb2R5LFxuICAgICAgICAgIGRhdGVNaXNzaW5nRmllbGRzVGltZSxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3RcbiAgICAgICAgKTtcbiAgICAgICAgYnJlYWs7XG4gICAgfVxuXG4gICAgaWYgKGZtdHdwUmVzPy5xdWVyeSA9PT0gJ2NvbXBsZXRlZCcpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UgPVxuICAgICAgICBhd2FpdCBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VGcm9tQVBJUmVzcG9uc2VGb3JVc2VyUXVlcnkoXG4gICAgICAgICAgb3BlbmFpLFxuICAgICAgICAgIGZtdHdwUmVzLmRhdGEgYXMgc3RyaW5nLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdjb21wbGV0ZWQnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBudWxsO1xuICAgIH0gZWxzZSBpZiAoZm10d3BSZXM/LnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlID1cbiAgICAgICAgYXdhaXQgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlVG9SZXF1ZXN0VXNlckZvck1pc3NpbmdGaWVsZHMoXG4gICAgICAgICAgb3BlbmFpLFxuICAgICAgICAgIGZtdHdwUmVzPy5kYXRhIGFzIFJlcXVpcmVkRmllbGRzVHlwZSxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdFxuICAgICAgICApO1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBmbXR3cFJlcz8uZGF0YSBhcyBSZXF1aXJlZEZpZWxkc1R5cGU7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0YSA9IGZtdHdwUmVzPy5wcmV2RGF0YTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRhRXh0cmEgPSBmbXR3cFJlcz8ucHJldkRhdGFFeHRyYTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRlSnNvbkJvZHkgPSBmbXR3cFJlcz8ucHJldkRhdGVKc29uQm9keTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZKc29uQm9keSA9IGZtdHdwUmVzPy5wcmV2SnNvbkJvZHk7XG4gICAgfSBlbHNlIGlmIChmbXR3cFJlcz8ucXVlcnkgPT09ICdldmVudF9ub3RfZm91bmQnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlOiBBc3Npc3RhbnRNZXNzYWdlVHlwZSA9IHtcbiAgICAgICAgcm9sZTogJ2Fzc2lzdGFudCcsXG4gICAgICAgIGNvbnRlbnQ6ICdPb3BzLi4uIHNvbWV0aGluZyB3ZW50IHdyb25nLiBTb3JyeSA6KCcsXG4gICAgICB9O1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnZXZlbnRfbm90X2ZvdW5kJztcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnJlcXVpcmVkID0gbnVsbDtcbiAgICB9XG5cbiAgICByZXR1cm4gbWVzc2FnZUhpc3RvcnlPYmplY3Q7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGUsXG4gICAgICAnIHVuYWJsZSB0byBmaW5kIG1lZXRpbmcgdGltZSB3aXRoIHBlcm1pc3Npb24gY29udHJvbCBjZW50ZXIgcGVuZGluZydcbiAgICApO1xuICB9XG59O1xuIl19