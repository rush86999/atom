import got from 'got';

import { google } from 'googleapis';

import dayjs from 'dayjs';

import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import {
  googleAuthRedirectUri,
  googleClientIdAtomicWeb,
  googleClientIdIos,
  googleClientIdWeb,
  googleClientSecretAtomicWeb,
  googleClientSecretWeb,
  googleTokenUrl,
} from './constants';
import { RefreshTokenResponseBodyType } from './types';

import {
  googleAuthRedirectUri,
  googleClientIdAtomicWeb,
  googleClientIdIos,
  googleClientIdWeb,
  googleClientSecretAtomicWeb,
  googleClientSecretWeb,
  googleTokenUrl,
  googleClientIdGmail,
  googleClientSecretGmail,
  googleClientIdMcp,
  googleClientSecretMcp,
} from './constants'; // Added Mcp constants
dayjs.extend(utc);
dayjs.extend(timezone);

export const getGoogleTokenAndRefreshToken = async (code: string) => {
  try {
    const oauth2Client = new google.auth.OAuth2(
      googleClientIdWeb,
      googleClientSecretWeb,
      googleAuthRedirectUri
    );

    const { tokens } = await oauth2Client.getToken(code);

    return tokens;
  } catch (e) {
    console.log(e, ' unable to get google token and refresh token');
    throw e; // Re-throw the error to be handled by the caller
  }
};

// New function for Gmail token exchange
export const getGmailUserTokens = async (
  code: string,
  redirectUri: string
): Promise<google.auth.Credentials> => {
  try {
    const oauth2Client = new google.auth.OAuth2(
      googleClientIdGmail, // Use Gmail specific client ID
      googleClientSecretGmail, // Use Gmail specific client secret
      redirectUri // Use the provided redirect URI for this specific flow
    );

    const { tokens } = await oauth2Client.getToken(code);
    if (!tokens) {
      throw new Error('Failed to retrieve tokens from Google.');
    }
    return tokens;
  } catch (e) {
    console.error('Error in getGmailUserTokens:', e);
    throw e; // Re-throw the error
  }
};

export const googleCalendarAtomicWebRefreshToken = async (
  refreshToken: string
): Promise<RefreshTokenResponseBodyType> => {
  try {
    const res: RefreshTokenResponseBodyType = await got
      .post(googleTokenUrl, {
        form: {
          grant_type: 'refresh_token',
          refresh_token: refreshToken,
          client_id: googleClientIdAtomicWeb,
          client_secret: googleClientSecretAtomicWeb,
        },
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })
      .json();

    console.log(res, ' refresh token success');
    return res;
  } catch (e) {
    console.log(e, ' unable to refresh token');
    throw e; // Re-throw
  }
};

// New function for Gmail token refresh
export const refreshGmailAccessToken = async (
  refreshToken: string
): Promise<RefreshTokenResponseBodyType> => {
  try {
    const res: RefreshTokenResponseBodyType = await got
      .post(googleTokenUrl, {
        form: {
          grant_type: 'refresh_token',
          refresh_token: refreshToken,
          client_id: googleClientIdGmail, // Use Gmail specific client ID
          client_secret: googleClientSecretGmail, // Use Gmail specific client secret
        },
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })
      .json();

    console.log(res, 'Gmail access token refresh success');
    return res;
  } catch (e) {
    console.error('Error in refreshGmailAccessToken:', e);
    throw e; // Re-throw
  }
};
export const googleCalendarWebRefreshToken = async (
  refreshToken: string
): Promise<RefreshTokenResponseBodyType> => {
  try {
    const res: RefreshTokenResponseBodyType = await got
      .post(googleTokenUrl, {
        form: {
          grant_type: 'refresh_token',
          refresh_token: refreshToken,
          client_id: googleClientIdWeb,
          client_secret: googleClientSecretWeb,
        },
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })
      .json();

    console.log(res, ' refresh token success');
    return res;
  } catch (e) {
    console.log(e, ' unable to refresh token');
  }
};

// New function for Mcp token exchange
export const getMcpUserTokens = async (
  code: string,
  redirectUri: string
): Promise<google.auth.Credentials> => {
  try {
    const oauth2Client = new google.auth.OAuth2(
      googleClientIdMcp, // Use Mcp specific client ID
      googleClientSecretMcp, // Use Mcp specific client secret
      redirectUri // Use the provided redirect URI for this specific flow
    );

    const { tokens } = await oauth2Client.getToken(code);
    if (!tokens) {
      throw new Error('Failed to retrieve tokens from Google.');
    }
    return tokens;
  } catch (e) {
    console.error('Error in getMcpUserTokens:', e);
    throw e; // Re-throw the error
  }
};

// New function for Mcp token refresh
export const refreshMcpAccessToken = async (
  refreshToken: string
): Promise<RefreshTokenResponseBodyType> => {
  try {
    const res: RefreshTokenResponseBodyType = await got
      .post(googleTokenUrl, {
        form: {
          grant_type: 'refresh_token',
          refresh_token: refreshToken,
          client_id: googleClientIdMcp, // Use Mcp specific client ID
          client_secret: googleClientSecretMcp, // Use Mcp specific client secret
        },
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })
      .json();

    console.log(res, 'Mcp access token refresh success');
    return res;
  } catch (e) {
    console.error('Error in refreshMcpAccessToken:', e);
    throw e; // Re-throw
  }
};

export const googleCalendarIosRefreshToken = async (
  refreshToken: string
): Promise<RefreshTokenResponseBodyType> => {
  try {
    const res: RefreshTokenResponseBodyType = await got
      .post(googleTokenUrl, {
        form: {
          grant_type: 'refresh_token',
          refresh_token: refreshToken,
          client_id: googleClientIdIos,
        },
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })
      .json();

    console.log(res, ' refresh token success');
    return res;
  } catch (e) {
    console.log(e, ' unable to refresh token');
  }
};
