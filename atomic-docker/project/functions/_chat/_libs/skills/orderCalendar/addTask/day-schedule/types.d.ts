export type DailyScheduleObjectType = {
    start_time: string;
    end_time: string;
    task: string;
};
export type RecurrenceFrequencyType = 'daily' | 'weekly' | 'monthly' | 'yearly';
