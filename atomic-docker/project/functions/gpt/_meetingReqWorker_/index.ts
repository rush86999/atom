import { S3Client, DeleteObjectCommand, GetObjectCommand } from '@aws-sdk/client-s3';
import { bucketName, kafkaGPTGroupId, kafkaMeetingReqTemplateTopic } from '../_libs/constants';
import { Kafka, logLevel } from 'kafkajs';
import { Readable } from 'node:stream';
import { meetingRequest as sendMeetingRequestEmail, streamToString } from '../_libs/api-helper';
import { MeetingRequestBodyType } from '../_libs/types';
import got from 'got';
import dayjs from 'dayjs';

// Assuming ScheduleMeetingRequestType is defined in a path accessible like this
// If it's in app_build_docker, this direct import won't work due to different project/module structures.
// For now, let's duplicate a minimal version here or assume it's made available.
interface ScheduleMeetingRequestType {
  participantNames: string[];
  durationMinutes: number;
  preferredDate: string; // YYYY-MM-DD
  preferredStartTimeFrom: string; // HH:MM:SS
  preferredStartTimeTo: string; // HH:MM:SS
}

const SCHEDULER_API_URL = process.env.SCHEDULER_API_URL || 'http://localhost:8080'; // Same as in app_build_docker

const s3Client = new S3Client({
    credentials: {
        accessKeyId: process.env.S3_ACCESS_KEY,
        secretAccessKey: process.env.S3_SECRET_KEY,
    },
    endpoint: process.env.S3_ENDPOINT,
    forcePathStyle: true,
})

const callSchedulerApi = async (payload: ScheduleMeetingRequestType): Promise<{ success: boolean; data?: any; error?: string }> => {
    try {
        const url = `${SCHEDULER_API_URL}/timeTable/user/scheduleMeeting`;
        console.log('[MeetingReqWorker] Calling Scheduler API URL:', url);
        console.log('[MeetingReqWorker] Scheduler API Payload:', JSON.stringify(payload, null, 2));

        const response: any = await got.post(url, {
            json: payload,
            headers: {
                'Content-Type': 'application/json',
                // TODO: Add Authorization header if required by the scheduler API
            },
            responseType: 'json', // Ensures `got` parses the response as JSON
            throwHttpErrors: false, // We want to handle HTTP errors manually
        });

        if (response.statusCode && response.statusCode >= 200 && response.statusCode < 300) {
            console.log('[MeetingReqWorker] Scheduler API success response:', response.body);
            return { success: true, data: response.body };
        } else {
            const errorBody = response.body || response.statusMessage || 'Unknown error from scheduler';
            console.error(`[MeetingReqWorker] Scheduler API error response (Status ${response.statusCode}):`, errorBody);
            return { success: false, error: `Scheduler API Error (Status ${response.statusCode}): ${JSON.stringify(errorBody)}` };
        }
    } catch (error: any) {
        console.error('[MeetingReqWorker] Failed to call Scheduler API:', error.message, error.stack);
        return { success: false, error: error.message || 'An unexpected error occurred while calling the scheduler API' };
    }
};


const kafka = new Kafka({
    logLevel: logLevel.DEBUG,
    brokers: (process.env.KAFKA_BROKERS || 'kafka1:29092').split(','), // Use env var
    clientId: 'atomic',
    // ssl: true,
    sasl: {
        mechanism: 'plain', // scram-sha-256 or scram-sha-512
        username: process.env.KAFKA_USERNAME,
        password: process.env.KAFKA_PASSWORD,
      },
})


