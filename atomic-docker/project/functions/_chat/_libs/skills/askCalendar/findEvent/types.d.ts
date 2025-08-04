import { DataAttributesType } from '@chat/_libs/skills/askCalendar/types';
export type QueryEventType = {
    userId: string;
    timezone: string;
    title: string;
    isMeeting?: boolean;
    attributes: DataAttributesType[];
    windowStartDate?: string;
    windowEndDate?: string;
};
