import {
  MeetingPrepNluEntities,
  AggregatedPrepResults,
  PrepResultSourceEntry,
  GmailMessageSnippet,
  SlackMessageSnippet,
  NotionPageSummary,
  CalendarEventSummary,
} from '../types';
import { fetchMeetingPrepInfo } from '../skills/meetingPrepSkill';
import { logger } from '../../_utils/logger';

function formatSourceResults(sourceEntry: PrepResultSourceEntry): string {
  if (sourceEntry.error_message) {
    return `  Error fetching from ${sourceEntry.source}: ${sourceEntry.error_message}\n`;
  }
  if (sourceEntry.count === 0) {
    return `  No information found from ${sourceEntry.source}.\n`;
  }

  let details = '';
  switch (sourceEntry.source) {
    case 'gmail':
      const gmailResults = sourceEntry.results as GmailMessageSnippet[];
      details = gmailResults
        .map(
          (r) =>
            `    - Subject: ${r.subject || 'N/A'}, From: ${r.from || 'N/A'}, Snippet: ${r.snippet?.substring(0, 50)}...`
        )
        .join('\n');
      break;
    case 'slack':
      const slackResults = sourceEntry.results as SlackMessageSnippet[];
      details = slackResults
        .map(
          (r) =>
            `    - Channel: ${r.channel?.name || r.channel?.id || 'N/A'}, User: ${r.user?.name || r.user?.id || 'N/A'}, Text: ${r.text?.substring(0, 50)}...`
        )
        .join('\n');
      break;
    case 'notion':
      const notionResults = sourceEntry.results as NotionPageSummary[];
      details = notionResults
        .map((r) => `    - Title: ${r.title || 'N/A'}, URL: ${r.url || 'N/A'}`)
        .join('\n');
      break;
    case 'calendar_events':
      const calendarResults = sourceEntry.results as CalendarEventSummary[];
      details = calendarResults
        .map(
          (r) =>
            `    - Summary: ${r.summary || 'N/A'}, Start: ${r.start ? new Date(r.start).toLocaleString() : 'N/A'}`
        )
        .join('\n');
      break;
    default:
      details = `    Raw results: ${JSON.stringify(sourceEntry.results.slice(0, 2))}...`;
  }
  return `  From ${sourceEntry.source} (${sourceEntry.count} item(s)):\n${details}\n`;
}

/**
 * Handles the "RequestMeetingPreparation" intent.
 * Calls the meeting preparation skill and formats the results for the user.
 *
 * @param userId The ID of the user.
 * @param entities The NLU entities extracted for the RequestMeetingPreparation intent.
 * @returns A promise that resolves to a user-facing string response.
 */
export async function handleMeetingPreparationRequest(
  userId: string,
  entities: MeetingPrepNluEntities
): Promise<string> {
  logger.info(
    `[MeetingPrepCommandHandler] Handling meeting preparation request for user ${userId}, meeting reference: "${entities.meeting_reference}"`
  );
  logger.debug(
    `[MeetingPrepCommandHandler] Received NLU entities: ${JSON.stringify(entities)}`
  );

  try {
    const prepResults: AggregatedPrepResults = await fetchMeetingPrepInfo(
      userId,
      entities
    );
    logger.info(
      `[MeetingPrepCommandHandler] Meeting preparation skill finished. Sources processed: ${prepResults.results_by_source.length}`
    );

    let responseText = `Okay, I've gathered some information for your meeting: "${prepResults.meeting_reference_identified}":\n\n`;

    if (prepResults.identified_calendar_event) {
      responseText += `I've identified this as the event: "${prepResults.identified_calendar_event.summary}" starting at ${prepResults.identified_calendar_event.start ? new Date(prepResults.identified_calendar_event.start).toLocaleString() : 'Unknown time'}.\n\n`;
    } else {
      responseText += `I couldn't definitively link this to a specific calendar event based on the reference provided.\n\n`;
    }

    if (prepResults.results_by_source.length > 0) {
      prepResults.results_by_source.forEach((sourceEntry) => {
        responseText += formatSourceResults(sourceEntry);
      });
    } else {
      responseText +=
        "I didn't find any specific items from the requested sources.\n";
    }

    if (prepResults.overall_summary_notes) {
      responseText += `\nSummary of Findings:\n${prepResults.overall_summary_notes}\n`;
    }

    if (
      prepResults.errors_encountered &&
      prepResults.errors_encountered.length > 0
    ) {
      responseText += '\nSome issues were encountered during preparation:\n';
      prepResults.errors_encountered.forEach((err) => {
        responseText += `  - ${err.source_attempted || 'Overall'}: ${err.message}\n`;
      });
    }

    logger.debug(
      `[MeetingPrepCommandHandler] Final response text: ${responseText}`
    );
    return responseText;
  } catch (error: any) {
    logger.error(
      `[MeetingPrepCommandHandler] Critical error handling meeting preparation request: ${error.message}`,
      error
    );
    return `I encountered an unexpected error while trying to prepare for your meeting: ${error.message}. Please try again later.`;
  }
}
