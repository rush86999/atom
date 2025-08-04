import { S3Client } from '@aws-sdk/client-s3';
import { Kafka } from 'kafkajs';
import { validateMeetingRequestBody, publishToS3AndKafka, } from '../_libs/common-on-event-handler';
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
    clientId: process.env.KAFKA_CLIENT_ID_MEETING_REQ_ADMIN ||
        'gpt-meeting-req-admin-producer',
    brokers: (process.env.KAFKA_BROKERS || 'localhost:9092').split(','),
    sasl: process.env.KAFKA_USERNAME && process.env.KAFKA_PASSWORD
        ? {
            mechanism: 'plain',
            username: process.env.KAFKA_USERNAME,
            password: process.env.KAFKA_PASSWORD,
        }
        : undefined,
});
export const handler = async (req, res) => {
    const validationResult = validateMeetingRequestBody(req.body);
    if (!validationResult.valid || !validationResult.data) {
        // Ensure data is present for type safety
        console.error('Payload validation failed for meeting-request-admin:', validationResult.error);
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
    const validatedPayload = validationResult.data; // Using 'as any' to bypass strict type check for now
    try {
        const publishResult = await publishToS3AndKafka(validatedPayload, kafkaMeetingReqTemplateTopic, s3Client, kafka);
        if (!publishResult.success) {
            console.error('Failed to publish meeting request to S3/Kafka (admin):', publishResult.error);
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
    }
    catch (e) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibWVldGluZy1yZXF1ZXN0LWFkbWluLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibWVldGluZy1yZXF1ZXN0LWFkbWluLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUNBLE9BQU8sRUFBRSxRQUFRLEVBQUUsTUFBTSxvQkFBb0IsQ0FBQztBQUM5QyxPQUFPLEVBQUUsS0FBSyxFQUFFLE1BQU0sU0FBUyxDQUFDO0FBQ2hDLE9BQU8sRUFDTCwwQkFBMEIsRUFDMUIsbUJBQW1CLEdBQ3BCLE1BQU0sa0NBQWtDLENBQUM7QUFFMUMsT0FBTyxFQUFFLDRCQUE0QixFQUFFLE1BQU0sb0JBQW9CLENBQUM7QUFFbEUsa0NBQWtDO0FBQ2xDLE1BQU0sUUFBUSxHQUFHLElBQUksUUFBUSxDQUFDO0lBQzVCLE1BQU0sRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLFVBQVUsSUFBSSxXQUFXO0lBQzdDLFdBQVcsRUFBRTtRQUNYLFdBQVcsRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLGFBQWEsSUFBSSxFQUFFO1FBQzVDLGVBQWUsRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLGFBQWEsSUFBSSxFQUFFO0tBQ2pEO0lBQ0QsUUFBUSxFQUFFLE9BQU8sQ0FBQyxHQUFHLENBQUMsV0FBVztJQUNqQyxjQUFjLEVBQUUsSUFBSTtDQUNyQixDQUFDLENBQUM7QUFFSCxNQUFNLEtBQUssR0FBRyxJQUFJLEtBQUssQ0FBQztJQUN0QixRQUFRLEVBQ04sT0FBTyxDQUFDLEdBQUcsQ0FBQyxpQ0FBaUM7UUFDN0MsZ0NBQWdDO0lBQ2xDLE9BQU8sRUFBRSxDQUFDLE9BQU8sQ0FBQyxHQUFHLENBQUMsYUFBYSxJQUFJLGdCQUFnQixDQUFDLENBQUMsS0FBSyxDQUFDLEdBQUcsQ0FBQztJQUNuRSxJQUFJLEVBQ0YsT0FBTyxDQUFDLEdBQUcsQ0FBQyxjQUFjLElBQUksT0FBTyxDQUFDLEdBQUcsQ0FBQyxjQUFjO1FBQ3RELENBQUMsQ0FBQztZQUNFLFNBQVMsRUFBRSxPQUFPO1lBQ2xCLFFBQVEsRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLGNBQWM7WUFDcEMsUUFBUSxFQUFFLE9BQU8sQ0FBQyxHQUFHLENBQUMsY0FBYztTQUNyQztRQUNILENBQUMsQ0FBQyxTQUFTO0NBQ2hCLENBQUMsQ0FBQztBQUVILE1BQU0sQ0FBQyxNQUFNLE9BQU8sR0FBRyxLQUFLLEVBQUUsR0FBWSxFQUFFLEdBQWEsRUFBRSxFQUFFO0lBQzNELE1BQU0sZ0JBQWdCLEdBQUcsMEJBQTBCLENBQUMsR0FBRyxDQUFDLElBQUksQ0FBQyxDQUFDO0lBQzlELElBQUksQ0FBQyxnQkFBZ0IsQ0FBQyxLQUFLLElBQUksQ0FBQyxnQkFBZ0IsQ0FBQyxJQUFJLEVBQUUsQ0FBQztRQUN0RCx5Q0FBeUM7UUFDekMsT0FBTyxDQUFDLEtBQUssQ0FDWCxzREFBc0QsRUFDdEQsZ0JBQWdCLENBQUMsS0FBSyxDQUN2QixDQUFDO1FBQ0YsT0FBTyxHQUFHO2FBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQzthQUNYLElBQUksQ0FBQztZQUNKLE9BQU8sRUFBRSxnQkFBZ0IsQ0FBQyxLQUFLLEVBQUUsT0FBTyxJQUFJLHlCQUF5QjtZQUNyRSxLQUFLLEVBQUUsZ0JBQWdCLENBQUMsS0FBSyxFQUFFLEtBQUs7U0FDckMsQ0FBQyxDQUFDO0lBQ1AsQ0FBQztJQUVELHVGQUF1RjtJQUN2Rix1R0FBdUc7SUFDdkcsK0ZBQStGO0lBQy9GLG1HQUFtRztJQUNuRyxpR0FBaUc7SUFDakcsNEdBQTRHO0lBQzVHLDhHQUE4RztJQUM5RyxNQUFNLGdCQUFnQixHQUFHLGdCQUFnQixDQUFDLElBQVcsQ0FBQyxDQUFDLHFEQUFxRDtJQUU1RyxJQUFJLENBQUM7UUFDSCxNQUFNLGFBQWEsR0FBRyxNQUFNLG1CQUFtQixDQUM3QyxnQkFBZ0IsRUFDaEIsNEJBQTRCLEVBQzVCLFFBQVEsRUFDUixLQUFLLENBQ04sQ0FBQztRQUVGLElBQUksQ0FBQyxhQUFhLENBQUMsT0FBTyxFQUFFLENBQUM7WUFDM0IsT0FBTyxDQUFDLEtBQUssQ0FDWCx3REFBd0QsRUFDeEQsYUFBYSxDQUFDLEtBQUssQ0FDcEIsQ0FBQztZQUNGLE9BQU8sR0FBRztpQkFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2lCQUNYLElBQUksQ0FBQztnQkFDSixPQUFPLEVBQUUsb0NBQW9DO2dCQUM3QyxPQUFPLEVBQUUsYUFBYSxDQUFDLEtBQUssRUFBRSxPQUFPO2FBQ3RDLENBQUMsQ0FBQztRQUNQLENBQUM7UUFFRCxPQUFPLEdBQUc7YUFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2FBQ1gsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLGlEQUFpRCxFQUFFLENBQUMsQ0FBQztJQUMxRSxDQUFDO0lBQUMsT0FBTyxDQUFNLEVBQUUsQ0FBQztRQUNoQixPQUFPLENBQUMsS0FBSyxDQUFDLG9EQUFvRCxFQUFFLENBQUMsQ0FBQyxDQUFDO1FBQ3ZFLE9BQU8sR0FBRzthQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7YUFDWCxJQUFJLENBQUM7WUFDSixPQUFPLEVBQUUsK0NBQStDO1lBQ3hELE9BQU8sRUFBRSxDQUFDLENBQUMsT0FBTztTQUNuQixDQUFDLENBQUM7SUFDUCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBRUYsZUFBZSxPQUFPLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBSZXF1ZXN0LCBSZXNwb25zZSB9IGZyb20gJ2V4cHJlc3MnO1xuaW1wb3J0IHsgUzNDbGllbnQgfSBmcm9tICdAYXdzLXNkay9jbGllbnQtczMnO1xuaW1wb3J0IHsgS2Fma2EgfSBmcm9tICdrYWZrYWpzJztcbmltcG9ydCB7XG4gIHZhbGlkYXRlTWVldGluZ1JlcXVlc3RCb2R5LFxuICBwdWJsaXNoVG9TM0FuZEthZmthLFxufSBmcm9tICcuLi9fbGlicy9jb21tb24tb24tZXZlbnQtaGFuZGxlcic7XG5pbXBvcnQgeyBNZWV0aW5nUmVxdWVzdEJvZHlUeXBlIH0gZnJvbSAnLi4vX2xpYnMvdHlwZXMnOyAvLyBFbnN1cmUgdGhpcyB0eXBlIGlzIGNvcnJlY3RseSBpbXBvcnRlZC9kZWZpbmVkXG5pbXBvcnQgeyBrYWZrYU1lZXRpbmdSZXFUZW1wbGF0ZVRvcGljIH0gZnJvbSAnLi4vX2xpYnMvY29uc3RhbnRzJztcblxuLy8gSW5pdGlhbGl6ZSBTMyBhbmQgS2Fma2EgY2xpZW50c1xuY29uc3QgczNDbGllbnQgPSBuZXcgUzNDbGllbnQoe1xuICByZWdpb246IHByb2Nlc3MuZW52LkFXU19SRUdJT04gfHwgJ3VzLWVhc3QtMScsXG4gIGNyZWRlbnRpYWxzOiB7XG4gICAgYWNjZXNzS2V5SWQ6IHByb2Nlc3MuZW52LlMzX0FDQ0VTU19LRVkgfHwgJycsXG4gICAgc2VjcmV0QWNjZXNzS2V5OiBwcm9jZXNzLmVudi5TM19TRUNSRVRfS0VZIHx8ICcnLFxuICB9LFxuICBlbmRwb2ludDogcHJvY2Vzcy5lbnYuUzNfRU5EUE9JTlQsXG4gIGZvcmNlUGF0aFN0eWxlOiB0cnVlLFxufSk7XG5cbmNvbnN0IGthZmthID0gbmV3IEthZmthKHtcbiAgY2xpZW50SWQ6XG4gICAgcHJvY2Vzcy5lbnYuS0FGS0FfQ0xJRU5UX0lEX01FRVRJTkdfUkVRX0FETUlOIHx8XG4gICAgJ2dwdC1tZWV0aW5nLXJlcS1hZG1pbi1wcm9kdWNlcicsXG4gIGJyb2tlcnM6IChwcm9jZXNzLmVudi5LQUZLQV9CUk9LRVJTIHx8ICdsb2NhbGhvc3Q6OTA5MicpLnNwbGl0KCcsJyksXG4gIHNhc2w6XG4gICAgcHJvY2Vzcy5lbnYuS0FGS0FfVVNFUk5BTUUgJiYgcHJvY2Vzcy5lbnYuS0FGS0FfUEFTU1dPUkRcbiAgICAgID8ge1xuICAgICAgICAgIG1lY2hhbmlzbTogJ3BsYWluJyxcbiAgICAgICAgICB1c2VybmFtZTogcHJvY2Vzcy5lbnYuS0FGS0FfVVNFUk5BTUUsXG4gICAgICAgICAgcGFzc3dvcmQ6IHByb2Nlc3MuZW52LktBRktBX1BBU1NXT1JELFxuICAgICAgICB9XG4gICAgICA6IHVuZGVmaW5lZCxcbn0pO1xuXG5leHBvcnQgY29uc3QgaGFuZGxlciA9IGFzeW5jIChyZXE6IFJlcXVlc3QsIHJlczogUmVzcG9uc2UpID0+IHtcbiAgY29uc3QgdmFsaWRhdGlvblJlc3VsdCA9IHZhbGlkYXRlTWVldGluZ1JlcXVlc3RCb2R5KHJlcS5ib2R5KTtcbiAgaWYgKCF2YWxpZGF0aW9uUmVzdWx0LnZhbGlkIHx8ICF2YWxpZGF0aW9uUmVzdWx0LmRhdGEpIHtcbiAgICAvLyBFbnN1cmUgZGF0YSBpcyBwcmVzZW50IGZvciB0eXBlIHNhZmV0eVxuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAnUGF5bG9hZCB2YWxpZGF0aW9uIGZhaWxlZCBmb3IgbWVldGluZy1yZXF1ZXN0LWFkbWluOicsXG4gICAgICB2YWxpZGF0aW9uUmVzdWx0LmVycm9yXG4gICAgKTtcbiAgICByZXR1cm4gcmVzXG4gICAgICAuc3RhdHVzKDQwMClcbiAgICAgIC5qc29uKHtcbiAgICAgICAgbWVzc2FnZTogdmFsaWRhdGlvblJlc3VsdC5lcnJvcj8ubWVzc2FnZSB8fCAnSW52YWxpZCByZXF1ZXN0IHBheWxvYWQnLFxuICAgICAgICBldmVudDogdmFsaWRhdGlvblJlc3VsdC5lcnJvcj8uZXZlbnQsXG4gICAgICB9KTtcbiAgfVxuXG4gIC8vIENhc3QgdG8gTWVldGluZ1JlcXVlc3RCb2R5VHlwZSBiZWNhdXNlIGNvbW1vbi1vbi1ldmVudC1oYW5kbGVyJ3MgcHVibGlzaFRvUzNBbmRLYWZrYVxuICAvLyBjdXJyZW50bHkgZXhwZWN0cyBDcmVhdGVEYXlTY2hlZHVsZUJvZHlUeXBlLiBUaGlzIHdpbGwgbmVlZCB0byBiZSBnZW5lcmFsaXplZCBvciBwdWJsaXNoVG9TM0FuZEthZmthXG4gIC8vIHdpbGwgbmVlZCB0byBiZSBkdXBsaWNhdGVkL21hZGUgZ2VuZXJpYyBpZiBwYXlsb2FkcyBhcmUgdmVyeSBkaWZmZXJlbnQgYW5kIGNhbm5vdCBiZSBtYXBwZWQuXG4gIC8vIEZvciBub3csIGFzc3VtaW5nIHRoZSBzdHJ1Y3R1cmUgcGFzc2VkIHRvIFMzL0thZmthIGlzIGFjY2VwdGFibGUgYXMgJ2FueScgb3IgYSBjb21tb24gYmFzZSB0eXBlLlxuICAvLyBPciwgbW9yZSBjb3JyZWN0bHksIHB1Ymxpc2hUb1MzQW5kS2Fma2Egc2hvdWxkIGFjY2VwdCBhIG1vcmUgZ2VuZXJpYyBwYXlsb2FkIHR5cGUgaWYgcG9zc2libGUsXG4gIC8vIG9yIGEgc3BlY2lmaWMgb25lIGlmIGl0cyBpbnRlcm5hbCBTMy9LYWZrYSBtZXNzYWdlIHN0cnVjdHVyZSByZWxpZXMgb24gc3BlY2lmaWMgZmllbGRzIG5vdCBjb21tb24gdG8gYWxsLlxuICAvLyBGb3IgdGhpcyBzdGVwLCB3ZSdsbCBhc3N1bWUgTWVldGluZ1JlcXVlc3RCb2R5VHlwZSBjYW4gYmUgaGFuZGxlZCBieSBwdWJsaXNoVG9TM0FuZEthZmthJ3Mgc3RyaW5naWZpY2F0aW9uLlxuICBjb25zdCB2YWxpZGF0ZWRQYXlsb2FkID0gdmFsaWRhdGlvblJlc3VsdC5kYXRhIGFzIGFueTsgLy8gVXNpbmcgJ2FzIGFueScgdG8gYnlwYXNzIHN0cmljdCB0eXBlIGNoZWNrIGZvciBub3dcblxuICB0cnkge1xuICAgIGNvbnN0IHB1Ymxpc2hSZXN1bHQgPSBhd2FpdCBwdWJsaXNoVG9TM0FuZEthZmthKFxuICAgICAgdmFsaWRhdGVkUGF5bG9hZCxcbiAgICAgIGthZmthTWVldGluZ1JlcVRlbXBsYXRlVG9waWMsXG4gICAgICBzM0NsaWVudCxcbiAgICAgIGthZmthXG4gICAgKTtcblxuICAgIGlmICghcHVibGlzaFJlc3VsdC5zdWNjZXNzKSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAnRmFpbGVkIHRvIHB1Ymxpc2ggbWVldGluZyByZXF1ZXN0IHRvIFMzL0thZmthIChhZG1pbik6JyxcbiAgICAgICAgcHVibGlzaFJlc3VsdC5lcnJvclxuICAgICAgKTtcbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAgIC5qc29uKHtcbiAgICAgICAgICBtZXNzYWdlOiAnRmFpbGVkIHRvIHByb2Nlc3MgbWVldGluZyByZXF1ZXN0LicsXG4gICAgICAgICAgZGV0YWlsczogcHVibGlzaFJlc3VsdC5lcnJvcj8ubWVzc2FnZSxcbiAgICAgICAgfSk7XG4gICAgfVxuXG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cygyMDIpXG4gICAgICAuanNvbih7IG1lc3NhZ2U6ICdTdWNjZXNzZnVsbHkgcXVldWVkIG1lZXRpbmcgcmVxdWVzdCBwcm9jZXNzaW5nLicgfSk7XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoJ1VuZXhwZWN0ZWQgZXJyb3IgaW4gbWVldGluZy1yZXF1ZXN0LWFkbWluIGhhbmRsZXI6JywgZSk7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAuanNvbih7XG4gICAgICAgIG1lc3NhZ2U6ICdBbiB1bmV4cGVjdGVkIGludGVybmFsIHNlcnZlciBlcnJvciBvY2N1cnJlZC4nLFxuICAgICAgICBkZXRhaWxzOiBlLm1lc3NhZ2UsXG4gICAgICB9KTtcbiAgfVxufTtcblxuZXhwb3J0IGRlZmF1bHQgaGFuZGxlcjtcbiJdfQ==