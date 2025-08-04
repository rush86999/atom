import { Request, Response } from 'express';
import { CalendarWebhookHeaders } from '../_libs/types/googleCalendarWebhook/types';
declare const handler: (req: Request & {
    headers: CalendarWebhookHeaders;
}, res: Response) => Promise<Response<any, Record<string, any>>>;
export default handler;
