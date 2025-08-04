export type MessageQueueType = {
  messageId: string;
  receiptHandle: string;
  body: string; // json stringified
  attributes: {
    ApproximateReceiveCount: string; // stringified number
    SentTimestamp: string; // stringified number
    SenderId: string; // function id
    ApproximateFirstReceiveTimestamp: string; // stringified number
  };
  messageAttributes: object;
  md5OfMessageAttributes: null;
  md5OfBody: string;
  eventSource: string; // 'aws:sqs',
  eventSourceARN: string; // 'arn:aws:sqs:us-east-1:767299747852:googlecalendarsync-dev-atomic-create-calendar-queue',
  awsRegion: string; // 'us-east-1'
};

export type ScheduleAssistWithMeetingQueueBodyType = {
  userId: string;
  windowStartDate: string;
  windowEndDate: string;
  timezone: string;
};
