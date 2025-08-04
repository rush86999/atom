export type MessageQueueType = {
    messageId: string;
    receiptHandle: string;
    body: string;
    attributes: {
        ApproximateReceiveCount: string;
        SentTimestamp: string;
        SenderId: string;
        ApproximateFirstReceiveTimestamp: string;
    };
    messageAttributes: object;
    md5OfMessageAttributes: null;
    md5OfBody: string;
    eventSource: string;
    eventSourceARN: string;
    awsRegion: string;
};
export type ScheduleAssistWithMeetingQueueBodyType = {
    userId: string;
    windowStartDate: string;
    windowEndDate: string;
    timezone: string;
};
