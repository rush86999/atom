export interface ScheduleMeetingRequestType {
  participantNames: string[];
  durationMinutes: number;
  preferredDate: string; // YYYY-MM-DD
  preferredTime: string; // HH:MM:SS
}
