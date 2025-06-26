export interface ScheduleMeetingRequestType {
  participantNames: string[];
  durationMinutes: number;
  preferredDate: string; // YYYY-MM-DD
  preferredStartTimeFrom: string; // HH:MM:SS
  preferredStartTimeTo: string; // HH:MM:SS
}
