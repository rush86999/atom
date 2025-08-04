import { StructuredMSTeamsQuery } from './llm_msteams_query_understander';
/**
 * Constructs a Keyword Query Language (KQL) string for Microsoft Graph Search API
 * from structured parameters.
 * Ref for KQL: https://learn.microsoft.com/en-us/sharepoint/dev/general-development/keyword-query-language-kql-syntax-reference
 * Ref for Graph Search on messages: https://learn.microsoft.com/en-us/graph/search-concept-chatmessage
 *
 * @param params StructuredMSTeamsQuery object containing various search criteria.
 * @returns A KQL string formatted for Microsoft Graph API's search query.
 */
export declare function buildMSTeamsSearchQuery(params: StructuredMSTeamsQuery): string;
