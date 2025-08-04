// api-helper-refactored.ts - Complete replacement for legacy api-helper.ts
// Consolidates all module exports into a single entry point for compatibility

// ====== CORE MODULE EXPORTS =======
// Modern modular architecture
export * from "./modules/init";

// Individual module exports for granular usage
export * from "./modules/lance-db";
export * from "./modules/zoom";
export * from "./modules/google/calendar/calendar-operations";
export * from "./modules/openai";
export * from "./modules/event";
export * from "./modules/user";
export * from "./modules/attendee";
export * from "./modules/conference";
export * from "./modules/reminder";
export * from "./modules/datetime";
export * from "./modules/graphile";
export * from "./modules/calendar-integration";

// ====== TYPE EXPORTS (COMPATIBILITY) ======
// Selective exports to avoid duplicates
export type {
  SafeType,
  SafeArray,
  SafeFunction,
  ProductionCompatibleTypes,
} from "./types/priority";

// Individual type exports
export type { EventType } from "./types/EventType";
export type { UserType } from "./types/UserType";
export type { ContactType } from "./types/ContactType";
export type { ConferenceType } from "./types/ConferenceType";
export type { AttendeeType } from "./types/AttendeeType";
export type { MeetingAssistType } from "./types/MeetingAssistType";
export type { ZoomMeetingObjectType } from "./types/ZoomMeetingObjectType";
export type { TrainingEventSchema } from "./_utils/lancedb_service";

// ====== LEGACY API HELPER COMPATIBILITY EXPORTS ======
// All functions from legacy api-helper.ts exported for backwards compatibility

// OpenAI Functions
export {
  callOpenAIWithMessageHistory,
  callOpenAI,
  safeCallOpenAIWithMessageHistory,
  convertEventTitleToOpenAIVector,
} from "./modules/openai/client";

// LanceDB Functions
export {
  searchSingleEventByVectorLanceDb,
  searchSingleEventByVectorWithDatesLanceDb,
  searchMultipleEventsByVectorWithDatesLanceDb,
  getEventVectorFromLanceDb,
  upsertEventToLanceDb,
  deleteEventFromLanceDb,
  deleteTrainingDataFromLanceDb,
  updateTrainingDataInLanceDb,
  searchTrainingDataFromLanceDb,
} from "./modules/lance-db/operations";

// Event CRUD Functions
export {
  upsertEvents,
  listEventsForUserGivenDates,
  extractAttributesNeededFromUserInput,
  generateQueryDateFromUserInput,
  generateMissingFieldsQueryDateFromUserInput,
  generateDateTime,
  generateMissingFieldsDateTime,
  generateAssistantMessageFromAPIResponseForUserQuery,
  generateAssistantMessageToRequestUserForMissingFields,
  generateJSONDataFromUserInput,
  generateMissingFieldsJSONDataFromUserInput,
  generateWorkSchedule,
  findAnEmptySlot,
  eventSearchBoundary,
  extrapolateDateFromJSONData,
  extrapolateStartDateFromJSONData,
  extrapolateEndDateFromJSONData,
} from "./modules/event/crud/events";

// User Functions
export {
  getUserGivenId,
  updateUserNameGivenId,
  extractQueryUserInputTimeToJSONPrompt,
  userInputToDateTimeJSONPrompt,
} from "./modules/user/helpers";

// Conference Functions
export {
  getConferenceGivenId,
  deleteConferenceGivenId,
  upsertConference,
  insertReminders,
} from "./modules/conference/helpers";

// Reminder Functions
export {
  deleteRemindersWithIds,
  createPreAndPostEventsFromEvent,
} from "./modules/reminder/helpers";

// Zoom Functions
export {
  createZoomMeeting,
  updateZoomMeeting,
  deleteZoomMeeting,
  createZoomMeetingHelper,
  getZoomAPIToken,
  refreshZoomToken,
  decryptZoomTokens,
  encryptZoomTokens,
  getZoomIntegration,
  updateZoomIntegration,
  resilientGotZoomApi,
} from "./modules/zoom/client";

// Google Calendar Functions
export {
  getGoogleAPIToken,
  getCalendarIntegrationByResource,
  getCalendarIntegrationByName,
  updateCalendarIntegration,
  refreshGoogleToken,
  createGoogleEvent,
  patchGoogleEvent,
  deleteGoogleEvent,
} from "./modules/google/calendar/calendar-operations";

// Attendee Functions
export {
  findContactByEmailGivenUserId,
  getContactByNameWithUserId,
  listUserContactInfosGivenUserId,
  getUserContactInfosGivenIds,
  upsertAttendeesforEvent,
  insertAttendeesforEvent,
  deleteAttendeesWithIds,
} from "./modules/attendee/helpers";

// Graphile Functions
export {
  getEventFromPrimaryKey,
  getTaskGivenId,
  getUserPreferences,
  generateWorkTimesForUser,
} from "./modules/graphile/queries";

// Legacy datetime functions
export {
  getNumberForWeekDay,
  getNumberInString,
  getRruleFreq,
  getRRuleDay,
  getRRuleByWeekDay,
} from "./modules/datetime/helpers";

// Calendar Integration Functions
export { getGlobalCalendar } from "./modules/calendar-integration/calendar-integration";

// Blockchain compatibility exports
export {
  getBusinessHours,
  dateRangesOverlap,
  validateDateString,
  getTimezoneOffset,
  convertToUTC,
  findNextOccurrence,
} from "./modules/datetime/helpers";

// Artificial work schedule utils
export {
  generateWorkTimes,
  formatTimeSlots,
  calculateWorkingHours,
} from "./modules/datetime/helpers";

// Vector storage compatibility exports
export {
  putDataInTrainEventIndexInOpenSearch,
  putDataInAllEventIndexInOpenSearch,
  searchTrainingEvents,
  upsertTrainingEvents,
} from "./modules/lance-db/operations";

// Google calendar extended operations
export {
  getLastNDaysOfEvents,
  updateEventPreferences,
} from "./modules/google/calendar/calendar-operations";

// Webhook and notification exports
export {
  sendNotification,
  processWebhookData,
} from "./modules/event/crud/events";

// Legacy compatibility layer for deprecated functions
export const legacyWarning = () => {
  console.warn(
    "[DEPRECATION] Some legacy functions are deprecated. Consider using the new modular approach.",
  );
};

// ====== LEGACY TYPE ALIASES ======
// For backwards compatibility
export type GoogleResType = any;
export type TrainingEventSchema = any;
export type FieldMapper<T> = T extends any ? any : object;
export type SafeArray = any[];
export type SafeType = Record<string, any>;
export type SafeFunction = (...args: any[]) => any;

// ====== LEGACY CONSTANTS ======
// Re-export common constants for backwards compatibility
export * from "./constants";

// ====== LEGACY UTILITIES ======
// Buffer and process globals for Node.js compatibility
declare global {
  var process: any;
  var Buffer: any;
}

// ====== COMPATIBILITY WARNING WRAPPER ======
// Wrapper for detecting legacy usage
const legacyWrapper = <T extends (...args: any[]) => any>(
  func: T,
  name: string,
): T => {
  return ((...args: Parameters<T>): ReturnType<T> => {
    if (process.env.NODE_ENV === "development") {
      console.warn(`[LEGACY API] ${name} is called from legacy api-helper`);
    }
    return func(...args);
  }) as T;
};

// flag to track migrations
export { legacyWrapper as __legacyCompatibilityWrapper };
