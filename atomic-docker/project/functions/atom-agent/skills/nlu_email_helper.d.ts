export interface StructuredEmailQuery {
    from?: string;
    to?: string;
    subject?: string;
    bodyKeywords?: string;
    label?: string;
    after?: string;
    before?: string;
    hasAttachment?: boolean;
    exactPhrase?: string;
    customQuery?: string;
    excludeChats?: boolean;
}
/**
 * Constructs a Gmail API compatible search query string from structured parameters.
 * Gmail search operators documentation: https://support.google.com/mail/answer/7190?hl=en
 * @param params StructuredEmailQuery object containing various search criteria.
 * @returns A string formatted for Gmail API's 'q' (query) parameter.
 */
export declare function buildGmailSearchQuery(params: StructuredEmailQuery): string;
/**
 * (Helper for LLM - not directly used by agent skill for query construction, but for prompt context)
 * This function is intended to format date conditions for the LLM prompt, ensuring it knows
 * how to interpret relative dates.
 * @param dateConditionText e.g., "today", "last week", "since Monday"
 * @param currentDate The actual current date (YYYY/MM/DD)
 * @returns A string explanation for the LLM, or null if not a special relative term.
 */
export declare function getRelativeDateInterpretationForLLM(dateConditionText: string, currentDate: string): string | null;
/**
 * Parses a relative date query string (e.g., "today", "yesterday", "last 7 days")
 * and returns 'after' and 'before' dates in YYYY/MM/DD format.
 * @param dateQuery The relative date query string.
 * @param referenceDate The date to which the relative query is applied, defaults to today.
 * @returns An object with 'after' and 'before' date strings, or undefined if parsing fails.
 */
export declare function parseRelativeDateQuery(dateQuery: string, referenceDate?: Date): {
    after?: string;
    before?: string;
} | undefined;
