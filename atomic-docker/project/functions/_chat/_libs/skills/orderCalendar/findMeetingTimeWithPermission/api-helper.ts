import qs from 'qs';
import { handshakeUrl } from './constants';
import { MeetingAssistInviteType } from '@chat/_libs/types/MeetingAssistInviteType';
import {
  AttendeeDetailsForBulkMeetingInviteType,
  AttendeeDetailsType,
  FindMeetingTimeWithPermissionType,
  MeetingInviteDetailsToHostType,
  RecurrenceFrequencyType,
} from './types';
import DateTimeJSONType from '@chat/_libs/datetime/DateTimeJSONJSONType';
import UserInputToJSONType, {
  MutatedCalendarExtractedJSONAttendeeType,
} from '@chat/_libs/types/UserInputToJSONType';
import RequiredFieldsType from '@chat/_libs/types/RequiredFieldsType';
import requiredFields from './requiredFields';
import {
  extrapolateStartDateFromJSONData,
  findContactByEmailGivenUserId,
  getCalendarIntegrationByName,
  getUserContactInfosGivenIds,
  getGlobalCalendar,
  listUserContactInfosGivenUserId,
  getContactByNameWithUserId,
  upsertMeetingAssistOne,
  createHostAttendee,
  getUserGivenId,
  upsertMeetingAssistInviteMany,
  generateDateTime,
  generateJSONDataFromUserInput,
  generateAssistantMessageFromAPIResponseForUserQuery,
  generateAssistantMessageToRequestUserForMissingFields,
  extrapolateEndDateFromJSONData,
  extrapolateDateFromJSONData,
  generateMissingFieldsDateTime,
  generateMissingFieldsJSONDataFromUserInput,
} from '@chat/_libs/api-helper';
import { getChatMeetingPreferenceGivenUserId } from '../scheduleMeeting/api-helper';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import { RecurrenceRuleType } from '@chat/_libs/types/EventType';
import { googleCalendarName } from '@chat/_libs/constants';
import { v4 as uuid } from 'uuid';
import { MeetingAssistType } from '@chat/_libs/types/MeetingAssistType';
import ResponseActionType from '@chat/_libs/types/ResponseActionType';
import {
  AssistantMessageType,
  SkillMessageHistoryType,
} from '@chat/_libs/types/Messaging/MessagingTypes';
import OpenAI from 'openai';
import { ChatMeetingPreferencesType } from '@chat/_libs/types/ChatMeetingPreferencesType';
import { UserType } from '@chat/_libs/types/UserType';
import { sendEmail } from '@/_utils/email/email';
import { ENV } from '@/_utils/env';

// const client = new LambdaClient({
//     region: 'us-east-1'
// })

export const generateInviteLink = (
  meetingId: string,
  attendeeId: string,
  primaryEmail?: string
) =>
  (primaryEmail &&
    `${handshakeUrl}?${qs.stringify({ meetingId, attendeeId, primaryEmail })}`) ||
  `${handshakeUrl}?${qs.stringify({ meetingId, attendeeId })}`;

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

const createMeetingAssistInvitees = async (
  invitees: MeetingAssistInviteType[]
) => {
  try {
    console.log(invitees, ' invitees');
    await upsertMeetingAssistInviteMany(invitees);
  } catch (e) {
    console.log(e, ' unable to create meeting assist invitees');
  }
};

// meeting-info-to-host-auth

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
  } catch (e) {
    console.log(e, ' unable to send email to host');
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
  } catch (e) {
    console.log(e, ' unable to send bulk meeting invite email');
  }
};

// FindMeetingTimeWithPermissionType

