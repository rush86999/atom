export const MAX_CHARACTER_LIMIT = 3250;
// export const HTML_REGEX_PATTERN = /<html>(.*?)<\/html>/gs
// /<html[^>]*>([\s\S]*?)<\/html>/i
export const HTML_REGEX_PATTERN = /<html[^>]*>([\s\S]*?)<\/html>/gi;
export const A_TAG_REGEX_PATTERN = /<a href="(.*?)"/;
export const URL_REGEX_PATTERN = /(https?:\/\/\S+)/g;
// matches spaces and ends with ">" character
// https?:\/\/([a-z0-9]+\.)?calendar\.atomiclife\.app\S+[\S, \S]+[">Atomic<\/a> :)]
export const ATOMIC_SUBDOMAIN_PATTERN =
  /https?:\/\/([a-z0-9]+\.)?calendar\.atomiclife\.app\S+[\S, \S]+\S+[> ]/g;
export const NUMBER_TO_REMOVE_FOR_SUBDOMAIN_SLICE = 2;

export const emailKnwIndex = 'knn-knw-index';
export const hasuraGraphUrl = process.env.HASURA_GRAPHQL_GRAPHQL_URL;
export const openAIChatGPTModel = 'gpt-3.5-turbo';
export const hasuraAdminSecret = process.env.HASURA_GRAPHQL_ADMIN_SECRET;
export const googleClientIdIos = process.env.GOOGLE_ClIENT_ID_IOS;
export const googleClientIdAndroid = process.env.GOOGLE_CLIENT_ID_ANDROID;
export const googleClientIdWeb = process.env.GOOGLE_CLIENT_ID_WEB;
export const googleClientIdAtomicWeb = process.env.GOOGLE_CLIENT_ID_ATOMIC_WEB;

export const googleTokenUrl = 'https://oauth2.googleapis.com/token';

export const googleClientSecretWeb = process.env.GOOGLE_CLIENT_SECRET_WEB;

export const googleCalendarResource = 'google';
export const zoomResourceName = 'zoom';
export const zoomClientSecret = process.env.ZOOM_CLIENT_SECRET;
export const zoomClientId = process.env.ZOOM_CLIENT_ID;
export const zoomTokenUrl = 'https://zoom.us/oauth/token';
export const zoomBaseUrl = 'https://api.zoom.us/v2';
export const zoomBaseTokenUrl = 'https://zoom.us';
export const zoomSaltForPass = process.env.ZOOM_SALT_FOR_PASS;
export const zoomIVForPass = process.env.ZOOM_IV_FOR_PASS;
export const zoomPassKey = process.env.ZOOM_PASS_KEY;

export const googleClientSecretAtomicWeb =
  process.env.GOOGLE_CLIENT_SECRET_ATOMIC_WEB;

export const defaultOpenAIAPIKey = process.env.OPENAI_API_KEY;
