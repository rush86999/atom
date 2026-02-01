import { Logger } from "../utils/logger";

export interface FollowUpCandidate {
    id: string;
    recipient: string;
    subject: string;
    original_sent_at: string;
    days_since_sent: number;
    thread_id?: string;
    last_message_snippet: string;
    suggested_draft?: string;
}

/**
 * Skill to manage and automate email follow-ups.
 */
export class EmailFollowUpSkill {
    private logger: Logger;

    constructor() {
        this.logger = new Logger("EmailFollowUpSkill");
    }

    /**
     * Fetches candidates for follow-up from the backend.
     */
    public async getFollowUpCandidates(): Promise<FollowUpCandidate[]> {
        this.logger.info("Fetching email follow-up candidates...");
        try {
            const response = await fetch('/api/v1/analytics/email-followups');
            if (!response.ok) throw new Error("Failed to fetch follow-up candidates");
            return await response.json();
        } catch (err) {
            this.logger.error("Error fetching follow-up candidates", err);
            return [];
        }
    }

    /**
     * Drafts a polite follow-up nudge using AI.
     */
    public async draftFollowUp(candidate: FollowUpCandidate): Promise<string> {
        this.logger.info(`Drafting follow-up for: ${candidate.id}`);

        // In a real app, this would use the LLMService
        // Mocking an AI draft:
        return `Hi there,\n\nI'm just following up on my previous email regarding "${candidate.subject}". I assume you've been busy, but I wanted to make sure this stayed on your radar. Looking forward to hearing from you!\n\nBest, [Your Name]`;
    }

    /**
     * Executes the sending of a follow-up email.
     */
    public async sendFollowUp(emailId: string, body: string): Promise<{ success: boolean; message: string }> {
        this.logger.info(`Sending follow-up for email ${emailId}...`);
        try {
            const response = await fetch('/api/email/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    to: "placeholder@example.com", // In real app, fetch from emailId
                    subject: "Re: Following up",
                    body: body
                })
            });

            if (!response.ok) throw new Error("Failed to send follow-up");

            return { success: true, message: "Follow-up sent successfully!" };
        } catch (err) {
            this.logger.error("Error sending follow-up", err);
            return { success: false, message: "Failed to send follow-up" };
        }
    }
}

export const emailFollowUpSkill = new EmailFollowUpSkill();
