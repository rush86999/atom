export type CalendarWebhookType = {
  calendarId: string;
  createdDate: string;
  expiration?: string;
  id: string;
  resourceId: string;
  resourceUri: string;
  token: string;
  updatedAt: string;
  userId: string;
  calendarIntegrationId: string;
};

export type CalendarWebhookHeaders = {
  'X-Goog-Channel-ID': string;
  'X-Goog-Channel-Token': string;
  'X-Goog-Channel-Expiration': string;
  'X-Goog-Resource-ID': string;
  'X-Goog-Resource-URI': string;
  'X-Goog-Resource-State': string;
  'X-Goog-Message-Number': number;
};
