import { Logger } from "../utils/logger";

export interface ScheduleOptimization {
    type: string;
    event_to_move: string;
    event_id: string;
    conflict_with: string;
    suggested_slots: Array<{
        start: string;
        end: string;
        reason: string;
    }>;
}

/**
 * Skill to manage and optimize user schedules.
 */
export class SchedulingSkill {
    private logger: Logger;

    constructor() {
        this.logger = new Logger("SchedulingSkill");
    }

    /**
     * Fetches potential schedule optimizations (conflict resolutions).
     */
    public async getOptimizations(): Promise<ScheduleOptimization[]> {
        this.logger.info("Fetching schedule optimizations...");
        try {
            const response = await fetch('/api/v1/calendar/optimize');
            if (!response.ok) throw new Error("Failed to fetch optimizations");
            return await response.json();
        } catch (err) {
            this.logger.error("Error fetching optimizations", err);
            return [];
        }
    }

    /**
     * Resolves a specific conflict by moving an event to a new slot.
     */
    public async resolveConflict(eventId: string, newStart: string, newEnd: string): Promise<{ success: boolean; message: string }> {
        this.logger.info(`Resolving conflict for event ${eventId}...`);
        try {
            const response = await fetch(`/api/v1/calendar/events/${eventId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ start: newStart, end: newEnd })
            });

            if (!response.ok) throw new Error("Failed to update event");

            return {
                success: true,
                message: `Successfully moved event to ${new Date(newStart).toLocaleString()}`
            };
        } catch (err) {
            this.logger.error("Error resolving conflict", err);
            return { success: false, message: "Failed to resolve conflict" };
        }
    }

    /**
     * Automatically resolves all detected conflicts using the first suggestion.
     */
    public async autoResolveConflicts(): Promise<{ resolvedCount: number; errors: string[] }> {
        const optimizations = await this.getOptimizations();
        let resolvedCount = 0;
        const errors: string[] = [];

        for (const opt of optimizations) {
            if (opt.suggested_slots.length > 0) {
                const bestSlot = opt.suggested_slots[0];
                const result = await this.resolveConflict(opt.event_id, bestSlot.start, bestSlot.end);
                if (result.success) {
                    resolvedCount++;
                    // New: Notify attendees after successful move
                    await this.notifyAttendees(opt.event_id, `Meeting moved to ${new Date(bestSlot.start).toLocaleString()} to resolve a conflict.`);
                } else {
                    errors.push(`Failed to move ${opt.event_to_move}: ${result.message}`);
                }
            }
        }

        return { resolvedCount, errors };
    }

    /**
     * Notifies all attendees of a specific event.
     */
    public async notifyAttendees(eventId: string, message: string): Promise<{ success: boolean }> {
        this.logger.info(`Notifying attendees for event ${eventId}: ${message}`);
        // In a real implementation, this would:
        // 1. Fetch event from Calendar API to get attendee list
        // 2. Cross-reference attendee emails with Slack IDs
        // 3. Send Slack DM or Channel message + Email
        return { success: true };
    }

    /**
     * Initiates a new meeting with a set of attendees.
     */
    public async initiateNewMeeting(title: string, attendees: string[], durationMinutes: number): Promise<{ success: boolean; eventId?: string }> {
        this.logger.info(`Initiating new meeting: ${title} with ${attendees.length} participants`);

        // Simulate finding the next best slot for the group
        const startTime = new Date();
        startTime.setHours(startTime.getHours() + 24); // Mock: next day
        const endTime = new Date(startTime.getTime() + durationMinutes * 60000);

        const response = await fetch('/api/v1/calendar/events', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                start: startTime.toISOString(),
                end: endTime.toISOString(),
                attendees,
                description: "Automatically initiated to resolve scheduling conflict."
            })
        });

        if (response.ok) {
            const data = await response.json();
            return { success: true, eventId: data.event.id };
        }
        return { success: false };
    }

    /**
     * Fetches the "opinion" of an attendee based on their role and the proposed change.
     */
    public async getAttendeeOpinionByRole(attendeeId: string, role: string, proposedChange: string): Promise<{ approved: boolean; feedback: string }> {
        this.logger.info(`Getting opinion for ${attendeeId} (Role: ${role}) on: ${proposedChange}`);

        // Simulate role-based logic
        if (role === "decision_maker") {
            // Decision makers are harder to please
            const approved = Math.random() > 0.3;
            return {
                approved,
                feedback: approved ? "Confirmed, this works for me." : "I have a conflicting high-priority sync. Please find another slot."
            };
        }

        // Other roles are generally more flexible in this mock
        return { approved: true, feedback: "Understood, will adjust." };
    }
}

export const schedulingSkill = new SchedulingSkill();
