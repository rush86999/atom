import { S3Client, DeleteObjectCommand, GetObjectCommand, } from '@aws-sdk/client-s3';
import { bucketName, kafkaGPTGroupId, kafkaMeetingReqTemplateTopic, } from '../_libs/constants';
import { Kafka, logLevel } from 'kafkajs';
import { meetingRequest as sendMeetingRequestEmail, streamToString, } from '../_libs/api-helper';
import got from 'got';
import dayjs from 'dayjs';
const SCHEDULER_API_URL = process.env.SCHEDULER_API_URL || 'http://localhost:8080'; // Same as in app_build_docker
const s3Client = new S3Client({
    credentials: {
        accessKeyId: process.env.S3_ACCESS_KEY,
        secretAccessKey: process.env.S3_SECRET_KEY,
    },
    endpoint: process.env.S3_ENDPOINT,
    forcePathStyle: true,
});
const callSchedulerApi = async (payload) => {
    try {
        const url = `${SCHEDULER_API_URL}/timeTable/user/scheduleMeeting`;
        console.log('[MeetingReqWorker] Calling Scheduler API URL:', url);
        console.log('[MeetingReqWorker] Scheduler API Payload:', JSON.stringify(payload, null, 2));
        const response = await got.post(url, {
            json: payload,
            headers: {
                'Content-Type': 'application/json',
                // TODO: Add Authorization header if required by the scheduler API
            },
            responseType: 'json', // Ensures `got` parses the response as JSON
            throwHttpErrors: false, // We want to handle HTTP errors manually
        });
        if (response.statusCode &&
            response.statusCode >= 200 &&
            response.statusCode < 300) {
            console.log('[MeetingReqWorker] Scheduler API success response:', response.body);
            return { success: true, data: response.body };
        }
        else {
            const errorBody = response.body ||
                response.statusMessage ||
                'Unknown error from scheduler';
            console.error(`[MeetingReqWorker] Scheduler API error response (Status ${response.statusCode}):`, errorBody);
            return {
                success: false,
                error: `Scheduler API Error (Status ${response.statusCode}): ${JSON.stringify(errorBody)}`,
            };
        }
    }
    catch (error) {
        console.error('[MeetingReqWorker] Failed to call Scheduler API:', error.message, error.stack);
        return {
            success: false,
            error: error.message ||
                'An unexpected error occurred while calling the scheduler API',
        };
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
});
const meetingRequestHandler = async () => {
    try {
        const consumer = kafka.consumer({ groupId: kafkaGPTGroupId });
        await consumer.connect();
        await consumer.subscribe({ topic: kafkaMeetingReqTemplateTopic });
        await consumer.run({
            eachMessage: async ({ topic, partition, message }) => {
                console.log({
                    key: message?.key?.toString(),
                    value: message?.value?.toString(),
                    headers: message?.headers,
                });
                // '{"fileKey":"fc5df674-b4ee-43c7-ad9e-298ae0eb6208/aed7b93e-8da4-447c-83e7-f0f0f1420226.json"}'
                const bodyData = JSON.parse(message?.value?.toString());
                const fileKey = bodyData.fileKey;
                console.log(bodyData, ' bodyData');
                const s3GetCommand = new GetObjectCommand({
                    Bucket: bucketName,
                    Key: fileKey,
                });
                const s3GetCommandOutput = await s3Client.send(s3GetCommand);
                const bodyString = await streamToString(s3GetCommandOutput.Body);
                const body = JSON.parse(bodyString);
                console.log(body, ' body');
                const s3DeleteCommand = new DeleteObjectCommand({
                    Bucket: bucketName,
                    Key: fileKey,
                });
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
                    }
                    else {
                        console.warn(`[MeetingReqWorker] Invalid windowStartDate format: ${body.windowStartDate}`);
                    }
                }
                else {
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
                    }
                    else {
                        console.warn(`[MeetingReqWorker] Invalid windowEndDate format: ${body.windowEndDate}`);
                    }
                }
                else {
                    console.warn(`[MeetingReqWorker] windowEndDate is missing or undefined.`);
                }
                // Fallback if date components are still missing
                if (!preferredDate ||
                    !preferredStartTimeFrom ||
                    !preferredStartTimeTo) {
                    console.error('[MeetingReqWorker] Could not determine preferredDate, preferredStartTimeFrom, or preferredStartTimeTo from S3 payload. Skipping scheduler call.');
                    // Proceed with original email functionality without direct scheduling
                }
                else {
                    const scheduleMeetingPayload = {
                        participantNames: [body.sender, body.receiver].filter((name) => !!name), // Basic parsing
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
                    }
                    else {
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
                return sendMeetingRequestEmail(body.userId, body.clientType || 'web', // Defaulting clientType if not present
                body.userTimezone, body.userDateContext || body.windowStartDate, // Use userDateContext or fallback
                body.attendees, // This is the string version
                body.subject, body.prompt, body.durationMinutes || body.slotDuration, // Use durationMinutes from body, fallback to slotDuration
                body.shareAvailability, body.availabilityUserDateStart || body.windowStartDate, body.availabilityUserDateEnd || body.windowEndDate, body.emailTo || body.email, // emailTo from body, fallback to body.email
                body.emailName, body.yesLink, body.noLink);
            },
        });
    }
    catch (e) {
        console.log(e, ' unable to create meeting request');
    }
};
export default meetingRequestHandler;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5kZXguanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpbmRleC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEVBQ0wsUUFBUSxFQUNSLG1CQUFtQixFQUNuQixnQkFBZ0IsR0FDakIsTUFBTSxvQkFBb0IsQ0FBQztBQUM1QixPQUFPLEVBQ0wsVUFBVSxFQUNWLGVBQWUsRUFDZiw0QkFBNEIsR0FDN0IsTUFBTSxvQkFBb0IsQ0FBQztBQUM1QixPQUFPLEVBQUUsS0FBSyxFQUFFLFFBQVEsRUFBRSxNQUFNLFNBQVMsQ0FBQztBQUUxQyxPQUFPLEVBQ0wsY0FBYyxJQUFJLHVCQUF1QixFQUN6QyxjQUFjLEdBQ2YsTUFBTSxxQkFBcUIsQ0FBQztBQUU3QixPQUFPLEdBQUcsTUFBTSxLQUFLLENBQUM7QUFDdEIsT0FBTyxLQUFLLE1BQU0sT0FBTyxDQUFDO0FBYTFCLE1BQU0saUJBQWlCLEdBQ3JCLE9BQU8sQ0FBQyxHQUFHLENBQUMsaUJBQWlCLElBQUksdUJBQXVCLENBQUMsQ0FBQyw4QkFBOEI7QUFFMUYsTUFBTSxRQUFRLEdBQUcsSUFBSSxRQUFRLENBQUM7SUFDNUIsV0FBVyxFQUFFO1FBQ1gsV0FBVyxFQUFFLE9BQU8sQ0FBQyxHQUFHLENBQUMsYUFBYTtRQUN0QyxlQUFlLEVBQUUsT0FBTyxDQUFDLEdBQUcsQ0FBQyxhQUFhO0tBQzNDO0lBQ0QsUUFBUSxFQUFFLE9BQU8sQ0FBQyxHQUFHLENBQUMsV0FBVztJQUNqQyxjQUFjLEVBQUUsSUFBSTtDQUNyQixDQUFDLENBQUM7QUFFSCxNQUFNLGdCQUFnQixHQUFHLEtBQUssRUFDNUIsT0FBbUMsRUFDd0IsRUFBRTtJQUM3RCxJQUFJLENBQUM7UUFDSCxNQUFNLEdBQUcsR0FBRyxHQUFHLGlCQUFpQixpQ0FBaUMsQ0FBQztRQUNsRSxPQUFPLENBQUMsR0FBRyxDQUFDLCtDQUErQyxFQUFFLEdBQUcsQ0FBQyxDQUFDO1FBQ2xFLE9BQU8sQ0FBQyxHQUFHLENBQ1QsMkNBQTJDLEVB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LENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsbUNBQW1DLENBQUMsQ0FBQztJQUN0RCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBRUYsZUFBZSxxQkFBcUIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7XG4gIFMzQ2xpZW50LFxuICBEZWxldGVPYmplY3RDb21tYW5kLFxuICBHZXRPYmplY3RDb21tYW5kLFxufSBmcm9tICdAYXdzLXNkay9jbGllbnQtczMnO1xuaW1wb3J0IHtcbiAgYnVja2V0TmFtZSxcbiAga2Fma2FHUFRHcm91cElkLFxuICBrYWZrYU1lZXRpbmdSZXFUZW1wbGF0ZVRvcGljLFxufSBmcm9tICcuLi9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IHsgS2Fma2EsIGxvZ0xldmVsIH0gZnJvbSAna2Fma2Fqcyc7XG5pbXBvcnQgeyBSZWFkYWJsZSB9IGZyb20gJ25vZGU6c3RyZWFtJztcbmltcG9ydCB7XG4gIG1lZXRpbmdSZXF1ZXN0IGFzIHNlbmRNZWV0aW5nUmVxdWVzdEVtYWlsLFxuICBzdHJlYW1Ub1N0cmluZyxcbn0gZnJvbSAnLi4vX2xpYnMvYXBpLWhlbHBlcic7XG5pbXBvcnQgeyBNZWV0aW5nUmVxdWVzdEJvZHlUeXBlIH0gZnJvbSAnLi4vX2xpYnMvdHlwZXMnO1xuaW1wb3J0IGdvdCBmcm9tICdnb3QnO1xuaW1wb3J0IGRheWpzIGZyb20gJ2RheWpzJztcblxuLy8gQXNzdW1pbmcgU2NoZWR1bGVNZWV0aW5nUmVxdWVzdFR5cGUgaXMgZGVmaW5lZCBpbiBhIHBhdGggYWNjZXNzaWJsZSBsaWtlIHRoaXNcbi8vIElmIGl0J3MgaW4gYXBwX2J1aWxkX2RvY2tlciwgdGhpcyBkaXJlY3QgaW1wb3J0IHdvbid0IHdvcmsgZHVlIHRvIGRpZmZlcmVudCBwcm9qZWN0L21vZHVsZSBzdHJ1Y3R1cmVzLlxuLy8gRm9yIG5vdywgbGV0J3MgZHVwbGljYXRlIGEgbWluaW1hbCB2ZXJzaW9uIGhlcmUgb3IgYXNzdW1lIGl0J3MgbWFkZSBhdmFpbGFibGUuXG5pbnRlcmZhY2UgU2NoZWR1bGVNZWV0aW5nUmVxdWVzdFR5cGUge1xuICBwYXJ0aWNpcGFudE5hbWVzOiBzdHJpbmdbXTtcbiAgZHVyYXRpb25NaW51dGVzOiBudW1iZXI7XG4gIHByZWZlcnJlZERhdGU6IHN0cmluZzsgLy8gWVlZWS1NTS1ERFxuICBwcmVmZXJyZWRTdGFydFRpbWVGcm9tOiBzdHJpbmc7IC8vIEhIOk1NOlNTXG4gIHByZWZlcnJlZFN0YXJ0VGltZVRvOiBzdHJpbmc7IC8vIEhIOk1NOlNTXG59XG5cbmNvbnN0IFNDSEVEVUxFUl9BUElfVVJMID1cbiAgcHJvY2Vzcy5lbnYuU0NIRURVTEVSX0FQSV9VUkwgfHwgJ2h0dHA6Ly9sb2NhbGhvc3Q6ODA4MCc7IC8vIFNhbWUgYXMgaW4gYXBwX2J1aWxkX2RvY2tlclxuXG5jb25zdCBzM0NsaWVudCA9IG5ldyBTM0NsaWVudCh7XG4gIGNyZWRlbnRpYWxzOiB7XG4gICAgYWNjZXNzS2V5SWQ6IHByb2Nlc3MuZW52LlMzX0FDQ0VTU19LRVksXG4gICAgc2VjcmV0QWNjZXNzS2V5OiBwcm9jZXNzLmVudi5TM19TRUNSRVRfS0VZLFxuICB9LFxuICBlbmRwb2ludDogcHJvY2Vzcy5lbnYuUzNfRU5EUE9JTlQsXG4gIGZvcmNlUGF0aFN0eWxlOiB0cnVlLFxufSk7XG5cbmNvbnN0IGNhbGxTY2hlZHVsZXJBcGkgPSBhc3luYyAoXG4gIHBheWxvYWQ6IFNjaGVkdWxlTWVldGluZ1JlcXVlc3RUeXBlXG4pOiBQcm9taXNlPHsgc3VjY2VzczogYm9vbGVhbjsgZGF0YT86IGFueTsgZXJyb3I/OiBzdHJpbmcgfT4gPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHVybCA9IGAke1NDSEVEVUxFUl9BUElfVVJMfS90aW1lVGFibGUvdXNlci9zY2hlZHVsZU1lZXRpbmdgO1xuICAgIGNvbnNvbGUubG9nKCdbTWVldGluZ1JlcVdvcmtlcl0gQ2FsbGluZyBTY2hlZHVsZXIgQVBJIFVSTDonLCB1cmwpO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgJ1tNZWV0aW5nUmVxV29ya2VyXSBTY2hlZHVsZXIgQVBJIFBheWxvYWQ6JyxcbiAgICAgIEpTT04uc3RyaW5naWZ5KHBheWxvYWQsIG51bGwsIDIpXG4gICAgKTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiBhbnkgPSBhd2FpdCBnb3QucG9zdCh1cmwsIHtcbiAgICAgIGpzb246IHBheWxvYWQsXG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIC8vIFRPRE86IEFkZCBBdXRob3JpemF0aW9uIGhlYWRlciBpZiByZXF1aXJlZCBieSB0aGUgc2NoZWR1bGVyIEFQSVxuICAgICAgfSxcbiAgICAgIHJlc3BvbnNlVHlwZTogJ2pzb24nLCAvLyBFbnN1cmVzIGBnb3RgIHBhcnNlcyB0aGUgcmVzcG9uc2UgYXMgSlNPTlxuICAgICAgdGhyb3dIdHRwRXJyb3JzOiBmYWxzZSwgLy8gV2Ugd2FudCB0byBoYW5kbGUgSFRUUCBlcnJvcnMgbWFudWFsbHlcbiAgICB9KTtcblxuICAgIGlmIChcbiAgICAgIHJlc3BvbnNlLnN0YXR1c0NvZGUgJiZcbiAgICAgIHJlc3BvbnNlLnN0YXR1c0NvZGUgPj0gMjAwICYmXG4gICAgICByZXNwb25zZS5zdGF0dXNDb2RlIDwgMzAwXG4gICAgKSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgJ1tNZWV0aW5nUmVxV29ya2VyXSBTY2hlZHVsZXIgQVBJIHN1Y2Nlc3MgcmVzcG9uc2U6JyxcbiAgICAgICAgcmVzcG9uc2UuYm9keVxuICAgICAgKTtcbiAgICAgIHJldHVybiB7IHN1Y2Nlc3M6IHRydWUsIGRhdGE6IHJlc3BvbnNlLmJvZHkgfTtcbiAgICB9IGVsc2Uge1xuICAgICAgY29uc3QgZXJyb3JCb2R5ID1cbiAgICAgICAgcmVzcG9uc2UuYm9keSB8fFxuICAgICAgICByZXNwb25zZS5zdGF0dXNNZXNzYWdlIHx8XG4gICAgICAgICdVbmtub3duIGVycm9yIGZyb20gc2NoZWR1bGVyJztcbiAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgIGBbTWVldGluZ1JlcVdvcmtlcl0gU2NoZWR1bGVyIEFQSSBlcnJvciByZXNwb25zZSAoU3RhdHVzICR7cmVzcG9uc2Uuc3RhdHVzQ29kZX0pOmAsXG4gICAgICAgIGVycm9yQm9keVxuICAgICAgKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgICBlcnJvcjogYFNjaGVkdWxlciBBUEkgRXJyb3IgKFN0YXR1cyAke3Jlc3BvbnNlLnN0YXR1c0NvZGV9KTogJHtKU09OLnN0cmluZ2lmeShlcnJvckJvZHkpfWAsXG4gICAgICB9O1xuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAnW01lZXRpbmdSZXFXb3JrZXJdIEZhaWxlZCB0byBjYWxsIFNjaGVkdWxlciBBUEk6JyxcbiAgICAgIGVycm9yLm1lc3NhZ2UsXG4gICAgICBlcnJvci5zdGFja1xuICAgICk7XG4gICAgcmV0dXJuIHtcbiAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgZXJyb3I6XG4gICAgICAgIGVycm9yLm1lc3NhZ2UgfHxcbiAgICAgICAgJ0FuIHVuZXhwZWN0ZWQgZXJyb3Igb2NjdXJyZWQgd2hpbGUgY2FsbGluZyB0aGUgc2NoZWR1bGVyIEFQSScsXG4gICAgfTtcbiAgfVxufTtcblxuY29uc3Qga2Fma2EgPSBuZXcgS2Fma2Eoe1xuICBsb2dMZXZlbDogbG9nTGV2ZWwuREVCVUcsXG4gIGJyb2tlcnM6IChwcm9jZXNzLmVudi5LQUZLQV9CUk9LRVJTIHx8ICdrYWZrYTE6MjkwOTInKS5zcGxpdCgnLCcpLCAvLyBVc2UgZW52IHZhclxuICBjbGllbnRJZDogJ2F0b21pYycsXG4gIC8vIHNzbDogdHJ1ZSxcbiAgc2FzbDoge1xuICAgIG1lY2hhbmlzbTogJ3BsYWluJywgLy8gc2NyYW0tc2hhLTI1NiBvciBzY3JhbS1zaGEtNTEyXG4gICAgdXNlcm5hbWU6IHByb2Nlc3MuZW52LktBRktBX1VTRVJOQU1FLFxuICAgIHBhc3N3b3JkOiBwcm9jZXNzLmVudi5LQUZLQV9QQVNTV09SRCxcbiAgfSxcbn0pO1xuXG5jb25zdCBtZWV0aW5nUmVxdWVzdEhhbmRsZXIgPSBhc3luYyAoKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgY29uc3VtZXIgPSBrYWZrYS5jb25zdW1lcih7IGdyb3VwSWQ6IGthZmthR1BUR3JvdXBJZCB9KTtcbiAgICBhd2FpdCBjb25zdW1lci5jb25uZWN0KCk7XG5cbiAgICBhd2FpdCBjb25zdW1lci5zdWJzY3JpYmUoeyB0b3BpYzoga2Fma2FNZWV0aW5nUmVxVGVtcGxhdGVUb3BpYyB9KTtcblxuICAgIGF3YWl0IGNvbnN1bWVyLnJ1bih7XG4gICAgICBlYWNoTWVzc2FnZTogYXN5bmMgKHsgdG9waWMsIHBhcnRpdGlvbiwgbWVzc2FnZSB9KSA9PiB7XG4gICAgICAgIGNvbnNvbGUubG9nKHtcbiAgICAgICAgICBrZXk6IG1lc3NhZ2U/LmtleT8udG9TdHJpbmcoKSxcbiAgICAgICAgICB2YWx1ZTogbWVzc2FnZT8udmFsdWU/LnRvU3RyaW5nKCksXG4gICAgICAgICAgaGVhZGVyczogbWVzc2FnZT8uaGVhZGVycyxcbiAgICAgICAgfSk7XG4gICAgICAgIC8vICd7XCJmaWxlS2V5XCI6XCJmYzVkZjY3NC1iNGVlLTQzYzctYWQ5ZS0yOThhZTBlYjYyMDgvYWVkN2I5M2UtOGRhNC00NDdjLTgzZTctZjBmMGYxNDIwMjI2Lmpzb25cIn0nXG4gICAgICAgIGNvbnN0IGJvZHlEYXRhID0gSlNPTi5wYXJzZShtZXNzYWdlPy52YWx1ZT8udG9TdHJpbmcoKSk7XG4gICAgICAgIGNvbnN0IGZpbGVLZXkgPSBib2R5RGF0YS5maWxlS2V5O1xuICAgICAgICBjb25zb2xlLmxvZyhib2R5RGF0YSwgJyBib2R5RGF0YScpO1xuICAgICAgICBjb25zdCBzM0dldENvbW1hbmQgPSBuZXcgR2V0T2JqZWN0Q29tbWFuZCh7XG4gICAgICAgICAgQnVja2V0OiBidWNrZXROYW1lLFxuICAgICAgICAgIEtleTogZmlsZUtleSxcbiAgICAgICAgfSk7XG5cbiAgICAgICAgY29uc3QgczNHZXRDb21tYW5kT3V0cHV0ID0gYXdhaXQgczNDbGllbnQuc2VuZChzM0dldENvbW1hbmQpO1xuICAgICAgICBjb25zdCBib2R5U3RyaW5nID0gYXdhaXQgc3RyZWFtVG9TdHJpbmcoXG4gICAgICAgICAgczNHZXRDb21tYW5kT3V0cHV0LkJvZHkgYXMgUmVhZGFibGVcbiAgICAgICAgKTtcblxuICAgICAgICBjb25zdCBib2R5OiBNZWV0aW5nUmVxdWVzdEJvZHlUeXBlID0gSlNPTi5wYXJzZShib2R5U3RyaW5nKTtcbiAgICAgICAgY29uc29sZS5sb2coYm9keSwgJyBib2R5Jyk7XG5cbiAgICAgICAgY29uc3QgczNEZWxldGVDb21tYW5kID0gbmV3IERlbGV0ZU9iamVjdENvbW1hbmQoe1xuICAgICAgICAgIEJ1Y2tldDogYnVja2V0TmFtZSxcbiAgICAgICAgICBLZXk6IGZpbGVLZXksXG4gICAgICAgIH0pO1xuICAgICAgICBjb25zdCBzM0RlbGV0ZUNvbW1hbmRPdXRwdXQgPSBhd2FpdCBzM0NsaWVudC5zZW5kKHMzRGVsZXRlQ29tbWFuZCk7XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgICdbTWVldGluZ1JlcVdvcmtlcl0gUzMgZGVsZXRlIGNvbW1hbmQgb3V0cHV0OicsXG4gICAgICAgICAgczNEZWxldGVDb21tYW5kT3V0cHV0XG4gICAgICAgICk7XG5cbiAgICAgICAgLy8gQ29uc3RydWN0IHBheWxvYWQgZm9yIHRoZSBzY2hlZHVsZXIgQVBJXG4gICAgICAgIC8vIEVuc3VyZSBib2R5LndpbmRvd1N0YXJ0RGF0ZSBhbmQgYm9keS53aW5kb3dFbmREYXRlIGFyZSB2YWxpZCBJU08gc3RyaW5ncyBvciBwYXJzZWFibGUgZGF0ZS10aW1lIHN0cmluZ3NcbiAgICAgICAgbGV0IHByZWZlcnJlZERhdGUgPSAnJztcbiAgICAgICAgbGV0IHByZWZlcnJlZFN0YXJ0VGltZUZyb20gPSAnJztcbiAgICAgICAgbGV0IHByZWZlcnJlZFN0YXJ0VGltZVRvID0gJyc7XG5cbiAgICAgICAgaWYgKGJvZHkud2luZG93U3RhcnREYXRlKSB7XG4gICAgICAgICAgY29uc3Qgc3RhcnREYXRlT2JqID0gZGF5anMoYm9keS53aW5kb3dTdGFydERhdGUpO1xuICAgICAgICAgIGlmIChzdGFydERhdGVPYmouaXNWYWxpZCgpKSB7XG4gICAgICAgICAgICBwcmVmZXJyZWREYXRlID0gc3RhcnREYXRlT2JqLmZvcm1hdCgnWVlZWS1NTS1ERCcpO1xuICAgICAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lRnJvbSA9IHN0YXJ0RGF0ZU9iai5mb3JtYXQoJ0hIOm1tOnNzJyk7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgICAgICAgYFtNZWV0aW5nUmVxV29ya2VyXSBJbnZhbGlkIHdpbmRvd1N0YXJ0RGF0ZSBmb3JtYXQ6ICR7Ym9keS53aW5kb3dTdGFydERhdGV9YFxuICAgICAgICAgICAgKTtcbiAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgICAgYFtNZWV0aW5nUmVxV29ya2VyXSB3aW5kb3dTdGFydERhdGUgaXMgbWlzc2luZyBvciB1bmRlZmluZWQuYFxuICAgICAgICAgICk7XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoYm9keS53aW5kb3dFbmREYXRlKSB7XG4gICAgICAgICAgY29uc3QgZW5kRGF0ZU9iaiA9IGRheWpzKGJvZHkud2luZG93RW5kRGF0ZSk7XG4gICAgICAgICAgaWYgKGVuZERhdGVPYmouaXNWYWxpZCgpKSB7XG4gICAgICAgICAgICAvLyBJZiBwcmVmZXJyZWREYXRlIGlzIG5vdCBzZXQgZnJvbSB3aW5kb3dTdGFydERhdGUsIHRyeSB0byBzZXQgaXQgZnJvbSB3aW5kb3dFbmREYXRlXG4gICAgICAgICAgICBpZiAoIXByZWZlcnJlZERhdGUpIHtcbiAgICAgICAgICAgICAgcHJlZmVycmVkRGF0ZSA9IGVuZERhdGVPYmouZm9ybWF0KCdZWVlZLU1NLUREJyk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBwcmVmZXJyZWRTdGFydFRpbWVUbyA9IGVuZERhdGVPYmouZm9ybWF0KCdISDptbTpzcycpO1xuICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgICAgIGBbTWVldGluZ1JlcVdvcmtlcl0gSW52YWxpZCB3aW5kb3dFbmREYXRlIGZvcm1hdDogJHtib2R5LndpbmRvd0VuZERhdGV9YFxuICAgICAgICAgICAgKTtcbiAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgICAgYFtNZWV0aW5nUmVxV29ya2VyXSB3aW5kb3dFbmREYXRlIGlzIG1pc3Npbmcgb3IgdW5kZWZpbmVkLmBcbiAgICAgICAgICApO1xuICAgICAgICB9XG5cbiAgICAgICAgLy8gRmFsbGJhY2sgaWYgZGF0ZSBjb21wb25lbnRzIGFyZSBzdGlsbCBtaXNzaW5nXG4gICAgICAgIGlmIChcbiAgICAgICAgICAhcHJlZmVycmVkRGF0ZSB8fFxuICAgICAgICAgICFwcmVmZXJyZWRTdGFydFRpbWVGcm9tIHx8XG4gICAgICAgICAgIXByZWZlcnJlZFN0YXJ0VGltZVRvXG4gICAgICAgICkge1xuICAgICAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICAgICAnW01lZXRpbmdSZXFXb3JrZXJdIENvdWxkIG5vdCBkZXRlcm1pbmUgcHJlZmVycmVkRGF0ZSwgcHJlZmVycmVkU3RhcnRUaW1lRnJvbSwgb3IgcHJlZmVycmVkU3RhcnRUaW1lVG8gZnJvbSBTMyBwYXlsb2FkLiBTa2lwcGluZyBzY2hlZHVsZXIgY2FsbC4nXG4gICAgICAgICAgKTtcbiAgICAgICAgICAvLyBQcm9jZWVkIHdpdGggb3JpZ2luYWwgZW1haWwgZnVuY3Rpb25hbGl0eSB3aXRob3V0IGRpcmVjdCBzY2hlZHVsaW5nXG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgY29uc3Qgc2NoZWR1bGVNZWV0aW5nUGF5bG9hZDogU2NoZWR1bGVNZWV0aW5nUmVxdWVzdFR5cGUgPSB7XG4gICAgICAgICAgICBwYXJ0aWNpcGFudE5hbWVzOiBbYm9keS5zZW5kZXIsIGJvZHkucmVjZWl2ZXJdLmZpbHRlcihcbiAgICAgICAgICAgICAgKG5hbWUpID0+ICEhbmFtZVxuICAgICAgICAgICAgKSwgLy8gQmFzaWMgcGFyc2luZ1xuICAgICAgICAgICAgZHVyYXRpb25NaW51dGVzOiBib2R5LmR1cmF0aW9uTWludXRlcyB8fCBib2R5LnNsb3REdXJhdGlvbiB8fCAzMCwgLy8gVXNlIGR1cmF0aW9uTWludXRlcywgZmFsbGJhY2sgdG8gc2xvdER1cmF0aW9uXG4gICAgICAgICAgICBwcmVmZXJyZWREYXRlOiBwcmVmZXJyZWREYXRlLFxuICAgICAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lRnJvbTogcHJlZmVycmVkU3RhcnRUaW1lRnJvbSxcbiAgICAgICAgICAgIHByZWZlcnJlZFN0YXJ0VGltZVRvOiBwcmVmZXJyZWRTdGFydFRpbWVUbyxcbiAgICAgICAgICB9O1xuXG4gICAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgICAnW01lZXRpbmdSZXFXb3JrZXJdIEF0dGVtcHRpbmcgdG8gY2FsbCBzY2hlZHVsZXIgQVBJIHdpdGggcGF5bG9hZDonLFxuICAgICAgICAgICAgSlNPTi5zdHJpbmdpZnkoc2NoZWR1bGVNZWV0aW5nUGF5bG9hZCwgbnVsbCwgMilcbiAgICAgICAgICApO1xuICAgICAgICAgIGNvbnN0IHNjaGVkdWxlclJlc3BvbnNlID0gYXdhaXQgY2FsbFNjaGVkdWxlckFwaShcbiAgICAgICAgICAgIHNjaGVkdWxlTWVldGluZ1BheWxvYWRcbiAgICAgICAgICApO1xuXG4gICAgICAgICAgaWYgKHNjaGVkdWxlclJlc3BvbnNlLnN1Y2Nlc3MpIHtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgICAgICAnW01lZXRpbmdSZXFXb3JrZXJdIFN1Y2Nlc3NmdWxseSBjYWxsZWQgc2NoZWR1bGVyIEFQSS4gUmVzcG9uc2U6JyxcbiAgICAgICAgICAgICAgc2NoZWR1bGVyUmVzcG9uc2UuZGF0YVxuICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIC8vIFRPRE86IFBvdGVudGlhbGx5IHVzZSB0aGlzIHJlc3BvbnNlIHRvIGVucmljaCB0aGUgZW1haWwgY29udGVudCBvciBuZXh0IHN0ZXBzXG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICAgICAgICdbTWVldGluZ1JlcVdvcmtlcl0gRmFpbGVkIHRvIGNhbGwgc2NoZWR1bGVyIEFQSS4gRXJyb3I6JyxcbiAgICAgICAgICAgICAgc2NoZWR1bGVyUmVzcG9uc2UuZXJyb3JcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICAvLyBUT0RPOiBEZWNpZGUgb24gZXJyb3IgaGFuZGxpbmcuIE1heWJlIGVtYWlsIHNob3VsZCBpbmRpY2F0ZSBzY2hlZHVsaW5nIGF0dGVtcHQgZmFpbGVkLlxuICAgICAgICAgIH1cbiAgICAgICAgfVxuXG4gICAgICAgIC8vIE9yaWdpbmFsIGNhbGwgdG8gZ2VuZXJhdGUgYW5kIHNlbmQgbWVldGluZyByZXF1ZXN0IGVtYWlsXG4gICAgICAgIC8vIFRoZSBgbWVldGluZ1JlcXVlc3RgIGZyb20gYXBpLWhlbHBlciBoYXMgYmVlbiByZW5hbWVkIHRvIGBzZW5kTWVldGluZ1JlcXVlc3RFbWFpbGAgdG8gYXZvaWQgY29uZnVzaW9uXG4gICAgICAgIC8vIHdpdGggdGhlIGdlbmVyYWwgY29uY2VwdCBvZiBhIG1lZXRpbmcgcmVxdWVzdC5cbiAgICAgICAgLy8gRW5zdXJlIHRoZSBwYXJhbWV0ZXJzIHBhc3NlZCBhcmUgd2hhdCBgc2VuZE1lZXRpbmdSZXF1ZXN0RW1haWxgIGV4cGVjdHMuXG4gICAgICAgIC8vIFRoZSBvcmlnaW5hbCBgbWVldGluZ1JlcXVlc3RgIGluIGFwaS1oZWxwZXIudHMgZXhwZWN0czpcbiAgICAgICAgLy8gKHVzZXJJZCwgY2xpZW50VHlwZSwgdXNlclRpbWV6b25lLCB1c2VyRGF0ZUNvbnRleHQsIGF0dGVuZGVlc19zdHJpbmcsIHN1YmplY3QsIHByb21wdCwgZHVyYXRpb25NaW51dGVzLCAuLi4pXG4gICAgICAgIC8vIFdlIG5lZWQgdG8gbWFwIHRoZSBgYm9keWAgKE1lZXRpbmdSZXF1ZXN0Qm9keVR5cGUgZnJvbSBTMykgdG8gdGhlc2UgYXJndW1lbnRzIGNhcmVmdWxseS5cblxuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICAnW01lZXRpbmdSZXFXb3JrZXJdIFByb2NlZWRpbmcgdG8gZ2VuZXJhdGUgYW5kIHNlbmQgbWVldGluZyByZXF1ZXN0IGVtYWlsLidcbiAgICAgICAgKTtcbiAgICAgICAgLy8gTm90ZTogVGhlIG9yaWdpbmFsIGBtZWV0aW5nUmVxdWVzdGAgKG5vdyBgc2VuZE1lZXRpbmdSZXF1ZXN0RW1haWxgKSBoYXMgYSBkaWZmZXJlbnQgc2lnbmF0dXJlXG4gICAgICAgIC8vIHRoYW4gdGhlIHBhcmFtZXRlcnMgZGlyZWN0bHkgYXZhaWxhYmxlIG9uIGBNZWV0aW5nUmVxdWVzdEJvZHlUeXBlYCBmcm9tIFMzLlxuICAgICAgICAvLyBUaGlzIG1pZ2h0IHJlcXVpcmUgY2FyZWZ1bCBtYXBwaW5nIG9yIGVuc3VyaW5nIHRoZSBTMyBwYXlsb2FkIChgYm9keWApIG1hdGNoZXMgZXhhY3RseVxuICAgICAgICAvLyB3aGF0IGBzZW5kTWVldGluZ1JlcXVlc3RFbWFpbGAgZXhwZWN0cy5cbiAgICAgICAgLy8gRm9yIGluc3RhbmNlLCBgc2VuZE1lZXRpbmdSZXF1ZXN0RW1haWxgIGV4cGVjdHMgYGNsaWVudFR5cGVgLCBgdXNlckRhdGVDb250ZXh0YCwgYGF0dGVuZGVlc2AgKHN0cmluZyksIGBzdWJqZWN0YCwgYHByb21wdGAuXG4gICAgICAgIC8vIFRoZXNlIGFyZSBvbiBgTWVldGluZ1JlcXVlc3RCb2R5VHlwZWAgYXMgZGVmaW5lZCBpbiBgX2xpYnMvdHlwZXMudHNgLlxuXG4gICAgICAgIC8vIEFzc3VtaW5nIHRoZSBTMyAnYm9keScgY29udGFpbnMgYWxsIG5lY2Vzc2FyeSBmaWVsZHMgZm9yIHNlbmRNZWV0aW5nUmVxdWVzdEVtYWlsLlxuICAgICAgICAvLyBib2R5LmVtYWlsIGlzIGxpa2VseSBlbWFpbFRvIGZvciBzZW5kTWVldGluZ1JlcXVlc3RFbWFpbFxuICAgICAgICAvLyBib2R5LnNsb3REdXJhdGlvbiBpcyBkdXJhdGlvbk1pbnV0ZXMgZm9yIHNlbmRNZWV0aW5nUmVxdWVzdEVtYWlsXG4gICAgICAgIC8vIGJvZHkud2luZG93U3RhcnREYXRlIGNvdWxkIGJlIHVzZXJEYXRlQ29udGV4dCBvciBwYXJ0IG9mIGF2YWlsYWJpbGl0eVVzZXJEYXRlU3RhcnRcbiAgICAgICAgLy8gYm9keS53aW5kb3dFbmREYXRlIGNvdWxkIGJlIHBhcnQgb2YgYXZhaWxhYmlsaXR5VXNlckRhdGVFbmRcblxuICAgICAgICByZXR1cm4gc2VuZE1lZXRpbmdSZXF1ZXN0RW1haWwoXG4gICAgICAgICAgYm9keS51c2VySWQsXG4gICAgICAgICAgYm9keS5jbGllbnRUeXBlIHx8ICd3ZWInLCAvLyBEZWZhdWx0aW5nIGNsaWVudFR5cGUgaWYgbm90IHByZXNlbnRcbiAgICAgICAgICBib2R5LnVzZXJUaW1lem9uZSxcbiAgICAgICAgICBib2R5LnVzZXJEYXRlQ29udGV4dCB8fCBib2R5LndpbmRvd1N0YXJ0RGF0ZSwgLy8gVXNlIHVzZXJEYXRlQ29udGV4dCBvciBmYWxsYmFja1xuICAgICAgICAgIGJvZHkuYXR0ZW5kZWVzLCAvLyBUaGlzIGlzIHRoZSBzdHJpbmcgdmVyc2lvblxuICAgICAgICAgIGJvZHkuc3ViamVjdCxcbiAgICAgICAgICBib2R5LnByb21wdCxcbiAgICAgICAgICBib2R5LmR1cmF0aW9uTWludXRlcyB8fCBib2R5LnNsb3REdXJhdGlvbiwgLy8gVXNlIGR1cmF0aW9uTWludXRlcyBmcm9tIGJvZHksIGZhbGxiYWNrIHRvIHNsb3REdXJhdGlvblxuICAgICAgICAgIGJvZHkuc2hhcmVBdmFpbGFiaWxpdHksXG4gICAgICAgICAgYm9keS5hdmFpbGFiaWxpdHlVc2VyRGF0ZVN0YXJ0IHx8IGJvZHkud2luZG93U3RhcnREYXRlLFxuICAgICAgICAgIGJvZHkuYXZhaWxhYmlsaXR5VXNlckRhdGVFbmQgfHwgYm9keS53aW5kb3dFbmREYXRlLFxuICAgICAgICAgIGJvZHkuZW1haWxUbyB8fCBib2R5LmVtYWlsLCAvLyBlbWFpbFRvIGZyb20gYm9keSwgZmFsbGJhY2sgdG8gYm9keS5lbWFpbFxuICAgICAgICAgIGJvZHkuZW1haWxOYW1lLFxuICAgICAgICAgIGJvZHkueWVzTGluayxcbiAgICAgICAgICBib2R5Lm5vTGlua1xuICAgICAgICApO1xuICAgICAgfSxcbiAgICB9KTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGNyZWF0ZSBtZWV0aW5nIHJlcXVlc3QnKTtcbiAgfVxufTtcblxuZXhwb3J0IGRlZmF1bHQgbWVldGluZ1JlcXVlc3RIYW5kbGVyO1xuIl19