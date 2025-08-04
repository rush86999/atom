import { openAllEventVectorName } from '@google_calendar_sync/_libs/constants';
import { EventResourceType } from '@/google-calendar-sync/_libs/types';

export type BulkImportBodyType = {
  id: string;
  body: {
    [openAllEventVectorName]: number[];
    userId: string;
    start_date: string;
    end_date: string;
  };
};

export type EventObjectForVectorType = {
  method: 'upsert' | 'delete';
  event: EventResourceType;
  calendarId: string;
};

export type Event2VectorBodyType = {
  events: EventObjectForVectorType[];
  userId: string;
};

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

export type OpenAllEventSourceType = {
  userId: string;
  [openAllEventVectorName]: number[];
  start_date: string;
  end_date: string;
  title: string;
};

export type OpenSearchResponseBodyType = {
  took?: number;
  timed_out?: false;
  _shards?: {
    total: number;
    successful: number;
    skipped: number;
    failed: number;
  };
  hits?: {
    total: {
      value: number;
      relation: string;
    };
    max_score: number;
    hits?: [
      {
        _index: string;
        _type: string;
        _id: string;
        _score: number;
        _source: OpenAllEventSourceType;
      },
    ];
  };
};
