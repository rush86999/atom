export const bucketName = process.env.S3_BUCKET;

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

// export const calendarPremiumDelay = 300000
export const optaplannerDuration = parseInt(
  process.env.OPTAPLANNER_DURATION,
  10
);
export const optaplannerShortDuration = parseInt(
  process.env.OPTAPLANNER_SHORT_DURATION,
  10
);
export const onOptaPlanCalendarAdminCallBackUrl =
  process.env.OPTAPLAN_ADMIN_CALLBACK_URL;

// export const defaultFreemiumUsage = 5
export const text2VectorUrl = process.env.TEXT_TO_VECTOR_URL;
export const openSearchEndPoint = process.env.OPENSEARCH_ENDPOINT;
export const eventVectorName = 'event-vector';
export const vectorDimensions = 384;
export const searchIndex = 'knn-events-index';

export const defaultOpenAIAPIKey = process.env.OPENAI_API_KEY;
export const openAllEventIndex = 'knn-open-all-event-index';
export const openAllEventVectorDimensions = 1536;
export const openAllEventVectorName = 'embeddings';
export const openTrainEventVectorName = 'embeddings';

export const openTrainEventVectorDimensions = 1536;
export const openTrainEventIndex = 'knn-open-train-event-index';

export const classificationUrl = process.env.CLASSIFICATION_URL;
export const minThresholdScore = 0.6;
export const externalMeetingLabel = 'External Meeting';
export const meetingLabel = 'Meeting';
export const kafkaScheduleEventGroupId = 'schedule-event';

export const kafkaScheduleEventTopic = 'schedule-event-worker';
export const kafkaScheduleShortEventTopic = 'schedule-short-event-worker';
