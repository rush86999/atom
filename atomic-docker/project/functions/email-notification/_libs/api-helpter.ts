import dayjs from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import {
  BulkMeetingCancelledDetailsToAttendeeType,
  BulkMeetingInviteDetailsToAttendeeType,
  MeetingInviteDetailsToHostType,
} from '@email_notification/_libs/types';
import { EMAIL } from './constants';
import { sendEmail } from '@/_utils/email/email';
import { ENV } from '@/_utils/env';

dayjs.extend(isoWeek);
dayjs.extend(duration);
dayjs.extend(isBetween);
dayjs.extend(timezone);
dayjs.extend(utc);

export const sendMeetingInviteDetailsToHost = async (
  meetingInvite: MeetingInviteDetailsToHostType
) => {
  try {
    const attendees = meetingInvite?.attendees;
    const hostName = meetingInvite?.hostName;
    const hostEmail = meetingInvite?.hostEmail;
    const title = meetingInvite?.title;
    const notes = meetingInvite?.notes;
    const windowStartDate = meetingInvite?.windowStartDate;
    const windowEndDate = meetingInvite?.windowEndDate;
    const timezone = meetingInvite?.timezone;

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
    console.log(e, ' unable to send meeting details to host');
  }
};

export const sendBulkCancelToMeetingEmail = async (
  meetingCancel: BulkMeetingCancelledDetailsToAttendeeType
) => {
  try {
    const attendees = meetingCancel?.attendees;
    const hostName = meetingCancel?.hostName;
    const hostEmail = meetingCancel?.hostEmail;

    // validate
    if (!(attendees?.length > 0)) {
      throw new Error('no attendees provided');
    }

    if (!hostName) {
      throw new Error('no hostName provided');
    }

    if (!hostEmail) {
      throw new Error('no hostEmail provided');
    }

    for (const attendee of attendees) {
      const template = 'meeting-invite-details-to-host';

      const response = await sendEmail({
        template,
        locals: {
          name: attendee?.name,
          hostEmail,
          hostName,
          displayName: hostName,
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

      console.log(
        response,
        ' successfully sent bulk emails for meeting cancel info to attendees'
      );
    }
  } catch (e) {
    console.log(e, ' unable to send bulk cancel meeting');
  }
};

export const sendBulkInviteToMeetingEmail = async (
  meetingInvite: BulkMeetingInviteDetailsToAttendeeType
) => {
  try {
    const attendees = meetingInvite?.attendees;
    const hostName = meetingInvite?.hostName;
    const hostEmail = meetingInvite?.hostEmail;

    // validate
    if (!(attendees?.length > 0)) {
      throw new Error('no attendees provided');
    }

    if (!hostName) {
      throw new Error('no hostName provided');
    }

    if (!hostEmail) {
      throw new Error('no hostEmail provided');
    }

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
    console.log(e, ' unable to send bulk invite to meeting email');
  }
};
