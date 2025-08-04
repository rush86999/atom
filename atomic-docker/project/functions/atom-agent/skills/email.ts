import {
  Email,
  ReadEmailResponse,
  SendEmailResponse,
  EmailDetails,
} from '../../types';
import {
  listRecentEmails as listEmails,
  readEmail as read,
  sendEmail as send,
} from './emailSkills';
import { handleError } from '../../_utils/errorHandler';

export async function handleListEmails(entities: any): Promise<string> {
  try {
    let limit = 10; // Default limit
    if (entities?.limit) {
      if (typeof entities.limit === 'number') limit = entities.limit;
      else if (typeof entities.limit === 'string') {
        const parsedLimit = parseInt(entities.limit, 10);
        if (!isNaN(parsedLimit)) limit = parsedLimit;
      }
    }
    const emails: Email[] = await listEmails(limit);
    if (emails.length === 0) {
      return 'No recent emails found (via NLU).';
    } else {
      const emailList = emails
        .map(
          (email) =>
            `- (${email.read ? 'read' : 'unread'}) From: ${email.sender}, Subject: ${email.subject} (ID: ${email.id})`
        )
        .join('\n');
      return `Recent emails (via NLU):\n${emailList}`;
    }
  } catch (error: any) {
    return handleError(
      error,
      "Sorry, I couldn't fetch recent emails due to an error (NLU path)."
    );
  }
}

export async function handleReadEmail(entities: any): Promise<string> {
  try {
    const { email_id } = entities;
    if (!email_id || typeof email_id !== 'string') {
      return 'Email ID is required to read an email via NLU.';
    } else {
      const response: ReadEmailResponse = await read(email_id);
      if (response.success && response.email) {
        const email = response.email;
        return `Email (ID: ${email.id}):\nFrom: ${email.sender}\nTo: ${email.recipient}\nSubject: ${email.subject}\nDate: ${email.timestamp}\n\n${email.body}`;
      } else {
        return response.message || 'Could not read email via NLU.';
      }
    }
  } catch (error: any) {
    return handleError(
      error,
      "Sorry, I couldn't read the specified email due to an error (NLU path)."
    );
  }
}

export async function handleSendEmail(entities: any): Promise<string> {
  try {
    const { to, subject, body } = entities;
    if (!to || typeof to !== 'string') {
      return "Recipient 'to' address is required to send an email via NLU.";
    } else if (!subject || typeof subject !== 'string') {
      return 'Subject is required to send an email via NLU.';
    } else if (!body || typeof body !== 'string') {
      return 'Body is required to send an email via NLU.';
    } else {
      const emailDetails: EmailDetails = { to, subject, body };
      const response: SendEmailResponse = await send(emailDetails);
      if (response.success) {
        return `Email sent via NLU: ${response.message} (ID: ${response.emailId})`;
      } else {
        return `Failed to send email via NLU: ${response.message}`;
      }
    }
  } catch (error: any) {
    return handleError(
      error,
      "Sorry, I couldn't send the email due to an error (NLU path)."
    );
  }
}
