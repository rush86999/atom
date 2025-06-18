import { triggerZap } from './zapierSkills';
import { ZapTriggerResponse } from '../types';
import * as zapierUtils from '../_libs/zapier-utils';
import got from 'got';

// Mocks
jest.mock('got');
const mockedGot = got as jest.Mocked<typeof got>;

jest.mock('../_libs/zapier-utils', () => ({
    getZapierWebhookUrl: jest.fn(),
}));
const mockedGetZapierWebhookUrl = zapierUtils.getZapierWebhookUrl as jest.Mock;

describe('Zapier Skills - triggerZap', () => {
    let consoleErrorSpy: jest.SpyInstance;
    let consoleLogSpy: jest.SpyInstance;
    const mockUserId = 'test-user-zap-skill';
    const mockZapName = 'TestZap';
    const mockWebhookUrl = 'https://hooks.zapier.com/hooks/test/url';
    const mockData = { key: 'value', another: 123 };

    beforeEach(() => {
        jest.clearAllMocks();
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
        consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
    });
    afterEach(() => {
        consoleErrorSpy.mockRestore();
        consoleLogSpy.mockRestore();
    });

    it('should successfully trigger Zap and return parsed response', async () => {
        mockedGetZapierWebhookUrl.mockResolvedValue(mockWebhookUrl);
        const zapierSuccessResponse = { status: 'success', attempt: 'attempt_guid', id: 'zap_run_id', message: 'Zap triggered!' };
        mockedGot.post.mockResolvedValue({
            statusCode: 200,
            body: zapierSuccessResponse,
        } as any);

        const result = await triggerZap(mockUserId, mockZapName, mockData);

        expect(mockedGetZapierWebhookUrl).toHaveBeenCalledWith(mockUserId, mockZapName);
        expect(mockedGot.post).toHaveBeenCalledWith(mockWebhookUrl, {
            json: mockData,
            responseType: 'json',
            throwHttpErrors: false,
        });
        expect(result).toEqual({
            success: true,
            zapName: mockZapName,
            message: zapierSuccessResponse.message, // Uses message from response
            runId: zapierSuccessResponse.id,
        });
    });

    it('should use status if message is not in Zapier response', async () => {
        mockedGetZapierWebhookUrl.mockResolvedValue(mockWebhookUrl);
        const zapierSuccessResponse = { status: 'success_alt_field', attempt: 'attempt_guid2' };
        mockedGot.post.mockResolvedValue({ statusCode: 200, body: zapierSuccessResponse } as any);
        const result = await triggerZap(mockUserId, mockZapName, mockData);
        expect(result.message).toBe('success_alt_field');
    });

    it('should use default message if no specific message/status from Zapier', async () => {
        mockedGetZapierWebhookUrl.mockResolvedValue(mockWebhookUrl);
        mockedGot.post.mockResolvedValue({ statusCode: 200, body: {} } as any); // Empty body
        const result = await triggerZap(mockUserId, mockZapName, mockData);
        expect(result.message).toBe(`Zap "${mockZapName}" triggered successfully.`);
    });

    it('should return failure if webhook URL is not found', async () => {
        mockedGetZapierWebhookUrl.mockResolvedValue(null);
        const result = await triggerZap(mockUserId, mockZapName, mockData);
        expect(result.success).toBe(false);
        expect(result.message).toContain('No webhook URL configured');
        expect(mockedGot.post).not.toHaveBeenCalled();
    });

    it('should return failure if getZapierWebhookUrl throws', async () => {
        mockedGetZapierWebhookUrl.mockRejectedValue(new Error("DB error fetching URL"));
        const result = await triggerZap(mockUserId, mockZapName, mockData);
        expect(result.success).toBe(false);
        expect(result.message).toContain('Could not retrieve configuration');
        expect(result.message).toContain('DB error fetching URL');
    });

    it('should return failure if Zapier returns non-2xx status', async () => {
        mockedGetZapierWebhookUrl.mockResolvedValue(mockWebhookUrl);
        const zapierErrorResponse = { error: 'Invalid data', message: 'Zapier processing failed' };
        mockedGot.post.mockResolvedValue({
            statusCode: 400,
            body: zapierErrorResponse,
        } as any);
        const result = await triggerZap(mockUserId, mockZapName, mockData);
        expect(result.success).toBe(false);
        expect(result.message).toBe(zapierErrorResponse.message); // Should pick up message from body
    });

    it('should use error if message is not in Zapier error response', async () => {
        mockedGetZapierWebhookUrl.mockResolvedValue(mockWebhookUrl);
        const zapierErrorResponse = { error: 'zap_specific_error_code' };
        mockedGot.post.mockResolvedValue({ statusCode: 503, body: zapierErrorResponse } as any);
        const result = await triggerZap(mockUserId, mockZapName, mockData);
        expect(result.success).toBe(false);
        expect(result.message).toBe('zap_specific_error_code');
    });

    it('should use default status code message if no specific error/message from Zapier', async () => {
        mockedGetZapierWebhookUrl.mockResolvedValue(mockWebhookUrl);
        mockedGot.post.mockResolvedValue({ statusCode: 403, body: {} } as any); // Empty error body
        const result = await triggerZap(mockUserId, mockZapName, mockData);
        expect(result.success).toBe(false);
        expect(result.message).toBe('Zapier webhook returned status 403.');
    });


    it('should return failure if got.post throws network error', async () => {
        mockedGetZapierWebhookUrl.mockResolvedValue(mockWebhookUrl);
        mockedGot.post.mockRejectedValue(new Error("Network connection failed"));
        const result = await triggerZap(mockUserId, mockZapName, mockData);
        expect(result.success).toBe(false);
        expect(result.message).toContain('Failed to trigger Zap. Network or parsing error: Network connection failed');
    });

    it('should return failure if userId is missing', async () => {
        // @ts-ignore Test invalid input
        const result = await triggerZap(null, mockZapName, mockData);
        expect(result.success).toBe(false);
        expect(result.message).toBe("User ID not provided.");
    });

    it('should return failure if zapName is missing', async () => {
         // @ts-ignore Test invalid input
        const result = await triggerZap(mockUserId, null, mockData);
        expect(result.success).toBe(false);
        expect(result.message).toBe("Zap name not provided.");
    });
});