export const finalStepFMTWP = async (
  body: FindMeetingTimeWithPermissionType,
  primaryHostAttendeeInfo: MutatedCalendarExtractedJSONAttendeeType,
  defaultMeetingPreferences: ChatMeetingPreferencesType,
  user: UserType,
  meetingId: string,
  windowStartDate: string,
  windowEndDate: string,
  response: any
) => {
  try {
    // get primary calendar
    const primaryCalendar = await getGlobalCalendar(body?.userId);

    // validate
    if (!primaryCalendar?.id) {
      throw new Error('no primary calendar found inside createAgenda');
    }

    // get client type
    const calIntegration = await getCalendarIntegrationByName(
      body?.userId,
      googleCalendarName
    );

    // validate
    if (!calIntegration?.clientType) {
      throw new Error(
        'no client type inside calendar integration inside create agenda'
      );
    }

    // findContactByEmailGivenUserId
    // get attendees with provided emails
    const aWithEmails = body?.attendees?.filter((a) => !!a?.email);

    const aWithContactInfos = await getUserContactInfosGivenIds(
      aWithEmails?.map((a) => a?.email)
    );

    const inviteesFromExtractedJSON = body?.attendees;

    const invitees: MeetingAssistInviteType[] = [];

    for (const i of inviteesFromExtractedJSON) {
      const contact = await findContactByEmailGivenUserId(
        body?.userId,
        i.email
      );
      const userIdFound = aWithContactInfos?.find((b) => b?.id === i?.email);
      const invitee: MeetingAssistInviteType = {
        id: uuid(),
        hostId: body?.userId,
        hostName: primaryHostAttendeeInfo?.name,
        userId: i?.isHost ? body?.userId : userIdFound?.userId || uuid(),
        name:
          i?.name ||
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

    const meetingAssist: MeetingAssistType = {
      id: meetingId,
      userId: body?.userId,
      summary: body?.title,
      notes: body?.description,
      windowStartDate: body?.windowStartDate,
      windowEndDate: body?.windowEndDate,
      timezone: body?.timezone,
      location: { title: body?.location || '' },
      priority: body?.priority || 1,
      enableConference:
        !!body?.conferenceApp || !!defaultMeetingPreferences?.conferenceApp,
      conferenceApp:
        body?.conferenceApp || defaultMeetingPreferences?.conferenceApp,
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
      guestsCanSeeOtherGuests:
        defaultMeetingPreferences?.guestsCanSeeOtherGuests,
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

    await createHostAttendee(
      body?.userId,
      meetingId,
      body?.timezone,
      primaryHostAttendeeInfo?.email,
      primaryHostAttendeeInfo?.name
    );

    await createMeetingAssistInvitees(invitees);

    const inviteeEmails = convertInviteeTypeToInviteEmailRecipients(
      invitees,
      meetingId
    );

    await sendMeetingInfoToHostEmail(
      inviteeEmails,
      user?.email || '',
      primaryHostAttendeeInfo?.name || user?.name || '',
      body?.title,
      body?.description,
      dayjs(windowStartDate).format(),
      dayjs(windowEndDate).format(),
      body?.timezone
    );

    const filteredInviteeEmails = inviteeEmails?.filter((i) => !!i?.email);

    await sendBulkMeetingInviteEmail(
      filteredInviteeEmails,
      user?.email || '',
      primaryHostAttendeeInfo?.name || user?.name || ''
    );

    // success response
    response.query = 'completed';

    response.data =
      'Successfully sent an email to invitees to get availability and time preferences for finding a meeting time';

    return response;
  } catch (e) {
    console.log(e, ' unable to final step fmtwp');
  }
};

export const processFMTWPPending = async (
  userId: string,
  timezone: string,
  jsonBody: UserInputToJSONType,
  dateJSONBody: DateTimeJSONType,
  currentTime: string
): Promise<ResponseActionType> => {
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

    const missingFields: RequiredFieldsType = {
      required: [],
      dateTime: { required: [] },
    };

    const response: any = {
      query: '',
      data: {},
      skill: 'findMeetingTimeWithPermission',
    };

    const windowStartDate = extrapolateStartDateFromJSONData(
      currentTime,
      timezone,
      yearStart,
      monthStart,
      dayStart,
      isoWeekdayStart,
      hourStart,
      minuteStart,
      startTimeStart,
      dateJSONBody?.findTimeWindowStart?.relativeTimeChangeFromNow,
      dateJSONBody?.findTimeWindowStart?.relativeTimeFromNow
    );

    const windowEndDate = extrapolateEndDateFromJSONData(
      currentTime,
      timezone,
      yearEnd,
      monthEnd,
      dayEnd,
      isoWeekdayEnd,
      hourEnd,
      minuteEnd,
      endTimeEnd,
      dateJSONBody?.findTimeWindowEnd?.relativeTimeChangeFromNow,
      dateJSONBody?.findTimeWindowEnd?.relativeTimeFromNow
    );

    // get default values
    const defaultMeetingPreferences =
      await getChatMeetingPreferenceGivenUserId(userId);

    if (dateJSONBody?.duration) {
      duration = dateJSONBody?.duration;
    } else if (defaultMeetingPreferences?.duration) {
      duration = defaultMeetingPreferences?.duration;
    } else {
      duration = 30;
    }

    // take care of any recurring dates
    let recurObject: RecurrenceRuleType | {} = {};
    if (dateJSONBody?.recur?.frequency) {
      const recurEndDate = extrapolateDateFromJSONData(
        currentTime,
        timezone,
        dateJSONBody?.recur?.endDate?.year,
        dateJSONBody?.recur?.endDate?.month,
        dateJSONBody?.recur?.endDate?.day,
        dateJSONBody?.recur?.endDate?.isoWeekday,
        dateJSONBody?.recur?.endDate?.hour,
        dateJSONBody?.recur?.endDate?.minute,
        dateJSONBody?.recur?.endDate?.startTime,
        dateJSONBody?.recur?.endDate?.relativeTimeChangeFromNow,
        dateJSONBody?.recur?.endDate?.relativeTimeFromNow
      );

      recurObject = {
        frequency:
          (dateJSONBody?.recur?.frequency as RecurrenceFrequencyType) ||
          jsonBody?.params?.recurrence?.frequency,
        interval:
          dateJSONBody?.recur?.interval ||
          jsonBody?.params?.recurrence?.interval,
      };

      if (dateJSONBody?.recur?.byWeekDay) {
        (recurObject as RecurrenceRuleType).byWeekDay =
          dateJSONBody?.recur?.byWeekDay;
      }

      if (dateJSONBody?.recur?.byMonthDay) {
        (recurObject as RecurrenceRuleType).byMonthDay =
          dateJSONBody?.recur?.byMonthDay;
      }

      if (dateJSONBody?.recur?.occurrence) {
        (recurObject as RecurrenceRuleType).occurrence =
          dateJSONBody?.recur?.occurrence;
      }

      if (recurEndDate || jsonBody?.params?.recurrence?.endDate) {
        (recurObject as RecurrenceRuleType).endDate =
          recurEndDate || jsonBody?.params?.recurrence?.endDate;
      }
    }

    const body: FindMeetingTimeWithPermissionType = {
      userId,
      timezone,
      title:
        jsonBody?.params?.title ||
        jsonBody?.params?.summary ||
        jsonBody?.params?.description ||
        jsonBody?.params?.taskList?.[0]?.task,
      attendees: jsonBody?.params?.attendees,
      method: dateJSONBody?.method as any,
      duration,
      description: jsonBody?.params?.description || jsonBody?.params?.notes,
      conferenceApp:
        jsonBody?.params?.conference?.app ||
        defaultMeetingPreferences?.conferenceApp,
      windowStartDate:
        jsonBody?.params?.startTime || windowStartDate || currentTime,
      windowEndDate:
        jsonBody?.params?.endTime ||
        windowEndDate ||
        dayjs(currentTime).add(7, 'd').format(),
      bufferTime:
        jsonBody?.params?.bufferTime || defaultMeetingPreferences?.bufferTime,
      reminders:
        jsonBody?.params?.alarms || defaultMeetingPreferences?.reminders || [],
      priority: jsonBody?.params?.priority || 1,
      timePreferences: dateJSONBody?.timePreferences || [],
      location: jsonBody?.params?.location,
      transparency: jsonBody?.params?.transparency,
      visibility: jsonBody?.params.visibility,
    };

    if (
      (recurObject as RecurrenceRuleType)?.frequency as RecurrenceFrequencyType
    ) {
      body.recur = recurObject as any;
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
    const newAttendees: MutatedCalendarExtractedJSONAttendeeType[] = [];

    for (const a of body?.attendees) {
      if (!a?.email) {
        const contact = await getContactByNameWithUserId(
          userId,
          `%${a?.name}%`
        );
        if (contact?.emails?.[0]?.value) {
          const primaryEmail = contact?.emails?.find((e) => !!e.primary)?.value;
          const anyEmail = contact?.emails?.[0]?.value;
          newAttendees.push({ ...a, email: primaryEmail || anyEmail });
        } else {
          response.query = 'missing_fields';
          missingFields.required.push(
            requiredFields.required?.[1]?.['and']?.[2]
          );
          response.data = missingFields;
          response.prevData = body;
          // response.prevDataExtra = {
          //     windowStartDate,
          //     windowEndDate,
          // }
          response.prevJsonBody = jsonBody;
          response.prevDateJsonBody = dateJSONBody;
        }
      } else {
        newAttendees.push(a);
      }
    }

    body.attendees = newAttendees;

    const meetingId = uuid();

    // get host info
    const userContactInfos = await listUserContactInfosGivenUserId(userId);

    // check if any host info
    const providedHostInfo = body?.attendees?.find((a) => a?.isHost === true);

    const primaryInfoItem = userContactInfos?.find(
      (u) => u.primary && u.type === 'email'
    );

    const user = await getUserGivenId(userId);

    const primaryHostAttendeeInfo: MutatedCalendarExtractedJSONAttendeeType = {
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

    const response2 = await finalStepFMTWP(
      body,
      primaryHostAttendeeInfo,
      defaultMeetingPreferences,
      user,
      meetingId,
      windowStartDate,
      windowEndDate,
      response
    );

    return response2;
    // get primary calendar
    // const primaryCalendar = await getGlobalCalendar(userId)
  } catch (e) {
    console.log(e, ' unable to process find meeting time');
  }
};

export const processFMTWPMissingFieldsReturned = async (
  userId: string,
  timezone: string,
  jsonBody: UserInputToJSONType,
  dateJSONBody: DateTimeJSONType,
  currentTime: string,
  messageHistoryObject: SkillMessageHistoryType
) => {
  try {
    let duration = 0;

    const yearStart =
      dateJSONBody?.findTimeWindowStart?.year ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.year;
    const monthStart =
      dateJSONBody?.findTimeWindowStart?.month ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.month;
    const dayStart =
      dateJSONBody?.findTimeWindowStart?.day ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.day;
    const isoWeekdayStart =
      dateJSONBody?.findTimeWindowStart?.isoWeekday ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.isoWeekday;
    const hourStart =
      dateJSONBody?.findTimeWindowStart?.hour ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.hour;
    const minuteStart =
      dateJSONBody?.findTimeWindowStart?.minute ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.minute;
    const startTimeStart =
      dateJSONBody?.findTimeWindowStart?.startTime ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.startTime;

    const yearEnd =
      dateJSONBody?.findTimeWindowEnd?.year ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.year;
    const monthEnd =
      dateJSONBody?.findTimeWindowEnd?.month ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.month;
    const dayEnd =
      dateJSONBody?.findTimeWindowEnd?.day ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.day;
    const isoWeekdayEnd =
      dateJSONBody?.findTimeWindowEnd?.isoWeekday ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.isoWeekday;
    const hourEnd =
      dateJSONBody?.findTimeWindowEnd?.hour ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.hour;
    const minuteEnd =
      dateJSONBody?.findTimeWindowEnd?.minute ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.minute;
    const endTimeEnd =
      dateJSONBody?.findTimeWindowEnd?.startTime ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.startTime;

    const missingFields: RequiredFieldsType = {
      required: [],
      dateTime: { required: [] },
    };

    const response: any = {
      query: '',
      data: {},
      skill: 'findMeetingTimeWithPermission',
    };

    const windowStartDate = extrapolateStartDateFromJSONData(
      currentTime,
      timezone,
      yearStart,
      monthStart,
      dayStart,
      isoWeekdayStart,
      hourStart,
      minuteStart,
      startTimeStart,
      dateJSONBody?.findTimeWindowStart?.relativeTimeChangeFromNow ||
        messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart
          ?.relativeTimeChangeFromNow,
      dateJSONBody?.findTimeWindowStart?.relativeTimeFromNow ||
        messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart
          ?.relativeTimeFromNow
    );

    const windowEndDate = extrapolateEndDateFromJSONData(
      currentTime,
      timezone,
      yearEnd,
      monthEnd,
      dayEnd,
      isoWeekdayEnd,
      hourEnd,
      minuteEnd,
      endTimeEnd,
      dateJSONBody?.findTimeWindowEnd?.relativeTimeChangeFromNow,
      dateJSONBody?.findTimeWindowEnd?.relativeTimeFromNow
    );

    // get default values
    const defaultMeetingPreferences =
      await getChatMeetingPreferenceGivenUserId(userId);

    if (
      dateJSONBody?.duration ||
      messageHistoryObject?.prevDateJsonBody?.duration
    ) {
      duration =
        dateJSONBody?.duration ||
        messageHistoryObject?.prevDateJsonBody?.duration;
    } else if (defaultMeetingPreferences?.duration) {
      duration = defaultMeetingPreferences?.duration;
    } else {
      duration = 30;
    }

    // take care of any recurring dates
    let recurObject: RecurrenceRuleType | {} = {};
    if (
      dateJSONBody?.recur?.frequency ||
      messageHistoryObject?.prevDateJsonBody?.recur?.frequency
    ) {
      const recurEndDate = extrapolateDateFromJSONData(
        currentTime,
        timezone,
        dateJSONBody?.recur?.endDate?.year ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.year,
        dateJSONBody?.recur?.endDate?.month ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.month,
        dateJSONBody?.recur?.endDate?.day ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.day,
        dateJSONBody?.recur?.endDate?.isoWeekday ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.isoWeekday,
        dateJSONBody?.recur?.endDate?.hour ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.hour,
        dateJSONBody?.recur?.endDate?.minute ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.minute,
        dateJSONBody?.recur?.endDate?.startTime ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.startTime,
        dateJSONBody?.recur?.endDate?.relativeTimeChangeFromNow ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate
            ?.relativeTimeChangeFromNow,
        dateJSONBody?.recur?.endDate?.relativeTimeFromNow ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate
            ?.relativeTimeFromNow
      );

      recurObject = {
        frequency:
          (dateJSONBody?.recur?.frequency as RecurrenceFrequencyType) ||
          messageHistoryObject?.prevDateJsonBody?.recur?.frequency,
        interval:
          dateJSONBody?.recur?.interval ||
          messageHistoryObject?.prevDateJsonBody?.recur?.interval,
      };

      if (
        dateJSONBody?.recur?.byWeekDay ||
        messageHistoryObject?.prevDateJsonBody?.recur?.byWeekDay
      ) {
        (recurObject as RecurrenceRuleType).byWeekDay =
          dateJSONBody?.recur?.byWeekDay ||
          messageHistoryObject?.prevDateJsonBody?.recur?.byWeekDay;
      }

      if (
        dateJSONBody?.recur?.byMonthDay ||
        messageHistoryObject?.prevDateJsonBody?.recur?.byMonthDay
      ) {
        (recurObject as RecurrenceRuleType).byMonthDay =
          dateJSONBody?.recur?.byMonthDay ||
          messageHistoryObject?.prevDateJsonBody?.recur?.byMonthDay;
      }

      if (
        dateJSONBody?.recur?.occurrence ||
        messageHistoryObject?.prevDateJsonBody?.recur?.occurrence
      ) {
        (recurObject as RecurrenceRuleType).occurrence =
          dateJSONBody?.recur?.occurrence ||
          messageHistoryObject?.prevDateJsonBody?.recur?.occurrence;
      }

      if (
        recurEndDate ||
        messageHistoryObject?.prevJsonBody?.params?.recurrence?.endDate ||
        jsonBody?.params?.recurrence?.endDate
      ) {
        (recurObject as RecurrenceRuleType).endDate =
          recurEndDate ||
          messageHistoryObject?.prevJsonBody?.params?.recurrence?.endDate ||
          jsonBody?.params?.recurrence?.endDate;
      }
    }

    const newBody: FindMeetingTimeWithPermissionType = {
      userId,
      timezone,
      title:
        jsonBody?.params?.title ||
        jsonBody?.params?.summary ||
        jsonBody?.params?.description ||
        jsonBody?.params?.taskList?.[0]?.task ||
        messageHistoryObject?.prevJsonBody?.params?.title ||
        messageHistoryObject?.prevJsonBody?.params?.summary ||
        messageHistoryObject?.prevJsonBody?.params?.description ||
        messageHistoryObject?.prevJsonBody?.params?.taskList?.[0]?.task,
      attendees:
        jsonBody?.params?.attendees ||
        messageHistoryObject?.prevJsonBody?.params?.attendees,
      method: dateJSONBody?.method as any,
      duration,
      description:
        jsonBody?.params?.description ||
        jsonBody?.params?.notes ||
        messageHistoryObject?.prevJsonBody?.params?.description ||
        messageHistoryObject?.prevJsonBody?.params?.notes,
      conferenceApp:
        jsonBody?.params?.conference?.app ||
        messageHistoryObject?.prevJsonBody?.params?.conference?.app ||
        defaultMeetingPreferences?.conferenceApp,
      windowStartDate:
        jsonBody?.params?.startTime ||
        messageHistoryObject?.prevJsonBody?.params?.startTime ||
        windowStartDate ||
        currentTime,
      windowEndDate:
        jsonBody?.params?.endTime ||
        messageHistoryObject?.prevJsonBody?.params?.endTime ||
        windowEndDate ||
        dayjs(currentTime).add(7, 'd').format(),
      bufferTime:
        jsonBody?.params?.bufferTime ||
        messageHistoryObject?.prevJsonBody?.params?.bufferTime ||
        defaultMeetingPreferences?.bufferTime,
      reminders:
        jsonBody?.params?.alarms ||
        messageHistoryObject?.prevJsonBody?.params?.alarms ||
        defaultMeetingPreferences?.reminders ||
        [],
      priority:
        jsonBody?.params?.priority ||
        messageHistoryObject?.prevJsonBody?.params?.priority ||
        1,
      timePreferences:
        dateJSONBody?.timePreferences ||
        messageHistoryObject?.prevDateJsonBody?.timePreferences ||
        [],
      location:
        jsonBody?.params?.location ||
        messageHistoryObject?.prevJsonBody?.params?.location,
      transparency:
        jsonBody?.params?.transparency ||
        messageHistoryObject?.prevJsonBody?.params?.transparency,
      visibility:
        jsonBody?.params.visibility ||
        messageHistoryObject?.prevJsonBody?.params?.visibility,
    };

    if (
      (recurObject as RecurrenceRuleType)?.frequency as RecurrenceFrequencyType
    ) {
      newBody.recur = recurObject as any;
    }

    const prevBody: FindMeetingTimeWithPermissionType = {
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
    const newAttendees: MutatedCalendarExtractedJSONAttendeeType[] = [];

    for (const a of newBody?.attendees) {
      if (!a?.email) {
        const contact = await getContactByNameWithUserId(
          userId,
          `%${a?.name}%`
        );
        if (contact?.emails?.[0]?.value) {
          const primaryEmail = contact?.emails?.find((e) => !!e.primary)?.value;
          const anyEmail = contact?.emails?.[0]?.value;
          newAttendees.push({ ...a, email: primaryEmail || anyEmail });
        } else {
          response.query = 'missing_fields';
          missingFields.required.push(
            requiredFields.required?.[1]?.['and']?.[2]
          );
          response.data = missingFields;
          response.prevData = prevBody;
          response.prevJsonBody = jsonBody;
          response.prevDateJsonBody = dateJSONBody;
        }
      } else {
        newAttendees.push(a);
      }
    }

    newBody.attendees = newAttendees;

    if (!(prevBody?.attendees?.length > 0)) {
      prevBody.attendees = newBody?.attendees;
    }

    const meetingId: string = uuid();

    // get host info
    const userContactInfos = await listUserContactInfosGivenUserId(userId);

    // check if any host info
    const newProvidedHostInfo = newBody?.attendees?.find(
      (a) => a?.isHost === true
    );

    const prevProvidedHostInfo = prevBody?.attendees?.find(
      (a) => a?.isHost === true
    );

    const primaryInfoItem = userContactInfos?.find(
      (u) => u.primary && u.type === 'email'
    );

    const user = await getUserGivenId(userId);

    const primaryHostAttendeeInfo: MutatedCalendarExtractedJSONAttendeeType = {
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

    const prevHostInfo =
      prevProvidedHostInfo || newProvidedHostInfo || primaryHostAttendeeInfo;

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

    const response2 = await finalStepFMTWP(
      prevBody,
      primaryHostAttendeeInfo,
      defaultMeetingPreferences,
      user,
      meetingId,
      prevBody?.windowStartDate,
      prevBody?.windowEndDate,
      response
    );

    return response2;
  } catch (e) {
    console.log(e, ' unable to process fmtwp MissingFieldsReturned');
  }
};

export const FMTWPControlCenter = async (
  openai: OpenAI,
  userId: string,
  timezone: string,
  messageHistoryObject: SkillMessageHistoryType,
  userCurrentTime: string,
  query: 'missing_fields' | 'completed' | 'event_not_found' | 'pending'
) => {
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

    let fmtwpRes: ResponseActionType = {
      query: 'completed',
      data: '',
      skill: '',
      prevData: {},
      prevDataExtra: {},
    };

    switch (query) {
      case 'pending':
        const jsonBody = await generateJSONDataFromUserInput(
          userInput,
          userCurrentTime
        );
        const dateTime = await generateDateTime(
          userInput,
          userCurrentTime,
          timezone
        );
        fmtwpRes = await processFMTWPPending(
          userId,
          timezone,
          jsonBody,
          dateTime,
          userCurrentTime
        );
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
        const jsonMissingFieldsBody =
          await generateMissingFieldsJSONDataFromUserInput(
            userInput,
            priorUserInput,
            priorAssistantOutput,
            userCurrentTime
          );
        const dateMissingFieldsTime = await generateMissingFieldsDateTime(
          userInput,
          priorUserInput,
          priorAssistantOutput,
          userCurrentTime,
          timezone
        );

        fmtwpRes = await processFMTWPMissingFieldsReturned(
          userId,
          timezone,
          jsonMissingFieldsBody,
          dateMissingFieldsTime,
          userCurrentTime,
          messageHistoryObject
        );
        break;
    }

    if (fmtwpRes?.query === 'completed') {
      const assistantMessage =
        await generateAssistantMessageFromAPIResponseForUserQuery(
          openai,
          fmtwpRes.data as string,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'completed';
      messageHistoryObject.required = null;
    } else if (fmtwpRes?.query === 'missing_fields') {
      const assistantMessage =
        await generateAssistantMessageToRequestUserForMissingFields(
          openai,
          fmtwpRes?.data as RequiredFieldsType,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'missing_fields';
      messageHistoryObject.required = fmtwpRes?.data as RequiredFieldsType;
      messageHistoryObject.prevData = fmtwpRes?.prevData;
      messageHistoryObject.prevDataExtra = fmtwpRes?.prevDataExtra;
      messageHistoryObject.prevDateJsonBody = fmtwpRes?.prevDateJsonBody;
      messageHistoryObject.prevJsonBody = fmtwpRes?.prevJsonBody;
    } else if (fmtwpRes?.query === 'event_not_found') {
      const assistantMessage: AssistantMessageType = {
        role: 'assistant',
        content: 'Oops... something went wrong. Sorry :(',
      };

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'event_not_found';
      messageHistoryObject.required = null;
    }

    return messageHistoryObject;
  } catch (e) {
    console.log(
      e,
      ' unable to find meeting time with permission control center pending'
    );
  }
};
