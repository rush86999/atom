import { Request, Response } from 'express';
import { createGoogleEvent } from './_libs/api-helper';

const handler = async (req: Request, res: Response) => {
  try {
    const { session_variables, input } = req.body;
    const userId = session_variables['x-hasura-user-id'];
    const { calendarId, summary, startTime, endTime, timezone } = input;

    if (!userId || !calendarId || !summary || !startTime || !endTime || !timezone) {
      return res.status(400).json({ message: 'Missing required parameters' });
    }

    const result = await createGoogleEvent(
      userId,
      calendarId,
      'atomic-web', // clientType
      undefined, // generatedId
      endTime, // endDateTime
      startTime, // startDateTime
      1, // conferenceDataVersion
      undefined, // maxAttendees
      'all', // sendUpdates
      undefined, // anyoneCanAddSelf
      [], // attendees
      { createRequest: { conferenceSolutionKey: { type: 'hangoutsMeet' }, requestId: 'workflow-automation' } }, // conferenceData
      summary,
      '', // description
      timezone
    );

    return res.status(200).json(result);
  } catch (e) {
    console.error(e, ' unable to create google calendar event');
    return res.status(500).json({ message: 'Internal Server Error' });
  }
};

export default handler;
