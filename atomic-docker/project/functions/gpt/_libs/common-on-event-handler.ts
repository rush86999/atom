import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { Kafka, CompressionTypes, ProducerRecord } from 'kafkajs';
import { v4 as uuidv4 } from 'uuid';

// Assuming this type definition exists or should be created
// Based on typical payload for create-day-schedule
export interface CreateDayScheduleBodyType {
  userId: string;
  startDate: string; // YYYY-MM-DD
  endDate: string; // YYYY-MM-DD
  timezone: string;
  tasks: Array<{
    // Assuming tasks is an array of objects
    summary: string;
    description?: string;
    start_time?: string; // e.g., "09:00 AM" - might be optional if all-day
    end_time?: string; // e.g., "10:00 AM"
    duration?: number; // in minutes - alternative to end_time
  }>;
  isAllDay?: boolean;
  prompt?: string; // If this is part of the body to be validated/passed
  // Add any other fields that are part of the body and need validation/passing
}

// Import MeetingRequestBodyType
import { MeetingRequestBodyType } from './types';

interface DayScheduleValidationResult {
  // Renamed for clarity
  valid: boolean;
  error?: { message: string; event: any };
  data?: CreateDayScheduleBodyType;
}

interface MeetingRequestValidationResult {
  valid: boolean;
  error?: { message: string; event: any };
  data?: MeetingRequestBodyType;
}

export const validateDaySchedulePayload = (
  body: any
): DayScheduleValidationResult => {
  if (!body) {
    return {
      valid: false,
      error: { message: 'Request body is missing.', event: body },
    };
  }
  if (!body.userId) {
    return {
      valid: false,
      error: { message: 'userId is required.', event: body },
    };
  }
  if (!body.startDate) {
    return {
      valid: false,
      error: { message: 'startDate is required.', event: body },
    };
  }
  if (!body.endDate) {
    return {
      valid: false,
      error: { message: 'endDate is required.', event: body },
    };
  }
  if (!body.timezone) {
    return {
      valid: false,
      error: { message: 'timezone is required.', event: body },
    };
  }
  if (!body.tasks || !Array.isArray(body.tasks) || body.tasks.length === 0) {
    return {
      valid: false,
      error: {
        message: 'tasks array is required and must not be empty.',
        event: body,
      },
    };
  }
  // Add more specific validation for task items if needed
  for (const task of body.tasks) {
    if (!task.summary) {
      return {
        valid: false,
        error: { message: 'Each task must have a summary.', event: body },
      };
    }
  }

  return { valid: true, data: body as CreateDayScheduleBodyType };
};

interface PublishResult {
  success: boolean;
  error?: { message: string; details?: any };
}

let s3: S3Client | undefined;
let kafka: Kafka | undefined;
let kafkaProducer: any; // kafkajs.Producer is not directly exposed, using 'any'
import { kafkaBrokers, s3Endpoint } from './constants'; // Import new constants

const initializeS3Client = () => {
  if (!s3) {
    const s3Config: any = { region: process.env.AWS_REGION || 'us-east-1' };
    if (s3Endpoint) {
      // Use s3Endpoint from constants if available
      s3Config.endpoint = s3Endpoint;
      s3Config.forcePathStyle = true; // Often needed for MinIO or local S3 setups
    }
    // Add credentials if explicitly needed and not handled by environment/IAM
    // This part depends on how credentials are managed in your environment.
    // For example, if using specific access keys:
    // if (process.env.S3_ACCESS_KEY && process.env.S3_SECRET_KEY) {
    //     s3Config.credentials = {
    //         accessKeyId: process.env.S3_ACCESS_KEY,
    //         secretAccessKey: process.env.S3_SECRET_KEY,
    //     };
    // }
    s3 = new S3Client(s3Config);
  }
  return s3;
};

const initializeKafka = () => {
  if (!kafka) {
    // Basic Kafka configuration
    const kafkaConfig: any = {
      clientId: process.env.KAFKA_CLIENT_ID_COMMON || 'gpt-common-producer', // More specific default client ID
      brokers: kafkaBrokers, // Use kafkaBrokers from constants
    };

    // Optional SASL configuration (example: plain)
    if (process.env.KAFKA_USERNAME && process.env.KAFKA_PASSWORD) {
      kafkaConfig.sasl = {
        mechanism: 'plain', // Or 'scram-sha-256', 'scram-sha-512'
        username: process.env.KAFKA_USERNAME,
        password: process.env.KAFKA_PASSWORD,
      };
    }
    // Optional SSL configuration
    // if (process.env.KAFKA_SSL_ENABLED === 'true') {
    //   kafkaConfig.ssl = true; // or an object with ca, key, cert
    // }

    kafka = new Kafka(kafkaConfig);
  }
  return kafka;
};

const getKafkaProducer = async (kafkaInstance: Kafka) => {
  if (!kafkaProducer) {
    kafkaProducer = kafkaInstance.producer();
    await kafkaProducer.connect();
  }
  return kafkaProducer;
};

