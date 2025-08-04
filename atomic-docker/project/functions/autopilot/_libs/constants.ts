export const hasuraMetadataUrl = process.env.HASURA_GRAPHQL_METADATA_URL;
export const hasuraGraphUrl = process.env.HASURA_GRAPHQL_GRAPHQL_URL;
export const hasuraAdminSecret = process.env.HASURA_GRAPHQL_ADMIN_SECRET;
export const authApiToken = process.env.API_TOKEN;

export const onScheduledTriggerDailyFeaturesApplyWebhookProdAdminUrl =
  process.env.ON_SCHEDULE_DAILY_FEATURES_APPLY_ADMIN_URL;

export const onScheduledTriggerDailyScheduleAssistWebhookProdAdminUrl =
  process.env.ON_SCHEDULE_DAILY_SCHEDULE_ASSIST_ADMIN_URL;

export const featuresApplyAdminUrl =
  process.env.FEATURES_WORKER_TO_QUEUE_ADMIN_URL;

export const scheduleAssistUrl =
  process.env.SCHEDULE_MEETING_TO_QUEUE_ADMIN_URL;
