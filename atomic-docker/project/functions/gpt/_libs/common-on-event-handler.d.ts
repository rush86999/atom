import { S3Client } from '@aws-sdk/client-s3';
import { Kafka } from 'kafkajs';
export interface CreateDayScheduleBodyType {
    userId: string;
    startDate: string;
    endDate: string;
    timezone: string;
    tasks: Array<{
        summary: string;
        description?: string;
        start_time?: string;
        end_time?: string;
        duration?: number;
    }>;
    isAllDay?: boolean;
    prompt?: string;
}
import { MeetingRequestBodyType } from './types';
interface DayScheduleValidationResult {
    valid: boolean;
    error?: {
        message: string;
        event: any;
    };
    data?: CreateDayScheduleBodyType;
}
interface MeetingRequestValidationResult {
    valid: boolean;
    error?: {
        message: string;
        event: any;
    };
    data?: MeetingRequestBodyType;
}
export declare const validateDaySchedulePayload: (body: any) => DayScheduleValidationResult;
interface PublishResult {
    success: boolean;
    error?: {
        message: string;
        details?: any;
    };
}
export declare const publishToS3AndKafka: (payload: CreateDayScheduleBodyType, kafkaTopic: string, s3ClientInstance?: S3Client, kafkaInstance?: Kafka) => Promise<PublishResult>;
export declare const disconnectKafkaProducer: () => Promise<void>;
export declare const validateMeetingRequestBody: (body: any) => MeetingRequestValidationResult;
export {};
