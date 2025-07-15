import { SkillResponse } from '../../types';
import { PYTHON_API_SERVICE_BASE_URL } from '../../_libs/constants';
import { handleError } from '../../_utils/errorHandler';

export async function handleMeetingPrep(userId: string, entities: any): Promise<string> {
    try {
        const { meeting_title, attendees } = entities;

        if (!meeting_title || typeof meeting_title !== 'string') {
            return "Meeting title is required to prepare a meeting briefing.";
        }

        const response = await fetch(`${PYTHON_API_SERVICE_BASE_URL}/meeting-prep`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                meeting_title,
                attendees,
            }),
        });

        if (response.ok) {
            const data = await response.json();
            return data.briefing;
        } else {
            const error = await response.json();
            return `Failed to prepare meeting briefing: ${error.error}`;
        }
    } catch (error: any) {
        return handleError(error, "Sorry, I couldn't prepare the meeting briefing due to an error.");
    }
}
