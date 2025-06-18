import { google, gmail_v1 } from 'googleapis';
import { Email, SendEmailResponse, ReadEmailResponse, EmailDetails } from '../types';
import {
  ATOM_GMAIL_CLIENT_ID,
  ATOM_GMAIL_CLIENT_SECRET,
} from '../_libs/constants';
import { getAtomGmailTokens, saveAtomGmailTokens } from '../_libs/token-utils';
import { Buffer } from 'buffer'; // For Base64 encoding

// Helper to extract header value
const getHeader = (headers: gmail_v1.Schema$MessagePartHeader[], name: string): string => {
  const header = headers.find(h => h.name === name);
  return header?.value || '';
};

// Helper to find and decode message body part
const getMessageBody = (parts?: gmail_v1.Schema$MessagePart[]): string => {
    if (!parts) return "";
    for (const part of parts) {
        if (part.mimeType === 'text/plain' && part.body?.data) {
            return Buffer.from(part.body.data, 'base64url').toString('utf8');
        }
        // Recurse for multipart messages (like multipart/alternative)
        if (part.parts) {
            const subPartBody = getMessageBody(part.parts);
            if (subPartBody) return subPartBody;
        }
    }
    // Fallback for simple messages where body is directly on payload
    // This might need more robust handling based on various email structures
    return "";
};


export async function listRecentEmails(userId: string, limit: number = 10): Promise<Email[]> {
  console.log(`Attempting to fetch up to ${limit} recent emails for userId: ${userId}...`);

  const retrievedTokens = await getAtomGmailTokens(userId);
  if (!retrievedTokens?.access_token) {
    console.error(`No valid Gmail tokens for userId: ${userId}. User needs to authenticate.`);
    return []; // Indicate auth error or no data
  }

  if (!ATOM_GMAIL_CLIENT_ID || !ATOM_GMAIL_CLIENT_SECRET) {
    console.error('Atom Agent Gmail client ID or secret not configured.');
    return [];
  }

  const oauth2Client = new google.auth.OAuth2(ATOM_GMAIL_CLIENT_ID, ATOM_GMAIL_CLIENT_SECRET);
  oauth2Client.setCredentials({
    access_token: retrievedTokens.access_token,
    refresh_token: retrievedTokens.refresh_token,
    expiry_date: retrievedTokens.expiry_date,
    scope: retrievedTokens.scope,
    token_type: retrievedTokens.token_type,
  });

  oauth2Client.on('tokens', async (newTokens) => {
    console.log('Gmail API tokens were refreshed for Atom Agent (listRecentEmails):', newTokens);
    let tokensToSave = { ...retrievedTokens, ...newTokens };
    if (!newTokens.refresh_token) {
      tokensToSave.refresh_token = retrievedTokens.refresh_token;
    }
    await saveAtomGmailTokens(userId, {
        access_token: tokensToSave.access_token!,
        refresh_token: tokensToSave.refresh_token,
        scope: tokensToSave.scope,
        token_type: tokensToSave.token_type,
        expiry_date: tokensToSave.expiry_date!,
      }, retrievedTokens.appEmail); // Pass existing appEmail as it's not part of refresh event
  });

  const gmail = google.gmail({ version: 'v1', auth: oauth2Client });

  try {
    const listResponse = await gmail.users.messages.list({
      userId: 'me',
      maxResults: limit,
      q: 'is:inbox', // Example query: fetch from inbox
    });

    if (!listResponse.data.messages || listResponse.data.messages.length === 0) {
      console.log('No messages found in inbox for Atom Agent.');
      return [];
    }

    const emails: Email[] = [];
    for (const messageMeta of listResponse.data.messages) {
      if (messageMeta.id) {
        const msgResponse = await gmail.users.messages.get({
          userId: 'me',
          id: messageMeta.id,
          format: 'metadata', // Get only headers for listing
          metadataHeaders: ['Subject', 'From', 'To', 'Date', 'Snippet'],
        });

        const headers = msgResponse.data.payload?.headers || [];
        emails.push({
          id: msgResponse.data.id || 'unknown_id',
          sender: getHeader(headers, 'From'),
          recipient: getHeader(headers, 'To'), // This might be 'me' or the user's email
          subject: getHeader(headers, 'Subject'),
          body: msgResponse.data.snippet || '', // Use snippet for list view
          timestamp: new Date(getHeader(headers, 'Date')).toISOString() || new Date(msgResponse.data.internalDate || Date.now()).toISOString(),
          read: !(msgResponse.data.labelIds?.includes('UNREAD') ?? false),
        });
      }
    }
    return emails;
  } catch (error: any) {
    console.error('Error listing Gmail messages for Atom Agent:', error.message);
     if (error.response?.data?.error === 'invalid_grant' || error.message.toLowerCase().includes('token has been expired or revoked')) {
        console.error('Gmail token error (invalid_grant or expired/revoked). User might need to re-authenticate for Atom Agent.');
    }
    return [];
  }
}

