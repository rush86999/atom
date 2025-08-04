export const hasuraGraphUrl = process.env.HASURA_GRAPHQL_GRAPHQL_URL;

export const hasuraAdminSecret = process.env.HASURA_GRAPHQL_ADMIN_SECRET;
export const authApiToken = process.env.API_TOKEN;
export const dayOfWeekIntToString = {
  1: 'MONDAY',
  2: 'TUESDAY',
  3: 'WEDNESDAY',
  4: 'THURSDAY',
  5: 'FRIDAY',
  6: 'SATURDAY',
  7: 'SUNDAY',
};

export const optaPlannerUrl = process.env.OPTAPLANNER_URL;
export const optaPlannerUsername = process.env.OPTAPLANNER_USERNAME;
export const optaPlannerPassword = process.env.OPTAPLANNER_PASSWORD;

export const optaplannerDuration = parseInt(
  process.env.OPTAPLANNER_DURATION,
  10
);
export const onOptaPlanCalendarAdminCallBackUrl =
  process.env.OPTAPLAN_ADMIN_CALLBACK_URL;

export const defaultFreemiumUsage = 5;
export const text2VectorUrl = process.env.TEXT_TO_VECTOR_URL;
export const openSearchEndPoint = process.env.OPENSEARCH_ENDPOINT;
export const eventVectorName = 'event-vector';
export const vectorDimensions = 384;
export const searchIndex = 'knn-events-index';
export const classificationUrl = process.env.CLASSIFICATION_URL;
export const minThresholdScore = 0.6;
export const externalMeetingLabel = 'External Meeting';
export const meetingLabel = 'Meeting';
export const googleCalendarResource = 'google';

export const googleClientIdIos = process.env.GOOGLE_ClIENT_ID_IOS;
export const googleClientIdAndroid = process.env.GOOGLE_CLIENT_ID_ANDROID;
export const googleClientIdWeb = process.env.GOOGLE_CLIENT_ID_WEB;
export const googleTokenUrl = 'https://oauth2.googleapis.com/token';
export const googleClientSecretWeb = process.env.GOOGLE_CLIENT_SECRET_WEB;
export const zoomResourceName = 'zoom';
export const zoomClientSecret = process.env.ZOOM_CLIENT_SECRET;
export const zoomClientId = process.env.ZOOM_CLIENT_ID;
export const zoomTokenUrl = 'https://zoom.us/oauth/token';
export const zoomBaseUrl = 'https://api.zoom.us/v2';
export const zoomBaseTokenUrl = 'https://zoom.us';
export const zoomSaltForPass = process.env.ZOOM_SALT_FOR_PASS;
export const zoomIVForPass = process.env.ZOOM_IV_FOR_PASS;
export const zoomPassKey = process.env.ZOOM_PASS_KEY;

export const googleClientIdAtomicWeb = process.env.GOOGLE_CLIENT_ID_ATOMIC_WEB;
export const googleClientSecretAtomicWeb =
  process.env.GOOGLE_CLIENT_SECRET_ATOMIC_WEB;

export const bucketName = process.env.S3_BUCKET;

export const kafkaPostProcessCalTopic = 'post-process-cal-worker';
export const kafkaPostProcessCalGroupId = 'post-process-cal';
