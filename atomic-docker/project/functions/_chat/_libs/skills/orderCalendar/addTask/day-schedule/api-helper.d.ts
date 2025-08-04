import { BufferTimeType } from '@chat/_libs/types/EventType';
export declare const createDayScheduleForTasks: (userId: string, tasks: string[], // make sure to add previous events inside tasks when submitting
timezone: string, dayWindowStartDate: string, dayWindowEndDate: string, userCurrentTime: string, bufferTime?: BufferTimeType, startDate?: string) => Promise<DailyScheduleObjectType[] | undefined>;
