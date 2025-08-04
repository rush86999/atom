import { MeetingAssistAttendeeType, MeetingAssistType } from '@lib/types';
import type { NextApiRequest, NextApiResponse } from 'next';
export default function handler(req: NextApiRequest, res: NextApiResponse<MeetingAssistType | MeetingAssistAttendeeType | undefined>): Promise<any>;
