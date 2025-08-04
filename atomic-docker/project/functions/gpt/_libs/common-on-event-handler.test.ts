// Unit tests for common-on-event-handler.ts
import {
  validateDaySchedulePayload,
  publishToS3AndKafka,
  CreateDayScheduleBodyType, // Assuming this type is exported for test data
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
    const baseValidPayload: CreateDayScheduleBodyType = {
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

    const requiredFields: Array<keyof CreateDayScheduleBodyType> = [
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
      let payload: any = { ...baseValidPayload, tasks: 'not-an-array' };
      let result = validateDaySchedulePayload(payload);
      expect(result.valid).toBe(false);
      expect(result.error?.message).toBe(
        'tasks array is required and must not be empty.'
      );

      payload = { ...baseValidPayload, tasks: [] };
      result = validateDaySchedulePayload(payload);
      expect(result.valid).toBe(false);
      expect(result.error?.message).toBe(
        'tasks array is required and must not be empty.'
      );
    });

    it('should return valid:false if a task is missing a summary', () => {
      const payload = {
        ...baseValidPayload,
        tasks: [{ description: 'No summary' } as any],
      };
      const result = validateDaySchedulePayload(payload);
      expect(result.valid).toBe(false);
      expect(result.error?.message).toBe('Each task must have a summary.');
    });
  });

  describe('publishToS3AndKafka', () => {
    const mockPayload: CreateDayScheduleBodyType = {
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
  const baseValidMeetingRequestPayload: MeetingRequestBodyType = {
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

  const requiredMeetingFields: Array<keyof MeetingRequestBodyType> = [
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
      clientType: 'invalidClient' as any,
    };
    const result = validateMeetingRequestBody(payload);
    expect(result.valid).toBe(false);
    expect(result.error?.message).toBe('Invalid clientType.');
  });

  it('should return valid:false for invalid durationMinutes type', () => {
    const payload = {
      ...baseValidMeetingRequestPayload,
      durationMinutes: 'not-a-number' as any,
    };
    const result = validateMeetingRequestBody(payload);
    expect(result.valid).toBe(false);
    expect(result.error?.message).toBe('durationMinutes must be a number.');
  });

  it('should return valid:false if shareAvailability is present but not a boolean', () => {
    const payload = {
      ...baseValidMeetingRequestPayload,
      shareAvailability: 'not-a-boolean' as any,
    };
    const result = validateMeetingRequestBody(payload);
    expect(result.valid).toBe(false);
    expect(result.error?.message).toBe(
      'shareAvailability must be a boolean if provided.'
    );
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
