import type { NextApiRequest, NextApiResponse } from 'next';
type MeetingAttendanceStatus = {
    task_id: string;
    user_id: string | null;
    platform: string | null;
    meeting_identifier: string | null;
    status_timestamp: string;
    current_status_message: string;
    final_notion_page_url: string | null;
    error_details: string | null;
    created_at: string;
};
type ErrorResponse = {
    error: string;
    details?: string;
};
export default function handler(req: NextApiRequest, res: NextApiResponse<MeetingAttendanceStatus | MeetingAttendanceStatus[] | ErrorResponse>): Promise<void>;
export {};
