// Unit tests for common-on-event-handler.ts
import { validateDaySchedulePayload, publishToS3AndKafka, // Assuming this type is exported for test data
disconnectKafkaProducer, // For cleaning up Kafka producer if necessary
 } from './common-on-event-handler';
// Mocks for AWS SDK S3 Client and Kafkajs
// These will be more detailed within the describe block for publishToS3AndKafka
const mockS3Send = jest.fn();
jest.mock('@aws-sdk/client-s3', () => {
    return {
        S3Client: jest.fn(() => ({
            send: mockS3Send,
        })),
        PutObjectCommand: jest.fn((args) => ({
            /* mock command object if needed, or just check args */ input: args,
        })),
    };
});
const mockKafkaTransactionSend = jest.fn();
const mockKafkaTransactionCommit = jest.fn();
const mockKafkaTransactionAbort = jest.fn();
const mockKafkaProducerConnect = jest.fn();
const mockKafkaProducerDisconnect = jest.fn();
const mockKafkaProducerTransaction = jest.fn(() => ({
    send: mockKafkaTransactionSend,
    commit: mockKafkaTransactionCommit,
    abort: mockKafkaTransactionAbort,
}));
jest.mock('kafkajs', () => {
    // Save the original module
    const originalModule = jest.requireActual('kafkajs');
    return {
        ...originalModule, // Export all actual non-mocked parts
        Kafka: jest.fn(() => ({
            producer: jest.fn(() => ({
                connect: mockKafkaProducerConnect,
                disconnect: mockKafkaProducerDisconnect,
                transaction: mockKafkaProducerTransaction,
                // Mock other producer methods if directly used by publishToS3AndKafka outside transaction
            })),
            // Mock admin client if it were used directly in publishToS3AndKafka
            // admin: jest.fn(() => ({ ... }))
        })),
        // Export CompressionTypes if it's used by the code under test
        CompressionTypes: originalModule.CompressionTypes,
    };
});
describe('common-on-event-handler', () => {
    describe('validateDaySchedulePayload', () => {
        const baseValidPayload = {
            userId: 'user123',
            startDate: '2024-01-01',
            endDate: '2024-01-01',
            timezone: 'America/New_York',
            tasks: [{ summary: 'Task 1' }],
        };
        it('should return valid:true for a valid payload', () => {
            const result = validateDaySchedulePayload(baseValidPayload);
            expect(result.valid).toBe(true);
            expect(result.data).toEqual(baseValidPayload);
            expect(result.error).toBeUndefined();
        });
        it('should return valid:false if body is missing', () => {
            const result = validateDaySchedulePayload(null);
            expect(result.valid).toBe(false);
            expect(result.error?.message).toBe('Request body is missing.');
        });
        const requiredFields = [
            'userId',
            'startDate',
            'endDate',
            'timezone',
            'tasks',
        ];
        requiredFields.forEach((field) => {
            it(`should return valid:false if ${field} is missing`, () => {
                const payload = { ...baseValidPayload };
                delete payload[field];
                const result = validateDaySchedulePayload(payload);
                expect(result.valid).toBe(false);
                expect(result.error?.message).toBe(`${field} is required.`);
            });
        });
        it('should return valid:false if tasks is not an array or empty', () => {
            let payload = { ...baseValidPayload, tasks: 'not-an-array' };
            let result = validateDaySchedulePayload(payload);
            expect(result.valid).toBe(false);
            expect(result.error?.message).toBe('tasks array is required and must not be empty.');
            payload = { ...baseValidPayload, tasks: [] };
            result = validateDaySchedulePayload(payload);
            expect(result.valid).toBe(false);
            expect(result.error?.message).toBe('tasks array is required and must not be empty.');
        });
        it('should return valid:false if a task is missing a summary', () => {
            const payload = {
                ...baseValidPayload,
                tasks: [{ description: 'No summary' }],
            };
            const result = validateDaySchedulePayload(payload);
            expect(result.valid).toBe(false);
            expect(result.error?.message).toBe('Each task must have a summary.');
        });
    });
    describe('publishToS3AndKafka', () => {
        const mockPayload = {
            userId: 'userS3Kafka',
            startDate: '2024-01-01',
            endDate: '2024-01-01',
            timezone: 'UTC',
            tasks: [{ summary: 'Test S3 Kafka' }],
        };
        const mockKafkaTopic = 'test-topic';
        // S3Client and Kafka instances will be created internally by default by the function
        // or can be passed in (our function is designed to accept them).
        // For these tests, we'll rely on the internal creation which uses the mocked S3Client and Kafka from jest.mock.
        beforeEach(() => {
            mockS3Send.mockClear();
            mockKafkaProducerConnect.mockClear();
            mockKafkaProducerTransaction.mockClear();
            mockKafkaTransactionSend.mockClear();
            mockKafkaTransactionCommit.mockClear();
            mockKafkaTransactionAbort.mockClear();
            // Set necessary ENV vars for internal client initialization
            process.env.S3_BUCKET_NAME = 'test-bucket';
            process.env.AWS_REGION = 'us-west-1'; // Or any region
        });
        afterAll(async () => {
            // Clean up Kafka producer if it was initialized and connected
            await disconnectKafkaProducer();
        });
        // Test Case 1: Successful S3 upload and Kafka publish.
        it('should return success:true on successful S3 and Kafka operations', async () => {
            mockS3Send.mockResolvedValue({ $metadata: { httpStatusCode: 200 } });
            mockKafkaProducerConnect.mockResolvedValue(undefined);
            mockKafkaTransactionSend.mockResolvedValue([
                { topicName: mockKafkaTopic, partition: 0, errorCode: 0 },
            ]);
            mockKafkaTransactionCommit.mockResolvedValue(undefined);
            const result = await publishToS3AndKafka(mockPayload, mockKafkaTopic);
            expect(result.success).toBe(true);
            expect(mockS3Send).toHaveBeenCalledTimes(1);
            expect(mockKafkaProducerConnect).toHaveBeenCalledTimes(1); // Assuming producer is new for the call or first call
            expect(mockKafkaProducerTransaction).toHaveBeenCalledTimes(1);
            expect(mockKafkaTransactionSend).toHaveBeenCalledTimes(1);
            expect(mockKafkaTransactionCommit).toHaveBeenCalledTimes(1);
            expect(mockKafkaTransactionAbort).not.toHaveBeenCalled();
        });
        // Test Case 2: S3 upload fails.
        it('should return success:false and abort Kafka transaction if S3 upload fails', async () => {
            const s3Error = new Error('S3 Access Denied');
            mockS3Send.mockRejectedValue(s3Error);
            mockKafkaProducerConnect.mockResolvedValue(undefined); // Kafka connect still happens before S3 attempt
            mockKafkaTransactionAbort.mockResolvedValue(undefined);
            const result = await publishToS3AndKafka(mockPayload, mockKafkaTopic);
            expect(result.success).toBe(false);
            expect(result.error?.message).toBe('Failed to publish to S3 or Kafka.');
            expect(result.error?.details).toBe(s3Error.message);
            expect(mockS3Send).toHaveBeenCalledTimes(1);
            expect(mockKafkaProducerTransaction).toHaveBeenCalledTimes(1); // Transaction starts
            expect(mockKafkaTransactionSend).not.toHaveBeenCalled(); // But does not send
            expect(mockKafkaTransactionCommit).not.toHaveBeenCalled();
            expect(mockKafkaTransactionAbort).toHaveBeenCalledTimes(1); // Abort is called
        });
        // Test Case 3: Kafka transaction.send fails.
        it('should return success:false and abort Kafka transaction if Kafka send fails', async () => {
            mockS3Send.mockResolvedValue({ $metadata: { httpStatusCode: 200 } }); // S3 succeeds
            const kafkaError = new Error('Kafka unavailable');
            mockKafkaProducerConnect.mockResolvedValue(undefined);
            mockKafkaTransactionSend.mockRejectedValue(kafkaError);
            mockKafkaTransactionAbort.mockResolvedValue(undefined);
            const result = await publishToS3AndKafka(mockPayload, mockKafkaTopic);
            expect(result.success).toBe(false);
            expect(result.error?.message).toBe('Failed to publish to S3 or Kafka.');
            expect(result.error?.details).toBe(kafkaError.message);
            expect(mockS3Send).toHaveBeenCalledTimes(1);
            expect(mockKafkaProducerTransaction).toHaveBeenCalledTimes(1);
            expect(mockKafkaTransactionSend).toHaveBeenCalledTimes(1);
            expect(mockKafkaTransactionCommit).not.toHaveBeenCalled();
            expect(mockKafkaTransactionAbort).toHaveBeenCalledTimes(1);
        });
    });
});
describe('validateMeetingRequestBody', () => {
    const baseValidMeetingRequestPayload = {
        userId: 'userMeeting123',
        clientType: 'web',
        userTimezone: 'America/New_York',
        userDateContext: 'next Tuesday',
        attendees: 'john.doe@example.com,jane.doe@example.com',
        subject: 'Project Alpha Sync',
        prompt: 'Discuss Q4 roadmap and resource allocation.',
        durationMinutes: 45,
        shareAvailability: false, // Default, specific tests for true later
        emailTo: 'teamlead@example.com',
        emailName: 'Team Lead',
        yesLink: 'http://example.com/confirm/yes',
        noLink: 'http://example.com/confirm/no',
        receiver: 'teamlead@example.com', // Or some ID
        sender: 'userMeeting123', // Or user's email
    };
    it('should return valid:true for a valid meeting request payload', () => {
        const result = validateMeetingRequestBody(baseValidMeetingRequestPayload);
        expect(result.valid).toBe(true);
        expect(result.data).toEqual(baseValidMeetingRequestPayload);
        expect(result.error).toBeUndefined();
    });
    it('should return valid:false if body is missing for meeting request', () => {
        const result = validateMeetingRequestBody(null);
        expect(result.valid).toBe(false);
        expect(result.error?.message).toBe('Request body is missing.');
    });
    const requiredMeetingFields = [
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
    ];
    requiredMeetingFields.forEach((field) => {
        it(`should return valid:false if meeting request field '${field}' is missing`, () => {
            const payload = { ...baseValidMeetingRequestPayload };
            delete payload[field]; // Remove the field
            const result = validateMeetingRequestBody(payload);
            expect(result.valid).toBe(false);
            expect(result.error?.message).toBe(`${String(field)} is required.`);
        });
        it(`should return valid:false if meeting request field '${field}' is an empty string`, () => {
            const payload = { ...baseValidMeetingRequestPayload, [field]: '' };
            const result = validateMeetingRequestBody(payload);
            expect(result.valid).toBe(false);
            expect(result.error?.message).toBe(`${String(field)} is required.`);
        });
    });
    it('should return valid:false for invalid clientType', () => {
        const payload = {
            ...baseValidMeetingRequestPayload,
            clientType: 'invalidClient',
        };
        const result = validateMeetingRequestBody(payload);
        expect(result.valid).toBe(false);
        expect(result.error?.message).toBe('Invalid clientType.');
    });
    it('should return valid:false for invalid durationMinutes type', () => {
        const payload = {
            ...baseValidMeetingRequestPayload,
            durationMinutes: 'not-a-number',
        };
        const result = validateMeetingRequestBody(payload);
        expect(result.valid).toBe(false);
        expect(result.error?.message).toBe('durationMinutes must be a number.');
    });
    it('should return valid:false if shareAvailability is present but not a boolean', () => {
        const payload = {
            ...baseValidMeetingRequestPayload,
            shareAvailability: 'not-a-boolean',
        };
        const result = validateMeetingRequestBody(payload);
        expect(result.valid).toBe(false);
        expect(result.error?.message).toBe('shareAvailability must be a boolean if provided.');
    });
    it('should return valid:true if shareAvailability is undefined (defaults to false effectively)', () => {
        const payload = { ...baseValidMeetingRequestPayload };
        delete payload.shareAvailability; // Not strictly required by validator if it can be optional
        // The current validator doesn't list it as required, so this should pass
        // if the boolean check is only if it's present.
        const result = validateMeetingRequestBody(payload);
        // The validator makes shareAvailability optional in its check, so it's valid if missing
        // However, the orchestrator `meetingRequest` has specific logic for it.
        // The validator itself doesn't require `shareAvailability`.
        expect(result.valid).toBe(true);
    });
    it('should return valid:true if optional availability dates are missing when shareAvailability is false', () => {
        const payload = {
            ...baseValidMeetingRequestPayload,
            shareAvailability: false,
        };
        delete payload.availabilityUserDateStart;
        delete payload.availabilityUserDateEnd;
        const result = validateMeetingRequestBody(payload);
        expect(result.valid).toBe(true); // These fields are only logically required if shareAvailability is true
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY29tbW9uLW9uLWV2ZW50LWhhbmRsZXIudGVzdC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImNvbW1vbi1vbi1ldmVudC1oYW5kbGVyLnRlc3QudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsNENBQTRDO0FBQzVDLE9BQU8sRUFDTCwwQkFBMEIsRUFDMUIsbUJBQW1CLEVBQ1EsK0NBQStDO0FBQzFFLHVCQUF1QixFQUFFLDhDQUE4QztFQUN4RSxNQUFNLDJCQUEyQixDQUFDO0FBRW5DLDBDQUEwQztBQUMxQyxnRkFBZ0Y7QUFDaEYsTUFBTSxVQUFVLEdBQUcsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDO0FBQzdCLElBQUksQ0FBQyxJQUFJLENBQUMsb0JBQW9CLEVBQUUsR0FBRyxFQUFFO0lBQ25DLE9BQU87UUFDTCxRQUFRLEVBQUUsSUFBSSxDQUFDLEVBQUUsQ0FBQyxHQUFHLEVBQUUsQ0FBQyxDQUFDO1lBQ3ZCLElBQUksRUFBRSxVQUFVO1NBQ2pCLENBQUMsQ0FBQztRQUNILGdCQUFnQixFQUFFLElBQUksQ0FBQyxFQUFFLENBQUMsQ0FBQyxJQUFJLEVBQUUsRUFBRSxDQUFDLENBQUM7WUFDbkMsdURBQXVELENBQUMsS0FBSyxFQUFFLElBQUk7U0FDcEUsQ0FBQyxDQUFDO0tBQ0osQ0FBQztBQUNKLENBQUMsQ0FBQyxDQUFDO0FBRUgsTUFBTSx3QkFBd0IsR0FBRyxJQUFJLENBQUMsRUFBRSxFQUFFLENBQUM7QUFDM0MsTUFBTSwwQkFBMEIsR0FBRyxJQUFJLENBQUMsRUFBRSxFQUFFLENBQUM7QUFDN0MsTUFBTSx5QkFBeUIsR0FBRyxJQUFJLENBQUMsRUFBRSxFQUFFLENBQUM7QUFDNUMsTUFBTSx3QkFBd0IsR0FBRyxJQUFJLENBQUMsRUFBRSxFQUFFLENBQUM7QUFDM0MsTUFBTSwyQkFBMkIsR0FBRyxJQUFJLENBQUMsRUFBRSxFQUFFLENBQUM7QUFDOUMsTUFBTSw0QkFBNEIsR0FBRyxJQUFJLENBQUMsRUFBRSxDQUFDLEdBQUcsRUFBRSxDQUFDLENBQUM7SUFDbEQsSUFBSSxFQUFFLHdCQUF3QjtJQUM5QixNQUFNLEVBQUUsMEJBQTBCO0lBQ2xDLEtBQUssRUFBRSx5QkFBeUI7Q0FDakMsQ0FBQyxDQUFDLENBQUM7QUFFSixJQUFJLENBQUMsSUFBSSxDQUFDLFNBQVMsRUFBRSxHQUFHLEVBQUU7SUFDeEIsMkJBQTJCO0lBQzNCLE1BQU0sY0FBYyxHQUFHLElBQUksQ0FBQyxhQUFhLENBQUMsU0FBUyxDQUFDLENBQUM7SUFDckQsT0FBTztRQUNMLEdBQUcsY0FBYyxFQUFFLHFDQUFxQztRQUN4RCxLQUFLLEVBQUUsSUFBSSxDQUFDLEVBQUUsQ0FBQyxHQUFHLEVBQUUsQ0FBQyxDQUFDO1lBQ3BCLFFBQVEsRUFBRSxJQUFJLENBQUMsRUFBRSxDQUFDLEdBQUcsRUFBRSxDQUFDLENBQUM7Z0JBQ3ZCLE9BQU8sRUFBRSx3QkFBd0I7Z0JBQ2pDLFVBQVUsRUFBRSwyQkFBMkI7Z0JBQ3ZDLFdBQVcsRUFBRSw0QkFBNEI7Z0JBQ3pDLDBGQUEwRjthQUMzRixDQUFDLENBQUM7WUFDSCxvRUFBb0U7WUFDcEUsa0NBQWtDO1NBQ25DLENBQUMsQ0FBQztRQUNILDhEQUE4RDtRQUM5RCxnQkFBZ0IsRUFBRSxjQUFjLENBQUMsZ0JBQWdCO0tBQ2xELENBQUM7QUFDSixDQUFDLENBQUMsQ0FBQztBQUVILFFBQVEsQ0FBQyx5QkFBeUIsRUFBRSxHQUFHLEVBQUU7SUFDdkMsUUFBUSxDQUFDLDRCQUE0QixFQUFFLEdBQUcsRUFBRTtRQUMxQyxNQUFNLGdCQUFnQixHQUE4QjtZQUNsRCxNQUFNLEVBQUUsU0FBUztZQUNqQixTQUFTLEVBQUUsWUFBWTtZQUN2QixPQUFPLEVBQUUsWUFBWTtZQUNyQixRQUFRLEVBQUUsa0JBQWtCO1lBQzVCLEtBQUssRUFBRSxDQUFDLEVBQUUsT0FBTyxFQUFFLFFBQVEsRUFBRSxDQUFDO1NBQy9CLENBQUM7UUFFRixFQUFFLENBQUMsOENBQThDLEVBQUUsR0FBRyxFQUFFO1lBQ3RELE1BQU0sTUFBTSxHQUFHLDBCQUEwQixDQUFDLGdCQUFnQixDQUFDLENBQUM7WUFDNUQsTUFBTSxDQUFDLE1BQU0sQ0FBQyxLQUFLLENBQUMsQ0FBQyxJQUFJLENBQUMsSUFBSSxDQUFDLENBQUM7WUFDaEMsTUFBTSxDQUFDLE1BQU0sQ0FBQyxJQUFJLENBQUMsQ0FBQyxPQUFPLENBQUMsZ0JBQWdCLENBQUMsQ0FBQztZQUM5QyxNQUFNLENBQUMsTUFBTSxDQUFDLEtBQUssQ0FBQyxDQUFDLGFBQWEsRUFBRSxDQUFDO1FBQ3ZDLENBQUMsQ0FBQyxDQUFDO1FBRUgsRUFBRSxDQUFDLDhDQUE4QyxFQUFFLEdBQUcsRUFBRTtZQUN0RCxNQUFNLE1BQU0sR0FBRywwQkFBMEIsQ0FBQyxJQUFJLENBQUMsQ0FBQztZQUNoRCxNQUFNLENBQUMsTUFBTSxDQUFDLEtBQUssQ0FBQyxDQUFDLElBQUksQ0FBQyxLQUFLLENBQUMsQ0FBQztZQUNqQyxNQUFNLENBQUMsTUFBTSxDQUFDLEtBQUssRUFBRSxPQUFPLENBQUMsQ0FBQyxJQUFJLENBQUMsMEJBQTBCLENBQUMsQ0FBQztRQUNqRSxDQUFDLENBQUMsQ0FBQztRQUVILE1BQU0sY0FBYyxHQUEyQztZQUM3RCxRQUFRO1lBQ1IsV0FBVztZQUNYLFNBQVM7WUFDVCxVQUFVO1lBQ1YsT0FBTztTQUNSLENBQUM7UUFDRixjQUFjLENBQUMsT0FBTyxDQUFDLENBQUMsS0FBSyxFQUFFLEVBQUU7WUFDL0IsRUFBRSxDQUFDLGdDQUFnQyxLQUFLLGFBQWEsRUFBRSxHQUFHLEVBQUU7Z0JBQzFELE1BQU0sT0FBTyxHQUFHLEVBQUUsR0FBRyxnQkFBZ0IsRUFBRSxDQUFDO2dCQUN4QyxPQUFPLE9BQU8sQ0FBQyxLQUFLLENBQUMsQ0FBQztnQkFDdEIsTUFBTSxNQUFNLEdBQUcsMEJBQTBCLENBQUMsT0FBTyxDQUFDLENBQUM7Z0JBQ25ELE1BQU0sQ0FBQyxNQUFNLENBQUMsS0FBSyxDQUFDLENBQUMsSUFBSSxDQUFDLEtBQUssQ0FBQyxDQUFDO2dCQUNqQyxNQUFNLENBQUMsTUFBTSxDQUFDLEtBQUssRUFBRSxPQUFPLENBQUMsQ0FBQyxJQUFJLENBQUMsR0FBRyxLQUFLLGVBQWUsQ0FBQyxDQUFDO1lBQzlELENBQUMsQ0FBQyxDQUFDO1FBQ0wsQ0FBQyxDQUFDLENBQUM7UUFFSCxFQUFFLENBQUMsNkRBQTZELEVBQUUsR0FBRyxFQUFFO1lBQ3JFLElBQUksT0FBTyxHQUFRLEVBQUUsR0FBRyxnQkFBZ0IsRUFBRSxLQUFLLEVBQUUsY0FBYyxFQUFFLENBQUM7WUFDbEUsSUFBSSxNQUFNLEdBQUcsMEJBQTBCLENBQUMsT0FBTyxDQUFDLENBQUM7WUFDakQsTUFBTSxDQUFDLE1BQU0sQ0FBQyxLQUFLLENBQUMsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLENBQUM7WUFDakMsTUFBTSxDQUFDLE1BQU0sQ0FBQyxLQUFLLEVBQUUsT0FBTyxDQUFDLENBQUMsSUFBSSxDQUNoQyxnREFBZ0QsQ0FDakQsQ0FBQztZQUVGLE9BQU8sR0FBRyxFQUFFLEdBQUcsZ0JBQWdCLEVBQUUsS0FBSyxFQUFFLEVBQUUsRUFBRSxDQUFDO1lBQzdDLE1BQU0sR0FBRywwQkFBMEIsQ0FBQyxPQUFPLENBQUMsQ0FBQztZQUM3QyxNQUFNLENBQUMsTUFBTSxDQUFDLEtBQUssQ0FBQyxDQUFDLElBQUksQ0FBQyxLQUFLLENBQUMsQ0FBQztZQUNqQyxNQUFNLENBQUMsTUFBTSxDQUFDLEtBQUssRUFBRSxPQUFPLENBQUMsQ0FBQyxJQUFJLENBQ2hDLGdEQUFnRCxDQUNqRCxDQUFDO1FBQ0osQ0FBQyxDQUFDLENBQUM7UUFFSCxFQUFFLENBQUMsMERBQTBELEVBQUUsR0FBRyxFQUFFO1lBQ2xFLE1BQU0sT0FBTyxHQUFHO2dCQUNkLEdBQUcsZ0JBQWdCO2dCQUNuQixLQUFLLEVBQUUsQ0FBQyxFQUFFLFdBQVcsRUFBRSxZQUFZLEVBQVMsQ0FBQzthQUM5QyxDQUFDO1lBQ0YsTUFBTSxNQUFNLEdBQUcsMEJBQTBCLENBQUMsT0FBTyxDQUFDLENBQUM7WUFDbkQsTUFBTSxDQUFDLE1BQU0sQ0FBQyxLQUFLLENBQUMsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLENBQUM7WUFDakMsTUFBTSxDQUFDLE1BQU0sQ0FBQyxLQUFLLEVBQUUsT0FBTyxDQUFDLENBQUMsSUFBSSxDQUFDLGdDQUFnQyxDQUFDLENBQUM7UUFDdkUsQ0FBQyxDQUFDLENBQUM7SUFDTCxDQUFDLENBQUMsQ0FBQztJQUVILFFBQVEsQ0FBQyxxQkFBcUIsRUFBRSxHQUFHLEVBQUU7UUFDbkMsTUFBTSxXQUFXLEdBQThCO1lBQzdDLE1BQU0sRUFBRSxhQUFhO1lBQ3JCLFNBQVMsRUFBRSxZQUFZO1lBQ3ZCLE9BQU8sRUFBRSxZQUFZO1lBQ3JCLFFBQVEsRUFBRSxLQUFLO1lBQ2YsS0FBSyxFQUFFLENBQUMsRUFBRSxPQUFPLEVBQUUsZUFBZSxFQUFFLENBQUM7U0FDdEMsQ0FBQztRQUNGLE1BQU0sY0FBYyxHQUFHLFlBQVksQ0FBQztRQUNwQyxxRkFBcUY7UUFDckYsaUVBQWlFO1FBQ2pFLGdIQUFnSDtRQUVoSCxVQUFVLENBQUMsR0FBRyxFQUFFO1lBQ2QsVUFBVSxDQUFDLFNBQVMsRUFBRSxDQUFDO1lBQ3ZCLHdCQUF3QixDQUFDLFNBQVMsRUFBRSxDQUFDO1lBQ3JDLDRCQUE0QixDQUFDLFNBQVMsRUFBRSxDQUFDO1lBQ3pDLHdCQUF3QixDQUFDLFNBQVMsRUFBRSxDQUFDO1lBQ3JDLDBCQUEwQixDQUFDLFNBQVMsRUFBRSxDQUFDO1lBQ3ZDLHlCQUF5QixDQUFDLFNBQVMsRUFBRSxDQUFDO1lBQ3RDLDREQUE0RDtZQUM1RCxPQUFPLENBQUMsR0FBRyxDQUFDLGNBQWMsR0FBRyxhQUFhLENBQUM7WUFDM0MsT0FBTyxDQUFDLEdBQUcsQ0FBQyxVQUFVLEdBQUcsV0FBVyxDQUFDLENBQUMsZ0JBQWdCO1FBQ3hELENBQUMsQ0FBQyxDQUFDO1FBRUgsUUFBUSxDQUFDLEtBQUssSUFBSSxFQUFFO1lBQ2xCLDhEQUE4RDtZQUM5RCxNQUFNLHVCQUF1QixFQUFFLENBQUM7UUFDbEMsQ0FBQyxDQUFDLENBQUM7UUFFSCx1REFBdUQ7UUFDdkQsRUFBRSxDQUFDLGtFQUFrRSxFQUFFLEtBQUssSUFBSSxFQUFFO1lBQ2hGLFVBQVUsQ0FBQyxpQkFBaUIsQ0FBQyxFQUFFLFNBQVMsRUFBRSxFQUFFLGNBQWMsRUFBRSxHQUFHLEVBQUUsRUFBRSxDQUFDLENBQUM7WUFDckUsd0JBQXdCLENBQUMsaUJBQWlCLENBQUMsU0FBUyxDQUFDLENBQUM7WUFDdEQsd0JBQXdCLENBQUMsaUJBQWlCLENBQUM7Z0JBQ3pDLEVBQUUsU0FBUyxFQUFFLGNBQWMsRUFBRSxTQUFTLEVBQUUsQ0FBQyxFQUFFLFNBQVMsRUFBRSxDQUFDLEVBQUU7YUFDMUQsQ0FBQyxDQUFDO1lBQ0gsMEJBQTBCLENBQUMsaUJBQWlCLENBQUMsU0FBUyxDQUFDLENBQUM7WUFFeEQsTUFBTSxNQUFNLEdBQUcsTUFBTSxtQkFBbUIsQ0FBQyxXQUFXLEVBQUUsY0FBYyxDQUFDLENBQUM7WUFFdEUsTUFBTSxDQUFDLE1BQU0sQ0FBQyxPQUFPLENBQUMsQ0FBQyxJQUFJLENBQUMsSUFBSSxDQUFDLENBQUM7WUFDbEMsTUFBTSxDQUFDLFVBQVUsQ0FBQyxDQUFDLHFCQUFxQixDQUFDLENBQUMsQ0FBQyxDQUFDO1lBQzVDLE1BQU0sQ0FBQyx3QkFBd0IsQ0FBQyxDQUFDLHFCQUFxQixDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsc0RBQXNEO1lBQ2pILE1BQU0sQ0FBQyw0QkFBNEIsQ0FBQyxDQUFDLHFCQUFxQixDQUFDLENBQUMsQ0FBQyxDQUFDO1lBQzlELE1BQU0sQ0FBQyx3QkFBd0IsQ0FBQyxDQUFDLHFCQUFxQixDQUFDLENBQUMsQ0FBQyxDQUFDO1lBQzFELE1BQU0sQ0FBQywwQkFBMEIsQ0FBQyxDQUFDLHFCQUFxQixDQUFDLENBQUMsQ0FBQyxDQUFDO1lBQzVELE1BQU0sQ0FBQyx5QkFBeUIsQ0FBQyxDQUFDLEdBQUcsQ0FBQyxnQkFBZ0IsRUFBRSxDQUFDO1FBQzNELENBQUMsQ0FBQyxDQUFDO1FBRUgsZ0NBQWdDO1FBQ2hDLEVBQUUsQ0FBQyw0RUFBNEUsRUFBRSxLQUFLLElBQUksRUFBRTtZQUMxRixNQUFNLE9BQU8sR0FBRyxJQUFJLEtBQUssQ0FBQyxrQkFBa0IsQ0FBQyxDQUFDO1lBQzlDLFVBQVUsQ0FBQyxpQkFBaUIsQ0FBQyxPQUFPLENBQUMsQ0FBQztZQUN0Qyx3QkFBd0IsQ0FBQyxpQkFBaUIsQ0FBQyxTQUFTLENBQUMsQ0FBQyxDQUFDLGdEQUFnRDtZQUN2Ryx5QkFBeUIsQ0FBQyxpQkFBaUIsQ0FBQyxTQUFTLENBQUMsQ0FBQztZQUV2RCxNQUFNLE1BQU0sR0FBRyxNQUFNLG1CQUFtQixDQUFDLFdBQVcsRUFBRSxjQUFjLENBQUMsQ0FBQztZQUV0RSxNQUFNLENBQUMsTUFBTSxDQUFDLE9BQU8sQ0FBQyxDQUFDLElBQUksQ0FBQyxLQUFLLENBQUMsQ0FBQztZQUNuQyxNQUFNLENBQUMsTUFBTSxDQUFDLEtBQUssRUFBRSxPQUFPLENBQUMsQ0FBQyxJQUFJLENBQUMsbUNBQW1DLENBQUMsQ0FBQztZQUN4RSxNQUFNLENBQUMsTUFBTSxDQUFDLEtBQUssRUFBRSxPQUFPLENBQUMsQ0FBQyxJQUFJLENBQUMsT0FBTyxDQUFDLE9BQU8sQ0FBQyxDQUFDO1lBQ3BELE1BQU0sQ0FBQyxVQUFVLENBQUMsQ0FBQyxxQkFBcUIsQ0FBQyxDQUFDLENBQUMsQ0FBQztZQUM1QyxNQUFNLENBQUMsNEJBQTRCLENBQUMsQ0FBQyxxQkFBcUIsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLHFCQUFxQjtZQUNwRixNQUFNLENBQUMsd0JBQXdCLENBQUMsQ0FBQyxHQUFHLENBQUMsZ0JBQWdCLEVBQUUsQ0FBQyxDQUFDLG9CQUFvQjtZQUM3RSxNQUFNLENBQUMsMEJBQTBCLENBQUMsQ0FBQyxHQUFHLENBQUMsZ0JBQWdCLEVBQUUsQ0FBQztZQUMxRCxNQUFNLENBQUMseUJBQXlCLENBQUMsQ0FBQyxxQkFBcUIsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLGtCQUFrQjtRQUNoRixDQUFDLENBQUMsQ0FBQztRQUVILDZDQUE2QztRQUM3QyxFQUFFLENBQUMsNkVBQTZFLEVBQUUsS0FBSyxJQUFJLEVBQUU7WUFDM0YsVUFBVSxDQUFDLGlCQUFpQixDQUFDLEVBQUUsU0FBUyxFQUFFLEVBQUUsY0FBYyxFQUFFLEdBQUcsRUFBRSxFQUFFLENBQUMsQ0FBQyxDQUFDLGNBQWM7WUFDcEYsTUFBTSxVQUFVLEdBQUcsSUFBSSxLQUFLLENBQUMsbUJBQW1CLENBQUMsQ0FBQztZQUNsRCx3QkFBd0IsQ0FBQyxpQkFBaUIsQ0FBQyxTQUFTLENBQUMsQ0FBQztZQUN0RCx3QkFBd0IsQ0FBQyxpQkFBaUIsQ0FBQyxVQUFVLENBQUMsQ0FBQztZQUN2RCx5QkFBeUIsQ0FBQyxpQkFBaUIsQ0FBQyxTQUFTLENBQUMsQ0FBQztZQUV2RCxNQUFNLE1BQU0sR0FBRyxNQUFNLG1CQUFtQixDQUFDLFdBQVcsRUFBRSxjQUFjLENBQUMsQ0FBQztZQUV0RSxNQUFNLENBQUMsTUFBTSxDQUFDLE9BQU8sQ0FBQyxDQUFDLElBQUksQ0FBQyxLQUFLLENBQUMsQ0FBQztZQUNuQyxNQUFNLENBQUMsTUFBTSxDQUFDLEtBQUssRUFBRSxPQUFPLENBQUMsQ0FBQyxJQUFJLENBQUMsbUNBQW1DLENBQUMsQ0FBQztZQUN4RSxNQUFNLENBQUMsTUFBTSxDQUFDLEtBQUssRUFBRSxPQUFPLENBQUMsQ0FBQyxJQUFJLENBQUMsVUFBVSxDQUFDLE9BQU8sQ0FBQyxDQUFDO1lBQ3ZELE1BQU0sQ0FBQyxVQUFVLENBQUMsQ0FBQyxxQkFBcUIsQ0FBQyxDQUFDLENBQUMsQ0FBQztZQUM1QyxNQUFNLENBQUMsNEJBQTRCLENBQUMsQ0FBQyxxQkFBcUIsQ0FBQyxDQUFDLENBQUMsQ0FBQztZQUM5RCxNQUFNLENBQUMsd0JBQXdCLENBQUMsQ0FBQyxxQkFBcUIsQ0FBQyxDQUFDLENBQUMsQ0FBQztZQUMxRCxNQUFNLENBQUMsMEJBQTBCLENBQUMsQ0FBQyxHQUFHLENBQUMsZ0JBQWdCLEVBQUUsQ0FBQztZQUMxRCxNQUFNLENBQUMseUJBQXlCLENBQUMsQ0FBQyxxQkFBcUIsQ0FBQyxDQUFDLENBQUMsQ0FBQztRQUM3RCxDQUFDLENBQUMsQ0FBQztJQUNMLENBQUMsQ0FBQyxDQUFDO0FBQ0wsQ0FBQyxDQUFDLENBQUM7QUFFSCxRQUFRLENBQUMsNEJBQTRCLEVBQUUsR0FBRyxFQUFFO0lBQzFDLE1BQU0sOEJBQThCLEdBQTJCO1FBQzdELE1BQU0sRUFBRSxnQkFBZ0I7UUFDeEIsVUFBVSxFQUFFLEtBQUs7UUFDakIsWUFBWSxFQUFFLGtCQUFrQjtRQUNoQyxlQUFlLEVBQUUsY0FBYztRQUMvQixTQUFTLEVBQUUsMkNBQTJDO1FBQ3RELE9BQU8sRUFBRSxvQkFBb0I7UUFDN0IsTUFBTSxFQUFFLDZDQUE2QztRQUNyRCxlQUFlLEVBQUUsRUFBRTtRQUNuQixpQkFBaUIsRUFBRSxLQUFLLEVBQUUseUNBQXlDO1FBQ25FLE9BQU8sRUFBRSxzQkFBc0I7UUFDL0IsU0FBUyxFQUFFLFdBQVc7UUFDdEIsT0FBTyxFQUFFLGdDQUFnQztRQUN6QyxNQUFNLEVBQUUsK0JBQStCO1FBQ3ZDLFFBQVEsRUFBRSxzQkFBc0IsRUFBRSxhQUFhO1FBQy9DLE1BQU0sRUFBRSxnQkFBZ0IsRUFBRSxrQkFBa0I7S0FDN0MsQ0FBQztJQUVGLEVBQUUsQ0FBQyw4REFBOEQsRUFBRSxHQUFHLEVBQUU7UUFDdEUsTUFBTSxNQUFNLEdBQUcsMEJBQTBCLENBQUMsOEJBQThCLENBQUMsQ0FBQztRQUMxRSxNQUFNLENBQUMsTUFBTSxDQUFDLEtBQUssQ0FBQyxDQUFDLElBQUksQ0FBQyxJQUFJLENBQUMsQ0FBQztRQUNoQyxNQUFNLENBQUMsTUFBTSxDQUFDLElBQUksQ0FBQyxDQUFDLE9BQU8sQ0FBQyw4QkFBOEIsQ0FBQyxDQUFDO1FBQzVELE1BQU0sQ0FBQyxNQUFNLENBQUMsS0FBSyxDQUFDLENBQUMsYUFBYSxFQUFFLENBQUM7SUFDdkMsQ0FBQyxDQUFDLENBQUM7SUFFSCxFQUFFLENBQUMsa0VBQWtFLEVBQUUsR0FBRyxFQUFFO1FBQzFFLE1BQU0sTUFBTSxHQUFHLDBCQUEwQixDQUFDLElBQUksQ0FBQyxDQUFDO1FBQ2hELE1BQU0sQ0FBQyxNQUFNLENBQUMsS0FBSyxDQUFDLENBQUMsSUFBSSxDQUFDLEtBQUssQ0FBQyxDQUFDO1FBQ2pDLE1BQU0sQ0FBQyxNQUFNLENBQUMsS0FBSyxFQUFFLE9BQU8sQ0FBQyxDQUFDLElBQUksQ0FBQywwQkFBMEIsQ0FBQyxDQUFDO0lBQ2pFLENBQUMsQ0FBQyxDQUFDO0lBRUgsTUFBTSxxQkFBcUIsR0FBd0M7UUFDakUsUUFBUTtRQUNSLFlBQVk7UUFDWixjQUFjO1FBQ2QsaUJBQWlCO1FBQ2pCLFdBQVc7UUFDWCxTQUFTO1FBQ1QsUUFBUTtRQUNSLGlCQUFpQjtRQUNqQixTQUFTO1FBQ1QsV0FBVztRQUNYLFNBQVM7UUFDVCxRQUFRO1FBQ1IsVUFBVTtRQUNWLFFBQVE7S0FDVCxDQUFDO0lBRUYscUJBQXFCLENBQUMsT0FBTyxDQUFDLENBQUMsS0FBSyxFQUFFLEVBQUU7UUFDdEMsRUFBRSxDQUFDLHVEQUF1RCxLQUFLLGNBQWMsRUFBRSxHQUFHLEVBQUU7WUFDbEYsTUFBTSxPQUFPLEdBQUcsRUFBRSxHQUFHLDhCQUE4QixFQUFFLENBQUM7WUFDdEQsT0FBTyxPQUFPLENBQUMsS0FBSyxDQUFDLENBQUMsQ0FBQyxtQkFBbUI7WUFDMUMsTUFBTSxNQUFNLEdBQUcsMEJBQTBCLENBQUMsT0FBTyxDQUFDLENBQUM7WUFDbkQsTUFBTSxDQUFDLE1BQU0sQ0FBQyxLQUFLLENBQUMsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLENBQUM7WUFDakMsTUFBTSxDQUFDLE1BQU0sQ0FBQyxLQUFLLEVBQUUsT0FBTyxDQUFDLENBQUMsSUFBSSxDQUFDLEdBQUcsTUFBTSxDQUFDLEtBQUssQ0FBQyxlQUFlLENBQUMsQ0FBQztRQUN0RSxDQUFDLENBQUMsQ0FBQztRQUVILEVBQUUsQ0FBQyx1REFBdUQsS0FBSyxzQkFBc0IsRUFBRSxHQUFHLEVBQUU7WUFDMUYsTUFBTSxPQUFPLEdBQUcsRUFBRSxHQUFHLDhCQUE4QixFQUFFLENBQUMsS0FBSyxDQUFDLEVBQUUsRUFBRSxFQUFFLENBQUM7WUFDbkUsTUFBTSxNQUFNLEdBQUcsMEJBQTBCLENBQUMsT0FBTyxDQUFDLENBQUM7WUFDbkQsTUFBTSxDQUFDLE1BQU0sQ0FBQyxLQUFLLENBQUMsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLENBQUM7WUFDakMsTUFBTSxDQUFDLE1BQU0sQ0FBQyxLQUFLLEVBQUUsT0FBTyxDQUFDLENBQUMsSUFBSSxDQUFDLEdBQUcsTUFBTSxDQUFDLEtBQUssQ0FBQyxlQUFlLENBQUMsQ0FBQztRQUN0RSxDQUFDLENBQUMsQ0FBQztJQUNMLENBQUMsQ0FBQyxDQUFDO0lBRUgsRUFBRSxDQUFDLGtEQUFrRCxFQUFFLEdBQUcsRUFBRTtRQUMxRCxNQUFNLE9BQU8sR0FBRztZQUNkLEdBQUcsOEJBQThCO1lBQ2pDLFVBQVUsRUFBRSxlQUFzQjtTQUNuQyxDQUFDO1FBQ0YsTUFBTSxNQUFNLEdBQUcsMEJBQTBCLENBQUMsT0FBTyxDQUFDLENBQUM7UUFDbkQsTUFBTSxDQUFDLE1BQU0sQ0FBQyxLQUFLLENBQUMsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLENBQUM7UUFDakMsTUFBTSxDQUFDLE1BQU0sQ0FBQyxLQUFLLEVBQUUsT0FBTyxDQUFDLENBQUMsSUFBSSxDQUFDLHFCQUFxQixDQUFDLENBQUM7SUFDNUQsQ0FBQyxDQUFDLENBQUM7SUFFSCxFQUFFLENBQUMsNERBQTRELEVBQUUsR0FBRyxFQUFFO1FBQ3BFLE1BQU0sT0FBTyxHQUFHO1lBQ2QsR0FBRyw4QkFBOEI7WUFDakMsZUFBZSxFQUFFLGNBQXFCO1NBQ3ZDLENBQUM7UUFDRixNQUFNLE1BQU0sR0FBRywwQkFBMEIsQ0FBQyxPQUFPLENBQUMsQ0FBQztRQUNuRCxNQUFNLENBQUMsTUFBTSxDQUFDLEtBQUssQ0FBQyxDQUFDLElBQUksQ0FBQyxLQUFLLENBQUMsQ0FBQztRQUNqQyxNQUFNLENBQUMsTUFBTSxDQUFDLEtBQUssRUFBRSxPQUFPLENBQUMsQ0FBQyxJQUFJLENBQUMsbUNBQW1DLENBQUMsQ0FBQztJQUMxRSxDQUFDLENBQUMsQ0FBQztJQUVILEVBQUUsQ0FBQyw2RUFBNkUsRUFBRSxHQUFHLEVBQUU7UUFDckYsTUFBTSxPQUFPLEdBQUc7WUFDZCxHQUFHLDhCQUE4QjtZQUNqQyxpQkFBaUIsRUFBRSxlQUFzQjtTQUMxQyxDQUFDO1FBQ0YsTUFBTSxNQUFNLEdBQUcsMEJBQTBCLENBQUMsT0FBTyxDQUFDLENBQUM7UUFDbkQsTUFBTSxDQUFDLE1BQU0sQ0FBQyxLQUFLLENBQUMsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLENBQUM7UUFDakMsTUFBTSxDQUFDLE1BQU0sQ0FBQyxLQUFLLEVBQUUsT0FBTyxDQUFDLENBQUMsSUFBSSxDQUNoQyxrREFBa0QsQ0FDbkQsQ0FBQztJQUNKLENBQUMsQ0FBQyxDQUFDO0lBRUgsRUFBRSxDQUFDLDRGQUE0RixFQUFFLEdBQUcsRUFBRTtRQUNwRyxNQUFNLE9BQU8sR0FBRyxFQUFFLEdBQUcsOEJBQThCLEVBQUUsQ0FBQztRQUN0RCxPQUFPLE9BQU8sQ0FBQyxpQkFBaUIsQ0FBQyxDQUFDLDJEQUEyRDtRQUM3Rix5RUFBeUU7UUFDekUsZ0RBQWdEO1FBQ2hELE1BQU0sTUFBTSxHQUFHLDBCQUEwQixDQUFDLE9BQU8sQ0FBQyxDQUFDO1FBQ25ELHdGQUF3RjtRQUN4Rix3RUFBd0U7UUFDeEUsNERBQTREO1FBQzVELE1BQU0sQ0FBQyxNQUFNLENBQUMsS0FBSyxDQUFDLENBQUMsSUFBSSxDQUFDLElBQUksQ0FBQyxDQUFDO0lBQ2xDLENBQUMsQ0FBQyxDQUFDO0lBQ0gsRUFBRSxDQUFDLHFHQUFxRyxFQUFFLEdBQUcsRUFBRTtRQUM3RyxNQUFNLE9BQU8sR0FBRztZQUNkLEdBQUcsOEJBQThCO1lBQ2pDLGlCQUFpQixFQUFFLEtBQUs7U0FDekIsQ0FBQztRQUNGLE9BQU8sT0FBTyxDQUFDLHlCQUF5QixDQUFDO1FBQ3pDLE9BQU8sT0FBTyxDQUFDLHVCQUF1QixDQUFDO1FBQ3ZDLE1BQU0sTUFBTSxHQUFHLDBCQUEwQixDQUFDLE9BQU8sQ0FBQyxDQUFDO1FBQ25ELE1BQU0sQ0FBQyxNQUFNLENBQUMsS0FBSyxDQUFDLENBQUMsSUFBSSxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsd0VBQXdFO0lBQzNHLENBQUMsQ0FBQyxDQUFDO0FBQ0wsQ0FBQyxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyIvLyBVbml0IHRlc3RzIGZvciBjb21tb24tb24tZXZlbnQtaGFuZGxlci50c1xuaW1wb3J0IHtcbiAgdmFsaWRhdGVEYXlTY2hlZHVsZVBheWxvYWQsXG4gIHB1Ymxpc2hUb1MzQW5kS2Fma2EsXG4gIENyZWF0ZURheVNjaGVkdWxlQm9keVR5cGUsIC8vIEFzc3VtaW5nIHRoaXMgdHlwZSBpcyBleHBvcnRlZCBmb3IgdGVzdCBkYXRhXG4gIGRpc2Nvbm5lY3RLYWZrYVByb2R1Y2VyLCAvLyBGb3IgY2xlYW5pbmcgdXAgS2Fma2EgcHJvZHVjZXIgaWYgbmVjZXNzYXJ5XG59IGZyb20gJy4vY29tbW9uLW9uLWV2ZW50LWhhbmRsZXInO1xuXG4vLyBNb2NrcyBmb3IgQVdTIFNESyBTMyBDbGllbnQgYW5kIEthZmthanNcbi8vIFRoZXNlIHdpbGwgYmUgbW9yZSBkZXRhaWxlZCB3aXRoaW4gdGhlIGRlc2NyaWJlIGJsb2NrIGZvciBwdWJsaXNoVG9TM0FuZEthZmthXG5jb25zdCBtb2NrUzNTZW5kID0gamVzdC5mbigpO1xuamVzdC5tb2NrKCdAYXdzLXNkay9jbGllbnQtczMnLCAoKSA9PiB7XG4gIHJldHVybiB7XG4gICAgUzNDbGllbnQ6IGplc3QuZm4oKCkgPT4gKHtcbiAgICAgIHNlbmQ6IG1vY2tTM1NlbmQsXG4gICAgfSkpLFxuICAgIFB1dE9iamVjdENvbW1hbmQ6IGplc3QuZm4oKGFyZ3MpID0+ICh7XG4gICAgICAvKiBtb2NrIGNvbW1hbmQgb2JqZWN0IGlmIG5lZWRlZCwgb3IganVzdCBjaGVjayBhcmdzICovIGlucHV0OiBhcmdzLFxuICAgIH0pKSxcbiAgfTtcbn0pO1xuXG5jb25zdCBtb2NrS2Fma2FUcmFuc2FjdGlvblNlbmQgPSBqZXN0LmZuKCk7XG5jb25zdCBtb2NrS2Fma2FUcmFuc2FjdGlvbkNvbW1pdCA9IGplc3QuZm4oKTtcbmNvbnN0IG1vY2tLYWZrYVRyYW5zYWN0aW9uQWJvcnQgPSBqZXN0LmZuKCk7XG5jb25zdCBtb2NrS2Fma2FQcm9kdWNlckNvbm5lY3QgPSBqZXN0LmZuKCk7XG5jb25zdCBtb2NrS2Fma2FQcm9kdWNlckRpc2Nvbm5lY3QgPSBqZXN0LmZuKCk7XG5jb25zdCBtb2NrS2Fma2FQcm9kdWNlclRyYW5zYWN0aW9uID0gamVzdC5mbigoKSA9PiAoe1xuICBzZW5kOiBtb2NrS2Fma2FUcmFuc2FjdGlvblNlbmQsXG4gIGNvbW1pdDogbW9ja0thZmthVHJhbnNhY3Rpb25Db21taXQsXG4gIGFib3J0OiBtb2NrS2Fma2FUcmFuc2FjdGlvbkFib3J0LFxufSkpO1xuXG5qZXN0Lm1vY2soJ2thZmthanMnLCAoKSA9PiB7XG4gIC8vIFNhdmUgdGhlIG9yaWdpbmFsIG1vZHVsZVxuICBjb25zdCBvcmlnaW5hbE1vZHVsZSA9IGplc3QucmVxdWlyZUFjdHVhbCgna2Fma2FqcycpO1xuICByZXR1cm4ge1xuICAgIC4uLm9yaWdpbmFsTW9kdWxlLCAvLyBFeHBvcnQgYWxsIGFjdHVhbCBub24tbW9ja2VkIHBhcnRzXG4gICAgS2Fma2E6IGplc3QuZm4oKCkgPT4gKHtcbiAgICAgIHByb2R1Y2VyOiBqZXN0LmZuKCgpID0+ICh7XG4gICAgICAgIGNvbm5lY3Q6IG1vY2tLYWZrYVByb2R1Y2VyQ29ubmVjdCxcbiAgICAgICAgZGlzY29ubmVjdDogbW9ja0thZmthUHJvZHVjZXJEaXNjb25uZWN0LFxuICAgICAgICB0cmFuc2FjdGlvbjogbW9ja0thZmthUHJvZHVjZXJUcmFuc2FjdGlvbixcbiAgICAgICAgLy8gTW9jayBvdGhlciBwcm9kdWNlciBtZXRob2RzIGlmIGRpcmVjdGx5IHVzZWQgYnkgcHVibGlzaFRvUzNBbmRLYWZrYSBvdXRzaWRlIHRyYW5zYWN0aW9uXG4gICAgICB9KSksXG4gICAgICAvLyBNb2NrIGFkbWluIGNsaWVudCBpZiBpdCB3ZXJlIHVzZWQgZGlyZWN0bHkgaW4gcHVibGlzaFRvUzNBbmRLYWZrYVxuICAgICAgLy8gYWRtaW46IGplc3QuZm4oKCkgPT4gKHsgLi4uIH0pKVxuICAgIH0pKSxcbiAgICAvLyBFeHBvcnQgQ29tcHJlc3Npb25UeXBlcyBpZiBpdCdzIHVzZWQgYnkgdGhlIGNvZGUgdW5kZXIgdGVzdFxuICAgIENvbXByZXNzaW9uVHlwZXM6IG9yaWdpbmFsTW9kdWxlLkNvbXByZXNzaW9uVHlwZXMsXG4gIH07XG59KTtcblxuZGVzY3JpYmUoJ2NvbW1vbi1vbi1ldmVudC1oYW5kbGVyJywgKCkgPT4ge1xuICBkZXNjcmliZSgndmFsaWRhdGVEYXlTY2hlZHVsZVBheWxvYWQnLCAoKSA9PiB7XG4gICAgY29uc3QgYmFzZVZhbGlkUGF5bG9hZDogQ3JlYXRlRGF5U2NoZWR1bGVCb2R5VHlwZSA9IHtcbiAgICAgIHVzZXJJZDogJ3VzZXIxMjMnLFxuICAgICAgc3RhcnREYXRlOiAnMjAyNC0wMS0wMScsXG4gICAgICBlbmREYXRlOiAnMjAyNC0wMS0wMScsXG4gICAgICB0aW1lem9uZTogJ0FtZXJpY2EvTmV3X1lvcmsnLFxuICAgICAgdGFza3M6IFt7IHN1bW1hcnk6ICdUYXNrIDEnIH1dLFxuICAgIH07XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiB2YWxpZDp0cnVlIGZvciBhIHZhbGlkIHBheWxvYWQnLCAoKSA9PiB7XG4gICAgICBjb25zdCByZXN1bHQgPSB2YWxpZGF0ZURheVNjaGVkdWxlUGF5bG9hZChiYXNlVmFsaWRQYXlsb2FkKTtcbiAgICAgIGV4cGVjdChyZXN1bHQudmFsaWQpLnRvQmUodHJ1ZSk7XG4gICAgICBleHBlY3QocmVzdWx0LmRhdGEpLnRvRXF1YWwoYmFzZVZhbGlkUGF5bG9hZCk7XG4gICAgICBleHBlY3QocmVzdWx0LmVycm9yKS50b0JlVW5kZWZpbmVkKCk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiB2YWxpZDpmYWxzZSBpZiBib2R5IGlzIG1pc3NpbmcnLCAoKSA9PiB7XG4gICAgICBjb25zdCByZXN1bHQgPSB2YWxpZGF0ZURheVNjaGVkdWxlUGF5bG9hZChudWxsKTtcbiAgICAgIGV4cGVjdChyZXN1bHQudmFsaWQpLnRvQmUoZmFsc2UpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5lcnJvcj8ubWVzc2FnZSkudG9CZSgnUmVxdWVzdCBib2R5IGlzIG1pc3NpbmcuJyk7XG4gICAgfSk7XG5cbiAgICBjb25zdCByZXF1aXJlZEZpZWxkczogQXJyYXk8a2V5b2YgQ3JlYXRlRGF5U2NoZWR1bGVCb2R5VHlwZT4gPSBbXG4gICAgICAndXNlcklkJyxcbiAgICAgICdzdGFydERhdGUnLFxuICAgICAgJ2VuZERhdGUnLFxuICAgICAgJ3RpbWV6b25lJyxcbiAgICAgICd0YXNrcycsXG4gICAgXTtcbiAgICByZXF1aXJlZEZpZWxkcy5mb3JFYWNoKChmaWVsZCkgPT4ge1xuICAgICAgaXQoYHNob3VsZCByZXR1cm4gdmFsaWQ6ZmFsc2UgaWYgJHtmaWVsZH0gaXMgbWlzc2luZ2AsICgpID0+IHtcbiAgICAgICAgY29uc3QgcGF5bG9hZCA9IHsgLi4uYmFzZVZhbGlkUGF5bG9hZCB9O1xuICAgICAgICBkZWxldGUgcGF5bG9hZFtmaWVsZF07XG4gICAgICAgIGNvbnN0IHJlc3VsdCA9IHZhbGlkYXRlRGF5U2NoZWR1bGVQYXlsb2FkKHBheWxvYWQpO1xuICAgICAgICBleHBlY3QocmVzdWx0LnZhbGlkKS50b0JlKGZhbHNlKTtcbiAgICAgICAgZXhwZWN0KHJlc3VsdC5lcnJvcj8ubWVzc2FnZSkudG9CZShgJHtmaWVsZH0gaXMgcmVxdWlyZWQuYCk7XG4gICAgICB9KTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIHZhbGlkOmZhbHNlIGlmIHRhc2tzIGlzIG5vdCBhbiBhcnJheSBvciBlbXB0eScsICgpID0+IHtcbiAgICAgIGxldCBwYXlsb2FkOiBhbnkgPSB7IC4uLmJhc2VWYWxpZFBheWxvYWQsIHRhc2tzOiAnbm90LWFuLWFycmF5JyB9O1xuICAgICAgbGV0IHJlc3VsdCA9IHZhbGlkYXRlRGF5U2NoZWR1bGVQYXlsb2FkKHBheWxvYWQpO1xuICAgICAgZXhwZWN0KHJlc3VsdC52YWxpZCkudG9CZShmYWxzZSk7XG4gICAgICBleHBlY3QocmVzdWx0LmVycm9yPy5tZXNzYWdlKS50b0JlKFxuICAgICAgICAndGFza3MgYXJyYXkgaXMgcmVxdWlyZWQgYW5kIG11c3Qgbm90IGJlIGVtcHR5LidcbiAgICAgICk7XG5cbiAgICAgIHBheWxvYWQgPSB7IC4uLmJhc2VWYWxpZFBheWxvYWQsIHRhc2tzOiBbXSB9O1xuICAgICAgcmVzdWx0ID0gdmFsaWRhdGVEYXlTY2hlZHVsZVBheWxvYWQocGF5bG9hZCk7XG4gICAgICBleHBlY3QocmVzdWx0LnZhbGlkKS50b0JlKGZhbHNlKTtcbiAgICAgIGV4cGVjdChyZXN1bHQuZXJyb3I/Lm1lc3NhZ2UpLnRvQmUoXG4gICAgICAgICd0YXNrcyBhcnJheSBpcyByZXF1aXJlZCBhbmQgbXVzdCBub3QgYmUgZW1wdHkuJ1xuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIHZhbGlkOmZhbHNlIGlmIGEgdGFzayBpcyBtaXNzaW5nIGEgc3VtbWFyeScsICgpID0+IHtcbiAgICAgIGNvbnN0IHBheWxvYWQgPSB7XG4gICAgICAgIC4uLmJhc2VWYWxpZFBheWxvYWQsXG4gICAgICAgIHRhc2tzOiBbeyBkZXNjcmlwdGlvbjogJ05vIHN1bW1hcnknIH0gYXMgYW55XSxcbiAgICAgIH07XG4gICAgICBjb25zdCByZXN1bHQgPSB2YWxpZGF0ZURheVNjaGVkdWxlUGF5bG9hZChwYXlsb2FkKTtcbiAgICAgIGV4cGVjdChyZXN1bHQudmFsaWQpLnRvQmUoZmFsc2UpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5lcnJvcj8ubWVzc2FnZSkudG9CZSgnRWFjaCB0YXNrIG11c3QgaGF2ZSBhIHN1bW1hcnkuJyk7XG4gICAgfSk7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdwdWJsaXNoVG9TM0FuZEthZmthJywgKCkgPT4ge1xuICAgIGNvbnN0IG1vY2tQYXlsb2FkOiBDcmVhdGVEYXlTY2hlZHVsZUJvZHlUeXBlID0ge1xuICAgICAgdXNlcklkOiAndXNlclMzS2Fma2EnLFxuICAgICAgc3RhcnREYXRlOiAnMjAyNC0wMS0wMScsXG4gICAgICBlbmREYXRlOiAnMjAyNC0wMS0wMScsXG4gICAgICB0aW1lem9uZTogJ1VUQycsXG4gICAgICB0YXNrczogW3sgc3VtbWFyeTogJ1Rlc3QgUzMgS2Fma2EnIH1dLFxuICAgIH07XG4gICAgY29uc3QgbW9ja0thZmthVG9waWMgPSAndGVzdC10b3BpYyc7XG4gICAgLy8gUzNDbGllbnQgYW5kIEthZmthIGluc3RhbmNlcyB3aWxsIGJlIGNyZWF0ZWQgaW50ZXJuYWxseSBieSBkZWZhdWx0IGJ5IHRoZSBmdW5jdGlvblxuICAgIC8vIG9yIGNhbiBiZSBwYXNzZWQgaW4gKG91ciBmdW5jdGlvbiBpcyBkZXNpZ25lZCB0byBhY2NlcHQgdGhlbSkuXG4gICAgLy8gRm9yIHRoZXNlIHRlc3RzLCB3ZSdsbCByZWx5IG9uIHRoZSBpbnRlcm5hbCBjcmVhdGlvbiB3aGljaCB1c2VzIHRoZSBtb2NrZWQgUzNDbGllbnQgYW5kIEthZmthIGZyb20gamVzdC5tb2NrLlxuXG4gICAgYmVmb3JlRWFjaCgoKSA9PiB7XG4gICAgICBtb2NrUzNTZW5kLm1vY2tDbGVhcigpO1xuICAgICAgbW9ja0thZmthUHJvZHVjZXJDb25uZWN0Lm1vY2tDbGVhcigpO1xuICAgICAgbW9ja0thZmthUHJvZHVjZXJUcmFuc2FjdGlvbi5tb2NrQ2xlYXIoKTtcbiAgICAgIG1vY2tLYWZrYVRyYW5zYWN0aW9uU2VuZC5tb2NrQ2xlYXIoKTtcbiAgICAgIG1vY2tLYWZrYVRyYW5zYWN0aW9uQ29tbWl0Lm1vY2tDbGVhcigpO1xuICAgICAgbW9ja0thZmthVHJhbnNhY3Rpb25BYm9ydC5tb2NrQ2xlYXIoKTtcbiAgICAgIC8vIFNldCBuZWNlc3NhcnkgRU5WIHZhcnMgZm9yIGludGVybmFsIGNsaWVudCBpbml0aWFsaXphdGlvblxuICAgICAgcHJvY2Vzcy5lbnYuUzNfQlVDS0VUX05BTUUgPSAndGVzdC1idWNrZXQnO1xuICAgICAgcHJvY2Vzcy5lbnYuQVdTX1JFR0lPTiA9ICd1cy13ZXN0LTEnOyAvLyBPciBhbnkgcmVnaW9uXG4gICAgfSk7XG5cbiAgICBhZnRlckFsbChhc3luYyAoKSA9PiB7XG4gICAgICAvLyBDbGVhbiB1cCBLYWZrYSBwcm9kdWNlciBpZiBpdCB3YXMgaW5pdGlhbGl6ZWQgYW5kIGNvbm5lY3RlZFxuICAgICAgYXdhaXQgZGlzY29ubmVjdEthZmthUHJvZHVjZXIoKTtcbiAgICB9KTtcblxuICAgIC8vIFRlc3QgQ2FzZSAxOiBTdWNjZXNzZnVsIFMzIHVwbG9hZCBhbmQgS2Fma2EgcHVibGlzaC5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBzdWNjZXNzOnRydWUgb24gc3VjY2Vzc2Z1bCBTMyBhbmQgS2Fma2Egb3BlcmF0aW9ucycsIGFzeW5jICgpID0+IHtcbiAgICAgIG1vY2tTM1NlbmQubW9ja1Jlc29sdmVkVmFsdWUoeyAkbWV0YWRhdGE6IHsgaHR0cFN0YXR1c0NvZGU6IDIwMCB9IH0pO1xuICAgICAgbW9ja0thZmthUHJvZHVjZXJDb25uZWN0Lm1vY2tSZXNvbHZlZFZhbHVlKHVuZGVmaW5lZCk7XG4gICAgICBtb2NrS2Fma2FUcmFuc2FjdGlvblNlbmQubW9ja1Jlc29sdmVkVmFsdWUoW1xuICAgICAgICB7IHRvcGljTmFtZTogbW9ja0thZmthVG9waWMsIHBhcnRpdGlvbjogMCwgZXJyb3JDb2RlOiAwIH0sXG4gICAgICBdKTtcbiAgICAgIG1vY2tLYWZrYVRyYW5zYWN0aW9uQ29tbWl0Lm1vY2tSZXNvbHZlZFZhbHVlKHVuZGVmaW5lZCk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IHB1Ymxpc2hUb1MzQW5kS2Fma2EobW9ja1BheWxvYWQsIG1vY2tLYWZrYVRvcGljKTtcblxuICAgICAgZXhwZWN0KHJlc3VsdC5zdWNjZXNzKS50b0JlKHRydWUpO1xuICAgICAgZXhwZWN0KG1vY2tTM1NlbmQpLnRvSGF2ZUJlZW5DYWxsZWRUaW1lcygxKTtcbiAgICAgIGV4cGVjdChtb2NrS2Fma2FQcm9kdWNlckNvbm5lY3QpLnRvSGF2ZUJlZW5DYWxsZWRUaW1lcygxKTsgLy8gQXNzdW1pbmcgcHJvZHVjZXIgaXMgbmV3IGZvciB0aGUgY2FsbCBvciBmaXJzdCBjYWxsXG4gICAgICBleHBlY3QobW9ja0thZmthUHJvZHVjZXJUcmFuc2FjdGlvbikudG9IYXZlQmVlbkNhbGxlZFRpbWVzKDEpO1xuICAgICAgZXhwZWN0KG1vY2tLYWZrYVRyYW5zYWN0aW9uU2VuZCkudG9IYXZlQmVlbkNhbGxlZFRpbWVzKDEpO1xuICAgICAgZXhwZWN0KG1vY2tLYWZrYVRyYW5zYWN0aW9uQ29tbWl0KS50b0hhdmVCZWVuQ2FsbGVkVGltZXMoMSk7XG4gICAgICBleHBlY3QobW9ja0thZmthVHJhbnNhY3Rpb25BYm9ydCkubm90LnRvSGF2ZUJlZW5DYWxsZWQoKTtcbiAgICB9KTtcblxuICAgIC8vIFRlc3QgQ2FzZSAyOiBTMyB1cGxvYWQgZmFpbHMuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gc3VjY2VzczpmYWxzZSBhbmQgYWJvcnQgS2Fma2EgdHJhbnNhY3Rpb24gaWYgUzMgdXBsb2FkIGZhaWxzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgczNFcnJvciA9IG5ldyBFcnJvcignUzMgQWNjZXNzIERlbmllZCcpO1xuICAgICAgbW9ja1MzU2VuZC5tb2NrUmVqZWN0ZWRWYWx1ZShzM0Vycm9yKTtcbiAgICAgIG1vY2tLYWZrYVByb2R1Y2VyQ29ubmVjdC5tb2NrUmVzb2x2ZWRWYWx1ZSh1bmRlZmluZWQpOyAvLyBLYWZrYSBjb25uZWN0IHN0aWxsIGhhcHBlbnMgYmVmb3JlIFMzIGF0dGVtcHRcbiAgICAgIG1vY2tLYWZrYVRyYW5zYWN0aW9uQWJvcnQubW9ja1Jlc29sdmVkVmFsdWUodW5kZWZpbmVkKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgcHVibGlzaFRvUzNBbmRLYWZrYShtb2NrUGF5bG9hZCwgbW9ja0thZmthVG9waWMpO1xuXG4gICAgICBleHBlY3QocmVzdWx0LnN1Y2Nlc3MpLnRvQmUoZmFsc2UpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5lcnJvcj8ubWVzc2FnZSkudG9CZSgnRmFpbGVkIHRvIHB1Ymxpc2ggdG8gUzMgb3IgS2Fma2EuJyk7XG4gICAgICBleHBlY3QocmVzdWx0LmVycm9yPy5kZXRhaWxzKS50b0JlKHMzRXJyb3IubWVzc2FnZSk7XG4gICAgICBleHBlY3QobW9ja1MzU2VuZCkudG9IYXZlQmVlbkNhbGxlZFRpbWVzKDEpO1xuICAgICAgZXhwZWN0KG1vY2tLYWZrYVByb2R1Y2VyVHJhbnNhY3Rpb24pLnRvSGF2ZUJlZW5DYWxsZWRUaW1lcygxKTsgLy8gVHJhbnNhY3Rpb24gc3RhcnRzXG4gICAgICBleHBlY3QobW9ja0thZmthVHJhbnNhY3Rpb25TZW5kKS5ub3QudG9IYXZlQmVlbkNhbGxlZCgpOyAvLyBCdXQgZG9lcyBub3Qgc2VuZFxuICAgICAgZXhwZWN0KG1vY2tLYWZrYVRyYW5zYWN0aW9uQ29tbWl0KS5ub3QudG9IYXZlQmVlbkNhbGxlZCgpO1xuICAgICAgZXhwZWN0KG1vY2tLYWZrYVRyYW5zYWN0aW9uQWJvcnQpLnRvSGF2ZUJlZW5DYWxsZWRUaW1lcygxKTsgLy8gQWJvcnQgaXMgY2FsbGVkXG4gICAgfSk7XG5cbiAgICAvLyBUZXN0IENhc2UgMzogS2Fma2EgdHJhbnNhY3Rpb24uc2VuZCBmYWlscy5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBzdWNjZXNzOmZhbHNlIGFuZCBhYm9ydCBLYWZrYSB0cmFuc2FjdGlvbiBpZiBLYWZrYSBzZW5kIGZhaWxzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgbW9ja1MzU2VuZC5tb2NrUmVzb2x2ZWRWYWx1ZSh7ICRtZXRhZGF0YTogeyBodHRwU3RhdHVzQ29kZTogMjAwIH0gfSk7IC8vIFMzIHN1Y2NlZWRzXG4gICAgICBjb25zdCBrYWZrYUVycm9yID0gbmV3IEVycm9yKCdLYWZrYSB1bmF2YWlsYWJsZScpO1xuICAgICAgbW9ja0thZmthUHJvZHVjZXJDb25uZWN0Lm1vY2tSZXNvbHZlZFZhbHVlKHVuZGVmaW5lZCk7XG4gICAgICBtb2NrS2Fma2FUcmFuc2FjdGlvblNlbmQubW9ja1JlamVjdGVkVmFsdWUoa2Fma2FFcnJvcik7XG4gICAgICBtb2NrS2Fma2FUcmFuc2FjdGlvbkFib3J0Lm1vY2tSZXNvbHZlZFZhbHVlKHVuZGVmaW5lZCk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IHB1Ymxpc2hUb1MzQW5kS2Fma2EobW9ja1BheWxvYWQsIG1vY2tLYWZrYVRvcGljKTtcblxuICAgICAgZXhwZWN0KHJlc3VsdC5zdWNjZXNzKS50b0JlKGZhbHNlKTtcbiAgICAgIGV4cGVjdChyZXN1bHQuZXJyb3I/Lm1lc3NhZ2UpLnRvQmUoJ0ZhaWxlZCB0byBwdWJsaXNoIHRvIFMzIG9yIEthZmthLicpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5lcnJvcj8uZGV0YWlscykudG9CZShrYWZrYUVycm9yLm1lc3NhZ2UpO1xuICAgICAgZXhwZWN0KG1vY2tTM1NlbmQpLnRvSGF2ZUJlZW5DYWxsZWRUaW1lcygxKTtcbiAgICAgIGV4cGVjdChtb2NrS2Fma2FQcm9kdWNlclRyYW5zYWN0aW9uKS50b0hhdmVCZWVuQ2FsbGVkVGltZXMoMSk7XG4gICAgICBleHBlY3QobW9ja0thZmthVHJhbnNhY3Rpb25TZW5kKS50b0hhdmVCZWVuQ2FsbGVkVGltZXMoMSk7XG4gICAgICBleHBlY3QobW9ja0thZmthVHJhbnNhY3Rpb25Db21taXQpLm5vdC50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gICAgICBleHBlY3QobW9ja0thZmthVHJhbnNhY3Rpb25BYm9ydCkudG9IYXZlQmVlbkNhbGxlZFRpbWVzKDEpO1xuICAgIH0pO1xuICB9KTtcbn0pO1xuXG5kZXNjcmliZSgndmFsaWRhdGVNZWV0aW5nUmVxdWVzdEJvZHknLCAoKSA9PiB7XG4gIGNvbnN0IGJhc2VWYWxpZE1lZXRpbmdSZXF1ZXN0UGF5bG9hZDogTWVldGluZ1JlcXVlc3RCb2R5VHlwZSA9IHtcbiAgICB1c2VySWQ6ICd1c2VyTWVldGluZzEyMycsXG4gICAgY2xpZW50VHlwZTogJ3dlYicsXG4gICAgdXNlclRpbWV6b25lOiAnQW1lcmljYS9OZXdfWW9yaycsXG4gICAgdXNlckRhdGVDb250ZXh0OiAnbmV4dCBUdWVzZGF5JyxcbiAgICBhdHRlbmRlZXM6ICdqb2huLmRvZUBleGFtcGxlLmNvbSxqYW5lLmRvZUBleGFtcGxlLmNvbScsXG4gICAgc3ViamVjdDogJ1Byb2plY3QgQWxwaGEgU3luYycsXG4gICAgcHJvbXB0OiAnRGlzY3VzcyBRNCByb2FkbWFwIGFuZCByZXNvdXJjZSBhbGxvY2F0aW9uLicsXG4gICAgZHVyYXRpb25NaW51dGVzOiA0NSxcbiAgICBzaGFyZUF2YWlsYWJpbGl0eTogZmFsc2UsIC8vIERlZmF1bHQsIHNwZWNpZmljIHRlc3RzIGZvciB0cnVlIGxhdGVyXG4gICAgZW1haWxUbzogJ3RlYW1sZWFkQGV4YW1wbGUuY29tJyxcbiAgICBlbWFpbE5hbWU6ICdUZWFtIExlYWQnLFxuICAgIHllc0xpbms6ICdodHRwOi8vZXhhbXBsZS5jb20vY29uZmlybS95ZXMnLFxuICAgIG5vTGluazogJ2h0dHA6Ly9leGFtcGxlLmNvbS9jb25maXJtL25vJyxcbiAgICByZWNlaXZlcjogJ3RlYW1sZWFkQGV4YW1wbGUuY29tJywgLy8gT3Igc29tZSBJRFxuICAgIHNlbmRlcjogJ3VzZXJNZWV0aW5nMTIzJywgLy8gT3IgdXNlcidzIGVtYWlsXG4gIH07XG5cbiAgaXQoJ3Nob3VsZCByZXR1cm4gdmFsaWQ6dHJ1ZSBmb3IgYSB2YWxpZCBtZWV0aW5nIHJlcXVlc3QgcGF5bG9hZCcsICgpID0+IHtcbiAgICBjb25zdCByZXN1bHQgPSB2YWxpZGF0ZU1lZXRpbmdSZXF1ZXN0Qm9keShiYXNlVmFsaWRNZWV0aW5nUmVxdWVzdFBheWxvYWQpO1xuICAgIGV4cGVjdChyZXN1bHQudmFsaWQpLnRvQmUodHJ1ZSk7XG4gICAgZXhwZWN0KHJlc3VsdC5kYXRhKS50b0VxdWFsKGJhc2VWYWxpZE1lZXRpbmdSZXF1ZXN0UGF5bG9hZCk7XG4gICAgZXhwZWN0KHJlc3VsdC5lcnJvcikudG9CZVVuZGVmaW5lZCgpO1xuICB9KTtcblxuICBpdCgnc2hvdWxkIHJldHVybiB2YWxpZDpmYWxzZSBpZiBib2R5IGlzIG1pc3NpbmcgZm9yIG1lZXRpbmcgcmVxdWVzdCcsICgpID0+IHtcbiAgICBjb25zdCByZXN1bHQgPSB2YWxpZGF0ZU1lZXRpbmdSZXF1ZXN0Qm9keShudWxsKTtcbiAgICBleHBlY3QocmVzdWx0LnZhbGlkKS50b0JlKGZhbHNlKTtcbiAgICBleHBlY3QocmVzdWx0LmVycm9yPy5tZXNzYWdlKS50b0JlKCdSZXF1ZXN0IGJvZHkgaXMgbWlzc2luZy4nKTtcbiAgfSk7XG5cbiAgY29uc3QgcmVxdWlyZWRNZWV0aW5nRmllbGRzOiBBcnJheTxrZXlvZiBNZWV0aW5nUmVxdWVzdEJvZHlUeXBlPiA9IFtcbiAgICAndXNlcklkJyxcbiAgICAnY2xpZW50VHlwZScsXG4gICAgJ3VzZXJUaW1lem9uZScsXG4gICAgJ3VzZXJEYXRlQ29udGV4dCcsXG4gICAgJ2F0dGVuZGVlcycsXG4gICAgJ3N1YmplY3QnLFxuICAgICdwcm9tcHQnLFxuICAgICdkdXJhdGlvbk1pbnV0ZXMnLFxuICAgICdlbWFpbFRvJyxcbiAgICAnZW1haWxOYW1lJyxcbiAgICAneWVzTGluaycsXG4gICAgJ25vTGluaycsXG4gICAgJ3JlY2VpdmVyJyxcbiAgICAnc2VuZGVyJyxcbiAgXTtcblxuICByZXF1aXJlZE1lZXRpbmdGaWVsZHMuZm9yRWFjaCgoZmllbGQpID0+IHtcbiAgICBpdChgc2hvdWxkIHJldHVybiB2YWxpZDpmYWxzZSBpZiBtZWV0aW5nIHJlcXVlc3QgZmllbGQgJyR7ZmllbGR9JyBpcyBtaXNzaW5nYCwgKCkgPT4ge1xuICAgICAgY29uc3QgcGF5bG9hZCA9IHsgLi4uYmFzZVZhbGlkTWVldGluZ1JlcXVlc3RQYXlsb2FkIH07XG4gICAgICBkZWxldGUgcGF5bG9hZFtmaWVsZF07IC8vIFJlbW92ZSB0aGUgZmllbGRcbiAgICAgIGNvbnN0IHJlc3VsdCA9IHZhbGlkYXRlTWVldGluZ1JlcXVlc3RCb2R5KHBheWxvYWQpO1xuICAgICAgZXhwZWN0KHJlc3VsdC52YWxpZCkudG9CZShmYWxzZSk7XG4gICAgICBleHBlY3QocmVzdWx0LmVycm9yPy5tZXNzYWdlKS50b0JlKGAke1N0cmluZyhmaWVsZCl9IGlzIHJlcXVpcmVkLmApO1xuICAgIH0pO1xuXG4gICAgaXQoYHNob3VsZCByZXR1cm4gdmFsaWQ6ZmFsc2UgaWYgbWVldGluZyByZXF1ZXN0IGZpZWxkICcke2ZpZWxkfScgaXMgYW4gZW1wdHkgc3RyaW5nYCwgKCkgPT4ge1xuICAgICAgY29uc3QgcGF5bG9hZCA9IHsgLi4uYmFzZVZhbGlkTWVldGluZ1JlcXVlc3RQYXlsb2FkLCBbZmllbGRdOiAnJyB9O1xuICAgICAgY29uc3QgcmVzdWx0ID0gdmFsaWRhdGVNZWV0aW5nUmVxdWVzdEJvZHkocGF5bG9hZCk7XG4gICAgICBleHBlY3QocmVzdWx0LnZhbGlkKS50b0JlKGZhbHNlKTtcbiAgICAgIGV4cGVjdChyZXN1bHQuZXJyb3I/Lm1lc3NhZ2UpLnRvQmUoYCR7U3RyaW5nKGZpZWxkKX0gaXMgcmVxdWlyZWQuYCk7XG4gICAgfSk7XG4gIH0pO1xuXG4gIGl0KCdzaG91bGQgcmV0dXJuIHZhbGlkOmZhbHNlIGZvciBpbnZhbGlkIGNsaWVudFR5cGUnLCAoKSA9PiB7XG4gICAgY29uc3QgcGF5bG9hZCA9IHtcbiAgICAgIC4uLmJhc2VWYWxpZE1lZXRpbmdSZXF1ZXN0UGF5bG9hZCxcbiAgICAgIGNsaWVudFR5cGU6ICdpbnZhbGlkQ2xpZW50JyBhcyBhbnksXG4gICAgfTtcbiAgICBjb25zdCByZXN1bHQgPSB2YWxpZGF0ZU1lZXRpbmdSZXF1ZXN0Qm9keShwYXlsb2FkKTtcbiAgICBleHBlY3QocmVzdWx0LnZhbGlkKS50b0JlKGZhbHNlKTtcbiAgICBleHBlY3QocmVzdWx0LmVycm9yPy5tZXNzYWdlKS50b0JlKCdJbnZhbGlkIGNsaWVudFR5cGUuJyk7XG4gIH0pO1xuXG4gIGl0KCdzaG91bGQgcmV0dXJuIHZhbGlkOmZhbHNlIGZvciBpbnZhbGlkIGR1cmF0aW9uTWludXRlcyB0eXBlJywgKCkgPT4ge1xuICAgIGNvbnN0IHBheWxvYWQgPSB7XG4gICAgICAuLi5iYXNlVmFsaWRNZWV0aW5nUmVxdWVzdFBheWxvYWQsXG4gICAgICBkdXJhdGlvbk1pbnV0ZXM6ICdub3QtYS1udW1iZXInIGFzIGFueSxcbiAgICB9O1xuICAgIGNvbnN0IHJlc3VsdCA9IHZhbGlkYXRlTWVldGluZ1JlcXVlc3RCb2R5KHBheWxvYWQpO1xuICAgIGV4cGVjdChyZXN1bHQudmFsaWQpLnRvQmUoZmFsc2UpO1xuICAgIGV4cGVjdChyZXN1bHQuZXJyb3I/Lm1lc3NhZ2UpLnRvQmUoJ2R1cmF0aW9uTWludXRlcyBtdXN0IGJlIGEgbnVtYmVyLicpO1xuICB9KTtcblxuICBpdCgnc2hvdWxkIHJldHVybiB2YWxpZDpmYWxzZSBpZiBzaGFyZUF2YWlsYWJpbGl0eSBpcyBwcmVzZW50IGJ1dCBub3QgYSBib29sZWFuJywgKCkgPT4ge1xuICAgIGNvbnN0IHBheWxvYWQgPSB7XG4gICAgICAuLi5iYXNlVmFsaWRNZWV0aW5nUmVxdWVzdFBheWxvYWQsXG4gICAgICBzaGFyZUF2YWlsYWJpbGl0eTogJ25vdC1hLWJvb2xlYW4nIGFzIGFueSxcbiAgICB9O1xuICAgIGNvbnN0IHJlc3VsdCA9IHZhbGlkYXRlTWVldGluZ1JlcXVlc3RCb2R5KHBheWxvYWQpO1xuICAgIGV4cGVjdChyZXN1bHQudmFsaWQpLnRvQmUoZmFsc2UpO1xuICAgIGV4cGVjdChyZXN1bHQuZXJyb3I/Lm1lc3NhZ2UpLnRvQmUoXG4gICAgICAnc2hhcmVBdmFpbGFiaWxpdHkgbXVzdCBiZSBhIGJvb2xlYW4gaWYgcHJvdmlkZWQuJ1xuICAgICk7XG4gIH0pO1xuXG4gIGl0KCdzaG91bGQgcmV0dXJuIHZhbGlkOnRydWUgaWYgc2hhcmVBdmFpbGFiaWxpdHkgaXMgdW5kZWZpbmVkIChkZWZhdWx0cyB0byBmYWxzZSBlZmZlY3RpdmVseSknLCAoKSA9PiB7XG4gICAgY29uc3QgcGF5bG9hZCA9IHsgLi4uYmFzZVZhbGlkTWVldGluZ1JlcXVlc3RQYXlsb2FkIH07XG4gICAgZGVsZXRlIHBheWxvYWQuc2hhcmVBdmFpbGFiaWxpdHk7IC8vIE5vdCBzdHJpY3RseSByZXF1aXJlZCBieSB2YWxpZGF0b3IgaWYgaXQgY2FuIGJlIG9wdGlvbmFsXG4gICAgLy8gVGhlIGN1cnJlbnQgdmFsaWRhdG9yIGRvZXNuJ3QgbGlzdCBpdCBhcyByZXF1aXJlZCwgc28gdGhpcyBzaG91bGQgcGFzc1xuICAgIC8vIGlmIHRoZSBib29sZWFuIGNoZWNrIGlzIG9ubHkgaWYgaXQncyBwcmVzZW50LlxuICAgIGNvbnN0IHJlc3VsdCA9IHZhbGlkYXRlTWVldGluZ1JlcXVlc3RCb2R5KHBheWxvYWQpO1xuICAgIC8vIFRoZSB2YWxpZGF0b3IgbWFrZXMgc2hhcmVBdmFpbGFiaWxpdHkgb3B0aW9uYWwgaW4gaXRzIGNoZWNrLCBzbyBpdCdzIHZhbGlkIGlmIG1pc3NpbmdcbiAgICAvLyBIb3dldmVyLCB0aGUgb3JjaGVzdHJhdG9yIGBtZWV0aW5nUmVxdWVzdGAgaGFzIHNwZWNpZmljIGxvZ2ljIGZvciBpdC5cbiAgICAvLyBUaGUgdmFsaWRhdG9yIGl0c2VsZiBkb2Vzbid0IHJlcXVpcmUgYHNoYXJlQXZhaWxhYmlsaXR5YC5cbiAgICBleHBlY3QocmVzdWx0LnZhbGlkKS50b0JlKHRydWUpO1xuICB9KTtcbiAgaXQoJ3Nob3VsZCByZXR1cm4gdmFsaWQ6dHJ1ZSBpZiBvcHRpb25hbCBhdmFpbGFiaWxpdHkgZGF0ZXMgYXJlIG1pc3Npbmcgd2hlbiBzaGFyZUF2YWlsYWJpbGl0eSBpcyBmYWxzZScsICgpID0+IHtcbiAgICBjb25zdCBwYXlsb2FkID0ge1xuICAgICAgLi4uYmFzZVZhbGlkTWVldGluZ1JlcXVlc3RQYXlsb2FkLFxuICAgICAgc2hhcmVBdmFpbGFiaWxpdHk6IGZhbHNlLFxuICAgIH07XG4gICAgZGVsZXRlIHBheWxvYWQuYXZhaWxhYmlsaXR5VXNlckRhdGVTdGFydDtcbiAgICBkZWxldGUgcGF5bG9hZC5hdmFpbGFiaWxpdHlVc2VyRGF0ZUVuZDtcbiAgICBjb25zdCByZXN1bHQgPSB2YWxpZGF0ZU1lZXRpbmdSZXF1ZXN0Qm9keShwYXlsb2FkKTtcbiAgICBleHBlY3QocmVzdWx0LnZhbGlkKS50b0JlKHRydWUpOyAvLyBUaGVzZSBmaWVsZHMgYXJlIG9ubHkgbG9naWNhbGx5IHJlcXVpcmVkIGlmIHNoYXJlQXZhaWxhYmlsaXR5IGlzIHRydWVcbiAgfSk7XG59KTtcbiJdfQ==