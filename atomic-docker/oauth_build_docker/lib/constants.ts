import { v4 as uuid } from 'uuid';
import dayjs from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';

dayjs.extend(isoWeek);
dayjs.extend(duration);
dayjs.extend(isBetween);
dayjs.extend(timezone);
dayjs.extend(utc);

export const IS_PRODUCTION = process.env.NODE_ENV === 'production';

export const hasuraGraphUrl = process.env.HASURA_GRAPHQL_GRAPHQL_URL as string;

export const hasuraAdminSecret = process.env.HASURA_GRAPHQL_ADMIN_SECRET;
export const googleTokenUrl = 'https://oauth2.googleapis.com/token';
export const googleClientSecretWeb = process.env.GOOGLE_CLIENT_SECRET_WEB;
export const googleClientIdWeb = process.env.GOOGLE_CLIENT_ID_WEB;
export const googleRedirectUrl = process.env.GOOGLE_REDIRECT_URL;

export const zoomResourceName = 'zoom';

export const handshakeUrl = process.env.HANDSHAKE_URL;

export const zoomAuthUrl = 'https://zoom.us/oauth/authorize';

export const appUrl = process.env.NEXT_PUBLIC_APP_URL;

export const zoomSaltForPass = process.env.ZOOM_SALT_FOR_PASS as string;

export const zoomIVForPass = process.env.ZOOM_IV_FOR_PASS as string;

export const zoomPassKey = process.env.ZOOM_PASS_KEY as string;

export const githubClientId = process.env.GITHUB_CLIENT_ID;
export const githubClientSecret = process.env.GITHUB_CLIENT_SECRET;
export const githubRedirectUrl = process.env.GITHUB_REDIRECT_URI;
