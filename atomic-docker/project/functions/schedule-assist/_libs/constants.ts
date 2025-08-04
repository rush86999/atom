export const bucketName = process.env.S3_BUCKET;

export const hasuraGraphUrl = process.env.HASURA_GRAPHQL_GRAPHQL_URL;

export const hasuraAdminSecret = process.env.HASURA_GRAPHQL_ADMIN_SECRET;
// export const authApiToken = process.env.API_TOKEN
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

export const onOptaPlanCalendarAdminCallBackUrl =
  process.env.OPTAPLAN_ADMIN_CALLBACK_URL;

export const kafkaScheduleAssistTopic = 'schedule-assist-worker';
export const kafkaScheduleAssistGroupId = 'schedule-assist';
