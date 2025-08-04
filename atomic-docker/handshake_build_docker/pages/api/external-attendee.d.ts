import { MeetingAssistAttendeeType, MeetingAssistType, HandshakeApiResponse } from '@lib/types';
import type { NextApiRequest, NextApiResponse } from 'next';
export default function handler(req: NextApiRequest, res: NextApiResponse<HandshakeApiResponse<MeetingAssistType | MeetingAssistAttendeeType | {
    message: string;
}>>): Promise<any>;
