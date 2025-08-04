import { google } from 'googleapis';
import { logger } from '../../_utils/logger';
import { executeGraphQLQuery, executeGraphQLMutation } from '../_libs/graphqlClient';
import { ATOM_GOOGLE_CALENDAR_CLIENT_ID, ATOM_GOOGLE_CALENDAR_CLIENT_SECRET } from '../_libs/constants';
const GMAIL_SERVICE_NAME = 'google_calendar'; // Using the same service name as calendar for now
async function getStoredUserTokens(userId) {
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
        const response = await executeGraphQLQuery(query, variables, operationName, userId);
        if (!response || !response.user_tokens || response.user_tokens.length === 0) {
            return { ok: false, error: { code: 'AUTH_NO_TOKENS_FOUND', message: 'No Gmail tokens found for the user.' } };
        }
        const tokenRecord = response.user_tokens[0];
        const oauth2Token = {
            access_token: tokenRecord.access_token,
            refresh_token: tokenRecord.refresh_token || null,
            expiry_date: tokenRecord.expiry_date ? new Date(tokenRecord.expiry_date).getTime() : null,
            scope: tokenRecord.scope || undefined,
            token_type: tokenRecord.token_type || null,
        };
        return { ok: true, data: oauth2Token };
    }
    catch (error) {
        return { ok: false, error: { code: 'TOKEN_FETCH_FAILED', message: 'Failed to retrieve Gmail tokens.', details: error.message } };
    }
}
async function saveUserTokens(userId, tokens) {
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
    }
    catch (error) {
        return { ok: false, error: { code: 'TOKEN_SAVE_FAILED', message: 'Failed to save Gmail tokens.', details: error.message } };
    }
}
async function getGmailClient(userId) {
    logger.debug(`[emailSkills] Attempting to get Gmail client for user ${userId}`);
    const tokenResponse = await getStoredUserTokens(userId);
    if (!tokenResponse.ok || !tokenResponse.data) {
        logger.error(`[emailSkills] No Gmail access token found for user ${userId}.`);
        return null;
    }
    const currentTokens = tokenResponse.data;
    const oauth2Client = new google.auth.OAuth2(ATOM_GOOGLE_CALENDAR_CLIENT_ID, ATOM_GOOGLE_CALENDAR_CLIENT_SECRET);
    oauth2Client.setCredentials(currentTokens);
    oauth2Client.on('tokens', async (newTokens) => {
        let tokensToSave = { ...currentTokens, ...newTokens };
        if (!newTokens.refresh_token && currentTokens.refresh_token) {
            tokensToSave.refresh_token = currentTokens.refresh_token;
        }
        await saveUserTokens(userId, tokensToSave);
    });
    return google.gmail({ version: 'v1', auth: oauth2Client });
}
export async function searchMyEmails(userId, searchQuery, limit = 10) {
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
            if (!msg.id)
                return null;
            try {
                const msgDetails = await gmail.users.messages.get({
                    userId: 'me',
                    id: msg.id,
                    format: 'metadata',
                    fields: 'id,threadId,snippet,payload/headers,internalDate,labelIds',
                });
                if (!msgDetails.data)
                    return null;
                const headers = msgDetails.data.payload?.headers || [];
                const subject = headers.find(h => h.name?.toLowerCase() === 'subject')?.value || 'No Subject';
                const from = headers.find(h => h.name?.toLowerCase() === 'from')?.value || 'N/A';
                const dateHeader = headers.find(h => h.name?.toLowerCase() === 'date')?.value;
                const timestamp = msgDetails.data.internalDate
                    ? new Date(parseInt(msgDetails.data.internalDate, 10)).toISOString()
                    : (dateHeader ? new Date(dateHeader).toISOString() : new Date().toISOString());
                const isUnread = msgDetails.data.labelIds?.includes('UNREAD') || false;
                return {
                    id: msgDetails.data.id,
                    threadId: msgDetails.data.threadId || undefined,
                    sender: from,
                    recipient: 'me',
                    subject: subject,
                    body: msgDetails.data.snippet || '',
                    timestamp: timestamp,
                    read: !isUnread,
                };
            }
            catch (err) {
                logger.error(`[emailSkills] Error fetching details for message ID ${msg.id}:`, err);
                return null;
            }
        });
        const emails = (await Promise.all(emailDetailsPromises)).filter(email => email !== null);
        logger.info(`[emailSkills] Successfully fetched ${emails.length} email details for query "${searchQuery}".`);
        return emails;
    }
    catch (error) {
        logger.error(`[emailSkills] Error searching Gmail for user ${userId}, query "${searchQuery}":`, error);
        if (error.code === 401 || error.code === 403) {
            logger.error(`[emailSkills] Gmail API authentication/authorization error: ${error.message}`);
        }
        return [];
    }
}
// Helper to find and decode text/plain or text/html body from Gmail payload
function extractReadableBody(part, preferredType = 'text/plain') {
    if (!part)
        return null;
    let foundHtmlBody = null;
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
        let plainTextVersion = null;
        let htmlVersion = null;
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
        if (plainTextVersion)
            return plainTextVersion;
        if (htmlVersion)
            return htmlVersion; // Fallback to stripped HTML
    }
    // For other multipart types (e.g., multipart/related, multipart/mixed) or if the desired type is not found at this level,
    // recursively search subparts.
    if (part.parts && part.parts.length > 0) {
        for (const subPart of part.parts) {
            // Try to find preferred type first
            const body = extractReadableBody(subPart, preferredType);
            if (body)
                return body;
        }
        // If preferred type not found in any subpart, try to find HTML as a fallback in subparts
        if (preferredType === 'text/plain' && foundHtmlBody) {
            return foundHtmlBody; // Return HTML found at current level if no plain text in subparts
        }
        // If still nothing, and preferred was text/plain, broaden search in subparts for text/html
        if (preferredType === 'text/plain') {
            for (const subPart of part.parts) {
                const htmlBody = extractReadableBody(subPart, 'text/html');
                if (htmlBody)
                    return htmlBody; // Return the first stripped HTML found
            }
        }
    }
    // Fallback to HTML body found at this level if preferred was plain and nothing else found
    if (preferredType === 'text/plain' && foundHtmlBody) {
        return foundHtmlBody;
    }
    return null;
}
export async function readEmail(userId, emailId) {
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
        const email = {
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
    }
    catch (error) {
        logger.error(`[emailSkills] Error reading email ID ${emailId} for user ${userId}:`, error);
        if (error.code === 401 || error.code === 403) {
            return { success: false, message: `Gmail API authentication/authorization error: ${error.message}` };
        }
        if (error.code === 404) {
            return { success: false, message: `Email with ID ${emailId} not found.` };
        }
        return { success: false, message: error.message || `Failed to read email ${emailId}.` };
    }
}
// Removed callHasuraActionGraphQL and associated GQL constants as they are no longer used by searchMyEmails or readEmail.
import OpenAI from 'openai';
import { ATOM_OPENAI_API_KEY, ATOM_NLU_MODEL_NAME } from '../_libs/constants'; // Reuse existing constants
// OpenAI client for information extraction
let openAIClientForExtraction = null;
function getExtractionOpenAIClient() {
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
export async function extractInformationFromEmailBody(emailBody, infoKeywords) {
    if (!infoKeywords || infoKeywords.length === 0) {
        return {}; // No keywords to extract
    }
    console.log(`LLM Extractor: Attempting to extract information for keywords: [${infoKeywords.join(', ')}]`);
    const client = getExtractionOpenAIClient();
    // Prepare the prompt by injecting the specific keywords
    const keywordsJsonArrayString = JSON.stringify(infoKeywords);
    const systemPrompt = EXTRACTION_SYSTEM_PROMPT_TEMPLATE.replace("{{KEYWORDS_JSON_ARRAY_STRING}}", keywordsJsonArrayString);
    const messages = [
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
        const result = {};
        for (const keyword of infoKeywords) {
            result[keyword] = parsedResponse.hasOwnProperty(keyword) ? parsedResponse[keyword] : null;
        }
        console.log('LLM Extractor: Parsed and reconciled extraction:', result);
        return result;
    }
    catch (error) {
        console.error('LLM Extractor: Error processing information extraction with OpenAI:', error.message);
        if (error instanceof SyntaxError) {
            console.error('LLM Extractor: Failed to parse JSON response from LLM.');
            throw new Error('LLM Extractor: Failed to parse response from AI for information extraction.');
        }
        if (error.response?.data?.error?.message) {
            throw new Error(`LLM Extractor: API Error - ${error.response.data.error.message}`);
        }
        // Fallback for infoKeywords if LLM fails catastrophically
        const fallbackResult = {};
        infoKeywords.forEach(kw => fallbackResult[kw] = null);
        return fallbackResult;
    }
}
import { SESClient, SendEmailCommand } from '@aws-sdk/client-ses';
import { ENV } from '../../_utils/env'; // Updated path
let sesClient = null;
function getSESClient() {
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
export async function sendEmail(emailDetails) {
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
    const messageBody = {}; // SES.Body
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
        let lastError = null;
        while (attempt < MAX_RETRIES) {
            try {
                const data = await client.send(command);
                logger.info(`Email sent successfully via SES on attempt ${attempt + 1}.`, { messageId: data.MessageId });
                return { success: true, emailId: data.MessageId, message: 'Email sent successfully via AWS SES.' };
            }
            catch (error) {
                lastError = error;
                logger.warn(`Attempt ${attempt + 1} to send email via SES failed. Retrying...`, {
                    errorMessage: error.message,
                    recipient: emailDetails.to,
                    attempt: attempt + 1,
                    maxRetries: MAX_RETRIES,
                });
                attempt++;
                if (attempt < MAX_RETRIES) {
                    const delay = Math.pow(2, attempt - 1) * 1000; // Exponential backoff: 1s, 2s
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
    }
    finally {
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZW1haWxTa2lsbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJlbWFpbFNraWxscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFDQSxPQUFPLEVBQUUsTUFBTSxFQUFZLE1BQU0sWUFBWSxDQUFDO0FBRTlDLE9BQU8sRUFBRSxNQUFNLEVBQUUsTUFBTSxxQkFBcUIsQ0FBQztBQUM3QyxPQUFPLEVBQUUsbUJBQW1CLEVBQUUsc0JBQXNCLEVBQUUsTUFBTSx3QkFBd0IsQ0FBQztBQUNyRixPQUFPLEVBQUUsOEJBQThCLEVBQUUsa0NBQWtDLEVBQUUsTUFBTSxvQkFBb0IsQ0FBQztBQUV4RyxNQUFNLGtCQUFrQixHQUFHLGlCQUFpQixDQUFDLENBQUMsa0RBQWtEO0FBVWhHLEtBQUssVUFBVSxtQkFBbUIsQ0FBQyxNQUFjO0lBQy9DLE1BQU0sS0FBSyxHQUFHOzs7Ozs7Ozs7Ozs7OztHQWNiLENBQUM7SUFDRixNQUFNLFNBQVMsR0FBRyxFQUFFLE1BQU0sRUFBRSxXQUFXLEVBQUUsa0JBQWtCLEVBQUUsQ0FBQztJQUM5RCxNQUFNLGFBQWEsR0FBRyxjQUFjLENBQUM7SUFFckMsSUFBSSxDQUFDO1FBQ0gsTUFBTSxRQUFRLEdBQUcsTUFBTSxtQkFBbUIsQ0FBcUMsS0FBSyxFQUFFLFNBQVMsRUFBRSxhQUFhLEVBQUUsTUFBTSxDQUFDLENBQUM7UUFDeEgsSUFBSSxDQUFDLFFBQVEsSUFBSSxDQUFDLFFBQVEsQ0FBQyxXQUFXLElBQUksUUFBUSxDQUFDLFdBQVcsQ0FBQyxNQUFNLEtBQUssQ0FBQyxFQUFFLENBQUM7WUFDNUUsT0FBTyxFQUFFLEVBQUUsRUFBRSxLQUFLLEVBQUUsS0FBSyxFQUFFLEVBQUUsSUFBSSxFQUFFLHNCQUFzQixFQUFFLE9BQU8sRUFBRSxxQ0FBcUMsRUFBRSxFQUFFLENBQUM7UUFDaEgsQ0FBQztRQUNELE1BQU0sV0FBVyxHQUFHLFFBQVEsQ0FBQyxXQUFXLENBQUMsQ0FBQyxDQUFDLENBQUM7UUFDNUMsTUFBTSxXQUFX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QUMzQixDQUFDLENBQUM7UUFDSCxPQUFPLEVBQUUsT0FBTyxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsMENBQTBDLFdBQVcsY0FBYyxTQUFTLEVBQUUsT0FBTyxFQUFFLEVBQUUsQ0FBQztJQUM5SCxDQUFDO1lBQ0gsQ0FBQztJQUFELENBQUMsQUFERTtBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBFbWFpbCwgU2VuZEVtYWlsUmVzcG9uc2UsIFJlYWRFbWFpbFJlc3BvbnNlLCBHbWFpbE1lc3NhZ2VQYXJ0LCBTa2lsbFJlc3BvbnNlLCBTa2lsbEVycm9yIH0gZnJvbSAnLi4vdHlwZXMnO1xuaW1wb3J0IHsgZ29vZ2xlLCBnbWFpbF92MSB9IGZyb20gJ2dvb2dsZWFwaXMnO1xuaW1wb3J0IHsgQ3JlZGVudGlhbHMgYXMgT0F1dGgyVG9rZW4gfSBmcm9tICdnb29nbGUtYXV0aC1saWJyYXJ5JztcbmltcG9ydCB7IGxvZ2dlciB9IGZyb20gJy4uLy4uL191dGlscy9sb2dnZXInO1xuaW1wb3J0IHsgZXhlY3V0ZUdyYXBoUUxRdWVyeSwgZXhlY3V0ZUdyYXBoUUxNdXRhdGlvbiB9IGZyb20gJy4uL19saWJzL2dyYXBocWxDbGllbnQnO1xuaW1wb3J0IHsgQVRPTV9HT09HTEVfQ0FMRU5EQVJfQ0xJRU5UX0lELCBBVE9NX0dPT0dMRV9DQUxFTkRBUl9DTElFTlRfU0VDUkVUIH0gZnJvbSAnLi4vX2xpYnMvY29uc3RhbnRzJztcblxuY29uc3QgR01BSUxfU0VSVklDRV9OQU1FID0gJ2dvb2dsZV9jYWxlbmRhcic7IC8vIFVzaW5nIHRoZSBzYW1lIHNlcnZpY2UgbmFtZSBhcyBjYWxlbmRhciBmb3Igbm93XG5cbmludGVyZmFjZSBVc2VyVG9rZW5SZWNvcmQge1xuICBhY2Nlc3NfdG9rZW46IHN0cmluZztcbiAgcmVmcmVzaF90b2tlbj86IHN0cmluZyB8IG51bGw7XG4gIGV4cGlyeV9kYXRlPzogc3RyaW5nIHwgbnVsbDtcbiAgc2NvcGU/OiBzdHJpbmcgfCBudWxsO1xuICB0b2tlbl90eXBlPzogc3RyaW5nIHwgbnVsbDtcbn1cblxuYXN5bmMgZnVuY3Rpb24gZ2V0U3RvcmVkVXNlclRva2Vucyh1c2VySWQ6IHN0cmluZyk6IFByb21pc2U8U2tpbGxSZXNwb25zZTxPQXV0aDJUb2tlbj4+IHtcbiAgY29uc3QgcXVlcnkgPSBgXG4gICAgcXVlcnkgR2V0VXNlclRva2VuKCR1c2VySWQ6IFN0cmluZyEsICRzZXJ2aWNlTmFtZTogU3RyaW5nISkge1xuICAgICAgdXNlcl90b2tlbnMoXG4gICAgICAgIHdoZXJlOiB7IHVzZXJfaWQ6IHsgX2VxOiAkdXNlcklkIH0sIHNlcnZpY2VfbmFtZTogeyBfZXE6ICRzZXJ2aWNlTmFtZSB9IH0sXG4gICAgICAgIG9yZGVyX2J5OiB7IGNyZWF0ZWRfYXQ6IGRlc2MgfSxcbiAgICAgICAgbGltaXQ6IDFcbiAgICAgICkge1xuICAgICAgICBhY2Nlc3NfdG9rZW5cbiAgICAgICAgcmVmcmVzaF90b2tlblxuICAgICAgICBleHBpcnlfZGF0ZVxuICAgICAgICBzY29wZVxuICAgICAgICB0b2tlbl90eXBlXG4gICAgICB9XG4gICAgfVxuICBgO1xuICBjb25zdCB2YXJpYWJsZXMgPSB7IHVzZXJJZCwgc2VydmljZU5hbWU6IEdNQUlMX1NFUlZJQ0VfTkFNRSB9O1xuICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0dldFVzZXJUb2tlbic7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGV4ZWN1dGVHcmFwaFFMUXVlcnk8eyB1c2VyX3Rva2VuczogVXNlclRva2VuUmVjb3JkW10gfT4ocXVlcnksIHZhcmlhYmxlcywgb3BlcmF0aW9uTmFtZSwgdXNlcklkKTtcbiAgICBpZiAoIXJlc3BvbnNlIHx8ICFyZXNwb25zZS51c2VyX3Rva2VucyB8fCByZXNwb25zZS51c2VyX3Rva2Vucy5sZW5ndGggPT09IDApIHtcbiAgICAgIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ0FVVEhfTk9fVE9LRU5TX0ZPVU5EJywgbWVzc2FnZTogJ05vIEdtYWlsIHRva2VucyBmb3VuZCBmb3IgdGhlIHVzZXIuJyB9IH07XG4gICAgfVxuICAgIGNvbnN0IHRva2VuUmVjb3JkID0gcmVzcG9uc2UudXNlcl90b2tlbnNbMF07XG4gICAgY29uc3Qgb2F1dGgyVG9rZW46IE9BdXRoMlRva2VuID0ge1xuICAgICAgYWNjZXNzX3Rva2VuOiB0b2tlblJlY29yZC5hY2Nlc3NfdG9rZW4sXG4gICAgICByZWZyZXNoX3Rva2VuOiB0b2tlblJlY29yZC5yZWZyZXNoX3Rva2VuIHx8IG51bGwsXG4gICAgICBleHBpcnlfZGF0ZTogdG9rZW5SZWNvcmQuZXhwaXJ5X2RhdGUgPyBuZXcgRGF0ZSh0b2tlblJlY29yZC5leHBpcnlfZGF0ZSkuZ2V0VGltZSgpIDogbnVsbCxcbiAgICAgIHNjb3BlOiB0b2tlblJlY29yZC5zY29wZSB8fCB1bmRlZmluZWQsXG4gICAgICB0b2tlbl90eXBlOiB0b2tlblJlY29yZC50b2tlbl90eXBlIHx8IG51bGwsXG4gICAgfTtcbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogb2F1dGgyVG9rZW4gfTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIHJldHVybiB7IG9rOiBmYWxzZSwgZXJyb3I6IHsgY29kZTogJ1RPS0VOX0ZFVENIX0ZBSUxFRCcsIG1lc3NhZ2U6ICdGYWlsZWQgdG8gcmV0cmlldmUgR21haWwgdG9rZW5zLicsIGRldGFpbHM6IGVycm9yLm1lc3NhZ2UgfSB9O1xuICB9XG59XG5cbmFzeW5jIGZ1bmN0aW9uIHNhdmVVc2VyVG9rZW5zKHVzZXJJZDogc3RyaW5nLCB0b2tlbnM6IE9BdXRoMlRva2VuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPHZvaWQ+PiB7XG4gIGNvbnN0IG11dGF0aW9uID0gYFxuICAgIG11dGF0aW9uIFVwc2VydFVzZXJUb2tlbigkb2JqZWN0czogW3VzZXJfdG9rZW5zX2luc2VydF9pbnB1dCFdISkge1xuICAgICAgaW5zZXJ0X3VzZXJfdG9rZW5zKFxuICAgICAgICBvYmplY3RzOiAkb2JqZWN0cyxcbiAgICAgICAgb25fY29uZmxpY3Q6IHtcbiAgICAgICAgICBjb25zdHJhaW50OiB1c2VyX3Rva2Vuc191c2VyX2lkX3NlcnZpY2VfbmFtZV9rZXksXG4gICAgICAgICAgdXBkYXRlX2NvbHVtbnM6IFthY2Nlc3NfdG9rZW4sIHJlZnJlc2hfdG9rZW4sIGV4cGlyeV9kYXRlLCBzY29wZSwgdG9rZW5fdHlwZSwgdXBkYXRlZF9hdF1cbiAgICAgICAgfVxuICAgICAgKSB7XG4gICAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICAgIH1cbiAgICB9XG4gIGA7XG4gIGNvbnN0IHRva2VuRGF0YUZvckRiID0ge1xuICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICBzZXJ2aWNlX25hbWU6IEdNQUlMX1NFUlZJQ0VfTkFNRSxcbiAgICBhY2Nlc3NfdG9rZW46IHRva2Vucy5hY2Nlc3NfdG9rZW4sXG4gICAgcmVmcmVzaF90b2tlbjogdG9rZW5zLnJlZnJlc2hfdG9rZW4sXG4gICAgZXhwaXJ5X2RhdGU6IHRva2Vucy5leHBpcnlfZGF0ZSA/IG5ldyBEYXRlKHRva2Vucy5leHBpcnlfZGF0ZSkudG9JU09TdHJpbmcoKSA6IG51bGwsXG4gICAgc2NvcGU6IHRva2Vucy5zY29wZSxcbiAgICB0b2tlbl90eXBlOiB0b2tlbnMudG9rZW5fdHlwZSxcbiAgICB1cGRhdGVkX2F0OiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXG4gIH07XG4gIGNvbnN0IHZhcmlhYmxlcyA9IHsgb2JqZWN0czogW3Rva2VuRGF0YUZvckRiXSB9O1xuICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ1Vwc2VydFVzZXJUb2tlbic7XG5cbiAgdHJ5IHtcbiAgICBhd2FpdCBleGVjdXRlR3JhcGhRTE11dGF0aW9uKG11dGF0aW9uLCB2YXJpYWJsZXMsIG9wZXJhdGlvbk5hbWUsIHVzZXJJZCk7XG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHVuZGVmaW5lZCB9O1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgcmV0dXJuIHsgb2s6IGZhbHNlLCBlcnJvcjogeyBjb2RlOiAnVE9LRU5fU0FWRV9GQUlMRUQnLCBtZXNzYWdlOiAnRmFpbGVkIHRvIHNhdmUgR21haWwgdG9rZW5zLicsIGRldGFpbHM6IGVycm9yLm1lc3NhZ2UgfSB9O1xuICB9XG59XG5cbmFzeW5jIGZ1bmN0aW9uIGdldEdtYWlsQ2xpZW50KHVzZXJJZDogc3RyaW5nKTogUHJvbWlzZTxnbWFpbF92MS5HbWFpbCB8IG51bGw+IHtcbiAgbG9nZ2VyLmRlYnVnKGBbZW1haWxTa2lsbHNdIEF0dGVtcHRpbmcgdG8gZ2V0IEdtYWlsIGNsaWVudCBmb3IgdXNlciAke3VzZXJJZH1gKTtcbiAgY29uc3QgdG9rZW5SZXNwb25zZSA9IGF3YWl0IGdldFN0b3JlZFVzZXJUb2tlbnModXNlcklkKTtcblxuICBpZiAoIXRva2VuUmVzcG9uc2Uub2sgfHwgIXRva2VuUmVzcG9uc2UuZGF0YSkge1xuICAgIGxvZ2dlci5lcnJvcihgW2VtYWlsU2tpbGxzXSBObyBHbWFpbCBhY2Nlc3MgdG9rZW4gZm91bmQgZm9yIHVzZXIgJHt1c2VySWR9LmApO1xuICAgIHJldHVybiBudWxsO1xuICB9XG4gIGNvbnN0IGN1cnJlbnRUb2tlbnMgPSB0b2tlblJlc3BvbnNlLmRhdGE7XG5cbiAgY29uc3Qgb2F1dGgyQ2xpZW50ID0gbmV3IGdvb2dsZS5hdXRoLk9BdXRoMihcbiAgICBBVE9NX0dPT0dMRV9DQUxFTkRBUl9DTElFTlRfSUQsXG4gICAgQVRPTV9HT09HTEVfQ0FMRU5EQVJfQ0xJRU5UX1NFQ1JFVFxuICApO1xuICBvYXV0aDJDbGllbnQuc2V0Q3JlZGVudGlhbHMoY3VycmVudFRva2Vucyk7XG5cbiAgb2F1dGgyQ2xpZW50Lm9uKCd0b2tlbnMnLCBhc3luYyAobmV3VG9rZW5zKSA9PiB7XG4gICAgbGV0IHRva2Vuc1RvU2F2ZTogT0F1dGgyVG9rZW4gPSB7IC4uLmN1cnJlbnRUb2tlbnMsIC4uLm5ld1Rva2VucyB9O1xuICAgIGlmICghbmV3VG9rZW5zLnJlZnJlc2hfdG9rZW4gJiYgY3VycmVudFRva2Vucy5yZWZyZXNoX3Rva2VuKSB7XG4gICAgICB0b2tlbnNUb1NhdmUucmVmcmVzaF90b2tlbiA9IGN1cnJlbnRUb2tlbnMucmVmcmVzaF90b2tlbjtcbiAgICB9XG4gICAgYXdhaXQgc2F2ZVVzZXJUb2tlbnModXNlcklkLCB0b2tlbnNUb1NhdmUpO1xuICB9KTtcblxuICByZXR1cm4gZ29vZ2xlLmdtYWlsKHsgdmVyc2lvbjogJ3YxJywgYXV0aDogb2F1dGgyQ2xpZW50IH0pO1xufVxuXG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBzZWFyY2hNeUVtYWlscyh1c2VySWQ6IHN0cmluZywgc2VhcmNoUXVlcnk6IHN0cmluZywgbGltaXQ6IG51bWJlciA9IDEwKTogUHJvbWlzZTxFbWFpbFtdPiB7XG4gIGxvZ2dlci5pbmZvKGBbZW1haWxTa2lsbHNdIFNlYXJjaGluZyBlbWFpbHMgZm9yIHVzZXIgJHt1c2VySWR9IHdpdGggcXVlcnkgXCIke3NlYXJjaFF1ZXJ5fVwiLCBsaW1pdCAke2xpbWl0fS4uLmApO1xuXG4gIGNvbnN0IGdtYWlsID0gYXdhaXQgZ2V0R21haWxDbGllbnQodXNlcklkKTtcbiAgaWYgKCFnbWFpbCkge1xuICAgIGxvZ2dlci5lcnJvcihcIltlbWFpbFNraWxsc10gRmFpbGVkIHRvIGdldCBHbWFpbCBjbGllbnQsIGNhbm5vdCBzZWFyY2ggZW1haWxzLlwiKTtcbiAgICByZXR1cm4gW107XG4gIH1cblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZ21haWwudXNlcnMubWVzc2FnZXMubGlzdCh7XG4gICAgICB1c2VySWQ6ICdtZScsXG4gICAgICBxOiBzZWFyY2hRdWVyeSxcbiAgICAgIG1heFJlc3VsdHM6IGxpbWl0LFxuICAgICAgLy8gVG8gZ2V0IG1vcmUgZGV0YWlscyBpbiB0aGUgbGlzdCByZXNwb25zZSBpdHNlbGYgdG8gbWluaW1pemUgaW5kaXZpZHVhbCBgZ2V0YCBjYWxsczpcbiAgICAgIC8vIGZpZWxkczogXCJtZXNzYWdlcyhpZCx0aHJlYWRJZCxzbmlwcGV0LHBheWxvYWQvaGVhZGVycyxpbnRlcm5hbERhdGUpLG5leHRQYWdlVG9rZW5cIlxuICAgICAgLy8gSG93ZXZlciwgdGhpcyBtaWdodCBub3QgYWx3YXlzIGdpdmUgZW5vdWdoLCBhbmQgJ3NuaXBwZXQnIGZyb20gbGlzdCBpcyB2ZXJ5IHNob3J0LlxuICAgICAgLy8gRm9yIGNvbnNpc3RlbmN5IHdpdGggb3JpZ2luYWwgc3RydWN0dXJlIHRoYXQgaW1wbGllcyBtb3JlIGRldGFpbCwgd2UnbGwgZmV0Y2ggaW5kaXZpZHVhbGx5LlxuICAgIH0pO1xuXG4gICAgY29uc3QgbWVzc2FnZXMgPSByZXNwb25zZS5kYXRhLm1lc3NhZ2VzO1xuICAgIGlmICghbWVzc2FnZXMgfHwgbWVzc2FnZXMubGVuZ3RoID09PSAwKSB7XG4gICAgICBsb2dnZXIuaW5mbyhgW2VtYWlsU2tpbGxzXSBObyBtZXNzYWdlcyBmb3VuZCBmb3IgcXVlcnk6IFwiJHtzZWFyY2hRdWVyeX1cImApO1xuICAgICAgcmV0dXJuIFtdO1xuICAgIH1cblxuICAgIGNvbnN0IGVtYWlsRGV0YWlsc1Byb21pc2VzID0gbWVzc2FnZXMubWFwKGFzeW5jIChtc2cpID0+IHtcbiAgICAgIGlmICghbXNnLmlkKSByZXR1cm4gbnVsbDtcbiAgICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IG1zZ0RldGFpbHMgPSBhd2FpdCBnbWFpbC51c2Vycy5tZXNzYWdlcy5nZXQoe1xuICAgICAgICAgIHVzZXJJZDogJ21lJyxcbiAgICAgICAgICBpZDogbXNnLmlkLFxuICAgICAgICAgIGZvcm1hdDogJ21ldGFkYXRhJyxcbiAgICAgICAgICBmaWVsZHM6ICdpZCx0aHJlYWRJZCxzbmlwcGV0LHBheWxvYWQvaGVhZGVycyxpbnRlcm5hbERhdGUsbGFiZWxJZHMnLFxuICAgICAgICB9KTtcblxuICAgICAgICBpZiAoIW1zZ0RldGFpbHMuZGF0YSkgcmV0dXJuIG51bGw7XG4gICAgICAgIGNvbnN0IGhlYWRlcnMgPSBtc2dEZXRhaWxzLmRhdGEucGF5bG9hZD8uaGVhZGVycyB8fCBbXTtcbiAgICAgICAgY29uc3Qgc3ViamVjdCA9IGhlYWRlcnMuZmluZChoID0+IGgubmFtZT8udG9Mb3dlckNhc2UoKSA9PT0gJ3N1YmplY3QnKT8udmFsdWUgfHwgJ05vIFN1YmplY3QnO1xuICAgICAgICBjb25zdCBmcm9tID0gaGVhZGVycy5maW5kKGggPT4gaC5uYW1lPy50b0xvd2VyQ2FzZSgpID09PSAnZnJvbScpPy52YWx1ZSB8fCAnTi9BJztcbiAgICAgICAgY29uc3QgZGF0ZUhlYWRlciA9IGhlYWRlcnMuZmluZChoID0+IGgubmFtZT8udG9Mb3dlckNhc2UoKSA9PT0gJ2RhdGUnKT8udmFsdWU7XG5cbiAgICAgICAgY29uc3QgdGltZXN0YW1wID0gbXNnRGV0YWlscy5kYXRhLmludGVybmFsRGF0ZVxuICAgICAgICAgID8gbmV3IERhdGUocGFyc2VJbnQobXNnRGV0YWlscy5kYXRhLmludGVybmFsRGF0ZSwgMTApKS50b0lTT1N0cmluZygpXG4gICAgICAgICAgOiAoZGF0ZUhlYWRlciA/IG5ldyBEYXRlKGRhdGVIZWFkZXIpLnRvSVNPU3RyaW5nKCkgOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCkpO1xuXG4gICAgICAgIGNvbnN0IGlzVW5yZWFkID0gbXNnRGV0YWlscy5kYXRhLmxhYmVsSWRzPy5pbmNsdWRlcygnVU5SRUFEJykgfHwgZmFsc2U7XG5cbiAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICBpZDogbXNnRGV0YWlscy5kYXRhLmlkISxcbiAgICAgICAgICB0aHJlYWRJZDogbXNnRGV0YWlscy5kYXRhLnRocmVhZElkIHx8IHVuZGVmaW5lZCxcbiAgICAgICAgICBzZW5kZXI6IGZyb20sXG4gICAgICAgICAgcmVjaXBpZW50OiAnbWUnLFxuICAgICAgICAgIHN1YmplY3Q6IHN1YmplY3QsXG4gICAgICAgICAgYm9keTogbXNnRGV0YWlscy5kYXRhLnNuaXBwZXQgfHwgJycsXG4gICAgICAgICAgdGltZXN0YW1wOiB0aW1lc3RhbXAsXG4gICAgICAgICAgcmVhZDogIWlzVW5yZWFkLFxuICAgICAgICB9IGFzIEVtYWlsO1xuICAgICAgfSBjYXRjaCAoZXJyKSB7XG4gICAgICAgIGxvZ2dlci5lcnJvcihgW2VtYWlsU2tpbGxzXSBFcnJvciBmZXRjaGluZyBkZXRhaWxzIGZvciBtZXNzYWdlIElEICR7bXNnLmlkfTpgLCBlcnIpO1xuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH1cbiAgICB9KTtcblxuICAgIGNvbnN0IGVtYWlscyA9IChhd2FpdCBQcm9taXNlLmFsbChlbWFpbERldGFpbHNQcm9taXNlcykpLmZpbHRlcihlbWFpbCA9PiBlbWFpbCAhPT0gbnVsbCkgYXMgRW1haWxbXTtcbiAgICBsb2dnZXIuaW5mbyhgW2VtYWlsU2tpbGxzXSBTdWNjZXNzZnVsbHkgZmV0Y2hlZCAke2VtYWlscy5sZW5ndGh9IGVtYWlsIGRldGFpbHMgZm9yIHF1ZXJ5IFwiJHtzZWFyY2hRdWVyeX1cIi5gKTtcbiAgICByZXR1cm4gZW1haWxzO1xuXG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBsb2dnZXIuZXJyb3IoYFtlbWFpbFNraWxsc10gRXJyb3Igc2VhcmNoaW5nIEdtYWlsIGZvciB1c2VyICR7dXNlcklkfSwgcXVlcnkgXCIke3NlYXJjaFF1ZXJ5fVwiOmAsIGVycm9yKTtcbiAgICBpZiAoZXJyb3IuY29kZSA9PT0gNDAxIHx8IGVycm9yLmNvZGUgPT09IDQwMykge1xuICAgICAgICBsb2dnZXIuZXJyb3IoYFtlbWFpbFNraWxsc10gR21haWwgQVBJIGF1dGhlbnRpY2F0aW9uL2F1dGhvcml6YXRpb24gZXJyb3I6ICR7ZXJyb3IubWVzc2FnZX1gKTtcbiAgICB9XG4gICAgcmV0dXJuIFtdO1xuICB9XG59XG5cbi8vIEhlbHBlciB0byBmaW5kIGFuZCBkZWNvZGUgdGV4dC9wbGFpbiBvciB0ZXh0L2h0bWwgYm9keSBmcm9tIEdtYWlsIHBheWxvYWRcbmZ1bmN0aW9uIGV4dHJhY3RSZWFkYWJsZUJvZHkocGFydDogZ21haWxfdjEuU2NoZW1hJE1lc3NhZ2VQYXJ0IHwgdW5kZWZpbmVkLCBwcmVmZXJyZWRUeXBlOiAndGV4dC9wbGFpbicgfCAndGV4dC9odG1sJyA9ICd0ZXh0L3BsYWluJyk6IHN0cmluZyB8IG51bGwge1xuICAgIGlmICghcGFydCkgcmV0dXJuIG51bGw7XG5cbiAgICBsZXQgZm91bmRIdG1sQm9keTogc3RyaW5nIHwgbnVsbCA9IG51bGw7XG5cbiAgICAvLyBJZiB0aGlzIHBhcnQgaXMgdGhlIHByZWZlcnJlZCB0eXBlXG4gICAgaWYgKHBhcnQubWltZVR5cGUgPT09IHByZWZlcnJlZFR5cGUgJiYgcGFydC5ib2R5Py5kYXRhKSB7XG4gICAgICAgIGNvbnN0IGRlY29kZWRCb2R5ID0gQnVmZmVyLmZyb20ocGFydC5ib2R5LmRhdGEsICdiYXNlNjR1cmwnKS50b1N0cmluZygndXRmOCcpO1xuICAgICAgICBpZiAocHJlZmVycmVkVHlwZSA9PT0gJ3RleHQvaHRtbCcpIHtcbiAgICAgICAgICAgIC8vIEJhc2ljIEhUTUwgc3RyaXBwaW5nIGlmIHdlIGFyZSBmb3JjZWQgdG8gdXNlIEhUTUwuXG4gICAgICAgICAgICAvLyBBIGxpYnJhcnkgd291bGQgYmUgbXVjaCBiZXR0ZXIgZm9yIHRoaXMuXG4gICAgICAgICAgICByZXR1cm4gZGVjb2RlZEJvZHlcbiAgICAgICAgICAgICAgICAucmVwbGFjZSgvPHN0eWxlW14+XSo+Lio/PFxcL3N0eWxlPi9ncywgJycpIC8vIFJlbW92ZSBzdHlsZSBibG9ja3NcbiAgICAgICAgICAgICAgICAucmVwbGFjZSgvPHNjcmlwdFtePl0qPi4qPzxcXC9zY3JpcHQ+L2dzLCAnJykgLy8gUmVtb3ZlIHNjcmlwdCBibG9ja3NcbiAgICAgICAgICAgICAgICAucmVwbGFjZSgvPFtePl0rPi9nLCAnICcpIC8vIFJlbW92ZSBhbGwgb3RoZXIgdGFncywgcmVwbGFjZSB3aXRoIHNwYWNlXG4gICAgICAgICAgICAgICAgLnJlcGxhY2UoL1xccysvZywgJyAnKSAvLyBDb25kZW5zZSBtdWx0aXBsZSBzcGFjZXNcbiAgICAgICAgICAgICAgICAudHJpbSgpO1xuICAgICAgICB9XG4gICAgICAgIHJldHVybiBkZWNvZGVkQm9keTtcbiAgICB9XG5cbiAgICAvLyBJZiB0aGlzIHBhcnQgaXMgSFRNTCBhbmQgd2UgYXJlIGxvb2tpbmcgZm9yIHBsYWluIChzdG9yZSBpdCBhcyBmYWxsYmFjaylcbiAgICBpZiAocGFydC5taW1lVHlwZSA9PT0gJ3RleHQvaHRtbCcgJiYgcGFydC5ib2R5Py5kYXRhKSB7XG4gICAgICAgIGNvbnN0IGRlY29kZWRIdG1sID0gQnVmZmVyLmZyb20ocGFydC5ib2R5LmRhdGEsICdiYXNlNjR1cmwnKS50b1N0cmluZygndXRmOCcpO1xuICAgICAgICAvLyBCYXNpYyBIVE1MIHN0cmlwcGluZ1xuICAgICAgICBmb3VuZEh0bWxCb2R5ID0gZGVjb2RlZEh0bWxcbiAgICAgICAgICAgIC5yZXBsYWNlKC88c3R5bGVbXj5dKj4uKj88XFwvc3R5bGU+L2dzLCAnJylcbiAgICAgICAgICAgIC5yZXBsYWNlKC88c2NyaXB0W14+XSo+Lio/PFxcL3NjcmlwdD4vZ3MsICcnKVxuICAgICAgICAgICAgLnJlcGxhY2UoLzxbXj5dKz4vZywgJyAnKVxuICAgICAgICAgICAgLnJlcGxhY2UoL1xccysvZywgJyAnKVxuICAgICAgICAgICAgLnRyaW0oKTtcbiAgICB9XG5cbiAgICAvLyBJZiB0aGlzIHBhcnQgaXMgbXVsdGlwYXJ0L2FsdGVybmF0aXZlLCBzZWFyY2ggaXRzIHN1YnBhcnRzLCBwcmlvcml0aXppbmcgdGV4dC9wbGFpblxuICAgIGlmIChwYXJ0Lm1pbWVUeXBlID09PSAnbXVsdGlwYXJ0L2FsdGVybmF0aXZlJyAmJiBwYXJ0LnBhcnRzICYmIHBhcnQucGFydHMubGVuZ3RoID4gMCkge1xuICAgICAgICBsZXQgcGxhaW5UZXh0VmVyc2lvbjogc3RyaW5nIHwgbnVsbCA9IG51bGw7XG4gICAgICAgIGxldCBodG1sVmVyc2lvbjogc3RyaW5nIHwgbnVsbCA9IG51bGw7XG4gICAgICAgIGZvciAoY29uc3Qgc3ViUGFydCBvZiBwYXJ0LnBhcnRzKSB7XG4gICAgICAgICAgICBpZiAoc3ViUGFydC5taW1lVHlwZSA9PT0gJ3RleHQvcGxhaW4nICYmIHN1YlBhcnQuYm9keT8uZGF0YSkge1xuICAgICAgICAgICAgICAgIHBsYWluVGV4dFZlcnNpb24gPSBCdWZmZXIuZnJvbShzdWJQYXJ0LmJvZHkuZGF0YSwgJ2Jhc2U2NHVybCcpLnRvU3RyaW5nKCd1dGY4Jyk7XG4gICAgICAgICAgICAgICAgYnJlYWs7IC8vIEZvdW5kIHBsYWluIHRleHQsIHByZWZlciB0aGlzXG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBpZiAoc3ViUGFydC5taW1lVHlwZSA9PT0gJ3RleHQvaHRtbCcgJiYgc3ViUGFydC5ib2R5Py5kYXRhKSB7XG4gICAgICAgICAgICAgICAgIGNvbnN0IGRlY29kZWRIdG1sID0gQnVmZmVyLmZyb20oc3ViUGFydC5ib2R5LmRhdGEsICdiYXNlNjR1cmwnKS50b1N0cmluZygndXRmOCcpO1xuICAgICAgICAgICAgICAgICBodG1sVmVyc2lvbiA9IGRlY29kZWRIdG1sXG4gICAgICAgICAgICAgICAgICAgIC5yZXBsYWNlKC88c3R5bGVbXj5dKj4uKj88XFwvc3R5bGU+L2dzLCAnJylcbiAgICAgICAgICAgICAgICAgICAgLnJlcGxhY2UoLzxzY3JpcHRbXj5dKj4uKj88XFwvc2NyaXB0Pi9ncywgJycpXG4gICAgICAgICAgICAgICAgICAgIC5yZXBsYWNlKC88W14+XSs+L2csICcgJylcbiAgICAgICAgICAgICAgICAgICAgLnJlcGxhY2UoL1xccysvZywgJyAnKVxuICAgICAgICAgICAgICAgICAgICAudHJpbSgpO1xuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICAgIGlmIChwbGFpblRleHRWZXJzaW9uKSByZXR1cm4gcGxhaW5UZXh0VmVyc2lvbjtcbiAgICAgICAgaWYgKGh0bWxWZXJzaW9uKSByZXR1cm4gaHRtbFZlcnNpb247IC8vIEZhbGxiYWNrIHRvIHN0cmlwcGVkIEhUTUxcbiAgICB9XG5cbiAgICAvLyBGb3Igb3RoZXIgbXVsdGlwYXJ0IHR5cGVzIChlLmcuLCBtdWx0aXBhcnQvcmVsYXRlZCwgbXVsdGlwYXJ0L21peGVkKSBvciBpZiB0aGUgZGVzaXJlZCB0eXBlIGlzIG5vdCBmb3VuZCBhdCB0aGlzIGxldmVsLFxuICAgIC8vIHJlY3Vyc2l2ZWx5IHNlYXJjaCBzdWJwYXJ0cy5cbiAgICBpZiAocGFydC5wYXJ0cyAmJiBwYXJ0LnBhcnRzLmxlbmd0aCA+IDApIHtcbiAgICAgICAgZm9yIChjb25zdCBzdWJQYXJ0IG9mIHBhcnQucGFydHMpIHtcbiAgICAgICAgICAgIC8vIFRyeSB0byBmaW5kIHByZWZlcnJlZCB0eXBlIGZpcnN0XG4gICAgICAgICAgICBjb25zdCBib2R5ID0gZXh0cmFjdFJlYWRhYmxlQm9keShzdWJQYXJ0LCBwcmVmZXJyZWRUeXBlKTtcbiAgICAgICAgICAgIGlmIChib2R5KSByZXR1cm4gYm9keTtcbiAgICAgICAgfVxuICAgICAgICAvLyBJZiBwcmVmZXJyZWQgdHlwZSBub3QgZm91bmQgaW4gYW55IHN1YnBhcnQsIHRyeSB0byBmaW5kIEhUTUwgYXMgYSBmYWxsYmFjayBpbiBzdWJwYXJ0c1xuICAgICAgICBpZiAocHJlZmVycmVkVHlwZSA9PT0gJ3RleHQvcGxhaW4nICYmIGZvdW5kSHRtbEJvZHkpIHtcbiAgICAgICAgICAgIHJldHVybiBmb3VuZEh0bWxCb2R5OyAvLyBSZXR1cm4gSFRNTCBmb3VuZCBhdCBjdXJyZW50IGxldmVsIGlmIG5vIHBsYWluIHRleHQgaW4gc3VicGFydHNcbiAgICAgICAgfVxuICAgICAgICAgLy8gSWYgc3RpbGwgbm90aGluZywgYW5kIHByZWZlcnJlZCB3YXMgdGV4dC9wbGFpbiwgYnJvYWRlbiBzZWFyY2ggaW4gc3VicGFydHMgZm9yIHRleHQvaHRtbFxuICAgICAgICBpZiAocHJlZmVycmVkVHlwZSA9PT0gJ3RleHQvcGxhaW4nKSB7XG4gICAgICAgICAgICBmb3IgKGNvbnN0IHN1YlBhcnQgb2YgcGFydC5wYXJ0cykge1xuICAgICAgICAgICAgICAgIGNvbnN0IGh0bWxCb2R5ID0gZXh0cmFjdFJlYWRhYmxlQm9keShzdWJQYXJ0LCAndGV4dC9odG1sJyk7XG4gICAgICAgICAgICAgICAgaWYgKGh0bWxCb2R5KSByZXR1cm4gaHRtbEJvZHk7IC8vIFJldHVybiB0aGUgZmlyc3Qgc3RyaXBwZWQgSFRNTCBmb3VuZFxuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgfVxuXG4gICAgLy8gRmFsbGJhY2sgdG8gSFRNTCBib2R5IGZvdW5kIGF0IHRoaXMgbGV2ZWwgaWYgcHJlZmVycmVkIHdhcyBwbGFpbiBhbmQgbm90aGluZyBlbHNlIGZvdW5kXG4gICAgaWYgKHByZWZlcnJlZFR5cGUgPT09ICd0ZXh0L3BsYWluJyAmJiBmb3VuZEh0bWxCb2R5KSB7XG4gICAgICAgIHJldHVybiBmb3VuZEh0bWxCb2R5O1xuICAgIH1cblxuICAgIHJldHVybiBudWxsO1xufVxuXG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiByZWFkRW1haWwodXNlcklkOiBzdHJpbmcsIGVtYWlsSWQ6IHN0cmluZyk6IFByb21pc2U8UmVhZEVtYWlsUmVzcG9uc2U+IHtcbiAgbG9nZ2VyLmluZm8oYFtlbWFpbFNraWxsc10gUmVhZGluZyBlbWFpbCB3aXRoIElEOiAke2VtYWlsSWR9IGZvciB1c2VyICR7dXNlcklkfWApO1xuXG4gIGNvbnN0IGdtYWlsID0gYXdhaXQgZ2V0R21haWxDbGllbnQodXNlcklkKTtcbiAgaWYgKCFnbWFpbCkge1xuICAgIGNvbnN0IGVycm9yTXNnID0gXCJGYWlsZWQgdG8gZ2V0IEdtYWlsIGNsaWVudCwgY2Fubm90IHJlYWQgZW1haWwuXCI7XG4gICAgbG9nZ2VyLmVycm9yKGBbZW1haWxTa2lsbHNdICR7ZXJyb3JNc2d9YCk7XG4gICAgcmV0dXJuIHsgc3VjY2VzczogZmFsc2UsIG1lc3NhZ2U6IGVycm9yTXNnIH07XG4gIH1cblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZ21haWwudXNlcnMubWVzc2FnZXMuZ2V0KHtcbiAgICAgIHVzZXJJZDogJ21lJyxcbiAgICAgIGlkOiBlbWFpbElkLFxuICAgICAgZm9ybWF0OiAnZnVsbCcsIC8vIEdldCBmdWxsIHBheWxvYWQgdG8gZXh0cmFjdCBib2R5IGFuZCBoZWFkZXJzXG4gICAgfSk7XG5cbiAgICBjb25zdCBmZXRjaGVkRW1haWwgPSByZXNwb25zZS5kYXRhO1xuICAgIGlmICghZmV0Y2hlZEVtYWlsIHx8ICFmZXRjaGVkRW1haWwuaWQpIHtcbiAgICAgIGNvbnN0IGVycm9yTXNnID0gYEVtYWlsIHdpdGggSUQgJHtlbWFpbElkfSBub3QgZm91bmQgb3IgZGF0YSBpbmNvbXBsZXRlLmA7XG4gICAgICBsb2dnZXIud2FybihgW2VtYWlsU2tpbGxzXSAke2Vycm9yTXNnfWApO1xuICAgICAgcmV0dXJuIHsgc3VjY2VzczogZmFsc2UsIG1lc3NhZ2U6IGVycm9yTXNnIH07XG4gICAgfVxuXG4gICAgY29uc3QgaGVhZGVycyA9IGZldGNoZWRFbWFpbC5wYXlsb2FkPy5oZWFkZXJzIHx8IFtdO1xuICAgIGNvbnN0IHN1YmplY3QgPSBoZWFkZXJzLmZpbmQoaCA9PiBoLm5hbWU/LnRvTG93ZXJDYXNlKCkgPT09ICdzdWJqZWN0Jyk/LnZhbHVlIHx8ICdObyBTdWJqZWN0JztcbiAgICBjb25zdCBmcm9tID0gaGVhZGVycy5maW5kKGggPT4gaC5uYW1lPy50b0xvd2VyQ2FzZSgpID09PSAnZnJvbScpPy52YWx1ZSB8fCAnTi9BJztcbiAgICBjb25zdCB0byA9IGhlYWRlcnMuZmluZChoID0+IGgubmFtZT8udG9Mb3dlckNhc2UoKSA9PT0gJ3RvJyk/LnZhbHVlIHx8ICdOL0EnOyAvLyBDYW4gYmUgbXVsdGlwbGUsIGpvaW4gaWYgbmVlZGVkXG4gICAgY29uc3QgZGF0ZUhlYWRlciA9IGhlYWRlcnMuZmluZChoID0+IGgubmFtZT8udG9Mb3dlckNhc2UoKSA9PT0gJ2RhdGUnKT8udmFsdWU7XG5cbiAgICBjb25zdCB0aW1lc3RhbXAgPSBmZXRjaGVkRW1haWwuaW50ZXJuYWxEYXRlXG4gICAgICA/IG5ldyBEYXRlKHBhcnNlSW50KGZldGNoZWRFbWFpbC5pbnRlcm5hbERhdGUsIDEwKSkudG9JU09TdHJpbmcoKVxuICAgICAgOiAoZGF0ZUhlYWRlciA/IG5ldyBEYXRlKGRhdGVIZWFkZXIpLnRvSVNPU3RyaW5nKCkgOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCkpO1xuXG4gICAgY29uc3QgYm9keSA9IGV4dHJhY3RSZWFkYWJsZUJvZHkoZmV0Y2hlZEVtYWlsLnBheWxvYWQpIHx8IGZldGNoZWRFbWFpbC5zbmlwcGV0IHx8ICcnO1xuXG4gICAgLy8gRGV0ZXJtaW5lIHJlYWQgc3RhdHVzIChzaW1wbGlmaWVkOiBpZiAnVU5SRUFEJyBpcyBub3QgaW4gbGFiZWxJZHMsIGl0J3MgcmVhZClcbiAgICAvLyBUaGlzIGlzIGEgY29tbW9uIHdheSBidXQgbWlnaHQgbm90IGJlIDEwMCUgYWNjdXJhdGUgZm9yIGFsbCBlZGdlIGNhc2VzIG9mIFwicmVhZFwiIHN0YXR1cy5cbiAgICBjb25zdCBpc1VucmVhZCA9IGZldGNoZWRFbWFpbC5sYWJlbElkcz8uaW5jbHVkZXMoJ1VOUkVBRCcpIHx8IGZhbHNlO1xuXG4gICAgY29uc3QgZW1haWw6IEVtYWlsID0ge1xuICAgICAgaWQ6IGZldGNoZWRFbWFpbC5pZCxcbiAgICAgIHRocmVhZElkOiBmZXRjaGVkRW1haWwudGhyZWFkSWQgfHwgdW5kZWZpbmVkLFxuICAgICAgc2VuZGVyOiBmcm9tLFxuICAgICAgcmVjaXBpZW50OiB0byxcbiAgICAgIHN1YmplY3Q6IHN1YmplY3QsXG4gICAgICBib2R5OiBib2R5LFxuICAgICAgdGltZXN0YW1wOiB0aW1lc3RhbXAsXG4gICAgICByZWFkOiAhaXNVbnJlYWQsXG4gICAgfTtcbiAgICBsb2dnZXIuaW5mbyhgW2VtYWlsU2tpbGxzXSBTdWNjZXNzZnVsbHkgcmVhZCBlbWFpbCBJRCAke2VtYWlsSWR9LiBTdWJqZWN0OiAke3N1YmplY3R9YCk7XG4gICAgcmV0dXJuIHsgc3VjY2VzczogdHJ1ZSwgZW1haWwgfTtcblxuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKGBbZW1haWxTa2lsbHNdIEVycm9yIHJlYWRpbmcgZW1haWwgSUQgJHtlbWFpbElkfSBmb3IgdXNlciAke3VzZXJJZH06YCwgZXJyb3IpO1xuICAgIGlmIChlcnJvci5jb2RlID09PSA0MDEgfHwgZXJyb3IuY29kZSA9PT0gNDAzKSB7XG4gICAgICAgIHJldHVybiB7IHN1Y2Nlc3M6IGZhbHNlLCBtZXNzYWdlOiBgR21haWwgQVBJIGF1dGhlbnRpY2F0aW9uL2F1dGhvcml6YXRpb24gZXJyb3I6ICR7ZXJyb3IubWVzc2FnZX1gIH07XG4gICAgfVxuICAgIGlmIChlcnJvci5jb2RlID09PSA0MDQpIHtcbiAgICAgICAgcmV0dXJuIHsgc3VjY2VzczogZmFsc2UsIG1lc3NhZ2U6IGBFbWFpbCB3aXRoIElEICR7ZW1haWxJZH0gbm90IGZvdW5kLmAgfTtcbiAgICB9XG4gICAgcmV0dXJuIHsgc3VjY2VzczogZmFsc2UsIG1lc3NhZ2U6IChlcnJvciBhcyBFcnJvcikubWVzc2FnZSB8fCBgRmFpbGVkIHRvIHJlYWQgZW1haWwgJHtlbWFpbElkfS5gIH07XG4gIH1cbn1cblxuLy8gUmVtb3ZlZCBjYWxsSGFzdXJhQWN0aW9uR3JhcGhRTCBhbmQgYXNzb2NpYXRlZCBHUUwgY29uc3RhbnRzIGFzIHRoZXkgYXJlIG5vIGxvbmdlciB1c2VkIGJ5IHNlYXJjaE15RW1haWxzIG9yIHJlYWRFbWFpbC5cblxuaW1wb3J0IE9wZW5BSSBmcm9tICdvcGVuYWknO1xuaW1wb3J0IHsgQ2hhdENvbXBsZXRpb25NZXNzYWdlUGFyYW0gfSBmcm9tICdvcGVuYWkvcmVzb3VyY2VzL2NoYXQvY29tcGxldGlvbnMnO1xuaW1wb3J0IHsgQVRPTV9PUEVOQUlfQVBJX0tFWSwgQVRPTV9OTFVfTU9ERUxfTkFNRSB9IGZyb20gJy4uL19saWJzL2NvbnN0YW50cyc7IC8vIFJldXNlIGV4aXN0aW5nIGNvbnN0YW50c1xuXG4vLyBPcGVuQUkgY2xpZW50IGZvciBpbmZvcm1hdGlvbiBleHRyYWN0aW9uXG5sZXQgb3BlbkFJQ2xpZW50Rm9yRXh0cmFjdGlvbjogT3BlbkFJIHwgbnVsbCA9IG51bGw7XG5cbmZ1bmN0aW9uIGdldEV4dHJhY3Rpb25PcGVuQUlDbGllbnQoKTogT3BlbkFJIHtcbiAgaWYgKG9wZW5BSUNsaWVudEZvckV4dHJhY3Rpb24pIHtcbiAgICByZXR1cm4gb3BlbkFJQ2xpZW50Rm9yRXh0cmFjdGlvbjtcbiAgfVxuICBpZiAoIUFUT01fT1BFTkFJX0FQSV9LRVkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdPcGVuQUkgQVBJIEtleSBub3QgY29uZmlndXJlZCBmb3IgTExNIEVtYWlsIEV4dHJhY3Rvci4nKTtcbiAgICB0aHJvdyBuZXcgRXJyb3IoJ09wZW5BSSBBUEkgS2V5IG5vdCBjb25maWd1cmVkIGZvciBMTE0gRW1haWwgRXh0cmFjdG9yLicpO1xuICB9XG4gIG9wZW5BSUNsaWVudEZvckV4dHJhY3Rpb24gPSBuZXcgT3BlbkFJKHsgYXBpS2V5OiBBVE9NX09QRU5BSV9BUElfS0VZIH0pO1xuICByZXR1cm4gb3BlbkFJQ2xpZW50Rm9yRXh0cmFjdGlvbjtcbn1cblxuY29uc3QgRVhUUkFDVElPTl9TWVNURU1fUFJPTVBUX1RFTVBMQVRFID0gYFxuWW91IGFyZSBhbiBleHBlcnQgc3lzdGVtIGRlc2lnbmVkIHRvIGV4dHJhY3Qgc3BlY2lmaWMgcGllY2VzIG9mIGluZm9ybWF0aW9uIGZyb20gYW4gZW1haWwgYm9keS5cblRoZSB1c2VyIHdpbGwgcHJvdmlkZSBhbiBlbWFpbCBib2R5IGFuZCBhIGxpc3Qgb2YgaW5mb3JtYXRpb24gcG9pbnRzIHRoZXkgYXJlIGxvb2tpbmcgZm9yIChrZXl3b3JkcykuXG5Gb3IgZWFjaCBrZXl3b3JkLCBmaW5kIHRoZSBjb3JyZXNwb25kaW5nIGluZm9ybWF0aW9uIGluIHRoZSBlbWFpbCBib2R5LlxuUmVzcG9uZCBPTkxZIHdpdGggYSBzaW5nbGUsIHZhbGlkIEpTT04gb2JqZWN0LiBEbyBub3QgaW5jbHVkZSBhbnkgZXhwbGFuYXRvcnkgdGV4dCBiZWZvcmUgb3IgYWZ0ZXIgdGhlIEpTT04uXG5UaGUgSlNPTiBvYmplY3Qgc2hvdWxkIGhhdmUga2V5cyBjb3JyZXNwb25kaW5nIHRvIHRoZSB1c2VyJ3Mgb3JpZ2luYWwga2V5d29yZHMuXG5UaGUgdmFsdWUgZm9yIGVhY2gga2V5IHNob3VsZCBiZSB0aGUgZXh0cmFjdGVkIGluZm9ybWF0aW9uIGFzIGEgc3RyaW5nLlxuSWYgYSBzcGVjaWZpYyBwaWVjZSBvZiBpbmZvcm1hdGlvbiBmb3IgYSBrZXl3b3JkIGlzIG5vdCBmb3VuZCBpbiB0aGUgZW1haWwgYm9keSwgdGhlIHZhbHVlIGZvciB0aGF0IGtleSBzaG91bGQgYmUgbnVsbC5cblxuRXhhbXBsZTpcblVzZXIgcHJvdmlkZXMga2V5d29yZHM6IFtcImludm9pY2UgbnVtYmVyXCIsIFwiZHVlIGRhdGVcIiwgXCJhbW91bnRcIl1cbkVtYWlsIGJvZHk6IFwiQXR0YWNoZWQgaXMgaW52b2ljZSBJTlYtMTIzIGZvciAkNTAuMDAsIHBheW1lbnQgaXMgZHVlIG9uIDIwMjQtMDEtMTUuXCJcbllvdXIgSlNPTiByZXNwb25zZTpcbntcbiAgXCJpbnZvaWNlIG51bWJlclwiOiBcIklOVi0xMjNcIixcbiAgXCJkdWUgZGF0ZVwiOiBcIjIwMjQtMDEtMTVcIixcbiAgXCJhbW91bnRcIjogXCIkNTAuMDBcIlxufVxuXG5JZiBrZXl3b3JkcyBhcmUgW1wic2VuZGVyIG5hbWVcIiwgXCJtZWV0aW5nIHRpbWVcIl0gYW5kIGVtYWlsIGJvZHkgaXMgXCJGcm9tIEJvYiwgYWJvdXQgdGhlIHN5bmMgYXQgMyBQTS5cIixcbllvdXIgSlNPTiByZXNwb25zZTpcbntcbiAgXCJzZW5kZXIgbmFtZVwiOiBcIkJvYlwiLFxuICBcIm1lZXRpbmcgdGltZVwiOiBcIjMgUE1cIlxufVxuXG5JZiBhIGtleXdvcmQgaXMgXCJjb250cmFjdCBlbmQgZGF0ZVwiIGFuZCB0aGUgZW1haWwgc2F5cyBcIlRoZSBhZ3JlZW1lbnQgaXMgdmFsaWQgdW50aWwgTWFyY2ggNXRoLCAyMDI1XCIsXG5Zb3VyIEpTT04gcmVzcG9uc2U6XG57XG4gIFwiY29udHJhY3QgZW5kIGRhdGVcIjogXCJNYXJjaCA1dGgsIDIwMjVcIlxufVxuXG5JZiBpbmZvcm1hdGlvbiBmb3IgYSBrZXl3b3JkIGlzIG5vdCBmb3VuZCwgdXNlIG51bGwgZm9yIGl0cyB2YWx1ZS5cbkV4YW1wbGU6IEtleXdvcmRzOiBbXCJ0cmFja2luZyBudW1iZXJcIiwgXCJjb3Vwb24gY29kZVwiXSwgRW1haWw6IFwiWW91ciBvcmRlciBoYXMgc2hpcHBlZC5cIlxuWW91ciBKU09OIHJlc3BvbnNlOlxue1xuICBcInRyYWNraW5nIG51bWJlclwiOiBudWxsLFxuICBcImNvdXBvbiBjb2RlXCI6IG51bGxcbn1cblxuVGhlIGtleXdvcmRzIHlvdSBuZWVkIHRvIGV4dHJhY3QgaW5mb3JtYXRpb24gZm9yIGFyZToge3tLRVlXT1JEU19KU09OX0FSUkFZX1NUUklOR319XG5FeHRyYWN0IHRoZSBpbmZvcm1hdGlvbiBmcm9tIHRoZSBlbWFpbCBib2R5IHByb3ZpZGVkIGJ5IHRoZSB1c2VyLlxuYDtcblxuXG4vKipcbiAqIFVzZXMgYW4gTExNIHRvIGV4dHJhY3Qgc3BlY2lmaWMgcGllY2VzIG9mIGluZm9ybWF0aW9uIGZyb20gYW4gZW1haWwgYm9keVxuICogYmFzZWQgb24gYSBsaXN0IG9mIGtleXdvcmRzIG9yIGNvbmNlcHRzLlxuICogQHBhcmFtIGVtYWlsQm9keSBUaGUgcGxhaW4gdGV4dCBib2R5IG9mIHRoZSBlbWFpbC5cbiAqIEBwYXJhbSBpbmZvS2V5d29yZHMgQW4gYXJyYXkgb2Ygc3RyaW5ncyByZXByZXNlbnRpbmcgdGhlIGNvbmNlcHRzL2tleXdvcmRzIHRvIHNlYXJjaCBmb3IuXG4gKiAgICAgICAgICAgICAgICAgICAgIChlLmcuLCBbXCJjb250cmFjdCBlbmQgZGF0ZVwiLCBcImludm9pY2UgbnVtYmVyXCIsIFwibWVldGluZyBsaW5rXCJdKVxuICogQHJldHVybnMgQSBQcm9taXNlIHJlc29sdmluZyB0byBhIHJlY29yZCB3aGVyZSBrZXlzIGFyZSBpbmZvS2V5d29yZHMgYW5kIHZhbHVlcyBhcmUgdGhlIGV4dHJhY3RlZCBzdHJpbmdzIChvciBudWxsKS5cbiAqL1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGV4dHJhY3RJbmZvcm1hdGlvbkZyb21FbWFpbEJvZHkoXG4gIGVtYWlsQm9keTogc3RyaW5nLFxuICBpbmZvS2V5d29yZHM6IHN0cmluZ1tdXG4pOiBQcm9taXNlPFJlY29yZDxzdHJpbmcsIHN0cmluZyB8IG51bGw+PiB7XG4gIGlmICghaW5mb0tleXdvcmRzIHx8IGluZm9LZXl3b3Jkcy5sZW5ndGggPT09IDApIHtcbiAgICByZXR1cm4ge307IC8vIE5vIGtleXdvcmRzIHRvIGV4dHJhY3RcbiAgfVxuXG4gIGNvbnNvbGUubG9nKGBMTE0gRXh0cmFjdG9yOiBBdHRlbXB0aW5nIHRvIGV4dHJhY3QgaW5mb3JtYXRpb24gZm9yIGtleXdvcmRzOiBbJHtpbmZvS2V5d29yZHMuam9pbignLCAnKX1dYCk7XG4gIGNvbnN0IGNsaWVudCA9IGdldEV4dHJhY3Rpb25PcGVuQUlDbGllbnQoKTtcblxuICAvLyBQcmVwYXJlIHRoZSBwcm9tcHQgYnkgaW5qZWN0aW5nIHRoZSBzcGVjaWZpYyBrZXl3b3Jkc1xuICBjb25zdCBrZXl3b3Jkc0pzb25BcnJheVN0cmluZyA9IEpTT04uc3RyaW5naWZ5KGluZm9LZXl3b3Jkcyk7XG4gIGNvbnN0IHN5c3RlbVByb21wdCA9IEVYVFJBQ1RJT05fU1lTVEVNX1BST01QVF9URU1QTEFURS5yZXBsYWNlKFwie3tLRVlXT1JEU19KU09OX0FSUkFZX1NUUklOR319XCIsIGtleXdvcmRzSnNvbkFycmF5U3RyaW5nKTtcblxuICBjb25zdCBtZXNzYWdlczogQ2hhdENvbXBsZXRpb25NZXNzYWdlUGFyYW1bXSA9IFtcbiAgICB7IHJvbGU6ICdzeXN0ZW0nLCBjb250ZW50OiBzeXN0ZW1Qcm9tcHQgfSxcbiAgICB7IHJvbGU6ICd1c2VyJywgY29udGVudDogYEVtYWlsIEJvZHk6XFxuLS0tXFxuJHtlbWFpbEJvZHl9XFxuLS0tYCB9LFxuICBdO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgY29tcGxldGlvbiA9IGF3YWl0IGNsaWVudC5jaGF0LmNvbXBsZXRpb25zLmNyZWF0ZSh7XG4gICAgICBtb2RlbDogQVRPTV9OTFVfTU9ERUxfTkFNRSwgLy8gT3IgYSBtb3JlIGNhcGFibGUgbW9kZWwgbGlrZSBcImdwdC0zLjUtdHVyYm9cIiBvciBcImdwdC00XCJcbiAgICAgIG1lc3NhZ2VzOiBtZXNzYWdlcyxcbiAgICAgIHRlbXBlcmF0dXJlOiAwLjEsIC8vIExvdyB0ZW1wZXJhdHVyZSBmb3IgZmFjdHVhbCBleHRyYWN0aW9uXG4gICAgICByZXNwb25zZV9mb3JtYXQ6IHsgdHlwZTogJ2pzb25fb2JqZWN0JyB9LFxuICAgIH0pO1xuXG4gICAgY29uc3QgbGxtUmVzcG9uc2UgPSBjb21wbGV0aW9uLmNob2ljZXNbMF0/Lm1lc3NhZ2U/LmNvbnRlbnQ7XG4gICAgaWYgKCFsbG1SZXNwb25zZSkge1xuICAgICAgY29uc29sZS5lcnJvcignTExNIEV4dHJhY3RvcjogUmVjZWl2ZWQgYW4gZW1wdHkgcmVzcG9uc2UgZnJvbSBBSS4nKTtcbiAgICAgIHRocm93IG5ldyBFcnJvcignTExNIEV4dHJhY3RvcjogRW1wdHkgcmVzcG9uc2UgZnJvbSBBSS4nKTtcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZygnTExNIEV4dHJhY3RvcjogUmF3IExMTSBKU09OIHJlc3BvbnNlOicsIGxsbVJlc3BvbnNlKTtcbiAgICBjb25zdCBwYXJzZWRSZXNwb25zZSA9IEpTT04ucGFyc2UobGxtUmVzcG9uc2UpO1xuXG4gICAgLy8gRW5zdXJlIGFsbCByZXF1ZXN0ZWQga2V5d29yZHMgYXJlIHByZXNlbnQgaW4gdGhlIHJlc3BvbnNlLCB3aXRoIG51bGwgaWYgbm90IGZvdW5kIGJ5IExMTVxuICAgIGNvbnN0IHJlc3VsdDogUmVjb3JkPHN0cmluZywgc3RyaW5nIHwgbnVsbD4gPSB7fTtcbiAgICBmb3IgKGNvbnN0IGtleXdvcmQgb2YgaW5mb0tleXdvcmRzKSB7XG4gICAgICByZXN1bHRba2V5d29yZF0gPSBwYXJzZWRSZXNwb25zZS5oYXNPd25Qcm9wZXJ0eShrZXl3b3JkKSA/IHBhcnNlZFJlc3BvbnNlW2tleXdvcmRdIDogbnVsbDtcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZygnTExNIEV4dHJhY3RvcjogUGFyc2VkIGFuZCByZWNvbmNpbGVkIGV4dHJhY3Rpb246JywgcmVzdWx0KTtcbiAgICByZXR1cm4gcmVzdWx0O1xuXG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdMTE0gRXh0cmFjdG9yOiBFcnJvciBwcm9jZXNzaW5nIGluZm9ybWF0aW9uIGV4dHJhY3Rpb24gd2l0aCBPcGVuQUk6JywgZXJyb3IubWVzc2FnZSk7XG4gICAgaWYgKGVycm9yIGluc3RhbmNlb2YgU3ludGF4RXJyb3IpIHtcbiAgICAgICAgY29uc29sZS5lcnJvcignTExNIEV4dHJhY3RvcjogRmFpbGVkIHRvIHBhcnNlIEpTT04gcmVzcG9uc2UgZnJvbSBMTE0uJyk7XG4gICAgICAgIHRocm93IG5ldyBFcnJvcignTExNIEV4dHJhY3RvcjogRmFpbGVkIHRvIHBhcnNlIHJlc3BvbnNlIGZyb20gQUkgZm9yIGluZm9ybWF0aW9uIGV4dHJhY3Rpb24uJyk7XG4gICAgfVxuICAgIGlmIChlcnJvci5yZXNwb25zZT8uZGF0YT8uZXJyb3I/Lm1lc3NhZ2UpIHtcbiAgICAgICAgdGhyb3cgbmV3IEVycm9yKGBMTE0gRXh0cmFjdG9yOiBBUEkgRXJyb3IgLSAke2Vycm9yLnJlc3BvbnNlLmRhdGEuZXJyb3IubWVzc2FnZX1gKTtcbiAgICB9XG4gICAgLy8gRmFsbGJhY2sgZm9yIGluZm9LZXl3b3JkcyBpZiBMTE0gZmFpbHMgY2F0YXN0cm9waGljYWxseVxuICAgIGNvbnN0IGZhbGxiYWNrUmVzdWx0OiBSZWNvcmQ8c3RyaW5nLCBzdHJpbmcgfCBudWxsPiA9IHt9O1xuICAgIGluZm9LZXl3b3Jkcy5mb3JFYWNoKGt3ID0+IGZhbGxiYWNrUmVzdWx0W2t3XSA9IG51bGwpO1xuICAgIHJldHVybiBmYWxsYmFja1Jlc3VsdDtcbiAgfVxufVxuXG5cbmV4cG9ydCBpbnRlcmZhY2UgRW1haWxEZXRhaWxzIHtcbiAgdG86IHN0cmluZztcbiAgc3ViamVjdDogc3RyaW5nO1xuICBib2R5OiBzdHJpbmc7XG4gIGNjPzogc3RyaW5nW107XG4gIGJjYz86IHN0cmluZ1tdO1xuICBodG1sQm9keT86IHN0cmluZzsgLy8gT3B0aW9uYWwgSFRNTCBib2R5XG59XG5cbmltcG9ydCB7IFNFU0NsaWVudCwgU2VuZEVtYWlsQ29tbWFuZCB9IGZyb20gJ0Bhd3Mtc2RrL2NsaWVudC1zZXMnO1xuaW1wb3J0IHsgRU5WIH0gZnJvbSAnLi4vLi4vX3V0aWxzL2Vudic7IC8vIFVwZGF0ZWQgcGF0aFxuaW1wb3J0IHsgbG9nZ2VyIH0gZnJvbSAnLi4vLi4vX3V0aWxzL2xvZ2dlcic7IC8vIFVwZGF0ZWQgcGF0aFxuXG5sZXQgc2VzQ2xpZW50OiBTRVNDbGllbnQgfCBudWxsID0gbnVsbDtcblxuZnVuY3Rpb24gZ2V0U0VTQ2xpZW50KCk6IFNFU0NsaWVudCB7XG4gIGlmIChzZXNDbGllbnQpIHtcbiAgICByZXR1cm4gc2VzQ2xpZW50O1xuICB9XG4gIGlmICghRU5WLkFXU19SRUdJT04gfHwgIUVOVi5BV1NfQUNDRVNTX0tFWV9JRCB8fCAhRU5WLkFXU19TRUNSRVRfQUNDRVNTX0tFWSkge1xuICAgIGxvZ2dlci5lcnJvcignQVdTIFNFUyBlbnZpcm9ubWVudCB2YXJpYWJsZXMgbm90IGZ1bGx5IGNvbmZpZ3VyZWQgKEFXU19SRUdJT04sIEFXU19BQ0NFU1NfS0VZX0lELCBBV1NfU0VDUkVUX0FDQ0VTU19LRVkpLicpO1xuICAgIHRocm93IG5ldyBFcnJvcignQVdTIFNFUyBlbnZpcm9ubWVudCB2YXJpYWJsZXMgbm90IGZ1bGx5IGNvbmZpZ3VyZWQuJyk7XG4gIH1cbiAgc2VzQ2xpZW50ID0gbmV3IFNFU0NsaWVudCh7XG4gICAgcmVnaW9uOiBFTlYuQVdTX1JFR0lPTixcbiAgICBjcmVkZW50aWFsczoge1xuICAgICAgYWNjZXNzS2V5SWQ6IEVOVi5BV1NfQUNDRVNTX0tFWV9JRCxcbiAgICAgIHNlY3JldEFjY2Vzc0tleTogRU5WLkFXU19TRUNSRVRfQUNDRVNTX0tFWSxcbiAgICB9LFxuICB9KTtcbiAgcmV0dXJuIHNlc0NsaWVudDtcbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHNlbmRFbWFpbChlbWFpbERldGFpbHM6IEVtYWlsRGV0YWlscyk6IFByb21pc2U8U2VuZEVtYWlsUmVzcG9uc2U+IHtcbiAgbG9nZ2VyLmluZm8oJ0F0dGVtcHRpbmcgdG8gc2VuZCBlbWFpbCB2aWEgQVdTIFNFUyB3aXRoIGRldGFpbHM6JywgZW1haWxEZXRhaWxzKTtcblxuICBpZiAoIWVtYWlsRGV0YWlscy50byB8fCAhZW1haWxEZXRhaWxzLnN1YmplY3QgfHwgKCFlbWFpbERldGFpbHMuYm9keSAmJiAhZW1haWxEZXRhaWxzLmh0bWxCb2R5KSkge1xuICAgIGxvZ2dlci53YXJuKCdNaXNzaW5nIHJlcXVpcmVkIGVtYWlsIGRldGFpbHMgKHRvLCBzdWJqZWN0LCBhbmQgYXQgbGVhc3Qgb25lIG9mIGJvZHkgb3IgaHRtbEJvZHkpLicsIGVtYWlsRGV0YWlscyk7XG4gICAgcmV0dXJuIHsgc3VjY2VzczogZmFsc2UsIG1lc3NhZ2U6ICdNaXNzaW5nIHJlcXVpcmVkIGVtYWlsIGRldGFpbHMgKHRvLCBzdWJqZWN0LCBhbmQgYm9keS9odG1sQm9keSkuJyB9O1xuICB9XG4gIGlmICghRU5WLlNFU19TT1VSQ0VfRU1BSUwpIHtcbiAgICBsb2dnZXIuZXJyb3IoJ1NFU19TT1VSQ0VfRU1BSUwgZW52aXJvbm1lbnQgdmFyaWFibGUgaXMgbm90IHNldC4gQ2Fubm90IHNlbmQgZW1haWwuJyk7XG4gICAgcmV0dXJuIHsgc3VjY2VzczogZmFsc2UsIG1lc3NhZ2U6ICdFbWFpbCBzZW5kaW5nIGlzIG5vdCBjb25maWd1cmVkIChtaXNzaW5nIHNvdXJjZSBlbWFpbCkuJyB9O1xuICB9XG5cbiAgY29uc3QgY2xpZW50ID0gZ2V0U0VTQ2xpZW50KCk7XG5cbiAgY29uc3QgZGVzdGluYXRpb24gPSB7XG4gICAgVG9BZGRyZXNzZXM6IFtlbWFpbERldGFpbHMudG9dLFxuICAgIENjQWRkcmVzc2VzOiBlbWFpbERldGFpbHMuY2MgfHwgW10sXG4gICAgQmNjQWRkcmVzc2VzOiBlbWFpbERldGFpbHMuYmNjIHx8IFtdLFxuICB9O1xuXG4gIC8vIENvbnN0cnVjdCBtZXNzYWdlIGJvZHlcbiAgY29uc3QgbWVzc2FnZUJvZHkgPSB7fSBhcyBhbnk7IC8vIFNFUy5Cb2R5XG4gIGlmIChlbWFpbERldGFpbHMuYm9keSkge1xuICAgIG1lc3NhZ2VCb2R5LlRleHQgPSB7XG4gICAgICBDaGFyc2V0OiAnVVRGLTgnLFxuICAgICAgRGF0YTogZW1haWxEZXRhaWxzLmJvZHksXG4gICAgfTtcbiAgfVxuICBpZiAoZW1haWxEZXRhaWxzLmh0bWxCb2R5KSB7XG4gICAgbWVzc2FnZUJvZHkuSHRtbCA9IHtcbiAgICAgIENoYXJzZXQ6ICdVVEYtOCcsXG4gICAgICBEYXRhOiBlbWFpbERldGFpbHMuaHRtbEJvZHksXG4gICAgfTtcbiAgfVxuXG5cbiAgY29uc3QgcGFyYW1zID0ge1xuICAgIERlc3RpbmF0aW9uOiBkZXN0aW5hdGlvbixcbiAgICBNZXNzYWdlOiB7XG4gICAgICBCb2R5OiBtZXNzYWdlQm9keSxcbiAgICAgIFN1YmplY3Q6IHtcbiAgICAgICAgQ2hhcnNldDogJ1VURi04JyxcbiAgICAgICAgRGF0YTogZW1haWxEZXRhaWxzLnN1YmplY3QsXG4gICAgICB9LFxuICAgIH0sXG4gICAgU291cmNlOiBFTlYuU0VTX1NPVVJDRV9FTUFJTCxcbiAgICAvLyBSZXBseVRvQWRkcmVzc2VzOiBbRU5WLlNFU19TT1VSQ0VfRU1BSUxdLCAvLyBPcHRpb25hbDogU2V0IHJlcGx5LXRvIGlmIGRpZmZlcmVudFxuICB9O1xuXG4gIHRyeSB7XG4gICAgbG9nZ2VyLmluZm8oYFNlbmRpbmcgZW1haWwgdG8gJHtlbWFpbERldGFpbHMudG99IHZpYSBTRVMgZnJvbSAke0VOVi5TRVNfU09VUkNFX0VNQUlMfWApO1xuICAgIGNvbnN0IGNvbW1hbmQgPSBuZXcgU2VuZEVtYWlsQ29tbWFuZChwYXJhbXMpO1xuXG4gICAgY29uc3QgTUFYX1JFVFJJRVMgPSAzO1xuICAgIGxldCBhdHRlbXB0ID0gMDtcbiAgICBsZXQgbGFzdEVycm9yOiBhbnkgPSBudWxsO1xuXG4gICAgd2hpbGUgKGF0dGVtcHQgPCBNQVhfUkVUUklFUykge1xuICAgICAgdHJ5IHtcbiAgICAgICAgY29uc3QgZGF0YSA9IGF3YWl0IGNsaWVudC5zZW5kKGNvbW1hbmQpO1xuICAgICAgICBsb2dnZXIuaW5mbyhgRW1haWwgc2VudCBzdWNjZXNzZnVsbHkgdmlhIFNFUyBvbiBhdHRlbXB0ICR7YXR0ZW1wdCArIDF9LmAsIHsgbWVzc2FnZUlkOiBkYXRhLk1lc3NhZ2VJZCB9KTtcbiAgICAgICAgcmV0dXJuIHsgc3VjY2VzczogdHJ1ZSwgZW1haWxJZDogZGF0YS5NZXNzYWdlSWQsIG1lc3NhZ2U6ICdFbWFpbCBzZW50IHN1Y2Nlc3NmdWxseSB2aWEgQVdTIFNFUy4nIH07XG4gICAgICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgICAgIGxhc3RFcnJvciA9IGVycm9yO1xuICAgICAgICBsb2dnZXIud2FybihgQXR0ZW1wdCAke2F0dGVtcHQgKyAxfSB0byBzZW5kIGVtYWlsIHZpYSBTRVMgZmFpbGVkLiBSZXRyeWluZy4uLmAsIHtcbiAgICAgICAgICBlcnJvck1lc3NhZ2U6IGVycm9yLm1lc3NhZ2UsXG4gICAgICAgICAgcmVjaXBpZW50OiBlbWFpbERldGFpbHMudG8sXG4gICAgICAgICAgYXR0ZW1wdDogYXR0ZW1wdCArIDEsXG4gICAgICAgICAgbWF4UmV0cmllczogTUFYX1JFVFJJRVMsXG4gICAgICAgIH0pO1xuICAgICAgICBhdHRlbXB0Kys7XG4gICAgICAgIGlmIChhdHRlbXB0IDwgTUFYX1JFVFJJRVMpIHtcbiAgICAgICAgICBjb25zdCBkZWxheSA9IE1hdGgucG93KDIsIGF0dGVtcHQgLTEpICogMTAwMDsgLy8gRXhwb25lbnRpYWwgYmFja29mZjogMXMsIDJzXG4gICAgICAgICAgYXdhaXQgbmV3IFByb21pc2UocmVzb2x2ZSA9PiBzZXRUaW1lb3V0KHJlc29sdmUsIGRlbGF5KSk7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9XG5cbiAgICBsb2dnZXIuZXJyb3IoJ0Vycm9yIHNlbmRpbmcgZW1haWwgdmlhIEFXUyBTRVMgYWZ0ZXIgbXVsdGlwbGUgcmV0cmllczonLCB7XG4gICAgICBlcnJvck1lc3NhZ2U6IGxhc3RFcnJvcj8ubWVzc2FnZSxcbiAgICAgIGVycm9yU3RhY2s6IGxhc3RFcnJvcj8uc3RhY2ssXG4gICAgICBlcnJvckRldGFpbHM6IGxhc3RFcnJvcixcbiAgICAgIHJlY2lwaWVudDogZW1haWxEZXRhaWxzLnRvLFxuICAgIH0pO1xuICAgIHJldHVybiB7IHN1Y2Nlc3M6IGZhbHNlLCBtZXNzYWdlOiBgRmFpbGVkIHRvIHNlbmQgZW1haWwgdmlhIEFXUyBTRVMgYWZ0ZXIgJHtNQVhfUkVUUklFU30gYXR0ZW1wdHM6ICR7bGFzdEVycm9yPy5tZXNzYWdlfWAgfTtcbiAgfVxufVxuIl19