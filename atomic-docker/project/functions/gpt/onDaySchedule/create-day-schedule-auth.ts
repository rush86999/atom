import { Request, Response } from 'express';
import { S3Client } from '@aws-sdk/client-s3';
import { Kafka } from 'kafkajs';
import {
  validateDaySchedulePayload,
  publishToS3AndKafka,
  // CreateDayScheduleBodyType // Assuming this type might come from common handler or types file
} from '../_libs/common-on-event-handler';
// Assuming kafkaOnDayScheduleTopic might be defined in constants or ENV
import { kafkaOnDayScheduleTopic as KAFKA_ON_DAY_SCHEDULE_TOPIC_AUTH } from '../_libs/constants'; // Use a specific topic name or the same if applicable

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
  clientId: process.env.KAFKA_CLIENT_ID_AUTH || 'gpt-auth-producer', // Potentially different clientId for auth context
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
  // 1. Validate Payload
  const validationResult = validateDaySchedulePayload(req.body);
  if (!validationResult.valid || !validationResult.data) {
    console.error(
      'Payload validation failed for create-day-schedule-auth:',
      validationResult.error
    );
    return res
      .status(400)
      .json({
        message: validationResult.error?.message || 'Invalid request payload',
        event: validationResult.error?.event,
      });
  }

  const validatedPayload = validationResult.data;

  try {
    // 2. Publish to S3 and Kafka
    const publishResult = await publishToS3AndKafka(
      validatedPayload,
      KAFKA_ON_DAY_SCHEDULE_TOPIC_AUTH, // Use the specific auth topic
      s3Client,
      kafka
    );

    if (!publishResult.success) {
      console.error(
        'Failed to publish to S3/Kafka for create-day-schedule-auth:',
        publishResult.error
      );
      return res
        .status(500)
        .json({
          message: 'Failed to process schedule due to an internal error.',
          details: publishResult.error?.message,
        });
    }

    // 3. Respond to client
    // Auth handler returns 200 for success
    return res.status(200).json({
      // Changed to .json for consistency, though original was .send
      message: 'Successfully created day schedule',
    });
  } catch (e: any) {
    console.error('Unexpected error in create-day-schedule-auth handler:', e);
    return res
      .status(500)
      .json({
        message: 'An unexpected internal server error occurred.',
        details: e.message,
      });
  }
};

export default handler;