export async function readEmail(userId: string, emailId: string): Promise<ReadEmailResponse> {
  console.log(`Attempting to read emailId: ${emailId} for userId: ${userId}...`);

  const retrievedTokens = await getAtomGmailTokens(userId);
  if (!retrievedTokens?.access_token) {
    return { success: false, message: 'Authentication required. Please connect your Gmail account.' };
  }

  if (!ATOM_GMAIL_CLIENT_ID || !ATOM_GMAIL_CLIENT_SECRET) {
    console.error('Atom Agent Gmail client ID or secret not configured.');
    return { success: false, message: 'Server configuration error for email service.' };
  }

  const oauth2Client = new google.auth.OAuth2(ATOM_GMAIL_CLIENT_ID, ATOM_GMAIL_CLIENT_SECRET);
  oauth2Client.setCredentials({ access_token: retrievedTokens.access_token, refresh_token: retrievedTokens.refresh_token, expiry_date: retrievedTokens.expiry_date, scope: retrievedTokens.scope, token_type: retrievedTokens.token_type });

  oauth2Client.on('tokens', async (newTokens) => {
    console.log('Gmail API tokens were refreshed for Atom Agent (readEmail):', newTokens);
    let tokensToSave = { ...retrievedTokens, ...newTokens };
    if (!newTokens.refresh_token) tokensToSave.refresh_token = retrievedTokens.refresh_token;
    await saveAtomGmailTokens(userId, { access_token: tokensToSave.access_token!, refresh_token: tokensToSave.refresh_token, scope: tokensToSave.scope, token_type: tokensToSave.token_type, expiry_date: tokensToSave.expiry_date! }, retrievedTokens.appEmail);
  });

  const gmail = google.gmail({ version: 'v1', auth: oauth2Client });

  try {
    const msgResponse = await gmail.users.messages.get({
      userId: 'me',
      id: emailId,
      format: 'full', // Get full message details
    });

    if (!msgResponse.data) {
      return { success: false, message: `Email with ID ${emailId} not found.` };
    }

    const headers = msgResponse.data.payload?.headers || [];
    let body = "";
    if (msgResponse.data.payload?.parts) {
        body = getMessageBody(msgResponse.data.payload.parts);
    } else if (msgResponse.data.payload?.body?.data) {
        body = Buffer.from(msgResponse.data.payload.body.data, 'base64url').toString('utf8');
    }


    const email: Email = {
      id: msgResponse.data.id || emailId,
      sender: getHeader(headers, 'From'),
      recipient: getHeader(headers, 'To'),
      subject: getHeader(headers, 'Subject'),
      body: body,
      timestamp: new Date(getHeader(headers, 'Date')).toISOString() || new Date(msgResponse.data.internalDate || Date.now()).toISOString(),
      read: !(msgResponse.data.labelIds?.includes('UNREAD') ?? false),
    };

    // Optionally mark as read
    if (msgResponse.data.labelIds?.includes('UNREAD')) {
      await gmail.users.messages.modify({
        userId: 'me',
        id: emailId,
        requestBody: { removeLabelIds: ['UNREAD'] },
      });
      console.log(`Email ${emailId} marked as read for Atom Agent.`);
      email.read = true;
    }

    return { success: true, email };
  } catch (error: any) {
    console.error(`Error reading Gmail message ${emailId} for Atom Agent:`, error.message);
    return { success: false, message: `Failed to read email: ${error.message}` };
  }
}


