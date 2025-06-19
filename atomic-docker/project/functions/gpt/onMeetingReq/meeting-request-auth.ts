import { Request, Response } from 'express';
import { S3Client } from '@aws-sdk/client-s3';
import { Kafka } from 'kafkajs';
import {
    validateMeetingRequestBody,
    publishToS3AndKafka
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
    clientId: process.env.KAFKA_CLIENT_ID_MEETING_REQ_AUTH || 'gpt-meeting-req-auth-producer',
    brokers: (process.env.KAFKA_BROKERS || 'localhost:9092').split(','),
    sasl: process.env.KAFKA_USERNAME && process.env.KAFKA_PASSWORD ? {
        mechanism: 'plain',
        username: process.env.KAFKA_USERNAME,
        password: process.env.KAFKA_PASSWORD,
      } : undefined,
});

export const handler = async (req: Request, res: Response) => {
    const validationResult = validateMeetingRequestBody(req.body);
    if (!validationResult.valid || !validationResult.data) { // Ensure data is present for type safety
        console.error('Payload validation failed for meeting-request-auth:', validationResult.error);
        return res.status(400).json({ message: validationResult.error?.message || "Invalid request payload", event: validationResult.error?.event });
    }

    const validatedPayload = validationResult.data as any; // Using 'as any' for now, see note in admin refactor

    try {
        const publishResult = await publishToS3AndKafka(
            validatedPayload,
            kafkaMeetingReqTemplateTopic,
            s3Client,
            kafka
        );

        if (!publishResult.success) {
            console.error('Failed to publish meeting request to S3/Kafka (auth):', publishResult.error);
            return res.status(500).json({ message: 'Failed to process meeting request.', details: publishResult.error?.message });
        }

        return res.status(200).json({ message: 'Successfully queued meeting request processing.' }); // Auth uses 200

    } catch (e: any) {
        console.error('Unexpected error in meeting-request-auth handler:', e);
        return res.status(500).json({ message: 'An unexpected internal server error occurred.', details: e.message });
    }
};

export default handler;
