import { Request, Response } from 'express';
import { createGoogleEvent } from '../../gpt/_libs/api-helper';

interface CreateEventRequestBody {
  session_variables: {
    'x-hasura-user-id': string;
  };
  input: {
    calendarId: string;
    summary: string;
    description?: string;
    startDateTime: string;
    endDateTime: string;
    timezone: string;
  };
}

const handler = async (
  req: Request<{}, {}, CreateEventRequestBody>,
  res: Response
) => {
  const userId = req.body.session_variables['x-hasura-user-id'];
  const { calendarId, summary, description, startDateTime, endDateTime, timezone } = req.body.input;

  if (!userId || !calendarId || !summary || !startDateTime || !endDateTime || !timezone) {
    return res.status(400).json({ success: false, message: 'Missing required fields.' });
  }

  try {
    // Assuming 'web' as a default clientType for now. This might need to be passed in the request.
    const result = await createGoogleEvent(
      userId,
      calendarId,
      'web',
      summary,
      startDateTime,
      endDateTime,
      timezone,
      description
    );

    if (result.success) {
      return res.status(200).json({ success: true, data: result.data });
    } else {
      return res.status(500).json({ success: false, message: result.error.message, details: result.error.details });
    }
  } catch (e: any) {
    console.error(`Error in create-event handler for user ${userId}:`, e);
    return res.status(500).json({ success: false, message: 'An unexpected error occurred.' });
  }
};

export default handler;
