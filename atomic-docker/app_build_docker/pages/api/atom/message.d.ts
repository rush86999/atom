import type { NextApiRequest, NextApiResponse } from 'next';
import { HandleMessageResponse } from '../../../../project/functions/atom-agent/handler';
type Data = HandleMessageResponse;
export default function handler(req: NextApiRequest, res: NextApiResponse<Data>): Promise<void | NextApiResponse<HandleMessageResponse>>;
export {};
