import { Email, SendEmailResponse, ReadEmailResponse, GmailMessagePart } from '../types'; // Assuming GmailMessagePart might be useful from types
import fetch from 'node-fetch'; // For making HTTP requests if not using Apollo Client

// Helper to call Hasura Actions (simplified)
// In a real app, use a configured Apollo Client or a more robust fetch wrapper.
const HASURA_GRAPHQL_ENDPOINT = process.env.HASURA_GRAPHQL_ENDPOINT || 'http://localhost:8080/v1/graphql';
const HASURA_ACTION_HEADERS = (userId: string) => ({
    'Content-Type': 'application/json',
    // If your Hasura actions require admin secret for this internal call:
    // ...(process.env.HASURA_ADMIN_SECRET ? { 'x-hasura-admin-secret': process.env.HASURA_ADMIN_SECRET } : {}),
    // If actions are permissioned for 'user' role and expect X-Hasura-User-Id:
    'X-Hasura-Role': 'user',
    'X-Hasura-User-Id': userId,
});

async function callHasuraActionGraphQL(userId: string, query: string, variables: Record<string, any>) {
    try {
        const response = await fetch(HASURA_GRAPHQL_ENDPOINT, {
            method: 'POST',
            headers: HASURA_ACTION_HEADERS(userId),
            body: JSON.stringify({ query, variables }),
        });

        if (!response.ok) {
            const errorBody = await response.text();
            console.error(`Hasura GQL call failed with status ${response.status}: ${errorBody}`);
            throw new Error(`Hasura GQL call failed: ${response.statusText}`);
        }
        const jsonResponse = await response.json();
        if (jsonResponse.errors) {
            console.error(`Hasura GQL call returned errors: ${JSON.stringify(jsonResponse.errors)}`);
            throw new Error(`Hasura GQL call returned errors: ${jsonResponse.errors.map((e: any) => e.message).join(', ')}`);
        }
        return jsonResponse.data;
    } catch (error) {
        console.error('Error calling Hasura Action GQL:', error);
        throw error; // Re-throw to be handled by the skill
    }
}


// Renamed listRecentEmails to reflect its new capability
export async function searchMyEmails(userId: string, searchQuery: string, limit: number = 10): Promise<Email[]> {
  console.log(`Searching emails for user ${userId} with query "${searchQuery}", limit ${limit}...`);

  const GQL_SEARCH_EMAILS = `
    mutation SearchUserGmail($input: GmailSearchQueryInput!) {
      searchUserGmail(input: $input) {
        success
        message
        results {
          id
          threadId
          snippet
          # Placeholders from GQL schema, actual data depends on searchUserGmail handler
          subject
          from
          date
        }
      }
    }
  `;

  try {
    const responseData = await callHasuraActionGraphQL(userId, GQL_SEARCH_EMAILS, {
        input: { query: searchQuery, maxResults: limit }
    });

    const searchResult = responseData.searchUserGmail;

    if (!searchResult.success) {
      console.error(`searchUserGmail action failed: ${searchResult.message}`);
      return []; // Or throw error
    }

    // Transform GmailSearchResultItem to Agent's Email type
    return (searchResult.results || []).map((item: any): Email => ({
      id: item.id,
      threadId: item.threadId,
      sender: item.from || 'N/A', // Placeholder data from GQL schema
      recipient: 'me', // Assuming 'me' for now
      subject: item.subject || 'No Subject', // Placeholder
      body: item.snippet || '', // Use snippet as body preview
      timestamp: item.date || new Date().toISOString(), // Placeholder
      read: false, // Cannot determine read status from search result snippet alone
    }));

  } catch (error) {
    console.error(`Error in searchMyEmails skill for user ${userId}:`, error);
    return []; // Return empty or throw
  }
}

// Helper to find and decode text/plain or text/html body from Gmail payload
function extractReadableBody(part: any, preferredType: 'text/plain' | 'text/html' = 'text/plain'): string | null {
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
  console.log(`Reading email with ID: ${emailId} for user ${userId}`);

  const GQL_GET_EMAIL_CONTENT = `
    mutation GetUserGmailContent($input: GetUserGmailContentInput!) {
      getUserGmailContent(input: $input) {
        success
        message
        email {
          id
          threadId
          snippet
          payload {
            headers { name value }
            mimeType
            body { data size }
            parts { # Recursive parts for full body traversal
              partId mimeType filename headers { name value } body { data size attachmentId }
              parts {
                partId mimeType filename headers { name value } body { data size attachmentId }
                parts { # Deeper nesting if necessary
                  partId mimeType filename headers { name value } body { data size attachmentId }
                }
              }
            }
          }
          # Other fields from GmailMessageContent if needed
          # internalDate, labelIds, etc.
        }
      }
    }
  `;

  try {
    const responseData = await callHasuraActionGraphQL(userId, GQL_GET_EMAIL_CONTENT, {
        input: { emailId }
    });

    const getResult = responseData.getUserGmailContent;

    if (!getResult.success || !getResult.email) {
      console.error(`getUserGmailContent action failed or email not found: ${getResult.message}`);
      return { success: false, message: getResult.message || `Email ${emailId} not found.` };
    }

    const fetchedEmail = getResult.email;

    // Extract relevant info for the agent's Email type
    const headers = fetchedEmail.payload?.headers || [];
    const subject = headers.find(h => h.name?.toLowerCase() === 'subject')?.value || 'No Subject';
    const from = headers.find(h => h.name?.toLowerCase() === 'from')?.value || 'N/A';
    const to = headers.find(h => h.name?.toLowerCase() === 'to')?.value || 'N/A';
    // A more robust date parsing would be needed if internalDate is not directly usable
    const timestamp = fetchedEmail.internalDate ? new Date(parseInt(fetchedEmail.internalDate)).toISOString() : new Date().toISOString();

    // Use the enhanced body extraction logic
    const body = extractReadableBody(fetchedEmail.payload) || fetchedEmail.snippet || '';


    const email: Email = {
      id: fetchedEmail.id,
      threadId: fetchedEmail.threadId,
      sender: from,
      recipient: to,
      subject: subject,
      body: body,
      timestamp: timestamp,
      read: true, // Assume read since we fetched full content. Gmail API can provide 'UNREAD' in labelIds.
    };
    return { success: true, email };

  } catch (error) {
    console.error(`Error in readEmail skill for user ${userId}, emailId ${emailId}:`, error);
    return { success: false, message: (error as Error).message || 'Failed to read email.' };
  }
}

import OpenAI from 'openai'; // Required for LLM-based extraction
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
    const data = await client.send(command);
    logger.info('Email sent successfully via SES.', { messageId: data.MessageId });
    return { success: true, emailId: data.MessageId, message: 'Email sent successfully via AWS SES.' };
  } catch (error: any) {
    logger.error('Error sending email via AWS SES:', {
      errorMessage: error.message,
      errorStack: error.stack,
      errorDetails: error,
      recipient: emailDetails.to,
    });
    return { success: false, message: `Failed to send email via AWS SES: ${error.message}` };
  }
}
