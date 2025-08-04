import { Email, SendEmailResponse, ReadEmailResponse, GmailMessagePart, SkillResponse, SkillError } from '../types';
import { google, gmail_v1 } from 'googleapis';
import { Credentials as OAuth2Token } from 'google-auth-library';
import { logger } from '../../_utils/logger';
import { executeGraphQLQuery, executeGraphQLMutation } from '../_libs/graphqlClient';
import { ATOM_GOOGLE_CALENDAR_CLIENT_ID, ATOM_GOOGLE_CALENDAR_CLIENT_SECRET } from '../_libs/constants';

const GMAIL_SERVICE_NAME = 'google_calendar'; // Using the same service name as calendar for now

interface UserTokenRecord {
  access_token: string;
  refresh_token?: string | null;
  expiry_date?: string | null;
  scope?: string | null;
  token_type?: string | null;
}

async function getStoredUserTokens(userId: string): Promise<SkillResponse<OAuth2Token>> {
  const query = `
    query GetUserToken($userId: String!, $serviceName: String!) {
      user_tokens(
        where: { user_id: { _eq: $userId }, service_name: { _eq: $serviceName } },
        order_by: { created_at: desc },
        limit: 1
      ) {
        access_token
        refresh_token
        expiry_date
        scope
        token_type
      }
    }
  `;
  const variables = { userId, serviceName: GMAIL_SERVICE_NAME };
  const operationName = 'GetUserToken';

  try {
    const response = await executeGraphQLQuery<{ user_tokens: UserTokenRecord[] }>(query, variables, operationName, userId);
    if (!response || !response.user_tokens || response.user_tokens.length === 0) {
      return { ok: false, error: { code: 'AUTH_NO_TOKENS_FOUND', message: 'No Gmail tokens found for the user.' } };
    }
    const tokenRecord = response.user_tokens[0];
    const oauth2Token: OAuth2Token = {
      access_token: tokenRecord.access_token,
      refresh_token: tokenRecord.refresh_token || null,
      expiry_date: tokenRecord.expiry_date ? new Date(tokenRecord.expiry_date).getTime() : null,
      scope: tokenRecord.scope || undefined,
      token_type: tokenRecord.token_type || null,
    };
    return { ok: true, data: oauth2Token };
  } catch (error: any) {
    return { ok: false, error: { code: 'TOKEN_FETCH_FAILED', message: 'Failed to retrieve Gmail tokens.', details: error.message } };
  }
}

async function saveUserTokens(userId: string, tokens: OAuth2Token): Promise<SkillResponse<void>> {
  const mutation = `
    mutation UpsertUserToken($objects: [user_tokens_insert_input!]!) {
      insert_user_tokens(
        objects: $objects,
        on_conflict: {
          constraint: user_tokens_user_id_service_name_key,
          update_columns: [access_token, refresh_token, expiry_date, scope, token_type, updated_at]
        }
      ) {
        affected_rows
      }
    }
  `;
  const tokenDataForDb = {
    user_id: userId,
    service_name: GMAIL_SERVICE_NAME,
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
    expiry_date: tokens.expiry_date ? new Date(tokens.expiry_date).toISOString() : null,
    scope: tokens.scope,
    token_type: tokens.token_type,
    updated_at: new Date().toISOString(),
  };
  const variables = { objects: [tokenDataForDb] };
  const operationName = 'UpsertUserToken';

  try {
    await executeGraphQLMutation(mutation, variables, operationName, userId);
    return { ok: true, data: undefined };
  } catch (error: any) {
    return { ok: false, error: { code: 'TOKEN_SAVE_FAILED', message: 'Failed to save Gmail tokens.', details: error.message } };
  }
}

