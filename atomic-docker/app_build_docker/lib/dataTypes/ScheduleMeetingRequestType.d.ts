export interface ScheduleMeetingRequestType {
    participantNames: string[];
    durationMinutes: number;
    preferredDate: string;
    preferredStartTimeFrom: string;
    preferredStartTimeTo: string;
}
