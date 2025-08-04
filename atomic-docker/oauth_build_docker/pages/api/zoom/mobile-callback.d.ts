import { CalendarIntegrationType } from '@lib/types';
import type { NextApiRequest, NextApiResponse } from 'next';
export default function handler(req: NextApiRequest, res: NextApiResponse<CalendarIntegrationType | undefined>): Promise<any>;
