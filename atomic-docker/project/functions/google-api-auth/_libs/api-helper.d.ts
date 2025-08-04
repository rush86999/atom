import { RefreshTokenResponseBodyType } from './types';
export declare const getGoogleTokenAndRefreshToken: (code: string) => Promise<import("google-auth-library").Credentials>;
export declare const getGmailUserTokens: (code: string, redirectUri: string) => Promise<google.auth.Credentials>;
export declare const googleCalendarAtomicWebRefreshToken: (refreshToken: string) => Promise<RefreshTokenResponseBodyType>;
export declare const refreshGmailAccessToken: (refreshToken: string) => Promise<RefreshTokenResponseBodyType>;
export declare const googleCalendarWebRefreshToken: (refreshToken: string) => Promise<RefreshTokenResponseBodyType>;
export declare const getMcpUserTokens: (code: string, redirectUri: string) => Promise<google.auth.Credentials>;
export declare const refreshMcpAccessToken: (refreshToken: string) => Promise<RefreshTokenResponseBodyType>;
export declare const googleCalendarIosRefreshToken: (refreshToken: string) => Promise<RefreshTokenResponseBodyType>;
