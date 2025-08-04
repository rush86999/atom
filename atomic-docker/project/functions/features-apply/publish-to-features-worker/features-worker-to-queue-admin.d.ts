import { Request, Response } from 'express';
import { FeaturesApplyResponse } from '../_libs/types';
interface SuccessPayload {
    message: string;
    messageId?: string;
}
declare const publisher: (req: Request, res: Response<FeaturesApplyResponse<SuccessPayload>>) => Promise<Response<FeaturesApplyResponse<SuccessPayload>, Record<string, any>>>;
export default publisher;
