import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { Kafka, CompressionTypes } from 'kafkajs';
import { v4 as uuidv4 } from 'uuid';
export const validateDaySchedulePayload = (body) => {
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
    return { valid: true, data: body };
};
let s3;
let kafka;
let kafkaProducer; // kafkajs.Producer is not directly exposed, using 'any'
import { kafkaBrokers, s3Endpoint } from './constants'; // Import new constants
const initializeS3Client = () => {
    if (!s3) {
        const s3Config = { region: process.env.AWS_REGION || 'us-east-1' };
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
        const kafkaConfig = {
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
const getKafkaProducer = async (kafkaInstance) => {
    if (!kafkaProducer) {
        kafkaProducer = kafkaInstance.producer();
        await kafkaProducer.connect();
    }
    return kafkaProducer;
};
export const publishToS3AndKafka = async (payload, kafkaTopic, s3ClientInstance, kafkaInstance) => {
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
        const kafkaMessage = {
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
    }
    catch (e) {
        console.log('Error during S3 upload or Kafka publish:', e);
        try {
            await transaction.abort();
            console.log('Kafka transaction aborted.');
        }
        catch (abortError) {
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
        }
        catch (e) {
            console.error('Error disconnecting Kafka producer:', e.message);
        }
    }
};
export const validateMeetingRequestBody = (body) => {
    if (!body) {
        return {
            valid: false,
            error: { message: 'Request body is missing.', event: body },
        };
    }
    const requiredFields = [
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
        if (body[field] === undefined ||
            body[field] === null ||
            body[field] === '') {
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
    if (typeof body.clientType !== 'string' ||
        !['ios', 'android', 'web', 'atomic-web'].includes(body.clientType)) {
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
    if (body.shareAvailability !== undefined &&
        typeof body.shareAvailability !== 'boolean') {
        return {
            valid: false,
            error: {
                message: 'shareAvailability must be a boolean if provided.',
                event: body,
            },
        };
    }
    return { valid: true, data: body };
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY29tbW9uLW9uLWV2ZW50LWhhbmRsZXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjb21tb24tb24tZXZlbnQtaGFuZGxlci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEVBQUUsUUFBUSxFQUFFLGdCQUFnQixFQUFFLE1BQU0sb0JBQW9CLENBQUM7QUFDaEUsT0FBTyxFQUFFLEtBQUssRUFBRSxnQkFBZ0IsRUFBa0IsTUFBTSxTQUFTLENBQUM7QUFDbEUsT0FBTyxFQUFFLEVBQUUsSUFBSSxNQUFNLEVBQUUsTUFBTSxNQUFNLENBQUM7QUFzQ3BDLE1BQU0sQ0FBQyxNQUFNLDBCQUEwQixHQUFHLENBQ3hDLElBQVMsRUFDb0IsRUFBRTtJQUMvQixJQUFJLENBQUMsSUFBSSxFQUFFLENBQUM7UUFDVixPQUFPO1lBQ0wsS0FBSyxFQUFFLEtBQUs7WUFDWixLQUFLLEVBQUUsRUFBRSxPQUFPLEVBQUUsMEJBQTBCLEVBQUUsS0FBSyxFQUFFLElBQUksRUFBRTtTQUM1RCxDQUFDO0lBQ0osQ0FBQztJQUNELElBQUksQ0FBQyxJQUFJLENBQUMsTUFBTSxFQUFFLENBQUM7UUFDakIsT0FBTztZQUNMLEtBQUssRUFBRSxLQUFLO1lBQ1osS0FBSyxFQUFFLEVBQUUsT0FBTyxFQUFFLHFCQUFxQixFQUFFLEtBQUssRUFBRSxJQUFJLEVBQUU7U0FDdkQsQ0FBQztJQUNKLENBQUM7SUFDRCxJQUFJLENBQUMsSUFBSSxDQUFDLFNBQVMsRUFBRSxDQUFDO1FBQ3BCLE9BQU87WUFDTCxLQUFLLEVBQUUsS0FBSztZQUNaLEtBQUssRUFBRSxFQUFFLE9BQU8sRUFBRSx3QkFBd0IsRUFBRSxLQUFLLEVBQUUsSUFBSSxFQUFFO1NBQzFELENBQUM7SUFDSixDQUFDO0lBQ0QsSUFBSSxDQUFDLElBQUksQ0FBQyxPQUFPLEVBQUUsQ0FBQztRQUNsQixPQUFPO1lBQ0wsS0FBSyxFQUFFLEtBQUs7WUFDWixLQUFLLEVBQUUsRUFBRSxPQUFPLEVBQUUsc0JB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QUksQ0FBQyxTQUFTLEtBQUssUUFBUTtRQUNwQyxPQUFPO1lBQ0wsS0FBSyxFQUFFLEtBQUs7WUFDWixLQUFLLEVBQUUsRUFBRSxPQUFPLEVBQUUsNkJBQTZCLEVBQUUsS0FBSyxFQUFFLElBQUksRUFBRTtTQUMvRCxDQUFDO0lBQ0osSUFBSSxPQUFPLElBQUksQ0FBQyxPQUFPLEtBQUssUUFBUTtRQUNsQyxPQUFPO1lBQ0wsS0FBSyxFQUFFLEtBQUs7WUFDWixLQUFLLEVBQUUsRUFBRSxPQUFPLEVBQUUsMkJBQTJCLEVBQUUsS0FBSyxFQUFFLElBQUksRUFBRTtTQUM3RCxDQUFDO0lBQ0osSUFBSSxPQUFPLElBQUksQ0FBQyxNQUFNLEtBQUssUUFBUTtRQUNqQyxPQUFPO1lBQ0wsS0FBSyxFQUFFLEtBQUs7WUFDWixLQUFLLEVBQUUsRUFBRSxPQUFPLEVBQUUsMEJBQTBCLEVBQUUsS0FBSyxFQUFFLElBQUksRUFBRTtTQUM1RCxDQUFDO0lBQ0osSUFBSSxPQUFPLElBQUksQ0FBQyxlQUFlLEtBQUssUUFBUTtRQUMxQyxPQUFPO1lBQ0wsS0FBSyxFQUFFLEtBQUs7WUFDWixLQUFLLEVBQUUsRUFBRSxPQUFPLEVBQUUsbUNBQW1DLEVBQUUsS0FBSyxFQUFFLElBQUksRUFBRTtTQUNyRSxDQUFDO0lBQ0osSUFBSSxPQUFPLElBQUksQ0FBQyxPQUFPLEtBQUssUUFBUTtRQUNsQyxPQUFPO1lBQ0wsS0FBSyxFQUFFLEtBQUs7WUFDWixLQUFLLEVBQUUsRUFBRSxPQUFPLEVBQUUsMkJBQTJCLEVBQUUsS0FBSyxFQUFFLElBQUksRUFBRTtTQUM3RCxDQUFDO0lBQ0osSUFBSSxPQUFPLElBQUksQ0FBQyxTQUFTLEtBQUssUUFBUTtRQUNwQyxPQUFPO1lBQ0wsS0FBSyxFQUFFLEtBQUs7WUFDWixLQUFLLEVBQUUsRUFBRSxPQUFPLEVBQUUsNkJBQTZCLEVBQUUsS0FBSyxFQUFFLElBQUksRUFBRTtTQUMvRCxDQUFDO0lBQ0osSUFBSSxPQUFPLElBQUksQ0FBQyxPQUFPLEtBQUssUUFBUTtRQUNsQyxPQUFPO1lBQ0wsS0FBSyxFQUFFLEtBQUs7WUFDWixLQUFLLEVBQUUsRUFBRSxPQUFPLEVBQUUsMkJBQTJCLEVBQUUsS0FBSyxFQUFFLElBQUksRUFBRTtTQUM3RCxDQUFDO0lBQ0osSUFBSSxPQUFPLElBQUksQ0FBQyxNQUFNLEtBQUssUUFBUTtRQUNqQyxPQUFPO1lBQ0wsS0FBSyxFQUFFLEtBQUs7WUFDWixLQUFLLEVBQUUsRUFBRSxPQUFPLEVBQUUsMEJBQTBCLEVBQUUsS0FBSyxFQUFFLElBQUksRUFBRTtTQUM1RCxDQUFDO0lBQ0osSUFBSSxPQUFPLElBQUksQ0FBQyxRQUFRLEtBQUssUUFBUTtRQUNuQyxPQUFPO1lBQ0wsS0FBSyxFQUFFLEtBQUs7WUFDWixLQUFLLEVBQUUsRUFBRSxPQUFPLEVBQUUsNEJBQTRCLEVBQUUsS0FBSyxFQUFFLElBQUksRUFBRTtTQUM5RCxDQUFDO0lBQ0osSUFBSSxPQUFPLElBQUksQ0FBQyxNQUFNLEtBQUssUUFBUTtRQUNqQyxPQUFPO1lBQ0wsS0FBSyxFQUFFLEtBQUs7WUFDWixLQUFLLEVBQUUsRUFBRSxPQUFPLEVBQUUsMEJBQTBCLEVBQUUsS0FBSyxFQUFFLElBQUksRUFBRTtTQUM1RCxDQUFDO0lBQ0osSUFDRSxJQUFJLENBQUMsaUJBQWlCLEtBQUssU0FBUztRQUNwQyxPQUFPLElBQUksQ0FBQyxpQkFBaUIsS0FBSyxTQUFTLEVBQzNDLENBQUM7UUFDRCxPQUFPO1lBQ0wsS0FBSyxFQUFFLEtBQUs7WUFDWixLQUFLLEVBQUU7Z0JBQ0wsT0FBTyxFQUFFLGtEQUFrRDtnQkFDM0QsS0FBSyxFQUFFLElBQUk7YUFDWjtTQUNGLENBQUM7SUFDSixDQUFDO0lBRUQsT0FBTyxFQUFFLEtBQUssRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLElBQThCLEVBQUUsQ0FBQztBQUMvRCxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBTM0NsaWVudCwgUHV0T2JqZWN0Q29tbWFuZCB9IGZyb20gJ0Bhd3Mtc2RrL2NsaWVudC1zMyc7XG5pbXBvcnQgeyBLYWZrYSwgQ29tcHJlc3Npb25UeXBlcywgUHJvZHVjZXJSZWNvcmQgfSBmcm9tICdrYWZrYWpzJztcbmltcG9ydCB7IHY0IGFzIHV1aWR2NCB9IGZyb20gJ3V1aWQnO1xuXG4vLyBBc3N1bWluZyB0aGlzIHR5cGUgZGVmaW5pdGlvbiBleGlzdHMgb3Igc2hvdWxkIGJlIGNyZWF0ZWRcbi8vIEJhc2VkIG9uIHR5cGljYWwgcGF5bG9hZCBmb3IgY3JlYXRlLWRheS1zY2hlZHVsZVxuZXhwb3J0IGludGVyZmFjZSBDcmVhdGVEYXlTY2hlZHVsZUJvZHlUeXBlIHtcbiAgdXNlcklkOiBzdHJpbmc7XG4gIHN0YXJ0RGF0ZTogc3RyaW5nOyAvLyBZWVlZLU1NLUREXG4gIGVuZERhdGU6IHN0cmluZzsgLy8gWVlZWS1NTS1ERFxuICB0aW1lem9uZTogc3RyaW5nO1xuICB0YXNrczogQXJyYXk8e1xuICAgIC8vIEFzc3VtaW5nIHRhc2tzIGlzIGFuIGFycmF5IG9mIG9iamVjdHNcbiAgICBzdW1tYXJ5OiBzdHJpbmc7XG4gICAgZGVzY3JpcHRpb24/OiBzdHJpbmc7XG4gICAgc3RhcnRfdGltZT86IHN0cmluZzsgLy8gZS5nLiwgXCIwOTowMCBBTVwiIC0gbWlnaHQgYmUgb3B0aW9uYWwgaWYgYWxsLWRheVxuICAgIGVuZF90aW1lPzogc3RyaW5nOyAvLyBlLmcuLCBcIjEwOjAwIEFNXCJcbiAgICBkdXJhdGlvbj86IG51bWJlcjsgLy8gaW4gbWludXRlcyAtIGFsdGVybmF0aXZlIHRvIGVuZF90aW1lXG4gIH0+O1xuICBpc0FsbERheT86IGJvb2xlYW47XG4gIHByb21wdD86IHN0cmluZzsgLy8gSWYgdGhpcyBpcyBwYXJ0IG9mIHRoZSBib2R5IHRvIGJlIHZhbGlkYXRlZC9wYXNzZWRcbiAgLy8gQWRkIGFueSBvdGhlciBmaWVsZHMgdGhhdCBhcmUgcGFydCBvZiB0aGUgYm9keSBhbmQgbmVlZCB2YWxpZGF0aW9uL3Bhc3Npbmdcbn1cblxuLy8gSW1wb3J0IE1lZXRpbmdSZXF1ZXN0Qm9keVR5cGVcbmltcG9ydCB7IE1lZXRpbmdSZXF1ZXN0Qm9keVR5cGUgfSBmcm9tICcuL3R5cGVzJztcblxuaW50ZXJmYWNlIERheVNjaGVkdWxlVmFsaWRhdGlvblJlc3VsdCB7XG4gIC8vIFJlbmFtZWQgZm9yIGNsYXJpdHlcbiAgdmFsaWQ6IGJvb2xlYW47XG4gIGVycm9yPzogeyBtZXNzYWdlOiBzdHJpbmc7IGV2ZW50OiBhbnkgfTtcbiAgZGF0YT86IENyZWF0ZURheVNjaGVkdWxlQm9keVR5cGU7XG59XG5cbmludGVyZmFjZSBNZWV0aW5nUmVxdWVzdFZhbGlkYXRpb25SZXN1bHQge1xuICB2YWxpZDogYm9vbGVhbjtcbiAgZXJyb3I/OiB7IG1lc3NhZ2U6IHN0cmluZzsgZXZlbnQ6IGFueSB9O1xuICBkYXRhPzogTWVldGluZ1JlcXVlc3RCb2R5VHlwZTtcbn1cblxuZXhwb3J0IGNvbnN0IHZhbGlkYXRlRGF5U2NoZWR1bGVQYXlsb2FkID0gKFxuICBib2R5OiBhbnlcbik6IERheVNjaGVkdWxlVmFsaWRhdGlvblJlc3VsdCA9PiB7XG4gIGlmICghYm9keSkge1xuICAgIHJldHVybiB7XG4gICAgICB2YWxpZDogZmFsc2UsXG4gICAgICBlcnJvcjogeyBtZXNzYWdlOiAnUmVxdWVzdCBib2R5IGlzIG1pc3NpbmcuJywgZXZlbnQ6IGJvZHkgfSxcbiAgICB9O1xuICB9XG4gIGlmICghYm9keS51c2VySWQpIHtcbiAgICByZXR1cm4ge1xuICAgICAgdmFsaWQ6IGZhbHNlLFxuICAgICAgZXJyb3I6IHsgbWVzc2FnZTogJ3VzZXJJZCBpcyByZXF1aXJlZC4nLCBldmVudDogYm9keSB9LFxuICAgIH07XG4gIH1cbiAgaWYgKCFib2R5LnN0YXJ0RGF0ZSkge1xuICAgIHJldHVybiB7XG4gICAgICB2YWxpZDogZmFsc2UsXG4gICAgICBlcnJvcjogeyBtZXNzYWdlOiAnc3RhcnREYXRlIGlzIHJlcXVpcmVkLicsIGV2ZW50OiBib2R5IH0sXG4gICAgfTtcbiAgfVxuICBpZiAoIWJvZHkuZW5kRGF0ZSkge1xuICAgIHJldHVybiB7XG4gICAgICB2YWxpZDogZmFsc2UsXG4gICAgICBlcnJvcjogeyBtZXNzYWdlOiAnZW5kRGF0ZSBpcyByZXF1aXJlZC4nLCBldmVudDogYm9keSB9LFxuICAgIH07XG4gIH1cbiAgaWYgKCFib2R5LnRpbWV6b25lKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIHZhbGlkOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7IG1lc3NhZ2U6ICd0aW1lem9uZSBpcyByZXF1aXJlZC4nLCBldmVudDogYm9keSB9LFxuICAgIH07XG4gIH1cbiAgaWYgKCFib2R5LnRhc2tzIHx8ICFBcnJheS5pc0FycmF5KGJvZHkudGFza3MpIHx8IGJvZHkudGFza3MubGVuZ3RoID09PSAwKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIHZhbGlkOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIG1lc3NhZ2U6ICd0YXNrcyBhcnJheSBpcyByZXF1aXJlZCBhbmQgbXVzdCBub3QgYmUgZW1wdHkuJyxcbiAgICAgICAgZXZlbnQ6IGJvZHksXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgLy8gQWRkIG1vcmUgc3BlY2lmaWMgdmFsaWRhdGlvbiBmb3IgdGFzayBpdGVtcyBpZiBuZWVkZWRcbiAgZm9yIChjb25zdCB0YXNrIG9mIGJvZHkudGFza3MpIHtcbiAgICBpZiAoIXRhc2suc3VtbWFyeSkge1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgdmFsaWQ6IGZhbHNlLFxuICAgICAgICBlcnJvcjogeyBtZXNzYWdlOiAnRWFjaCB0YXNrIG11c3QgaGF2ZSBhIHN1bW1hcnkuJywgZXZlbnQ6IGJvZHkgfSxcbiAgICAgIH07XG4gICAgfVxuICB9XG5cbiAgcmV0dXJuIHsgdmFsaWQ6IHRydWUsIGRhdGE6IGJvZHkgYXMgQ3JlYXRlRGF5U2NoZWR1bGVCb2R5VHlwZSB9O1xufTtcblxuaW50ZXJmYWNlIFB1Ymxpc2hSZXN1bHQge1xuICBzdWNjZXNzOiBib29sZWFuO1xuICBlcnJvcj86IHsgbWVzc2FnZTogc3RyaW5nOyBkZXRhaWxzPzogYW55IH07XG59XG5cbmxldCBzMzogUzNDbGllbnQgfCB1bmRlZmluZWQ7XG5sZXQga2Fma2E6IEthZmthIHwgdW5kZWZpbmVkO1xubGV0IGthZmthUHJvZHVjZXI6IGFueTsgLy8ga2Fma2Fqcy5Qcm9kdWNlciBpcyBub3QgZGlyZWN0bHkgZXhwb3NlZCwgdXNpbmcgJ2FueSdcbmltcG9ydCB7IGthZmthQnJva2VycywgczNFbmRwb2ludCB9IGZyb20gJy4vY29uc3RhbnRzJzsgLy8gSW1wb3J0IG5ldyBjb25zdGFudHNcblxuY29uc3QgaW5pdGlhbGl6ZVMzQ2xpZW50ID0gKCkgPT4ge1xuICBpZiAoIXMzKSB7XG4gICAgY29uc3QgczNDb25maWc6IGFueSA9IHsgcmVnaW9uOiBwcm9jZXNzLmVudi5BV1NfUkVHSU9OIHx8ICd1cy1lYXN0LTEnIH07XG4gICAgaWYgKHMzRW5kcG9pbnQpIHtcbiAgICAgIC8vIFVzZSBzM0VuZHBvaW50IGZyb20gY29uc3RhbnRzIGlmIGF2YWlsYWJsZVxuICAgICAgczNDb25maWcuZW5kcG9pbnQgPSBzM0VuZHBvaW50O1xuICAgICAgczNDb25maWcuZm9yY2VQYXRoU3R5bGUgPSB0cnVlOyAvLyBPZnRlbiBuZWVkZWQgZm9yIE1pbklPIG9yIGxvY2FsIFMzIHNldHVwc1xuICAgIH1cbiAgICAvLyBBZGQgY3JlZGVudGlhbHMgaWYgZXhwbGljaXRseSBuZWVkZWQgYW5kIG5vdCBoYW5kbGVkIGJ5IGVudmlyb25tZW50L0lBTVxuICAgIC8vIFRoaXMgcGFydCBkZXBlbmRzIG9uIGhvdyBjcmVkZW50aWFscyBhcmUgbWFuYWdlZCBpbiB5b3VyIGVudmlyb25tZW50LlxuICAgIC8vIEZvciBleGFtcGxlLCBpZiB1c2luZyBzcGVjaWZpYyBhY2Nlc3Mga2V5czpcbiAgICAvLyBpZiAocHJvY2Vzcy5lbnYuUzNfQUNDRVNTX0tFWSAmJiBwcm9jZXNzLmVudi5TM19TRUNSRVRfS0VZKSB7XG4gICAgLy8gICAgIHMzQ29uZmlnLmNyZWRlbnRpYWxzID0ge1xuICAgIC8vICAgICAgICAgYWNjZXNzS2V5SWQ6IHByb2Nlc3MuZW52LlMzX0FDQ0VTU19LRVksXG4gICAgLy8gICAgICAgICBzZWNyZXRBY2Nlc3NLZXk6IHByb2Nlc3MuZW52LlMzX1NFQ1JFVF9LRVksXG4gICAgLy8gICAgIH07XG4gICAgLy8gfVxuICAgIHMzID0gbmV3IFMzQ2xpZW50KHMzQ29uZmlnKTtcbiAgfVxuICByZXR1cm4gczM7XG59O1xuXG5jb25zdCBpbml0aWFsaXplS2Fma2EgPSAoKSA9PiB7XG4gIGlmICgha2Fma2EpIHtcbiAgICAvLyBCYXNpYyBLYWZrYSBjb25maWd1cmF0aW9uXG4gICAgY29uc3Qga2Fma2FDb25maWc6IGFueSA9IHtcbiAgICAgIGNsaWVudElkOiBwcm9jZXNzLmVudi5LQUZLQV9DTElFTlRfSURfQ09NTU9OIHx8ICdncHQtY29tbW9uLXByb2R1Y2VyJywgLy8gTW9yZSBzcGVjaWZpYyBkZWZhdWx0IGNsaWVudCBJRFxuICAgICAgYnJva2Vyczoga2Fma2FCcm9rZXJzLCAvLyBVc2Uga2Fma2FCcm9rZXJzIGZyb20gY29uc3RhbnRzXG4gICAgfTtcblxuICAgIC8vIE9wdGlvbmFsIFNBU0wgY29uZmlndXJhdGlvbiAoZXhhbXBsZTogcGxhaW4pXG4gICAgaWYgKHByb2Nlc3MuZW52LktBRktBX1VTRVJOQU1FICYmIHByb2Nlc3MuZW52LktBRktBX1BBU1NXT1JEKSB7XG4gICAgICBrYWZrYUNvbmZpZy5zYXNsID0ge1xuICAgICAgICBtZWNoYW5pc206ICdwbGFpbicsIC8vIE9yICdzY3JhbS1zaGEtMjU2JywgJ3NjcmFtLXNoYS01MTInXG4gICAgICAgIHVzZXJuYW1lOiBwcm9jZXNzLmVudi5LQUZLQV9VU0VSTkFNRSxcbiAgICAgICAgcGFzc3dvcmQ6IHByb2Nlc3MuZW52LktBRktBX1BBU1NXT1JELFxuICAgICAgfTtcbiAgICB9XG4gICAgLy8gT3B0aW9uYWwgU1NMIGNvbmZpZ3VyYXRpb25cbiAgICAvLyBpZiAocHJvY2Vzcy5lbnYuS0FGS0FfU1NMX0VOQUJMRUQgPT09ICd0cnVlJykge1xuICAgIC8vICAga2Fma2FDb25maWcuc3NsID0gdHJ1ZTsgLy8gb3IgYW4gb2JqZWN0IHdpdGggY2EsIGtleSwgY2VydFxuICAgIC8vIH1cblxuICAgIGthZmthID0gbmV3IEthZmthKGthZmthQ29uZmlnKTtcbiAgfVxuICByZXR1cm4ga2Fma2E7XG59O1xuXG5jb25zdCBnZXRLYWZrYVByb2R1Y2VyID0gYXN5bmMgKGthZmthSW5zdGFuY2U6IEthZmthKSA9PiB7XG4gIGlmICgha2Fma2FQcm9kdWNlcikge1xuICAgIGthZmthUHJvZHVjZXIgPSBrYWZrYUluc3RhbmNlLnByb2R1Y2VyKCk7XG4gICAgYXdhaXQga2Fma2FQcm9kdWNlci5jb25uZWN0KCk7XG4gIH1cbiAgcmV0dXJuIGthZmthUHJvZHVjZXI7XG59O1xuXG5leHBvcnQgY29uc3QgcHVibGlzaFRvUzNBbmRLYWZrYSA9IGFzeW5jIChcbiAgcGF5bG9hZDogQ3JlYXRlRGF5U2NoZWR1bGVCb2R5VHlwZSxcbiAga2Fma2FUb3BpYzogc3RyaW5nLFxuICBzM0NsaWVudEluc3RhbmNlPzogUzNDbGllbnQsXG4gIGthZmthSW5zdGFuY2U/OiBLYWZrYVxuKTogUHJvbWlzZTxQdWJsaXNoUmVzdWx0PiA9PiB7XG4gIGNvbnN0IGN1cnJlbnRTM0NsaWVudCA9IHMzQ2xpZW50SW5zdGFuY2UgfHwgaW5pdGlhbGl6ZVMzQ2xpZW50KCk7XG4gIGNvbnN0IGN1cnJlbnRLYWZrYSA9IGthZmthSW5zdGFuY2UgfHwgaW5pdGlhbGl6ZUthZmthKCk7XG5cbiAgY29uc3QgczNLZXkgPSBgZGF5LXNjaGVkdWxlcy8ke3BheWxvYWQudXNlcklkfS8ke3V1aWR2NCgpfS5qc29uYDtcbiAgY29uc3QgcHJvZHVjZXIgPSBhd2FpdCBnZXRLYWZrYVByb2R1Y2VyKGN1cnJlbnRLYWZrYSk7XG4gIGNvbnN0IHRyYW5zYWN0aW9uID0gYXdhaXQgcHJvZHVjZXIudHJhbnNhY3Rpb24oKTtcblxuICB0cnkge1xuICAgIC8vIDEuIFVwbG9hZCB0byBTM1xuICAgIGNvbnN0IHMzQ29tbWFuZCA9IG5ldyBQdXRPYmplY3RDb21tYW5kKHtcbiAgICAgIEJ1Y2tldDogcHJvY2Vzcy5lbnYuUzNfQlVDS0VUX05BTUUsXG4gICAgICBLZXk6IHMzS2V5LFxuICAgICAgQm9keTogSlNPTi5zdHJpbmdpZnkocGF5bG9hZCksXG4gICAgICBDb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgIH0pO1xuICAgIGF3YWl0IGN1cnJlbnRTM0NsaWVudC5zZW5kKHMzQ29tbWFuZCk7XG4gICAgY29uc29sZS5sb2coYFN1Y2Nlc3NmdWxseSB1cGxvYWRlZCB0byBTMzogJHtzM0tleX1gKTtcblxuICAgIC8vIDIuIFNlbmQgdG8gS2Fma2FcbiAgICBjb25zdCBrYWZrYU1lc3NhZ2U6IFByb2R1Y2VyUmVjb3JkID0ge1xuICAgICAgdG9waWM6IGthZmthVG9waWMsXG4gICAgICBtZXNzYWdlczogW1xuICAgICAgICB7XG4gICAgICAgICAga2V5OiBwYXlsb2FkLnVzZXJJZCwgLy8gR29vZCBwcmFjdGljZSB0byB1c2UgYSBrZXkgZm9yIHBhcnRpdGlvbmluZ1xuICAgICAgICAgIHZhbHVlOiBKU09OLnN0cmluZ2lmeSh7IC4uLnBheWxvYWQsIHMzS2V5IH0pLCAvLyBJbmNsdWRlIFMzIGtleSBpbiBLYWZrYSBtZXNzYWdlXG4gICAgICAgIH0sXG4gICAgICBdLFxuICAgICAgY29tcHJlc3Npb246IENvbXByZXNzaW9uVHlwZXMuR3ppcCxcbiAgICB9O1xuICAgIGF3YWl0IHRyYW5zYWN0aW9uLnNlbmQoa2Fma2FNZXNzYWdlKTtcbiAgICBjb25zb2xlLmxvZyhgU3VjY2Vzc2Z1bGx5IHNlbnQgdG8gS2Fma2EgdG9waWMgJHtrYWZrYVRvcGljfWApO1xuXG4gICAgYXdhaXQgdHJhbnNhY3Rpb24uY29tbWl0KCk7XG4gICAgcmV0dXJuIHsgc3VjY2VzczogdHJ1ZSB9O1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmxvZygnRXJyb3IgZHVyaW5nIFMzIHVwbG9hZCBvciBLYWZrYSBwdWJsaXNoOicsIGUpO1xuICAgIHRyeSB7XG4gICAgICBhd2FpdCB0cmFuc2FjdGlvbi5hYm9ydCgpO1xuICAgICAgY29uc29sZS5sb2coJ0thZmthIHRyYW5zYWN0aW9uIGFib3J0ZWQuJyk7XG4gICAgfSBjYXRjaCAoYWJvcnRFcnJvcjogYW55KSB7XG4gICAgICBjb25zb2xlLmxvZygnRmFpbGVkIHRvIGFib3J0IEthZmthIHRyYW5zYWN0aW9uOicsIGFib3J0RXJyb3IpO1xuICAgIH1cbiAgICByZXR1cm4ge1xuICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBtZXNzYWdlOiAnRmFpbGVkIHRvIHB1Ymxpc2ggdG8gUzMgb3IgS2Fma2EuJyxcbiAgICAgICAgZGV0YWlsczogZS5tZXNzYWdlIHx8IGUsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgLy8gTm90ZTogUHJvZHVjZXIgZGlzY29ubmVjdCBpcyB1c3VhbGx5IGhhbmRsZWQgZ2xvYmFsbHkgb3Igb24gc2h1dGRvd24sIG5vdCBwZXIgbWVzc2FnZS5cbiAgLy8gSWYgeW91IG5lZWQgdG8gZGlzY29ubmVjdCBwcm9kdWNlciBhZnRlciBlYWNoIGNhbGwgKG5vdCByZWNvbW1lbmRlZCBmb3IgcGVyZm9ybWFuY2UpLFxuICAvLyB5b3UnZCBhZGQgYGF3YWl0IHByb2R1Y2VyLmRpc2Nvbm5lY3QoKTsga2Fma2FQcm9kdWNlciA9IHVuZGVmaW5lZDtgIGhlcmUgb3IgaW4gYSBmaW5hbGx5IGJsb2NrLlxufTtcblxuLy8gT3B0aW9uYWw6IGZ1bmN0aW9uIHRvIGRpc2Nvbm5lY3QgS2Fma2EgcHJvZHVjZXIgZHVyaW5nIGNsZWFudXAvc2h1dGRvd24gaWYgbmVlZGVkXG5leHBvcnQgY29uc3QgZGlzY29ubmVjdEthZmthUHJvZHVjZXIgPSBhc3luYyAoKSA9PiB7XG4gIGlmIChrYWZrYVByb2R1Y2VyKSB7XG4gICAgdHJ5IHtcbiAgICAgIGF3YWl0IGthZmthUHJvZHVjZXIuZGlzY29ubmVjdCgpO1xuICAgICAgY29uc29sZS5sb2coJ0thZmthIHByb2R1Y2VyIGRpc2Nvbm5lY3RlZC4nKTtcbiAgICAgIGthZmthUHJvZHVjZXIgPSB1bmRlZmluZWQ7XG4gICAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgICBjb25zb2xlLmVycm9yKCdFcnJvciBkaXNjb25uZWN0aW5nIEthZmthIHByb2R1Y2VyOicsIGUubWVzc2FnZSk7XG4gICAgfVxuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdmFsaWRhdGVNZWV0aW5nUmVxdWVzdEJvZHkgPSAoXG4gIGJvZHk6IGFueVxuKTogTWVldGluZ1JlcXVlc3RWYWxpZGF0aW9uUmVzdWx0ID0+IHtcbiAgaWYgKCFib2R5KSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIHZhbGlkOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7IG1lc3NhZ2U6ICdSZXF1ZXN0IGJvZHkgaXMgbWlzc2luZy4nLCBldmVudDogYm9keSB9LFxuICAgIH07XG4gIH1cblxuICBjb25zdCByZXF1aXJlZEZpZWxkczogQXJyYXk8a2V5b2YgTWVldGluZ1JlcXVlc3RCb2R5VHlwZT4gPSBbXG4gICAgJ3VzZXJJZCcsXG4gICAgJ2NsaWVudFR5cGUnLFxuICAgICd1c2VyVGltZXpvbmUnLFxuICAgICd1c2VyRGF0ZUNvbnRleHQnLFxuICAgICdhdHRlbmRlZXMnLFxuICAgICdzdWJqZWN0JyxcbiAgICAncHJvbXB0JyxcbiAgICAnZHVyYXRpb25NaW51dGVzJyxcbiAgICAnZW1haWxUbycsXG4gICAgJ2VtYWlsTmFtZScsXG4gICAgJ3llc0xpbmsnLFxuICAgICdub0xpbmsnLFxuICAgICdyZWNlaXZlcicsXG4gICAgJ3NlbmRlcicsXG4gICAgLy8gJ3NoYXJlQXZhaWxhYmlsaXR5JyBpcyBib29sZWFuLCB3aWxsIGRlZmF1bHQgdG8gZmFsc2UgaWYgbm90IHByZXNlbnQsIHVzdWFsbHkgZmluZS5cbiAgICAvLyBPcHRpb25hbCBmaWVsZHMgbGlrZSBhdmFpbGFiaWxpdHlVc2VyRGF0ZVN0YXJ0L0VuZCBhcmUgdmFsaWRhdGVkIGNvbmRpdGlvbmFsbHkgaW4gb3JjaGVzdHJhdG9yIGlmIHNoYXJlQXZhaWxhYmlsaXR5IGlzIHRydWUuXG4gIF07XG5cbiAgZm9yIChjb25zdCBmaWVsZCBvZiByZXF1aXJlZEZpZWxkcykge1xuICAgIGlmIChcbiAgICAgIGJvZHlbZmllbGRdID09PSB1bmRlZmluZWQgfHxcbiAgICAgIGJvZHlbZmllbGRdID09PSBudWxsIHx8XG4gICAgICBib2R5W2ZpZWxkXSA9PT0gJydcbiAgICApIHtcbiAgICAgIC8vIENoZWNrIGZvciBlbXB0eSBzdHJpbmcgdG9vXG4gICAgICByZXR1cm4ge1xuICAgICAgICB2YWxpZDogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7IG1lc3NhZ2U6IGAke1N0cmluZyhmaWVsZCl9IGlzIHJlcXVpcmVkLmAsIGV2ZW50OiBib2R5IH0sXG4gICAgICB9O1xuICAgIH1cbiAgfVxuXG4gIC8vIFR5cGUgY2hlY2tzIChiYXNpYylcbiAgaWYgKHR5cGVvZiBib2R5LnVzZXJJZCAhPT0gJ3N0cmluZycpXG4gICAgcmV0dXJuIHtcbiAgICAgIHZhbGlkOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7IG1lc3NhZ2U6ICd1c2VySWQgbXVzdCBiZSBhIHN0cmluZy4nLCBldmVudDogYm9keSB9LFxuICAgIH07XG4gIGlmIChcbiAgICB0eXBlb2YgYm9keS5jbGllbnRUeXBlICE9PSAnc3RyaW5nJyB8fFxuICAgICFbJ2lvcycsICdhbmRyb2lkJywgJ3dlYicsICdhdG9taWMtd2ViJ10uaW5jbHVkZXMoYm9keS5jbGllbnRUeXBlKVxuICApIHtcbiAgICByZXR1cm4ge1xuICAgICAgdmFsaWQ6IGZhbHNlLFxuICAgICAgZXJyb3I6IHsgbWVzc2FnZTogJ0ludmFsaWQgY2xpZW50VHlwZS4nLCBldmVudDogYm9keSB9LFxuICAgIH07XG4gIH1cbiAgaWYgKHR5cGVvZiBib2R5LnVzZXJUaW1lem9uZSAhPT0gJ3N0cmluZycpXG4gICAgcmV0dXJuIHtcbiAgICAgIHZhbGlkOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7IG1lc3NhZ2U6ICd1c2VyVGltZXpvbmUgbXVzdCBiZSBhIHN0cmluZy4nLCBldmVudDogYm9keSB9LFxuICAgIH07XG4gIGlmICh0eXBlb2YgYm9keS5hdHRlbmRlZXMgIT09ICdzdHJpbmcnKVxuICAgIHJldHVybiB7XG4gICAgICB2YWxpZDogZmFsc2UsXG4gICAgICBlcnJvcjogeyBtZXNzYWdlOiAnYXR0ZW5kZWVzIG11c3QgYmUgYSBzdHJpbmcuJywgZXZlbnQ6IGJvZHkgfSxcbiAgICB9O1xuICBpZiAodHlwZW9mIGJvZHkuc3ViamVjdCAhPT0gJ3N0cmluZycpXG4gICAgcmV0dXJuIHtcbiAgICAgIHZhbGlkOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7IG1lc3NhZ2U6ICdzdWJqZWN0IG11c3QgYmUgYSBzdHJpbmcuJywgZXZlbnQ6IGJvZHkgfSxcbiAgICB9O1xuICBpZiAodHlwZW9mIGJvZHkucHJvbXB0ICE9PSAnc3RyaW5nJylcbiAgICByZXR1cm4ge1xuICAgICAgdmFsaWQ6IGZhbHNlLFxuICAgICAgZXJyb3I6IHsgbWVzc2FnZTogJ3Byb21wdCBtdXN0IGJlIGEgc3RyaW5nLicsIGV2ZW50OiBib2R5IH0sXG4gICAgfTtcbiAgaWYgKHR5cGVvZiBib2R5LmR1cmF0aW9uTWludXRlcyAhPT0gJ251bWJlcicpXG4gICAgcmV0dXJuIHtcbiAgICAgIHZhbGlkOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7IG1lc3NhZ2U6ICdkdXJhdGlvbk1pbnV0ZXMgbXVzdCBiZSBhIG51bWJlci4nLCBldmVudDogYm9keSB9LFxuICAgIH07XG4gIGlmICh0eXBlb2YgYm9keS5lbWFpbFRvICE9PSAnc3RyaW5nJylcbiAgICByZXR1cm4ge1xuICAgICAgdmFsaWQ6IGZhbHNlLFxuICAgICAgZXJyb3I6IHsgbWVzc2FnZTogJ2VtYWlsVG8gbXVzdCBiZSBhIHN0cmluZy4nLCBldmVudDogYm9keSB9LFxuICAgIH07XG4gIGlmICh0eXBlb2YgYm9keS5lbWFpbE5hbWUgIT09ICdzdHJpbmcnKVxuICAgIHJldHVybiB7XG4gICAgICB2YWxpZDogZmFsc2UsXG4gICAgICBlcnJvcjogeyBtZXNzYWdlOiAnZW1haWxOYW1lIG11c3QgYmUgYSBzdHJpbmcuJywgZXZlbnQ6IGJvZHkgfSxcbiAgICB9O1xuICBpZiAodHlwZW9mIGJvZHkueWVzTGluayAhPT0gJ3N0cmluZycpXG4gICAgcmV0dXJuIHtcbiAgICAgIHZhbGlkOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7IG1lc3NhZ2U6ICd5ZXNMaW5rIG11c3QgYmUgYSBzdHJpbmcuJywgZXZlbnQ6IGJvZHkgfSxcbiAgICB9O1xuICBpZiAodHlwZW9mIGJvZHkubm9MaW5rICE9PSAnc3RyaW5nJylcbiAgICByZXR1cm4ge1xuICAgICAgdmFsaWQ6IGZhbHNlLFxuICAgICAgZXJyb3I6IHsgbWVzc2FnZTogJ25vTGluayBtdXN0IGJlIGEgc3RyaW5nLicsIGV2ZW50OiBib2R5IH0sXG4gICAgfTtcbiAgaWYgKHR5cGVvZiBib2R5LnJlY2VpdmVyICE9PSAnc3RyaW5nJylcbiAgICByZXR1cm4ge1xuICAgICAgdmFsaWQ6IGZhbHNlLFxuICAgICAgZXJyb3I6IHsgbWVzc2FnZTogJ3JlY2VpdmVyIG11c3QgYmUgYSBzdHJpbmcuJywgZXZlbnQ6IGJvZHkgfSxcbiAgICB9O1xuICBpZiAodHlwZW9mIGJvZHkuc2VuZGVyICE9PSAnc3RyaW5nJylcbiAgICByZXR1cm4ge1xuICAgICAgdmFsaWQ6IGZhbHNlLFxuICAgICAgZXJyb3I6IHsgbWVzc2FnZTogJ3NlbmRlciBtdXN0IGJlIGEgc3RyaW5nLicsIGV2ZW50OiBib2R5IH0sXG4gICAgfTtcbiAgaWYgKFxuICAgIGJvZHkuc2hhcmVBdmFpbGFiaWxpdHkgIT09IHVuZGVmaW5lZCAmJlxuICAgIHR5cGVvZiBib2R5LnNoYXJlQXZhaWxhYmlsaXR5ICE9PSAnYm9vbGVhbidcbiAgKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIHZhbGlkOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIG1lc3NhZ2U6ICdzaGFyZUF2YWlsYWJpbGl0eSBtdXN0IGJlIGEgYm9vbGVhbiBpZiBwcm92aWRlZC4nLFxuICAgICAgICBldmVudDogYm9keSxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIHJldHVybiB7IHZhbGlkOiB0cnVlLCBkYXRhOiBib2R5IGFzIE1lZXRpbmdSZXF1ZXN0Qm9keVR5cGUgfTtcbn07XG4iXX0=