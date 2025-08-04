import { StructuredEmailQuery } from './nlu_email_helper';
/**
 * Uses an LLM to understand a natural language email query and transform it
 * into a StructuredEmailQuery object.
 * @param rawUserQuery The user's natural language query about finding emails.
 * @returns A Promise resolving to a Partial<StructuredEmailQuery> object.
 * @throws Error if LLM call fails or parsing is unsuccessful.
 */
export declare function understandEmailSearchQueryLLM(rawUserQuery: string): Promise<Partial<StructuredEmailQuery>>;
import { EmailDetails } from './emailSkills';
/**
 * (Placeholder) Uses an LLM to understand a natural language command for sending an email
 * and transform it into an EmailDetails object.
 * @param rawUserQuery The user's natural language command for sending an email.
 * @returns A Promise resolving to a Partial<EmailDetails> object.
 * @throws Error if LLM call fails or parsing is unsuccessful.
 */
export declare function understandEmailSendCommandLLM(rawUserQuery: string): Promise<Partial<EmailDetails>>;
