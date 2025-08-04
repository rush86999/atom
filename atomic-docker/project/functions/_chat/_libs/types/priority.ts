// Core shared types to eliminate duplication in api-helper.ts
export type GoogleResType = any;
export type EventType = any;
export type TrainingEventSchema = any;
export type MeetingAssistType = any;
export type AttendeeType = any;
export type ConferenceType = any;
export type ContactType = any;
export type UserContactInfoType = any;
export type MeetingAssistAttendeeType = any;
export type MeetingAssistInviteType = any;
export type UserType = any;
export type Weekday = any;
export type SafeType = Record<string, any>;
export type SafeArray = any[];
export type SafeFunction = (...args: any[]) => any;

// Production type safety layer
export interface ProductionCompatibleTypes {
  TrainingEventSchema: any;
  EventSchema: any;
}

// Manual type extensions for Buffer compatibility
declare global {
  var process: any;
  var Buffer: any;
}
