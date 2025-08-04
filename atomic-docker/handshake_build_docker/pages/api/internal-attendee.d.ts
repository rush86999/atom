import { MeetingAssistAttendeeType, MeetingAssistType, UserContactInfoType } from '@lib/types';
import type { NextApiRequest, NextApiResponse } from 'next';
export default function handler(req: NextApiRequest, res: NextApiResponse<MeetingAssistType | MeetingAssistAttendeeType | UserContactInfoType | undefined>): Promise<any>;
