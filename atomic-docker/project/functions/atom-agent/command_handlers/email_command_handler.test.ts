import {
  handleSendEmailRequest,
  ParsedNluSendEmailRequest,
} from './email_command_handler';
import * as emailSkills from '../skills/emailSkills'; // To mock sendEmailSkill
import { logger as mockLogger } from '../../_utils/logger'; // To mock logger

// Mock emailSkills module
jest.mock('../skills/emailSkills', () => ({
  ...jest.requireActual('../skills/emailSkills'), // Import and retain other exports
  sendEmail: jest.fn(), // Mock only the sendEmail function
}));

// Mock logger
jest.mock('../../_utils/logger', () => ({
  logger: {
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
  },
}));

const mockSendEmailSkill = emailSkills.sendEmail as jest.Mock;

describe('Email Command Handler', () => {
  beforeEach(() => {
    // Clear mock history before each test
    mockSendEmailSkill.mockClear();
    (mockLogger.info as jest.Mock).mockClear();
    (mockLogger.warn as jest.Mock).mockClear();
    (mockLogger.error as jest.Mock).mockClear();
  });

  describe('handleSendEmailRequest', () => {
    const baseRequest: ParsedNluSendEmailRequest = {
      userId: 'test-user-123',
      emailDetails: {
        to: 'recipient@example.com',
        subject: 'Test Subject from Handler',
        body: 'Test body from handler.',
      },
    };

    it('should call sendEmailSkill and return success message on successful send', async () => {
      mockSendEmailSkill.mockResolvedValueOnce({
        success: true,
        emailId: 'test-email-id-123',
        message: 'Email sent successfully.',
      });

      const responseMessage = await handleSendEmailRequest(baseRequest);

      expect(mockSendEmailSkill).toHaveBeenCalledWith(baseRequest.emailDetails);
      expect(responseMessage).toContain(
        "Okay, I've sent the email to recipient@example.com"
      );
      expect(responseMessage).toContain('Message ID: test-email-id-123');
      expect(mockLogger.info).toHaveBeenCalledWith(
        `Agent: Attempting to send email for user ${baseRequest.userId} with details:`,
        baseRequest.emailDetails
      );
      expect(mockLogger.info).toHaveBeenCalledWith(
        `Agent: Email sent successfully for user ${baseRequest.userId}. Response:`,
        expect.objectContaining({ success: true, emailId: 'test-email-id-123' })
      );
    });

    it('should return failure message if sendEmailSkill indicates failure', async () => {
      mockSendEmailSkill.mockResolvedValueOnce({
        success: false,
        message: 'SES specific error from skill.',
      });

      const responseMessage = await handleSendEmailRequest(baseRequest);

      expect(mockSendEmailSkill).toHaveBeenCalledWith(baseRequest.emailDetails);
      expect(responseMessage).toContain(
        'I tried to send the email, but something went wrong. SES specific error from skill.'
      );
      expect(mockLogger.error).toHaveBeenCalledWith(
        `Agent: Failed to send email for user ${baseRequest.userId}. Response:`,
        expect.objectContaining({
          success: false,
          message: 'SES specific error from skill.',
        })
      );
    });

    it('should return validation error message if "to" is missing', async () => {
      const invalidRequest: ParsedNluSendEmailRequest = {
        ...baseRequest,
        emailDetails: { ...baseRequest.emailDetails, to: '' },
      };
      const responseMessage = await handleSendEmailRequest(invalidRequest);
      expect(responseMessage).toContain(
        "I'm sorry, but I'm missing some crucial information"
      );
      expect(mockSendEmailSkill).not.toHaveBeenCalled();
      expect(mockLogger.warn).toHaveBeenCalled();
    });

    it('should return validation error message if "subject" is missing', async () => {
      const invalidRequest: ParsedNluSendEmailRequest = {
        ...baseRequest,
        emailDetails: { ...baseRequest.emailDetails, subject: '' },
      };
      const responseMessage = await handleSendEmailRequest(invalidRequest);
      expect(responseMessage).toContain(
        "I'm sorry, but I'm missing some crucial information"
      );
      expect(mockSendEmailSkill).not.toHaveBeenCalled();
      expect(mockLogger.warn).toHaveBeenCalled();
    });

    it('should return validation error message if "body" and "htmlBody" are missing', async () => {
      const invalidRequest: ParsedNluSendEmailRequest = {
        ...baseRequest,
        emailDetails: {
          to: 'recipient@example.com',
          subject: 'Valid Subject',
          body: '',
        }, // body is empty, htmlBody undefined
      };
      const responseMessage = await handleSendEmailRequest(invalidRequest);
      expect(responseMessage).toContain(
        "I'm sorry, but I'm missing some crucial information"
      );
      expect(mockSendEmailSkill).not.toHaveBeenCalled();
      expect(mockLogger.warn).toHaveBeenCalled();
    });

    it('should handle unexpected errors from sendEmailSkill', async () => {
      const errorMessage = 'Unexpected skill error';
      mockSendEmailSkill.mockRejectedValueOnce(new Error(errorMessage));

      const responseMessage = await handleSendEmailRequest(baseRequest);

      expect(mockSendEmailSkill).toHaveBeenCalledWith(baseRequest.emailDetails);
      expect(responseMessage).toContain(
        `I encountered a critical error while trying to send the email: ${errorMessage}`
      );
      expect(mockLogger.error).toHaveBeenCalledWith(
        `Agent: Critical error in handleSendEmailRequest for user ${baseRequest.userId}:`,
        expect.any(Error)
      );
    });
  });
});
