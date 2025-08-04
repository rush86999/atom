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
