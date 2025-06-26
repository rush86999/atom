import { StructuredSlackQuery } from './llm_slack_query_understander'; // Import the structure
import { logger } from '../../_utils/logger';

/**
 * Constructs a Slack API compatible search query string from structured parameters.
 * Slack search operators documentation: https://slack.com/help/articles/202528808-Search-in-Slack
 * @param params StructuredSlackQuery object containing various search criteria.
 * @returns A string formatted for Slack API's 'search.messages' query parameter.
 */
export function buildSlackSearchQuery(params: StructuredSlackQuery): string {
  const queryParts: string[] = [];

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
  } else { // 'onDate' is exclusive with 'beforeDate'/'afterDate' in typical usage
    if (params.afterDate) {
      queryParts.push(`after:${params.afterDate}`);
    }
    if (params.beforeDate) {
      queryParts.push(`before:${params.beforeDate}`);
    }
  }

  const finalQuery = queryParts.filter(part => part.length > 0).join(' ').trim();
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
