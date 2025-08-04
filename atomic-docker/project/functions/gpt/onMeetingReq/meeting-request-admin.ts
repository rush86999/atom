import { Request, Response } from 'express';
import { S3Client } from '@aws-sdk/client-s3';
import { Kafka } from 'kafkajs';
import {
  validateMeetingRequestBody,
  publishToS3AndKafka,
} from '../_libs/common-on-event-handler';
import { MeetingRequestBodyType } from '../_libs/types'; // Ensure this type is correctly imported/defined
import { kafkaMeetingReqTemplateTopic } from '../_libs/constants';

// Initialize S3 and Kafka clients
const s3Client = new S3Client({
  region: process.env.AWS_REGION || 'us-east-1',
  credentials: {
    accessKeyId: process.env.S3_ACCESS_KEY || '',
    secretAccessKey: process.env.S3_SECRET_KEY || '',
  },
  endpoint: process.env.S3_ENDPOINT,
  forcePathStyle: true,
});

const kafka = new Kafka({
  clientId:
    process.env.KAFKA_CLIENT_ID_MEETING_REQ_ADMIN ||
    'gpt-meeting-req-admin-producer',
  brokers: (process.env.KAFKA_BROKERS || 'localhost:9092').split(','),
  sasl:
    process.env.KAFKA_USERNAME && process.env.KAFKA_PASSWORD
      ? {
          mechanism: 'plain',
          username: process.env.KAFKA_USERNAME,
          password: process.env.KAFKA_PASSWORD,
        }
      : undefined,
});

export const handler = async (req: Request, res: Response) => {
  const validationResult = validateMeetingRequestBody(req.body);
  if (!validationResult.valid || !validationResult.data) {
    // Ensure data is present for type safety
    console.error(
      'Payload validation failed for meeting-request-admin:',
      validationResult.error
    );
    return res
      .status(400)
      .json({
        message: validationResult.error?.message || 'Invalid request payload',
        event: validationResult.error?.event,
      });
  }

  // Cast to MeetingRequestBodyType because common-on-event-handler's publishToS3AndKafka
  // currently expects CreateDayScheduleBodyType. This will need to be generalized or publishToS3AndKafka
  // will need to be duplicated/made generic if payloads are very different and cannot be mapped.
  // For now, assuming the structure passed to S3/Kafka is acceptable as 'any' or a common base type.
  // Or, more correctly, publishToS3AndKafka should accept a more generic payload type if possible,
  // or a specific one if its internal S3/Kafka message structure relies on specific fields not common to all.
  // For this step, we'll assume MeetingRequestBodyType can be handled by publishToS3AndKafka's stringification.
  const validatedPayload = validationResult.data as any; // Using 'as any' to bypass strict type check for now

  try {
    const publishResult = await publishToS3AndKafka(
      validatedPayload,
      kafkaMeetingReqTemplateTopic,
      s3Client,
      kafka
    );

    if (!publishResult.success) {
      console.error(
        'Failed to publish meeting request to S3/Kafka (admin):',
        publishResult.error
      );
      return res
        .status(500)
        .json({
          message: 'Failed to process meeting request.',
          details: publishResult.error?.message,
        });
    }

    return res
      .status(202)
      .json({ message: 'Successfully queued meeting request processing.' });
  } catch (e: any) {
    console.error('Unexpected error in meeting-request-admin handler:', e);
    return res
      .status(500)
      .json({
        message: 'An unexpected internal server error occurred.',
        details: e.message,
      });
  }
};

export default handler;
