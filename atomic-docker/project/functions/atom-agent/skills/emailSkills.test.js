// Note: The tests for listRecentEmails and readEmail might be outdated
// as they seem to rely on a local mock data structure that was present in earlier versions
// or a different setup involving Hasura actions directly.
// These tests will likely fail or need significant updates if searchMyEmails and readEmail
// now make actual GraphQL calls to Hasura as suggested by their implementation.
// For the scope of this task, I'm focusing on the sendEmail tests.

describe('Email Skills', () => {
    // Mock ENV variables for AWS SES
    const mockEnv = {
        AWS_REGION: 'us-east-1',
        AWS_ACCESS_KEY_ID: 'test-access-key-id',
        AWS_SECRET_ACCESS_KEY: 'test-secret-access-key',
        SES_SOURCE_EMAIL: 'sender@example.com',
        // Mock other ENV vars if emailSkills.ts ends up using them indirectly
    };
    // Mock @aws-sdk/client-ses
    const mockSend = jest.fn();
    beforeEach(() => {
        // Reset mocks before each test
        mockSend.mockReset(); // Use mockReset to clear mock state and implementations
        jest.resetModules(); // Reset module registry to allow re-importing with fresh mocks
        // Mock modules for each test to ensure clean state
        jest.mock('@aws-sdk/client-ses', () => ({
            SESClient: jest.fn(() => ({
                send: mockSend,
            })),
            SendEmailCommand: jest.fn((params) => ({
                type: 'SendEmailCommand',
                params,
            })),
        }));
        jest.mock('../../_utils/logger', () => ({
            logger: {
                info: jest.fn(),
                warn: jest.fn(),
                error: jest.fn(),
            },
        }));
        jest.mock('../../_utils/env', () => ({
            ENV: mockEnv,
        }));
    });

    describe('sendEmail (AWS SES Implementation)', () => {
        it('should send an email successfully with text body', async () => {
            mockSend.mockResolvedValueOnce({ MessageId: 'ses-message-id-123' });
            const freshEmailSkills = require('./emailSkills'); // Re-import to get fresh mocks
            const emailDetails = {
                to: 'recipient@example.com',
                subject: 'Hello from SES',
                body: 'This is a test email body.',
            };
            const response = await freshEmailSkills.sendEmail(emailDetails);
            expect(response.success).toBe(true);
            expect(response.emailId).toBe('ses-message-id-123');
            expect(response.message).toContain('Email sent successfully via AWS SES.');
            expect(mockSend).toHaveBeenCalledTimes(1);
            const sentCommand = mockSend.mock.calls[0][0];
            expect(sentCommand.params.Source).toBe(mockEnv.SES_SOURCE_EMAIL);
            expect(sentCommand.params.Destination.ToAddresses).toEqual([
                emailDetails.to,
            ]);
            expect(sentCommand.params.Message.Subject.Data).toBe(
                emailDetails.subject
            );
            expect(sentCommand.params.Message.Body.Text.Data).toBe(emailDetails.body);
            expect(sentCommand.params.Message.Body.Html).toBeUndefined();
        });

        it('should send an email successfully with HTML body', async () => {
            mockSend.mockResolvedValueOnce({ MessageId: 'ses-message-id-456' });
            const freshEmailSkills = require('./emailSkills');
            const emailDetails = {
                to: 'recipient@example.com',
                subject: 'HTML Email Test',
                htmlBody: '<p>This is an HTML email.</p>',
            };
            const response = await freshEmailSkills.sendEmail(emailDetails);
            expect(response.success).toBe(true);
            expect(response.emailId).toBe('ses-message-id-456');
            expect(mockSend).toHaveBeenCalledTimes(1);
            const sentCommand = mockSend.mock.calls[0][0];
            expect(sentCommand.params.Message.Body.Html.Data).toBe(
                emailDetails.htmlBody
            );
            expect(sentCommand.params.Message.Body.Text).toBeUndefined();
        });

        it('should send an email successfully with both text and HTML body', async () => {
            mockSend.mockResolvedValueOnce({ MessageId: 'ses-message-id-789' });
            const freshEmailSkills = require('./emailSkills');
            const emailDetails = {
                to: 'recipient@example.com',
                subject: 'Text and HTML Email',
                body: 'Plain text version.',
                htmlBody: '<p>HTML version.</p>',
            };
            const response = await freshEmailSkills.sendEmail(emailDetails);
            expect(response.success).toBe(true);
            expect(response.emailId).toBe('ses-message-id-789');
            expect(mockSend).toHaveBeenCalledTimes(1);
            const sentCommandArgs = mockSend.mock.calls[0][0].params;
            expect(sentCommandArgs.Message.Body.Text.Data).toBe(emailDetails.body);
            expect(sentCommandArgs.Message.Body.Html.Data).toBe(emailDetails.htmlBody);
        });
    });

    describe('Error Handling', () => {
        it('should handle AWS SES errors gracefully', async () => {
            mockSend.mockRejectedValueOnce(new Error('AWS SES Error'));
            const freshEmailSkills = require('./emailSkills');
            const emailDetails = {
                to: 'recipient@example.com',
                subject: 'Error Test',
                body: 'Test body',
            };
            const response = await freshEmailSkills.sendEmail(emailDetails);
            expect(response.success).toBe(false);
            expect(response.message).toContain('Failed to send email');
        });
    });
