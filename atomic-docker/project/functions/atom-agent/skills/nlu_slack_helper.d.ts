import { StructuredSlackQuery } from './llm_slack_query_understander';
/**
 * Constructs a Slack API compatible search query string from structured parameters.
 * Slack search operators documentation: https://slack.com/help/articles/202528808-Search-in-Slack
 * @param params StructuredSlackQuery object containing various search criteria.
 * @returns A string formatted for Slack API's 'search.messages' query parameter.
 */
export declare function buildSlackSearchQuery(params: StructuredSlackQuery): string;
