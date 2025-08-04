import { logger } from '../../_utils/logger';
/**
 * Constructs a Slack API compatible search query string from structured parameters.
 * Slack search operators documentation: https://slack.com/help/articles/202528808-Search-in-Slack
 * @param params StructuredSlackQuery object containing various search criteria.
 * @returns A string formatted for Slack API's 'search.messages' query parameter.
 */
export function buildSlackSearchQuery(params) {
    const queryParts = [];
    if (params.fromUser) {
        // Slack search syntax: from:@username or from:Display Name (can be tricky with spaces)
        // If it's already a user ID (Uxxxxxxxx), that's best.
        // For now, assuming NLU provides a usable name/ID. Resolution to ID should happen before this if possible,
        // or Slack search might handle some name resolutions.
        queryParts.push(`from:${params.fromUser.trim()}`);
    }
    if (params.inChannel) {
        // Slack search syntax: in:#channel-name or in:@direct-message-user or in:ChannelID
        queryParts.push(`in:${params.inChannel.trim()}`);
    }
    if (params.mentionsUser) {
        // Slack search syntax: mentions:@username or mentions:Display Name
        queryParts.push(`mentions:${params.mentionsUser.trim()}`);
    }
    if (params.textKeywords) {
        // General keywords are just added to the query string.
        queryParts.push(params.textKeywords.trim());
    }
    if (params.exactPhrase) {
        queryParts.push(`"${params.exactPhrase.trim()}"`);
    }
    if (params.hasFile) {
        queryParts.push('has:file');
    }
    if (params.hasLink) {
        queryParts.push('has:link');
    }
    if (params.hasReaction) {
        // Ensure emoji code is clean, e.g., :smile:
        const reactionCode = params.hasReaction.replace(/:/g, '');
        if (reactionCode) {
            queryParts.push(`has::${reactionCode}:`);
        }
    }
    // Date filters
    // Slack search uses "on", "before", "after", "during" (for months/years)
    // The LLM is prompted to provide YYYY-MM-DD format.
    if (params.onDate) {
        queryParts.push(`on:${params.onDate}`);
    }
    else {
        // 'onDate' is exclusive with 'beforeDate'/'afterDate' in typical usage
        if (params.afterDate) {
            queryParts.push(`after:${params.afterDate}`);
        }
        if (params.beforeDate) {
            queryParts.push(`before:${params.beforeDate}`);
        }
    }
    const finalQuery = queryParts
        .filter((part) => part.length > 0)
        .join(' ')
        .trim();
    logger.debug(`[NluSlackHelper] Built Slack search query: "${finalQuery}" from params:`, params);
    return finalQuery;
}
/*
// Example Usage:
const exampleParams1: StructuredSlackQuery = {
  fromUser: '@bob',
  textKeywords: 'Q1 report',
  inChannel: '#marketing',
  onDate: '2023-10-26',
};
console.log(`Example 1 Query: ${buildSlackSearchQuery(exampleParams1)}`);
// Expected: from:@bob in:#marketing on:2023-10-26 Q1 report (order may vary slightly but terms should be there)

const exampleParams2: StructuredSlackQuery = {
  hasFile: true,
  fromUser: 'Jane Doe',
  afterDate: '2023-09-01',
  beforeDate: '2023-09-30',
  textKeywords: 'PDF contract',
};
console.log(`Example 2 Query: ${buildSlackSearchQuery(exampleParams2)}`);
// Expected: has:file from:Jane Doe after:2023-09-01 before:2023-09-30 PDF contract

const exampleParams3: StructuredSlackQuery = {
  exactPhrase: 'project deadline extension',
  inChannel: '@alice', // DM with Alice
  hasReaction: ':eyes:',
};
console.log(`Example 3 Query: ${buildSlackSearchQuery(exampleParams3)}`);
// Expected: "project deadline extension" in:@alice has::eyes:
*/
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibmx1X3NsYWNrX2hlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIm5sdV9zbGFja19oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQ0EsT0FBTyxFQUFFLE1BQU0sRUFBRSxNQUFNLHFCQUFxQixDQUFDO0FBRTdDOzs7OztHQUtHO0FBQ0gsTUFBTSxVQUFVLHFCQUFxQixDQUFDLE1BQTRCO0lBQ2hFLE1BQU0sVUFBVSxHQUFhLEVBQUUsQ0FBQztJQUVoQyxJQUFJLE1BQU0sQ0FBQyxRQUFRLEVBQUUsQ0FBQztRQUNwQix1RkFBdUY7UUFDdkYsc0RBQXNEO1FBQ3RELDJHQUEyRztRQUMzRyxzREFBc0Q7UUFDdEQsVUFBVSxDQUFDLElBQUksQ0FBQyxRQUFRLE1BQU0sQ0FBQyxRQUFRLENBQUMsSUFBSSxFQUFFLEVBQUUsQ0FBQyxDQUFDO0lBQ3BELENBQUM7SUFFRCxJQUFJLE1BQU0sQ0FBQyxTQUFTLEVBQUUsQ0FBQztRQUNyQixtRkFBbUY7UUFDbkYsVUFBVSxDQUFDLElBQUksQ0FBQyxNQUFNLE1BQU0sQ0FBQyxTQUFTLENBQUMsSUFBSSxFQUFFLEVBQUUsQ0FBQyxDQUFDO0lBQ25ELENBQUM7SUFFRCxJQUFJLE1BQU0sQ0FBQyxZQUFZLEVBQUUsQ0FBQztRQUN4QixtRUFBbUU7UUFDbkUsVUFBVSxDQUFDLElBQUksQ0FBQyxZQUFZLE1BQU0sQ0FBQyxZQUFZLENBQUMsSUFBSSxFQUFFLEVBQUUsQ0FBQyxDQUFDO0lBQzVELENBQUM7SUFFRCxJQUFJLE1BQU0sQ0FBQyxZQUFZLEVBQUUsQ0FBQztRQUN4Qix1REFBdUQ7UUFDdkQsVUFBVSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQUMsWUFBWSxDQUFDLElBQUksRUFBRSxDQUFDLENBQUM7SUFDOUMsQ0FBQztJQUVELElBQUksTUFBTSxDQUFDLFdBQVcsRUFBRSxDQUFDO1FBQ3ZCLFVBQVUsQ0FBQyxJQUFJLENBQUMsSUFBSSxNQUFNLENBQUMsV0FBVyxDQUFDLElBQUksRUFBRSxHQUFHLENBQUMsQ0FBQztJQUNwRCxDQUFDO0lBRUQsSUFBSSxNQUFNLENBQUMsT0FBTyxFQUFFLENBQUM7UUFDbkIsVUFBVSxDQUFDLElBQUksQ0FBQyxVQUFVLENBQUMsQ0FBQztJQUM5QixDQUFDO0lBRUQsSUFBSSxNQUFNLENBQUMsT0FBTyxFQUFFLENBQUM7UUFDbkIsVUFBVSxDQUFDLElBQUksQ0FBQyxVQUFVLENBQUMsQ0FBQztJQUM5QixDQUFDO0lBRUQsSUFBSSxNQUFNLENBQUMsV0FBVyxFQUFFLENBQUM7UUFDdkIsNENBQTRDO1FBQzVDLE1BQU0sWUFBWSxHQUFHLE1BQU0sQ0FBQyxXQUFXLENBQUMsT0FBTyxDQUFDLElBQUksRUFBRSxFQUFFLENBQUMsQ0FBQztRQUMxRCxJQUFJLFlBQVksRUFBRSxDQUFDO1lBQ2pCLFVBQVUsQ0FBQyxJQUFJLENBQUMsUUFBUSxZQUFZLEdBQUcsQ0FBQyxDQUFDO1FBQzNDLENBQUM7SUFDSCxDQUFDO0lBRUQsZUFBZTtJQUNmLHlFQUF5RTtJQUN6RSxvREFBb0Q7SUFDcEQsSUFBSSxNQUFNLENBQUMsTUFBTSxFQUFFLENBQUM7UUFDbEIsVUFBVSxDQUFDLElBQUksQ0FBQyxNQUFNLE1BQU0sQ0FBQyxNQUFNLEVBQUUsQ0FBQyxDQUFDO0lBQ3pDLENBQUM7U0FBTSxDQUFDO1FBQ04sdUVBQXVFO1FBQ3ZFLElBQUksTUFBTSxDQUFDLFNBQVMsRUFBRSxDQUFDO1lBQ3JCLFVBQVUsQ0FBQyxJQUFJLENBQUMsU0FBUyxNQUFNLENBQUMsU0FBUyxFQUFFLENBQUMsQ0FBQztRQUMvQyxDQUFDO1FBQ0QsSUFBSSxNQUFNLENBQUMsVUFBVSxFQUFFLENBQUM7WUFDdEIsVUFBVSxDQUFDLElBQUksQ0FBQyxVQUFVLE1BQU0sQ0FBQyxVQUFVLEVBQUUsQ0FBQyxDQUFDO1FBQ2pELENBQUM7SUFDSCxDQUFDO0lBRUQsTUFBTSxVQUFVLEdBQUcsVUFBVTtTQUMxQixNQUFNLENBQUMsQ0FBQyxJQUFJLEVBQUUsRUFBRSxDQUFDLElBQUksQ0FBQyxNQUFNLEdBQUcsQ0FBQyxDQUFDO1NBQ2pDLElBQUksQ0FBQyxHQUFHLENBQUM7U0FDVCxJQUFJLEVBQUUsQ0FBQztJQUNWLE1BQU0sQ0FBQyxLQUFLLENBQ1YsK0NBQStDLFVBQVUsZ0JBQWdCLEVBQ3pFLE1BQU0sQ0FDUCxDQUFDO0lBQ0YsT0FBTyxVQUFVLENBQUM7QUFDcEIsQ0FBQztBQUVEOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0VBNEJFIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgU3RydWN0dXJlZFNsYWNrUXVlcnkgfSBmcm9tICcuL2xsbV9zbGFja19xdWVyeV91bmRlcnN0YW5kZXInOyAvLyBJbXBvcnQgdGhlIHN0cnVjdHVyZVxuaW1wb3J0IHsgbG9nZ2VyIH0gZnJvbSAnLi4vLi4vX3V0aWxzL2xvZ2dlcic7XG5cbi8qKlxuICogQ29uc3RydWN0cyBhIFNsYWNrIEFQSSBjb21wYXRpYmxlIHNlYXJjaCBxdWVyeSBzdHJpbmcgZnJvbSBzdHJ1Y3R1cmVkIHBhcmFtZXRlcnMuXG4gKiBTbGFjayBzZWFyY2ggb3BlcmF0b3JzIGRvY3VtZW50YXRpb246IGh0dHBzOi8vc2xhY2suY29tL2hlbHAvYXJ0aWNsZXMvMjAyNTI4ODA4LVNlYXJjaC1pbi1TbGFja1xuICogQHBhcmFtIHBhcmFtcyBTdHJ1Y3R1cmVkU2xhY2tRdWVyeSBvYmplY3QgY29udGFpbmluZyB2YXJpb3VzIHNlYXJjaCBjcml0ZXJpYS5cbiAqIEByZXR1cm5zIEEgc3RyaW5nIGZvcm1hdHRlZCBmb3IgU2xhY2sgQVBJJ3MgJ3NlYXJjaC5tZXNzYWdlcycgcXVlcnkgcGFyYW1ldGVyLlxuICovXG5leHBvcnQgZnVuY3Rpb24gYnVpbGRTbGFja1NlYXJjaFF1ZXJ5KHBhcmFtczogU3RydWN0dXJlZFNsYWNrUXVlcnkpOiBzdHJpbmcge1xuICBjb25zdCBxdWVyeVBhcnRzOiBzdHJpbmdbXSA9IFtdO1xuXG4gIGlmIChwYXJhbXMuZnJvbVVzZXIpIHtcbiAgICAvLyBTbGFjayBzZWFyY2ggc3ludGF4OiBmcm9tOkB1c2VybmFtZSBvciBmcm9tOkRpc3BsYXkgTmFtZSAoY2FuIGJlIHRyaWNreSB3aXRoIHNwYWNlcylcbiAgICAvLyBJZiBpdCdzIGFscmVhZHkgYSB1c2VyIElEIChVeHh4eHh4eHgpLCB0aGF0J3MgYmVzdC5cbiAgICAvLyBGb3Igbm93LCBhc3N1bWluZyBOTFUgcHJvdmlkZXMgYSB1c2FibGUgbmFtZS9JRC4gUmVzb2x1dGlvbiB0byBJRCBzaG91bGQgaGFwcGVuIGJlZm9yZSB0aGlzIGlmIHBvc3NpYmxlLFxuICAgIC8vIG9yIFNsYWNrIHNlYXJjaCBtaWdodCBoYW5kbGUgc29tZSBuYW1lIHJlc29sdXRpb25zLlxuICAgIHF1ZXJ5UGFydHMucHVzaChgZnJvbToke3BhcmFtcy5mcm9tVXNlci50cmltKCl9YCk7XG4gIH1cblxuICBpZiAocGFyYW1zLmluQ2hhbm5lbCkge1xuICAgIC8vIFNsYWNrIHNlYXJjaCBzeW50YXg6IGluOiNjaGFubmVsLW5hbWUgb3IgaW46QGRpcmVjdC1tZXNzYWdlLXVzZXIgb3IgaW46Q2hhbm5lbElEXG4gICAgcXVlcnlQYXJ0cy5wdXNoKGBpbjoke3BhcmFtcy5pbkNoYW5uZWwudHJpbSgpfWApO1xuICB9XG5cbiAgaWYgKHBhcmFtcy5tZW50aW9uc1VzZXIpIHtcbiAgICAvLyBTbGFjayBzZWFyY2ggc3ludGF4OiBtZW50aW9uczpAdXNlcm5hbWUgb3IgbWVudGlvbnM6RGlzcGxheSBOYW1lXG4gICAgcXVlcnlQYXJ0cy5wdXNoKGBtZW50aW9uczoke3BhcmFtcy5tZW50aW9uc1VzZXIudHJpbSgpfWApO1xuICB9XG5cbiAgaWYgKHBhcmFtcy50ZXh0S2V5d29yZHMpIHtcbiAgICAvLyBHZW5lcmFsIGtleXdvcmRzIGFyZSBqdXN0IGFkZGVkIHRvIHRoZSBxdWVyeSBzdHJpbmcuXG4gICAgcXVlcnlQYXJ0cy5wdXNoKHBhcmFtcy50ZXh0S2V5d29yZHMudHJpbSgpKTtcbiAgfVxuXG4gIGlmIChwYXJhbXMuZXhhY3RQaHJhc2UpIHtcbiAgICBxdWVyeVBhcnRzLnB1c2goYFwiJHtwYXJhbXMuZXhhY3RQaHJhc2UudHJpbSgpfVwiYCk7XG4gIH1cblxuICBpZiAocGFyYW1zLmhhc0ZpbGUpIHtcbiAgICBxdWVyeVBhcnRzLnB1c2goJ2hhczpmaWxlJyk7XG4gIH1cblxuICBpZiAocGFyYW1zLmhhc0xpbmspIHtcbiAgICBxdWVyeVBhcnRzLnB1c2goJ2hhczpsaW5rJyk7XG4gIH1cblxuICBpZiAocGFyYW1zLmhhc1JlYWN0aW9uKSB7XG4gICAgLy8gRW5zdXJlIGVtb2ppIGNvZGUgaXMgY2xlYW4sIGUuZy4sIDpzbWlsZTpcbiAgICBjb25zdCByZWFjdGlvbkNvZGUgPSBwYXJhbXMuaGFzUmVhY3Rpb24ucmVwbGFjZSgvOi9nLCAnJyk7XG4gICAgaWYgKHJlYWN0aW9uQ29kZSkge1xuICAgICAgcXVlcnlQYXJ0cy5wdXNoKGBoYXM6OiR7cmVhY3Rpb25Db2RlfTpgKTtcbiAgICB9XG4gIH1cblxuICAvLyBEYXRlIGZpbHRlcnNcbiAgLy8gU2xhY2sgc2VhcmNoIHVzZXMgXCJvblwiLCBcImJlZm9yZVwiLCBcImFmdGVyXCIsIFwiZHVyaW5nXCIgKGZvciBtb250aHMveWVhcnMpXG4gIC8vIFRoZSBMTE0gaXMgcHJvbXB0ZWQgdG8gcHJvdmlkZSBZWVlZLU1NLUREIGZvcm1hdC5cbiAgaWYgKHBhcmFtcy5vbkRhdGUpIHtcbiAgICBxdWVyeVBhcnRzLnB1c2goYG9uOiR7cGFyYW1zLm9uRGF0ZX1gKTtcbiAgfSBlbHNlIHtcbiAgICAvLyAnb25EYXRlJyBpcyBleGNsdXNpdmUgd2l0aCAnYmVmb3JlRGF0ZScvJ2FmdGVyRGF0ZScgaW4gdHlwaWNhbCB1c2FnZVxuICAgIGlmIChwYXJhbXMuYWZ0ZXJEYXRlKSB7XG4gICAgICBxdWVyeVBhcnRzLnB1c2goYGFmdGVyOiR7cGFyYW1zLmFmdGVyRGF0ZX1gKTtcbiAgICB9XG4gICAgaWYgKHBhcmFtcy5iZWZvcmVEYXRlKSB7XG4gICAgICBxdWVyeVBhcnRzLnB1c2goYGJlZm9yZToke3BhcmFtcy5iZWZvcmVEYXRlfWApO1xuICAgIH1cbiAgfVxuXG4gIGNvbnN0IGZpbmFsUXVlcnkgPSBxdWVyeVBhcnRzXG4gICAgLmZpbHRlcigocGFydCkgPT4gcGFydC5sZW5ndGggPiAwKVxuICAgIC5qb2luKCcgJylcbiAgICAudHJpbSgpO1xuICBsb2dnZXIuZGVidWcoXG4gICAgYFtObHVTbGFja0hlbHBlcl0gQnVpbHQgU2xhY2sgc2VhcmNoIHF1ZXJ5OiBcIiR7ZmluYWxRdWVyeX1cIiBmcm9tIHBhcmFtczpgLFxuICAgIHBhcmFtc1xuICApO1xuICByZXR1cm4gZmluYWxRdWVyeTtcbn1cblxuLypcbi8vIEV4YW1wbGUgVXNhZ2U6XG5jb25zdCBleGFtcGxlUGFyYW1zMTogU3RydWN0dXJlZFNsYWNrUXVlcnkgPSB7XG4gIGZyb21Vc2VyOiAnQGJvYicsXG4gIHRleHRLZXl3b3JkczogJ1ExIHJlcG9ydCcsXG4gIGluQ2hhbm5lbDogJyNtYXJrZXRpbmcnLFxuICBvbkRhdGU6ICcyMDIzLTEwLTI2Jyxcbn07XG5jb25zb2xlLmxvZyhgRXhhbXBsZSAxIFF1ZXJ5OiAke2J1aWxkU2xhY2tTZWFyY2hRdWVyeShleGFtcGxlUGFyYW1zMSl9YCk7XG4vLyBFeHBlY3RlZDogZnJvbTpAYm9iIGluOiNtYXJrZXRpbmcgb246MjAyMy0xMC0yNiBRMSByZXBvcnQgKG9yZGVyIG1heSB2YXJ5IHNsaWdodGx5IGJ1dCB0ZXJtcyBzaG91bGQgYmUgdGhlcmUpXG5cbmNvbnN0IGV4YW1wbGVQYXJhbXMyOiBTdHJ1Y3R1cmVkU2xhY2tRdWVyeSA9IHtcbiAgaGFzRmlsZTogdHJ1ZSxcbiAgZnJvbVVzZXI6ICdKYW5lIERvZScsXG4gIGFmdGVyRGF0ZTogJzIwMjMtMDktMDEnLFxuICBiZWZvcmVEYXRlOiAnMjAyMy0wOS0zMCcsXG4gIHRleHRLZXl3b3JkczogJ1BERiBjb250cmFjdCcsXG59O1xuY29uc29sZS5sb2coYEV4YW1wbGUgMiBRdWVyeTogJHtidWlsZFNsYWNrU2VhcmNoUXVlcnkoZXhhbXBsZVBhcmFtczIpfWApO1xuLy8gRXhwZWN0ZWQ6IGhhczpmaWxlIGZyb206SmFuZSBEb2UgYWZ0ZXI6MjAyMy0wOS0wMSBiZWZvcmU6MjAyMy0wOS0zMCBQREYgY29udHJhY3RcblxuY29uc3QgZXhhbXBsZVBhcmFtczM6IFN0cnVjdHVyZWRTbGFja1F1ZXJ5ID0ge1xuICBleGFjdFBocmFzZTogJ3Byb2plY3QgZGVhZGxpbmUgZXh0ZW5zaW9uJyxcbiAgaW5DaGFubmVsOiAnQGFsaWNlJywgLy8gRE0gd2l0aCBBbGljZVxuICBoYXNSZWFjdGlvbjogJzpleWVzOicsXG59O1xuY29uc29sZS5sb2coYEV4YW1wbGUgMyBRdWVyeTogJHtidWlsZFNsYWNrU2VhcmNoUXVlcnkoZXhhbXBsZVBhcmFtczMpfWApO1xuLy8gRXhwZWN0ZWQ6IFwicHJvamVjdCBkZWFkbGluZSBleHRlbnNpb25cIiBpbjpAYWxpY2UgaGFzOjpleWVzOlxuKi9cbiJdfQ==