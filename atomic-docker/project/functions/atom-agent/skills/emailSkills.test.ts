import * as emailSkills from "./emailSkills";

describe("Email Skills", () => {
  // Mock ENV variables for AWS SES
  const mockEnv = {
    AWS_REGION: "us-east-1",
    AWS_ACCESS_KEY_ID: "test-access-key-id",
    AWS_SECRET_ACCESS_KEY: "test-secret-access-key",
    SES_SOURCE_EMAIL: "sender@example.com",
  };

  // Mock @aws-sdk/client-ses
  const mockSend = jest.fn();

  beforeEach(() => {
    mockSend.mockReset();
    jest.resetModules();

    jest.mock("@aws-sdk/client-ses", () => ({
      SESClient: jest.fn(() => ({
        send: mockSend,
      })),
      SendEmailCommand: jest.fn((params) => ({
        type: "SendEmailCommand",
        params,
      })),
    }));

    jest.mock("../../_utils/logger", () => ({
      logger: {
        info: jest.fn(),
        warn: jest.fn(),
        error: jest.fn(),
      },
    }));

    jest.mock("../../_utils/env", () => ({
      ENV: mockEnv,
    }));
  });

  describe("sendEmail (AWS SES Implementation)", () => {
    it("should send an email successfully with text body", async () => {
      mockSend.mockResolvedValueOnce({ MessageId: "ses-message-id-123" });
      const freshEmailSkills = require("./emailSkills");

      const emailDetails = {
        to: "recipient@example.com",
        subject: "Hello from SES",
        body: "This is a test email body.",
      };
      const response = await freshEmailSkills.sendEmail(emailDetails);

      expect(response.success).toBe(true);
      expect(response.emailId).toBe("ses-message-id-123");
    });

    it("should handle SES send error", async () => {
      mockSend.mockRejectedValueOnce(new Error("SES Error: Access Denied"));
      const freshEmailSkills = require("./emailSkills");

      const emailDetails = {
        to: "recipient@example.com",
        subject: "Test Subject",
        body: "Test email body",
      };
      const response = await freshEmailSkills.sendEmail(emailDetails);

      expect(response.success).toBe(false);
      expect(response.message).toContain(
        "Failed to send email via AWS SES after 3 attempts",
      );
      expect(mockSend).toHaveBeenCalledTimes(3);
    });
  });
});