const meetingRequestHandler = async () => {
    try {
        const consumer = kafka.consumer({ groupId: kafkaGPTGroupId })
        await consumer.connect()

        await consumer.subscribe({ topic: kafkaMeetingReqTemplateTopic })

        await consumer.run({
            eachMessage: async ({ topic, partition, message }) => {
                console.log({
                    key: message?.key?.toString(),
                    value: message?.value?.toString(),
                    headers: message?.headers,
                })
                // '{"fileKey":"fc5df674-b4ee-43c7-ad9e-298ae0eb6208/aed7b93e-8da4-447c-83e7-f0f0f1420226.json"}'
                const bodyData = JSON.parse(message?.value?.toString())
                const fileKey = bodyData.fileKey
                console.log(bodyData, ' bodyData')
                const s3GetCommand = new GetObjectCommand({
                  Bucket: bucketName,
                  Key: fileKey,
                })
          
                const s3GetCommandOutput = await s3Client.send(s3GetCommand)
                const bodyString = await streamToString(s3GetCommandOutput.Body as Readable)
          
                const body: MeetingRequestBodyType = JSON.parse(bodyString)
                console.log(body, ' body')
          
                const s3DeleteCommand = new DeleteObjectCommand({
                  Bucket: bucketName,
                  Key: fileKey,
                })
                const s3DeleteCommandOutput = await s3Client.send(s3DeleteCommand);
                console.log('[MeetingReqWorker] S3 delete command output:', s3DeleteCommandOutput);

                // Construct payload for the scheduler API
                // Ensure body.windowStartDate and body.windowEndDate are valid ISO strings or parseable date-time strings
                let preferredDate = '';
                let preferredStartTimeFrom = '';
                let preferredStartTimeTo = '';

                if (body.windowStartDate) {
                    const startDateObj = dayjs(body.windowStartDate);
                    if (startDateObj.isValid()) {
                        preferredDate = startDateObj.format('YYYY-MM-DD');
                        preferredStartTimeFrom = startDateObj.format('HH:mm:ss');
                    } else {
                        console.warn(`[MeetingReqWorker] Invalid windowStartDate format: ${body.windowStartDate}`);
                    }
                } else {
                    console.warn(`[MeetingReqWorker] windowStartDate is missing or undefined.`);
                }

                if (body.windowEndDate) {
                    const endDateObj = dayjs(body.windowEndDate);
                    if (endDateObj.isValid()) {
                        // If preferredDate is not set from windowStartDate, try to set it from windowEndDate
                        if (!preferredDate) {
                            preferredDate = endDateObj.format('YYYY-MM-DD');
                        }
                        preferredStartTimeTo = endDateObj.format('HH:mm:ss');
                    } else {
                        console.warn(`[MeetingReqWorker] Invalid windowEndDate format: ${body.windowEndDate}`);
                    }
                } else {
                    console.warn(`[MeetingReqWorker] windowEndDate is missing or undefined.`);
                }

                // Fallback if date components are still missing
                if (!preferredDate || !preferredStartTimeFrom || !preferredStartTimeTo) {
                    console.error('[MeetingReqWorker] Could not determine preferredDate, preferredStartTimeFrom, or preferredStartTimeTo from S3 payload. Skipping scheduler call.');
                    // Proceed with original email functionality without direct scheduling
                } else {
                    const scheduleMeetingPayload: ScheduleMeetingRequestType = {
                        participantNames: [body.sender, body.receiver].filter(name => !!name), // Basic parsing
                        durationMinutes: body.durationMinutes || body.slotDuration || 30, // Use durationMinutes, fallback to slotDuration
                        preferredDate: preferredDate,
                        preferredStartTimeFrom: preferredStartTimeFrom,
                        preferredStartTimeTo: preferredStartTimeTo,
                    };

                    console.log('[MeetingReqWorker] Attempting to call scheduler API with payload:', JSON.stringify(scheduleMeetingPayload, null, 2));
                    const schedulerResponse = await callSchedulerApi(scheduleMeetingPayload);

                    if (schedulerResponse.success) {
                        console.log('[MeetingReqWorker] Successfully called scheduler API. Response:', schedulerResponse.data);
                        // TODO: Potentially use this response to enrich the email content or next steps
                    } else {
                        console.error('[MeetingReqWorker] Failed to call scheduler API. Error:', schedulerResponse.error);
                        // TODO: Decide on error handling. Maybe email should indicate scheduling attempt failed.
                    }
                }

                // Original call to generate and send meeting request email
                // The `meetingRequest` from api-helper has been renamed to `sendMeetingRequestEmail` to avoid confusion
                // with the general concept of a meeting request.
                // Ensure the parameters passed are what `sendMeetingRequestEmail` expects.
                // The original `meetingRequest` in api-helper.ts expects:
                // (userId, clientType, userTimezone, userDateContext, attendees_string, subject, prompt, durationMinutes, ...)
                // We need to map the `body` (MeetingRequestBodyType from S3) to these arguments carefully.

                console.log('[MeetingReqWorker] Proceeding to generate and send meeting request email.');
                // Note: The original `meetingRequest` (now `sendMeetingRequestEmail`) has a different signature
                // than the parameters directly available on `MeetingRequestBodyType` from S3.
                // This might require careful mapping or ensuring the S3 payload (`body`) matches exactly
                // what `sendMeetingRequestEmail` expects.
                // For instance, `sendMeetingRequestEmail` expects `clientType`, `userDateContext`, `attendees` (string), `subject`, `prompt`.
                // These are on `MeetingRequestBodyType` as defined in `_libs/types.ts`.

                // Assuming the S3 'body' contains all necessary fields for sendMeetingRequestEmail.
                // body.email is likely emailTo for sendMeetingRequestEmail
                // body.slotDuration is durationMinutes for sendMeetingRequestEmail
                // body.windowStartDate could be userDateContext or part of availabilityUserDateStart
                // body.windowEndDate could be part of availabilityUserDateEnd

                return sendMeetingRequestEmail(
                    body.userId,
                    body.clientType || 'web', // Defaulting clientType if not present
                    body.userTimezone,
                    body.userDateContext || body.windowStartDate, // Use userDateContext or fallback
                    body.attendees, // This is the string version
                    body.subject,
                    body.prompt,
                    body.durationMinutes || body.slotDuration, // Use durationMinutes from body, fallback to slotDuration
                    body.shareAvailability,
                    body.availabilityUserDateStart || body.windowStartDate,
                    body.availabilityUserDateEnd || body.windowEndDate,
                    body.emailTo || body.email, // emailTo from body, fallback to body.email
                    body.emailName,
                    body.yesLink,
                    body.noLink
                  );
            },
        })
    } catch (e) {
        console.log(e, ' unable to create meeting request')
    }
}

export default meetingRequestHandler
