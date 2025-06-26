import { StructuredMSTeamsQuery } from './llm_msteams_query_understander';
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
export function buildMSTeamsSearchQuery(params: StructuredMSTeamsQuery): string {
  const kqlParts: string[] = [];

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
  // KQL date format is YYYY-MM-DD. Can also use relative terms like 'today', 'yesterday'.
  // Or ranges: created:YYYY-MM-DD..YYYY-MM-DD
  if (params.onDate) {
    kqlParts.push(`created:${params.onDate}`);
  } else if (params.afterDate && params.beforeDate) {
    kqlParts.push(`created:${params.afterDate}..${params.beforeDate}`);
  } else if (params.afterDate) {
    kqlParts.push(`created>=${params.afterDate}`);
  } else if (params.beforeDate) {
    kqlParts.push(`created<=${params.beforeDate}`);
  }

  // EntityType filter is applied in the search request body, not typically in KQL string for messages directly.
  // e.g. entityTypes: ['chatMessage']

  const finalKqlQuery = kqlParts.filter(part => part.length > 0).join(' AND ').trim();
  // Note: KQL often uses implicit AND, but explicitly adding it can be clearer.
  // Depending on Graph Search behavior, just joining by space might also work for some terms.
  // Using 'AND' for more precise conjunction.

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
