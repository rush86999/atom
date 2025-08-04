import { logger } from '../../_utils/logger';
/**
 * Constructs a Keyword Query Language (KQL) string for Microsoft Graph Search API
 * from structured parameters.
 * Ref for KQL: https://learn.microsoft.com/en-us/sharepoint/dev/general-development/keyword-query-language-kql-syntax-reference
 * Ref for Graph Search on messages: https://learn.microsoft.com/en-us/graph/search-concept-chatmessage
 *
 * @param params StructuredMSTeamsQuery object containing various search criteria.
 * @returns A KQL string formatted for Microsoft Graph API's search query.
 */
export function buildMSTeamsSearchQuery(params) {
    const kqlParts = [];
    // Free-text keywords (these usually come first or without a specific property)
    if (params.textKeywords) {
        kqlParts.push(params.textKeywords.trim());
    }
    if (params.exactPhrase) {
        kqlParts.push(`"${params.exactPhrase.trim()}"`);
    }
    // Property-restricted queries
    if (params.fromUser) {
        // Graph search can often resolve names/emails for 'from'
        kqlParts.push(`from:${params.fromUser.trim()}`);
    }
    if (params.mentionsUser) {
        // KQL for mentions might be `participants:"John Doe"` or checking body/content.
        // For simplicity, we can add it as a keyword or assume Graph Search handles "mentions:User Name".
        // A more specific KQL might be `mentions:${params.mentionsUser.trim()}` if supported or by adding to text.
        // Let's assume for now that adding it as a keyword is a starting point,
        // or specific Graph properties like `summary` might include mentions.
        // For direct KQL, `participants` is more about who is in the chat.
        // `mentions` isn't a standard KQL property for messages in the same way as `from`.
        // So, we might add it to the general text search or expect the LLM to have incorporated it.
        // Adding as a keyword for now:
        kqlParts.push(`"${params.mentionsUser.trim()}"`); // Treat as part of text search
    }
    if (params.inChatOrChannel) {
        // This is complex. KQL doesn't have a direct "inChatOrChannel" property.
        // This usually needs to be handled by targeting the search scope (e.g. a specific chat ID or channel ID in the API call)
        // or by using properties like `parentfolderid` or `siteid` if searching within SharePoint context of Teams files.
        // For messages, the search endpoint itself might be scoped, or `chatId` / `channelId` used in a different way.
        // For a general search query, we might include it as text:
        kqlParts.push(`"${params.inChatOrChannel.trim()}"`);
    }
    if (params.subjectContains) {
        // `subject` is a common KQL property
        kqlParts.push(`subject:${params.subjectContains.trim()}`);
    }
    if (params.hasFile) {
        // KQL for attachments: `hasattachment:true`
        kqlParts.push('hasattachment:true');
    }
    if (params.hasLink) {
        // KQL for links: `containslink:true` (this is more SharePoint specific)
        // For messages, might need to search for "http" or "https" as keywords.
        kqlParts.push('(http OR https)');
    }
    // Date filters
    // KQL date format is YYYY-MM-DD. Graph Search for messages uses 'lastModifiedDateTime'.
    if (params.onDate) {
        // To cover the whole day, create a range.
        kqlParts.push(`(lastModifiedDateTime>=${params.onDate}T00:00:00Z AND lastModifiedDateTime<=${params.onDate}T23:59:59Z)`);
    }
    else {
        // if onDate is not present, then before/after can be used
        if (params.afterDate) {
            kqlParts.push(`lastModifiedDateTime>=${params.afterDate}T00:00:00Z`);
        }
        if (params.beforeDate) {
            // To be inclusive of the 'beforeDate', it should be less than the start of the *next* day,
            // or less than or equal to the end of the 'beforeDate'.
            kqlParts.push(`lastModifiedDateTime<=${params.beforeDate}T23:59:59Z`);
        }
    }
    if (params.hasLink &&
        !kqlParts.some((p) => p.toLowerCase().includes('http'))) {
        // Add http/https as keywords if hasLink is true and not already part of textKeywords
        if (params.textKeywords && params.textKeywords.length > 0) {
            if (!params.textKeywords.toLowerCase().includes('http')) {
                kqlParts.push('(http OR https)');
            }
        }
        else {
            kqlParts.push('(http OR https)');
        }
    }
    // EntityType filter (e.g., entityTypes: ['chatMessage']) is typically applied in the search request body,
    // not usually in the KQL string for messages directly, but KQL might support `IsDocument:false` or similar.
    // For now, we assume the API call will scope to messages.
    const finalKqlQuery = kqlParts
        .filter((part) => part && part.length > 0)
        .join(' AND ')
        .trim();
    logger.debug(`[NluMSTeamsHelper] Built MS Teams KQL query: "${finalKqlQuery}" from params:`, params);
    return finalKqlQuery;
}
/*
// Example Usage:
const exampleParams1: StructuredMSTeamsQuery = {
  fromUser: 'bob@example.com',
  textKeywords: 'Q1 budget report',
  onDate: '2023-10-26',
};
console.log(`Example 1 KQL: ${buildMSTeamsSearchQuery(exampleParams1)}`);
// Expected: Q1 budget report AND from:bob@example.com AND created:2023-10-26 (order may vary)

const exampleParams2: StructuredMSTeamsQuery = {
  hasFile: true,
  afterDate: '2023-09-01',
  beforeDate: '2023-09-30',
  subjectContains: 'Project Phoenix Update'
};
console.log(`Example 2 KQL: ${buildMSTeamsSearchQuery(exampleParams2)}`);
// Expected: subject:Project Phoenix Update AND hasattachment:true AND created:2023-09-01..2023-09-30

const exampleParams3: StructuredMSTeamsQuery = {
  exactPhrase: 'final sign-off needed',
  mentionsUser: 'Sarah Day',
};
console.log(`Example 3 KQL: ${buildMSTeamsSearchQuery(exampleParams3)}`);
// Expected: "final sign-off needed" AND "Sarah Day"
*/
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibmx1X21zdGVhbXNfaGVscGVyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibmx1X21zdGVhbXNfaGVscGVyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUNBLE9BQU8sRUFBRSxNQUFNLEVBQUUsTUFBTSxxQkFBcUIsQ0FBQztBQUU3Qzs7Ozs7Ozs7R0FRRztBQUNILE1BQU0sVUFBVSx1QkFBdUIsQ0FDckMsTUFBOEI7SUFFOUIsTUFBTSxRQUFRLEdBQWEsRUFBRSxDQUFDO0lBRTlCLCtFQUErRTtJQUMvRSxJQUFJLE1BQU0sQ0FBQyxZQUFZLEVBQUUsQ0FBQztRQUN4QixRQUFRLENBQUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxZQUFZLENBQUMsSUFBSSxFQUFFLENBQUMsQ0FBQztJQUM1QyxDQUFDO0lBQ0QsSUFBSSxNQUFNLENBQUMsV0FBVyxFQUFFLENBQUM7UUFDdkIsUUFBUSxDQUFDLElBQUksQ0FBQyxJQUFJLE1BQU0sQ0FBQyxXQUFXLENBQUMsSUFBSSxFQUFFLEdBQUcsQ0FBQyxDQUFDO0lBQ2xELENBQUM7SUFFRCw4QkFBOEI7SUFDOUIsSUFBSSxNQUFNLENBQUMsUUFBUSxFQUFFLENBQUM7UUFDcEIseURBQXlEO1FBQ3pELFFBQVEsQ0FBQyxJQUFJLENBQUMsUUFBUSxNQUFNLENBQUMsUUFBUSxDQUFDLElBQUksRUFBRSxFQUFFLENBQUMsQ0FBQztJQUNsRCxDQUFDO0lBQ0QsSUFBSSxNQUFNLENBQUMsWUFBWSxFQUFFLENBQUM7UUFDeEIsZ0ZBQWdGO1FBQ2hGLGtHQUFrRztRQUNsRywyR0FBMkc7UUFDM0csd0VBQXdFO1FBQ3hFLHNFQUFzRTtRQUN0RSxtRUFBbUU7UUFDbkUsbUZBQW1GO1FBQ25GLDRGQUE0RjtRQUM1RiwrQkFBK0I7UUFDL0IsUUFBUSxDQUFDLElBQUksQ0FBQyxJQUFJLE1BQU0sQ0FBQyxZQUFZLENBQUMsSUFBSSxFQUFFLEdBQUcsQ0FBQyxDQUFDLENBQUMsK0JBQStCO0lBQ25GLENBQUM7SUFFRCxJQUFJ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b20gJy4vbGxtX21zdGVhbXNfcXVlcnlfdW5kZXJzdGFuZGVyJztcbmltcG9ydCB7IGxvZ2dlciB9IGZyb20gJy4uLy4uL191dGlscy9sb2dnZXInO1xuXG4vKipcbiAqIENvbnN0cnVjdHMgYSBLZXl3b3JkIFF1ZXJ5IExhbmd1YWdlIChLUUwpIHN0cmluZyBmb3IgTWljcm9zb2Z0IEdyYXBoIFNlYXJjaCBBUElcbiAqIGZyb20gc3RydWN0dXJlZCBwYXJhbWV0ZXJzLlxuICogUmVmIGZvciBLUUw6IGh0dHBzOi8vbGVhcm4ubWljcm9zb2Z0LmNvbS9lbi11cy9zaGFyZXBvaW50L2Rldi9nZW5lcmFsLWRldmVsb3BtZW50L2tleXdvcmQtcXVlcnktbGFuZ3VhZ2Uta3FsLXN5bnRheC1yZWZlcmVuY2VcbiAqIFJlZiBmb3IgR3JhcGggU2VhcmNoIG9uIG1lc3NhZ2VzOiBodHRwczovL2xlYXJuLm1pY3Jvc29mdC5jb20vZW4tdXMvZ3JhcGgvc2VhcmNoLWNvbmNlcHQtY2hhdG1lc3NhZ2VcbiAqXG4gKiBAcGFyYW0gcGFyYW1zIFN0cnVjdHVyZWRNU1RlYW1zUXVlcnkgb2JqZWN0IGNvbnRhaW5pbmcgdmFyaW91cyBzZWFyY2ggY3JpdGVyaWEuXG4gKiBAcmV0dXJucyBBIEtRTCBzdHJpbmcgZm9ybWF0dGVkIGZvciBNaWNyb3NvZnQgR3JhcGggQVBJJ3Mgc2VhcmNoIHF1ZXJ5LlxuICovXG5leHBvcnQgZnVuY3Rpb24gYnVpbGRNU1RlYW1zU2VhcmNoUXVlcnkoXG4gIHBhcmFtczogU3RydWN0dXJlZE1TVGVhbXNRdWVyeVxuKTogc3RyaW5nIHtcbiAgY29uc3Qga3FsUGFydHM6IHN0cmluZ1tdID0gW107XG5cbiAgLy8gRnJlZS10ZXh0IGtleXdvcmRzICh0aGVzZSB1c3VhbGx5IGNvbWUgZmlyc3Qgb3Igd2l0aG91dCBhIHNwZWNpZmljIHByb3BlcnR5KVxuICBpZiAocGFyYW1zLnRleHRLZXl3b3Jkcykge1xuICAgIGtxbFBhcnRzLnB1c2gocGFyYW1zLnRleHRLZXl3b3Jkcy50cmltKCkpO1xuICB9XG4gIGlmIChwYXJhbXMuZXhhY3RQaHJhc2UpIHtcbiAgICBrcWxQYXJ0cy5wdXNoKGBcIiR7cGFyYW1zLmV4YWN0UGhyYXNlLnRyaW0oKX1cImApO1xuICB9XG5cbiAgLy8gUHJvcGVydHktcmVzdHJpY3RlZCBxdWVyaWVzXG4gIGlmIChwYXJhbXMuZnJvbVVzZXIpIHtcbiAgICAvLyBHcmFwaCBzZWFyY2ggY2FuIG9mdGVuIHJlc29sdmUgbmFtZXMvZW1haWxzIGZvciAnZnJvbSdcbiAgICBrcWxQYXJ0cy5wdXNoKGBmcm9tOiR7cGFyYW1zLmZyb21Vc2VyLnRyaW0oKX1gKTtcbiAgfVxuICBpZiAocGFyYW1zLm1lbnRpb25zVXNlcikge1xuICAgIC8vIEtRTCBmb3IgbWVudGlvbnMgbWlnaHQgYmUgYHBhcnRpY2lwYW50czpcIkpvaG4gRG9lXCJgIG9yIGNoZWNraW5nIGJvZHkvY29udGVudC5cbiAgICAvLyBGb3Igc2ltcGxpY2l0eSwgd2UgY2FuIGFkZCBpdCBhcyBhIGtleXdvcmQgb3IgYXNzdW1lIEdyYXBoIFNlYXJjaCBoYW5kbGVzIFwibWVudGlvbnM6VXNlciBOYW1lXCIuXG4gICAgLy8gQSBtb3JlIHNwZWNpZmljIEtRTCBtaWdodCBiZSBgbWVudGlvbnM6JHtwYXJhbXMubWVudGlvbnNVc2VyLnRyaW0oKX1gIGlmIHN1cHBvcnRlZCBvciBieSBhZGRpbmcgdG8gdGV4dC5cbiAgICAvLyBMZXQncyBhc3N1bWUgZm9yIG5vdyB0aGF0IGFkZGluZyBpdCBhcyBhIGtleXdvcmQgaXMgYSBzdGFydGluZyBwb2ludCxcbiAgICAvLyBvciBzcGVjaWZpYyBHcmFwaCBwcm9wZXJ0aWVzIGxpa2UgYHN1bW1hcnlgIG1pZ2h0IGluY2x1ZGUgbWVudGlvbnMuXG4gICAgLy8gRm9yIGRpcmVjdCBLUUwsIGBwYXJ0aWNpcGFudHNgIGlzIG1vcmUgYWJvdXQgd2hvIGlzIGluIHRoZSBjaGF0LlxuICAgIC8vIGBtZW50aW9uc2AgaXNuJ3QgYSBzdGFuZGFyZCBLUUwgcHJvcGVydHkgZm9yIG1lc3NhZ2VzIGluIHRoZSBzYW1lIHdheSBhcyBgZnJvbWAuXG4gICAgLy8gU28sIHdlIG1pZ2h0IGFkZCBpdCB0byB0aGUgZ2VuZXJhbCB0ZXh0IHNlYXJjaCBvciBleHBlY3QgdGhlIExMTSB0byBoYXZlIGluY29ycG9yYXRlZCBpdC5cbiAgICAvLyBBZGRpbmcgYXMgYSBrZXl3b3JkIGZvciBub3c6XG4gICAga3FsUGFydHMucHVzaChgXCIke3BhcmFtcy5tZW50aW9uc1VzZXIudHJpbSgpfVwiYCk7IC8vIFRyZWF0IGFzIHBhcnQgb2YgdGV4dCBzZWFyY2hcbiAgfVxuXG4gIGlmIChwYXJhbXMuaW5DaGF0T3JDaGFubmVsKSB7XG4gICAgLy8gVGhpcyBpcyBjb21wbGV4LiBLUUwgZG9lc24ndCBoYXZlIGEgZGlyZWN0IFwiaW5DaGF0T3JDaGFubmVsXCIgcHJvcGVydHkuXG4gICAgLy8gVGhpcyB1c3VhbGx5IG5lZWRzIHRvIGJlIGhhbmRsZWQgYnkgdGFyZ2V0aW5nIHRoZSBzZWFyY2ggc2NvcGUgKGUuZy4gYSBzcGVjaWZpYyBjaGF0IElEIG9yIGNoYW5uZWwgSUQgaW4gdGhlIEFQSSBjYWxsKVxuICAgIC8vIG9yIGJ5IHVzaW5nIHByb3BlcnRpZXMgbGlrZSBgcGFyZW50Zm9sZGVyaWRgIG9yIGBzaXRlaWRgIGlmIHNlYXJjaGluZyB3aXRoaW4gU2hhcmVQb2ludCBjb250ZXh0IG9mIFRlYW1zIGZpbGVzLlxuICAgIC8vIEZvciBtZXNzYWdlcywgdGhlIHNlYXJjaCBlbmRwb2ludCBpdHNlbGYgbWlnaHQgYmUgc2NvcGVkLCBvciBgY2hhdElkYCAvIGBjaGFubmVsSWRgIHVzZWQgaW4gYSBkaWZmZXJlbnQgd2F5LlxuICAgIC8vIEZvciBhIGdlbmVyYWwgc2VhcmNoIHF1ZXJ5LCB3ZSBtaWdodCBpbmNsdWRlIGl0IGFzIHRleHQ6XG4gICAga3FsUGFydHMucHVzaChgXCIke3BhcmFtcy5pbkNoYXRPckNoYW5uZWwudHJpbSgpfVwiYCk7XG4gIH1cblxuICBpZiAocGFyYW1zLnN1YmplY3RDb250YWlucykge1xuICAgIC8vIGBzdWJqZWN0YCBpcyBhIGNvbW1vbiBLUUwgcHJvcGVydHlcbiAgICBrcWxQYXJ0cy5wdXNoKGBzdWJqZWN0OiR7cGFyYW1zLnN1YmplY3RDb250YWlucy50cmltKCl9YCk7XG4gIH1cblxuICBpZiAocGFyYW1zLmhhc0ZpbGUpIHtcbiAgICAvLyBLUUwgZm9yIGF0dGFjaG1lbnRzOiBgaGFzYXR0YWNobWVudDp0cnVlYFxuICAgIGtxbFBhcnRzLnB1c2goJ2hhc2F0dGFjaG1lbnQ6dHJ1ZScpO1xuICB9XG4gIGlmIChwYXJhbXMuaGFzTGluaykge1xuICAgIC8vIEtRTCBmb3IgbGlua3M6IGBjb250YWluc2xpbms6dHJ1ZWAgKHRoaXMgaXMgbW9yZSBTaGFyZVBvaW50IHNwZWNpZmljKVxuICAgIC8vIEZvciBtZXNzYWdlcywgbWlnaHQgbmVlZCB0byBzZWFyY2ggZm9yIFwiaHR0cFwiIG9yIFwiaHR0cHNcIiBhcyBrZXl3b3Jkcy5cbiAgICBrcWxQYXJ0cy5wdXNoKCcoaHR0cCBPUiBodHRwcyknKTtcbiAgfVxuXG4gIC8vIERhdGUgZmlsdGVyc1xuICAvLyBLUUwgZGF0ZSBmb3JtYXQgaXMgWVlZWS1NTS1ERC4gR3JhcGggU2VhcmNoIGZvciBtZXNzYWdlcyB1c2VzICdsYXN0TW9kaWZpZWREYXRlVGltZScuXG4gIGlmIChwYXJhbXMub25EYXRlKSB7XG4gICAgLy8gVG8gY292ZXIgdGhlIHdob2xlIGRheSwgY3JlYXRlIGEgcmFuZ2UuXG4gICAga3FsUGFydHMucHVzaChcbiAgICAgIGAobGFzdE1vZGlmaWVkRGF0ZVRpbWU+PSR7cGFyYW1zLm9uRGF0ZX1UMDA6MDA6MDBaIEFORCBsYXN0TW9kaWZpZWREYXRlVGltZTw9JHtwYXJhbXMub25EYXRlfVQyMzo1OTo1OVopYFxuICAgICk7XG4gIH0gZWxzZSB7XG4gICAgLy8gaWYgb25EYXRlIGlzIG5vdCBwcmVzZW50LCB0aGVuIGJlZm9yZS9hZnRlciBjYW4gYmUgdXNlZFxuICAgIGlmIChwYXJhbXMuYWZ0ZXJEYXRlKSB7XG4gICAgICBrcWxQYXJ0cy5wdXNoKGBsYXN0TW9kaWZpZWREYXRlVGltZT49JHtwYXJhbXMuYWZ0ZXJEYXRlfVQwMDowMDowMFpgKTtcbiAgICB9XG4gICAgaWYgKHBhcmFtcy5iZWZvcmVEYXRlKSB7XG4gICAgICAvLyBUbyBiZSBpbmNsdXNpdmUgb2YgdGhlICdiZWZvcmVEYXRlJywgaXQgc2hvdWxkIGJlIGxlc3MgdGhhbiB0aGUgc3RhcnQgb2YgdGhlICpuZXh0KiBkYXksXG4gICAgICAvLyBvciBsZXNzIHRoYW4gb3IgZXF1YWwgdG8gdGhlIGVuZCBvZiB0aGUgJ2JlZm9yZURhdGUnLlxuICAgICAga3FsUGFydHMucHVzaChgbGFzdE1vZGlmaWVkRGF0ZVRpbWU8PSR7cGFyYW1zLmJlZm9yZURhdGV9VDIzOjU5OjU5WmApO1xuICAgIH1cbiAgfVxuXG4gIGlmIChcbiAgICBwYXJhbXMuaGFzTGluayAmJlxuICAgICFrcWxQYXJ0cy5zb21lKChwKSA9PiBwLnRvTG93ZXJDYXNlKCkuaW5jbHVkZXMoJ2h0dHAnKSlcbiAgKSB7XG4gICAgLy8gQWRkIGh0dHAvaHR0cHMgYXMga2V5d29yZHMgaWYgaGFzTGluayBpcyB0cnVlIGFuZCBub3QgYWxyZWFkeSBwYXJ0IG9mIHRleHRLZXl3b3Jkc1xuICAgIGlmIChwYXJhbXMudGV4dEtleXdvcmRzICYmIHBhcmFtcy50ZXh0S2V5d29yZHMubGVuZ3RoID4gMCkge1xuICAgICAgaWYgKCFwYXJhbXMudGV4dEtleXdvcmRzLnRvTG93ZXJDYXNlKCkuaW5jbHVkZXMoJ2h0dHAnKSkge1xuICAgICAgICBrcWxQYXJ0cy5wdXNoKCcoaHR0cCBPUiBodHRwcyknKTtcbiAgICAgIH1cbiAgICB9IGVsc2Uge1xuICAgICAga3FsUGFydHMucHVzaCgnKGh0dHAgT1IgaHR0cHMpJyk7XG4gICAgfVxuICB9XG5cbiAgLy8gRW50aXR5VHlwZSBmaWx0ZXIgKGUuZy4sIGVudGl0eVR5cGVzOiBbJ2NoYXRNZXNzYWdlJ10pIGlzIHR5cGljYWxseSBhcHBsaWVkIGluIHRoZSBzZWFyY2ggcmVxdWVzdCBib2R5LFxuICAvLyBub3QgdXN1YWxseSBpbiB0aGUgS1FMIHN0cmluZyBmb3IgbWVzc2FnZXMgZGlyZWN0bHksIGJ1dCBLUUwgbWlnaHQgc3VwcG9ydCBgSXNEb2N1bWVudDpmYWxzZWAgb3Igc2ltaWxhci5cbiAgLy8gRm9yIG5vdywgd2UgYXNzdW1lIHRoZSBBUEkgY2FsbCB3aWxsIHNjb3BlIHRvIG1lc3NhZ2VzLlxuXG4gIGNvbnN0IGZpbmFsS3FsUXVlcnkgPSBrcWxQYXJ0c1xuICAgIC5maWx0ZXIoKHBhcnQpID0+IHBhcnQgJiYgcGFydC5sZW5ndGggPiAwKVxuICAgIC5qb2luKCcgQU5EICcpXG4gICAgLnRyaW0oKTtcblxuICBsb2dnZXIuZGVidWcoXG4gICAgYFtObHVNU1RlYW1zSGVscGVyXSBCdWlsdCBNUyBUZWFtcyBLUUwgcXVlcnk6IFwiJHtmaW5hbEtxbFF1ZXJ5fVwiIGZyb20gcGFyYW1zOmAsXG4gICAgcGFyYW1zXG4gICk7XG4gIHJldHVybiBmaW5hbEtxbFF1ZXJ5O1xufVxuXG4vKlxuLy8gRXhhbXBsZSBVc2FnZTpcbmNvbnN0IGV4YW1wbGVQYXJhbXMxOiBTdHJ1Y3R1cmVkTVNUZWFtc1F1ZXJ5ID0ge1xuICBmcm9tVXNlcjogJ2JvYkBleGFtcGxlLmNvbScsXG4gIHRleHRLZXl3b3JkczogJ1ExIGJ1ZGdldCByZXBvcnQnLFxuICBvbkRhdGU6ICcyMDIzLTEwLTI2Jyxcbn07XG5jb25zb2xlLmxvZyhgRXhhbXBsZSAxIEtRTDogJHtidWlsZE1TVGVhbXNTZWFyY2hRdWVyeShleGFtcGxlUGFyYW1zMSl9YCk7XG4vLyBFeHBlY3RlZDogUTEgYnVkZ2V0IHJlcG9ydCBBTkQgZnJvbTpib2JAZXhhbXBsZS5jb20gQU5EIGNyZWF0ZWQ6MjAyMy0xMC0yNiAob3JkZXIgbWF5IHZhcnkpXG5cbmNvbnN0IGV4YW1wbGVQYXJhbXMyOiBTdHJ1Y3R1cmVkTVNUZWFtc1F1ZXJ5ID0ge1xuICBoYXNGaWxlOiB0cnVlLFxuICBhZnRlckRhdGU6ICcyMDIzLTA5LTAxJyxcbiAgYmVmb3JlRGF0ZTogJzIwMjMtMDktMzAnLFxuICBzdWJqZWN0Q29udGFpbnM6ICdQcm9qZWN0IFBob2VuaXggVXBkYXRlJ1xufTtcbmNvbnNvbGUubG9nKGBFeGFtcGxlIDIgS1FMOiAke2J1aWxkTVNUZWFtc1NlYXJjaFF1ZXJ5KGV4YW1wbGVQYXJhbXMyKX1gKTtcbi8vIEV4cGVjdGVkOiBzdWJqZWN0OlByb2plY3QgUGhvZW5peCBVcGRhdGUgQU5EIGhhc2F0dGFjaG1lbnQ6dHJ1ZSBBTkQgY3JlYXRlZDoyMDIzLTA5LTAxLi4yMDIzLTA5LTMwXG5cbmNvbnN0IGV4YW1wbGVQYXJhbXMzOiBTdHJ1Y3R1cmVkTVNUZWFtc1F1ZXJ5ID0ge1xuICBleGFjdFBocmFzZTogJ2ZpbmFsIHNpZ24tb2ZmIG5lZWRlZCcsXG4gIG1lbnRpb25zVXNlcjogJ1NhcmFoIERheScsXG59O1xuY29uc29sZS5sb2coYEV4YW1wbGUgMyBLUUw6ICR7YnVpbGRNU1RlYW1zU2VhcmNoUXVlcnkoZXhhbXBsZVBhcmFtczMpfWApO1xuLy8gRXhwZWN0ZWQ6IFwiZmluYWwgc2lnbi1vZmYgbmVlZGVkXCIgQU5EIFwiU2FyYWggRGF5XCJcbiovXG4iXX0=