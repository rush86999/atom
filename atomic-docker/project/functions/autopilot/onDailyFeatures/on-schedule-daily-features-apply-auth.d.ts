import { Request, Response } from 'express';
import { AutopilotApiResponse } from '@autopilot/_libs/types';
interface SuccessPayload {
    message: string;
    details?: any;
}
declare const handler: (req: Request, res: Response<AutopilotApiResponse<SuccessPayload | null>>) => Promise<Response<AutopilotApiResponse<SuccessPayload | null>, Record<string, any>>>;
export default handler;
