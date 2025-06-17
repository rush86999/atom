import * as emailSkills from './emailSkills';
import { Email, SendEmailResponse, ReadEmailResponse } from '../types';

describe('Email Skills', () => {
  // Keep a reference to the original mockEmails to reset state if necessary,
  // or ensure tests don't rely on state changes from one another if mocks are complex.
  // For this simple mock, direct manipulation is tested.

  describe('listRecentEmails', () => {
    it('should return an array of email objects', async () => {
      const emails = await emailSkills.listRecentEmails();
      expect(Array.isArray(emails)).toBe(true);
      if (emails.length > 0) {
        const firstEmail = emails[0];
        expect(firstEmail).toHaveProperty('id');
        expect(firstEmail).toHaveProperty('sender');
        expect(firstEmail).toHaveProperty('subject');
        expect(firstEmail).toHaveProperty('read');
      }
    });

    it('should limit the number of emails returned', async () => {
      // Assuming the mockEmails in emailSkills.ts has at least 2 emails
      const limitedEmails = await emailSkills.listRecentEmails(1);
      expect(limitedEmails.length).toBeLessThanOrEqual(1);

      // Based on current mockEmails in emailSkills.ts (has 3 emails)
      expect(await emailSkills.listRecentEmails(0)).toHaveLength(0);
      expect(await emailSkills.listRecentEmails(1)).toHaveLength(1);
      expect(await emailSkills.listRecentEmails(2)).toHaveLength(2);
      expect(await emailSkills.listRecentEmails(3)).toHaveLength(3);
      expect(await emailSkills.listRecentEmails(4)).toHaveLength(3); // Max of mock data
    });
  });

  describe('readEmail', () => {
    // Reset mock data state before each test if 'read' status changes affect other tests
    // This simple mock doesn't require complex setup/teardown for 'read' status across tests,
    // but in a real scenario with a shared mock object, you might.

    it('should return the email and mark it as read if found', async () => {
      // Use an ID known to be in the mockEmails array and initially unread
      const targetEmailId = 'email1'; // Assuming 'email1' is initially unread

      // Verify it's unread first (optional, depends on mock state persistence)
      // let initialEmails = await emailSkills.listRecentEmails();
      // let initialEmail = initialEmails.find(e => e.id === targetEmailId);
      // if(initialEmail) expect(initialEmail.read).toBe(false);


      const response = await emailSkills.readEmail(targetEmailId);
      expect(response.success).toBe(true);
      expect(response.email).toBeDefined();
      expect(response.email?.id).toBe(targetEmailId);
      expect(response.email?.read).toBe(true); // Check if it was marked as read

      // Verify it's marked as read in the list (if the mock directly modifies the list)
      const updatedEmails = await emailSkills.listRecentEmails(); // Re-fetch to see if change persisted
      const updatedEmail = updatedEmails.find(e => e.id === targetEmailId);
      expect(updatedEmail?.read).toBe(true);
    });

    it('should return a failure response if email is not found', async () => {
      const response = await emailSkills.readEmail('nonexistent-id');
      expect(response.success).toBe(false);
      expect(response.email).toBeUndefined();
      expect(response.message).toContain('Email with ID nonexistent-id not found.');
    });
  });

  describe('sendEmail', () => {
    it('should return a success response for valid email details', async () => {
      const emailDetails: emailSkills.EmailDetails = {
        to: 'test@example.com',
        subject: 'Test Subject',
        body: 'Test email body',
      };
      const response = await emailSkills.sendEmail(emailDetails);
      expect(response.success).toBe(true);
      expect(response.emailId).toBeDefined();
      expect(response.message).toContain('Email sent successfully (mock).');
    });

    it('should return a failure response if required details are missing', async () => {
      const emailDetails: Partial<emailSkills.EmailDetails> = { to: 'test@example.com' };
      // Type assertion needed because the function expects full EmailDetails, but we're testing partial input
      const response = await emailSkills.sendEmail(emailDetails as emailSkills.EmailDetails);
      expect(response.success).toBe(false);
      expect(response.emailId).toBeUndefined();
      expect(response.message).toContain('Missing required email details (to, subject, body).');
    });
  });
});