export const publishToS3AndKafka = async (
  payload: CreateDayScheduleBodyType,
  kafkaTopic: string,
  s3ClientInstance?: S3Client,
  kafkaInstance?: Kafka
): Promise<PublishResult> => {
  const currentS3Client = s3ClientInstance || initializeS3Client();
  const currentKafka = kafkaInstance || initializeKafka();

  const s3Key = `day-schedules/${payload.userId}/${uuidv4()}.json`;
  const producer = await getKafkaProducer(currentKafka);
  const transaction = await producer.transaction();

  try {
    // 1. Upload to S3
    const s3Command = new PutObjectCommand({
      Bucket: process.env.S3_BUCKET_NAME,
      Key: s3Key,
      Body: JSON.stringify(payload),
      ContentType: 'application/json',
    });
    await currentS3Client.send(s3Command);
    console.log(`Successfully uploaded to S3: ${s3Key}`);

    // 2. Send to Kafka
    const kafkaMessage: ProducerRecord = {
      topic: kafkaTopic,
      messages: [
        {
          key: payload.userId, // Good practice to use a key for partitioning
          value: JSON.stringify({ ...payload, s3Key }), // Include S3 key in Kafka message
        },
      ],
      compression: CompressionTypes.Gzip,
    };
    await transaction.send(kafkaMessage);
    console.log(`Successfully sent to Kafka topic ${kafkaTopic}`);

    await transaction.commit();
    return { success: true };
  } catch (e: any) {
    console.log('Error during S3 upload or Kafka publish:', e);
    try {
      await transaction.abort();
      console.log('Kafka transaction aborted.');
    } catch (abortError: any) {
      console.log('Failed to abort Kafka transaction:', abortError);
    }
    return {
      success: false,
      error: {
        message: 'Failed to publish to S3 or Kafka.',
        details: e.message || e,
      },
    };
  }
  // Note: Producer disconnect is usually handled globally or on shutdown, not per message.
  // If you need to disconnect producer after each call (not recommended for performance),
  // you'd add `await producer.disconnect(); kafkaProducer = undefined;` here or in a finally block.
};

// Optional: function to disconnect Kafka producer during cleanup/shutdown if needed
export const disconnectKafkaProducer = async () => {
  if (kafkaProducer) {
    try {
      await kafkaProducer.disconnect();
      console.log('Kafka producer disconnected.');
      kafkaProducer = undefined;
    } catch (e: any) {
      console.error('Error disconnecting Kafka producer:', e.message);
    }
  }
};

export const validateMeetingRequestBody = (
  body: any
): MeetingRequestValidationResult => {
  if (!body) {
    return {
      valid: false,
      error: { message: 'Request body is missing.', event: body },
    };
  }

  const requiredFields: Array<keyof MeetingRequestBodyType> = [
    'userId',
    'clientType',
    'userTimezone',
    'userDateContext',
    'attendees',
    'subject',
    'prompt',
    'durationMinutes',
    'emailTo',
    'emailName',
    'yesLink',
    'noLink',
    'receiver',
    'sender',
    // 'shareAvailability' is boolean, will default to false if not present, usually fine.
    // Optional fields like availabilityUserDateStart/End are validated conditionally in orchestrator if shareAvailability is true.
  ];

  for (const field of requiredFields) {
    if (
      body[field] === undefined ||
      body[field] === null ||
      body[field] === ''
    ) {
      // Check for empty string too
      return {
        valid: false,
        error: { message: `${String(field)} is required.`, event: body },
      };
    }
  }

  // Type checks (basic)
  if (typeof body.userId !== 'string')
    return {
      valid: false,
      error: { message: 'userId must be a string.', event: body },
    };
  if (
    typeof body.clientType !== 'string' ||
    !['ios', 'android', 'web', 'atomic-web'].includes(body.clientType)
  ) {
    return {
      valid: false,
      error: { message: 'Invalid clientType.', event: body },
    };
  }
  if (typeof body.userTimezone !== 'string')
    return {
      valid: false,
      error: { message: 'userTimezone must be a string.', event: body },
    };
  if (typeof body.attendees !== 'string')
    return {
      valid: false,
      error: { message: 'attendees must be a string.', event: body },
    };
  if (typeof body.subject !== 'string')
    return {
      valid: false,
      error: { message: 'subject must be a string.', event: body },
    };
  if (typeof body.prompt !== 'string')
    return {
      valid: false,
      error: { message: 'prompt must be a string.', event: body },
    };
  if (typeof body.durationMinutes !== 'number')
    return {
      valid: false,
      error: { message: 'durationMinutes must be a number.', event: body },
    };
  if (typeof body.emailTo !== 'string')
    return {
      valid: false,
      error: { message: 'emailTo must be a string.', event: body },
    };
  if (typeof body.emailName !== 'string')
    return {
      valid: false,
      error: { message: 'emailName must be a string.', event: body },
    };
  if (typeof body.yesLink !== 'string')
    return {
      valid: false,
      error: { message: 'yesLink must be a string.', event: body },
    };
  if (typeof body.noLink !== 'string')
    return {
      valid: false,
      error: { message: 'noLink must be a string.', event: body },
    };
  if (typeof body.receiver !== 'string')
    return {
      valid: false,
      error: { message: 'receiver must be a string.', event: body },
    };
  if (typeof body.sender !== 'string')
    return {
      valid: false,
      error: { message: 'sender must be a string.', event: body },
    };
  if (
    body.shareAvailability !== undefined &&
    typeof body.shareAvailability !== 'boolean'
  ) {
    return {
      valid: false,
      error: {
        message: 'shareAvailability must be a boolean if provided.',
        event: body,
      },
    };
  }

  return { valid: true, data: body as MeetingRequestBodyType };
};
