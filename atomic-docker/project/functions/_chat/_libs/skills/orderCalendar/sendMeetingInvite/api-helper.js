import requiredFields from './requiredFields';
import { callOpenAI, extrapolateEndDateFromJSONData, extrapolateStartDateFromJSONData, generateAssistantMessageToRequestUserForMissingFields, generateDateTime, generateJSONDataFromUserInput, generateMissingFieldsDateTime, generateMissingFieldsJSONDataFromUserInput, getCalendarIntegrationByName, getContactByNameWithUserId, getGlobalCalendar, getUserGivenId, listUserContactInfosGivenUserId, } from '@chat/_libs/api-helper';
import { getChatMeetingPreferenceGivenUserId } from '../scheduleMeeting/api-helper';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import { atomicCalendarSubdomainUrl, defaultOpenAIAPIKey, googleCalendarName, openAIChatGPT35LongModel, openAIChatGPT35Model, } from '@chat/_libs/constants';
import { meetingRequestSubjectPrompt, meetingRequestWithAvailabilityPrompt, } from './prompts';
import OpenAI from 'openai';
import qs from 'qs';
import { generateAvailabilityForUser } from '@chat/_libs/skills/askCalendar/askAvailability/api-helper';
import { summarizeAvailabilityPrompt, summarizeAvailabilityExampleInput, summarizeAvailabilityExampleOutput, summarizeAvailabilityResponsesPrompt, summarizeAvailabilityResponsesPromptExampleInput, summarizeAvailabilityResponsesPromptExampleOutput, } from '@chat/_libs/skills/askCalendar/askAvailability/prompts';
import _ from 'lodash';
import { process_day_availibility, process_summarize_availability, } from '@/gpt-meeting/_libs/api-helper';
import { sendEmail } from '@/_utils/email/email';
import { ENV } from '@/_utils/env';
export const day_availability_summary = async (dayAvailabilityObject) => {
    try {
        const response = await process_day_availibility(dayAvailabilityObject);
        return response;
    }
    catch (e) {
        console.log(e, ' unable to get day availability summary');
    }
};
export const summarize_availability = async (summarizeAvailabilityObject) => {
    try {
        const response = await process_summarize_availability(summarizeAvailabilityObject);
        console.log(response, ' response');
        return response;
    }
    catch (e) {
        console.log(e, ' error in summarize_availability');
    }
};
export const sendMeetingRequestTemplate = async (name, email, body, subject) => {
    try {
        const template = 'meeting-request-template';
        await sendEmail({
            template,
            locals: {
                name,
                body,
                displayName: name,
                email,
                locale: ENV.AUTH_LOCALE_DEFAULT,
                serverUrl: ENV.FUNCTION_SERVER_URL,
                clientUrl: ENV.APP_CLIENT_URL,
            },
            message: {
                to: email,
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
        console.log(e, ' unable to send meeting request');
    }
};
export const finalStepSendMeetingInvite = async (body, primaryHostAttendeeInfo, defaultMeetingPreferences, currentTime, response) => {
    try {
        const primaryCalendar = await getGlobalCalendar(body?.userId);
        if (!primaryCalendar?.id) {
            throw new Error('no primary calendar found inside createAgenda');
        }
        const calIntegration = await getCalendarIntegrationByName(body?.userId, googleCalendarName);
        if (!calIntegration?.clientType) {
            throw new Error('no client type inside calendar integration inside create agenda');
        }
        const openai = new OpenAI({
            apiKey: defaultOpenAIAPIKey,
        });
        const availableSlots = await generateAvailabilityForUser(body?.userId, body?.windowStartDate, body?.windowEndDate, body?.receiverTimezone, body?.duration || 30);
        const uniqDates = _.uniqBy(availableSlots, (curr) => dayjs(curr?.startDate?.slice(0, 19))
            .tz(body?.receiverTimezone)
            .format('YYYY-MM-DD'));
        const prompt = summarizeAvailabilityPrompt;
        const exampleInput = summarizeAvailabilityExampleInput;
        const exampleOutput = summarizeAvailabilityExampleOutput;
        let openAIAvailabilityRes = '';
        for (const uniqDate of uniqDates) {
            const filteredAvailability = availableSlots?.filter((a) => dayjs(a?.startDate)
                .tz(body?.receiverTimezone)
                .format('YYYY-MM-DD') ===
                dayjs(uniqDate?.startDate)
                    .tz(body?.receiverTimezone)
                    .format('YYYY-MM-DD'));
            if (filteredAvailability?.length > 0) {
                const miniAvailabilityText = `${dayjs(uniqDate?.startDate).tz(body?.receiverTimezone).format('L')} - ${filteredAvailability?.map((curr) => `${dayjs(curr?.startDate).tz(body?.receiverTimezone).format('LT')} - ${dayjs(curr?.endDate).tz(body?.receiverTimezone).format('LT')},`)?.reduce((prev, curr) => `${prev} ${curr}`, '')}` +
                    '\n\n';
                const miniUserData = `My availability: ` + miniAvailabilityText;
                console.log(miniUserData, ' newAvailabilityPrompt');
                const miniOpenAIAvailabilityRes = await callOpenAI(openai, prompt, openAIChatGPT35LongModel, miniUserData, exampleInput, exampleOutput);
                if (!miniOpenAIAvailabilityRes) {
                    throw new Error('no openAIAvailabilityRes present inside appointmentRequest');
                }
                openAIAvailabilityRes += '\n' + miniOpenAIAvailabilityRes;
            }
        }
        const availabilityFinalSummaryUserData = openAIAvailabilityRes;
        let finalOpenAIAvailabilitySummaryResponse = '';
        if (availabilityFinalSummaryUserData) {
            finalOpenAIAvailabilitySummaryResponse = await callOpenAI(openai, summarizeAvailabilityResponsesPrompt, openAIChatGPT35LongModel, availabilityFinalSummaryUserData, summarizeAvailabilityResponsesPromptExampleInput, summarizeAvailabilityResponsesPromptExampleOutput);
        }
        const meetingInvitePrompt = meetingRequestWithAvailabilityPrompt;
        const meetingInviteUserData = `${body?.title} \n ${body?.description}`;
        let meetingInviteOpenAIRes = await callOpenAI(openai, meetingInvitePrompt, openAIChatGPT35Model, meetingInviteUserData);
        if (!meetingInviteOpenAIRes) {
            throw new Error('no openAIRes present inside appointmentRequest');
        }
        meetingInviteOpenAIRes += '\n' + finalOpenAIAvailabilitySummaryResponse;
        const meetingQueryParams = {
            userId: body?.userId,
            timezone: body?.timezone,
            enableConference: !!body?.conferenceApp ? 'true' : 'false',
            conferenceApp: body?.conferenceApp,
            useDefaultAlarms: body?.reminders?.length > 0 ? 'false' : 'true',
            reminders: body?.reminders?.map((n) => `${n}`),
            attendeeEmails: body?.attendees?.map((a) => a?.email),
            duration: `${body?.duration}`,
            calendarId: primaryCalendar?.id,
            startTime: currentTime,
            name: primaryHostAttendeeInfo?.name,
            primaryEmail: primaryHostAttendeeInfo?.email,
            sendUpdates: defaultMeetingPreferences?.sendUpdates,
            anyoneCanAddSelf: defaultMeetingPreferences?.anyoneCanAddSelf
                ? 'true'
                : 'false',
            guestsCanInviteOthers: defaultMeetingPreferences?.guestsCanInviteOthers
                ? 'true'
                : 'false',
            guestsCanSeeOtherGuests: defaultMeetingPreferences?.guestsCanSeeOtherGuests ? 'true' : 'false',
            transparency: body?.transparency,
            visibility: body?.visibility,
        };
        const calendarLink = atomicCalendarSubdomainUrl + '?' + qs.stringify(meetingQueryParams);
        const calendarLinkMessage = `You can quickly schedule a meeting by clicking \"Reply All\" with your time to send me a copy and let me take care of the heavy work. Atom, an AI assistant from <a href=\"${calendarLink}\">Atomic</a> :)`;
        meetingInviteOpenAIRes += '\n' + calendarLinkMessage;
        const emailSubjectPrompt = meetingRequestSubjectPrompt;
        const emailSubjectUserData = meetingInviteOpenAIRes;
        const emailSubjectInviteOpenAIRes = await callOpenAI(openai, emailSubjectPrompt, openAIChatGPT35Model, emailSubjectUserData);
        await sendMeetingRequestTemplate(primaryHostAttendeeInfo?.name, body?.attendees?.filter((a) => !!a?.isHost)?.[0]?.email, meetingInviteOpenAIRes, emailSubjectInviteOpenAIRes);
        response.query = 'completed';
        response.data = `Your meeting invite message is ready and sent to your email! :) \n`;
        return response;
    }
    catch (e) {
        console.log(e, ' unable to final step send meeting invite');
    }
};
export const processSendMeetingInvitePending = async (userId, timezone, jsonBody, dateJSONBody, currentTime, formData) => {
    try {
        const missingFields = {
            required: [],
            dateTime: { required: [] },
        };
        const response = {
            query: '',
            data: {},
            skill: 'sendMeetingInvite',
        };
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
        const windowBranchStartDate = extrapolateStartDateFromJSONData(currentTime, timezone, yearStart, monthStart, dayStart, isoWeekdayStart, hourStart, minuteStart, startTimeStart, dateJSONBody?.findTimeWindowStart?.relativeTimeChangeFromNow, dateJSONBody?.findTimeWindowStart?.relativeTimeFromNow);
        let windowStartDate = windowBranchStartDate;
        if (!windowStartDate) {
            windowStartDate = dayjs().format();
        }
        let windowEndDate = extrapolateEndDateFromJSONData(currentTime, timezone, yearEnd, monthEnd, dayEnd, isoWeekdayEnd, hourEnd, minuteEnd, endTimeEnd, dateJSONBody?.findTimeWindowEnd?.relativeTimeChangeFromNow, dateJSONBody?.findTimeWindowEnd?.relativeTimeFromNow);
        if (!windowEndDate) {
            windowEndDate = dayjs(windowStartDate).add(1, 'w').format();
        }
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
            reminders: jsonBody?.params?.alarms || defaultMeetingPreferences?.reminders || [],
            transparency: jsonBody?.params?.transparency,
            visibility: jsonBody?.params.visibility,
            receiverTimezone: formData?.value,
        };
        if (!formData?.value) {
            response.query = 'missing_fields';
            missingFields.dateTime.required.push(requiredFields.required?.[2]);
            response.data = missingFields;
            response.prevData = body;
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (!body?.title) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[0]);
            response.data = missingFields;
            response.prevData = body;
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (!(body?.attendees?.length > 0)) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[1]);
            response.data = missingFields;
            response.prevData = body;
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
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
                    response.prevJsonBody = jsonBody;
                    response.prevDateJsonBody = dateJSONBody;
                }
            }
            else {
                newAttendees.push(a);
            }
        }
        body.attendees = newAttendees;
        const userContactInfos = await listUserContactInfosGivenUserId(userId);
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
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepSendMeetingInvite(body, primaryHostAttendeeInfo, defaultMeetingPreferences, currentTime, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process send meeting invite');
    }
};
export const processSendMeetingInviteMissingFieldsReturned = async (userId, timezone, jsonBody, dateJSONBody, currentTime, formData, messageHistoryObject) => {
    try {
        const missingFields = {
            required: [],
            dateTime: { required: [] },
        };
        const response = {
            query: '',
            data: {},
            skill: 'sendMeetingInvite',
        };
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
        const windowBranchStartDate = extrapolateStartDateFromJSONData(currentTime, timezone, yearStart, monthStart, dayStart, isoWeekdayStart, hourStart, minuteStart, startTimeStart, dateJSONBody?.findTimeWindowStart?.relativeTimeChangeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart
                ?.relativeTimeChangeFromNow, dateJSONBody?.findTimeWindowStart?.relativeTimeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart
                ?.relativeTimeFromNow);
        let windowStartDate = windowBranchStartDate;
        if (!windowStartDate) {
            windowStartDate = dayjs().format();
        }
        let windowEndDate = extrapolateEndDateFromJSONData(currentTime, timezone, yearEnd, monthEnd, dayEnd, isoWeekdayEnd, hourEnd, minuteEnd, endTimeEnd, dateJSONBody?.findTimeWindowEnd?.relativeTimeChangeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd
                ?.relativeTimeChangeFromNow, dateJSONBody?.findTimeWindowEnd?.relativeTimeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd
                ?.relativeTimeFromNow);
        if (!windowEndDate) {
            windowEndDate = dayjs(windowStartDate).add(1, 'w').format();
        }
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
            reminders: jsonBody?.params?.alarms ||
                messageHistoryObject?.prevJsonBody?.params?.alarms ||
                defaultMeetingPreferences?.reminders ||
                [],
            transparency: jsonBody?.params?.transparency ||
                messageHistoryObject?.prevJsonBody?.params?.transparency,
            visibility: jsonBody?.params.visibility ||
                messageHistoryObject?.prevJsonBody?.params?.visibility,
            receiverTimezone: formData?.value,
        };
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
        if (!(prevBody?.reminders?.length > 0)) {
            prevBody.reminders = newBody?.reminders || [];
        }
        if (!prevBody?.transparency) {
            prevBody.transparency = newBody?.transparency;
        }
        if (!prevBody?.visibility) {
            prevBody.visibility = newBody?.visibility;
        }
        if (!prevBody?.receiverTimezone) {
            prevBody.receiverTimezone = newBody?.receiverTimezone;
        }
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
        const userContactInfos = await listUserContactInfosGivenUserId(userId);
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
        if (!prevBody?.receiverTimezone) {
            response.query = 'missing_fields';
            missingFields.dateTime.required.push(requiredFields.required?.[2]);
            response.data = missingFields;
            response.prevData = prevBody;
        }
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepSendMeetingInvite(prevBody, prevHostInfo, defaultMeetingPreferences, currentTime, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process send meeitng invite missing fields returned');
    }
};
export const sendMeetingInviteControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
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
        let SMIRes = {
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
                SMIRes = await processSendMeetingInvitePending(userId, timezone, jsonBody, dateTime, userCurrentTime, messageHistoryObject?.formData);
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
                SMIRes = await processSendMeetingInviteMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, dateMissingFieldsTime, userCurrentTime, messageHistoryObject?.formData, messageHistoryObject);
                break;
        }
        if (SMIRes?.query === 'completed') {
            const assistantMessage = {
                role: 'assistant',
                content: SMIRes?.data,
            };
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (SMIRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, SMIRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required = SMIRes?.data;
            messageHistoryObject.prevData = SMIRes?.prevData;
            messageHistoryObject.prevDataExtra = SMIRes?.prevDataExtra;
            messageHistoryObject.prevDateJsonBody = SMIRes?.prevDateJsonBody;
            messageHistoryObject.prevJsonBody = SMIRes?.prevJsonBody;
        }
        else if (SMIRes?.query === 'event_not_found') {
            const assistantMessage = {
                role: 'assistant',
                content: "Oops... I couldn't find the event. Sorry :(",
            };
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'event_not_found';
            messageHistoryObject.required = null;
        }
        return messageHistoryObject;
    }
    catch (e) {
        console.log(e, ' unable to send meeting invite control center pending');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBVUEsT0FBTyxjQUFjLE1BQU0sa0JBQWtCLENBQUM7QUFDOUMsT0FBTyxFQUNMLFVBQVUsRUFDViw4QkFBOEIsRUFDOUIsZ0NBQWdDLEVBQ2hDLHFEQUFxRCxFQUNyRCxnQkFBZ0IsRUFDaEIsNkJBQTZCLEVBQzdCLDZCQUE2QixFQUM3QiwwQ0FBMEMsRUFDMUMsNEJBQTRCLEVBQzVCLDBCQUEwQixFQUMxQixpQkFBaUIsRUFDakIsY0FBYyxFQUNkLCtCQUErQixHQUNoQyxNQUFNLHdCQUF3QixDQUFDO0FBQ2hDLE9BQU8sRUFBRSxtQ0FBbUMsRUFBRSxNQUFNLCtCQUErQixDQUFDO0FBQ3BGLE9BQU8sRUFBRSxLQUFLLEVBQUUsTUFBTSxpQ0FBaUMsQ0FBQztBQUN4RCxPQUFPLEVBQ0wsMEJBQTBCLEVBQzFCLG1CQUFtQixFQUNuQixrQkFBa0IsRUFDbEIsd0JBQXdCLEVBQ3hCLG9CQUFvQixHQUNyQixNQUFNLHVCQUF1QixDQUFDO0FBTS9CLE9BQU8sRUFDTCwyQkFBMkIsRUFDM0Isb0NBQW9DLEdBQ3JDLE1BQU0sV0FBVyxDQUFDO0FBQ25CLE9BQU8sTUFBTSxNQUFNLFFBQVEsQ0FBQztBQUM1QixPQUFPLEVBQUUsTUFBTSxJQUFJLENBQUM7QUFPcEIsT0FBTyxFQUFFLDJCQUEyQixFQUFFLE1BQU0sMkRBQTJELENBQUM7QUFDeEcsT0FBTyxFQUNMLDJCQUEyQixFQUMzQixpQ0FBaUMsRUFDakMsa0NBQWtDLEVBQ2xDLG9DQUFvQyxFQUNwQyxnREFBZ0QsRUFDaEQsaURBQWlELEdBQ2xELE1BQU0sd0RBQXdELENBQUM7QUFDaEUsT0FBTyxDQUFDLE1BQU0sUUFBUSxDQUFDO0FBQ3ZCLE9BQU8sRUFDTCx3QkFBd0IsRUFDeEIsOEJBQThCLEdBQy9CLE1BQU0sZ0NBQWdDLENBQUM7QUFDeEMsT0FBTyxFQUFFLFNB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QztJQUMxRSxDQUFDO0FBQ0gsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IERhdGVUaW1lSlNPTlR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvZGF0ZXRpbWUvRGF0ZVRpbWVKU09OSlNPTlR5cGUnO1xuaW1wb3J0IFVzZXJJbnB1dFRvSlNPTlR5cGUsIHtcbiAgTXV0YXRlZENhbGVuZGFyRXh0cmFjdGVkSlNPTkF0dGVuZGVlVHlwZSxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvVXNlcklucHV0VG9KU09OVHlwZSc7XG5pbXBvcnQge1xuICBNZWV0aW5nVXJsUXVlcnlQYXJhbXNUeXBlLFxuICBSZWNlaXZlclRpbWV6b25lRm9ybURhdGFSZXNwb25zZVR5cGUsXG4gIFNlbmRNZWV0aW5nSW52aXRlVHlwZSxcbn0gZnJvbSAnLi90eXBlcyc7XG5pbXBvcnQgUmVxdWlyZWRGaWVsZHNUeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1JlcXVpcmVkRmllbGRzVHlwZSc7XG5pbXBvcnQgcmVxdWlyZWRGaWVsZHMgZnJvbSAnLi9yZXF1aXJlZEZpZWxkcyc7XG5pbXBvcnQge1xuICBjYWxsT3BlbkFJLFxuICBleHRyYXBvbGF0ZUVuZERhdGVGcm9tSlNPTkRhdGEsXG4gIGV4dHJhcG9sYXRlU3RhcnREYXRlRnJvbUpTT05EYXRhLFxuICBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VUb1JlcXVlc3RVc2VyRm9yTWlzc2luZ0ZpZWxkcyxcbiAgZ2VuZXJhdGVEYXRlVGltZSxcbiAgZ2VuZXJhdGVKU09ORGF0YUZyb21Vc2VySW5wdXQsXG4gIGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0RhdGVUaW1lLFxuICBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNKU09ORGF0YUZyb21Vc2VySW5wdXQsXG4gIGdldENhbGVuZGFySW50ZWdyYXRpb25CeU5hbWUsXG4gIGdldENvbnRhY3RCeU5hbWVXaXRoVXNlcklkLFxuICBnZXRHbG9iYWxDYWxlbmRhcixcbiAgZ2V0VXNlckdpdmVuSWQsXG4gIGxpc3RVc2VyQ29udGFjdEluZm9zR2l2ZW5Vc2VySWQsXG59IGZyb20gJ0BjaGF0L19saWJzL2FwaS1oZWxwZXInO1xuaW1wb3J0IHsgZ2V0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlR2l2ZW5Vc2VySWQgfSBmcm9tICcuLi9zY2hlZHVsZU1lZXRpbmcvYXBpLWhlbHBlcic7XG5pbXBvcnQgeyBkYXlqcyB9IGZyb20gJ0BjaGF0L19saWJzL2RhdGV0aW1lL2RhdGUtdXRpbHMnO1xuaW1wb3J0IHtcbiAgYXRvbWljQ2FsZW5kYXJTdWJkb21haW5VcmwsXG4gIGRlZmF1bHRPcGVuQUlBUElLZXksXG4gIGdvb2dsZUNhbGVuZGFyTmFtZSxcbiAgb3BlbkFJQ2hhdEdQVDM1TG9uZ01vZGVsLFxuICBvcGVuQUlDaGF0R1BUMzVNb2RlbCxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7XG4gIERheUF2YWlsYWJpbGl0eVR5cGUsXG4gIFN1bW1hcml6ZURheUF2YWlsYWJpbGl0eVR5cGUsXG59IGZyb20gJy4vYXZhaWxhYmlsaXR5VHlwZXMnO1xuXG5pbXBvcnQge1xuICBtZWV0aW5nUmVxdWVzdFN1YmplY3RQcm9tcHQsXG4gIG1lZXRpbmdSZXF1ZXN0V2l0aEF2YWlsYWJpbGl0eVByb21wdCxcbn0gZnJvbSAnLi9wcm9tcHRzJztcbmltcG9ydCBPcGVuQUkgZnJvbSAnb3BlbmFpJztcbmltcG9ydCBxcyBmcm9tICdxcyc7XG5pbXBvcnQge1xuICBBc3Npc3RhbnRNZXNzYWdlVHlwZSxcbiAgU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGUsXG59IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL01lc3NhZ2luZy9NZXNzYWdpbmdUeXBlcyc7XG5pbXBvcnQgeyBDaGF0TWVldGluZ1ByZWZlcmVuY2VzVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0NoYXRNZWV0aW5nUHJlZmVyZW5jZXNUeXBlJztcbmltcG9ydCBSZXNwb25zZUFjdGlvblR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVzcG9uc2VBY3Rpb25UeXBlJztcbmltcG9ydCB7IGdlbmVyYXRlQXZhaWxhYmlsaXR5Rm9yVXNlciB9IGZyb20gJ0BjaGF0L19saWJzL3NraWxscy9hc2tDYWxlbmRhci9hc2tBdmFpbGFiaWxpdHkvYXBpLWhlbHBlcic7XG5pbXBvcnQge1xuICBzdW1tYXJpemVBdmFpbGFiaWxpdHlQcm9tcHQsXG4gIHN1bW1hcml6ZUF2YWlsYWJpbGl0eUV4YW1wbGVJbnB1dCxcbiAgc3VtbWFyaXplQXZhaWxhYmlsaXR5RXhhbXBsZU91dHB1dCxcbiAgc3VtbWFyaXplQXZhaWxhYmlsaXR5UmVzcG9uc2VzUHJvbXB0LFxuICBzdW1tYXJpemVBdmFpbGFiaWxpdHlSZXNwb25zZXNQcm9tcHRFeGFtcGxlSW5wdXQsXG4gIHN1bW1hcml6ZUF2YWlsYWJpbGl0eVJlc3BvbnNlc1Byb21wdEV4YW1wbGVPdXRwdXQsXG59IGZyb20gJ0BjaGF0L19saWJzL3NraWxscy9hc2tDYWxlbmRhci9hc2tBdmFpbGFiaWxpdHkvcHJvbXB0cyc7XG5pbXBvcnQgXyBmcm9tICdsb2Rhc2gnO1xuaW1wb3J0IHtcbiAgcHJvY2Vzc19kYXlfYXZhaWxpYmlsaXR5LFxuICBwcm9jZXNzX3N1bW1hcml6ZV9hdmFpbGFiaWxpdHksXG59IGZyb20gJ0AvZ3B0LW1lZXRpbmcvX2xpYnMvYXBpLWhlbHBlcic7XG5pbXBvcnQgeyBzZW5kRW1haWwgfSBmcm9tICdAL191dGlscy9lbWFpbC9lbWFpbCc7XG5pbXBvcnQgeyBFTlYgfSBmcm9tICdAL191dGlscy9lbnYnO1xuXG5leHBvcnQgY29uc3QgZGF5X2F2YWlsYWJpbGl0eV9zdW1tYXJ5ID0gYXN5bmMgKFxuICBkYXlBdmFpbGFiaWxpdHlPYmplY3Q6IERheUF2YWlsYWJpbGl0eVR5cGVcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgcHJvY2Vzc19kYXlfYXZhaWxpYmlsaXR5KGRheUF2YWlsYWJpbGl0eU9iamVjdCk7XG4gICAgcmV0dXJuIHJlc3BvbnNlO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGRheSBhdmFpbGFiaWxpdHkgc3VtbWFyeScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3Qgc3VtbWFyaXplX2F2YWlsYWJpbGl0eSA9IGFzeW5jIChcbiAgc3VtbWFyaXplQXZhaWxhYmlsaXR5T2JqZWN0OiBTdW1tYXJpemVEYXlBdmFpbGFiaWxpdHlUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IHByb2Nlc3Nfc3VtbWFyaXplX2F2YWlsYWJpbGl0eShcbiAgICAgIHN1bW1hcml6ZUF2YWlsYWJpbGl0eU9iamVjdFxuICAgICk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXNwb25zZSwgJyByZXNwb25zZScpO1xuICAgIHJldHVybiByZXNwb25zZTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgZXJyb3IgaW4gc3VtbWFyaXplX2F2YWlsYWJpbGl0eScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3Qgc2VuZE1lZXRpbmdSZXF1ZXN0VGVtcGxhdGUgPSBhc3luYyAoXG4gIG5hbWU6IHN0cmluZyxcbiAgZW1haWw6IHN0cmluZyxcbiAgYm9keTogc3RyaW5nLFxuICBzdWJqZWN0OiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHRlbXBsYXRlID0gJ21lZXRpbmctcmVxdWVzdC10ZW1wbGF0ZSc7XG5cbiAgICBhd2FpdCBzZW5kRW1haWwoe1xuICAgICAgdGVtcGxhdGUsXG4gICAgICBsb2NhbHM6IHtcbiAgICAgICAgbmFtZSxcbiAgICAgICAgYm9keSxcbiAgICAgICAgZGlzcGxheU5hbWU6IG5hbWUsXG4gICAgICAgIGVtYWlsLFxuICAgICAgICBsb2NhbGU6IEVOVi5BVVRIX0xPQ0FMRV9ERUZBVUxULFxuICAgICAgICBzZXJ2ZXJVcmw6IEVOVi5GVU5DVElPTl9TRVJWRVJfVVJMLFxuICAgICAgICBjbGllbnRVcmw6IEVOVi5BUFBfQ0xJRU5UX1VSTCxcbiAgICAgIH0sXG4gICAgICBtZXNzYWdlOiB7XG4gICAgICAgIHRvOiBlbWFpbCxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICd4LWVtYWlsLXRlbXBsYXRlJzoge1xuICAgICAgICAgICAgcHJlcGFyZWQ6IHRydWUsXG4gICAgICAgICAgICB2YWx1ZTogdGVtcGxhdGUsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgfSk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBzZW5kIG1lZXRpbmcgcmVxdWVzdCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZmluYWxTdGVwU2VuZE1lZXRpbmdJbnZpdGUgPSBhc3luYyAoXG4gIGJvZHk6IFNlbmRNZWV0aW5nSW52aXRlVHlwZSxcbiAgcHJpbWFyeUhvc3RBdHRlbmRlZUluZm86IE11dGF0ZWRDYWxlbmRhckV4dHJhY3RlZEpTT05BdHRlbmRlZVR5cGUsXG4gIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM6IENoYXRNZWV0aW5nUHJlZmVyZW5jZXNUeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nLFxuICByZXNwb25zZTogYW55XG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBwcmltYXJ5Q2FsZW5kYXIgPSBhd2FpdCBnZXRHbG9iYWxDYWxlbmRhcihib2R5Py51c2VySWQpO1xuXG4gICAgaWYgKCFwcmltYXJ5Q2FsZW5kYXI/LmlkKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIHByaW1hcnkgY2FsZW5kYXIgZm91bmQgaW5zaWRlIGNyZWF0ZUFnZW5kYScpO1xuICAgIH1cblxuICAgIGNvbnN0IGNhbEludGVncmF0aW9uID0gYXdhaXQgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZShcbiAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgIGdvb2dsZUNhbGVuZGFyTmFtZVxuICAgICk7XG5cbiAgICBpZiAoIWNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgICdubyBjbGllbnQgdHlwZSBpbnNpZGUgY2FsZW5kYXIgaW50ZWdyYXRpb24gaW5zaWRlIGNyZWF0ZSBhZ2VuZGEnXG4gICAgICApO1xuICAgIH1cblxuICAgIGNvbnN0IG9wZW5haSA9IG5ldyBPcGVuQUkoe1xuICAgICAgYXBpS2V5OiBkZWZhdWx0T3BlbkFJQVBJS2V5LFxuICAgIH0pO1xuXG4gICAgY29uc3QgYXZhaWxhYmxlU2xvdHMgPSBhd2FpdCBnZW5lcmF0ZUF2YWlsYWJpbGl0eUZvclVzZXIoXG4gICAgICBib2R5Py51c2VySWQsXG4gICAgICBib2R5Py53aW5kb3dTdGFydERhdGUsXG4gICAgICBib2R5Py53aW5kb3dFbmREYXRlLFxuICAgICAgYm9keT8ucmVjZWl2ZXJUaW1lem9uZSxcbiAgICAgIGJvZHk/LmR1cmF0aW9uIHx8IDMwXG4gICAgKTtcblxuICAgIGNvbnN0IHVuaXFEYXRlcyA9IF8udW5pcUJ5KGF2YWlsYWJsZVNsb3RzLCAoY3VycikgPT5cbiAgICAgIGRheWpzKGN1cnI/LnN0YXJ0RGF0ZT8uc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooYm9keT8ucmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERCcpXG4gICAgKTtcblxuICAgIGNvbnN0IHByb21wdCA9IHN1bW1hcml6ZUF2YWlsYWJpbGl0eVByb21wdDtcblxuICAgIGNvbnN0IGV4YW1wbGVJbnB1dCA9IHN1bW1hcml6ZUF2YWlsYWJpbGl0eUV4YW1wbGVJbnB1dDtcblxuICAgIGNvbnN0IGV4YW1wbGVPdXRwdXQgPSBzdW1tYXJpemVBdmFpbGFiaWxpdHlFeGFtcGxlT3V0cHV0O1xuXG4gICAgbGV0IG9wZW5BSUF2YWlsYWJpbGl0eVJlcyA9ICcnO1xuXG4gICAgZm9yIChjb25zdCB1bmlxRGF0ZSBvZiB1bmlxRGF0ZXMpIHtcbiAgICAgIGNvbnN0IGZpbHRlcmVkQXZhaWxhYmlsaXR5ID0gYXZhaWxhYmxlU2xvdHM/LmZpbHRlcihcbiAgICAgICAgKGEpID0+XG4gICAgICAgICAgZGF5anMoYT8uc3RhcnREYXRlKVxuICAgICAgICAgICAgLnR6KGJvZHk/LnJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREJykgPT09XG4gICAgICAgICAgZGF5anModW5pcURhdGU/LnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgIC50eihib2R5Py5yZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERCcpXG4gICAgICApO1xuXG4gICAgICBpZiAoZmlsdGVyZWRBdmFpbGFiaWxpdHk/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgY29uc3QgbWluaUF2YWlsYWJpbGl0eVRleHQgPVxuICAgICAgICAgIGAke2RheWpzKHVuaXFEYXRlPy5zdGFydERhdGUpLnR6KGJvZHk/LnJlY2VpdmVyVGltZXpvbmUpLmZvcm1hdCgnTCcpfSAtICR7ZmlsdGVyZWRBdmFpbGFiaWxpdHk/Lm1hcCgoY3VycikgPT4gYCR7ZGF5anMoY3Vycj8uc3RhcnREYXRlKS50eihib2R5Py5yZWNlaXZlclRpbWV6b25lKS5mb3JtYXQoJ0xUJyl9IC0gJHtkYXlqcyhjdXJyPy5lbmREYXRlKS50eihib2R5Py5yZWNlaXZlclRpbWV6b25lKS5mb3JtYXQoJ0xUJyl9LGApPy5yZWR1Y2UoKHByZXYsIGN1cnIpID0+IGAke3ByZXZ9ICR7Y3Vycn1gLCAnJyl9YCArXG4gICAgICAgICAgJ1xcblxcbic7XG5cbiAgICAgICAgY29uc3QgbWluaVVzZXJEYXRhID0gYE15IGF2YWlsYWJpbGl0eTogYCArIG1pbmlBdmFpbGFiaWxpdHlUZXh0O1xuXG4gICAgICAgIGNvbnNvbGUubG9nKG1pbmlVc2VyRGF0YSwgJyBuZXdBdmFpbGFiaWxpdHlQcm9tcHQnKTtcblxuICAgICAgICBjb25zdCBtaW5pT3BlbkFJQXZhaWxhYmlsaXR5UmVzID0gYXdhaXQgY2FsbE9wZW5BSShcbiAgICAgICAgICBvcGVuYWksXG4gICAgICAgICAgcHJvbXB0LFxuICAgICAgICAgIG9wZW5BSUNoYXRHUFQzNUxvbmdNb2RlbCxcbiAgICAgICAgICBtaW5pVXNlckRhdGEsXG4gICAgICAgICAgZXhhbXBsZUlucHV0LFxuICAgICAgICAgIGV4YW1wbGVPdXRwdXRcbiAgICAgICAgKTtcblxuICAgICAgICBpZiAoIW1pbmlPcGVuQUlBdmFpbGFiaWxpdHlSZXMpIHtcbiAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgICAgICAnbm8gb3BlbkFJQXZhaWxhYmlsaXR5UmVzIHByZXNlbnQgaW5zaWRlIGFwcG9pbnRtZW50UmVxdWVzdCdcbiAgICAgICAgICApO1xuICAgICAgICB9XG5cbiAgICAgICAgb3BlbkFJQXZhaWxhYmlsaXR5UmVzICs9ICdcXG4nICsgbWluaU9wZW5BSUF2YWlsYWJpbGl0eVJlcztcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCBhdmFpbGFiaWxpdHlGaW5hbFN1bW1hcnlVc2VyRGF0YSA9IG9wZW5BSUF2YWlsYWJpbGl0eVJlcztcblxuICAgIGxldCBmaW5hbE9wZW5BSUF2YWlsYWJpbGl0eVN1bW1hcnlSZXNwb25zZSA9ICcnO1xuXG4gICAgaWYgKGF2YWlsYWJpbGl0eUZpbmFsU3VtbWFyeVVzZXJEYXRhKSB7XG4gICAgICBmaW5hbE9wZW5BSUF2YWlsYWJpbGl0eVN1bW1hcnlSZXNwb25zZSA9IGF3YWl0IGNhbGxPcGVuQUkoXG4gICAgICAgIG9wZW5haSxcbiAgICAgICAgc3VtbWFyaXplQXZhaWxhYmlsaXR5UmVzcG9uc2VzUHJvbXB0LFxuICAgICAgICBvcGVuQUlDaGF0R1BUMzVMb25nTW9kZWwsXG4gICAgICAgIGF2YWlsYWJpbGl0eUZpbmFsU3VtbWFyeVVzZXJEYXRhLFxuICAgICAgICBzdW1tYXJpemVBdmFpbGFiaWxpdHlSZXNwb25zZXNQcm9tcHRFeGFtcGxlSW5wdXQsXG4gICAgICAgIHN1bW1hcml6ZUF2YWlsYWJpbGl0eVJlc3BvbnNlc1Byb21wdEV4YW1wbGVPdXRwdXRcbiAgICAgICk7XG4gICAgfVxuXG4gICAgY29uc3QgbWVldGluZ0ludml0ZVByb21wdCA9IG1lZXRpbmdSZXF1ZXN0V2l0aEF2YWlsYWJpbGl0eVByb21wdDtcblxuICAgIGNvbnN0IG1lZXRpbmdJbnZpdGVVc2VyRGF0YSA9IGAke2JvZHk/LnRpdGxlfSBcXG4gJHtib2R5Py5kZXNjcmlwdGlvbn1gO1xuXG4gICAgbGV0IG1lZXRpbmdJbnZpdGVPcGVuQUlSZXMgPSBhd2FpdCBjYWxsT3BlbkFJKFxuICAgICAgb3BlbmFpLFxuICAgICAgbWVldGluZ0ludml0ZVByb21wdCxcbiAgICAgIG9wZW5BSUNoYXRHUFQzNU1vZGVsLFxuICAgICAgbWVldGluZ0ludml0ZVVzZXJEYXRhXG4gICAgKTtcblxuICAgIGlmICghbWVldGluZ0ludml0ZU9wZW5BSVJlcykge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBvcGVuQUlSZXMgcHJlc2VudCBpbnNpZGUgYXBwb2ludG1lbnRSZXF1ZXN0Jyk7XG4gICAgfVxuXG4gICAgbWVldGluZ0ludml0ZU9wZW5BSVJlcyArPSAnXFxuJyArIGZpbmFsT3BlbkFJQXZhaWxhYmlsaXR5U3VtbWFyeVJlc3BvbnNlO1xuXG4gICAgY29uc3QgbWVldGluZ1F1ZXJ5UGFyYW1zOiBNZWV0aW5nVXJsUXVlcnlQYXJhbXNUeXBlID0ge1xuICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICB0aW1lem9uZTogYm9keT8udGltZXpvbmUsXG4gICAgICBlbmFibGVDb25mZXJlbmNlOiAhIWJvZHk/LmNvbmZlcmVuY2VBcHAgPyAndHJ1ZScgOiAnZmFsc2UnLFxuICAgICAgY29uZmVyZW5jZUFwcDogYm9keT8uY29uZmVyZW5jZUFwcCxcbiAgICAgIHVzZURlZmF1bHRBbGFybXM6IGJvZHk/LnJlbWluZGVycz8ubGVuZ3RoID4gMCA/ICdmYWxzZScgOiAndHJ1ZScsXG4gICAgICByZW1pbmRlcnM6IGJvZHk/LnJlbWluZGVycz8ubWFwKChuKSA9PiBgJHtufWApLFxuICAgICAgYXR0ZW5kZWVFbWFpbHM6IGJvZHk/LmF0dGVuZGVlcz8ubWFwKChhKSA9PiBhPy5lbWFpbCksXG4gICAgICBkdXJhdGlvbjogYCR7Ym9keT8uZHVyYXRpb259YCxcbiAgICAgIGNhbGVuZGFySWQ6IHByaW1hcnlDYWxlbmRhcj8uaWQsXG4gICAgICBzdGFydFRpbWU6IGN1cnJlbnRUaW1lLFxuICAgICAgbmFtZTogcHJpbWFyeUhvc3RBdHRlbmRlZUluZm8/Lm5hbWUsXG4gICAgICBwcmltYXJ5RW1haWw6IHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvPy5lbWFpbCxcbiAgICAgIHNlbmRVcGRhdGVzOiBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5zZW5kVXBkYXRlcyxcbiAgICAgIGFueW9uZUNhbkFkZFNlbGY6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LmFueW9uZUNhbkFkZFNlbGZcbiAgICAgICAgPyAndHJ1ZSdcbiAgICAgICAgOiAnZmFsc2UnLFxuICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5ndWVzdHNDYW5JbnZpdGVPdGhlcnNcbiAgICAgICAgPyAndHJ1ZSdcbiAgICAgICAgOiAnZmFsc2UnLFxuICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHM6XG4gICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzID8gJ3RydWUnIDogJ2ZhbHNlJyxcbiAgICAgIHRyYW5zcGFyZW5jeTogYm9keT8udHJhbnNwYXJlbmN5LFxuICAgICAgdmlzaWJpbGl0eTogYm9keT8udmlzaWJpbGl0eSxcbiAgICB9O1xuXG4gICAgY29uc3QgY2FsZW5kYXJMaW5rID1cbiAgICAgIGF0b21pY0NhbGVuZGFyU3ViZG9tYWluVXJsICsgJz8nICsgcXMuc3RyaW5naWZ5KG1lZXRpbmdRdWVyeVBhcmFtcyk7XG4gICAgY29uc3QgY2FsZW5kYXJMaW5rTWVzc2FnZSA9IGBZb3UgY2FuIHF1aWNrbHkgc2NoZWR1bGUgYSBtZWV0aW5nIGJ5IGNsaWNraW5nIFxcXCJSZXBseSBBbGxcXFwiIHdpdGggeW91ciB0aW1lIHRvIHNlbmQgbWUgYSBjb3B5IGFuZCBsZXQgbWUgdGFrZSBjYXJlIG9mIHRoZSBoZWF2eSB3b3JrLiBBdG9tLCBhbiBBSSBhc3Npc3RhbnQgZnJvbSA8YSBocmVmPVxcXCIke2NhbGVuZGFyTGlua31cXFwiPkF0b21pYzwvYT4gOilgO1xuXG4gICAgbWVldGluZ0ludml0ZU9wZW5BSVJlcyArPSAnXFxuJyArIGNhbGVuZGFyTGlua01lc3NhZ2U7XG5cbiAgICBjb25zdCBlbWFpbFN1YmplY3RQcm9tcHQgPSBtZWV0aW5nUmVxdWVzdFN1YmplY3RQcm9tcHQ7XG5cbiAgICBjb25zdCBlbWFpbFN1YmplY3RVc2VyRGF0YSA9IG1lZXRpbmdJbnZpdGVPcGVuQUlSZXM7XG5cbiAgICBjb25zdCBlbWFpbFN1YmplY3RJbnZpdGVPcGVuQUlSZXMgPSBhd2FpdCBjYWxsT3BlbkFJKFxuICAgICAgb3BlbmFpLFxuICAgICAgZW1haWxTdWJqZWN0UHJvbXB0LFxuICAgICAgb3BlbkFJQ2hhdEdQVDM1TW9kZWwsXG4gICAgICBlbWFpbFN1YmplY3RVc2VyRGF0YVxuICAgICk7XG5cbiAgICBhd2FpdCBzZW5kTWVldGluZ1JlcXVlc3RUZW1wbGF0ZShcbiAgICAgIHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvPy5uYW1lLFxuICAgICAgYm9keT8uYXR0ZW5kZWVzPy5maWx0ZXIoKGEpID0+ICEhYT8uaXNIb3N0KT8uWzBdPy5lbWFpbCxcbiAgICAgIG1lZXRpbmdJbnZpdGVPcGVuQUlSZXMsXG4gICAgICBlbWFpbFN1YmplY3RJbnZpdGVPcGVuQUlSZXNcbiAgICApO1xuXG4gICAgcmVzcG9uc2UucXVlcnkgPSAnY29tcGxldGVkJztcblxuICAgIHJlc3BvbnNlLmRhdGEgPSBgWW91ciBtZWV0aW5nIGludml0ZSBtZXNzYWdlIGlzIHJlYWR5IGFuZCBzZW50IHRvIHlvdXIgZW1haWwhIDopIFxcbmA7XG5cbiAgICByZXR1cm4gcmVzcG9uc2U7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBmaW5hbCBzdGVwIHNlbmQgbWVldGluZyBpbnZpdGUnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHByb2Nlc3NTZW5kTWVldGluZ0ludml0ZVBlbmRpbmcgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBqc29uQm9keTogVXNlcklucHV0VG9KU09OVHlwZSxcbiAgZGF0ZUpTT05Cb2R5OiBEYXRlVGltZUpTT05UeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nLFxuICBmb3JtRGF0YTogUmVjZWl2ZXJUaW1lem9uZUZvcm1EYXRhUmVzcG9uc2VUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBtaXNzaW5nRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gICAgICByZXF1aXJlZDogW10sXG4gICAgICBkYXRlVGltZTogeyByZXF1aXJlZDogW10gfSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IGFueSA9IHtcbiAgICAgIHF1ZXJ5OiAnJyxcbiAgICAgIGRhdGE6IHt9LFxuICAgICAgc2tpbGw6ICdzZW5kTWVldGluZ0ludml0ZScsXG4gICAgfTtcblxuICAgIGxldCBkdXJhdGlvbiA9IDA7XG5cbiAgICBjb25zdCB5ZWFyU3RhcnQgPSBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/LnllYXI7XG4gICAgY29uc3QgbW9udGhTdGFydCA9IGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8ubW9udGg7XG4gICAgY29uc3QgZGF5U3RhcnQgPSBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/LmRheTtcbiAgICBjb25zdCBpc29XZWVrZGF5U3RhcnQgPSBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/Lmlzb1dlZWtkYXk7XG4gICAgY29uc3QgaG91clN0YXJ0ID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5ob3VyO1xuICAgIGNvbnN0IG1pbnV0ZVN0YXJ0ID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5taW51dGU7XG4gICAgY29uc3Qgc3RhcnRUaW1lU3RhcnQgPSBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/LnN0YXJ0VGltZTtcblxuICAgIGNvbnN0IHllYXJFbmQgPSBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy55ZWFyO1xuICAgIGNvbnN0IG1vbnRoRW5kID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8ubW9udGg7XG4gICAgY29uc3QgZGF5RW5kID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8uZGF5O1xuICAgIGNvbnN0IGlzb1dlZWtkYXlFbmQgPSBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5pc29XZWVrZGF5O1xuICAgIGNvbnN0IGhvdXJFbmQgPSBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5ob3VyO1xuICAgIGNvbnN0IG1pbnV0ZUVuZCA9IGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/Lm1pbnV0ZTtcbiAgICBjb25zdCBlbmRUaW1lRW5kID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8uc3RhcnRUaW1lO1xuXG4gICAgY29uc3Qgd2luZG93QnJhbmNoU3RhcnREYXRlID0gZXh0cmFwb2xhdGVTdGFydERhdGVGcm9tSlNPTkRhdGEoXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgeWVhclN0YXJ0LFxuICAgICAgbW9udGhTdGFydCxcbiAgICAgIGRheVN0YXJ0LFxuICAgICAgaXNvV2Vla2RheVN0YXJ0LFxuICAgICAgaG91clN0YXJ0LFxuICAgICAgbWludXRlU3RhcnQsXG4gICAgICBzdGFydFRpbWVTdGFydCxcbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICk7XG5cbiAgICBsZXQgd2luZG93U3RhcnREYXRlID0gd2luZG93QnJhbmNoU3RhcnREYXRlO1xuXG4gICAgaWYgKCF3aW5kb3dTdGFydERhdGUpIHtcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSA9IGRheWpzKCkuZm9ybWF0KCk7XG4gICAgfVxuXG4gICAgbGV0IHdpbmRvd0VuZERhdGUgPSBleHRyYXBvbGF0ZUVuZERhdGVGcm9tSlNPTkRhdGEoXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgeWVhckVuZCxcbiAgICAgIG1vbnRoRW5kLFxuICAgICAgZGF5RW5kLFxuICAgICAgaXNvV2Vla2RheUVuZCxcbiAgICAgIGhvdXJFbmQsXG4gICAgICBtaW51dGVFbmQsXG4gICAgICBlbmRUaW1lRW5kLFxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICApO1xuXG4gICAgaWYgKCF3aW5kb3dFbmREYXRlKSB7XG4gICAgICB3aW5kb3dFbmREYXRlID0gZGF5anMod2luZG93U3RhcnREYXRlKS5hZGQoMSwgJ3cnKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBjb25zdCBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzID1cbiAgICAgIGF3YWl0IGdldENoYXRNZWV0aW5nUHJlZmVyZW5jZUdpdmVuVXNlcklkKHVzZXJJZCk7XG5cbiAgICBpZiAoZGF0ZUpTT05Cb2R5Py5kdXJhdGlvbikge1xuICAgICAgZHVyYXRpb24gPSBkYXRlSlNPTkJvZHk/LmR1cmF0aW9uO1xuICAgIH0gZWxzZSBpZiAoZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uZHVyYXRpb24pIHtcbiAgICAgIGR1cmF0aW9uID0gZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uZHVyYXRpb247XG4gICAgfSBlbHNlIHtcbiAgICAgIGR1cmF0aW9uID0gMzA7XG4gICAgfVxuXG4gICAgY29uc3QgYm9keTogU2VuZE1lZXRpbmdJbnZpdGVUeXBlID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgdGltZXpvbmUsXG4gICAgICB0aXRsZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGl0bGUgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uc3VtbWFyeSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8uWzBdPy50YXNrLFxuICAgICAgYXR0ZW5kZWVzOiBqc29uQm9keT8ucGFyYW1zPy5hdHRlbmRlZXMsXG4gICAgICBtZXRob2Q6IGRhdGVKU09OQm9keT8ubWV0aG9kIGFzIGFueSxcbiAgICAgIGR1cmF0aW9uLFxuICAgICAgZGVzY3JpcHRpb246IGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8IGpzb25Cb2R5Py5wYXJhbXM/Lm5vdGVzLFxuICAgICAgY29uZmVyZW5jZUFwcDpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uY29uZmVyZW5jZT8uYXBwIHx8XG4gICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LmNvbmZlcmVuY2VBcHAsXG4gICAgICB3aW5kb3dTdGFydERhdGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSB8fCB3aW5kb3dTdGFydERhdGUgfHwgY3VycmVudFRpbWUsXG4gICAgICB3aW5kb3dFbmREYXRlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lIHx8XG4gICAgICAgIHdpbmRvd0VuZERhdGUgfHxcbiAgICAgICAgZGF5anMoY3VycmVudFRpbWUpLmFkZCg3LCAnZCcpLmZvcm1hdCgpLFxuICAgICAgcmVtaW5kZXJzOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5hbGFybXMgfHwgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ucmVtaW5kZXJzIHx8IFtdLFxuICAgICAgdHJhbnNwYXJlbmN5OiBqc29uQm9keT8ucGFyYW1zPy50cmFuc3BhcmVuY3ksXG4gICAgICB2aXNpYmlsaXR5OiBqc29uQm9keT8ucGFyYW1zLnZpc2liaWxpdHksXG4gICAgICByZWNlaXZlclRpbWV6b25lOiBmb3JtRGF0YT8udmFsdWUsXG4gICAgfTtcblxuICAgIGlmICghZm9ybURhdGE/LnZhbHVlKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLmRhdGVUaW1lLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlsyXSk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gYm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBpZiAoIWJvZHk/LnRpdGxlKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlswXSk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gYm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBpZiAoIShib2R5Py5hdHRlbmRlZXM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlsxXSk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gYm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBjb25zdCBuZXdBdHRlbmRlZXM6IE11dGF0ZWRDYWxlbmRhckV4dHJhY3RlZEpTT05BdHRlbmRlZVR5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBhIG9mIGJvZHk/LmF0dGVuZGVlcykge1xuICAgICAgaWYgKCFhPy5lbWFpbCkge1xuICAgICAgICBjb25zdCBjb250YWN0ID0gYXdhaXQgZ2V0Q29udGFjdEJ5TmFtZVdpdGhVc2VySWQoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIGAlJHthPy5uYW1lfSVgXG4gICAgICAgICk7XG4gICAgICAgIGlmIChjb250YWN0Py5lbWFpbHM/LlswXT8udmFsdWUpIHtcbiAgICAgICAgICBjb25zdCBwcmltYXJ5RW1haWwgPSBjb250YWN0Py5lbWFpbHM/LmZpbmQoKGUpID0+ICEhZS5wcmltYXJ5KT8udmFsdWU7XG4gICAgICAgICAgY29uc3QgYW55RW1haWwgPSBjb250YWN0Py5lbWFpbHM/LlswXT8udmFsdWU7XG4gICAgICAgICAgbmV3QXR0ZW5kZWVzLnB1c2goeyAuLi5hLCBlbWFpbDogcHJpbWFyeUVtYWlsIHx8IGFueUVtYWlsIH0pO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2goXG4gICAgICAgICAgICByZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzFdPy5bJ2FuZCddPy5bMl1cbiAgICAgICAgICApO1xuICAgICAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIG5ld0F0dGVuZGVlcy5wdXNoKGEpO1xuICAgICAgfVxuICAgIH1cblxuICAgIGJvZHkuYXR0ZW5kZWVzID0gbmV3QXR0ZW5kZWVzO1xuXG4gICAgY29uc3QgdXNlckNvbnRhY3RJbmZvcyA9IGF3YWl0IGxpc3RVc2VyQ29udGFjdEluZm9zR2l2ZW5Vc2VySWQodXNlcklkKTtcblxuICAgIGNvbnN0IHByb3ZpZGVkSG9zdEluZm8gPSBib2R5Py5hdHRlbmRlZXM/LmZpbmQoKGEpID0+IGE/LmlzSG9zdCA9PT0gdHJ1ZSk7XG5cbiAgICBjb25zdCBwcmltYXJ5SW5mb0l0ZW0gPSB1c2VyQ29udGFjdEluZm9zPy5maW5kKFxuICAgICAgKHUpID0+IHUucHJpbWFyeSAmJiB1LnR5cGUgPT09ICdlbWFpbCdcbiAgICApO1xuXG4gICAgY29uc3QgdXNlciA9IGF3YWl0IGdldFVzZXJHaXZlbklkKHVzZXJJZCk7XG5cbiAgICBjb25zdCBwcmltYXJ5SG9zdEF0dGVuZGVlSW5mbzogTXV0YXRlZENhbGVuZGFyRXh0cmFjdGVkSlNPTkF0dGVuZGVlVHlwZSA9IHtcbiAgICAgIG5hbWU6IHByaW1hcnlJbmZvSXRlbT8ubmFtZSB8fCB1c2VyPy5uYW1lLFxuICAgICAgZW1haWw6IHByaW1hcnlJbmZvSXRlbT8uaWQgfHwgdXNlcj8uZW1haWwsXG4gICAgICBpc0hvc3Q6IHRydWUsXG4gICAgfTtcblxuICAgIGlmICghcHJvdmlkZWRIb3N0SW5mbyAmJiBwcmltYXJ5SG9zdEF0dGVuZGVlSW5mbz8uZW1haWwpIHtcbiAgICAgIGJvZHk/LmF0dGVuZGVlcy5wdXNoKHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvKTtcbiAgICB9XG5cbiAgICBjb25zdCBob3N0SW5mbyA9IHByb3ZpZGVkSG9zdEluZm8gfHwgcHJpbWFyeUhvc3RBdHRlbmRlZUluZm87XG5cbiAgICBpZiAoIWhvc3RJbmZvPy5lbWFpbCkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZC5wdXNoKHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMV1bJ2FuZCddWzFdKTtcbiAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBib2R5O1xuICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgIH1cblxuICAgIGlmIChyZXNwb25zZS5xdWVyeSA9PT0gJ21pc3NpbmdfZmllbGRzJykge1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIGNvbnN0IHJlc3BvbnNlMiA9IGF3YWl0IGZpbmFsU3RlcFNlbmRNZWV0aW5nSW52aXRlKFxuICAgICAgYm9keSxcbiAgICAgIHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvLFxuICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcyxcbiAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgcmVzcG9uc2VcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlc3BvbnNlMjtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHByb2Nlc3Mgc2VuZCBtZWV0aW5nIGludml0ZScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc1NlbmRNZWV0aW5nSW52aXRlTWlzc2luZ0ZpZWxkc1JldHVybmVkID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAganNvbkJvZHk6IFVzZXJJbnB1dFRvSlNPTlR5cGUsXG4gIGRhdGVKU09OQm9keTogRGF0ZVRpbWVKU09OVHlwZSxcbiAgY3VycmVudFRpbWU6IHN0cmluZyxcbiAgZm9ybURhdGE6IFJlY2VpdmVyVGltZXpvbmVGb3JtRGF0YVJlc3BvbnNlVHlwZSxcbiAgbWVzc2FnZUhpc3RvcnlPYmplY3Q6IFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBtaXNzaW5nRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gICAgICByZXF1aXJlZDogW10sXG4gICAgICBkYXRlVGltZTogeyByZXF1aXJlZDogW10gfSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IGFueSA9IHtcbiAgICAgIHF1ZXJ5OiAnJyxcbiAgICAgIGRhdGE6IHt9LFxuICAgICAgc2tpbGw6ICdzZW5kTWVldGluZ0ludml0ZScsXG4gICAgfTtcblxuICAgIGxldCBkdXJhdGlvbiA9IDA7XG5cbiAgICBjb25zdCB5ZWFyU3RhcnQgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py55ZWFyIHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8ueWVhcjtcbiAgICBjb25zdCBtb250aFN0YXJ0ID1cbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8ubW9udGggfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5tb250aDtcbiAgICBjb25zdCBkYXlTdGFydCA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/LmRheSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/LmRheTtcbiAgICBjb25zdCBpc29XZWVrZGF5U3RhcnQgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5pc29XZWVrZGF5IHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8uaXNvV2Vla2RheTtcbiAgICBjb25zdCBob3VyU3RhcnQgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5ob3VyIHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8uaG91cjtcbiAgICBjb25zdCBtaW51dGVTdGFydCA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/Lm1pbnV0ZSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/Lm1pbnV0ZTtcbiAgICBjb25zdCBzdGFydFRpbWVTdGFydCA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/LnN0YXJ0VGltZSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/LnN0YXJ0VGltZTtcblxuICAgIGNvbnN0IHllYXJFbmQgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8ueWVhciB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy55ZWFyO1xuICAgIGNvbnN0IG1vbnRoRW5kID1cbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/Lm1vbnRoIHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/Lm1vbnRoO1xuICAgIGNvbnN0IGRheUVuZCA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5kYXkgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8uZGF5O1xuICAgIGNvbnN0IGlzb1dlZWtkYXlFbmQgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8uaXNvV2Vla2RheSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5pc29XZWVrZGF5O1xuICAgIGNvbnN0IGhvdXJFbmQgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8uaG91ciB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5ob3VyO1xuICAgIGNvbnN0IG1pbnV0ZUVuZCA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5taW51dGUgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8ubWludXRlO1xuICAgIGNvbnN0IGVuZFRpbWVFbmQgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8uc3RhcnRUaW1lIHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/LnN0YXJ0VGltZTtcblxuICAgIGNvbnN0IHdpbmRvd0JyYW5jaFN0YXJ0RGF0ZSA9IGV4dHJhcG9sYXRlU3RhcnREYXRlRnJvbUpTT05EYXRhKFxuICAgICAgY3VycmVudFRpbWUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHllYXJTdGFydCxcbiAgICAgIG1vbnRoU3RhcnQsXG4gICAgICBkYXlTdGFydCxcbiAgICAgIGlzb1dlZWtkYXlTdGFydCxcbiAgICAgIGhvdXJTdGFydCxcbiAgICAgIG1pbnV0ZVN0YXJ0LFxuICAgICAgc3RhcnRUaW1lU3RhcnQsXG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3cgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnRcbiAgICAgICAgICA/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/LnJlbGF0aXZlVGltZUZyb21Ob3cgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnRcbiAgICAgICAgICA/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICApO1xuXG4gICAgbGV0IHdpbmRvd1N0YXJ0RGF0ZSA9IHdpbmRvd0JyYW5jaFN0YXJ0RGF0ZTtcblxuICAgIGlmICghd2luZG93U3RhcnREYXRlKSB7XG4gICAgICB3aW5kb3dTdGFydERhdGUgPSBkYXlqcygpLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGxldCB3aW5kb3dFbmREYXRlID0gZXh0cmFwb2xhdGVFbmREYXRlRnJvbUpTT05EYXRhKFxuICAgICAgY3VycmVudFRpbWUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHllYXJFbmQsXG4gICAgICBtb250aEVuZCxcbiAgICAgIGRheUVuZCxcbiAgICAgIGlzb1dlZWtkYXlFbmQsXG4gICAgICBob3VyRW5kLFxuICAgICAgbWludXRlRW5kLFxuICAgICAgZW5kVGltZUVuZCxcbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3cgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93RW5kXG4gICAgICAgICAgPy5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93LFxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8ucmVsYXRpdmVUaW1lRnJvbU5vdyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dFbmRcbiAgICAgICAgICA/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICApO1xuXG4gICAgaWYgKCF3aW5kb3dFbmREYXRlKSB7XG4gICAgICB3aW5kb3dFbmREYXRlID0gZGF5anMod2luZG93U3RhcnREYXRlKS5hZGQoMSwgJ3cnKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBjb25zdCBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzID1cbiAgICAgIGF3YWl0IGdldENoYXRNZWV0aW5nUHJlZmVyZW5jZUdpdmVuVXNlcklkKHVzZXJJZCk7XG5cbiAgICBpZiAoZGF0ZUpTT05Cb2R5Py5kdXJhdGlvbikge1xuICAgICAgZHVyYXRpb24gPSBkYXRlSlNPTkJvZHk/LmR1cmF0aW9uO1xuICAgIH0gZWxzZSBpZiAoZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uZHVyYXRpb24pIHtcbiAgICAgIGR1cmF0aW9uID0gZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uZHVyYXRpb247XG4gICAgfSBlbHNlIHtcbiAgICAgIGR1cmF0aW9uID0gMzA7XG4gICAgfVxuXG4gICAgY29uc3QgbmV3Qm9keTogU2VuZE1lZXRpbmdJbnZpdGVUeXBlID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgdGltZXpvbmUsXG4gICAgICB0aXRsZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGl0bGUgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uc3VtbWFyeSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8uWzBdPy50YXNrIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udGl0bGUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8uWzBdPy50YXNrLFxuICAgICAgYXR0ZW5kZWVzOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5hdHRlbmRlZXMgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5hdHRlbmRlZXMsXG4gICAgICBtZXRob2Q6IGRhdGVKU09OQm9keT8ubWV0aG9kIGFzIGFueSxcbiAgICAgIGR1cmF0aW9uLFxuICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/Lm5vdGVzIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5ub3RlcyxcbiAgICAgIGNvbmZlcmVuY2VBcHA6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmNvbmZlcmVuY2U/LmFwcCB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmNvbmZlcmVuY2U/LmFwcCB8fFxuICAgICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5jb25mZXJlbmNlQXBwLFxuICAgICAgd2luZG93U3RhcnREYXRlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUgfHxcbiAgICAgICAgd2luZG93U3RhcnREYXRlIHx8XG4gICAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgd2luZG93RW5kRGF0ZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZW5kVGltZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmVuZFRpbWUgfHxcbiAgICAgICAgd2luZG93RW5kRGF0ZSB8fFxuICAgICAgICBkYXlqcyhjdXJyZW50VGltZSkuYWRkKDcsICdkJykuZm9ybWF0KCksXG4gICAgICByZW1pbmRlcnM6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmFsYXJtcyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmFsYXJtcyB8fFxuICAgICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5yZW1pbmRlcnMgfHxcbiAgICAgICAgW10sXG4gICAgICB0cmFuc3BhcmVuY3k6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRyYW5zcGFyZW5jeSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRyYW5zcGFyZW5jeSxcbiAgICAgIHZpc2liaWxpdHk6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXMudmlzaWJpbGl0eSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnZpc2liaWxpdHksXG4gICAgICByZWNlaXZlclRpbWV6b25lOiBmb3JtRGF0YT8udmFsdWUsXG4gICAgfTtcblxuICAgIGNvbnN0IHByZXZCb2R5OiBTZW5kTWVldGluZ0ludml0ZVR5cGUgPSB7XG4gICAgICAuLi5tZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGEsXG4gICAgfTtcblxuICAgIGlmICghcHJldkJvZHk/LnVzZXJJZCkge1xuICAgICAgcHJldkJvZHkudXNlcklkID0gdXNlcklkIHx8IG5ld0JvZHk/LnVzZXJJZDtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py50aW1lem9uZSkge1xuICAgICAgcHJldkJvZHkudGltZXpvbmUgPSB0aW1lem9uZSB8fCBuZXdCb2R5Py50aW1lem9uZTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py50aXRsZSkge1xuICAgICAgcHJldkJvZHkudGl0bGUgPSBuZXdCb2R5Py50aXRsZTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5kdXJhdGlvbikge1xuICAgICAgcHJldkJvZHkuZHVyYXRpb24gPSBuZXdCb2R5Py5kdXJhdGlvbjtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5kZXNjcmlwdGlvbikge1xuICAgICAgcHJldkJvZHkuZGVzY3JpcHRpb24gPSBuZXdCb2R5Py5kZXNjcmlwdGlvbjtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5jb25mZXJlbmNlQXBwKSB7XG4gICAgICBwcmV2Qm9keS5jb25mZXJlbmNlQXBwID0gbmV3Qm9keT8uY29uZmVyZW5jZUFwcDtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py53aW5kb3dTdGFydERhdGUpIHtcbiAgICAgIHByZXZCb2R5LndpbmRvd1N0YXJ0RGF0ZSA9IG5ld0JvZHk/LndpbmRvd1N0YXJ0RGF0ZTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py53aW5kb3dFbmREYXRlKSB7XG4gICAgICBwcmV2Qm9keS53aW5kb3dFbmREYXRlID0gbmV3Qm9keT8ud2luZG93RW5kRGF0ZTtcbiAgICB9XG5cbiAgICBpZiAoIShwcmV2Qm9keT8ucmVtaW5kZXJzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkucmVtaW5kZXJzID0gbmV3Qm9keT8ucmVtaW5kZXJzIHx8IFtdO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRyYW5zcGFyZW5jeSkge1xuICAgICAgcHJldkJvZHkudHJhbnNwYXJlbmN5ID0gbmV3Qm9keT8udHJhbnNwYXJlbmN5O1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnZpc2liaWxpdHkpIHtcbiAgICAgIHByZXZCb2R5LnZpc2liaWxpdHkgPSBuZXdCb2R5Py52aXNpYmlsaXR5O1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnJlY2VpdmVyVGltZXpvbmUpIHtcbiAgICAgIHByZXZCb2R5LnJlY2VpdmVyVGltZXpvbmUgPSBuZXdCb2R5Py5yZWNlaXZlclRpbWV6b25lO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRpdGxlKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlswXSk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gcHJldkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKCEocHJldkJvZHk/LmF0dGVuZGVlcz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzFdKTtcbiAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBjb25zdCBuZXdBdHRlbmRlZXM6IE11dGF0ZWRDYWxlbmRhckV4dHJhY3RlZEpTT05BdHRlbmRlZVR5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBhIG9mIG5ld0JvZHk/LmF0dGVuZGVlcykge1xuICAgICAgaWYgKCFhPy5lbWFpbCkge1xuICAgICAgICBjb25zdCBjb250YWN0ID0gYXdhaXQgZ2V0Q29udGFjdEJ5TmFtZVdpdGhVc2VySWQoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIGAlJHthPy5uYW1lfSVgXG4gICAgICAgICk7XG4gICAgICAgIGlmIChjb250YWN0Py5lbWFpbHM/LlswXT8udmFsdWUpIHtcbiAgICAgICAgICBjb25zdCBwcmltYXJ5RW1haWwgPSBjb250YWN0Py5lbWFpbHM/LmZpbmQoKGUpID0+ICEhZS5wcmltYXJ5KT8udmFsdWU7XG4gICAgICAgICAgY29uc3QgYW55RW1haWwgPSBjb250YWN0Py5lbWFpbHM/LlswXT8udmFsdWU7XG4gICAgICAgICAgbmV3QXR0ZW5kZWVzLnB1c2goeyAuLi5hLCBlbWFpbDogcHJpbWFyeUVtYWlsIHx8IGFueUVtYWlsIH0pO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2goXG4gICAgICAgICAgICByZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzFdPy5bJ2FuZCddPy5bMl1cbiAgICAgICAgICApO1xuICAgICAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gcHJldkJvZHk7XG4gICAgICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICAgICAgfVxuICAgICAgfSBlbHNlIHtcbiAgICAgICAgbmV3QXR0ZW5kZWVzLnB1c2goYSk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgbmV3Qm9keS5hdHRlbmRlZXMgPSBuZXdBdHRlbmRlZXM7XG5cbiAgICBpZiAoIShwcmV2Qm9keT8uYXR0ZW5kZWVzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkuYXR0ZW5kZWVzID0gbmV3Qm9keT8uYXR0ZW5kZWVzO1xuICAgIH1cblxuICAgIGNvbnN0IHVzZXJDb250YWN0SW5mb3MgPSBhd2FpdCBsaXN0VXNlckNvbnRhY3RJbmZvc0dpdmVuVXNlcklkKHVzZXJJZCk7XG5cbiAgICBjb25zdCBuZXdQcm92aWRlZEhvc3RJbmZvID0gbmV3Qm9keT8uYXR0ZW5kZWVzPy5maW5kKFxuICAgICAgKGEpID0+IGE/LmlzSG9zdCA9PT0gdHJ1ZVxuICAgICk7XG5cbiAgICBjb25zdCBwcmV2UHJvdmlkZWRIb3N0SW5mbyA9IHByZXZCb2R5Py5hdHRlbmRlZXM/LmZpbmQoXG4gICAgICAoYSkgPT4gYT8uaXNIb3N0ID09PSB0cnVlXG4gICAgKTtcblxuICAgIGNvbnN0IHByaW1hcnlJbmZvSXRlbSA9IHVzZXJDb250YWN0SW5mb3M/LmZpbmQoXG4gICAgICAodSkgPT4gdS5wcmltYXJ5ICYmIHUudHlwZSA9PT0gJ2VtYWlsJ1xuICAgICk7XG5cbiAgICBjb25zdCB1c2VyID0gYXdhaXQgZ2V0VXNlckdpdmVuSWQodXNlcklkKTtcblxuICAgIGNvbnN0IHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvOiBNdXRhdGVkQ2FsZW5kYXJFeHRyYWN0ZWRKU09OQXR0ZW5kZWVUeXBlID0ge1xuICAgICAgbmFtZTogcHJpbWFyeUluZm9JdGVtPy5uYW1lIHx8IHVzZXI/Lm5hbWUsXG4gICAgICBlbWFpbDogcHJpbWFyeUluZm9JdGVtPy5pZCB8fCB1c2VyPy5lbWFpbCxcbiAgICAgIGlzSG9zdDogdHJ1ZSxcbiAgICB9O1xuXG4gICAgaWYgKCFuZXdQcm92aWRlZEhvc3RJbmZvICYmIHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvPy5lbWFpbCkge1xuICAgICAgbmV3Qm9keT8uYXR0ZW5kZWVzLnB1c2gocHJpbWFyeUhvc3RBdHRlbmRlZUluZm8pO1xuICAgIH1cblxuICAgIGlmICghcHJldlByb3ZpZGVkSG9zdEluZm8gJiYgcHJpbWFyeUhvc3RBdHRlbmRlZUluZm8/LmVtYWlsKSB7XG4gICAgICBwcmV2Qm9keT8uYXR0ZW5kZWVzLnB1c2gocHJpbWFyeUhvc3RBdHRlbmRlZUluZm8pO1xuICAgIH1cblxuICAgIGNvbnN0IHByZXZIb3N0SW5mbyA9XG4gICAgICBwcmV2UHJvdmlkZWRIb3N0SW5mbyB8fCBuZXdQcm92aWRlZEhvc3RJbmZvIHx8IHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvO1xuXG4gICAgaWYgKCFwcmV2SG9zdEluZm8/LmVtYWlsKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlsxXVsnYW5kJ11bMV0pO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IHByZXZCb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnJlY2VpdmVyVGltZXpvbmUpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMuZGF0ZVRpbWUucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzJdKTtcbiAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keTtcbiAgICB9XG5cbiAgICBpZiAocmVzcG9uc2UucXVlcnkgPT09ICdtaXNzaW5nX2ZpZWxkcycpIHtcbiAgICAgIHJldHVybiByZXNwb25zZTtcbiAgICB9XG5cbiAgICBjb25zdCByZXNwb25zZTIgPSBhd2FpdCBmaW5hbFN0ZXBTZW5kTWVldGluZ0ludml0ZShcbiAgICAgIHByZXZCb2R5LFxuICAgICAgcHJldkhvc3RJbmZvLFxuICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcyxcbiAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgcmVzcG9uc2VcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlc3BvbnNlMjtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZSxcbiAgICAgICcgdW5hYmxlIHRvIHByb2Nlc3Mgc2VuZCBtZWVpdG5nIGludml0ZSBtaXNzaW5nIGZpZWxkcyByZXR1cm5lZCdcbiAgICApO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3Qgc2VuZE1lZXRpbmdJbnZpdGVDb250cm9sQ2VudGVyID0gYXN5bmMgKFxuICBvcGVuYWk6IE9wZW5BSSxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIG1lc3NhZ2VIaXN0b3J5T2JqZWN0OiBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZSxcbiAgdXNlckN1cnJlbnRUaW1lOiBzdHJpbmcsXG4gIHF1ZXJ5OiAnbWlzc2luZ19maWVsZHMnIHwgJ2NvbXBsZXRlZCcgfCAnZXZlbnRfbm90X2ZvdW5kJyB8ICdwZW5kaW5nJ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgbWVzc2FnZUxlbmd0aCA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzPy5sZW5ndGg7XG4gICAgbGV0IHVzZXJNZXNzYWdlID0gJyc7XG4gICAgZm9yIChsZXQgaSA9IG1lc3NhZ2VMZW5ndGg7IGkgPiAwOyBpLS0pIHtcbiAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlc1tpIC0gMV07XG5cbiAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICd1c2VyJykge1xuICAgICAgICB1c2VyTWVzc2FnZSA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgYnJlYWs7XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgdXNlcklucHV0ID0gdXNlck1lc3NhZ2U7XG5cbiAgICBsZXQgU01JUmVzOiBSZXNwb25zZUFjdGlvblR5cGUgPSB7XG4gICAgICBxdWVyeTogJ2NvbXBsZXRlZCcsXG4gICAgICBkYXRhOiAnJyxcbiAgICAgIHNraWxsOiAnJyxcbiAgICAgIHByZXZEYXRhOiB7fSxcbiAgICAgIHByZXZEYXRhRXh0cmE6IHt9LFxuICAgIH07XG5cbiAgICBzd2l0Y2ggKHF1ZXJ5KSB7XG4gICAgICBjYXNlICdwZW5kaW5nJzpcbiAgICAgICAgY29uc3QganNvbkJvZHkgPSBhd2FpdCBnZW5lcmF0ZUpTT05EYXRhRnJvbVVzZXJJbnB1dChcbiAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICk7XG4gICAgICAgIGNvbnN0IGRhdGVUaW1lID0gYXdhaXQgZ2VuZXJhdGVEYXRlVGltZShcbiAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lLFxuICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICk7XG4gICAgICAgIFNNSVJlcyA9IGF3YWl0IHByb2Nlc3NTZW5kTWVldGluZ0ludml0ZVBlbmRpbmcoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgIGpzb25Cb2R5LFxuICAgICAgICAgIGRhdGVUaW1lLFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZSxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8uZm9ybURhdGFcbiAgICAgICAgKTtcbiAgICAgICAgYnJlYWs7XG4gICAgICBjYXNlICdtaXNzaW5nX2ZpZWxkcyc6XG4gICAgICAgIGxldCBwcmlvclVzZXJJbnB1dCA9ICcnO1xuICAgICAgICBsZXQgcHJpb3JBc3Npc3RhbnRPdXRwdXQgPSAnJztcblxuICAgICAgICBmb3IgKGxldCBpID0gbWVzc2FnZUxlbmd0aDsgaSA+IDA7IGktLSkge1xuICAgICAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlc1tpIC0gMV07XG5cbiAgICAgICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAnYXNzaXN0YW50Jykge1xuICAgICAgICAgICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAndXNlcicpIHtcbiAgICAgICAgICAgIGlmIChtZXNzYWdlLmNvbnRlbnQgIT09IHVzZXJJbnB1dCkge1xuICAgICAgICAgICAgICBwcmlvclVzZXJJbnB1dCA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKCFwcmlvclVzZXJJbnB1dCB8fCAhcHJpb3JBc3Npc3RhbnRPdXRwdXQpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZyhwcmlvclVzZXJJbnB1dCwgJyBwcmlvclVzZXJJbnB1dCcpO1xuICAgICAgICAgIGNvbnNvbGUubG9nKHByaW9yQXNzaXN0YW50T3V0cHV0LCAnIHByaW9yQXNzaXN0YW50T3V0cHV0Jyk7XG4gICAgICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBwcmlvclVzZXJpbnB1dCBvciBwcmlvckFzc2lzdGFudE91dHB1dCcpO1xuICAgICAgICB9XG4gICAgICAgIGNvbnN0IGpzb25NaXNzaW5nRmllbGRzQm9keSA9XG4gICAgICAgICAgYXdhaXQgZ2VuZXJhdGVNaXNzaW5nRmllbGRzSlNPTkRhdGFGcm9tVXNlcklucHV0KFxuICAgICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgICAgcHJpb3JVc2VySW5wdXQsXG4gICAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCxcbiAgICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICAgICk7XG4gICAgICAgIGNvbnN0IGRhdGVNaXNzaW5nRmllbGRzVGltZSA9IGF3YWl0IGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0RhdGVUaW1lKFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICBwcmlvclVzZXJJbnB1dCxcbiAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgKTtcblxuICAgICAgICBTTUlSZXMgPSBhd2FpdCBwcm9jZXNzU2VuZE1lZXRpbmdJbnZpdGVNaXNzaW5nRmllbGRzUmV0dXJuZWQoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgIGpzb25NaXNzaW5nRmllbGRzQm9keSxcbiAgICAgICAgICBkYXRlTWlzc2luZ0ZpZWxkc1RpbWUsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5mb3JtRGF0YSxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdFxuICAgICAgICApO1xuICAgICAgICBicmVhaztcbiAgICB9XG5cbiAgICBpZiAoU01JUmVzPy5xdWVyeSA9PT0gJ2NvbXBsZXRlZCcpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2U6IEFzc2lzdGFudE1lc3NhZ2VUeXBlID0ge1xuICAgICAgICByb2xlOiAnYXNzaXN0YW50JyxcbiAgICAgICAgY29udGVudDogU01JUmVzPy5kYXRhIGFzIHN0cmluZyxcbiAgICAgIH07XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnY29tcGxldGVkJztcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnJlcXVpcmVkID0gbnVsbDtcbiAgICB9IGVsc2UgaWYgKFNNSVJlcz8ucXVlcnkgPT09ICdtaXNzaW5nX2ZpZWxkcycpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UgPVxuICAgICAgICBhd2FpdCBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VUb1JlcXVlc3RVc2VyRm9yTWlzc2luZ0ZpZWxkcyhcbiAgICAgICAgICBvcGVuYWksXG4gICAgICAgICAgU01JUmVzPy5kYXRhIGFzIFJlcXVpcmVkRmllbGRzVHlwZSxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdFxuICAgICAgICApO1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBTTUlSZXM/LmRhdGEgYXMgUmVxdWlyZWRGaWVsZHNUeXBlO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkRhdGEgPSBTTUlSZXM/LnByZXZEYXRhO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkRhdGFFeHRyYSA9IFNNSVJlcz8ucHJldkRhdGFFeHRyYTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRlSnNvbkJvZHkgPSBTTUlSZXM/LnByZXZEYXRlSnNvbkJvZHk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2SnNvbkJvZHkgPSBTTUlSZXM/LnByZXZKc29uQm9keTtcbiAgICB9IGVsc2UgaWYgKFNNSVJlcz8ucXVlcnkgPT09ICdldmVudF9ub3RfZm91bmQnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlOiBBc3Npc3RhbnRNZXNzYWdlVHlwZSA9IHtcbiAgICAgICAgcm9sZTogJ2Fzc2lzdGFudCcsXG4gICAgICAgIGNvbnRlbnQ6IFwiT29wcy4uLiBJIGNvdWxkbid0IGZpbmQgdGhlIGV2ZW50LiBTb3JyeSA6KFwiLFxuICAgICAgfTtcblxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXMucHVzaChhc3Npc3RhbnRNZXNzYWdlKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnF1ZXJ5ID0gJ2V2ZW50X25vdF9mb3VuZCc7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5yZXF1aXJlZCA9IG51bGw7XG4gICAgfVxuXG4gICAgcmV0dXJuIG1lc3NhZ2VIaXN0b3J5T2JqZWN0O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gc2VuZCBtZWV0aW5nIGludml0ZSBjb250cm9sIGNlbnRlciBwZW5kaW5nJyk7XG4gIH1cbn07XG4iXX0=