import type { NextApiRequest } from 'next';
import { CalendarIntegrationType, colorType } from './dataTypes/Calendar_IntegrationType';
import { colorResponseType } from './calendarLib/types';
import { type Credentials } from 'google-auth-library/build/src/auth/credentials';
import { ScheduleMeetingRequestType } from './dataTypes/ScheduleMeetingRequestType';
export declare const exchangeCodeForTokens: (code: string) => Promise<Credentials>;
export declare const generateGoogleAuthUrl: (state?: string) => string;
export declare const getMinimalCalendarIntegrationByResource: (userId: string, resource: string) => Promise<CalendarIntegrationType | undefined>;
export declare const updateAccessTokenCalendarIntegration: (id: string, token: string | null, expiresIn: number | null, enabled?: boolean, refreshToken?: string | null) => Promise<void>;
export declare const refreshGoogleToken: (refreshToken: string, clientType: "ios" | "android" | "web" | "atomic-web") => Promise<{
    access_token: string;
    expires_in: number;
    scope: string;
    token_type: string;
} | undefined>;
/**
 * query getCalendarIntegration($userId: uuid!, $resource: String!, $clientType: String!) {
  Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}, clientType: {_eq: $clientType}}) {
    appAccountId
    appEmail
    appId
    clientType
    colors
    contactEmail
    contactFirstName
    contactLastName
    contactName
    createdDate
    deleted
    enabled
    expiresAt
    id
    name
    pageToken
    password
    phoneCountry
    phoneNumber
    refreshToken
    resource
    syncEnabled
    syncToken
    token
    updatedAt
    userId
    username
  }
}

 */
export declare const getAllCalendarIntegratonsByResourceAndClientType: (userId: string, resource: string, clientType: "ios" | "android" | "web" | "atomic-web") => Promise<CalendarIntegrationType[] | undefined>;
export declare const getAllCalendarIntegrationsByResource: (userId: string, resource: string) => Promise<CalendarIntegrationType[] | undefined>;
export declare const getGoogleColors: (token: string) => Promise<colorResponseType>;
export declare const triggerGooglePeopleSync: (calendarIntegrationId: string, userId: string, req: NextApiRequest) => Promise<void>;
export declare const updateGoogleIntegration: (id: string, enabled?: boolean, token?: string, refreshToken?: string, expiresAt?: string, syncEnabled?: boolean, colors?: colorType[], pageToken?: string, syncToken?: string, clientType?: "ios" | "android" | "web" | "atomic-web") => Promise<CalendarIntegrationType | undefined>;
export declare const scheduleMeeting: (payload: ScheduleMeetingRequestType, clientType: "ios" | "android" | "web" | "atomic-web") => Promise<string>;
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
export declare const getMinimalCalendarIntegrationByName: (userId: string, name: string) => Promise<CalendarIntegrationType | undefined>;
/**
 * query getCalendarIntegration($userId: uuid!, $resource: String!, $clientType: String!) {
  Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}, clientType: {_eq: $clientType}}) {
    appAccountId
    appEmail
    appId
    clientType
    colors
    contactEmail
    contactFirstName
    contactLastName
    contactName
    createdDate
    deleted
    enabled
    expiresAt
    id
    name
    pageToken
    password
    phoneCountry
    phoneNumber
    refreshToken
    resource
    syncEnabled
    syncToken
    token
    updatedAt
    userId
    username
  }
}

 */
export declare const getAllCalendarIntegratonsByResourceAndClientType: (userId: string, resource: string, clientType: "ios" | "android" | "web" | "atomic-web") => Promise<CalendarIntegrationType[] | undefined>;
export declare const getAllCalendarIntegrationsByResource: (userId: string, resource: string) => Promise<CalendarIntegrationType[] | undefined>;
export declare const getGoogleColors: (token: string) => Promise<colorResponseType | undefined>;
export declare const triggerGooglePeopleSync: (calendarIntegrationId: string, userId: string, req: NextApiRequest) => Promise<void>;
export declare const updateGoogleIntegration: (id: string, enabled?: boolean, token?: string, refreshToken?: string, expiresAt?: string, syncEnabled?: boolean, colors?: colorType[], pageToken?: string, syncToken?: string, clientType?: "ios" | "android" | "web" | "atomic-web") => Promise<CalendarIntegrationType | undefined>;
export declare const scheduleMeeting: (payload: ScheduleMeetingRequestType) => Promise<any>;
