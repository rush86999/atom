import { Request, Response } from 'express';

import { v4 as uuidv4 } from 'uuid';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';

import {
  deleteCalendarWebhookById,
  getCalendarWebhookById,
  requestCalendarWatch,
  insertCalendarWebhook,
} from '@google_calendar_sync/_libs/api-helper';

dayjs.extend(utc);
dayjs.extend(timezone);

const handler = async (req: Request, res: Response) => {
  try {
    console.log(req, ' req');
    const body = req.body;

    // validate
    const calendarId = body?.calendarId;
    const userId = body?.userId;
    const channelId = body?.channelId;

    if (!calendarId) {
      console.log('calendarId is missing');
      return res.status(400).json({
        message: 'calendarId missing',
        event: body,
      });
    }

    if (!userId) {
      console.log('userId is missing');
      return res.status(400).json({
        message: 'userId is missing',
        event: body,
      });
    }

    if (!channelId) {
      console.log('channelId is missing');
      return res.status(400).json({
        message: 'channelId is missing',
        event: body,
      });
    }

    const webhook = await getCalendarWebhookById(channelId);

    // validate
    const token = uuidv4();
    const newChannelId = uuidv4();
    console.log(newChannelId, ' newChannelId');
    const response = await requestCalendarWatch(
      calendarId,
      newChannelId,
      token,
      userId
    );

    await deleteCalendarWebhookById(channelId);

    await insertCalendarWebhook({
      calendarId: calendarId,
      createdDate: dayjs().format(),
      expiration: dayjs().add(604800, 's').format(),
      id: newChannelId,
      resourceId: response?.resourceId,
      resourceUri: response?.resourceUri,
      token,
      updatedAt: dayjs().format(),
      userId,
      calendarIntegrationId: webhook?.calendarIntegrationId,
    });

    return res.status(200).json({
      message: `successfully taken care of googleCalendaryWatch!`,
      event: body,
    });
  } catch (e) {
    console.log(e, ' unable sync google calendar');

    return res.status(400).json({
      message: `error processing googleCalendarSync: message: ${e?.message}, code: ${e?.statusCode}`,
      event: e,
    });
  }
};

export default handler;
