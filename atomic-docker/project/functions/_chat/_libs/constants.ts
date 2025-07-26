export const hasuraGraphUrl = process.env.HASURA_GRAPHQL_GRAPHQL_URL;

export const hasuraAdminSecret = process.env.HASURA_GRAPHQL_ADMIN_SECRET;

export const defaultOpenAIAPIKey = process.env.OPENAI_API_KEY;
export const openAllEventIndex = "knn-open-all-event-index";
export const openAllEventVectorDimensions = 1536;

export const openAIChatGPT35Model = "gpt-3.5-turbo";
export const openAIChatGPT35LongModel = "gpt-3.5-turbo-16k";
export const openAIChatGPT4Model = "gpt-4";

export const openAllEventVectorName = "embeddings";

export const openTrainEventVectorName = "embeddings";
export const openTrainEventVectorDimensions = 1536;
export const openTrainEventIndex = "knn-open-train-event-index";

export const googleCalendarResource = "google";
export const googleCalendarName = "Google Calendar";
export const googleClientIdIos = process.env.GOOGLE_ClIENT_ID_IOS;
export const googleClientIdAndroid = process.env.GOOGLE_CLIENT_ID_ANDROID;
export const googleClientIdWeb = process.env.GOOGLE_CLIENT_ID_WEB;
export const googleClientIdAtomicWeb = process.env.GOOGLE_CLIENT_ID_ATOMIC_WEB;

export const googleTokenUrl = "https://oauth2.googleapis.com/token";

export const googleClientSecretWeb = process.env.GOOGLE_CLIENT_SECRET_WEB;

// GOOGLE_CLIENT_SECRET_ATOMIC_WEB
export const googleClientSecretAtomicWeb =
  process.env.GOOGLE_CLIENT_SECRET_ATOMIC_WEB;
export const zoomClientSecret = process.env.ZOOM_CLIENT_SECRET;
export const zoomClientId = process.env.ZOOM_CLIENT_ID;
export const zoomTokenUrl = "https://zoom.us/oauth/token";
export const zoomBaseUrl = "https://api.zoom.us/v2";
export const zoomBaseTokenUrl = "https://zoom.us";
export const zoomSaltForPass = process.env.ZOOM_SALT_FOR_PASS;
export const zoomIVForPass = process.env.ZOOM_IV_FOR_PASS;
export const zoomPassKey = process.env.ZOOM_PASS_KEY;
export const zoomResourceName = "zoom";

export enum Day {
  MO = "MO",
  TU = "TU",
  WE = "WE",
  TH = "TH",
  FR = "FR",
  SA = "SA",
  SU = "SU",
}

export const atomicCalendarSubdomainUrl = "https://calendar.atomiclife.app";

export const replyToAddress = "meeting@atomicscheduleassist.com";
export const noReplyAddress = "no-reply@atomiclife.app";

export const googleResourceName = "google";

// Postgraphile configuration
export const postgraphileGraphUrl = process.env.POSTGRAPHILE_GRAPHQL_URL;
export const postgraphileAdminSecret = process.env.POSTGRAPHILE_ADMIN_SECRET;
