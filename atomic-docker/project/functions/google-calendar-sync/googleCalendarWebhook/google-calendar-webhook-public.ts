import { Request, Response } from 'express';

import {
  getCalendarWebhookById,
  getGoogleAPIToken,
  getGoogleCalendarInDb,
  getGoogleColor,
  getGoogleIntegration,
  incrementalGoogleCalendarSync2,
  updateGoogleIntegration,
} from '@google_calendar_sync/_libs/api-helper';
import { googleCalendarResource } from '@google_calendar_sync/_libs/constants';
import { CalendarWebhookHeaders } from '../_libs/types/googleCalendarWebhook/types';

const handler = async (
  req: Request & { headers: CalendarWebhookHeaders },
  res: Response
) => {
  try {
    console.log(req, ' req');
    const headers: CalendarWebhookHeaders = req.headers;

    if (headers['X-Goog-Resource-State'] === 'sync') {
      return res.status(200).json({
        message: 'sync received successfully',
        event: req.body,
      });
    }

    //
    const channelId = headers['X-Goog-Channel-ID'];

    const webhook = await getCalendarWebhookById(channelId);

    // validate
    const token = headers['X-Goog-Channel-Token'];

    if (webhook?.token !== token) {
      console.log(webhook?.token, token, ' both tokens are not equal exit');
      return res.status(400).json({
        message: 'tokens are not equal',
        event: req.body,
      });
    }

    // start incremental sync

    const googleIntegration = await getGoogleIntegration(
      webhook?.calendarIntegrationId
    );
    const clientType = googleIntegration?.clientType;

    if (!clientType) {
      return res.status(400).json({
        message: 'clientType is not available',
        event: req.body,
      });
    }

    const calendarInDb = await getGoogleCalendarInDb(webhook?.calendarId);

    const pageToken = calendarInDb?.pageToken;
    const syncToken = calendarInDb?.syncToken;

    const authToken = await getGoogleAPIToken(
      webhook?.userId,
      googleCalendarResource,
      clientType
    );

    const colorItem = await getGoogleColor(authToken);
    console.log(colorItem, ' colorItem inside googleCalendarSync');

    if (!calendarInDb?.id) {
      console.log(calendarInDb?.id, '-id, calendar was deleted');
      return res.status(400).json({
        message: `${calendarInDb?.id} -id, calendar was deleted`,
        event: req.body,
      });
    }

    const syncEnabled = await incrementalGoogleCalendarSync2(
      webhook?.calendarId,
      webhook?.userId,
      clientType,
      syncToken,
      pageToken,
      colorItem
    );

    // if sync is not enabled let the user go through oauth again if needed
    if (syncEnabled === false) {
      await updateGoogleIntegration(
        webhook?.calendarIntegrationId,
        syncEnabled
      );
      return res.status(200).json({
        message: `sync is disabled for googleCalendarSync`,
        event: req.body,
      });
    }

    return res.status(200).json({
      message: `successfully taken care of googleCalendarySync!`,
      event: req.body,
    });
  } catch (e) {
    console.log(e, ' unable sync google calendar');

    return res.status(400).json({
      message: `error processing googleCalendarSync: message: ${e?.message}, code: ${e?.statusCode}`,
      event: req.body,
    });
  }
};

export default handler;
