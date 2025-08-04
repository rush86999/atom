import requiredFields from './requiredFields';
import { callOpenAI, extrapolateEndDateFromJSONData, extrapolateStartDateFromJSONData, generateAssistantMessageToRequestUserForMissingFields, generateDateTime, generateJSONDataFromUserInput, generateMissingFieldsDateTime, generateMissingFieldsJSONDataFromUserInput, getCalendarIntegrationByName, getContactByNameWithUserId, getGlobalCalendar, getUserGivenId, listUserContactInfosGivenUserId, } from '@chat/_libs/api-helper';
import { getChatMeetingPreferenceGivenUserId } from '../scheduleMeeting/api-helper';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import { atomicCalendarSubdomainUrl, defaultOpenAIAPIKey, googleCalendarName, openAIChatGPT35LongModel, openAIChatGPT35Model, replyToAddress, } from '@chat/_libs/constants';
import { meetingRequestSubjectPrompt, meetingRequestWithAvailabilityPrompt, } from './prompts';
import OpenAI from 'openai';
import qs from 'qs';
import { generateAvailabilityForUser } from '@chat/_libs/skills/askCalendar/askAvailability/api-helper';
import _ from 'lodash';
import { summarizeAvailabilityPrompt, summarizeAvailabilityExampleInput, summarizeAvailabilityExampleOutput, } from '@chat/_libs/skills/askCalendar/askAvailability/prompts';
import { process_day_availibility, process_summarize_availability, } from '@/gpt-meeting/_libs/api-helper';
import { sendEmail } from '@/_utils/email/email';
import { ENV } from '@/_utils/env';
export const day_availability_summary = async (dayAvailabilityObject) => {
    try {
        const response = await process_day_availibility(dayAvailabilityObject);
        console.log(response, ' response');
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
export const finalStepGenerateMeetingInvite = async (body, primaryHostAttendeeInfo, defaultMeetingPreferences, currentTime, response) => {
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
                openAIAvailabilityRes += '\n\n' + miniOpenAIAvailabilityRes;
            }
        }
        const meetingInvitePrompt = meetingRequestWithAvailabilityPrompt;
        const meetingInviteUserData = `${body?.title} \n ${body?.description}`;
        let meetingInviteOpenAIRes = await callOpenAI(openai, meetingInvitePrompt, openAIChatGPT35Model, meetingInviteUserData);
        if (!meetingInviteOpenAIRes) {
            throw new Error('no openAIRes present inside appointmentRequest');
        }
        meetingInviteOpenAIRes += '\n' + openAIAvailabilityRes;
        const meetingQueryParams = {
            userId: body?.userId,
            timezone: body?.timezone,
            enableConference: !!body?.conferenceApp ? 'true' : 'false',
            conferenceApp: body?.conferenceApp,
            useDefaultAlarms: body?.reminders?.length > 0 ? 'false' : 'true',
            reminders: body?.reminders?.map((n) => `${n}`),
            attendeeEmails: body?.attendees?.map((a) => a?.email),
            duration: body?.duration
                ? `${body?.duration}`
                : `${defaultMeetingPreferences?.duration || 30}`,
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
        console.log(meetingQueryParams, ' meetingQueryParams');
        const calendarLink = atomicCalendarSubdomainUrl + '?' + qs.stringify(meetingQueryParams);
        const calendarLinkMessage = `You can quickly schedule a meeting by clicking \"Reply All\" with your time to send me a copy and let me take care of the heavy work. \n - Atom, an AI assistant from <a href=\"${calendarLink}\">Atomic</a> :)`;
        meetingInviteOpenAIRes += '\n\n' + calendarLinkMessage;
        const emailSubjectPrompt = meetingRequestSubjectPrompt;
        const emailSubjectUserData = meetingInviteOpenAIRes;
        const emailSubjectInviteOpenAIRes = await callOpenAI(openai, emailSubjectPrompt, openAIChatGPT35Model, emailSubjectUserData);
        response.query = 'completed';
        const responseMessage = `
            Your meeting invite message is ready! :) \n
        `;
        response.data = responseMessage;
        response.htmlEmail = `
            <div>
                <p>To: ${body?.attendees?.filter((a) => !a?.isHost)?.[0]?.email}, ${replyToAddress}</p>
                <p>Subject: ${emailSubjectInviteOpenAIRes}</p>
                <pre style="font-family:sans-serif;">${meetingInviteOpenAIRes}</pre>
            </div>
    `;
        return response;
    }
    catch (e) {
        console.log(e, ' unable to final step generate meeting invite');
    }
};
export const processGenerateMeetingInvitePending = async (userId, timezone, jsonBody, dateJSONBody, currentTime, formData) => {
    try {
        const missingFields = {
            required: [],
            dateTime: { required: [] },
        };
        const response = {
            query: '',
            data: {},
            skill: 'generateMeetingInvite',
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
            reminders: jsonBody?.params?.alarms || defaultMeetingPreferences?.reminders,
            transparency: jsonBody?.params?.transparency,
            visibility: jsonBody?.params.visibility,
            receiverTimezone: formData?.value,
        };
        console.log(body, ' body');
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
                    response.prevData = body;
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
        if (!formData?.value) {
            response.query = 'missing_fields';
            missingFields.dateTime.required.push(requiredFields.required?.[2]);
            response.data = missingFields;
            response.prevData = body;
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepGenerateMeetingInvite(body, hostInfo, defaultMeetingPreferences, currentTime, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process send meeting invite');
    }
};
export const processGenerateMeetingInviteMissingFieldsReturned = async (userId, timezone, jsonBody, dateJSONBody, currentTime, formData, messageHistoryObject) => {
    try {
        const missingFields = {
            required: [],
            dateTime: { required: [] },
        };
        const response = {
            query: '',
            data: {},
            skill: 'generateMeetingInvite',
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
                defaultMeetingPreferences?.reminders,
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
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepGenerateMeetingInvite(prevBody, prevHostInfo, defaultMeetingPreferences, currentTime, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to generate meeting invite missing fields returned');
    }
};
export const generateMeetingInviteControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
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
        let GMIRes = {
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
                GMIRes = await processGenerateMeetingInvitePending(userId, timezone, jsonBody, dateTime, userCurrentTime, messageHistoryObject?.formData);
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
                GMIRes = await processGenerateMeetingInviteMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, dateMissingFieldsTime, userCurrentTime, messageHistoryObject?.formData, messageHistoryObject);
                break;
        }
        if (GMIRes?.query === 'completed') {
            const assistantMessage = {
                role: 'assistant',
                content: GMIRes?.data,
            };
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
            messageHistoryObject.htmlEmail = GMIRes.htmlEmail;
        }
        else if (GMIRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, GMIRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required = GMIRes?.data;
            messageHistoryObject.prevData = GMIRes?.prevData;
            messageHistoryObject.prevDataExtra = GMIRes?.prevDataExtra;
            messageHistoryObject.prevDateJsonBody = GMIRes?.prevDateJsonBody;
            messageHistoryObject.prevJsonBody = GMIRes?.prevJsonBody;
        }
        else if (GMIRes?.query === 'event_not_found') {
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
        console.log(e, ' unable to generate meeting invite control center pending');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBVUEsT0FBTyxjQUFjLE1BQU0sa0JBQWtCLENBQUM7QUFDOUMsT0FBTyxFQUNMLFVBQVUsRUFDViw4QkFBOEIsRUFDOUIsZ0NBQWdDLEVBRWhDLHFEQUFxRCxFQUNyRCxnQkFBZ0IsRUFDaEIsNkJBQTZCLEVBQzdCLDZCQUE2QixFQUM3QiwwQ0FBMEMsRUFDMUMsNEJBQTRCLEVBQzVCLDBCQUEwQixFQUMxQixpQkFBaUIsRUFDakIsY0FBYyxFQUNkLCtCQUErQixHQUNoQyxNQUFNLHdCQUF3QixDQUFDO0FBQ2hDLE9BQU8sRUFBRSxtQ0FBbUMsRUFBRSxNQUFNLCtCQUErQixDQUFDO0FBQ3BGLE9BQU8sRUFBRSxLQUFLLEVBQUUsTUFBTSxpQ0FBaUMsQ0FBQztBQUN4RCxPQUFPLEVBQ0wsMEJBQTBCLEVBQzFCLG1CQUFtQixFQUNuQixrQkFBa0IsRUFFbEIsd0JBQXdCLEVBQ3hCLG9CQUFvQixFQUNwQixjQUFjLEdBQ2YsTUFBTSx1QkFBdUIsQ0FBQztBQVMvQixPQUFPLEVBQ0wsMkJBQTJCLEVBQzNCLG9DQUFvQyxHQUNyQyxNQUFNLFdBQVcsQ0FBQztBQUNuQixPQUFPLE1BQU0sTUFBTSxRQUFRLENBQUM7QUFDNUIsT0FBTyxFQUFFLE1BQU0sSUFBSSxDQUFDO0FBT3BCLE9BQU8sRUFBRSwyQkFBMkIsRUFBRSxNQUFNLDJEQUEyRCxDQUFDO0FBQ3hHLE9BQU8sQ0FBQyxNQUFNLFFBQVEsQ0FBQztBQUN2QixPQUFPLEVBQ0wsMkJBQTJCLEVBQzNCLGlDQUFpQyxFQUNqQyxrQ0FBa0MsR0FJbkMsTUFBTSx3REFBd0QsQ0FBQztBQUNoRSxPQUFPLEVBQ0wsd0JBQXdCLEVBQ3hCLDhCQUE4QixHQUMvQixNQUFNLGdDQUFnQyxDQUFDO0FBQ3hDLE9BQU8sRUFBRSxTQUFTLEVBQUUsTUFBTSxzQkFBc0IsQ0FBQztBQUNq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LElBQUksQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO1lBQ3JELG9CQUFvQixDQUFDLEtBQUssR0FBRyxpQkFBaUIsQ0FBQztZQUMvQyxvQkFBb0IsQ0FBQyxRQUFRLEdBQUcsSUFBSSxDQUFDO1FBQ3ZDLENBQUM7UUFFRCxPQUFPLG9CQUFvQixDQUFDO0lBQzlCLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsMkRBQTJELENBQUMsQ0FBQztJQUM5RSxDQUFDO0FBQ0gsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IERhdGVUaW1lSlNPTlR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvZGF0ZXRpbWUvRGF0ZVRpbWVKU09OSlNPTlR5cGUnO1xuaW1wb3J0IFVzZXJJbnB1dFRvSlNPTlR5cGUsIHtcbiAgTXV0YXRlZENhbGVuZGFyRXh0cmFjdGVkSlNPTkF0dGVuZGVlVHlwZSxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvVXNlcklucHV0VG9KU09OVHlwZSc7XG5pbXBvcnQge1xuICBNZWV0aW5nVXJsUXVlcnlQYXJhbXNUeXBlLFxuICBSZWNlaXZlclRpbWV6b25lRm9ybURhdGFSZXNwb25zZVR5cGUsXG4gIEdlbmVyYXRlTWVldGluZ0ludml0ZVR5cGUsXG59IGZyb20gJy4vdHlwZXMnO1xuaW1wb3J0IFJlcXVpcmVkRmllbGRzVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9SZXF1aXJlZEZpZWxkc1R5cGUnO1xuaW1wb3J0IHJlcXVpcmVkRmllbGRzIGZyb20gJy4vcmVxdWlyZWRGaWVsZHMnO1xuaW1wb3J0IHtcbiAgY2FsbE9wZW5BSSxcbiAgZXh0cmFwb2xhdGVFbmREYXRlRnJvbUpTT05EYXRhLFxuICBleHRyYXBvbGF0ZVN0YXJ0RGF0ZUZyb21KU09ORGF0YSxcbiAgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlRnJvbUFQSVJlc3BvbnNlRm9yVXNlclF1ZXJ5LFxuICBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VUb1JlcXVlc3RVc2VyRm9yTWlzc2luZ0ZpZWxkcyxcbiAgZ2VuZXJhdGVEYXRlVGltZSxcbiAgZ2VuZXJhdGVKU09ORGF0YUZyb21Vc2VySW5wdXQsXG4gIGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0RhdGVUaW1lLFxuICBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNKU09ORGF0YUZyb21Vc2VySW5wdXQsXG4gIGdldENhbGVuZGFySW50ZWdyYXRpb25CeU5hbWUsXG4gIGdldENvbnRhY3RCeU5hbWVXaXRoVXNlcklkLFxuICBnZXRHbG9iYWxDYWxlbmRhcixcbiAgZ2V0VXNlckdpdmVuSWQsXG4gIGxpc3RVc2VyQ29udGFjdEluZm9zR2l2ZW5Vc2VySWQsXG59IGZyb20gJ0BjaGF0L19saWJzL2FwaS1oZWxwZXInO1xuaW1wb3J0IHsgZ2V0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlR2l2ZW5Vc2VySWQgfSBmcm9tICcuLi9zY2hlZHVsZU1lZXRpbmcvYXBpLWhlbHBlcic7XG5pbXBvcnQgeyBkYXlqcyB9IGZyb20gJ0BjaGF0L19saWJzL2RhdGV0aW1lL2RhdGUtdXRpbHMnO1xuaW1wb3J0IHtcbiAgYXRvbWljQ2FsZW5kYXJTdWJkb21haW5VcmwsXG4gIGRlZmF1bHRPcGVuQUlBUElLZXksXG4gIGdvb2dsZUNhbGVuZGFyTmFtZSxcbiAgbm9SZXBseUFkZHJlc3MsXG4gIG9wZW5BSUNoYXRHUFQzNUxvbmdNb2RlbCxcbiAgb3BlbkFJQ2hhdEdQVDM1TW9kZWwsXG4gIHJlcGx5VG9BZGRyZXNzLFxufSBmcm9tICdAY2hhdC9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IHtcbiAgRGF5QXZhaWxhYmlsaXR5VHlwZSxcbiAgU3VtbWFyaXplRGF5QXZhaWxhYmlsaXR5VHlwZSxcbn0gZnJvbSAnLi9hdmFpbGFiaWxpdHlUeXBlcyc7XG5pbXBvcnQge1xuICBkYXRlQXZhaWxhYmlsaXR5RnVuY3Rpb25OYW1lLFxuICBzdW1tYXJpemVBdmFpbGFiaWxpdHlGdW5jdGlvbk5hbWUsXG59IGZyb20gJy4vY29uc3RhbnRzJztcbmltcG9ydCB7XG4gIG1lZXRpbmdSZXF1ZXN0U3ViamVjdFByb21wdCxcbiAgbWVldGluZ1JlcXVlc3RXaXRoQXZhaWxhYmlsaXR5UHJvbXB0LFxufSBmcm9tICcuL3Byb21wdHMnO1xuaW1wb3J0IE9wZW5BSSBmcm9tICdvcGVuYWknO1xuaW1wb3J0IHFzIGZyb20gJ3FzJztcbmltcG9ydCB7XG4gIEFzc2lzdGFudE1lc3NhZ2VUeXBlLFxuICBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZSxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvTWVzc2FnaW5nL01lc3NhZ2luZ1R5cGVzJztcbmltcG9ydCB7IENoYXRNZWV0aW5nUHJlZmVyZW5jZXNUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvQ2hhdE1lZXRpbmdQcmVmZXJlbmNlc1R5cGUnO1xuaW1wb3J0IFJlc3BvbnNlQWN0aW9uVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9SZXNwb25zZUFjdGlvblR5cGUnO1xuaW1wb3J0IHsgZ2VuZXJhdGVBdmFpbGFiaWxpdHlGb3JVc2VyIH0gZnJvbSAnQGNoYXQvX2xpYnMvc2tpbGxzL2Fza0NhbGVuZGFyL2Fza0F2YWlsYWJpbGl0eS9hcGktaGVscGVyJztcbmltcG9ydCBfIGZyb20gJ2xvZGFzaCc7XG5pbXBvcnQge1xuICBzdW1tYXJpemVBdmFpbGFiaWxpdHlQcm9tcHQsXG4gIHN1bW1hcml6ZUF2YWlsYWJpbGl0eUV4YW1wbGVJbnB1dCxcbiAgc3VtbWFyaXplQXZhaWxhYmlsaXR5RXhhbXBsZU91dHB1dCxcbiAgc3VtbWFyaXplQXZhaWxhYmlsaXR5UmVzcG9uc2VzUHJvbXB0LFxuICBzdW1tYXJpemVBdmFpbGFiaWxpdHlSZXNwb25zZXNQcm9tcHRFeGFtcGxlSW5wdXQsXG4gIHN1bW1hcml6ZUF2YWlsYWJpbGl0eVJlc3BvbnNlc1Byb21wdEV4YW1wbGVPdXRwdXQsXG59IGZyb20gJ0BjaGF0L19saWJzL3NraWxscy9hc2tDYWxlbmRhci9hc2tBdmFpbGFiaWxpdHkvcHJvbXB0cyc7XG5pbXBvcnQge1xuICBwcm9jZXNzX2RheV9hdmFpbGliaWxpdHksXG4gIHByb2Nlc3Nfc3VtbWFyaXplX2F2YWlsYWJpbGl0eSxcbn0gZnJvbSAnQC9ncHQtbWVldGluZy9fbGlicy9hcGktaGVscGVyJztcbmltcG9ydCB7IHNlbmRFbWFpbCB9IGZyb20gJ0AvX3V0aWxzL2VtYWlsL2VtYWlsJztcbmltcG9ydCB7IEVOViB9IGZyb20gJ0AvX3V0aWxzL2Vudic7XG5cbmV4cG9ydCBjb25zdCBkYXlfYXZhaWxhYmlsaXR5X3N1bW1hcnkgPSBhc3luYyAoXG4gIGRheUF2YWlsYWJpbGl0eU9iamVjdDogRGF5QXZhaWxhYmlsaXR5VHlwZVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBwcm9jZXNzX2RheV9hdmFpbGliaWxpdHkoZGF5QXZhaWxhYmlsaXR5T2JqZWN0KTtcblxuICAgIGNvbnNvbGUubG9nKHJlc3BvbnNlLCAnIHJlc3BvbnNlJyk7XG4gICAgcmV0dXJuIHJlc3BvbnNlO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGRheSBhdmFpbGFiaWxpdHkgc3VtbWFyeScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3Qgc3VtbWFyaXplX2F2YWlsYWJpbGl0eSA9IGFzeW5jIChcbiAgc3VtbWFyaXplQXZhaWxhYmlsaXR5T2JqZWN0OiBTdW1tYXJpemVEYXlBdmFpbGFiaWxpdHlUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IHByb2Nlc3Nfc3VtbWFyaXplX2F2YWlsYWJpbGl0eShcbiAgICAgIHN1bW1hcml6ZUF2YWlsYWJpbGl0eU9iamVjdFxuICAgICk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXNwb25zZSwgJyByZXNwb25zZScpO1xuICAgIHJldHVybiByZXNwb25zZTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgZXJyb3IgaW4gc3VtbWFyaXplX2F2YWlsYWJpbGl0eScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3Qgc2VuZE1lZXRpbmdSZXF1ZXN0VGVtcGxhdGUgPSBhc3luYyAoXG4gIG5hbWU6IHN0cmluZyxcbiAgZW1haWw6IHN0cmluZyxcbiAgYm9keTogc3RyaW5nLFxuICBzdWJqZWN0OiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHRlbXBsYXRlID0gJ21lZXRpbmctcmVxdWVzdC10ZW1wbGF0ZSc7XG5cbiAgICBhd2FpdCBzZW5kRW1haWwoe1xuICAgICAgdGVtcGxhdGUsXG4gICAgICBsb2NhbHM6IHtcbiAgICAgICAgbmFtZSxcbiAgICAgICAgYm9keSxcbiAgICAgICAgZGlzcGxheU5hbWU6IG5hbWUsXG4gICAgICAgIGVtYWlsLFxuICAgICAgICBsb2NhbGU6IEVOVi5BVVRIX0xPQ0FMRV9ERUZBVUxULFxuICAgICAgICBzZXJ2ZXJVcmw6IEVOVi5GVU5DVElPTl9TRVJWRVJfVVJMLFxuICAgICAgICBjbGllbnRVcmw6IEVOVi5BUFBfQ0xJRU5UX1VSTCxcbiAgICAgIH0sXG4gICAgICBtZXNzYWdlOiB7XG4gICAgICAgIHRvOiBlbWFpbCxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICd4LWVtYWlsLXRlbXBsYXRlJzoge1xuICAgICAgICAgICAgcHJlcGFyZWQ6IHRydWUsXG4gICAgICAgICAgICB2YWx1ZTogdGVtcGxhdGUsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgfSk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBzZW5kIG1lZXRpbmcgcmVxdWVzdCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZmluYWxTdGVwR2VuZXJhdGVNZWV0aW5nSW52aXRlID0gYXN5bmMgKFxuICBib2R5OiBHZW5lcmF0ZU1lZXRpbmdJbnZpdGVUeXBlLFxuICBwcmltYXJ5SG9zdEF0dGVuZGVlSW5mbzogTXV0YXRlZENhbGVuZGFyRXh0cmFjdGVkSlNPTkF0dGVuZGVlVHlwZSxcbiAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlczogQ2hhdE1lZXRpbmdQcmVmZXJlbmNlc1R5cGUsXG4gIGN1cnJlbnRUaW1lOiBzdHJpbmcsXG4gIHJlc3BvbnNlOiBhbnlcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHByaW1hcnlDYWxlbmRhciA9IGF3YWl0IGdldEdsb2JhbENhbGVuZGFyKGJvZHk/LnVzZXJJZCk7XG5cbiAgICBpZiAoIXByaW1hcnlDYWxlbmRhcj8uaWQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gcHJpbWFyeSBjYWxlbmRhciBmb3VuZCBpbnNpZGUgY3JlYXRlQWdlbmRhJyk7XG4gICAgfVxuXG4gICAgY29uc3QgY2FsSW50ZWdyYXRpb24gPSBhd2FpdCBnZXRDYWxlbmRhckludGVncmF0aW9uQnlOYW1lKFxuICAgICAgYm9keT8udXNlcklkLFxuICAgICAgZ29vZ2xlQ2FsZW5kYXJOYW1lXG4gICAgKTtcblxuICAgIGlmICghY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgJ25vIGNsaWVudCB0eXBlIGluc2lkZSBjYWxlbmRhciBpbnRlZ3JhdGlvbiBpbnNpZGUgY3JlYXRlIGFnZW5kYSdcbiAgICAgICk7XG4gICAgfVxuXG4gICAgY29uc3Qgb3BlbmFpID0gbmV3IE9wZW5BSSh7XG4gICAgICBhcGlLZXk6IGRlZmF1bHRPcGVuQUlBUElLZXksXG4gICAgfSk7XG5cbiAgICBjb25zdCBhdmFpbGFibGVTbG90cyA9IGF3YWl0IGdlbmVyYXRlQXZhaWxhYmlsaXR5Rm9yVXNlcihcbiAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgIGJvZHk/LndpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIGJvZHk/LndpbmRvd0VuZERhdGUsXG4gICAgICBib2R5Py5yZWNlaXZlclRpbWV6b25lLFxuICAgICAgYm9keT8uZHVyYXRpb24gfHwgMzBcbiAgICApO1xuXG4gICAgY29uc3QgdW5pcURhdGVzID0gXy51bmlxQnkoYXZhaWxhYmxlU2xvdHMsIChjdXJyKSA9PlxuICAgICAgZGF5anMoY3Vycj8uc3RhcnREYXRlPy5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihib2R5Py5yZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREJylcbiAgICApO1xuXG4gICAgY29uc3QgcHJvbXB0ID0gc3VtbWFyaXplQXZhaWxhYmlsaXR5UHJvbXB0O1xuXG4gICAgY29uc3QgZXhhbXBsZUlucHV0ID0gc3VtbWFyaXplQXZhaWxhYmlsaXR5RXhhbXBsZUlucHV0O1xuXG4gICAgY29uc3QgZXhhbXBsZU91dHB1dCA9IHN1bW1hcml6ZUF2YWlsYWJpbGl0eUV4YW1wbGVPdXRwdXQ7XG5cbiAgICBsZXQgb3BlbkFJQXZhaWxhYmlsaXR5UmVzID0gJyc7XG5cbiAgICBmb3IgKGNvbnN0IHVuaXFEYXRlIG9mIHVuaXFEYXRlcykge1xuICAgICAgY29uc3QgZmlsdGVyZWRBdmFpbGFiaWxpdHkgPSBhdmFpbGFibGVTbG90cz8uZmlsdGVyKFxuICAgICAgICAoYSkgPT5cbiAgICAgICAgICBkYXlqcyhhPy5zdGFydERhdGUpXG4gICAgICAgICAgICAudHooYm9keT8ucmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tREQnKSA9PT1cbiAgICAgICAgICBkYXlqcyh1bmlxRGF0ZT8uc3RhcnREYXRlKVxuICAgICAgICAgICAgLnR6KGJvZHk/LnJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREJylcbiAgICAgICk7XG5cbiAgICAgIGlmIChmaWx0ZXJlZEF2YWlsYWJpbGl0eT8ubGVuZ3RoID4gMCkge1xuICAgICAgICBjb25zdCBtaW5pQXZhaWxhYmlsaXR5VGV4dCA9XG4gICAgICAgICAgYCR7ZGF5anModW5pcURhdGU/LnN0YXJ0RGF0ZSkudHooYm9keT8ucmVjZWl2ZXJUaW1lem9uZSkuZm9ybWF0KCdMJyl9IC0gJHtmaWx0ZXJlZEF2YWlsYWJpbGl0eT8ubWFwKChjdXJyKSA9PiBgJHtkYXlqcyhjdXJyPy5zdGFydERhdGUpLnR6KGJvZHk/LnJlY2VpdmVyVGltZXpvbmUpLmZvcm1hdCgnTFQnKX0gLSAke2RheWpzKGN1cnI/LmVuZERhdGUpLnR6KGJvZHk/LnJlY2VpdmVyVGltZXpvbmUpLmZvcm1hdCgnTFQnKX0sYCk/LnJlZHVjZSgocHJldiwgY3VycikgPT4gYCR7cHJldn0gJHtjdXJyfWAsICcnKX1gICtcbiAgICAgICAgICAnXFxuXFxuJztcblxuICAgICAgICBjb25zdCBtaW5pVXNlckRhdGEgPSBgTXkgYXZhaWxhYmlsaXR5OiBgICsgbWluaUF2YWlsYWJpbGl0eVRleHQ7XG5cbiAgICAgICAgY29uc29sZS5sb2cobWluaVVzZXJEYXRhLCAnIG5ld0F2YWlsYWJpbGl0eVByb21wdCcpO1xuXG4gICAgICAgIGNvbnN0IG1pbmlPcGVuQUlBdmFpbGFiaWxpdHlSZXMgPSBhd2FpdCBjYWxsT3BlbkFJKFxuICAgICAgICAgIG9wZW5haSxcbiAgICAgICAgICBwcm9tcHQsXG4gICAgICAgICAgb3BlbkFJQ2hhdEdQVDM1TG9uZ01vZGVsLFxuICAgICAgICAgIG1pbmlVc2VyRGF0YSxcbiAgICAgICAgICBleGFtcGxlSW5wdXQsXG4gICAgICAgICAgZXhhbXBsZU91dHB1dFxuICAgICAgICApO1xuXG4gICAgICAgIGlmICghbWluaU9wZW5BSUF2YWlsYWJpbGl0eVJlcykge1xuICAgICAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgICAgICdubyBvcGVuQUlBdmFpbGFiaWxpdHlSZXMgcHJlc2VudCBpbnNpZGUgYXBwb2ludG1lbnRSZXF1ZXN0J1xuICAgICAgICAgICk7XG4gICAgICAgIH1cblxuICAgICAgICBvcGVuQUlBdmFpbGFiaWxpdHlSZXMgKz0gJ1xcblxcbicgKyBtaW5pT3BlbkFJQXZhaWxhYmlsaXR5UmVzO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IG1lZXRpbmdJbnZpdGVQcm9tcHQgPSBtZWV0aW5nUmVxdWVzdFdpdGhBdmFpbGFiaWxpdHlQcm9tcHQ7XG5cbiAgICBjb25zdCBtZWV0aW5nSW52aXRlVXNlckRhdGEgPSBgJHtib2R5Py50aXRsZX0gXFxuICR7Ym9keT8uZGVzY3JpcHRpb259YDtcblxuICAgIGxldCBtZWV0aW5nSW52aXRlT3BlbkFJUmVzID0gYXdhaXQgY2FsbE9wZW5BSShcbiAgICAgIG9wZW5haSxcbiAgICAgIG1lZXRpbmdJbnZpdGVQcm9tcHQsXG4gICAgICBvcGVuQUlDaGF0R1BUMzVNb2RlbCxcbiAgICAgIG1lZXRpbmdJbnZpdGVVc2VyRGF0YVxuICAgICk7XG5cbiAgICBpZiAoIW1lZXRpbmdJbnZpdGVPcGVuQUlSZXMpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gb3BlbkFJUmVzIHByZXNlbnQgaW5zaWRlIGFwcG9pbnRtZW50UmVxdWVzdCcpO1xuICAgIH1cblxuICAgIG1lZXRpbmdJbnZpdGVPcGVuQUlSZXMgKz0gJ1xcbicgKyBvcGVuQUlBdmFpbGFiaWxpdHlSZXM7XG5cbiAgICBjb25zdCBtZWV0aW5nUXVlcnlQYXJhbXM6IE1lZXRpbmdVcmxRdWVyeVBhcmFtc1R5cGUgPSB7XG4gICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgIHRpbWV6b25lOiBib2R5Py50aW1lem9uZSxcbiAgICAgIGVuYWJsZUNvbmZlcmVuY2U6ICEhYm9keT8uY29uZmVyZW5jZUFwcCA/ICd0cnVlJyA6ICdmYWxzZScsXG4gICAgICBjb25mZXJlbmNlQXBwOiBib2R5Py5jb25mZXJlbmNlQXBwLFxuICAgICAgdXNlRGVmYXVsdEFsYXJtczogYm9keT8ucmVtaW5kZXJzPy5sZW5ndGggPiAwID8gJ2ZhbHNlJyA6ICd0cnVlJyxcbiAgICAgIHJlbWluZGVyczogYm9keT8ucmVtaW5kZXJzPy5tYXAoKG4pID0+IGAke259YCksXG4gICAgICBhdHRlbmRlZUVtYWlsczogYm9keT8uYXR0ZW5kZWVzPy5tYXAoKGEpID0+IGE/LmVtYWlsKSxcbiAgICAgIGR1cmF0aW9uOiBib2R5Py5kdXJhdGlvblxuICAgICAgICA/IGAke2JvZHk/LmR1cmF0aW9ufWBcbiAgICAgICAgOiBgJHtkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5kdXJhdGlvbiB8fCAzMH1gLFxuICAgICAgY2FsZW5kYXJJZDogcHJpbWFyeUNhbGVuZGFyPy5pZCxcbiAgICAgIHN0YXJ0VGltZTogY3VycmVudFRpbWUsXG4gICAgICBuYW1lOiBwcmltYXJ5SG9zdEF0dGVuZGVlSW5mbz8ubmFtZSxcbiAgICAgIHByaW1hcnlFbWFpbDogcHJpbWFyeUhvc3RBdHRlbmRlZUluZm8/LmVtYWlsLFxuICAgICAgc2VuZFVwZGF0ZXM6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LnNlbmRVcGRhdGVzLFxuICAgICAgYW55b25lQ2FuQWRkU2VsZjogZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uYW55b25lQ2FuQWRkU2VsZlxuICAgICAgICA/ICd0cnVlJ1xuICAgICAgICA6ICdmYWxzZScsXG4gICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnM6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lmd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgICA/ICd0cnVlJ1xuICAgICAgICA6ICdmYWxzZScsXG4gICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0czpcbiAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMgPyAndHJ1ZScgOiAnZmFsc2UnLFxuICAgICAgdHJhbnNwYXJlbmN5OiBib2R5Py50cmFuc3BhcmVuY3ksXG4gICAgICB2aXNpYmlsaXR5OiBib2R5Py52aXNpYmlsaXR5LFxuICAgIH07XG5cbiAgICBjb25zb2xlLmxvZyhtZWV0aW5nUXVlcnlQYXJhbXMsICcgbWVldGluZ1F1ZXJ5UGFyYW1zJyk7XG5cbiAgICBjb25zdCBjYWxlbmRhckxpbmsgPVxuICAgICAgYXRvbWljQ2FsZW5kYXJTdWJkb21haW5VcmwgKyAnPycgKyBxcy5zdHJpbmdpZnkobWVldGluZ1F1ZXJ5UGFyYW1zKTtcbiAgICBjb25zdCBjYWxlbmRhckxpbmtNZXNzYWdlID0gYFlvdSBjYW4gcXVpY2tseSBzY2hlZHVsZSBhIG1lZXRpbmcgYnkgY2xpY2tpbmcgXFxcIlJlcGx5IEFsbFxcXCIgd2l0aCB5b3VyIHRpbWUgdG8gc2VuZCBtZSBhIGNvcHkgYW5kIGxldCBtZSB0YWtlIGNhcmUgb2YgdGhlIGhlYXZ5IHdvcmsuIFxcbiAtIEF0b20sIGFuIEFJIGFzc2lzdGFudCBmcm9tIDxhIGhyZWY9XFxcIiR7Y2FsZW5kYXJMaW5rfVxcXCI+QXRvbWljPC9hPiA6KWA7XG5cbiAgICBtZWV0aW5nSW52aXRlT3BlbkFJUmVzICs9ICdcXG5cXG4nICsgY2FsZW5kYXJMaW5rTWVzc2FnZTtcblxuICAgIGNvbnN0IGVtYWlsU3ViamVjdFByb21wdCA9IG1lZXRpbmdSZXF1ZXN0U3ViamVjdFByb21wdDtcblxuICAgIGNvbnN0IGVtYWlsU3ViamVjdFVzZXJEYXRhID0gbWVldGluZ0ludml0ZU9wZW5BSVJlcztcblxuICAgIGNvbnN0IGVtYWlsU3ViamVjdEludml0ZU9wZW5BSVJlcyA9IGF3YWl0IGNhbGxPcGVuQUkoXG4gICAgICBvcGVuYWksXG4gICAgICBlbWFpbFN1YmplY3RQcm9tcHQsXG4gICAgICBvcGVuQUlDaGF0R1BUMzVNb2RlbCxcbiAgICAgIGVtYWlsU3ViamVjdFVzZXJEYXRhXG4gICAgKTtcblxuICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ2NvbXBsZXRlZCc7XG5cbiAgICBjb25zdCByZXNwb25zZU1lc3NhZ2UgPSBgXG4gICAgICAgICAgICBZb3VyIG1lZXRpbmcgaW52aXRlIG1lc3NhZ2UgaXMgcmVhZHkhIDopIFxcblxuICAgICAgICBgO1xuXG4gICAgcmVzcG9uc2UuZGF0YSA9IHJlc3BvbnNlTWVzc2FnZTtcbiAgICByZXNwb25zZS5odG1sRW1haWwgPSBgXG4gICAgICAgICAgICA8ZGl2PlxuICAgICAgICAgICAgICAgIDxwPlRvOiAke2JvZHk/LmF0dGVuZGVlcz8uZmlsdGVyKChhKSA9PiAhYT8uaXNIb3N0KT8uWzBdPy5lbWFpbH0sICR7cmVwbHlUb0FkZHJlc3N9PC9wPlxuICAgICAgICAgICAgICAgIDxwPlN1YmplY3Q6ICR7ZW1haWxTdWJqZWN0SW52aXRlT3BlbkFJUmVzfTwvcD5cbiAgICAgICAgICAgICAgICA8cHJlIHN0eWxlPVwiZm9udC1mYW1pbHk6c2Fucy1zZXJpZjtcIj4ke21lZXRpbmdJbnZpdGVPcGVuQUlSZXN9PC9wcmU+XG4gICAgICAgICAgICA8L2Rpdj5cbiAgICBgO1xuXG4gICAgcmV0dXJuIHJlc3BvbnNlO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZmluYWwgc3RlcCBnZW5lcmF0ZSBtZWV0aW5nIGludml0ZScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0dlbmVyYXRlTWVldGluZ0ludml0ZVBlbmRpbmcgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBqc29uQm9keTogVXNlcklucHV0VG9KU09OVHlwZSxcbiAgZGF0ZUpTT05Cb2R5OiBEYXRlVGltZUpTT05UeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nLFxuICBmb3JtRGF0YTogUmVjZWl2ZXJUaW1lem9uZUZvcm1EYXRhUmVzcG9uc2VUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBtaXNzaW5nRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gICAgICByZXF1aXJlZDogW10sXG4gICAgICBkYXRlVGltZTogeyByZXF1aXJlZDogW10gfSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IGFueSA9IHtcbiAgICAgIHF1ZXJ5OiAnJyxcbiAgICAgIGRhdGE6IHt9LFxuICAgICAgc2tpbGw6ICdnZW5lcmF0ZU1lZXRpbmdJbnZpdGUnLFxuICAgIH07XG5cbiAgICBsZXQgZHVyYXRpb24gPSAwO1xuXG4gICAgY29uc3QgeWVhclN0YXJ0ID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py55ZWFyO1xuICAgIGNvbnN0IG1vbnRoU3RhcnQgPSBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/Lm1vbnRoO1xuICAgIGNvbnN0IGRheVN0YXJ0ID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5kYXk7XG4gICAgY29uc3QgaXNvV2Vla2RheVN0YXJ0ID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5pc29XZWVrZGF5O1xuICAgIGNvbnN0IGhvdXJTdGFydCA9IGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8uaG91cjtcbiAgICBjb25zdCBtaW51dGVTdGFydCA9IGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8ubWludXRlO1xuICAgIGNvbnN0IHN0YXJ0VGltZVN0YXJ0ID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5zdGFydFRpbWU7XG5cbiAgICBjb25zdCB5ZWFyRW5kID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8ueWVhcjtcbiAgICBjb25zdCBtb250aEVuZCA9IGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/Lm1vbnRoO1xuICAgIGNvbnN0IGRheUVuZCA9IGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/LmRheTtcbiAgICBjb25zdCBpc29XZWVrZGF5RW5kID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8uaXNvV2Vla2RheTtcbiAgICBjb25zdCBob3VyRW5kID0gZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8uaG91cjtcbiAgICBjb25zdCBtaW51dGVFbmQgPSBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5taW51dGU7XG4gICAgY29uc3QgZW5kVGltZUVuZCA9IGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/LnN0YXJ0VGltZTtcblxuICAgIGNvbnN0IHdpbmRvd0JyYW5jaFN0YXJ0RGF0ZSA9IGV4dHJhcG9sYXRlU3RhcnREYXRlRnJvbUpTT05EYXRhKFxuICAgICAgY3VycmVudFRpbWUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHllYXJTdGFydCxcbiAgICAgIG1vbnRoU3RhcnQsXG4gICAgICBkYXlTdGFydCxcbiAgICAgIGlzb1dlZWtkYXlTdGFydCxcbiAgICAgIGhvdXJTdGFydCxcbiAgICAgIG1pbnV0ZVN0YXJ0LFxuICAgICAgc3RhcnRUaW1lU3RhcnQsXG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICApO1xuXG4gICAgbGV0IHdpbmRvd1N0YXJ0RGF0ZSA9IHdpbmRvd0JyYW5jaFN0YXJ0RGF0ZTtcblxuICAgIGlmICghd2luZG93U3RhcnREYXRlKSB7XG4gICAgICB3aW5kb3dTdGFydERhdGUgPSBkYXlqcygpLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGxldCB3aW5kb3dFbmREYXRlID0gZXh0cmFwb2xhdGVFbmREYXRlRnJvbUpTT05EYXRhKFxuICAgICAgY3VycmVudFRpbWUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHllYXJFbmQsXG4gICAgICBtb250aEVuZCxcbiAgICAgIGRheUVuZCxcbiAgICAgIGlzb1dlZWtkYXlFbmQsXG4gICAgICBob3VyRW5kLFxuICAgICAgbWludXRlRW5kLFxuICAgICAgZW5kVGltZUVuZCxcbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5yZWxhdGl2ZVRpbWVGcm9tTm93XG4gICAgKTtcblxuICAgIGlmICghd2luZG93RW5kRGF0ZSkge1xuICAgICAgd2luZG93RW5kRGF0ZSA9IGRheWpzKHdpbmRvd1N0YXJ0RGF0ZSkuYWRkKDEsICd3JykuZm9ybWF0KCk7XG4gICAgfVxuXG4gICAgY29uc3QgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcyA9XG4gICAgICBhd2FpdCBnZXRDaGF0TWVldGluZ1ByZWZlcmVuY2VHaXZlblVzZXJJZCh1c2VySWQpO1xuXG4gICAgaWYgKGRhdGVKU09OQm9keT8uZHVyYXRpb24pIHtcbiAgICAgIGR1cmF0aW9uID0gZGF0ZUpTT05Cb2R5Py5kdXJhdGlvbjtcbiAgICB9IGVsc2UgaWYgKGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LmR1cmF0aW9uKSB7XG4gICAgICBkdXJhdGlvbiA9IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LmR1cmF0aW9uO1xuICAgIH0gZWxzZSB7XG4gICAgICBkdXJhdGlvbiA9IDMwO1xuICAgIH1cblxuICAgIGNvbnN0IGJvZHk6IEdlbmVyYXRlTWVldGluZ0ludml0ZVR5cGUgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHRpdGxlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2ssXG4gICAgICBhdHRlbmRlZXM6IGpzb25Cb2R5Py5wYXJhbXM/LmF0dGVuZGVlcyxcbiAgICAgIG1ldGhvZDogZGF0ZUpTT05Cb2R5Py5tZXRob2QgYXMgYW55LFxuICAgICAgZHVyYXRpb24sXG4gICAgICBkZXNjcmlwdGlvbjoganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHwganNvbkJvZHk/LnBhcmFtcz8ubm90ZXMsXG4gICAgICBjb25mZXJlbmNlQXBwOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5jb25mZXJlbmNlPy5hcHAgfHxcbiAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uY29uZmVyZW5jZUFwcCxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lIHx8IHdpbmRvd1N0YXJ0RGF0ZSB8fCBjdXJyZW50VGltZSxcbiAgICAgIHdpbmRvd0VuZERhdGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmVuZFRpbWUgfHxcbiAgICAgICAgd2luZG93RW5kRGF0ZSB8fFxuICAgICAgICBkYXlqcyhjdXJyZW50VGltZSkuYWRkKDcsICdkJykuZm9ybWF0KCksXG4gICAgICByZW1pbmRlcnM6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmFsYXJtcyB8fCBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5yZW1pbmRlcnMsXG4gICAgICB0cmFuc3BhcmVuY3k6IGpzb25Cb2R5Py5wYXJhbXM/LnRyYW5zcGFyZW5jeSxcbiAgICAgIHZpc2liaWxpdHk6IGpzb25Cb2R5Py5wYXJhbXMudmlzaWJpbGl0eSxcbiAgICAgIHJlY2VpdmVyVGltZXpvbmU6IGZvcm1EYXRhPy52YWx1ZSxcbiAgICB9O1xuXG4gICAgY29uc29sZS5sb2coYm9keSwgJyBib2R5Jyk7XG5cbiAgICBpZiAoIWJvZHk/LnRpdGxlKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlswXSk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gYm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBpZiAoIShib2R5Py5hdHRlbmRlZXM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlsxXSk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gYm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBjb25zdCBuZXdBdHRlbmRlZXM6IE11dGF0ZWRDYWxlbmRhckV4dHJhY3RlZEpTT05BdHRlbmRlZVR5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBhIG9mIGJvZHk/LmF0dGVuZGVlcykge1xuICAgICAgaWYgKCFhPy5lbWFpbCkge1xuICAgICAgICBjb25zdCBjb250YWN0ID0gYXdhaXQgZ2V0Q29udGFjdEJ5TmFtZVdpdGhVc2VySWQoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIGAlJHthPy5uYW1lfSVgXG4gICAgICAgICk7XG4gICAgICAgIGlmIChjb250YWN0Py5lbWFpbHM/LlswXT8udmFsdWUpIHtcbiAgICAgICAgICBjb25zdCBwcmltYXJ5RW1haWwgPSBjb250YWN0Py5lbWFpbHM/LmZpbmQoKGUpID0+ICEhZS5wcmltYXJ5KT8udmFsdWU7XG4gICAgICAgICAgY29uc3QgYW55RW1haWwgPSBjb250YWN0Py5lbWFpbHM/LlswXT8udmFsdWU7XG4gICAgICAgICAgbmV3QXR0ZW5kZWVzLnB1c2goeyAuLi5hLCBlbWFpbDogcHJpbWFyeUVtYWlsIHx8IGFueUVtYWlsIH0pO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2goXG4gICAgICAgICAgICByZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzFdPy5bJ2FuZCddPy5bMl1cbiAgICAgICAgICApO1xuICAgICAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gYm9keTtcbiAgICAgICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgICAgICB9XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBuZXdBdHRlbmRlZXMucHVzaChhKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBib2R5LmF0dGVuZGVlcyA9IG5ld0F0dGVuZGVlcztcblxuICAgIGNvbnN0IHVzZXJDb250YWN0SW5mb3MgPSBhd2FpdCBsaXN0VXNlckNvbnRhY3RJbmZvc0dpdmVuVXNlcklkKHVzZXJJZCk7XG5cbiAgICBjb25zdCBwcm92aWRlZEhvc3RJbmZvID0gYm9keT8uYXR0ZW5kZWVzPy5maW5kKChhKSA9PiBhPy5pc0hvc3QgPT09IHRydWUpO1xuXG4gICAgY29uc3QgcHJpbWFyeUluZm9JdGVtID0gdXNlckNvbnRhY3RJbmZvcz8uZmluZChcbiAgICAgICh1KSA9PiB1LnByaW1hcnkgJiYgdS50eXBlID09PSAnZW1haWwnXG4gICAgKTtcblxuICAgIGNvbnN0IHVzZXIgPSBhd2FpdCBnZXRVc2VyR2l2ZW5JZCh1c2VySWQpO1xuXG4gICAgY29uc3QgcHJpbWFyeUhvc3RBdHRlbmRlZUluZm86IE11dGF0ZWRDYWxlbmRhckV4dHJhY3RlZEpTT05BdHRlbmRlZVR5cGUgPSB7XG4gICAgICBuYW1lOiBwcmltYXJ5SW5mb0l0ZW0/Lm5hbWUgfHwgdXNlcj8ubmFtZSxcbiAgICAgIGVtYWlsOiBwcmltYXJ5SW5mb0l0ZW0/LmlkIHx8IHVzZXI/LmVtYWlsLFxuICAgICAgaXNIb3N0OiB0cnVlLFxuICAgIH07XG5cbiAgICBpZiAoIXByb3ZpZGVkSG9zdEluZm8gJiYgcHJpbWFyeUhvc3RBdHRlbmRlZUluZm8/LmVtYWlsKSB7XG4gICAgICBib2R5Py5hdHRlbmRlZXMucHVzaChwcmltYXJ5SG9zdEF0dGVuZGVlSW5mbyk7XG4gICAgfVxuXG4gICAgY29uc3QgaG9zdEluZm8gPSBwcm92aWRlZEhvc3RJbmZvIHx8IHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvO1xuXG4gICAgaWYgKCFob3N0SW5mbz8uZW1haWwpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzFdWydhbmQnXVsxXSk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gYm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBpZiAoIWZvcm1EYXRhPy52YWx1ZSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5kYXRlVGltZS5yZXF1aXJlZC5wdXNoKHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMl0pO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKHJlc3BvbnNlLnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzcG9uc2UyID0gYXdhaXQgZmluYWxTdGVwR2VuZXJhdGVNZWV0aW5nSW52aXRlKFxuICAgICAgYm9keSxcbiAgICAgIGhvc3RJbmZvLFxuICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcyxcbiAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgcmVzcG9uc2VcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlc3BvbnNlMjtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHByb2Nlc3Mgc2VuZCBtZWV0aW5nIGludml0ZScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0dlbmVyYXRlTWVldGluZ0ludml0ZU1pc3NpbmdGaWVsZHNSZXR1cm5lZCA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIGpzb25Cb2R5OiBVc2VySW5wdXRUb0pTT05UeXBlLFxuICBkYXRlSlNPTkJvZHk6IERhdGVUaW1lSlNPTlR5cGUsXG4gIGN1cnJlbnRUaW1lOiBzdHJpbmcsXG4gIGZvcm1EYXRhOiBSZWNlaXZlclRpbWV6b25lRm9ybURhdGFSZXNwb25zZVR5cGUsXG4gIG1lc3NhZ2VIaXN0b3J5T2JqZWN0OiBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgbWlzc2luZ0ZpZWxkczogUmVxdWlyZWRGaWVsZHNUeXBlID0ge1xuICAgICAgcmVxdWlyZWQ6IFtdLFxuICAgICAgZGF0ZVRpbWU6IHsgcmVxdWlyZWQ6IFtdIH0sXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiBhbnkgPSB7XG4gICAgICBxdWVyeTogJycsXG4gICAgICBkYXRhOiB7fSxcbiAgICAgIHNraWxsOiAnZ2VuZXJhdGVNZWV0aW5nSW52aXRlJyxcbiAgICB9O1xuXG4gICAgbGV0IGR1cmF0aW9uID0gMDtcblxuICAgIGNvbnN0IHllYXJTdGFydCA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/LnllYXIgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py55ZWFyO1xuICAgIGNvbnN0IG1vbnRoU3RhcnQgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5tb250aCB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/Lm1vbnRoO1xuICAgIGNvbnN0IGRheVN0YXJ0ID1cbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8uZGF5IHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8uZGF5O1xuICAgIGNvbnN0IGlzb1dlZWtkYXlTdGFydCA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/Lmlzb1dlZWtkYXkgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5pc29XZWVrZGF5O1xuICAgIGNvbnN0IGhvdXJTdGFydCA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93U3RhcnQ/LmhvdXIgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0Py5ob3VyO1xuICAgIGNvbnN0IG1pbnV0ZVN0YXJ0ID1cbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8ubWludXRlIHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8ubWludXRlO1xuICAgIGNvbnN0IHN0YXJ0VGltZVN0YXJ0ID1cbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8uc3RhcnRUaW1lIHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8uc3RhcnRUaW1lO1xuXG4gICAgY29uc3QgeWVhckVuZCA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy55ZWFyIHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/LnllYXI7XG4gICAgY29uc3QgbW9udGhFbmQgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8ubW9udGggfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8ubW9udGg7XG4gICAgY29uc3QgZGF5RW5kID1cbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/LmRheSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5kYXk7XG4gICAgY29uc3QgaXNvV2Vla2RheUVuZCA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5pc29XZWVrZGF5IHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/Lmlzb1dlZWtkYXk7XG4gICAgY29uc3QgaG91ckVuZCA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5ob3VyIHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/LmhvdXI7XG4gICAgY29uc3QgbWludXRlRW5kID1cbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dFbmQ/Lm1pbnV0ZSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5taW51dGU7XG4gICAgY29uc3QgZW5kVGltZUVuZCA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5zdGFydFRpbWUgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8uc3RhcnRUaW1lO1xuXG4gICAgY29uc3Qgd2luZG93QnJhbmNoU3RhcnREYXRlID0gZXh0cmFwb2xhdGVTdGFydERhdGVGcm9tSlNPTkRhdGEoXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgeWVhclN0YXJ0LFxuICAgICAgbW9udGhTdGFydCxcbiAgICAgIGRheVN0YXJ0LFxuICAgICAgaXNvV2Vla2RheVN0YXJ0LFxuICAgICAgaG91clN0YXJ0LFxuICAgICAgbWludXRlU3RhcnQsXG4gICAgICBzdGFydFRpbWVTdGFydCxcbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydFxuICAgICAgICAgID8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgIGRhdGVKU09OQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydD8ucmVsYXRpdmVUaW1lRnJvbU5vdyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dTdGFydFxuICAgICAgICAgID8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICk7XG5cbiAgICBsZXQgd2luZG93U3RhcnREYXRlID0gd2luZG93QnJhbmNoU3RhcnREYXRlO1xuXG4gICAgaWYgKCF3aW5kb3dTdGFydERhdGUpIHtcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSA9IGRheWpzKCkuZm9ybWF0KCk7XG4gICAgfVxuXG4gICAgbGV0IHdpbmRvd0VuZERhdGUgPSBleHRyYXBvbGF0ZUVuZERhdGVGcm9tSlNPTkRhdGEoXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgeWVhckVuZCxcbiAgICAgIG1vbnRoRW5kLFxuICAgICAgZGF5RW5kLFxuICAgICAgaXNvV2Vla2RheUVuZCxcbiAgICAgIGhvdXJFbmQsXG4gICAgICBtaW51dGVFbmQsXG4gICAgICBlbmRUaW1lRW5kLFxuICAgICAgZGF0ZUpTT05Cb2R5Py5maW5kVGltZVdpbmRvd0VuZD8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZmluZFRpbWVXaW5kb3dFbmRcbiAgICAgICAgICA/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBkYXRlSlNPTkJvZHk/LmZpbmRUaW1lV2luZG93RW5kPy5yZWxhdGl2ZVRpbWVGcm9tTm93IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5maW5kVGltZVdpbmRvd0VuZFxuICAgICAgICAgID8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICk7XG5cbiAgICBpZiAoIXdpbmRvd0VuZERhdGUpIHtcbiAgICAgIHdpbmRvd0VuZERhdGUgPSBkYXlqcyh3aW5kb3dTdGFydERhdGUpLmFkZCgxLCAndycpLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGNvbnN0IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXMgPVxuICAgICAgYXdhaXQgZ2V0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlR2l2ZW5Vc2VySWQodXNlcklkKTtcblxuICAgIGlmIChcbiAgICAgIGRhdGVKU09OQm9keT8uZHVyYXRpb24gfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5kdXJhdGlvblxuICAgICkge1xuICAgICAgZHVyYXRpb24gPVxuICAgICAgICBkYXRlSlNPTkJvZHk/LmR1cmF0aW9uIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5kdXJhdGlvbjtcbiAgICB9IGVsc2UgaWYgKGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LmR1cmF0aW9uKSB7XG4gICAgICBkdXJhdGlvbiA9IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LmR1cmF0aW9uO1xuICAgIH0gZWxzZSB7XG4gICAgICBkdXJhdGlvbiA9IDMwO1xuICAgIH1cblxuICAgIGNvbnN0IG5ld0JvZHk6IEdlbmVyYXRlTWVldGluZ0ludml0ZVR5cGUgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHRpdGxlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2sgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2ssXG4gICAgICBhdHRlbmRlZXM6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmF0dGVuZGVlcyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmF0dGVuZGVlcyxcbiAgICAgIG1ldGhvZDogZGF0ZUpTT05Cb2R5Py5tZXRob2QgYXMgYW55LFxuICAgICAgZHVyYXRpb24sXG4gICAgICBkZXNjcmlwdGlvbjpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ubm90ZXMgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/Lm5vdGVzLFxuICAgICAgY29uZmVyZW5jZUFwcDpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uY29uZmVyZW5jZT8uYXBwIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uY29uZmVyZW5jZT8uYXBwIHx8XG4gICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LmNvbmZlcmVuY2VBcHAsXG4gICAgICB3aW5kb3dTdGFydERhdGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSB8fFxuICAgICAgICB3aW5kb3dTdGFydERhdGUgfHxcbiAgICAgICAgY3VycmVudFRpbWUsXG4gICAgICB3aW5kb3dFbmREYXRlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uZW5kVGltZSB8fFxuICAgICAgICB3aW5kb3dFbmREYXRlIHx8XG4gICAgICAgIGRheWpzKGN1cnJlbnRUaW1lKS5hZGQoNywgJ2QnKS5mb3JtYXQoKSxcbiAgICAgIHJlbWluZGVyczpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uYWxhcm1zIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uYWxhcm1zIHx8XG4gICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LnJlbWluZGVycyxcbiAgICAgIHRyYW5zcGFyZW5jeTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udHJhbnNwYXJlbmN5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udHJhbnNwYXJlbmN5LFxuICAgICAgdmlzaWJpbGl0eTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcy52aXNpYmlsaXR5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udmlzaWJpbGl0eSxcbiAgICAgIHJlY2VpdmVyVGltZXpvbmU6IGZvcm1EYXRhPy52YWx1ZSxcbiAgICB9O1xuXG4gICAgY29uc3QgcHJldkJvZHk6IEdlbmVyYXRlTWVldGluZ0ludml0ZVR5cGUgPSB7XG4gICAgICAuLi5tZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGEsXG4gICAgfTtcblxuICAgIGlmICghcHJldkJvZHk/LnVzZXJJZCkge1xuICAgICAgcHJldkJvZHkudXNlcklkID0gdXNlcklkIHx8IG5ld0JvZHk/LnVzZXJJZDtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py50aW1lem9uZSkge1xuICAgICAgcHJldkJvZHkudGltZXpvbmUgPSB0aW1lem9uZSB8fCBuZXdCb2R5Py50aW1lem9uZTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py50aXRsZSkge1xuICAgICAgcHJldkJvZHkudGl0bGUgPSBuZXdCb2R5Py50aXRsZTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5kdXJhdGlvbikge1xuICAgICAgcHJldkJvZHkuZHVyYXRpb24gPSBuZXdCb2R5Py5kdXJhdGlvbjtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5kZXNjcmlwdGlvbikge1xuICAgICAgcHJldkJvZHkuZGVzY3JpcHRpb24gPSBuZXdCb2R5Py5kZXNjcmlwdGlvbjtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5jb25mZXJlbmNlQXBwKSB7XG4gICAgICBwcmV2Qm9keS5jb25mZXJlbmNlQXBwID0gbmV3Qm9keT8uY29uZmVyZW5jZUFwcDtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py53aW5kb3dTdGFydERhdGUpIHtcbiAgICAgIHByZXZCb2R5LndpbmRvd1N0YXJ0RGF0ZSA9IG5ld0JvZHk/LndpbmRvd1N0YXJ0RGF0ZTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py53aW5kb3dFbmREYXRlKSB7XG4gICAgICBwcmV2Qm9keS53aW5kb3dFbmREYXRlID0gbmV3Qm9keT8ud2luZG93RW5kRGF0ZTtcbiAgICB9XG5cbiAgICBpZiAoIShwcmV2Qm9keT8ucmVtaW5kZXJzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkucmVtaW5kZXJzID0gbmV3Qm9keT8ucmVtaW5kZXJzIHx8IFtdO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRyYW5zcGFyZW5jeSkge1xuICAgICAgcHJldkJvZHkudHJhbnNwYXJlbmN5ID0gbmV3Qm9keT8udHJhbnNwYXJlbmN5O1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnZpc2liaWxpdHkpIHtcbiAgICAgIHByZXZCb2R5LnZpc2liaWxpdHkgPSBuZXdCb2R5Py52aXNpYmlsaXR5O1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnJlY2VpdmVyVGltZXpvbmUpIHtcbiAgICAgIHByZXZCb2R5LnJlY2VpdmVyVGltZXpvbmUgPSBuZXdCb2R5Py5yZWNlaXZlclRpbWV6b25lO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRpdGxlKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlswXSk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gcHJldkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKCEocHJldkJvZHk/LmF0dGVuZGVlcz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzFdKTtcbiAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBjb25zdCBuZXdBdHRlbmRlZXM6IE11dGF0ZWRDYWxlbmRhckV4dHJhY3RlZEpTT05BdHRlbmRlZVR5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBhIG9mIG5ld0JvZHk/LmF0dGVuZGVlcykge1xuICAgICAgaWYgKCFhPy5lbWFpbCkge1xuICAgICAgICBjb25zdCBjb250YWN0ID0gYXdhaXQgZ2V0Q29udGFjdEJ5TmFtZVdpdGhVc2VySWQoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIGAlJHthPy5uYW1lfSVgXG4gICAgICAgICk7XG4gICAgICAgIGlmIChjb250YWN0Py5lbWFpbHM/LlswXT8udmFsdWUpIHtcbiAgICAgICAgICBjb25zdCBwcmltYXJ5RW1haWwgPSBjb250YWN0Py5lbWFpbHM/LmZpbmQoKGUpID0+ICEhZS5wcmltYXJ5KT8udmFsdWU7XG4gICAgICAgICAgY29uc3QgYW55RW1haWwgPSBjb250YWN0Py5lbWFpbHM/LlswXT8udmFsdWU7XG4gICAgICAgICAgbmV3QXR0ZW5kZWVzLnB1c2goeyAuLi5hLCBlbWFpbDogcHJpbWFyeUVtYWlsIHx8IGFueUVtYWlsIH0pO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2goXG4gICAgICAgICAgICByZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzFdPy5bJ2FuZCddPy5bMl1cbiAgICAgICAgICApO1xuICAgICAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gcHJldkJvZHk7XG4gICAgICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICAgICAgfVxuICAgICAgfSBlbHNlIHtcbiAgICAgICAgbmV3QXR0ZW5kZWVzLnB1c2goYSk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgbmV3Qm9keS5hdHRlbmRlZXMgPSBuZXdBdHRlbmRlZXM7XG5cbiAgICBpZiAoIShwcmV2Qm9keT8uYXR0ZW5kZWVzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkuYXR0ZW5kZWVzID0gbmV3Qm9keT8uYXR0ZW5kZWVzO1xuICAgIH1cblxuICAgIGNvbnN0IHVzZXJDb250YWN0SW5mb3MgPSBhd2FpdCBsaXN0VXNlckNvbnRhY3RJbmZvc0dpdmVuVXNlcklkKHVzZXJJZCk7XG5cbiAgICBjb25zdCBuZXdQcm92aWRlZEhvc3RJbmZvID0gbmV3Qm9keT8uYXR0ZW5kZWVzPy5maW5kKFxuICAgICAgKGEpID0+IGE/LmlzSG9zdCA9PT0gdHJ1ZVxuICAgICk7XG5cbiAgICBjb25zdCBwcmV2UHJvdmlkZWRIb3N0SW5mbyA9IHByZXZCb2R5Py5hdHRlbmRlZXM/LmZpbmQoXG4gICAgICAoYSkgPT4gYT8uaXNIb3N0ID09PSB0cnVlXG4gICAgKTtcblxuICAgIGNvbnN0IHByaW1hcnlJbmZvSXRlbSA9IHVzZXJDb250YWN0SW5mb3M/LmZpbmQoXG4gICAgICAodSkgPT4gdS5wcmltYXJ5ICYmIHUudHlwZSA9PT0gJ2VtYWlsJ1xuICAgICk7XG5cbiAgICBjb25zdCB1c2VyID0gYXdhaXQgZ2V0VXNlckdpdmVuSWQodXNlcklkKTtcblxuICAgIGNvbnN0IHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvOiBNdXRhdGVkQ2FsZW5kYXJFeHRyYWN0ZWRKU09OQXR0ZW5kZWVUeXBlID0ge1xuICAgICAgbmFtZTogcHJpbWFyeUluZm9JdGVtPy5uYW1lIHx8IHVzZXI/Lm5hbWUsXG4gICAgICBlbWFpbDogcHJpbWFyeUluZm9JdGVtPy5pZCB8fCB1c2VyPy5lbWFpbCxcbiAgICAgIGlzSG9zdDogdHJ1ZSxcbiAgICB9O1xuXG4gICAgaWYgKCFuZXdQcm92aWRlZEhvc3RJbmZvICYmIHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvPy5lbWFpbCkge1xuICAgICAgbmV3Qm9keT8uYXR0ZW5kZWVzLnB1c2gocHJpbWFyeUhvc3RBdHRlbmRlZUluZm8pO1xuICAgIH1cblxuICAgIGlmICghcHJldlByb3ZpZGVkSG9zdEluZm8gJiYgcHJpbWFyeUhvc3RBdHRlbmRlZUluZm8/LmVtYWlsKSB7XG4gICAgICBwcmV2Qm9keT8uYXR0ZW5kZWVzLnB1c2gocHJpbWFyeUhvc3RBdHRlbmRlZUluZm8pO1xuICAgIH1cblxuICAgIGNvbnN0IHByZXZIb3N0SW5mbyA9XG4gICAgICBwcmV2UHJvdmlkZWRIb3N0SW5mbyB8fCBuZXdQcm92aWRlZEhvc3RJbmZvIHx8IHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvO1xuXG4gICAgaWYgKCFwcmV2SG9zdEluZm8/LmVtYWlsKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlsxXVsnYW5kJ11bMV0pO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IHByZXZCb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnJlY2VpdmVyVGltZXpvbmUpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMuZGF0ZVRpbWUucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzJdKTtcbiAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBpZiAocmVzcG9uc2UucXVlcnkgPT09ICdtaXNzaW5nX2ZpZWxkcycpIHtcbiAgICAgIHJldHVybiByZXNwb25zZTtcbiAgICB9XG5cbiAgICBjb25zdCByZXNwb25zZTIgPSBhd2FpdCBmaW5hbFN0ZXBHZW5lcmF0ZU1lZXRpbmdJbnZpdGUoXG4gICAgICBwcmV2Qm9keSxcbiAgICAgIHByZXZIb3N0SW5mbyxcbiAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXMsXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHJlc3BvbnNlXG4gICAgKTtcblxuICAgIHJldHVybiByZXNwb25zZTI7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGUsXG4gICAgICAnIHVuYWJsZSB0byBnZW5lcmF0ZSBtZWV0aW5nIGludml0ZSBtaXNzaW5nIGZpZWxkcyByZXR1cm5lZCdcbiAgICApO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVNZWV0aW5nSW52aXRlQ29udHJvbENlbnRlciA9IGFzeW5jIChcbiAgb3BlbmFpOiBPcGVuQUksXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBtZXNzYWdlSGlzdG9yeU9iamVjdDogU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGUsXG4gIHVzZXJDdXJyZW50VGltZTogc3RyaW5nLFxuICBxdWVyeTogJ21pc3NpbmdfZmllbGRzJyB8ICdjb21wbGV0ZWQnIHwgJ2V2ZW50X25vdF9mb3VuZCcgfCAncGVuZGluZydcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG1lc3NhZ2VMZW5ndGggPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcz8ubGVuZ3RoO1xuICAgIGxldCB1c2VyTWVzc2FnZSA9ICcnO1xuICAgIGZvciAobGV0IGkgPSBtZXNzYWdlTGVuZ3RoOyBpID4gMDsgaS0tKSB7XG4gICAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXNbaSAtIDFdO1xuXG4gICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAndXNlcicpIHtcbiAgICAgICAgdXNlck1lc3NhZ2UgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgIGJyZWFrO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IHVzZXJJbnB1dCA9IHVzZXJNZXNzYWdlO1xuXG4gICAgbGV0IEdNSVJlczogUmVzcG9uc2VBY3Rpb25UeXBlID0ge1xuICAgICAgcXVlcnk6ICdjb21wbGV0ZWQnLFxuICAgICAgZGF0YTogJycsXG4gICAgICBza2lsbDogJycsXG4gICAgICBwcmV2RGF0YToge30sXG4gICAgICBwcmV2RGF0YUV4dHJhOiB7fSxcbiAgICB9O1xuXG4gICAgc3dpdGNoIChxdWVyeSkge1xuICAgICAgY2FzZSAncGVuZGluZyc6XG4gICAgICAgIGNvbnN0IGpzb25Cb2R5ID0gYXdhaXQgZ2VuZXJhdGVKU09ORGF0YUZyb21Vc2VySW5wdXQoXG4gICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICApO1xuICAgICAgICBjb25zdCBkYXRlVGltZSA9IGF3YWl0IGdlbmVyYXRlRGF0ZVRpbWUoXG4gICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZSxcbiAgICAgICAgICB0aW1lem9uZVxuICAgICAgICApO1xuXG4gICAgICAgIEdNSVJlcyA9IGF3YWl0IHByb2Nlc3NHZW5lcmF0ZU1lZXRpbmdJbnZpdGVQZW5kaW5nKFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICBqc29uQm9keSxcbiAgICAgICAgICBkYXRlVGltZSxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LmZvcm1EYXRhXG4gICAgICAgICk7XG4gICAgICAgIGJyZWFrO1xuICAgICAgY2FzZSAnbWlzc2luZ19maWVsZHMnOlxuICAgICAgICBsZXQgcHJpb3JVc2VySW5wdXQgPSAnJztcbiAgICAgICAgbGV0IHByaW9yQXNzaXN0YW50T3V0cHV0ID0gJyc7XG5cbiAgICAgICAgZm9yIChsZXQgaSA9IG1lc3NhZ2VMZW5ndGg7IGkgPiAwOyBpLS0pIHtcbiAgICAgICAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXNbaSAtIDFdO1xuXG4gICAgICAgICAgaWYgKG1lc3NhZ2Uucm9sZSA9PT0gJ2Fzc2lzdGFudCcpIHtcbiAgICAgICAgICAgIHByaW9yQXNzaXN0YW50T3V0cHV0ID0gbWVzc2FnZS5jb250ZW50O1xuICAgICAgICAgICAgY29udGludWU7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgaWYgKG1lc3NhZ2Uucm9sZSA9PT0gJ3VzZXInKSB7XG4gICAgICAgICAgICBpZiAobWVzc2FnZS5jb250ZW50ICE9PSB1c2VySW5wdXQpIHtcbiAgICAgICAgICAgICAgcHJpb3JVc2VySW5wdXQgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cbiAgICAgICAgfVxuXG4gICAgICAgIGlmICghcHJpb3JVc2VySW5wdXQgfHwgIXByaW9yQXNzaXN0YW50T3V0cHV0KSB7XG4gICAgICAgICAgY29uc29sZS5sb2cocHJpb3JVc2VySW5wdXQsICcgcHJpb3JVc2VySW5wdXQnKTtcbiAgICAgICAgICBjb25zb2xlLmxvZyhwcmlvckFzc2lzdGFudE91dHB1dCwgJyBwcmlvckFzc2lzdGFudE91dHB1dCcpO1xuICAgICAgICAgIHRocm93IG5ldyBFcnJvcignbm8gcHJpb3JVc2VyaW5wdXQgb3IgcHJpb3JBc3Npc3RhbnRPdXRwdXQnKTtcbiAgICAgICAgfVxuICAgICAgICBjb25zdCBqc29uTWlzc2luZ0ZpZWxkc0JvZHkgPVxuICAgICAgICAgIGF3YWl0IGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0pTT05EYXRhRnJvbVVzZXJJbnB1dChcbiAgICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICAgIHByaW9yVXNlcklucHV0LFxuICAgICAgICAgICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQsXG4gICAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgICApO1xuICAgICAgICBjb25zdCBkYXRlTWlzc2luZ0ZpZWxkc1RpbWUgPSBhd2FpdCBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNEYXRlVGltZShcbiAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgcHJpb3JVc2VySW5wdXQsXG4gICAgICAgICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lLFxuICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICk7XG5cbiAgICAgICAgR01JUmVzID0gYXdhaXQgcHJvY2Vzc0dlbmVyYXRlTWVldGluZ0ludml0ZU1pc3NpbmdGaWVsZHNSZXR1cm5lZChcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAganNvbk1pc3NpbmdGaWVsZHNCb2R5LFxuICAgICAgICAgIGRhdGVNaXNzaW5nRmllbGRzVGltZSxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LmZvcm1EYXRhLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG4gICAgICAgIGJyZWFrO1xuICAgIH1cblxuICAgIGlmIChHTUlSZXM/LnF1ZXJ5ID09PSAnY29tcGxldGVkJykge1xuICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZTogQXNzaXN0YW50TWVzc2FnZVR5cGUgPSB7XG4gICAgICAgIHJvbGU6ICdhc3Npc3RhbnQnLFxuICAgICAgICBjb250ZW50OiBHTUlSZXM/LmRhdGEgYXMgc3RyaW5nLFxuICAgICAgfTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdjb21wbGV0ZWQnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBudWxsO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QuaHRtbEVtYWlsID0gR01JUmVzLmh0bWxFbWFpbDtcbiAgICB9IGVsc2UgaWYgKEdNSVJlcz8ucXVlcnkgPT09ICdtaXNzaW5nX2ZpZWxkcycpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UgPVxuICAgICAgICBhd2FpdCBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VUb1JlcXVlc3RVc2VyRm9yTWlzc2luZ0ZpZWxkcyhcbiAgICAgICAgICBvcGVuYWksXG4gICAgICAgICAgR01JUmVzPy5kYXRhIGFzIFJlcXVpcmVkRmllbGRzVHlwZSxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdFxuICAgICAgICApO1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBHTUlSZXM/LmRhdGEgYXMgUmVxdWlyZWRGaWVsZHNUeXBlO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkRhdGEgPSBHTUlSZXM/LnByZXZEYXRhO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkRhdGFFeHRyYSA9IEdNSVJlcz8ucHJldkRhdGFFeHRyYTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRlSnNvbkJvZHkgPSBHTUlSZXM/LnByZXZEYXRlSnNvbkJvZHk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2SnNvbkJvZHkgPSBHTUlSZXM/LnByZXZKc29uQm9keTtcbiAgICB9IGVsc2UgaWYgKEdNSVJlcz8ucXVlcnkgPT09ICdldmVudF9ub3RfZm91bmQnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlOiBBc3Npc3RhbnRNZXNzYWdlVHlwZSA9IHtcbiAgICAgICAgcm9sZTogJ2Fzc2lzdGFudCcsXG4gICAgICAgIGNvbnRlbnQ6IFwiT29wcy4uLiBJIGNvdWxkbid0IGZpbmQgdGhlIGV2ZW50LiBTb3JyeSA6KFwiLFxuICAgICAgfTtcblxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXMucHVzaChhc3Npc3RhbnRNZXNzYWdlKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnF1ZXJ5ID0gJ2V2ZW50X25vdF9mb3VuZCc7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5yZXF1aXJlZCA9IG51bGw7XG4gICAgfVxuXG4gICAgcmV0dXJuIG1lc3NhZ2VIaXN0b3J5T2JqZWN0O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2VuZXJhdGUgbWVldGluZyBpbnZpdGUgY29udHJvbCBjZW50ZXIgcGVuZGluZycpO1xuICB9XG59O1xuIl19