async function getGmailClient(userId: string): Promise<gmail_v1.Gmail | null> {
  logger.debug(`[emailSkills] Attempting to get Gmail client for user ${userId}`);
  const tokenResponse = await getStoredUserTokens(userId);

  if (!tokenResponse.ok || !tokenResponse.data) {
    logger.error(`[emailSkills] No Gmail access token found for user ${userId}.`);
    return null;
  }
  const currentTokens = tokenResponse.data;

  const oauth2Client = new google.auth.OAuth2(
    ATOM_GOOGLE_CALENDAR_CLIENT_ID,
    ATOM_GOOGLE_CALENDAR_CLIENT_SECRET
  );
  oauth2Client.setCredentials(currentTokens);

  oauth2Client.on('tokens', async (newTokens) => {
    let tokensToSave: OAuth2Token = { ...currentTokens, ...newTokens };
    if (!newTokens.refresh_token && currentTokens.refresh_token) {
      tokensToSave.refresh_token = currentTokens.refresh_token;
    }
    await saveUserTokens(userId, tokensToSave);
  });

  return google.gmail({ version: 'v1', auth: oauth2Client });
}


export async function searchMyEmails(userId: string, searchQuery: string, limit: number = 10): Promise<Email[]> {
  logger.info(`[emailSkills] Searching emails for user ${userId} with query "${searchQuery}", limit ${limit}...`);

  const gmail = await getGmailClient(userId);
  if (!gmail) {
    logger.error("[emailSkills] Failed to get Gmail client, cannot search emails.");
    return [];
  }

  try {
    const response = await gmail.users.messages.list({
      userId: 'me',
      q: searchQuery,
      maxResults: limit,
      // To get more details in the list response itself to minimize individual `get` calls:
      // fields: "messages(id,threadId,snippet,payload/headers,internalDate),nextPageToken"
      // However, this might not always give enough, and 'snippet' from list is very short.
      // For consistency with original structure that implies more detail, we'll fetch individually.
    });

    const messages = response.data.messages;
    if (!messages || messages.length === 0) {
      logger.info(`[emailSkills] No messages found for query: "${searchQuery}"`);
      return [];
    }

    const emailDetailsPromises = messages.map(async (msg) => {
      if (!msg.id) return null;
      try {
        const msgDetails = await gmail.users.messages.get({
          userId: 'me',
          id: msg.id,
          format: 'metadata',
          fields: 'id,threadId,snippet,payload/headers,internalDate,labelIds',
        });

        if (!msgDetails.data) return null;
        const headers = msgDetails.data.payload?.headers || [];
        const subject = headers.find(h => h.name?.toLowerCase() === 'subject')?.value || 'No Subject';
        const from = headers.find(h => h.name?.toLowerCase() === 'from')?.value || 'N/A';
        const dateHeader = headers.find(h => h.name?.toLowerCase() === 'date')?.value;

        const timestamp = msgDetails.data.internalDate
          ? new Date(parseInt(msgDetails.data.internalDate, 10)).toISOString()
          : (dateHeader ? new Date(dateHeader).toISOString() : new Date().toISOString());

        const isUnread = msgDetails.data.labelIds?.includes('UNREAD') || false;

        return {
          id: msgDetails.data.id!,
          threadId: msgDetails.data.threadId || undefined,
          sender: from,
          recipient: 'me',
          subject: subject,
          body: msgDetails.data.snippet || '',
          timestamp: timestamp,
          read: !isUnread,
        } as Email;
      } catch (err) {
        logger.error(`[emailSkills] Error fetching details for message ID ${msg.id}:`, err);
        return null;
      }
    });

    const emails = (await Promise.all(emailDetailsPromises)).filter(email => email !== null) as Email[];
    logger.info(`[emailSkills] Successfully fetched ${emails.length} email details for query "${searchQuery}".`);
    return emails;

  } catch (error: any) {
    logger.error(`[emailSkills] Error searching Gmail for user ${userId}, query "${searchQuery}":`, error);
    if (error.code === 401 || error.code === 403) {
        logger.error(`[emailSkills] Gmail API authentication/authorization error: ${error.message}`);
    }
    return [];
  }
}

