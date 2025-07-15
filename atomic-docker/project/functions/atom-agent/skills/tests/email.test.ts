import { handleListEmails, handleReadEmail, handleSendEmail } from '../email';
import * as emailSkills from '../emailSkills';

jest.mock('../emailSkills', () => ({
    listRecentEmails: jest.fn(),
    readEmail: jest.fn(),
    sendEmail: jest.fn(),
}));

describe('email skill', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });

    describe('handleListEmails', () => {
        it('should return a list of recent emails', async () => {
            const mockEmails = [
                {
                    id: 'test-email-1',
                    sender: 'test1@example.com',
                    subject: 'Test Email 1',
                    read: false,
                },
                {
                    id: 'test-email-2',
                    sender: 'test2@example.com',
                    subject: 'Test Email 2',
                    read: true,
                },
            ];
            (emailSkills.listRecentEmails as jest.Mock).mockResolvedValue(mockEmails);

            const result = await handleListEmails({});

            expect(result).toContain('Recent emails (via NLU):');
            expect(result).toContain('Test Email 1');
            expect(result).toContain('Test Email 2');
        });

        it('should return a message when there are no recent emails', async () => {
            (emailSkills.listRecentEmails as jest.Mock).mockResolvedValue([]);

            const result = await handleListEmails({});

            expect(result).toBe('No recent emails found (via NLU).');
        });

        it('should return an error message when an error occurs', async () => {
            (emailSkills.listRecentEmails as jest.Mock).mockRejectedValue(new Error('Test Error'));

            const result = await handleListEmails({});

            expect(result).toBe("Sorry, I couldn't fetch recent emails due to an error (NLU path).");
        });
    });

    describe('handleReadEmail', () => {
        it('should return the content of an email', async () => {
            const mockEmail = {
                id: 'test-email-1',
                sender: 'test1@example.com',
                recipient: 'test@example.com',
                subject: 'Test Email 1',
                timestamp: new Date().toISOString(),
                body: 'This is a test email.',
            };
            (emailSkills.readEmail as jest.Mock).mockResolvedValue({
                success: true,
                email: mockEmail,
            });

            const result = await handleReadEmail({ email_id: 'test-email-1' });

            expect(result).toContain('Email (ID: test-email-1):');
            expect(result).toContain('This is a test email.');
        });

        it('should return an error message when the email ID is missing', async () => {
            const result = await handleReadEmail({});

            expect(result).toBe('Email ID is required to read an email via NLU.');
        });

        it('should return an error message when an error occurs', async () => {
            (emailSkills.readEmail as jest.Mock).mockRejectedValue(new Error('Test Error'));

            const result = await handleReadEmail({ email_id: 'test-email-1' });

            expect(result).toBe("Sorry, I couldn't read the specified email due to an error (NLU path).");
        });
    });

    describe('handleSendEmail', () => {
        it('should send an email', async () => {
            const mockEmail = {
                to: 'test@example.com',
                subject: 'Test Email',
                body: 'This is a test email.',
            };
            (emailSkills.sendEmail as jest.Mock).mockResolvedValue({
                success: true,
                message: 'Email sent successfully',
                emailId: 'test-email-id',
            });

            const result = await handleSendEmail(mockEmail);

            expect(result).toContain('Email sent via NLU: Email sent successfully');
        });

        it('should return an error message when the recipient is missing', async () => {
            const mockEmail = {
                subject: 'Test Email',
                body: 'This is a test email.',
            };

            const result = await handleSendEmail(mockEmail);

            expect(result).toBe("Recipient 'to' address is required to send an email via NLU.");
        });

        it('should return an error message when the subject is missing', async () => {
            const mockEmail = {
                to: 'test@example.com',
                body: 'This is a test email.',
            };

            const result = await handleSendEmail(mockEmail);

            expect(result).toBe('Subject is required to send an email via NLU.');
        });

        it('should return an error message when the body is missing', async () => {
            const mockEmail = {
                to: 'test@example.com',
                subject: 'Test Email',
            };

            const result = await handleSendEmail(mockEmail);

            expect(result).toBe('Body is required to send an email via NLU.');
        });

        it('should return an error message when an error occurs', async () => {
            const mockEmail = {
                to: 'test@example.com',
                subject: 'Test Email',
                body: 'This is a test email.',
            };
            (emailSkills.sendEmail as jest.Mock).mockRejectedValue(new Error('Test Error'));

            const result = await handleSendEmail(mockEmail);

            expect(result).toBe("Sorry, I couldn't send the email due to an error (NLU path).");
        });
    });
});
