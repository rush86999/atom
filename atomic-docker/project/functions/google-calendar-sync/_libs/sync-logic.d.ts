import { colorTypeResponse } from './types/googleCalendarSync/types';
export declare const initialGoogleCalendarSync2: (calendarId: string, userId: string, clientType: "ios" | "android" | "web" | "atomic-web", colorItem?: colorTypeResponse) => Promise<any>;
export interface PerformCalendarSyncParams {
    calendarIntegrationId: string;
    calendarId: string;
    userId: string;
    timezone: string;
}
export declare const performCalendarSync: (params: PerformCalendarSyncParams) => Promise<{
    success: boolean;
    message: string;
    status: number;
    syncDisabled?: undefined;
} | {
    success: boolean;
    message: string;
    status: number;
    syncDisabled: boolean;
}>;
