export const hasuraMetadataUrl = process.env.HASURA_GRAPHQL_METADATA_URL;
export const hasuraGraphUrl = process.env.HASURA_GRAPHQL_GRAPHQL_URL;

export const hasuraAdminSecret = process.env.HASURA_GRAPHQL_ADMIN_SECRET;
export const authApiToken = process.env.API_TOKEN;

export const text2VectorUrl = process.env.TEXT_TO_VECTOR_URL;
export const openSearchEndPoint = process.env.OPENSEARCH_ENDPOINT;
export const eventVectorName = 'event-vector';
export const vectorDimensions = 384;
export const searchIndex = 'knn-events-index';

export const googleCalendarResource = 'google';

export const googlePeopleResource = 'google';
export const googlePeopleName = 'Google Contacts';

export const googleMeetResource = 'google';
export const googleClientIdIos = process.env.GOOGLE_ClIENT_ID_IOS;
export const googleClientIdAndroid = process.env.GOOGLE_CLIENT_ID_ANDROID;
export const googleClientIdWeb = process.env.GOOGLE_CLIENT_ID_WEB;
export const googleTokenUrl = 'https://oauth2.googleapis.com/token';
export const googleClientSecretWeb = process.env.GOOGLE_CLIENT_SECRET_WEB;
export const googleClientIdAtomicWeb = process.env.GOOGLE_CLIENT_ID_ATOMIC_WEB;

export const zoomResourceName = 'zoom';
export const zoomClientSecret = process.env.ZOOM_CLIENT_SECRET;
export const zoomClientId = process.env.ZOOM_CLIENT_ID;
export const zoomBaseUrl = 'https://api.zoom.us/v2';
export const zoomBaseTokenUrl = 'https://zoom.us';
export const googleColorUrl = 'https://www.googleapis.com/calendar/v3/colors';

// CHANGE THIS!!!
export const selfGoogleCalendarWebhookPublicUrl =
  process.env.GOOGLE_CALENDAR_WEBHOOK_URL;

// CHANGE THIS!!
export const selfGooglePeopleAdminUrl =
  process.env.GOOGLE_PEOPLE_SYNC_ADMIN_URL;

export const zoomSaltForPass = process.env.ZOOM_SALT_FOR_PASS;
export const zoomIVForPass = process.env.ZOOM_IV_FOR_PASS;
export const zoomPassKey = process.env.ZOOM_PASS_KEY;

// GOOGLE_CLIENT_SECRET_ATOMIC_WEB
export const googleClientSecretAtomicWeb =
  process.env.GOOGLE_CLIENT_SECRET_ATOMIC_WEB;

export const bucketName = process.env.S3_BUCKET;

export const defaultOpenAIAPIKey = process.env.OPENAI_API_KEY;

export const openAllEventIndex = 'knn-open-all-event-index';

export const openAllEventVectorDimensions = 1536;

export const openAIChatGPT35Model = 'gpt-3.5-turbo';
export const openAIChatGPT35LongModel = 'gpt-3.5-turbo-16k';
export const openAIChatGPT4Model = 'gpt-4';

export const openAllEventVectorName = 'embeddings';

export const googleCalendarStopWatchUrl =
  'https://www.googleapis.com/calendar/v3/channels/stop';

export const openTrainEventVectorName = 'embeddings';
export const openTrainEventVectorDimensions = 1536;
export const openTrainEventIndex = 'knn-open-train-event-index';

export const kafkaGoogleCalendarSyncTopic = 'google-calendar-sync';
export const kafkaGoogleCalendarSyncGroupId = 'google-calendar-sync';
