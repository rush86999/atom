// Helper functions for NLU processing related to email skills
/**
 * Constructs a Gmail API compatible search query string from structured parameters.
 * Gmail search operators documentation: https://support.google.com/mail/answer/7190?hl=en
 * @param params StructuredEmailQuery object containing various search criteria.
 * @returns A string formatted for Gmail API's 'q' (query) parameter.
 */
export function buildGmailSearchQuery(params) {
    const queryParts = [];
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
    }
    else if (params.hasAttachment === false) {
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
    const builtQuery = queryParts
        .filter((part) => part.length > 0)
        .join(' ')
        .trim();
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
export function getRelativeDateInterpretationForLLM(dateConditionText, currentDate) {
    const lowerText = dateConditionText.toLowerCase();
    // This is illustrative. More robust parsing would be needed for complex relative dates.
    if (lowerText === 'yesterday')
        return `Yesterday (day before ${currentDate})`;
    if (lowerText === 'today')
        return `Today (${currentDate})`;
    if (lowerText === 'tomorrow')
        return `Tomorrow (day after ${currentDate})`;
    if (lowerText === 'last week')
        return `The full calendar week before the week of ${currentDate}`;
    if (lowerText === 'this week')
        return `The current calendar week containing ${currentDate}`;
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
export function parseRelativeDateQuery(dateQuery, referenceDate = new Date()) {
    const query = dateQuery.toLowerCase().trim();
    const today = new Date(referenceDate); // Use a copy of referenceDate
    today.setHours(0, 0, 0, 0); // Normalize to start of day
    const formatDate = (date) => {
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
        return {
            after: formatDate(tomorrow),
            before: formatDate(dayAfterTomorrow),
        };
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
    if (query === 'this week') {
        const firstDayOfWeek = new Date(today);
        firstDayOfWeek.setDate(today.getDate() - today.getDay()); // Sunday
        const lastDayOfWeek = new Date(firstDayOfWeek);
        lastDayOfWeek.setDate(firstDayOfWeek.getDate() + 7); // Next Sunday
        return {
            after: formatDate(firstDayOfWeek),
            before: formatDate(lastDayOfWeek),
        };
    }
    if (query === 'last week') {
        const firstDayOfLastWeek = new Date(today);
        firstDayOfLastWeek.setDate(today.getDate() - today.getDay() - 7); // Previous Sunday
        const lastDayOfLastWeek = new Date(firstDayOfLastWeek);
        lastDayOfLastWeek.setDate(firstDayOfLastWeek.getDate() + 7); // End of last week (this Sunday)
        return {
            after: formatDate(firstDayOfLastWeek),
            before: formatDate(lastDayOfLastWeek),
        };
    }
    // If query is already in YYYY/MM/DD format for after/before, pass it through
    // This is a simple check, could be more robust with regex
    if (query.includes('after:') || query.includes('before:')) {
        let afterDate, beforeDate;
        const afterMatch = query.match(/after:(\d{4}\/\d{2}\/\d{2})/);
        if (afterMatch)
            afterDate = afterMatch[1];
        const beforeMatch = query.match(/before:(\d{4}\/\d{2}\/\d{2})/);
        if (beforeMatch)
            beforeDate = beforeMatch[1];
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibmx1X2VtYWlsX2hlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIm5sdV9lbWFpbF9oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsOERBQThEO0FBZ0I5RDs7Ozs7R0FLRztBQUNILE1BQU0sVUFBVSxxQkFBcUIsQ0FBQyxNQUE0QjtJQUNoRSxNQUFNLFVBQVUsR0FBYSxFQUFFLENBQUM7SUFFaEMsSUFBSSxNQUFNLENBQUMsSUFBSSxFQUFFLENBQUM7UUFDaEIscUhBQXFIO1FBQ3JILFVBQVUsQ0FBQyxJQUFJLENBQUMsU0FBUyxNQUFNLENBQUMsSUFBSSxDQUFDLElBQUksRUFBRSxHQUFHLENBQUMsQ0FBQztJQUNsRCxDQUFDO0lBQ0QsSUFBSSxNQUFNLENBQUMsRUFBRSxFQUFFLENBQUM7UUFDZCxVQUFVLENBQUMsSUFBSSxDQUFDLE9BQU8sTUFBTSxDQUFDLEVBQUUsQ0FBQyxJQUFJLEVBQUUsR0FBRyxDQUFDLENBQUM7SUFDOUMsQ0FBQztJQUNELElBQUksTUFBTSxDQUFDLE9BQU8sRUFBRSxDQUFDO1FBQ25CLGdHQUFnRztRQUNoRyxVQUFVLENBQUMsSUFBSSxDQUFDLFlBQVksTUFBTSxDQUFDLE9BQU8sQ0FBQyxJQUFJLEVBQUUsR0FBRyxDQUFDLENBQUM7SUFDeEQsQ0FBQztJQUNELElBQUksTUFBTSxDQUFDLFlBQVksRUFBRSxDQUFDO1FBQ3hCLHNEQUFzRDtRQUN0RCxzREFBc0Q7UUFDdEQsVUFBVSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQUMsWUFBWSxDQUFDLElBQUksRUFBRSxDQUFDLENBQUM7SUFDOUMsQ0FBQztJQUNELElBQUksTUFBTSxDQUFDLFdBQVcsRUFBRSxDQUFDO1FBQ3ZCLFVBQVUsQ0FBQyxJQUFJLENBQUMsSUFBSSxNQUFNLENBQUMsV0FBVyxDQUFDLElBQUksRUFBRSxHQUFHLENBQUMsQ0FBQztJQUNwRCxDQUFDO0lBQ0QsSUFBSSxNQUFNLENBQUMsS0FBSyxFQUFFLENBQUM7UUFDakIs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SSxTQUFTLElBQUksVUFBVSxFQUFFLENBQUM7WUFDNUIsT0FBTyxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsTUFBTSxFQUFFLFVBQVUsRUFBRSxDQUFDO1FBQ2xELENBQUM7SUFDSCxDQUFDO0lBRUQsT0FBTyxTQUFTLENBQUMsQ0FBQyx1QkFBdUI7QUFDM0MsQ0FBQztBQUVEOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7RUF1Q0UiLCJzb3VyY2VzQ29udGVudCI6WyIvLyBIZWxwZXIgZnVuY3Rpb25zIGZvciBOTFUgcHJvY2Vzc2luZyByZWxhdGVkIHRvIGVtYWlsIHNraWxsc1xuXG5leHBvcnQgaW50ZXJmYWNlIFN0cnVjdHVyZWRFbWFpbFF1ZXJ5IHtcbiAgZnJvbT86IHN0cmluZztcbiAgdG8/OiBzdHJpbmc7XG4gIHN1YmplY3Q/OiBzdHJpbmc7XG4gIGJvZHlLZXl3b3Jkcz86IHN0cmluZzsgLy8gS2V5d29yZHMgdG8gc2VhcmNoIGluIHRoZSBlbWFpbCBib2R5XG4gIGxhYmVsPzogc3RyaW5nO1xuICBhZnRlcj86IHN0cmluZzsgLy8gRXhwZWN0ZWQgZm9ybWF0OiBZWVlZL01NL0REXG4gIGJlZm9yZT86IHN0cmluZzsgLy8gRXhwZWN0ZWQgZm9ybWF0OiBZWVlZL01NL0REXG4gIGhhc0F0dGFjaG1lbnQ/OiBib29sZWFuO1xuICBleGFjdFBocmFzZT86IHN0cmluZzsgLy8gRm9yIHNlYXJjaGluZyBhbiBleGFjdCBwaHJhc2VcbiAgY3VzdG9tUXVlcnk/OiBzdHJpbmc7IC8vIEFsbG93IHBhc3NpbmcgYSByYXcgcXVlcnkgcGFydCB0byBiZSBhcHBlbmRlZFxuICBleGNsdWRlQ2hhdHM/OiBib29sZWFuOyAvLyBFeHBsaWNpdGx5IGV4Y2x1ZGUgY2hhdCBtZXNzYWdlc1xufVxuXG4vKipcbiAqIENvbnN0cnVjdHMgYSBHbWFpbCBBUEkgY29tcGF0aWJsZSBzZWFyY2ggcXVlcnkgc3RyaW5nIGZyb20gc3RydWN0dXJlZCBwYXJhbWV0ZXJzLlxuICogR21haWwgc2VhcmNoIG9wZXJhdG9ycyBkb2N1bWVudGF0aW9uOiBodHRwczovL3N1cHBvcnQuZ29vZ2xlLmNvbS9tYWlsL2Fuc3dlci83MTkwP2hsPWVuXG4gKiBAcGFyYW0gcGFyYW1zIFN0cnVjdHVyZWRFbWFpbFF1ZXJ5IG9iamVjdCBjb250YWluaW5nIHZhcmlvdXMgc2VhcmNoIGNyaXRlcmlhLlxuICogQHJldHVybnMgQSBzdHJpbmcgZm9ybWF0dGVkIGZvciBHbWFpbCBBUEkncyAncScgKHF1ZXJ5KSBwYXJhbWV0ZXIuXG4gKi9cbmV4cG9ydCBmdW5jdGlvbiBidWlsZEdtYWlsU2VhcmNoUXVlcnkocGFyYW1zOiBTdHJ1Y3R1cmVkRW1haWxRdWVyeSk6IHN0cmluZyB7XG4gIGNvbnN0IHF1ZXJ5UGFydHM6IHN0cmluZ1tdID0gW107XG5cbiAgaWYgKHBhcmFtcy5mcm9tKSB7XG4gICAgLy8gVXNpbmcgcGFyZW50aGVzZXMgY2FuIGhlbHAgaWYgJ2Zyb20nIGNvbnRhaW5zIG11bHRpcGxlIG5hbWVzL2VtYWlscywgdGhvdWdoIEdtYWlsIGlzIHVzdWFsbHkgZ29vZCB3aXRoIGBmcm9tOm5hbWVgXG4gICAgcXVlcnlQYXJ0cy5wdXNoKGBmcm9tOigke3BhcmFtcy5mcm9tLnRyaW0oKX0pYCk7XG4gIH1cbiAgaWYgKHBhcmFtcy50bykge1xuICAgIHF1ZXJ5UGFydHMucHVzaChgdG86KCR7cGFyYW1zLnRvLnRyaW0oKX0pYCk7XG4gIH1cbiAgaWYgKHBhcmFtcy5zdWJqZWN0KSB7XG4gICAgLy8gRm9yIG11bHRpcGxlIHN1YmplY3Qga2V5d29yZHMsIGxldCBOTFUgcHJvdmlkZSB0aGVtIHNwYWNlLXNlcGFyYXRlZCBlLmcuLCBcImltcG9ydGFudCBwcm9qZWN0XCJcbiAgICBxdWVyeVBhcnRzLnB1c2goYHN1YmplY3Q6KCR7cGFyYW1zLnN1YmplY3QudHJpbSgpfSlgKTtcbiAgfVxuICBpZiAocGFyYW1zLmJvZHlLZXl3b3Jkcykge1xuICAgIC8vIEtleXdvcmRzIGZvciBib2R5IHNlYXJjaCBhcmUgdHlwaWNhbGx5IGp1c3QgbGlzdGVkLlxuICAgIC8vIElmIGl0J3MgYW4gZXhhY3QgcGhyYXNlLCB1c2UgZXhhY3RQaHJhc2UgcGFyYW1ldGVyLlxuICAgIHF1ZXJ5UGFydHMucHVzaChwYXJhbXMuYm9keUtleXdvcmRzLnRyaW0oKSk7XG4gIH1cbiAgaWYgKHBhcmFtcy5leGFjdFBocmFzZSkge1xuICAgIHF1ZXJ5UGFydHMucHVzaChgXCIke3BhcmFtcy5leGFjdFBocmFzZS50cmltKCl9XCJgKTtcbiAgfVxuICBpZiAocGFyYW1zLmxhYmVsKSB7XG4gICAgLy8gTGFiZWxzIHdpdGggc3BhY2VzIHNob3VsZCBiZSBoeXBoZW5hdGVkIG9yIHF1b3RlZCwgZS5nLiwgXCJteS1sYWJlbFwiIG9yIFwiXFxcIm15IGxhYmVsXFxcIlwiXG4gICAgLy8gQXNzdW1pbmcgTkxVIHByb3ZpZGVzIGNsZWFuIGxhYmVsIG5hbWVzLlxuICAgIHF1ZXJ5UGFydHMucHVzaChcbiAgICAgIGBsYWJlbDoke3BhcmFtcy5sYWJlbC50cmltKCkucmVwbGFjZSgvXFxzKy9nLCAnLScpLnRvTG93ZXJDYXNlKCl9YFxuICAgICk7XG4gIH1cbiAgaWYgKHBhcmFtcy5hZnRlcikge1xuICAgIHF1ZXJ5UGFydHMucHVzaChgYWZ0ZXI6JHtwYXJhbXMuYWZ0ZXIudHJpbSgpfWApO1xuICB9XG4gIGlmIChwYXJhbXMuYmVmb3JlKSB7XG4gICAgcXVlcnlQYXJ0cy5wdXNoKGBiZWZvcmU6JHtwYXJhbXMuYmVmb3JlLnRyaW0oKX1gKTtcbiAgfVxuICBpZiAocGFyYW1zLmhhc0F0dGFjaG1lbnQgPT09IHRydWUpIHtcbiAgICBxdWVyeVBhcnRzLnB1c2goJ2hhczphdHRhY2htZW50Jyk7XG4gIH0gZWxzZSBpZiAocGFyYW1zLmhhc0F0dGFjaG1lbnQgPT09IGZhbHNlKSB7XG4gICAgLy8gTm90ZTogR21haWwgZG9lc24ndCBoYXZlIGEgZGlyZWN0IFwiLWhhczphdHRhY2htZW50XCIgaW4gdGhlIHNhbWUgd2F5LlxuICAgIC8vIFRoaXMgbWlnaHQgbmVlZCB0byBiZSBoYW5kbGVkIGJ5IGZpbHRlcmluZyByZXN1bHRzIG9yIGJ5IG5vdCBhZGRpbmcgdGhpcyBwYXJ0LlxuICAgIC8vIEZvciBub3csIG9taXR0aW5nIHRoZSAnZmFsc2UnIGNhc2UgZm9yIGRpcmVjdCBxdWVyeS5cbiAgfVxuICBpZiAocGFyYW1zLmV4Y2x1ZGVDaGF0cyA9PT0gdHJ1ZSkge1xuICAgIHF1ZXJ5UGFydHMucHVzaCgnTk9UIGlzOmNoYXQnKTtcbiAgfVxuICBpZiAocGFyYW1zLmN1c3RvbVF1ZXJ5KSB7XG4gICAgcXVlcnlQYXJ0cy5wdXNoKHBhcmFtcy5jdXN0b21RdWVyeS50cmltKCkpO1xuICB9XG5cbiAgY29uc3QgYnVpbHRRdWVyeSA9IHF1ZXJ5UGFydHNcbiAgICAuZmlsdGVyKChwYXJ0KSA9PiBwYXJ0Lmxlbmd0aCA+IDApXG4gICAgLmpvaW4oJyAnKVxuICAgIC50cmltKCk7XG5cbiAgLy8gSWYgc3RydWN0dXJlZCBwYXJzaW5nIHJlc3VsdHMgaW4gYW4gZW1wdHkgcXVlcnksIGJ1dCBhIHJhdyBxdWVyeSB3YXMgcHJvdmlkZWQgKGFzIGZhbGxiYWNrIGZyb20gc2tpbGwpLCB1c2UgcmF3LlxuICAvLyBUaGUgcmF3UXVlcnlGYWxsYmFjayBpcyBhbiBhZGRpdGlvbiB0byB0aGUgZnVuY3Rpb24gc2lnbmF0dXJlLlxuICAvLyBUaGlzIGxvZ2ljIGlzIGJldHRlciBoYW5kbGVkIGluIHRoZSBjYWxsaW5nIHNraWxsIChnbWFpbFNraWxscy50cykgYWN0dWFsbHksXG4gIC8vIGFzIGJ1aWxkR21haWxTZWFyY2hRdWVyeSBzaG91bGQgcHVyZWx5IHRyYW5zbGF0ZSBzdHJ1Y3R1cmVkIHRvIHN0cmluZy5cbiAgLy8gVGhlIHNraWxsIGNhbiBkZWNpZGUgaWYgdGhlIHN0cnVjdHVyZWQgcXVlcnkgaXMgdG9vIHNwYXJzZSBhbmQgdGhlbiB1c2UgcmF3LlxuICAvLyBTbywgSSB3aWxsIHJlbW92ZSB0aGlzIHJhd1F1ZXJ5RmFsbGJhY2sgbG9naWMgZnJvbSBoZXJlIGFuZCBlbnN1cmUgaXQncyBpbiBnbWFpbFNraWxscy50cy5cblxuICByZXR1cm4gYnVpbHRRdWVyeTtcbn1cblxuLyoqXG4gKiAoSGVscGVyIGZvciBMTE0gLSBub3QgZGlyZWN0bHkgdXNlZCBieSBhZ2VudCBza2lsbCBmb3IgcXVlcnkgY29uc3RydWN0aW9uLCBidXQgZm9yIHByb21wdCBjb250ZXh0KVxuICogVGhpcyBmdW5jdGlvbiBpcyBpbnRlbmRlZCB0byBmb3JtYXQgZGF0ZSBjb25kaXRpb25zIGZvciB0aGUgTExNIHByb21wdCwgZW5zdXJpbmcgaXQga25vd3NcbiAqIGhvdyB0byBpbnRlcnByZXQgcmVsYXRpdmUgZGF0ZXMuXG4gKiBAcGFyYW0gZGF0ZUNvbmRpdGlvblRleHQgZS5nLiwgXCJ0b2RheVwiLCBcImxhc3Qgd2Vla1wiLCBcInNpbmNlIE1vbmRheVwiXG4gKiBAcGFyYW0gY3VycmVudERhdGUgVGhlIGFjdHVhbCBjdXJyZW50IGRhdGUgKFlZWVkvTU0vREQpXG4gKiBAcmV0dXJucyBBIHN0cmluZyBleHBsYW5hdGlvbiBmb3IgdGhlIExMTSwgb3IgbnVsbCBpZiBub3QgYSBzcGVjaWFsIHJlbGF0aXZlIHRlcm0uXG4gKi9cbmV4cG9ydCBmdW5jdGlvbiBnZXRSZWxhdGl2ZURhdGVJbnRlcnByZXRhdGlvbkZvckxMTShcbiAgZGF0ZUNvbmRpdGlvblRleHQ6IHN0cmluZyxcbiAgY3VycmVudERhdGU6IHN0cmluZ1xuKTogc3RyaW5nIHwgbnVsbCB7XG4gIGNvbnN0IGxvd2VyVGV4dCA9IGRhdGVDb25kaXRpb25UZXh0LnRvTG93ZXJDYXNlKCk7XG4gIC8vIFRoaXMgaXMgaWxsdXN0cmF0aXZlLiBNb3JlIHJvYnVzdCBwYXJzaW5nIHdvdWxkIGJlIG5lZWRlZCBmb3IgY29tcGxleCByZWxhdGl2ZSBkYXRlcy5cbiAgaWYgKGxvd2VyVGV4dCA9PT0gJ3llc3RlcmRheScpIHJldHVybiBgWWVzdGVyZGF5IChkYXkgYmVmb3JlICR7Y3VycmVudERhdGV9KWA7XG4gIGlmIChsb3dlclRleHQgPT09ICd0b2RheScpIHJldHVybiBgVG9kYXkgKCR7Y3VycmVudERhdGV9KWA7XG4gIGlmIChsb3dlclRleHQgPT09ICd0b21vcnJvdycpIHJldHVybiBgVG9tb3Jyb3cgKGRheSBhZnRlciAke2N1cnJlbnREYXRlfSlgO1xuICBpZiAobG93ZXJUZXh0ID09PSAnbGFzdCB3ZWVrJylcbiAgICByZXR1cm4gYFRoZSBmdWxsIGNhbGVuZGFyIHdlZWsgYmVmb3JlIHRoZSB3ZWVrIG9mICR7Y3VycmVudERhdGV9YDtcbiAgaWYgKGxvd2VyVGV4dCA9PT0gJ3RoaXMgd2VlaycpXG4gICAgcmV0dXJuIGBUaGUgY3VycmVudCBjYWxlbmRhciB3ZWVrIGNvbnRhaW5pbmcgJHtjdXJyZW50RGF0ZX1gO1xuICAvLyBBZGQgbW9yZSBjYXNlcyBhcyBuZWVkZWQgYnkgdGhlIExMTSBwcm9tcHQgZm9yIGRhdGUgaW5mZXJlbmNlLlxuICByZXR1cm4gbnVsbDtcbn1cblxuLypcbi8vIEV4YW1wbGUgVXNhZ2U6XG5jb25zdCBleGFtcGxlMSA9IGJ1aWxkR21haWxTZWFyY2hRdWVyeSh7XG4gIGZyb206ICdqYW5lLmRvZUBleGFtcGxlLmNvbScsXG4gIHN1YmplY3Q6ICdQcm9qZWN0IFVwZGF0ZSBRMycsXG4gIGFmdGVyOiAnMjAyMy8wNy8wMScsXG4gIGJlZm9yZTogJzIwMjMvMDkvMzAnLFxuICBib2R5S2V5d29yZHM6ICdzdW1tYXJ5IHJlcG9ydCcsXG4gIGV4Y2x1ZGVDaGF0czogdHJ1ZSxcbn0pO1xuY29uc29sZS5sb2coZXhhbXBsZTEpO1xuLy8gRXhwZWN0ZWQ6IGZyb206KGphbmUuZG9lQGV4YW1wbGUuY29tKSBzdWJqZWN0OihQcm9qZWN0IFVwZGF0ZSBRMykgYWZ0ZXI6MjAyMy8wNy8wMSBiZWZvcmU6MjAyMy8wOS8zMCBzdW1tYXJ5IHJlcG9ydCBOT1QgaXM6Y2hhdFxuXG5jb25zdCBleGFtcGxlMiA9IGJ1aWxkR21haWxTZWFyY2hRdWVyeSh7XG4gIGV4YWN0UGhyYXNlOiBcImNvbnRyYWN0IHJlbmV3YWwgdGVybXNcIixcbiAgbGFiZWw6IFwiaW1wb3J0YW50LWNvbnRyYWN0c1wiLFxuICBoYXNBdHRhY2htZW50OiB0cnVlXG59KTtcbmNvbnNvbGUubG9nKGV4YW1wbGUyKTtcbi8vIEV4cGVjdGVkOiBcImNvbnRyYWN0IHJlbmV3YWwgdGVybXNcIiBsYWJlbDppbXBvcnRhbnQtY29udHJhY3RzIGhhczphdHRhY2htZW50XG5cbmNvbnN0IGV4YW1wbGUzID0gYnVpbGRHbWFpbFNlYXJjaFF1ZXJ5KHtcbiAgc3ViamVjdDogXCJNZWV0aW5nIFByZXBcIixcbiAgYWZ0ZXI6IFwiMjAyMy8xMC8yMFwiLFxuICBiZWZvcmU6IFwiMjAyMy8xMC8yNVwiLFxuICBjdXN0b21RdWVyeTogXCIoZnJvbTpwZXJzb25BQGV4YW1wbGUuY29tIE9SIHRvOnBlcnNvbkFAZXhhbXBsZS5jb20gT1IgZnJvbTpwZXJzb25CQGV4YW1wbGUuY29tIE9SIHRvOnBlcnNvbkJAZXhhbXBsZS5jb20pXCIsXG4gIGV4Y2x1ZGVDaGF0czogdHJ1ZVxufSk7XG5jb25zb2xlLmxvZyhleGFtcGxlMyk7XG4vLyBFeHBlY3RlZDogc3ViamVjdDooTWVldGluZyBQcmVwKSBhZnRlcjoyMDIzLzEwLzIwIGJlZm9yZToyMDIzLzEwLzI1IChmcm9tOnBlcnNvbkFAZXhhbXBsZS5jb20gT1IgdG86cGVyc29uQUBleGFtcGxlLmNvbSBPUiBmcm9tOnBlcnNvbkJAZXhhbXBsZS5jb20gT1IgdG86cGVyc29uQkBleGFtcGxlLmNvbSkgTk9UIGlzOmNoYXRcblxuY29uc3QgZXhhbXBsZTRfb25seUN1c3RvbSA9IGJ1aWxkR21haWxTZWFyY2hRdWVyeSh7XG4gICAgY3VzdG9tUXVlcnk6IFwiKGZyb206Ym9zc0BleGFtcGxlLmNvbSBPUiB0bzpib3NzQGV4YW1wbGUuY29tKSBvbGRlcl90aGFuOjdkXCIsXG4gICAgZXhjbHVkZUNoYXRzOiBmYWxzZSAvLyB0ZXN0IG5vdCBleGNsdWRpbmcgY2hhdHNcbn0pO1xuY29uc29sZS5sb2coZXhhbXBsZTRfb25seUN1c3RvbSk7XG4vLyBFeHBlY3RlZDogKGZyb206Ym9zc0BleGFtcGxlLmNvbSBPUiB0bzpib3NzQGV4YW1wbGUuY29tKSBvbGRlcl90aGFuOjdkXG4vLyBOb3RlOiBleGNsdWRlQ2hhdHM6IGZhbHNlIG1lYW5zIFwiTk9UIGlzOmNoYXRcIiBpcyBOT1QgYWRkZWQuIElmIGV4Y2x1ZGVDaGF0cyBpcyB1bmRlZmluZWQsIGl0IGRlZmF1bHRzIHRvIHRydWUgaW4gc2VhcmNoRW1haWxzRm9yUHJlcC5cblxuY29uc3QgZXhhbXBsZTVfZW1wdHkgPSBidWlsZEdtYWlsU2VhcmNoUXVlcnkoe30pO1xuY29uc29sZS5sb2coZXhhbXBsZTVfZW1wdHkpO1xuLy8gRXhwZWN0ZWQ6IFwiXCIgKG9yIFwiTk9UIGlzOmNoYXRcIiBpZiBkZWZhdWx0IGV4Y2x1ZGVDaGF0czp0cnVlIHdhcyBwYXJ0IG9mIHRoaXMgZnVuY3Rpb24sIGJ1dCBpdCdzIG5vdClcbiovXG5cbi8qKlxuICogUGFyc2VzIGEgcmVsYXRpdmUgZGF0ZSBxdWVyeSBzdHJpbmcgKGUuZy4sIFwidG9kYXlcIiwgXCJ5ZXN0ZXJkYXlcIiwgXCJsYXN0IDcgZGF5c1wiKVxuICogYW5kIHJldHVybnMgJ2FmdGVyJyBhbmQgJ2JlZm9yZScgZGF0ZXMgaW4gWVlZWS9NTS9ERCBmb3JtYXQuXG4gKiBAcGFyYW0gZGF0ZVF1ZXJ5IFRoZSByZWxhdGl2ZSBkYXRlIHF1ZXJ5IHN0cmluZy5cbiAqIEBwYXJhbSByZWZlcmVuY2VEYXRlIFRoZSBkYXRlIHRvIHdoaWNoIHRoZSByZWxhdGl2ZSBxdWVyeSBpcyBhcHBsaWVkLCBkZWZhdWx0cyB0byB0b2RheS5cbiAqIEByZXR1cm5zIEFuIG9iamVjdCB3aXRoICdhZnRlcicgYW5kICdiZWZvcmUnIGRhdGUgc3RyaW5ncywgb3IgdW5kZWZpbmVkIGlmIHBhcnNpbmcgZmFpbHMuXG4gKi9cbmV4cG9ydCBmdW5jdGlvbiBwYXJzZVJlbGF0aXZlRGF0ZVF1ZXJ5KFxuICBkYXRlUXVlcnk6IHN0cmluZyxcbiAgcmVmZXJlbmNlRGF0ZTogRGF0ZSA9IG5ldyBEYXRlKClcbik6IHsgYWZ0ZXI/OiBzdHJpbmc7IGJlZm9yZT86IHN0cmluZyB9IHwgdW5kZWZpbmVkIHtcbiAgY29uc3QgcXVlcnkgPSBkYXRlUXVlcnkudG9Mb3dlckNhc2UoKS50cmltKCk7XG4gIGNvbnN0IHRvZGF5ID0gbmV3IERhdGUocmVmZXJlbmNlRGF0ZSk7IC8vIFVzZSBhIGNvcHkgb2YgcmVmZXJlbmNlRGF0ZVxuICB0b2RheS5zZXRIb3VycygwLCAwLCAwLCAwKTsgLy8gTm9ybWFsaXplIHRvIHN0YXJ0IG9mIGRheVxuXG4gIGNvbnN0IGZvcm1hdERhdGUgPSAoZGF0ZTogRGF0ZSk6IHN0cmluZyA9PiB7XG4gICAgY29uc3QgeWVhciA9IGRhdGUuZ2V0RnVsbFllYXIoKTtcbiAgICBjb25zdCBtb250aCA9IChkYXRlLmdldE1vbnRoKCkgKyAxKS50b1N0cmluZygpLnBhZFN0YXJ0KDIsICcwJyk7XG4gICAgY29uc3QgZGF5ID0gZGF0ZS5nZXREYXRlKCkudG9TdHJpbmcoKS5wYWRTdGFydCgyLCAnMCcpO1xuICAgIHJldHVybiBgJHt5ZWFyfS8ke21vbnRofS8ke2RheX1gO1xuICB9O1xuXG4gIGlmIChxdWVyeSA9PT0gJ3RvZGF5Jykge1xuICAgIGNvbnN0IHRvbW9ycm93ID0gbmV3IERhdGUodG9kYXkpO1xuICAgIHRvbW9ycm93LnNldERhdGUodG9kYXkuZ2V0RGF0ZSgpICsgMSk7XG4gICAgcmV0dXJuIHsgYWZ0ZXI6IGZvcm1hdERhdGUodG9kYXkpLCBiZWZvcmU6IGZvcm1hdERhdGUodG9tb3Jyb3cpIH07XG4gIH1cblxuICBpZiAocXVlcnkgPT09ICd5ZXN0ZXJkYXknKSB7XG4gICAgY29uc3QgeWVzdGVyZGF5ID0gbmV3IERhdGUodG9kYXkpO1xuICAgIHllc3RlcmRheS5zZXREYXRlKHRvZGF5LmdldERhdGUoKSAtIDEpO1xuICAgIHJldHVybiB7IGFmdGVyOiBmb3JtYXREYXRlKHllc3RlcmRheSksIGJlZm9yZTogZm9ybWF0RGF0ZSh0b2RheSkgfTtcbiAgfVxuXG4gIGlmIChxdWVyeSA9PT0gJ3RvbW9ycm93Jykge1xuICAgIGNvbnN0IHRvbW9ycm93ID0gbmV3IERhdGUodG9kYXkpO1xuICAgIHRvbW9ycm93LnNldERhdGUodG9kYXkuZ2V0RGF0ZSgpICsgMSk7XG4gICAgY29uc3QgZGF5QWZ0ZXJUb21vcnJvdyA9IG5ldyBEYXRlKHRvbW9ycm93KTtcbiAgICBkYXlBZnRlclRvbW9ycm93LnNldERhdGUodG9tb3Jyb3cuZ2V0RGF0ZSgpICsgMSk7XG4gICAgcmV0dXJuIHtcbiAgICAgIGFmdGVyOiBmb3JtYXREYXRlKHRvbW9ycm93KSxcbiAgICAgIGJlZm9yZTogZm9ybWF0RGF0ZShkYXlBZnRlclRvbW9ycm93KSxcbiAgICB9O1xuICB9XG5cbiAgY29uc3QgbGFzdE5EYXlzTWF0Y2ggPSBxdWVyeS5tYXRjaCgvXmxhc3QgKFxcZCspIGRheXM/JC8pO1xuICBpZiAobGFzdE5EYXlzTWF0Y2gpIHtcbiAgICBjb25zdCBkYXlzID0gcGFyc2VJbnQobGFzdE5EYXlzTWF0Y2hbMV0sIDEwKTtcbiAgICBpZiAoZGF5cyA+IDApIHtcbiAgICAgIGNvbnN0IHBhc3REYXRlID0gbmV3IERhdGUodG9kYXkpO1xuICAgICAgcGFzdERhdGUuc2V0RGF0ZSh0b2RheS5nZXREYXRlKCkgLSBkYXlzKTtcbiAgICAgIGNvbnN0IGRheUFmdGVyVG9kYXkgPSBuZXcgRGF0ZSh0b2RheSk7IC8vIFNlYXJjaCB1cCB0byBlbmQgb2YgdG9kYXlcbiAgICAgIGRheUFmdGVyVG9kYXkuc2V0RGF0ZSh0b2RheS5nZXREYXRlKCkgKyAxKTtcbiAgICAgIHJldHVybiB7IGFmdGVyOiBmb3JtYXREYXRlKHBhc3REYXRlKSwgYmVmb3JlOiBmb3JtYXREYXRlKGRheUFmdGVyVG9kYXkpIH07XG4gICAgfVxuICB9XG5cbiAgY29uc3QgbmV4dE5EYXlzTWF0Y2ggPSBxdWVyeS5tYXRjaCgvXm5leHQgKFxcZCspIGRheXM/JC8pO1xuICBpZiAobmV4dE5EYXlzTWF0Y2gpIHtcbiAgICBjb25zdCBkYXlzID0gcGFyc2VJbnQobmV4dE5EYXlzTWF0Y2hbMV0sIDEwKTtcbiAgICBpZiAoZGF5cyA+IDApIHtcbiAgICAgIGNvbnN0IGZ1dHVyZURhdGUgPSBuZXcgRGF0ZSh0b2RheSk7XG4gICAgICBmdXR1cmVEYXRlLnNldERhdGUodG9kYXkuZ2V0RGF0ZSgpICsgZGF5cyArIDEpOyAvLyArMSBiZWNhdXNlICdiZWZvcmUnIGlzIGV4Y2x1c2l2ZSB1cHBlciBib3VuZCBmb3IgdGhlIGRheVxuICAgICAgY29uc3QgZGF5T2ZRdWVyeSA9IG5ldyBEYXRlKHRvZGF5KTsgLy8gU2VhcmNoIGZyb20gc3RhcnQgb2YgdG9kYXlcbiAgICAgIHJldHVybiB7IGFmdGVyOiBmb3JtYXREYXRlKGRheU9mUXVlcnkpLCBiZWZvcmU6IGZvcm1hdERhdGUoZnV0dXJlRGF0ZSkgfTtcbiAgICB9XG4gIH1cblxuICAvLyBBZGQgbW9yZSBzcGVjaWZpYyBjYXNlcyBsaWtlIFwidGhpcyB3ZWVrXCIsIFwibGFzdCB3ZWVrXCIsIFwidGhpcyBtb250aFwiLCBcImxhc3QgbW9udGhcIiBhcyBuZWVkZWQuXG4gIC8vIEZvciBcInRoaXMgd2Vla1wiIChhc3N1bWluZyB3ZWVrIHN0YXJ0cyBvbiBTdW5kYXkpXG4gIGlmIChxdWVyeSA9PT0gJ3RoaXMgd2VlaycpIHtcbiAgICBjb25zdCBmaXJzdERheU9mV2VlayA9IG5ldyBEYXRlKHRvZGF5KTtcbiAgICBmaXJzdERheU9mV2Vlay5zZXREYXRlKHRvZGF5LmdldERhdGUoKSAtIHRvZGF5LmdldERheSgpKTsgLy8gU3VuZGF5XG4gICAgY29uc3QgbGFzdERheU9mV2VlayA9IG5ldyBEYXRlKGZpcnN0RGF5T2ZXZWVrKTtcbiAgICBsYXN0RGF5T2ZXZWVrLnNldERhdGUoZmlyc3REYXlPZldlZWsuZ2V0RGF0ZSgpICsgNyk7IC8vIE5leHQgU3VuZGF5XG4gICAgcmV0dXJuIHtcbiAgICAgIGFmdGVyOiBmb3JtYXREYXRlKGZpcnN0RGF5T2ZXZWVrKSxcbiAgICAgIGJlZm9yZTogZm9ybWF0RGF0ZShsYXN0RGF5T2ZXZWVrKSxcbiAgICB9O1xuICB9XG5cbiAgaWYgKHF1ZXJ5ID09PSAnbGFzdCB3ZWVrJykge1xuICAgIGNvbnN0IGZpcnN0RGF5T2ZMYXN0V2VlayA9IG5ldyBEYXRlKHRvZGF5KTtcbiAgICBmaXJzdERheU9mTGFzdFdlZWsuc2V0RGF0ZSh0b2RheS5nZXREYXRlKCkgLSB0b2RheS5nZXREYXkoKSAtIDcpOyAvLyBQcmV2aW91cyBTdW5kYXlcbiAgICBjb25zdCBsYXN0RGF5T2ZMYXN0V2VlayA9IG5ldyBEYXRlKGZpcnN0RGF5T2ZMYXN0V2Vlayk7XG4gICAgbGFzdERheU9mTGFzdFdlZWsuc2V0RGF0ZShmaXJzdERheU9mTGFzdFdlZWsuZ2V0RGF0ZSgpICsgNyk7IC8vIEVuZCBvZiBsYXN0IHdlZWsgKHRoaXMgU3VuZGF5KVxuICAgIHJldHVybiB7XG4gICAgICBhZnRlcjogZm9ybWF0RGF0ZShmaXJzdERheU9mTGFzdFdlZWspLFxuICAgICAgYmVmb3JlOiBmb3JtYXREYXRlKGxhc3REYXlPZkxhc3RXZWVrKSxcbiAgICB9O1xuICB9XG5cbiAgLy8gSWYgcXVlcnkgaXMgYWxyZWFkeSBpbiBZWVlZL01NL0REIGZvcm1hdCBmb3IgYWZ0ZXIvYmVmb3JlLCBwYXNzIGl0IHRocm91Z2hcbiAgLy8gVGhpcyBpcyBhIHNpbXBsZSBjaGVjaywgY291bGQgYmUgbW9yZSByb2J1c3Qgd2l0aCByZWdleFxuICBpZiAocXVlcnkuaW5jbHVkZXMoJ2FmdGVyOicpIHx8IHF1ZXJ5LmluY2x1ZGVzKCdiZWZvcmU6JykpIHtcbiAgICBsZXQgYWZ0ZXJEYXRlLCBiZWZvcmVEYXRlO1xuICAgIGNvbnN0IGFmdGVyTWF0Y2ggPSBxdWVyeS5tYXRjaCgvYWZ0ZXI6KFxcZHs0fVxcL1xcZHsyfVxcL1xcZHsyfSkvKTtcbiAgICBpZiAoYWZ0ZXJNYXRjaCkgYWZ0ZXJEYXRlID0gYWZ0ZXJNYXRjaFsxXTtcbiAgICBjb25zdCBiZWZvcmVNYXRjaCA9IHF1ZXJ5Lm1hdGNoKC9iZWZvcmU6KFxcZHs0fVxcL1xcZHsyfVxcL1xcZHsyfSkvKTtcbiAgICBpZiAoYmVmb3JlTWF0Y2gpIGJlZm9yZURhdGUgPSBiZWZvcmVNYXRjaFsxXTtcbiAgICBpZiAoYWZ0ZXJEYXRlIHx8IGJlZm9yZURhdGUpIHtcbiAgICAgIHJldHVybiB7IGFmdGVyOiBhZnRlckRhdGUsIGJlZm9yZTogYmVmb3JlRGF0ZSB9O1xuICAgIH1cbiAgfVxuXG4gIHJldHVybiB1bmRlZmluZWQ7IC8vIFF1ZXJ5IG5vdCByZWNvZ25pemVkXG59XG5cbi8qXG4vLyBFeGFtcGxlIFRlc3QgQ2FzZXMgZm9yIHBhcnNlUmVsYXRpdmVEYXRlUXVlcnkgKGFzc3VtaW5nIHRvZGF5IGlzIDIwMjMtMTAtMjYpXG5jb25zdCByZWZEYXRlID0gbmV3IERhdGUoXCIyMDIzLTEwLTI2VDEwOjAwOjAwLjAwMFpcIik7IC8vIFRodXJzZGF5XG5cbmNvbnNvbGUubG9nKFwiVG9kYXk6XCIsIHBhcnNlUmVsYXRpdmVEYXRlUXVlcnkoXCJ0b2RheVwiLCByZWZEYXRlKSk7XG4vLyBFeHBlY3RlZDogeyBhZnRlcjogXCIyMDIzLzEwLzI2XCIsIGJlZm9yZTogXCIyMDIzLzEwLzI3XCIgfVxuXG5jb25zb2xlLmxvZyhcIlllc3RlcmRheTpcIiwgcGFyc2VSZWxhdGl2ZURhdGVRdWVyeShcInllc3RlcmRheVwiLCByZWZEYXRlKSk7XG4vLyBFeHBlY3RlZDogeyBhZnRlcjogXCIyMDIzLzEwLzI1XCIsIGJlZm9yZTogXCIyMDIzLzEwLzI2XCIgfVxuXG5jb25zb2xlLmxvZyhcIlRvbW9ycm93OlwiLCBwYXJzZVJlbGF0aXZlRGF0ZVF1ZXJ5KFwidG9tb3Jyb3dcIiwgcmVmRGF0ZSkpO1xuLy8gRXhwZWN0ZWQ6IHsgYWZ0ZXI6IFwiMjAyMy8xMC8yN1wiLCBiZWZvcmU6IFwiMjAyMy8xMC8yOFwiIH1cblxuY29uc29sZS5sb2coXCJMYXN0IDcgZGF5czpcIiwgcGFyc2VSZWxhdGl2ZURhdGVRdWVyeShcImxhc3QgNyBkYXlzXCIsIHJlZkRhdGUpKTtcbi8vIEV4cGVjdGVkOiB7IGFmdGVyOiBcIjIwMjMvMTAvMTlcIiwgYmVmb3JlOiBcIjIwMjMvMTAvMjdcIiB9IChpbmNsdWRlcyB0b2RheSBpbiByYW5nZSlcblxuY29uc29sZS5sb2coXCJMYXN0IDEgZGF5OlwiLCBwYXJzZVJlbGF0aXZlRGF0ZVF1ZXJ5KFwibGFzdCAxIGRheVwiLCByZWZEYXRlKSk7XG4vLyBFeHBlY3RlZDogeyBhZnRlcjogXCIyMDIzLzEwLzI1XCIsIGJlZm9yZTogXCIyMDIzLzEwLzI3XCIgfSAoeWVzdGVyZGF5IGFuZCB0b2RheSlcblxuY29uc29sZS5sb2coXCJOZXh0IDMgZGF5czpcIiwgcGFyc2VSZWxhdGl2ZURhdGVRdWVyeShcIm5leHQgMyBkYXlzXCIsIHJlZkRhdGUpKTtcbi8vIEV4cGVjdGVkOiB7IGFmdGVyOiBcIjIwMjMvMTAvMjZcIiwgYmVmb3JlOiBcIjIwMjMvMTAvMzBcIiB9ICh0b2RheSwgdG9tb3Jyb3csIGRheSBhZnRlciwgZGF5IGFmdGVyIHRoYXQgaXMgZXhjbHVzaXZlIGJlZm9yZSlcblxuY29uc29sZS5sb2coXCJUaGlzIHdlZWsgKFN1bi1TYXQpOlwiLCBwYXJzZVJlbGF0aXZlRGF0ZVF1ZXJ5KFwidGhpcyB3ZWVrXCIsIHJlZkRhdGUpKTsgLy8gQXNzdW1pbmcgdG9kYXkgaXMgVGh1LCBPY3QgMjYsIDIwMjNcbi8vIEV4cGVjdGVkOiB7IGFmdGVyOiBcIjIwMjMvMTAvMjJcIiwgYmVmb3JlOiBcIjIwMjMvMTAvMjlcIiB9IChTdW4gT2N0IDIyIHRvIFNhdCBPY3QgMjgpXG5cbmNvbnNvbGUubG9nKFwiTGFzdCB3ZWVrIChTdW4tU2F0KTpcIiwgcGFyc2VSZWxhdGl2ZURhdGVRdWVyeShcImxhc3Qgd2Vla1wiLCByZWZEYXRlKSk7XG4vLyBFeHBlY3RlZDogeyBhZnRlcjogXCIyMDIzLzEwLzE1XCIsIGJlZm9yZTogXCIyMDIzLzEwLzIyXCIgfSAoU3VuIE9jdCAxNSB0byBTYXQgT2N0IDIxKVxuXG5jb25zb2xlLmxvZyhcImFmdGVyOjIwMjMvMDEvMTU6XCIsIHBhcnNlUmVsYXRpdmVEYXRlUXVlcnkoXCJhZnRlcjoyMDIzLzAxLzE1XCIsIHJlZkRhdGUpKTtcbi8vIEV4cGVjdGVkOiB7IGFmdGVyOiBcIjIwMjMvMDEvMTVcIiwgYmVmb3JlOiB1bmRlZmluZWQgfVxuXG5jb25zb2xlLmxvZyhcImJlZm9yZToyMDI0LzAxLzAxOlwiLCBwYXJzZVJlbGF0aXZlRGF0ZVF1ZXJ5KFwiYmVmb3JlOjIwMjQvMDEvMDFcIiwgcmVmRGF0ZSkpO1xuLy8gRXhwZWN0ZWQ6IHsgYWZ0ZXI6IHVuZGVmaW5lZCwgYmVmb3JlOiBcIjIwMjQvMDEvMDFcIiB9XG5cbmNvbnNvbGUubG9nKFwiYWZ0ZXI6MjAyMy8wNS8xMCBiZWZvcmU6MjAyMy8wNS8xMjpcIiwgcGFyc2VSZWxhdGl2ZURhdGVRdWVyeShcImFmdGVyOjIwMjMvMDUvMTAgYmVmb3JlOjIwMjMvMDUvMTJcIiwgcmVmRGF0ZSkpO1xuLy8gRXhwZWN0ZWQ6IHsgYWZ0ZXI6IFwiMjAyMy8wNS8xMFwiLCBiZWZvcmU6IFwiMjAyMy8wNS8xMlwiIH1cblxuY29uc29sZS5sb2coXCJJbnZhbGlkIHF1ZXJ5OlwiLCBwYXJzZVJlbGF0aXZlRGF0ZVF1ZXJ5KFwicmFuZG9tIHN0cmluZ1wiLCByZWZEYXRlKSk7XG4vLyBFeHBlY3RlZDogdW5kZWZpbmVkXG4qL1xuIl19