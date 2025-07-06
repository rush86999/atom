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

const example3 = buildGmailSearchQuery({
  subject: "Meeting Prep",
  after: "2023/10/20",
  before: "2023/10/25",
  customQuery: "(from:personA@example.com OR to:personA@example.com OR from:personB@example.com OR to:personB@example.com)",
  excludeChats: true
});
console.log(example3);
// Expected: subject:(Meeting Prep) after:2023/10/20 before:2023/10/25 (from:personA@example.com OR to:personA@example.com OR from:personB@example.com OR to:personB@example.com) NOT is:chat

const example4_onlyCustom = buildGmailSearchQuery({
    customQuery: "(from:boss@example.com OR to:boss@example.com) older_than:7d",
    excludeChats: false // test not excluding chats
});
console.log(example4_onlyCustom);
// Expected: (from:boss@example.com OR to:boss@example.com) older_than:7d
// Note: excludeChats: false means "NOT is:chat" is NOT added. If excludeChats is undefined, it defaults to true in searchEmailsForPrep.

const example5_empty = buildGmailSearchQuery({});
console.log(example5_empty);
// Expected: "" (or "NOT is:chat" if default excludeChats:true was part of this function, but it's not)
*/

/**
 * Parses a relative date query string (e.g., "today", "yesterday", "last 7 days")
 * and returns 'after' and 'before' dates in YYYY/MM/DD format.
 * @param dateQuery The relative date query string.
 * @param referenceDate The date to which the relative query is applied, defaults to today.
 * @returns An object with 'after' and 'before' date strings, or undefined if parsing fails.
 */
export function parseRelativeDateQuery(
    dateQuery: string,
    referenceDate: Date = new Date()
): { after?: string; before?: string } | undefined {
    const query = dateQuery.toLowerCase().trim();
    const today = new Date(referenceDate); // Use a copy of referenceDate
    today.setHours(0, 0, 0, 0); // Normalize to start of day

    const formatDate = (date: Date): string => {
        const year = date.getFullYear();
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const day = date.getDate().toString().padStart(2, '0');
        return `${year}/${month}/${day}`;
    };

    if (query === 'today') {
        const tomorrow = new Date(today);
        tomorrow.setDate(today.getDate() + 1);
        return { after: formatDate(today), before: formatDate(tomorrow) };
    }

    if (query === 'yesterday') {
        const yesterday = new Date(today);
        yesterday.setDate(today.getDate() - 1);
        return { after: formatDate(yesterday), before: formatDate(today) };
    }

    if (query === 'tomorrow') {
        const tomorrow = new Date(today);
        tomorrow.setDate(today.getDate() + 1);
        const dayAfterTomorrow = new Date(tomorrow);
        dayAfterTomorrow.setDate(tomorrow.getDate() + 1);
        return { after: formatDate(tomorrow), before: formatDate(dayAfterTomorrow) };
    }

    const lastNDaysMatch = query.match(/^last (\d+) days?$/);
    if (lastNDaysMatch) {
        const days = parseInt(lastNDaysMatch[1], 10);
        if (days > 0) {
            const pastDate = new Date(today);
            pastDate.setDate(today.getDate() - days);
            const dayAfterToday = new Date(today); // Search up to end of today
            dayAfterToday.setDate(today.getDate() + 1);
            return { after: formatDate(pastDate), before: formatDate(dayAfterToday) };
        }
    }

    const nextNDaysMatch = query.match(/^next (\d+) days?$/);
    if (nextNDaysMatch) {
        const days = parseInt(nextNDaysMatch[1], 10);
        if (days > 0) {
            const futureDate = new Date(today);
            futureDate.setDate(today.getDate() + days + 1); // +1 because 'before' is exclusive upper bound for the day
            const dayOfQuery = new Date(today); // Search from start of today
            return { after: formatDate(dayOfQuery), before: formatDate(futureDate) };
        }
    }

    // Add more specific cases like "this week", "last week", "this month", "last month" as needed.
    // For "this week" (assuming week starts on Sunday)
    if (query === "this week") {
        const firstDayOfWeek = new Date(today);
        firstDayOfWeek.setDate(today.getDate() - today.getDay()); // Sunday
        const lastDayOfWeek = new Date(firstDayOfWeek);
        lastDayOfWeek.setDate(firstDayOfWeek.getDate() + 7); // Next Sunday
        return { after: formatDate(firstDayOfWeek), before: formatDate(lastDayOfWeek) };
    }

    if (query === "last week") {
        const firstDayOfLastWeek = new Date(today);
        firstDayOfLastWeek.setDate(today.getDate() - today.getDay() - 7); // Previous Sunday
        const lastDayOfLastWeek = new Date(firstDayOfLastWeek);
        lastDayOfLastWeek.setDate(firstDayOfLastWeek.getDate() + 7); // End of last week (this Sunday)
        return { after: formatDate(firstDayOfLastWeek), before: formatDate(lastDayOfLastWeek) };
    }


    // If query is already in YYYY/MM/DD format for after/before, pass it through
    // This is a simple check, could be more robust with regex
    if (query.includes("after:") || query.includes("before:")) {
        let afterDate, beforeDate;
        const afterMatch = query.match(/after:(\d{4}\/\d{2}\/\d{2})/);
        if (afterMatch) afterDate = afterMatch[1];
        const beforeMatch = query.match(/before:(\d{4}\/\d{2}\/\d{2})/);
        if (beforeMatch) beforeDate = beforeMatch[1];
        if (afterDate || beforeDate) {
            return { after: afterDate, before: beforeDate };
        }
    }

    return undefined; // Query not recognized
}

