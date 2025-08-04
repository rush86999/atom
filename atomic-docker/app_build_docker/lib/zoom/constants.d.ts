export declare const zoomApiUrl = "https://api.zoom.us/v2";
export declare const zoomCreateMeetingUrl: string | undefined;
export declare const zoomUpdateMeetingUrl: string | undefined;
export declare const zoomDeleteMeetingUrl: string | undefined;
export declare const zoomName = "Zoom Meeting";
export declare const zoomResourceName = "zoom";
export declare const zoomOAuthStartUrl: string | undefined;
export declare const meetingType: {
    instant: number;
    scheduled: number;
    recurring_no_fixed: number;
    recurring_fixed: number;
};
export declare const urlScheme = "atomiclife";
export declare const getDeepLink: (path?: string) => string;
