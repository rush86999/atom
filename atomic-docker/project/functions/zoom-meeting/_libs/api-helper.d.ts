export declare const updateZoomMeetingStartDate: (zoomToken: string, meetingId: number, startDate: string, timezone: string) => Promise<void>;
export declare const updateZoomMeeting: (zoomToken: string, meetingId: number, startDate?: string, timezone?: string, agenda?: string, duration?: number, contactName?: string, contactEmail?: string, meetingInvitees?: string[], privateMeeting?: boolean) => Promise<void>;
export declare const createZoomMeeting: (zoomToken: string, startDate: string, timezone: string, agenda: string, duration: number, contactName?: string, contactEmail?: string, meetingInvitees?: string[], privateMeeting?: boolean) => Promise<any>;
export declare const getZoomMeeting: (zoomToken: string, meetingId: number) => Promise<any>;
export declare const deleteZoomMeeting: (zoomToken: string, meetingId: number, scheduleForReminder?: boolean, cancelMeetingReminder?: boolean) => Promise<void>;
export declare const refreshZoomToken: (refreshToken: string) => Promise<{
    access_token: string;
    token_type: "bearer";
    refresh_token: string;
    expires_in: number;
    scope: string;
}>;
export declare const getCalendarIntegration: (userId: string, resource: string) => Promise<any>;
export declare const updateCalendarIntegration: (id: string, token?: string, expiresIn?: number, enabled?: boolean) => Promise<void>;
export declare const decryptZoomTokens: (encryptedToken: string, encryptedRefreshToken?: string) => {
    token: string;
    refreshToken: string;
} | {
    token: string;
    refreshToken?: undefined;
};
export declare const encryptZoomTokens: (token: string, refreshToken?: string) => {
    encryptedToken: string;
    encryptedRefreshToken: string;
} | {
    encryptedToken: string;
    encryptedRefreshToken?: undefined;
};
export declare const getZoomIntegration: (userId: string) => Promise<{
    token: string;
    refreshToken: string;
    id: any;
    expiresAt: any;
} | {
    token: string;
    refreshToken?: undefined;
    id: any;
    expiresAt: any;
} | undefined>;
export declare const updateZoomIntegration: (id: string, accessToken: string, expiresIn: number) => Promise<void>;
export declare const getZoomAPIToken: (userId: string) => Promise<any>;
