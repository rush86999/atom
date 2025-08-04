export const openAIAPIKey = process.env.OPENAI_API_KEY;

export const hasuraGraphUrl = process.env.HASURA_GRAPHQL_GRAPHQL_URL;

export const hasuraAdminSecret = process.env.HASURA_GRAPHQL_ADMIN_SECRET;

export const googleClientIdIos = process.env.GOOGLE_ClIENT_ID_IOS;
export const googleClientIdAndroid = process.env.GOOGLE_CLIENT_ID_ANDROID;
export const googleClientIdWeb = process.env.GOOGLE_CLIENT_ID_WEB;

export const googleTokenUrl = 'https://oauth2.googleapis.com/token';

export const googleClientSecretWeb = process.env.GOOGLE_CLIENT_SECRET_WEB;

export const googleCalendarResource = 'google';

export const openAIDavinci003Model = 'text-davinci-003';
export const openAIChatGPTModel = 'gpt-3.5-turbo';

export const EMAIL = process.env.EMAIL; // example:  no-reply@atomiclife.app
export const DOMAIN = process.env.DOMAIN; // example: atomiclife.app [no https or backslashes '/']

export const bucketName = process.env.S3_BUCKET;

export const authApiToken = process.env.API_TOKEN;

export const maxCharacterCount = 5000;

export const googleClientIdAtomicWeb = process.env.GOOGLE_CLIENT_ID_ATOMIC_WEB;
// GOOGLE_CLIENT_SECRET_ATOMIC_WEB
export const googleClientSecretAtomicWeb =
  process.env.GOOGLE_CLIENT_SECRET_ATOMIC_WEB;

// Kafka Configuration
export const kafkaBrokers = (process.env.KAFKA_BROKERS || 'localhost:9092')
  .split(',')
  .map((broker) => broker.trim());
export const kafkaOnDayScheduleTopic =
  process.env.KAFKA_TOPIC_ON_DAY_SCHEDULE || 'on-day-schedule';
export const kafkaMeetingReqTemplateTopic =
  process.env.KAFKA_TOPIC_MEETING_REQ_TEMPLATE || 'meeting-req-template';
export const kafkaGPTGroupId = process.env.KAFKA_GROUP_ID_GPT || 'gpt';

// S3 Configuration
// bucketName is already process.env.S3_BUCKET
export const s3Endpoint = process.env.S3_ENDPOINT; // May be undefined if not set, S3 client handles this
