// --- Generic Skill Error and Response Types ---
// (Mirrors the structure from other services for consistency)
export interface SkillError {
  code: string;
  message: string;
  details?: any;
}

export interface AutopilotApiResponse<T> {
  ok: boolean;
  data?: T;
  error?: SkillError;
}

export type ScheduleAssistWithMeetingQueueBodyType = {
    userId: string,
    windowStartDate: string,
    windowEndDate: string,
    timezone: string,
}


export type AutopilotType = {
    id: string,
    userId: string,
    scheduleAt: string,
    timezone: string,
    payload: ScheduleAssistWithMeetingQueueBodyType, 
    updatedAt: string,
    createdDate: string,
}

export type AddDailyFeaturesApplyEventTriggerType = {
    autopilot: AutopilotType,
    body: ScheduleAssistWithMeetingQueueBodyType,
}

export type StartDailyAssistEventTriggerType = {
    autopilot: AutopilotType,
    body: ScheduleAssistWithMeetingQueueBodyType,
}

export type MM = '01' | '02' | '03' | '04' | '05' | '06' | '07' | '08' | '09' | '10' | '11' | '12'

export type HH = '00' | '01' | '02' | '03' | '04' | '05' | '06' | '07' | '08' | '09' | '10' | '11' | '12' | '13' | '14' | '15' | '16' | '17' | '18' | '19' | '20' | '21' | '22' | '23'

export type Time = `${HH}:${MM}`


type DayOfWeekIntType = 1 | 2 | 3 | 4 | 5 | 6 | 7

type StartTimeType = {
  day: DayOfWeekIntType,
  hour: number,
  minutes: number,
}

type EndTimeType = {
  day: DayOfWeekIntType,
  hour: number,
  minutes: number,
}

export type UserPreferenceType = {
    id: string,
    userId: string,
    reminders?: number[], // invite part
    followUp?: number[], // invite part
    isPublicCalendar?: boolean,
    publicCalendarCategories?: string[],
    startTimes?: StartTimeType[],
    endTimes?: EndTimeType[],
    copyAvailability?: boolean,
    copyTimeBlocking?: boolean,
    copyTimePreference?: boolean,
    copyReminders?: boolean,
    copyPriorityLevel?: boolean,
    copyModifiable?: boolean,
    copyCategories?: boolean,
    copyIsBreak?: boolean,
    maxWorkLoadPercent: number,
    minNumberOfBreaks: number,
    breakLength: number,
    breakColor?: string,
    backToBackMeetings: boolean,
    maxNumberOfMeetings: number,
    copyIsMeeting?: boolean,
    copyIsExternalMeeting?: boolean,
    copyColor?: boolean,
    updatedAt?: string,
    createdDate?: string,
    deleted: boolean
}


export type HasuraTriggerBodyType = {
    scheduled_time: string,
    payload: StartDailyAssistEventTriggerType | AddDailyFeaturesApplyEventTriggerType,
    created_at: string,
    id: string,
    comment?: string,
}




export type DeleteScheduledEventBody = string
