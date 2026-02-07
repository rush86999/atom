/**
 * Traditional Unit Tests for Email Utilities
 *
 * Tests sendEmail function to kill more mutants
 */

import { sendEmail, generateVerificationEmailHTML } from '../email';

// Mock nodemailer
jest.mock('nodemailer', () => ({
  createTransport: jest.fn(),
}));

import nodemailer from 'nodemailer';

describe('Email Utilities - Traditional Unit Tests', () => {
  const mockSendMail = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (nodemailer.createTransport as jest.Mock).mockReturnValue({
      sendMail: mockSendMail,
    });

    // Set up environment variables for tests
    process.env.SMTP_HOST = 'smtp.example.com';
    process.env.SMTP_USER = 'test@example.com';
    process.env.SMTP_PASS = 'password';
    process.env.SMTP_PORT = '587';
    process.env.EMAIL_FROM = '"Test" <test@example.com>';
    delete process.env.SMTP_SECURE; // Ensure no leftover value
  });

  describe('sendEmail', () => {
    it('should return true when email is sent successfully', async () => {
      mockSendMail.mockResolvedValue({ messageId: 'test-id' });

      const result = await sendEmail({
        to: 'recipient@example.com',
        subject: 'Test Subject',
        html: '<p>Test HTML</p>',
      });

      expect(result).toBe(true);
      expect(nodemailer.createTransport).toHaveBeenCalledWith({
        host: 'smtp.example.com',
        port: 587,
        secure: false,
        auth: {
          user: 'test@example.com',
          pass: 'password',
        },
      });
    });

    it('should return false and log mock when SMTP not configured', async () => {
      delete process.env.SMTP_HOST;

      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();
      const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation();

      const result = await sendEmail({
        to: 'recipient@example.com',
        subject: 'Test Subject',
        html: '<p>Test HTML</p>',
      });

      expect(result).toBe(false);
      expect(consoleWarnSpy).toHaveBeenCalledWith('⚠️ SMTP configuration missing. Email not sent.');
      expect(consoleLogSpy).toHaveBeenCalledWith('[Mock Email] To: recipient@example.com, Subject: Test Subject');

      consoleWarnSpy.mockRestore();
      consoleLogSpy.mockRestore();
    });

    it('should return false when SMTP_USER not configured', async () => {
      delete process.env.SMTP_USER;

      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();
      const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation();

      const result = await sendEmail({
        to: 'recipient@example.com',
        subject: 'Test Subject',
        html: '<p>Test HTML</p>',
      });

      expect(result).toBe(false);

      consoleWarnSpy.mockRestore();
      consoleLogSpy.mockRestore();
    });

    it('should return false when SMTP_PASS not configured', async () => {
      delete process.env.SMTP_PASS;

      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();
      const consoleLogSpy = jest.spyOn(console, 'log').mockImplementation();

      const result = await sendEmail({
        to: 'recipient@example.com',
        subject: 'Test Subject',
        html: '<p>Test HTML</p>',
      });

      expect(result).toBe(false);

      consoleWarnSpy.mockRestore();
      consoleLogSpy.mockRestore();
    });

    it('should return false on send error', async () => {
      mockSendMail.mockRejectedValue(new Error('Send failed'));

      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

      const result = await sendEmail({
        to: 'recipient@example.com',
        subject: 'Test Subject',
        html: '<p>Test HTML</p>',
      });

      expect(result).toBe(false);
      expect(consoleErrorSpy).toHaveBeenCalledWith('Error sending email:', expect.any(Error));

      consoleErrorSpy.mockRestore();
    });

    it('should use default from address when EMAIL_FROM not set', async () => {
      delete process.env.EMAIL_FROM;
      mockSendMail.mockResolvedValue({ messageId: 'test-id' });

      const result = await sendEmail({
        to: 'recipient@example.com',
        subject: 'Test Subject',
        html: '<p>Test HTML</p>',
      });

      expect(result).toBe(true);
      expect(mockSendMail).toHaveBeenCalledWith({
        from: '"Atom Platform" <noreply@atom.ai>',
        to: 'recipient@example.com',
        subject: 'Test Subject',
        html: '<p>Test HTML</p>',
      });
    });

    it('should parse SMTP_PORT correctly as integer', async () => {
      process.env.SMTP_PORT = '465';
      process.env.SMTP_SECURE = 'true';
      mockSendMail.mockResolvedValue({ messageId: 'test-id' });

      const result = await sendEmail({
        to: 'recipient@example.com',
        subject: 'Test Subject',
        html: '<p>Test HTML</p>',
      });

      expect(result).toBe(true);
      expect(nodemailer.createTransport).toHaveBeenCalledWith({
        host: 'smtp.example.com',
        port: 465,
        secure: true,
        auth: {
          user: 'test@example.com',
          pass: 'password',
        },
      });
    });

    it('should use default port 587 when SMTP_PORT not set', async () => {
      delete process.env.SMTP_PORT;
      mockSendMail.mockResolvedValue({ messageId: 'test-id' });

      const result = await sendEmail({
        to: 'recipient@example.com',
        subject: 'Test Subject',
        html: '<p>Test HTML</p>',
      });

      expect(result).toBe(true);
      expect(nodemailer.createTransport).toHaveBeenCalledWith({
        host: 'smtp.example.com',
        port: 587,
        secure: false,
        auth: {
          user: 'test@example.com',
          pass: 'password',
        },
      });
    });

    it('should pass all email options correctly', async () => {
      mockSendMail.mockResolvedValue({ messageId: 'test-id' });

      const result = await sendEmail({
        to: 'test@example.com',
        subject: 'Important Email',
        html: '<h1>Hello</h1>',
      });

      expect(result).toBe(true);
      expect(mockSendMail).toHaveBeenCalledWith({
        from: '"Test" <test@example.com>',
        to: 'test@example.com',
        subject: 'Important Email',
        html: '<h1>Hello</h1>',
      });
    });
  });

  describe('generateVerificationEmailHTML', () => {
    it('should contain verification code in output', () => {
      const html = generateVerificationEmailHTML('ABC123', 'TestUser');
      expect(html).toContain('ABC123');
    });

    it('should contain name in greeting', () => {
      const html = generateVerificationEmailHTML('ABC123', 'Alice');
      expect(html).toContain('Alice');
    });

    it('should contain expiration message', () => {
      const html = generateVerificationEmailHTML('ABC123', 'Bob');
      expect(html).toContain('15 minutes');
    });

    it('should contain ignore message', () => {
      const html = generateVerificationEmailHTML('ABC123', 'Charlie');
      expect(html).toContain("didn't request this code");
    });

    it('should contain strong tag for code styling', () => {
      const html = generateVerificationEmailHTML('ABC123', 'Dave');
      expect(html).toContain('<strong');
    });

    it('should contain style attributes', () => {
      const html = generateVerificationEmailHTML('ABC123', 'Eve');
      expect(html).toContain('style=');
    });

    it('should handle empty name', () => {
      const html = generateVerificationEmailHTML('ABC123', '');
      expect(html).toContain('ABC123');
    });

    it('should handle special characters in name', () => {
      const html = generateVerificationEmailHTML('ABC123', "O'Brien");
      expect(html).toContain("O'Brien");
    });

    it('should handle very long code', () => {
      const html = generateVerificationEmailHTML('VERYLONGCODE123456', 'Frank');
      expect(html).toContain('VERYLONGCODE123456');
    });
  });
});
