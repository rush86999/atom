import { sendEmail } from './email'; // The function to test
import { ENV } from '@utils/env';
import { logger } from '@utils/logger';

// Mock dependencies
jest.mock('nodemailer');
jest.mock('email-templates');
jest.mock('@utils/env', () => ({
  ENV: {
    AUTH_SMTP_HOST: 'smtp.example.com',
    AUTH_SMTP_PORT: '587',
    AUTH_SMTP_SECURE: 'false',
    AUTH_SMTP_PASS: 'password',
    AUTH_SMTP_USER: 'user',
    AUTH_SMTP_SENDER: 'sender@example.com',
    AUTH_SMTP_X_SMTPAPI_HEADER: '',
    LOG_LEVEL: 'info', // Or whatever default you want for tests
  },
}));
jest.mock('@utils/logger', () => ({
  logger: {
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
    debug: jest.fn(), // Add other levels if used by the module
  },
}));

const mockNodemailer = require('nodemailer');
const mockEmailTemplates = require('email-templates');

describe('sendEmail (Nodemailer via _utils/email/email.ts)', () => {
  let mockTransportSendMail: jest.Mock;
  let mockEmailClientSend: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();

    mockTransportSendMail = jest.fn();
    mockNodemailer.createTransport.mockReturnValue({
      sendMail: mockTransportSendMail,
    });

    // Mock the email-templates client's send method
    // This is a bit more involved because sendEmail uses `new Email().send()`
    // We need to mock the Email class constructor and its send method.
    mockEmailClientSend = jest.fn();
    mockEmailTemplates.mockImplementation(() => {
      return {
        send: mockEmailClientSend,
      };
    });
  });

  const emailOptions = {
    template: 'test-template',
    message: {
      to: 'recipient@example.com',
      subject: 'Test Subject', // Added subject for completeness
    },
    locals: { name: 'Tester' },
  };

  it('should send an email successfully on the first attempt', async () => {
    mockEmailClientSend.mockResolvedValueOnce({
      messageId: 'nodemailer-message-id-123',
    });

    await sendEmail(emailOptions);

    expect(mockEmailClientSend).toHaveBeenCalledTimes(1);
    expect(mockEmailClientSend).toHaveBeenCalledWith(
      expect.objectContaining({
        template: emailOptions.template,
        message: expect.objectContaining({ to: emailOptions.message.to }),
      })
    );
    expect(logger.info).toHaveBeenCalledWith(
      expect.stringContaining('Email sent successfully via SMTP on attempt 1'),
      expect.anything()
    );
    expect(logger.warn).not.toHaveBeenCalled();
    expect(logger.error).not.toHaveBeenCalled();
  });

  it('should send an email successfully on the second attempt after one failure', async () => {
    mockEmailClientSend
      .mockRejectedValueOnce(new Error('SMTP Error Attempt 1'))
      .mockResolvedValueOnce({ messageId: 'nodemailer-message-id-456' });

    await sendEmail(emailOptions);

    expect(mockEmailClientSend).toHaveBeenCalledTimes(2);
    expect(logger.warn).toHaveBeenCalledTimes(1);
    expect(logger.warn).toHaveBeenCalledWith(
      expect.stringContaining(
        'Attempt 1 to send email via SMTP failed. Retrying...'
      ),
      expect.objectContaining({ errorMessage: 'SMTP Error Attempt 1' })
    );
    expect(logger.info).toHaveBeenCalledWith(
      expect.stringContaining('Email sent successfully via SMTP on attempt 2'),
      expect.anything()
    );
    expect(logger.error).not.toHaveBeenCalled();
  });

  it('should fail after all retry attempts and log the final error', async () => {
    mockEmailClientSend
      .mockRejectedValueOnce(new Error('SMTP Error Attempt 1'))
      .mockRejectedValueOnce(new Error('SMTP Error Attempt 2'))
      .mockRejectedValueOnce(new Error('SMTP Error Attempt 3'));

    await expect(sendEmail(emailOptions)).rejects.toThrow(
      'SMTP Error Attempt 3'
    );

    expect(mockEmailClientSend).toHaveBeenCalledTimes(3);
    expect(logger.warn).toHaveBeenCalledTimes(3);
    expect(logger.warn).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining('Attempt 1'),
      expect.anything()
    );
    expect(logger.warn).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('Attempt 2'),
      expect.anything()
    );
    expect(logger.warn).toHaveBeenNthCalledWith(
      3,
      expect.stringContaining('Attempt 3'),
      expect.anything()
    );
    expect(logger.error).toHaveBeenCalledTimes(1);
    expect(logger.error).toHaveBeenCalledWith(
      expect.stringContaining('SMTP error after 3 attempts'),
      expect.anything(), // The actual error object, which is hard to match exactly
      expect.anything() // The context object
    );
  });

  it('should include X-SMTPAPI header if ENV var is set', async () => {
    const originalSmtpApiHeader = ENV.AUTH_SMTP_X_SMTPAPI_HEADER;
    ENV.AUTH_SMTP_X_SMTPAPI_HEADER = '{"category": "test"}';
    mockEmailClientSend.mockResolvedValueOnce({
      messageId: 'nodemailer-header-test',
    });

    await sendEmail(emailOptions);

    expect(mockEmailClientSend).toHaveBeenCalledTimes(1);
    expect(mockEmailClientSend).toHaveBeenCalledWith(
      expect.objectContaining({
        message: expect.objectContaining({
          headers: expect.objectContaining({
            'X-SMTPAPI': '{"category": "test"}',
          }),
        }),
      })
    );
    // Restore ENV var
    ENV.AUTH_SMTP_X_SMTPAPI_HEADER = originalSmtpApiHeader;
  });
});
