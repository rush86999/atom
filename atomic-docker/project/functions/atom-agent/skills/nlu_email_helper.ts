// Helper functions for NLU processing related to email skills

export interface StructuredEmailQuery {
  from?: string;
  to?: string;
  subject?: string;
  bodyKeywords?: string; // Keywords to search in the email body
  label?: string;
  after?: string;     // Expected format: YYYY/MM/DD
  before?: string;    // Expected format: YYYY/MM/DD
  hasAttachment?: boolean;
  exactPhrase?: string; // For searching an exact phrase
  customQuery?: string; // Allow passing a raw query part to be appended
  excludeChats?: boolean; // Explicitly exclude chat messages
}

/**
 * Constructs a Gmail API compatible search query string from structured parameters.
 * Gmail search operators documentation: https://support.google.com/mail/answer/7190?hl=en
 * @param params StructuredEmailQuery object containing various search criteria.
 * @returns A string formatted for Gmail API's 'q' (query) parameter.
 */
export function buildGmailSearchQuery(params: StructuredEmailQuery): string {
  const queryParts: string[] = [];

  if (params.from) {
    // Using parentheses can help if 'from' contains multiple names/emails, though Gmail is usually good with `from:name`
    queryParts.push(`from:(${params.from.trim()})`);
  }
  if (params.to) {
    queryParts.push(`to:(${params.to.trim()})`);
  }
  if (params.subject) {
    // For multiple subject keywords, let NLU provide them space-separated e.g., "important project"
    queryParts.push(`subject:(${params.subject.trim()})`);
  }
  if (params.bodyKeywords) {
    // Keywords for body search are typically just listed.
    // If it's an exact phrase, use exactPhrase parameter.
    queryParts.push(params.bodyKeywords.trim());
  }
  if (params.exactPhrase) {
    queryParts.push(`"${params.exactPhrase.trim()}"`);
  }
  if (params.label) {
    // Labels with spaces should be hyphenated or quoted, e.g., "my-label" or "\"my label\""
    // Assuming NLU provides clean label names.
    queryParts.push(`label:${params.label.trim().replace(/\s+/g, '-').toLowerCase()}`);
  }
  if (params.after) {
    queryParts.push(`after:${params.after.trim()}`);
  }
  if (params.before) {
    queryParts.push(`before:${params.before.trim()}`);
  }
  if (params.hasAttachment === true) {
    queryParts.push('has:attachment');
  } else if (params.hasAttachment === false) {
    // Note: Gmail doesn't have a direct "-has:attachment" in the same way.
    // This might need to be handled by filtering results or by not adding this part.
    // For now, omitting the 'false' case for direct query.
  }
  if (params.excludeChats === true) {
    queryParts.push('NOT is:chat');
  }
  if (params.customQuery) {
    queryParts.push(params.customQuery.trim());
  }

  const builtQuery = queryParts.filter(part => part.length > 0).join(' ').trim();

  // If structured parsing results in an empty query, but a raw query was provided (as fallback from skill), use raw.
  // The rawQueryFallback is an addition to the function signature.
  // This logic is better handled in the calling skill (gmailSkills.ts) actually,
  // as buildGmailSearchQuery should purely translate structured to string.
  // The skill can decide if the structured query is too sparse and then use raw.
  // So, I will remove this rawQueryFallback logic from here and ensure it's in gmailSkills.ts.

  return builtQuery;
}

/**
 * (Helper for LLM - not directly used by agent skill for query construction, but for prompt context)
 * This function is intended to format date conditions for the LLM prompt, ensuring it knows
 * how to interpret relative dates.
 * @param dateConditionText e.g., "today", "last week", "since Monday"
 * @param currentDate The actual current date (YYYY/MM/DD)
 * @returns A string explanation for the LLM, or null if not a special relative term.
 */
export function getRelativeDateInterpretationForLLM(dateConditionText: string, currentDate: string): string | null {
    const lowerText = dateConditionText.toLowerCase();
    // This is illustrative. More robust parsing would be needed for complex relative dates.
    if (lowerText === "yesterday") return `Yesterday (day before ${currentDate})`;
    if (lowerText === "today") return `Today (${currentDate})`;
    if (lowerText === "tomorrow") return `Tomorrow (day after ${currentDate})`;
    if (lowerText === "last week") return `The full calendar week before the week of ${currentDate}`;
    if (lowerText === "this week") return `The current calendar week containing ${currentDate}`;
    // Add more cases as needed by the LLM prompt for date inference.
    return null;
}


/*
// Example Usage:
const example1 = buildGmailSearchQuery({
  from: 'jane.doe@example.com',
  subject: 'Project Update Q3',
  after: '2023/07/01',
  before: '2023/09/30',
  bodyKeywords: 'summary report',
  excludeChats: true,
});
console.log(example1);
// Expected: from:(jane.doe@example.com) subject:(Project Update Q3) after:2023/07/01 before:2023/09/30 summary report NOT is:chat

const example2 = buildGmailSearchQuery({
  exactPhrase: "contract renewal terms",
  label: "important-contracts",
  hasAttachment: true
});
console.log(example2);
// Expected: "contract renewal terms" label:important-contracts has:attachment
*/
