import { ZoomWebhookRequestType, ZoomWebhookValidationRequestType } from '@lib/types';
import type { NextApiResponse } from 'next';
export declare const validateZoomWebook: (request: ZoomWebhookValidationRequestType, response: NextApiResponse) => any;
export declare const verifyZoomWebhook: (request: ZoomWebhookRequestType) => boolean;
export declare const exchangeCodeForTokens: (code: string, userId: string) => Promise<any>;
export declare const generateGoogleAuthUrl: (state: string) => any;
export declare const getMinimalCalendarIntegration: (userId: string, resource: string) => Promise<any>;
export declare const deAuthZoomGivenUserId: (appId: string) => Promise<void>;
export declare const updateAccessTokenCalendarIntegration: (id: string, token: string | null, expiresIn: number | null, enabled?: boolean, refreshToken?: string | null) => Promise<void>;
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
export declare const updateZoomIntegration: (id: string, appAccountId: string, appEmail: string, appId: string, token: string | null, expiresIn: number | null, refreshToken?: string, contactFirstName?: string, contactLastName?: string, phoneCountry?: string, // 'US'
phoneNumber?: string, // '+1 1234567891'
enabled?: boolean) => Promise<void>;