export async function sendEmail(userId: string, emailDetails: EmailDetails): Promise<SendEmailResponse> {
  console.log(`Attempting to send email for userId: ${userId} with details:`, emailDetails);

  const retrievedTokens = await getAtomGmailTokens(userId);
  if (!retrievedTokens?.access_token) {
    return { success: false, message: 'Authentication required. Please connect your Gmail account.' };
  }
   if (!emailDetails.to || !emailDetails.subject || !emailDetails.body) {
    return { success: false, message: 'Missing required email details (to, subject, body).' };
  }
  if (!ATOM_GMAIL_CLIENT_ID || !ATOM_GMAIL_CLIENT_SECRET) {
    console.error('Atom Agent Gmail client ID or secret not configured.');
    return { success: false, message: 'Server configuration error for email service.' };
  }

  const oauth2Client = new google.auth.OAuth2(ATOM_GMAIL_CLIENT_ID, ATOM_GMAIL_CLIENT_SECRET);
  oauth2Client.setCredentials({ access_token: retrievedTokens.access_token, refresh_token: retrievedTokens.refresh_token, expiry_date: retrievedTokens.expiry_date, scope: retrievedTokens.scope, token_type: retrievedTokens.token_type });

  oauth2Client.on('tokens', async (newTokens) => {
    console.log('Gmail API tokens were refreshed for Atom Agent (sendEmail):', newTokens);
    let tokensToSave = { ...retrievedTokens, ...newTokens };
    if (!newTokens.refresh_token) tokensToSave.refresh_token = retrievedTokens.refresh_token;
    await saveAtomGmailTokens(userId, { access_token: tokensToSave.access_token!, refresh_token: tokensToSave.refresh_token, scope: tokensToSave.scope, token_type: tokensToSave.token_type, expiry_date: tokensToSave.expiry_date! }, retrievedTokens.appEmail);
  });

  const gmail = google.gmail({ version: 'v1', auth: oauth2Client });

  // TODO: Use the user's actual email (retrievedTokens.appEmail) as the "From" address.
  // For now, using "me" might work if the API allows it, or it might use the primary authenticated email.
  // Constructing a proper raw email is complex. For simplicity, we'll use a basic structure.
  const emailLines = [];
  emailLines.push(`From: ${retrievedTokens.appEmail || '"me" <unknown@example.com>'}`); // Use stored email or fallback
  emailLines.push(`To: ${emailDetails.to}`);
  if(emailDetails.cc) emailLines.push(`Cc: ${emailDetails.cc.join(',')}`);
  if(emailDetails.bcc) emailLines.push(`Bcc: ${emailDetails.bcc.join(',')}`);
  emailLines.push('Content-Type: text/html; charset=utf-8'); // Or text/plain
  emailLines.push('MIME-Version: 1.0');
  emailLines.push(`Subject: ${emailDetails.subject}`);
  emailLines.push('');
  emailLines.push(emailDetails.body);

  const rawEmail = Buffer.from(emailLines.join('\r\n')).toString('base64url');

  try {
    const sendResponse = await gmail.users.messages.send({
      userId: 'me',
      requestBody: {
        raw: rawEmail,
      },
    });

    if (sendResponse.data.id) {
      console.log('Email sent successfully by Atom Agent. Message ID:', sendResponse.data.id);
      return { success: true, emailId: sendResponse.data.id, message: 'Email sent successfully via Gmail.' };
    } else {
      console.error('Gmail send response did not include a message ID for Atom Agent.');
      return { success: false, message: 'Email send attempt made, but no confirmation ID received.' };
    }
  } catch (error: any) {
    console.error('Error sending Gmail message for Atom Agent:', error.message);
    return { success: false, message: `Failed to send email via Gmail: ${error.message}` };
  }
}
