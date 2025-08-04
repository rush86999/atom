import { AvailableSlotsByDate, EventType, MeetingAssistAttendeeType, MeetingAssistEventType, MeetingAssistPreferredTimeRangeType, MeetingAssistType, UserPreferenceType } from '@lib/types';
import type { NextApiRequest, NextApiResponse } from 'next';
export default function handler(req: NextApiRequest, res: NextApiResponse<EventType[] | AvailableSlotsByDate | MeetingAssistType | UserPreferenceType | MeetingAssistAttendeeType[] | MeetingAssistEventType[] | MeetingAssistPreferredTimeRangeType[] | undefined | number>): Promise<any>;
