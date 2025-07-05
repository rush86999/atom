import {
  MeetingPrepNluEntities,
  AggregatedPrepResults,
  InformationRequest,
  GmailSearchParameters,
  SlackSearchParameters,
  NotionSearchParameters,
  CalendarEventsSearchParameters,
  PrepResultSourceEntry,
  PrepErrorMessage,
  GmailMessageSnippet,
  SlackMessageSnippet,
  NotionPageSummary,
  CalendarEventSummary,
} from '../types'; // Assuming types.ts is in the parent directory of skills

// Import other necessary skills if they are to be called directly
import * as gmailSkills from './gmailSkills'; // Added for searchEmailsForPrep
// import * as slackSkills from './slackSkills';
// import * as notionSkills from './notionAndResearchSkills';
import * as calendarSkills from './calendarSkills'; // Import calendarSkills

import { logger } from '../../_utils/logger'; // Assuming a logger utility

/**
 * Fetches and aggregates information from various sources in preparation for a meeting.
 *
 * @param userId The ID of the user for whom the preparation is being done.
 * @param nluEntities The parsed NLU entities from the RequestMeetingPreparation intent.
 * @returns A promise that resolves to AggregatedPrepResults containing all fetched information.
 */
export async function fetchMeetingPrepInfo(
  userId: string,
  nluEntities: MeetingPrepNluEntities,
): Promise<AggregatedPrepResults> {
  logger.info(`[meetingPrepSkill] Starting meeting preparation for user ${userId} and meeting: ${nluEntities.meeting_reference}`);

  const aggregatedResults: AggregatedPrepResults = {
    meeting_reference_identified: nluEntities.meeting_reference,
    results_by_source: [],
    errors_encountered: [],
  };

  // 1. Resolve nluEntities.meeting_reference to a specific calendar event.
  let resolvedEvent: CalendarEventSummary | null = null;
  try {
    logger.info(`[meetingPrepSkill] Attempting to resolve meeting_reference: "${nluEntities.meeting_reference}" using findEventByFuzzyReference.`);
    const eventResponse = await calendarSkills.findEventByFuzzyReference(
      userId,
      nluEntities.meeting_reference,
      nluEntities.overall_lookback_period
    );

    if (eventResponse.ok && eventResponse.data) {
      resolvedEvent = eventResponse.data;
      aggregatedResults.identified_calendar_event = resolvedEvent; // Store the resolved event
      logger.info(`[meetingPrepSkill] Successfully resolved meeting reference to event: "${resolvedEvent.summary}" (ID: ${resolvedEvent.id})`);
    } else if (eventResponse.error) {
      logger.warn(`[meetingPrepSkill] Could not resolve meeting_reference "${nluEntities.meeting_reference}" to a specific event. Error: ${eventResponse.error.message}`);
      aggregatedResults.errors_encountered?.push({
        source_attempted: 'calendar_lookup',
        message: `Could not resolve meeting reference: ${eventResponse.error.message}`,
        details: JSON.stringify(eventResponse.error.details),
      });
    } else {
      logger.info(`[meetingPrepSkill] No specific calendar event found for reference: "${nluEntities.meeting_reference}". Proceeding without specific event context.`);
    }
  } catch (error: any) {
    logger.error(`[meetingPrepSkill] Critical error during findEventByFuzzyReference for "${nluEntities.meeting_reference}": ${error.message}`, error);
    aggregatedResults.errors_encountered?.push({
      source_attempted: 'calendar_lookup',
      message: `Critical error resolving meeting reference: ${error.message}`,
      details: error.stack,
    });
  }
  // Ensure aggregatedResults.identified_calendar_event is correctly passed along if resolution happened
  // This is already handled above by assigning to aggregatedResults.identified_calendar_event

  for (const request of nluEntities.information_requests) {
    const sourceResultEntry: PrepResultSourceEntry = {
      source: request.source,
      search_parameters_used: request.search_parameters,
      results: [],
      count: 0,
    };

    try {
      logger.debug(`[meetingPrepSkill] Processing source: ${request.source} with params: ${JSON.stringify(request.search_parameters)}`);
      switch (request.source) {
        case 'gmail':
          const gmailParams = request.search_parameters as GmailSearchParameters;
          logger.info(`[meetingPrepSkill] Calling searchEmailsForPrep with params: ${JSON.stringify(gmailParams)} and meeting context: ${aggregatedResults.identified_calendar_event?.summary}`);

          const gmailSearchResponse = await gmailSkills.searchEmailsForPrep(
            userId,
            gmailParams,
            aggregatedResults.identified_calendar_event, // Pass resolved meeting for context
            5 // Limit to 5 results for now
          );

          if (gmailSearchResponse.ok && gmailSearchResponse.data) {
            sourceResultEntry.results = gmailSearchResponse.data.results;
            sourceResultEntry.count = gmailSearchResponse.data.results.length;
            sourceResultEntry.search_query_executed = gmailSearchResponse.data.query_executed;
            logger.info(`[meetingPrepSkill] searchEmailsForPrep returned ${sourceResultEntry.count} results. Query: ${sourceResultEntry.search_query_executed}`);
          } else {
            logger.error(`[meetingPrepSkill] searchEmailsForPrep failed: ${gmailSearchResponse.error?.message}`);
            sourceResultEntry.error_message = gmailSearchResponse.error?.message || "Failed to fetch Gmail results.";
            // Also add to overall errors
            aggregatedResults.errors_encountered?.push({
              source_attempted: 'gmail',
              message: sourceResultEntry.error_message,
              details: JSON.stringify(gmailSearchResponse.error?.details)
            });
          }
          break;
        case 'slack':
          const slackParams = request.search_parameters as SlackSearchParameters;
          logger.info(`[meetingPrepSkill] Calling Slack skill with params:`, slackParams);
          // TODO: Replace with actual call to an enhanced Slack skill
          // const slackResults: SlackMessageSnippet[] = await slackSkills.searchSlackMessagesForPrep(
          //   userId,
          //   slackParams,
          //   aggregatedResults.identified_calendar_event // Pass resolved meeting for context
          // );
          // sourceResultEntry.results = slackResults;
          // sourceResultEntry.count = slackResults.length;
          // sourceResultEntry.search_query_executed = "Actual Slack query built by slackSkills";

          // Placeholder implementation for Slack
          if (slackParams.text_keywords?.includes("Q4 strategy")) {
            sourceResultEntry.results = [{
              ts: "1234567890.123456",
              channel: { id: "C123ABC", name: slackParams.channel_name || "sales" },
              user: {id: "UABC123", name: "someuser"},
              text: "Discussing Q4 strategy document, please review attachment.",
              permalink: "https://app.slack.com/client/T123ABC/C123ABC/p1234567890123456"
            }];
            sourceResultEntry.count = 1;
          } else {
            sourceResultEntry.results = [];
            sourceResultEntry.count = 0;
          }
          logger.warn(`[meetingPrepSkill] Slack source processing is currently using placeholder data.`);
          // End Placeholder
          break;
        case 'notion':
          const notionParams = request.search_parameters as NotionSearchParameters;
          logger.info(`[meetingPrepSkill] Calling Notion skill with params:`, notionParams);
          // TODO: Replace with actual call to an enhanced Notion skill
          // const notionResults: NotionPageSummary[] = await notionSkills.searchNotionForPrep(
          //   userId,
          //   notionParams,
          //   aggregatedResults.identified_calendar_event // Pass resolved meeting for context
          // );
          // sourceResultEntry.results = notionResults;
          // sourceResultEntry.count = notionResults.length;
          // sourceResultEntry.search_query_executed = "Actual Notion query/filter built by notionSkills";

          // Placeholder implementation for Notion
          if (notionParams.page_title_keywords?.includes("Acme Project") || notionParams.content_keywords?.includes("Acme Corp")) {
            sourceResultEntry.results = [{
              id: "notion_sim_page_1",
              title: "Acme Project Plan",
              url: "https://www.notion.so/sim/acmeprojectplan",
              last_edited_time: new Date().toISOString(),
              preview_text: "Initial project plan and deliverables for Acme Corp..."
            }];
            sourceResultEntry.count = 1;
          } else {
            sourceResultEntry.results = [];
            sourceResultEntry.count = 0;
          }
          logger.warn(`[meetingPrepSkill] Notion source processing is currently using placeholder data.`);
          // End Placeholder
          break;
        case 'calendar_events':
          const calendarParams = request.search_parameters as CalendarEventsSearchParameters;
          logger.info(`[meetingPrepSkill] Calling Calendar Events skill with params:`, calendarParams);
          // TODO: Replace with actual call to an enhanced Calendar skill
          // const relatedEvents: CalendarEventSummary[] = await calendarSkills.searchRelatedCalendarEventsForPrep(
          //   userId,
          //   calendarParams,
          //   aggregatedResults.identified_calendar_event // Pass resolved meeting for context
          // );
          // sourceResultEntry.results = relatedEvents;
          // sourceResultEntry.count = relatedEvents.length;
          // sourceResultEntry.search_query_executed = "Actual Calendar query/filter built by calendarSkills";

          // Placeholder implementation for Calendar Events
          if (calendarParams.related_to_attendees_of_meeting_reference && aggregatedResults.identified_calendar_event?.summary?.includes("Acme Corp")) {
            sourceResultEntry.results = [{
              id: "related_event_456",
              summary: "Past Q2 Review - Acme Corp",
              start: new Date(Date.now() - 30 * 24 * 3600 * 1000).toISOString(), // Approx a month ago
              end: new Date(Date.now() - 30 * 24 * 3600 * 1000 + 3600 * 1000).toISOString(),
              htmlLink: "https://calendar.google.com/calendar/event?eid=sim_456"
            }];
            sourceResultEntry.count = 1;
          } else {
            sourceResultEntry.results = [];
            sourceResultEntry.count = 0;
          }
          logger.warn(`[meetingPrepSkill] Calendar Events source processing is currently using placeholder data.`);
          // End Placeholder
          break;
        default:
          logger.warn(`[meetingPrepSkill] Unknown source type: ${request.source}`);
          sourceResultEntry.error_message = `Unknown source type: ${request.source}`;
          const unkError: PrepErrorMessage = { source_attempted: request.source, message: `Unknown source type requested: ${request.source}`};
          aggregatedResults.errors_encountered?.push(unkError);
      }
    } catch (error: any) {
      logger.error(`[meetingPrepSkill] Error processing source ${request.source}: ${error.message}`, error);
      sourceResultEntry.error_message = `Error processing source ${request.source}: ${error.message}`;
      const procError: PrepErrorMessage = { source_attempted: request.source, message: error.message, details: error.stack };
      aggregatedResults.errors_encountered?.push(procError);
    }
    aggregatedResults.results_by_source.push(sourceResultEntry);
  }

  // TODO:
  // 2. Optionally, generate an overall_summary_notes using an LLM based on all aggregatedResults.results_by_source.
  try {
    const foundItems = aggregatedResults.results_by_source.reduce((acc, rs) => acc + rs.count, 0);
    if (foundItems > 0) {
      // Construct a simple dynamic summary based on counts
      const summaryParts: string[] = [];
      aggregatedResults.results_by_source.forEach(rs => {
        if (rs.count > 0) {
          summaryParts.push(`${rs.count} item(s) from ${rs.source}`);
        }
      });
      if (summaryParts.length > 0) {
        aggregatedResults.overall_summary_notes = `Found: ${summaryParts.join(', ')}. (Detailed AI summary pending full data source integration.)`;
        logger.info(`[meetingPrepSkill] Generated basic summary: ${aggregatedResults.overall_summary_notes}`);
      } else {
        // This case should ideally not be hit if foundItems > 0, but as a fallback:
        aggregatedResults.overall_summary_notes = "Some items were found, but counts per source are zero. (Detailed AI summary pending.)";
        logger.info(`[meetingPrepSkill] Items found but no counts per source for summary.`);
      }

      // Keep LLM summarization commented out for now
      // logger.info(`[meetingPrepSkill] Placeholder for AI summarization of collected data.`);
      // const summaryContext = aggregatedResults.results_by_source
      //   .filter(rs => rs.results.length > 0)
      //   .map(rs => `Source ${rs.source} found ${rs.count} items: ${JSON.stringify(rs.results.slice(0, 2))}...`)
      //   .join('\n');
      // aggregatedResults.overall_summary_notes = await llmUtilities.summarizeText(
      //   `Summarize the key information found for the meeting preparation regarding "${aggregatedResults.meeting_reference_identified}". Context: ${summaryContext}`,
      //   // maxTokens: 200
      // );
      // logger.warn(`[meetingPrepSkill] AI summarization is currently using placeholder data.`);
    } else {
      logger.info(`[meetingPrepSkill] No data found by any source, skipping summary generation.`);
      aggregatedResults.overall_summary_notes = "No specific information items were found from the requested sources.";
    }
  } catch (summaryError: any) {
    logger.error(`[meetingPrepSkill] Error during AI summarization: ${summaryError.message}`, summaryError);
    aggregatedResults.errors_encountered?.push({
      source_attempted: 'overall_summary',
      message: `Failed to generate overall summary: ${summaryError.message}`,
      details: summaryError.stack,
    });
  }

  logger.info(`[meetingPrepSkill] Finished meeting preparation for user ${userId}. Found ${aggregatedResults.results_by_source.reduce((acc, r) => acc + r.count, 0)} items across ${aggregatedResults.results_by_source.length} sources.`);
  return aggregatedResults;
}
