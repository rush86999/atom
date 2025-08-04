import { Request, Response } from 'express';
import { performCalendarSync } from '../_libs/sync-logic';

const handler = async (req: Request, res: Response) => {
  try {
    console.log(req, ' event');
    // custom validation
    /**
      axios post Body - stringified
      {
        calendarIntegrationId: string,
        calendarId: string,
        userId: string,
        eventTriggerId: string,
        isInitialSync: boolean,
        timezone: string,
      }
     */
    const bodyObj = req.body;
    console.log(req?.body, ' axios post');

    const { calendarIntegrationId, calendarId, userId, timezone } = bodyObj;

    // Basic validation for required parameters
    if (!calendarIntegrationId) {
      return res
        .status(400)
        .json({ message: 'no calendarIntegrationId found', event: bodyObj });
    }
    if (!calendarId) {
      return res
        .status(400)
        .json({ message: 'no calendarId found', event: bodyObj });
    }
    if (!userId) {
      return res
        .status(400)
        .json({ message: 'no userId found', event: bodyObj });
    }
    if (!timezone) {
      return res
        .status(400)
        .json({ message: 'no timezone present', event: bodyObj });
    }

    const syncResult = await performCalendarSync({
      calendarIntegrationId,
      calendarId,
      userId,
      timezone,
    });

    return res.status(syncResult.status).json({
      message: syncResult.message,
      event: bodyObj, // Consider if you want to return the original request body or parts of syncResult
    });
  } catch (e) {
    console.log(e, ' unable sync google calendar');
    // Ensure bodyObj is defined in catch scope if you need to use it
    const bodyObj = req.body;
    return res.status(400).json({
      message: `error processing googleCalendarSync: message: ${e?.message}, code: ${e?.code}`, // Assuming error object might have a 'code'
      event: bodyObj, // Or e, depending on what's more useful for debugging
    });
  }
};

export default handler;