// Helper to find and decode text/plain or text/html body from Gmail payload
function extractReadableBody(part: gmail_v1.Schema$MessagePart | undefined, preferredType: 'text/plain' | 'text/html' = 'text/plain'): string | null {
    if (!part) return null;

    let foundHtmlBody: string | null = null;

    // If this part is the preferred type
    if (part.mimeType === preferredType && part.body?.data) {
        const decodedBody = Buffer.from(part.body.data, 'base64url').toString('utf8');
        if (preferredType === 'text/html') {
            // Basic HTML stripping if we are forced to use HTML.
            // A library would be much better for this.
            return decodedBody
                .replace(/<style[^>]*>.*?<\/style>/gs, '') // Remove style blocks
                .replace(/<script[^>]*>.*?<\/script>/gs, '') // Remove script blocks
                .replace(/<[^>]+>/g, ' ') // Remove all other tags, replace with space
                .replace(/\s+/g, ' ') // Condense multiple spaces
                .trim();
        }
        return decodedBody;
    }

    // If this part is HTML and we are looking for plain (store it as fallback)
    if (part.mimeType === 'text/html' && part.body?.data) {
        const decodedHtml = Buffer.from(part.body.data, 'base64url').toString('utf8');
        // Basic HTML stripping
        foundHtmlBody = decodedHtml
            .replace(/<style[^>]*>.*?<\/style>/gs, '')
            .replace(/<script[^>]*>.*?<\/script>/gs, '')
            .replace(/<[^>]+>/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    }

    // If this part is multipart/alternative, search its subparts, prioritizing text/plain
    if (part.mimeType === 'multipart/alternative' && part.parts && part.parts.length > 0) {
        let plainTextVersion: string | null = null;
        let htmlVersion: string | null = null;
        for (const subPart of part.parts) {
            if (subPart.mimeType === 'text/plain' && subPart.body?.data) {
                plainTextVersion = Buffer.from(subPart.body.data, 'base64url').toString('utf8');
                break; // Found plain text, prefer this
            }
            if (subPart.mimeType === 'text/html' && subPart.body?.data) {
                 const decodedHtml = Buffer.from(subPart.body.data, 'base64url').toString('utf8');
                 htmlVersion = decodedHtml
                    .replace(/<style[^>]*>.*?<\/style>/gs, '')
                    .replace(/<script[^>]*>.*?<\/script>/gs, '')
                    .replace(/<[^>]+>/g, ' ')
                    .replace(/\s+/g, ' ')
                    .trim();
            }
        }
        if (plainTextVersion) return plainTextVersion;
        if (htmlVersion) return htmlVersion; // Fallback to stripped HTML
    }

    // For other multipart types (e.g., multipart/related, multipart/mixed) or if the desired type is not found at this level,
    // recursively search subparts.
    if (part.parts && part.parts.length > 0) {
        for (const subPart of part.parts) {
            // Try to find preferred type first
            const body = extractReadableBody(subPart, preferredType);
            if (body) return body;
        }
        // If preferred type not found in any subpart, try to find HTML as a fallback in subparts
        if (preferredType === 'text/plain' && foundHtmlBody) {
            return foundHtmlBody; // Return HTML found at current level if no plain text in subparts
        }
         // If still nothing, and preferred was text/plain, broaden search in subparts for text/html
        if (preferredType === 'text/plain') {
            for (const subPart of part.parts) {
                const htmlBody = extractReadableBody(subPart, 'text/html');
                if (htmlBody) return htmlBody; // Return the first stripped HTML found
            }
        }
    }

    // Fallback to HTML body found at this level if preferred was plain and nothing else found
    if (preferredType === 'text/plain' && foundHtmlBody) {
        return foundHtmlBody;
    }

    return null;
}


export async function readEmail(userId: string, emailId: string): Promise<ReadEmailResponse> {
  logger.info(`[emailSkills] Reading email with ID: ${emailId} for user ${userId}`);

  const gmail = await getGmailClient(userId);
  if (!gmail) {
    const errorMsg = "Failed to get Gmail client, cannot read email.";
    logger.error(`[emailSkills] ${errorMsg}`);
    return { success: false, message: errorMsg };
  }

  try {
    const response = await gmail.users.messages.get({
      userId: 'me',
      id: emailId,
      format: 'full', // Get full payload to extract body and headers
    });

    const fetchedEmail = response.data;
    if (!fetchedEmail || !fetchedEmail.id) {
      const errorMsg = `Email with ID ${emailId} not found or data incomplete.`;
      logger.warn(`[emailSkills] ${errorMsg}`);
      return { success: false, message: errorMsg };
    }

    const headers = fetchedEmail.payload?.headers || [];
    const subject = headers.find(h => h.name?.toLowerCase() === 'subject')?.value || 'No Subject';
    const from = headers.find(h => h.name?.toLowerCase() === 'from')?.value || 'N/A';
    const to = headers.find(h => h.name?.toLowerCase() === 'to')?.value || 'N/A'; // Can be multiple, join if needed
    const dateHeader = headers.find(h => h.name?.toLowerCase() === 'date')?.value;

    const timestamp = fetchedEmail.internalDate
      ? new Date(parseInt(fetchedEmail.internalDate, 10)).toISOString()
      : (dateHeader ? new Date(dateHeader).toISOString() : new Date().toISOString());

    const body = extractReadableBody(fetchedEmail.payload) || fetchedEmail.snippet || '';

    // Determine read status (simplified: if 'UNREAD' is not in labelIds, it's read)
    // This is a common way but might not be 100% accurate for all edge cases of "read" status.
    const isUnread = fetchedEmail.labelIds?.includes('UNREAD') || false;

    const email: Email = {
      id: fetchedEmail.id,
      threadId: fetchedEmail.threadId || undefined,
      sender: from,
      recipient: to,
      subject: subject,
      body: body,
      timestamp: timestamp,
      read: !isUnread,
    };
    logger.info(`[emailSkills] Successfully read email ID ${emailId}. Subject: ${subject}`);
    return { success: true, email };

  } catch (error: any) {
    logger.error(`[emailSkills] Error reading email ID ${emailId} for user ${userId}:`, error);
    if (error.code === 401 || error.code === 403) {
        return { success: false, message: `Gmail API authentication/authorization error: ${error.message}` };
    }
    if (error.code === 404) {
        return { success: false, message: `Email with ID ${emailId} not found.` };
    }
    return { success: false, message: (error as Error).message || `Failed to read email ${emailId}.` };
  }
}

// Removed callHasuraActionGraphQL and associated GQL constants as they are no longer used by searchMyEmails or readEmail.

import OpenAI from 'openai';
import { ChatCompletionMessageParam } from 'openai/resources/chat/completions';
import { ATOM_OPENAI_API_KEY, ATOM_NLU_MODEL_NAME } from '../_libs/constants'; // Reuse existing constants

// OpenAI client for information extraction
let openAIClientForExtraction: OpenAI | null = null;

function getExtractionOpenAIClient(): OpenAI {
  if (openAIClientForExtraction) {
    return openAIClientForExtraction;
  }
  if (!ATOM_OPENAI_API_KEY) {
    console.error('OpenAI API Key not configured for LLM Email Extractor.');
    throw new Error('OpenAI API Key not configured for LLM Email Extractor.');
  }
  openAIClientForExtraction = new OpenAI({ apiKey: ATOM_OPENAI_API_KEY });
  return openAIClientForExtraction;
}

const EXTRACTION_SYSTEM_PROMPT_TEMPLATE = `
You are an expert system designed to extract specific pieces of information from an email body.
The user will provide an email body and a list of information points they are looking for (keywords).
For each keyword, find the corresponding information in the email body.
Respond ONLY with a single, valid JSON object. Do not include any explanatory text before or after the JSON.
The JSON object should have keys corresponding to the user's original keywords.
The value for each key should be the extracted information as a string.
If a specific piece of information for a keyword is not found in the email body, the value for that key should be null.

Example:
User provides keywords: ["invoice number", "due date", "amount"]
Email body: "Attached is invoice INV-123 for $50.00, payment is due on 2024-01-15."
Your JSON response:
{
  "invoice number": "INV-123",
  "due date": "2024-01-15",
  "amount": "$50.00"
}

If keywords are ["sender name", "meeting time"] and email body is "From Bob, about the sync at 3 PM.",
Your JSON response:
{
  "sender name": "Bob",
  "meeting time": "3 PM"
}

If a keyword is "contract end date" and the email says "The agreement is valid until March 5th, 2025",
Your JSON response:
{
  "contract end date": "March 5th, 2025"
}

If information for a keyword is not found, use null for its value.
Example: Keywords: ["tracking number", "coupon code"], Email: "Your order has shipped."
Your JSON response:
{
  "tracking number": null,
  "coupon code": null
}

The keywords you need to extract information for are: {{KEYWORDS_JSON_ARRAY_STRING}}
Extract the information from the email body provided by the user.
`;


/**
 * Uses an LLM to extract specific pieces of information from an email body
 * based on a list of keywords or concepts.
 * @param emailBody The plain text body of the email.
 * @param infoKeywords An array of strings representing the concepts/keywords to search for.
 *                     (e.g., ["contract end date", "invoice number", "meeting link"])
 * @returns A Promise resolving to a record where keys are infoKeywords and values are the extracted strings (or null).
 */
export async function extractInformationFromEmailBody(
  emailBody: string,
  infoKeywords: string[]
): Promise<Record<string, string | null>> {
  if (!infoKeywords || infoKeywords.length === 0) {
    return {}; // No keywords to extract
  }

  console.log(`LLM Extractor: Attempting to extract information for keywords: [${infoKeywords.join(', ')}]`);
  const client = getExtractionOpenAIClient();

  // Prepare the prompt by injecting the specific keywords
  const keywordsJsonArrayString = JSON.stringify(infoKeywords);
  const systemPrompt = EXTRACTION_SYSTEM_PROMPT_TEMPLATE.replace("{{KEYWORDS_JSON_ARRAY_STRING}}", keywordsJsonArrayString);

  const messages: ChatCompletionMessageParam[] = [
    { role: 'system', content: systemPrompt },
    { role: 'user', content: `Email Body:\n---\n${emailBody}\n---` },
  ];

  try {
    const completion = await client.chat.completions.create({
      model: ATOM_NLU_MODEL_NAME, // Or a more capable model like "gpt-3.5-turbo" or "gpt-4"
      messages: messages,
      temperature: 0.1, // Low temperature for factual extraction
      response_format: { type: 'json_object' },
    });

    const llmResponse = completion.choices[0]?.message?.content;
    if (!llmResponse) {
      console.error('LLM Extractor: Received an empty response from AI.');
      throw new Error('LLM Extractor: Empty response from AI.');
    }

    console.log('LLM Extractor: Raw LLM JSON response:', llmResponse);
    const parsedResponse = JSON.parse(llmResponse);

    // Ensure all requested keywords are present in the response, with null if not found by LLM
    const result: Record<string, string | null> = {};
    for (const keyword of infoKeywords) {
      result[keyword] = parsedResponse.hasOwnProperty(keyword) ? parsedResponse[keyword] : null;
    }

    console.log('LLM Extractor: Parsed and reconciled extraction:', result);
    return result;

  } catch (error: any) {
    console.error('LLM Extractor: Error processing information extraction with OpenAI:', error.message);
    if (error instanceof SyntaxError) {
        console.error('LLM Extractor: Failed to parse JSON response from LLM.');
        throw new Error('LLM Extractor: Failed to parse response from AI for information extraction.');
    }
    if (error.response?.data?.error?.message) {
        throw new Error(`LLM Extractor: API Error - ${error.response.data.error.message}`);
    }
    // Fallback for infoKeywords if LLM fails catastrophically
    const fallbackResult: Record<string, string | null> = {};
    infoKeywords.forEach(kw => fallbackResult[kw] = null);
    return fallbackResult;
  }
}


export interface EmailDetails {
  to: string;
  subject: string;
  body: string;
  cc?: string[];
  bcc?: string[];
  htmlBody?: string; // Optional HTML body
}

import { SESClient, SendEmailCommand } from '@aws-sdk/client-ses';
import { ENV } from '../../_utils/env'; // Updated path
import { logger } from '../../_utils/logger'; // Updated path

let sesClient: SESClient | null = null;

function getSESClient(): SESClient {
  if (sesClient) {
    return sesClient;
  }
  if (!ENV.AWS_REGION || !ENV.AWS_ACCESS_KEY_ID || !ENV.AWS_SECRET_ACCESS_KEY) {
    logger.error('AWS SES environment variables not fully configured (AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY).');
    throw new Error('AWS SES environment variables not fully configured.');
  }
  sesClient = new SESClient({
    region: ENV.AWS_REGION,
    credentials: {
      accessKeyId: ENV.AWS_ACCESS_KEY_ID,
      secretAccessKey: ENV.AWS_SECRET_ACCESS_KEY,
    },
  });
  return sesClient;
}

export async function sendEmail(emailDetails: EmailDetails): Promise<SendEmailResponse> {
  logger.info('Attempting to send email via AWS SES with details:', emailDetails);

  if (!emailDetails.to || !emailDetails.subject || (!emailDetails.body && !emailDetails.htmlBody)) {
    logger.warn('Missing required email details (to, subject, and at least one of body or htmlBody).', emailDetails);
    return { success: false, message: 'Missing required email details (to, subject, and body/htmlBody).' };
  }
  if (!ENV.SES_SOURCE_EMAIL) {
    logger.error('SES_SOURCE_EMAIL environment variable is not set. Cannot send email.');
    return { success: false, message: 'Email sending is not configured (missing source email).' };
  }

  const client = getSESClient();

  const destination = {
    ToAddresses: [emailDetails.to],
    CcAddresses: emailDetails.cc || [],
    BccAddresses: emailDetails.bcc || [],
  };

  // Construct message body
  const messageBody = {} as any; // SES.Body
  if (emailDetails.body) {
    messageBody.Text = {
      Charset: 'UTF-8',
      Data: emailDetails.body,
    };
  }
  if (emailDetails.htmlBody) {
    messageBody.Html = {
      Charset: 'UTF-8',
      Data: emailDetails.htmlBody,
    };
  }


  const params = {
    Destination: destination,
    Message: {
      Body: messageBody,
      Subject: {
        Charset: 'UTF-8',
        Data: emailDetails.subject,
      },
    },
    Source: ENV.SES_SOURCE_EMAIL,
    // ReplyToAddresses: [ENV.SES_SOURCE_EMAIL], // Optional: Set reply-to if different
  };

  try {
    logger.info(`Sending email to ${emailDetails.to} via SES from ${ENV.SES_SOURCE_EMAIL}`);
    const command = new SendEmailCommand(params);

    const MAX_RETRIES = 3;
    let attempt = 0;
    let lastError: any = null;

    while (attempt < MAX_RETRIES) {
      try {
        const data = await client.send(command);
        logger.info(`Email sent successfully via SES on attempt ${attempt + 1}.`, { messageId: data.MessageId });
        return { success: true, emailId: data.MessageId, message: 'Email sent successfully via AWS SES.' };
      } catch (error: any) {
        lastError = error;
        logger.warn(`Attempt ${attempt + 1} to send email via SES failed. Retrying...`, {
          errorMessage: error.message,
          recipient: emailDetails.to,
          attempt: attempt + 1,
          maxRetries: MAX_RETRIES,
        });
        attempt++;
        if (attempt < MAX_RETRIES) {
          const delay = Math.pow(2, attempt -1) * 1000; // Exponential backoff: 1s, 2s
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }

    logger.error('Error sending email via AWS SES after multiple retries:', {
      errorMessage: lastError?.message,
      errorStack: lastError?.stack,
      errorDetails: lastError,
      recipient: emailDetails.to,
    });
    return { success: false, message: `Failed to send email via AWS SES after ${MAX_RETRIES} attempts: ${lastError?.message}` };
  } catch (error: any) {
    logger.error('Unhandled exception in sendEmail function:', {
        errorMessage: error.message,
        errorStack: error.stack,
        recipient: emailDetails.to,
    });
    return { success: false, message: `An unexpected error occurred: ${error.message}` };
  }
}