/*
// Example Test Cases for parseRelativeDateQuery (assuming today is 2023-10-26)
const refDate = new Date("2023-10-26T10:00:00.000Z"); // Thursday

console.log("Today:", parseRelativeDateQuery("today", refDate));
// Expected: { after: "2023/10/26", before: "2023/10/27" }

console.log("Yesterday:", parseRelativeDateQuery("yesterday", refDate));
// Expected: { after: "2023/10/25", before: "2023/10/26" }

console.log("Tomorrow:", parseRelativeDateQuery("tomorrow", refDate));
// Expected: { after: "2023/10/27", before: "2023/10/28" }

console.log("Last 7 days:", parseRelativeDateQuery("last 7 days", refDate));
// Expected: { after: "2023/10/19", before: "2023/10/27" } (includes today in range)

console.log("Last 1 day:", parseRelativeDateQuery("last 1 day", refDate));
// Expected: { after: "2023/10/25", before: "2023/10/27" } (yesterday and today)

console.log("Next 3 days:", parseRelativeDateQuery("next 3 days", refDate));
// Expected: { after: "2023/10/26", before: "2023/10/30" } (today, tomorrow, day after, day after that is exclusive before)

console.log("This week (Sun-Sat):", parseRelativeDateQuery("this week", refDate)); // Assuming today is Thu, Oct 26, 2023
// Expected: { after: "2023/10/22", before: "2023/10/29" } (Sun Oct 22 to Sat Oct 28)

console.log("Last week (Sun-Sat):", parseRelativeDateQuery("last week", refDate));
// Expected: { after: "2023/10/15", before: "2023/10/22" } (Sun Oct 15 to Sat Oct 21)

console.log("after:2023/01/15:", parseRelativeDateQuery("after:2023/01/15", refDate));
// Expected: { after: "2023/01/15", before: undefined }

console.log("before:2024/01/01:", parseRelativeDateQuery("before:2024/01/01", refDate));
// Expected: { after: undefined, before: "2024/01/01" }

console.log("after:2023/05/10 before:2023/05/12:", parseRelativeDateQuery("after:2023/05/10 before:2023/05/12", refDate));
// Expected: { after: "2023/05/10", before: "2023/05/12" }

console.log("Invalid query:", parseRelativeDateQuery("random string", refDate));
// Expected: undefined
*/
