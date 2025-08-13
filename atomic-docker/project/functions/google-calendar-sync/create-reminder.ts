import { Request, Response } from 'express';
import { createGoogleEvent } from './_libs/api-helper';

const handler = async (req: Request, res: Response) => {
  try {
    const { session_variables, input } = req.body;
    const userId = session_variables['x-hasura-user-id'];
    const { summary, dateTime, minutesBefore } = input;

    if (!userId || !summary || !dateTime || !minutesBefore) {
      return res.status(400).json({ message: 'Missing required parameters' });
    }

    const reminders = {
      useDefault: false,
      overrides: [{ method: 'popup', minutes: minutesBefore }],
    };

    const result = await createGoogleEvent(
      userId,
      'primary', // calendarId
      'atomic-web', // clientType
      undefined, // generatedId
      dateTime, // endDateTime
      dateTime, // startDateTime
      1, // conferenceDataVersion
      undefined, // maxAttendees
      'all', // sendUpdates
      undefined, // anyoneCanAddSelf
      [], // attendees
      undefined, // conferenceData
      summary,
      `Reminder set for ${dateTime}`, // description
      'UTC', // timezone
      undefined, // startDate
      undefined, // endDate
      undefined, // extendedProperties
      undefined, // guestsCanInviteOthers
      undefined, // guestsCanModify
      undefined, // guestsCanSeeOtherGuests
      undefined, // originalStartDateTime
      undefined, // originalStartDate
      undefined, // recurrence
      reminders,
      undefined, // source
      'confirmed', // status
      'transparent', // transparency
      'private', // visibility
      undefined, // iCalUID
      undefined, // attendeesOmitted
      undefined, // hangoutLink
      true, // privateCopy
      true, // locked
      undefined, // attachments
      'default', // eventType
      undefined, // location
      undefined // colorId
    );

    return res.status(200).json(result);
  } catch (e) {
    console.error(e, ' unable to create google calendar reminder event');
    return res.status(500).json({ message: 'Internal Server Error' });
  }
};

export default handler;
