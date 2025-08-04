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
export async function fetchMeetingPrepInfo(userId, nluEntities) {
    logger.info(`[meetingPrepSkill] Starting meeting preparation for user ${userId} and meeting: ${nluEntities.meeting_reference}`);
    const aggregatedResults = {
        meeting_reference_identified: nluEntities.meeting_reference,
        results_by_source: [],
        errors_encountered: [],
    };
    // 1. Resolve nluEntities.meeting_reference to a specific calendar event.
    let resolvedEvent = null;
    try {
        logger.info(`[meetingPrepSkill] Attempting to resolve meeting_reference: "${nluEntities.meeting_reference}" using findEventByFuzzyReference.`);
        const eventResponse = await calendarSkills.findEventByFuzzyReference(userId, nluEntities.meeting_reference, nluEntities.overall_lookback_period);
        if (eventResponse.ok && eventResponse.data) {
            resolvedEvent = eventResponse.data;
            aggregatedResults.identified_calendar_event = resolvedEvent; // Store the resolved event
            logger.info(`[meetingPrepSkill] Successfully resolved meeting reference to event: "${resolvedEvent.summary}" (ID: ${resolvedEvent.id})`);
        }
        else if (eventResponse.error) {
            logger.warn(`[meetingPrepSkill] Could not resolve meeting_reference "${nluEntities.meeting_reference}" to a specific event. Error: ${eventResponse.error.message}`);
            aggregatedResults.errors_encountered?.push({
                source_attempted: 'calendar_lookup',
                message: `Could not resolve meeting reference: ${eventResponse.error.message}`,
                details: JSON.stringify(eventResponse.error.details),
            });
        }
        else {
            logger.info(`[meetingPrepSkill] No specific calendar event found for reference: "${nluEntities.meeting_reference}". Proceeding without specific event context.`);
        }
    }
    catch (error) {
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
        const sourceResultEntry = {
            source: request.source,
            search_parameters_used: request.search_parameters,
            results: [],
            count: 0,
        };
        try {
            logger.debug(`[meetingPrepSkill] Processing source: ${request.source} with params: ${JSON.stringify(request.search_parameters)}`);
            switch (request.source) {
                case 'gmail':
                    const gmailParams = request.search_parameters;
                    logger.info(`[meetingPrepSkill] Calling searchEmailsForPrep with params: ${JSON.stringify(gmailParams)} and meeting context: ${aggregatedResults.identified_calendar_event?.summary}`);
                    const gmailSearchResponse = await gmailSkills.searchEmailsForPrep(userId, gmailParams, aggregatedResults.identified_calendar_event, // Pass resolved meeting for context
                    5 // Limit to 5 results for now
                    );
                    if (gmailSearchResponse.ok && gmailSearchResponse.data) {
                        sourceResultEntry.results = gmailSearchResponse.data.results;
                        sourceResultEntry.count = gmailSearchResponse.data.results.length;
                        sourceResultEntry.search_query_executed =
                            gmailSearchResponse.data.query_executed;
                        logger.info(`[meetingPrepSkill] searchEmailsForPrep returned ${sourceResultEntry.count} results. Query: ${sourceResultEntry.search_query_executed}`);
                    }
                    else {
                        logger.error(`[meetingPrepSkill] searchEmailsForPrep failed: ${gmailSearchResponse.error?.message}`);
                        sourceResultEntry.error_message =
                            gmailSearchResponse.error?.message ||
                                'Failed to fetch Gmail results.';
                        // Also add to overall errors
                        aggregatedResults.errors_encountered?.push({
                            source_attempted: 'gmail',
                            message: sourceResultEntry.error_message,
                            details: JSON.stringify(gmailSearchResponse.error?.details),
                        });
                    }
                    break;
                case 'slack':
                    const slackParams = request.search_parameters;
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
                    if (slackParams.text_keywords?.includes('Q4 strategy')) {
                        sourceResultEntry.results = [
                            {
                                ts: '1234567890.123456',
                                channel: {
                                    id: 'C123ABC',
                                    name: slackParams.channel_name || 'sales',
                                },
                                user: { id: 'UABC123', name: 'someuser' },
                                text: 'Discussing Q4 strategy document, please review attachment.',
                                permalink: 'https://app.slack.com/client/T123ABC/C123ABC/p1234567890123456',
                            },
                        ];
                        sourceResultEntry.count = 1;
                    }
                    else {
                        sourceResultEntry.results = [];
                        sourceResultEntry.count = 0;
                    }
                    logger.warn(`[meetingPrepSkill] Slack source processing is currently using placeholder data.`);
                    // End Placeholder
                    break;
                case 'notion':
                    const notionParams = request.search_parameters;
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
                    if (notionParams.page_title_keywords?.includes('Acme Project') ||
                        notionParams.content_keywords?.includes('Acme Corp')) {
                        sourceResultEntry.results = [
                            {
                                id: 'notion_sim_page_1',
                                title: 'Acme Project Plan',
                                url: 'https://www.notion.so/sim/acmeprojectplan',
                                last_edited_time: new Date().toISOString(),
                                preview_text: 'Initial project plan and deliverables for Acme Corp...',
                            },
                        ];
                        sourceResultEntry.count = 1;
                    }
                    else {
                        sourceResultEntry.results = [];
                        sourceResultEntry.count = 0;
                    }
                    logger.warn(`[meetingPrepSkill] Notion source processing is currently using placeholder data.`);
                    // End Placeholder
                    break;
                case 'calendar_events':
                    const calendarParams = request.search_parameters;
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
                    if (calendarParams.related_to_attendees_of_meeting_reference &&
                        aggregatedResults.identified_calendar_event?.summary?.includes('Acme Corp')) {
                        sourceResultEntry.results = [
                            {
                                id: 'related_event_456',
                                summary: 'Past Q2 Review - Acme Corp',
                                start: new Date(Date.now() - 30 * 24 * 3600 * 1000).toISOString(), // Approx a month ago
                                end: new Date(Date.now() - 30 * 24 * 3600 * 1000 + 3600 * 1000).toISOString(),
                                htmlLink: 'https://calendar.google.com/calendar/event?eid=sim_456',
                            },
                        ];
                        sourceResultEntry.count = 1;
                    }
                    else {
                        sourceResultEntry.results = [];
                        sourceResultEntry.count = 0;
                    }
                    logger.warn(`[meetingPrepSkill] Calendar Events source processing is currently using placeholder data.`);
                    // End Placeholder
                    break;
                default:
                    logger.warn(`[meetingPrepSkill] Unknown source type: ${request.source}`);
                    sourceResultEntry.error_message = `Unknown source type: ${request.source}`;
                    const unkError = {
                        source_attempted: request.source,
                        message: `Unknown source type requested: ${request.source}`,
                    };
                    aggregatedResults.errors_encountered?.push(unkError);
            }
        }
        catch (error) {
            logger.error(`[meetingPrepSkill] Error processing source ${request.source}: ${error.message}`, error);
            sourceResultEntry.error_message = `Error processing source ${request.source}: ${error.message}`;
            const procError = {
                source_attempted: request.source,
                message: error.message,
                details: error.stack,
            };
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
            const summaryParts = [];
            aggregatedResults.results_by_source.forEach((rs) => {
                if (rs.count > 0) {
                    summaryParts.push(`${rs.count} item(s) from ${rs.source}`);
                }
            });
            if (summaryParts.length > 0) {
                aggregatedResults.overall_summary_notes = `Found: ${summaryParts.join(', ')}. (Detailed AI summary pending full data source integration.)`;
                logger.info(`[meetingPrepSkill] Generated basic summary: ${aggregatedResults.overall_summary_notes}`);
            }
            else {
                // This case should ideally not be hit if foundItems > 0, but as a fallback:
                aggregatedResults.overall_summary_notes =
                    'Some items were found, but counts per source are zero. (Detailed AI summary pending.)';
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
        }
        else {
            logger.info(`[meetingPrepSkill] No data found by any source, skipping summary generation.`);
            aggregatedResults.overall_summary_notes =
                'No specific information items were found from the requested sources.';
        }
    }
    catch (summaryError) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibWVldGluZ1ByZXBTa2lsbC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIm1lZXRpbmdQcmVwU2tpbGwudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBZ0JBLGtFQUFrRTtBQUNsRSxPQUFPLEtBQUssV0FBVyxNQUFNLGVBQWUsQ0FBQyxDQUFDLGdDQUFnQztBQUM5RSxnREFBZ0Q7QUFDaEQsNkRBQTZEO0FBQzdELE9BQU8sS0FBSyxjQUFjLE1BQU0sa0JBQWtCLENBQUMsQ0FBQyx3QkFBd0I7QUFFNUUsT0FBTyxFQUFFLE1BQU0sRUFBRSxNQUFNLHFCQUFxQixDQUFDLENBQUMsNEJBQTRCO0FBRTFFOzs7Ozs7R0FNRztBQUNILE1BQU0sQ0FBQyxLQUFLLFVBQVUsb0JBQW9CLENBQ3hDLE1BQWMsRUFDZCxXQUFtQztJQUVuQyxNQUFNLENBQUMsSUFBSSxDQUNULDREQUE0RCxNQUFNLGlCQUFpQixXQUFXLENBQUMsaUJBQWlCLEVBQUUsQ0FDbkgsQ0FBQztJQUVGLE1BQU0saUJBQWlCLEdBQTBCO1FBQy9DLDRCQUE0QixFQUFFLFdBQVcsQ0FBQyxpQkFBaUI7UUFDM0QsaUJBQWlCLEVBQUUsRUFBRTtRQUNyQixrQkFBa0IsRUFBRSxFQUFFO0tBQ3ZCLENBQUM7SUFFRix5RUFBeUU7SUFDekUsSUFBSSxhQUFhLEdBQWdDLElBQUksQ0FBQztJQUN0RCxJQUFJLENBQUM7UUFDSCxNQUFNLENBQUMsSUFBSSxDQUNULGdFQUFnRSxXQUFXLENBQUMsaUJBQWlCLG9DQUFvQyxDQUNsSSxDQUFDO1FBQ0YsTUFBTSxhQUFhLEdBQUcsTUFBTSxjQUFjLENBQUMseUJBQXlCLENBQ2xFLE1BQU0sRUFDTixXQUFXLENBQUMsaUJBQWlCLEVBQzdCLFdBQVcsQ0FBQyx1QkFBdUIsQ0FDcEMsQ0FBQztRQUVGLElBQUksYUFBYSxDQUFDLEVBQUUsSUFBSSxhQUFhLENBQUMsSUFBSSxFQUFFLENBQUM7WUFDM0MsYUFBYSxHQUFHLGFBQWEsQ0FBQyxJQUFJLENBQUM7WUFD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bnRlbnQiOlsiaW1wb3J0IHtcbiAgTWVldGluZ1ByZXBObHVFbnRpdGllcyxcbiAgQWdncmVnYXRlZFByZXBSZXN1bHRzLFxuICBJbmZvcm1hdGlvblJlcXVlc3QsXG4gIEdtYWlsU2VhcmNoUGFyYW1ldGVycyxcbiAgU2xhY2tTZWFyY2hQYXJhbWV0ZXJzLFxuICBOb3Rpb25TZWFyY2hQYXJhbWV0ZXJzLFxuICBDYWxlbmRhckV2ZW50c1NlYXJjaFBhcmFtZXRlcnMsXG4gIFByZXBSZXN1bHRTb3VyY2VFbnRyeSxcbiAgUHJlcEVycm9yTWVzc2FnZSxcbiAgR21haWxNZXNzYWdlU25pcHBldCxcbiAgU2xhY2tNZXNzYWdlU25pcHBldCxcbiAgTm90aW9uUGFnZVN1bW1hcnksXG4gIENhbGVuZGFyRXZlbnRTdW1tYXJ5LFxufSBmcm9tICcuLi90eXBlcyc7IC8vIEFzc3VtaW5nIHR5cGVzLnRzIGlzIGluIHRoZSBwYXJlbnQgZGlyZWN0b3J5IG9mIHNraWxsc1xuXG4vLyBJbXBvcnQgb3RoZXIgbmVjZXNzYXJ5IHNraWxscyBpZiB0aGV5IGFyZSB0byBiZSBjYWxsZWQgZGlyZWN0bHlcbmltcG9ydCAqIGFzIGdtYWlsU2tpbGxzIGZyb20gJy4vZ21haWxTa2lsbHMnOyAvLyBBZGRlZCBmb3Igc2VhcmNoRW1haWxzRm9yUHJlcFxuLy8gaW1wb3J0ICogYXMgc2xhY2tTa2lsbHMgZnJvbSAnLi9zbGFja1NraWxscyc7XG4vLyBpbXBvcnQgKiBhcyBub3Rpb25Ta2lsbHMgZnJvbSAnLi9ub3Rpb25BbmRSZXNlYXJjaFNraWxscyc7XG5pbXBvcnQgKiBhcyBjYWxlbmRhclNraWxscyBmcm9tICcuL2NhbGVuZGFyU2tpbGxzJzsgLy8gSW1wb3J0IGNhbGVuZGFyU2tpbGxzXG5cbmltcG9ydCB7IGxvZ2dlciB9IGZyb20gJy4uLy4uL191dGlscy9sb2dnZXInOyAvLyBBc3N1bWluZyBhIGxvZ2dlciB1dGlsaXR5XG5cbi8qKlxuICogRmV0Y2hlcyBhbmQgYWdncmVnYXRlcyBpbmZvcm1hdGlvbiBmcm9tIHZhcmlvdXMgc291cmNlcyBpbiBwcmVwYXJhdGlvbiBmb3IgYSBtZWV0aW5nLlxuICpcbiAqIEBwYXJhbSB1c2VySWQgVGhlIElEIG9mIHRoZSB1c2VyIGZvciB3aG9tIHRoZSBwcmVwYXJhdGlvbiBpcyBiZWluZyBkb25lLlxuICogQHBhcmFtIG5sdUVudGl0aWVzIFRoZSBwYXJzZWQgTkxVIGVudGl0aWVzIGZyb20gdGhlIFJlcXVlc3RNZWV0aW5nUHJlcGFyYXRpb24gaW50ZW50LlxuICogQHJldHVybnMgQSBwcm9taXNlIHRoYXQgcmVzb2x2ZXMgdG8gQWdncmVnYXRlZFByZXBSZXN1bHRzIGNvbnRhaW5pbmcgYWxsIGZldGNoZWQgaW5mb3JtYXRpb24uXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBmZXRjaE1lZXRpbmdQcmVwSW5mbyhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIG5sdUVudGl0aWVzOiBNZWV0aW5nUHJlcE5sdUVudGl0aWVzXG4pOiBQcm9taXNlPEFnZ3JlZ2F0ZWRQcmVwUmVzdWx0cz4ge1xuICBsb2dnZXIuaW5mbyhcbiAgICBgW21lZXRpbmdQcmVwU2tpbGxdIFN0YXJ0aW5nIG1lZXRpbmcgcHJlcGFyYXRpb24gZm9yIHVzZXIgJHt1c2VySWR9IGFuZCBtZWV0aW5nOiAke25sdUVudGl0aWVzLm1lZXRpbmdfcmVmZXJlbmNlfWBcbiAgKTtcblxuICBjb25zdCBhZ2dyZWdhdGVkUmVzdWx0czogQWdncmVnYXRlZFByZXBSZXN1bHRzID0ge1xuICAgIG1lZXRpbmdfcmVmZXJlbmNlX2lkZW50aWZpZWQ6IG5sdUVudGl0aWVzLm1lZXRpbmdfcmVmZXJlbmNlLFxuICAgIHJlc3VsdHNfYnlfc291cmNlOiBbXSxcbiAgICBlcnJvcnNfZW5jb3VudGVyZWQ6IFtdLFxuICB9O1xuXG4gIC8vIDEuIFJlc29sdmUgbmx1RW50aXRpZXMubWVldGluZ19yZWZlcmVuY2UgdG8gYSBzcGVjaWZpYyBjYWxlbmRhciBldmVudC5cbiAgbGV0IHJlc29sdmVkRXZlbnQ6IENhbGVuZGFyRXZlbnRTdW1tYXJ5IHwgbnVsbCA9IG51bGw7XG4gIHRyeSB7XG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICBgW21lZXRpbmdQcmVwU2tpbGxdIEF0dGVtcHRpbmcgdG8gcmVzb2x2ZSBtZWV0aW5nX3JlZmVyZW5jZTogXCIke25sdUVudGl0aWVzLm1lZXRpbmdfcmVmZXJlbmNlfVwiIHVzaW5nIGZpbmRFdmVudEJ5RnV6enlSZWZlcmVuY2UuYFxuICAgICk7XG4gICAgY29uc3QgZXZlbnRSZXNwb25zZSA9IGF3YWl0IGNhbGVuZGFyU2tpbGxzLmZpbmRFdmVudEJ5RnV6enlSZWZlcmVuY2UoXG4gICAgICB1c2VySWQsXG4gICAgICBubHVFbnRpdGllcy5tZWV0aW5nX3JlZmVyZW5jZSxcbiAgICAgIG5sdUVudGl0aWVzLm92ZXJhbGxfbG9va2JhY2tfcGVyaW9kXG4gICAgKTtcblxuICAgIGlmIChldmVudFJlc3BvbnNlLm9rICYmIGV2ZW50UmVzcG9uc2UuZGF0YSkge1xuICAgICAgcmVzb2x2ZWRFdmVudCA9IGV2ZW50UmVzcG9uc2UuZGF0YTtcbiAgICAgIGFnZ3JlZ2F0ZWRSZXN1bHRzLmlkZW50aWZpZWRfY2FsZW5kYXJfZXZlbnQgPSByZXNvbHZlZEV2ZW50OyAvLyBTdG9yZSB0aGUgcmVzb2x2ZWQgZXZlbnRcbiAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICBgW21lZXRpbmdQcmVwU2tpbGxdIFN1Y2Nlc3NmdWxseSByZXNvbHZlZCBtZWV0aW5nIHJlZmVyZW5jZSB0byBldmVudDogXCIke3Jlc29sdmVkRXZlbnQuc3VtbWFyeX1cIiAoSUQ6ICR7cmVzb2x2ZWRFdmVudC5pZH0pYFxuICAgICAgKTtcbiAgICB9IGVsc2UgaWYgKGV2ZW50UmVzcG9uc2UuZXJyb3IpIHtcbiAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICBgW21lZXRpbmdQcmVwU2tpbGxdIENvdWxkIG5vdCByZXNvbHZlIG1lZXRpbmdfcmVmZXJlbmNlIFwiJHtubHVFbnRpdGllcy5tZWV0aW5nX3JlZmVyZW5jZX1cIiB0byBhIHNwZWNpZmljIGV2ZW50LiBFcnJvcjogJHtldmVudFJlc3BvbnNlLmVycm9yLm1lc3NhZ2V9YFxuICAgICAgKTtcbiAgICAgIGFnZ3JlZ2F0ZWRSZXN1bHRzLmVycm9yc19lbmNvdW50ZXJlZD8ucHVzaCh7XG4gICAgICAgIHNvdXJjZV9hdHRlbXB0ZWQ6ICdjYWxlbmRhcl9sb29rdXAnLFxuICAgICAgICBtZXNzYWdlOiBgQ291bGQgbm90IHJlc29sdmUgbWVldGluZyByZWZlcmVuY2U6ICR7ZXZlbnRSZXNwb25zZS5lcnJvci5tZXNzYWdlfWAsXG4gICAgICAgIGRldGFpbHM6IEpTT04uc3RyaW5naWZ5KGV2ZW50UmVzcG9uc2UuZXJyb3IuZGV0YWlscyksXG4gICAgICB9KTtcbiAgICB9IGVsc2Uge1xuICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgIGBbbWVldGluZ1ByZXBTa2lsbF0gTm8gc3BlY2lmaWMgY2FsZW5kYXIgZXZlbnQgZm91bmQgZm9yIHJlZmVyZW5jZTogXCIke25sdUVudGl0aWVzLm1lZXRpbmdfcmVmZXJlbmNlfVwiLiBQcm9jZWVkaW5nIHdpdGhvdXQgc3BlY2lmaWMgZXZlbnQgY29udGV4dC5gXG4gICAgICApO1xuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbbWVldGluZ1ByZXBTa2lsbF0gQ3JpdGljYWwgZXJyb3IgZHVyaW5nIGZpbmRFdmVudEJ5RnV6enlSZWZlcmVuY2UgZm9yIFwiJHtubHVFbnRpdGllcy5tZWV0aW5nX3JlZmVyZW5jZX1cIjogJHtlcnJvci5tZXNzYWdlfWAsXG4gICAgICBlcnJvclxuICAgICk7XG4gICAgYWdncmVnYXRlZFJlc3VsdHMuZXJyb3JzX2VuY291bnRlcmVkPy5wdXNoKHtcbiAgICAgIHNvdXJjZV9hdHRlbXB0ZWQ6ICdjYWxlbmRhcl9sb29rdXAnLFxuICAgICAgbWVzc2FnZTogYENyaXRpY2FsIGVycm9yIHJlc29sdmluZyBtZWV0aW5nIHJlZmVyZW5jZTogJHtlcnJvci5tZXNzYWdlfWAsXG4gICAgICBkZXRhaWxzOiBlcnJvci5zdGFjayxcbiAgICB9KTtcbiAgfVxuICAvLyBFbnN1cmUgYWdncmVnYXRlZFJlc3VsdHMuaWRlbnRpZmllZF9jYWxlbmRhcl9ldmVudCBpcyBjb3JyZWN0bHkgcGFzc2VkIGFsb25nIGlmIHJlc29sdXRpb24gaGFwcGVuZWRcbiAgLy8gVGhpcyBpcyBhbHJlYWR5IGhhbmRsZWQgYWJvdmUgYnkgYXNzaWduaW5nIHRvIGFnZ3JlZ2F0ZWRSZXN1bHRzLmlkZW50aWZpZWRfY2FsZW5kYXJfZXZlbnRcblxuICBmb3IgKGNvbnN0IHJlcXVlc3Qgb2Ygbmx1RW50aXRpZXMuaW5mb3JtYXRpb25fcmVxdWVzdHMpIHtcbiAgICBjb25zdCBzb3VyY2VSZXN1bHRFbnRyeTogUHJlcFJlc3VsdFNvdXJjZUVudHJ5ID0ge1xuICAgICAgc291cmNlOiByZXF1ZXN0LnNvdXJjZSxcbiAgICAgIHNlYXJjaF9wYXJhbWV0ZXJzX3VzZWQ6IHJlcXVlc3Quc2VhcmNoX3BhcmFtZXRlcnMsXG4gICAgICByZXN1bHRzOiBbXSxcbiAgICAgIGNvdW50OiAwLFxuICAgIH07XG5cbiAgICB0cnkge1xuICAgICAgbG9nZ2VyLmRlYnVnKFxuICAgICAgICBgW21lZXRpbmdQcmVwU2tpbGxdIFByb2Nlc3Npbmcgc291cmNlOiAke3JlcXVlc3Quc291cmNlfSB3aXRoIHBhcmFtczogJHtKU09OLnN0cmluZ2lmeShyZXF1ZXN0LnNlYXJjaF9wYXJhbWV0ZXJzKX1gXG4gICAgICApO1xuICAgICAgc3dpdGNoIChyZXF1ZXN0LnNvdXJjZSkge1xuICAgICAgICBjYXNlICdnbWFpbCc6XG4gICAgICAgICAgY29uc3QgZ21haWxQYXJhbXMgPVxuICAgICAgICAgICAgcmVxdWVzdC5zZWFyY2hfcGFyYW1ldGVycyBhcyBHbWFpbFNlYXJjaFBhcmFtZXRlcnM7XG4gICAgICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgICAgICBgW21lZXRpbmdQcmVwU2tpbGxdIENhbGxpbmcgc2VhcmNoRW1haWxzRm9yUHJlcCB3aXRoIHBhcmFtczogJHtKU09OLnN0cmluZ2lmeShnbWFpbFBhcmFtcyl9IGFuZCBtZWV0aW5nIGNvbnRleHQ6ICR7YWdncmVnYXRlZFJlc3VsdHMuaWRlbnRpZmllZF9jYWxlbmRhcl9ldmVudD8uc3VtbWFyeX1gXG4gICAgICAgICAgKTtcblxuICAgICAgICAgIGNvbnN0IGdtYWlsU2VhcmNoUmVzcG9uc2UgPSBhd2FpdCBnbWFpbFNraWxscy5zZWFyY2hFbWFpbHNGb3JQcmVwKFxuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgZ21haWxQYXJhbXMsXG4gICAgICAgICAgICBhZ2dyZWdhdGVkUmVzdWx0cy5pZGVudGlmaWVkX2NhbGVuZGFyX2V2ZW50LCAvLyBQYXNzIHJlc29sdmVkIG1lZXRpbmcgZm9yIGNvbnRleHRcbiAgICAgICAgICAgIDUgLy8gTGltaXQgdG8gNSByZXN1bHRzIGZvciBub3dcbiAgICAgICAgICApO1xuXG4gICAgICAgICAgaWYgKGdtYWlsU2VhcmNoUmVzcG9uc2Uub2sgJiYgZ21haWxTZWFyY2hSZXNwb25zZS5kYXRhKSB7XG4gICAgICAgICAgICBzb3VyY2VSZXN1bHRFbnRyeS5yZXN1bHRzID0gZ21haWxTZWFyY2hSZXNwb25zZS5kYXRhLnJlc3VsdHM7XG4gICAgICAgICAgICBzb3VyY2VSZXN1bHRFbnRyeS5jb3VudCA9IGdtYWlsU2VhcmNoUmVzcG9uc2UuZGF0YS5yZXN1bHRzLmxlbmd0aDtcbiAgICAgICAgICAgIHNvdXJjZVJlc3VsdEVudHJ5LnNlYXJjaF9xdWVyeV9leGVjdXRlZCA9XG4gICAgICAgICAgICAgIGdtYWlsU2VhcmNoUmVzcG9uc2UuZGF0YS5xdWVyeV9leGVjdXRlZDtcbiAgICAgICAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICAgICAgICBgW21lZXRpbmdQcmVwU2tpbGxdIHNlYXJjaEVtYWlsc0ZvclByZXAgcmV0dXJuZWQgJHtzb3VyY2VSZXN1bHRFbnRyeS5jb3VudH0gcmVzdWx0cy4gUXVlcnk6ICR7c291cmNlUmVzdWx0RW50cnkuc2VhcmNoX3F1ZXJ5X2V4ZWN1dGVkfWBcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICAgICAgICAgYFttZWV0aW5nUHJlcFNraWxsXSBzZWFyY2hFbWFpbHNGb3JQcmVwIGZhaWxlZDogJHtnbWFpbFNlYXJjaFJlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICBzb3VyY2VSZXN1bHRFbnRyeS5lcnJvcl9tZXNzYWdlID1cbiAgICAgICAgICAgICAgZ21haWxTZWFyY2hSZXNwb25zZS5lcnJvcj8ubWVzc2FnZSB8fFxuICAgICAgICAgICAgICAnRmFpbGVkIHRvIGZldGNoIEdtYWlsIHJlc3VsdHMuJztcbiAgICAgICAgICAgIC8vIEFsc28gYWRkIHRvIG92ZXJhbGwgZXJyb3JzXG4gICAgICAgICAgICBhZ2dyZWdhdGVkUmVzdWx0cy5lcnJvcnNfZW5jb3VudGVyZWQ/LnB1c2goe1xuICAgICAgICAgICAgICBzb3VyY2VfYXR0ZW1wdGVkOiAnZ21haWwnLFxuICAgICAgICAgICAgICBtZXNzYWdlOiBzb3VyY2VSZXN1bHRFbnRyeS5lcnJvcl9tZXNzYWdlLFxuICAgICAgICAgICAgICBkZXRhaWxzOiBKU09OLnN0cmluZ2lmeShnbWFpbFNlYXJjaFJlc3BvbnNlLmVycm9yPy5kZXRhaWxzKSxcbiAgICAgICAgICAgIH0pO1xuICAgICAgICAgIH1cbiAgICAgICAgICBicmVhaztcbiAgICAgICAgY2FzZSAnc2xhY2snOlxuICAgICAgICAgIGNvbnN0IHNsYWNrUGFyYW1zID1cbiAgICAgICAgICAgIHJlcXVlc3Quc2VhcmNoX3BhcmFtZXRlcnMgYXMgU2xhY2tTZWFyY2hQYXJhbWV0ZXJzO1xuICAgICAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICAgICAgYFttZWV0aW5nUHJlcFNraWxsXSBDYWxsaW5nIFNsYWNrIHNraWxsIHdpdGggcGFyYW1zOmAsXG4gICAgICAgICAgICBzbGFja1BhcmFtc1xuICAgICAgICAgICk7XG4gICAgICAgICAgLy8gVE9ETzogUmVwbGFjZSB3aXRoIGFjdHVhbCBjYWxsIHRvIGFuIGVuaGFuY2VkIFNsYWNrIHNraWxsXG4gICAgICAgICAgLy8gY29uc3Qgc2xhY2tSZXN1bHRzOiBTbGFja01lc3NhZ2VTbmlwcGV0W10gPSBhd2FpdCBzbGFja1NraWxscy5zZWFyY2hTbGFja01lc3NhZ2VzRm9yUHJlcChcbiAgICAgICAgICAvLyAgIHVzZXJJZCxcbiAgICAgICAgICAvLyAgIHNsYWNrUGFyYW1zLFxuICAgICAgICAgIC8vICAgYWdncmVnYXRlZFJlc3VsdHMuaWRlbnRpZmllZF9jYWxlbmRhcl9ldmVudCAvLyBQYXNzIHJlc29sdmVkIG1lZXRpbmcgZm9yIGNvbnRleHRcbiAgICAgICAgICAvLyApO1xuICAgICAgICAgIC8vIHNvdXJjZVJlc3VsdEVudHJ5LnJlc3VsdHMgPSBzbGFja1Jlc3VsdHM7XG4gICAgICAgICAgLy8gc291cmNlUmVzdWx0RW50cnkuY291bnQgPSBzbGFja1Jlc3VsdHMubGVuZ3RoO1xuICAgICAgICAgIC8vIHNvdXJjZVJlc3VsdEVudHJ5LnNlYXJjaF9xdWVyeV9leGVjdXRlZCA9IFwiQWN0dWFsIFNsYWNrIHF1ZXJ5IGJ1aWx0IGJ5IHNsYWNrU2tpbGxzXCI7XG5cbiAgICAgICAgICAvLyBQbGFjZWhvbGRlciBpbXBsZW1lbnRhdGlvbiBmb3IgU2xhY2tcbiAgICAgICAgICBpZiAoc2xhY2tQYXJhbXMudGV4dF9rZXl3b3Jkcz8uaW5jbHVkZXMoJ1E0IHN0cmF0ZWd5JykpIHtcbiAgICAgICAgICAgIHNvdXJjZVJlc3VsdEVudHJ5LnJlc3VsdHMgPSBbXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICB0czogJzEyMzQ1Njc4OTAuMTIzNDU2JyxcbiAgICAgICAgICAgICAgICBjaGFubmVsOiB7XG4gICAgICAgICAgICAgICAgICBpZDogJ0MxMjNBQkMnLFxuICAgICAgICAgICAgICAgICAgbmFtZTogc2xhY2tQYXJhbXMuY2hhbm5lbF9uYW1lIHx8ICdzYWxlcycsXG4gICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICB1c2VyOiB7IGlkOiAnVUFCQzEyMycsIG5hbWU6ICdzb21ldXNlcicgfSxcbiAgICAgICAgICAgICAgICB0ZXh0OiAnRGlzY3Vzc2luZyBRNCBzdHJhdGVneSBkb2N1bWVudCwgcGxlYXNlIHJldmlldyBhdHRhY2htZW50LicsXG4gICAgICAgICAgICAgICAgcGVybWFsaW5rOlxuICAgICAgICAgICAgICAgICAgJ2h0dHBzOi8vYXBwLnNsYWNrLmNvbS9jbGllbnQvVDEyM0FCQy9DMTIzQUJDL3AxMjM0NTY3ODkwMTIzNDU2JyxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIF07XG4gICAgICAgICAgICBzb3VyY2VSZXN1bHRFbnRyeS5jb3VudCA9IDE7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIHNvdXJjZVJlc3VsdEVudHJ5LnJlc3VsdHMgPSBbXTtcbiAgICAgICAgICAgIHNvdXJjZVJlc3VsdEVudHJ5LmNvdW50ID0gMDtcbiAgICAgICAgICB9XG4gICAgICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgICAgICBgW21lZXRpbmdQcmVwU2tpbGxdIFNsYWNrIHNvdXJjZSBwcm9jZXNzaW5nIGlzIGN1cnJlbnRseSB1c2luZyBwbGFjZWhvbGRlciBkYXRhLmBcbiAgICAgICAgICApO1xuICAgICAgICAgIC8vIEVuZCBQbGFjZWhvbGRlclxuICAgICAgICAgIGJyZWFrO1xuICAgICAgICBjYXNlICdub3Rpb24nOlxuICAgICAgICAgIGNvbnN0IG5vdGlvblBhcmFtcyA9XG4gICAgICAgICAgICByZXF1ZXN0LnNlYXJjaF9wYXJhbWV0ZXJzIGFzIE5vdGlvblNlYXJjaFBhcmFtZXRlcnM7XG4gICAgICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgICAgICBgW21lZXRpbmdQcmVwU2tpbGxdIENhbGxpbmcgTm90aW9uIHNraWxsIHdpdGggcGFyYW1zOmAsXG4gICAgICAgICAgICBub3Rpb25QYXJhbXNcbiAgICAgICAgICApO1xuICAgICAgICAgIC8vIFRPRE86IFJlcGxhY2Ugd2l0aCBhY3R1YWwgY2FsbCB0byBhbiBlbmhhbmNlZCBOb3Rpb24gc2tpbGxcbiAgICAgICAgICAvLyBjb25zdCBub3Rpb25SZXN1bHRzOiBOb3Rpb25QYWdlU3VtbWFyeVtdID0gYXdhaXQgbm90aW9uU2tpbGxzLnNlYXJjaE5vdGlvbkZvclByZXAoXG4gICAgICAgICAgLy8gICB1c2VySWQsXG4gICAgICAgICAgLy8gICBub3Rpb25QYXJhbXMsXG4gICAgICAgICAgLy8gICBhZ2dyZWdhdGVkUmVzdWx0cy5pZGVudGlmaWVkX2NhbGVuZGFyX2V2ZW50IC8vIFBhc3MgcmVzb2x2ZWQgbWVldGluZyBmb3IgY29udGV4dFxuICAgICAgICAgIC8vICk7XG4gICAgICAgICAgLy8gc291cmNlUmVzdWx0RW50cnkucmVzdWx0cyA9IG5vdGlvblJlc3VsdHM7XG4gICAgICAgICAgLy8gc291cmNlUmVzdWx0RW50cnkuY291bnQgPSBub3Rpb25SZXN1bHRzLmxlbmd0aDtcbiAgICAgICAgICAvLyBzb3VyY2VSZXN1bHRFbnRyeS5zZWFyY2hfcXVlcnlfZXhlY3V0ZWQgPSBcIkFjdHVhbCBOb3Rpb24gcXVlcnkvZmlsdGVyIGJ1aWx0IGJ5IG5vdGlvblNraWxsc1wiO1xuXG4gICAgICAgICAgLy8gUGxhY2Vob2xkZXIgaW1wbGVtZW50YXRpb24gZm9yIE5vdGlvblxuICAgICAgICAgIGlmIChcbiAgICAgICAgICAgIG5vdGlvblBhcmFtcy5wYWdlX3RpdGxlX2tleXdvcmRzPy5pbmNsdWRlcygnQWNtZSBQcm9qZWN0JykgfHxcbiAgICAgICAgICAgIG5vdGlvblBhcmFtcy5jb250ZW50X2tleXdvcmRzPy5pbmNsdWRlcygnQWNtZSBDb3JwJylcbiAgICAgICAgICApIHtcbiAgICAgICAgICAgIHNvdXJjZVJlc3VsdEVudHJ5LnJlc3VsdHMgPSBbXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBpZDogJ25vdGlvbl9zaW1fcGFnZV8xJyxcbiAgICAgICAgICAgICAgICB0aXRsZTogJ0FjbWUgUHJvamVjdCBQbGFuJyxcbiAgICAgICAgICAgICAgICB1cmw6ICdodHRwczovL3d3dy5ub3Rpb24uc28vc2ltL2FjbWVwcm9qZWN0cGxhbicsXG4gICAgICAgICAgICAgICAgbGFzdF9lZGl0ZWRfdGltZTogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgICAgICAgIHByZXZpZXdfdGV4dDpcbiAgICAgICAgICAgICAgICAgICdJbml0aWFsIHByb2plY3QgcGxhbiBhbmQgZGVsaXZlcmFibGVzIGZvciBBY21lIENvcnAuLi4nLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgXTtcbiAgICAgICAgICAgIHNvdXJjZVJlc3VsdEVudHJ5LmNvdW50ID0gMTtcbiAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgc291cmNlUmVzdWx0RW50cnkucmVzdWx0cyA9IFtdO1xuICAgICAgICAgICAgc291cmNlUmVzdWx0RW50cnkuY291bnQgPSAwO1xuICAgICAgICAgIH1cbiAgICAgICAgICBsb2dnZXIud2FybihcbiAgICAgICAgICAgIGBbbWVldGluZ1ByZXBTa2lsbF0gTm90aW9uIHNvdXJjZSBwcm9jZXNzaW5nIGlzIGN1cnJlbnRseSB1c2luZyBwbGFjZWhvbGRlciBkYXRhLmBcbiAgICAgICAgICApO1xuICAgICAgICAgIC8vIEVuZCBQbGFjZWhvbGRlclxuICAgICAgICAgIGJyZWFrO1xuICAgICAgICBjYXNlICdjYWxlbmRhcl9ldmVudHMnOlxuICAgICAgICAgIGNvbnN0IGNhbGVuZGFyUGFyYW1zID1cbiAgICAgICAgICAgIHJlcXVlc3Quc2VhcmNoX3BhcmFtZXRlcnMgYXMgQ2FsZW5kYXJFdmVudHNTZWFyY2hQYXJhbWV0ZXJzO1xuICAgICAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICAgICAgYFttZWV0aW5nUHJlcFNraWxsXSBDYWxsaW5nIENhbGVuZGFyIEV2ZW50cyBza2lsbCB3aXRoIHBhcmFtczpgLFxuICAgICAgICAgICAgY2FsZW5kYXJQYXJhbXNcbiAgICAgICAgICApO1xuICAgICAgICAgIC8vIFRPRE86IFJlcGxhY2Ugd2l0aCBhY3R1YWwgY2FsbCB0byBhbiBlbmhhbmNlZCBDYWxlbmRhciBza2lsbFxuICAgICAgICAgIC8vIGNvbnN0IHJlbGF0ZWRFdmVudHM6IENhbGVuZGFyRXZlbnRTdW1tYXJ5W10gPSBhd2FpdCBjYWxlbmRhclNraWxscy5zZWFyY2hSZWxhdGVkQ2FsZW5kYXJFdmVudHNGb3JQcmVwKFxuICAgICAgICAgIC8vICAgdXNlcklkLFxuICAgICAgICAgIC8vICAgY2FsZW5kYXJQYXJhbXMsXG4gICAgICAgICAgLy8gICBhZ2dyZWdhdGVkUmVzdWx0cy5pZGVudGlmaWVkX2NhbGVuZGFyX2V2ZW50IC8vIFBhc3MgcmVzb2x2ZWQgbWVldGluZyBmb3IgY29udGV4dFxuICAgICAgICAgIC8vICk7XG4gICAgICAgICAgLy8gc291cmNlUmVzdWx0RW50cnkucmVzdWx0cyA9IHJlbGF0ZWRFdmVudHM7XG4gICAgICAgICAgLy8gc291cmNlUmVzdWx0RW50cnkuY291bnQgPSByZWxhdGVkRXZlbnRzLmxlbmd0aDtcbiAgICAgICAgICAvLyBzb3VyY2VSZXN1bHRFbnRyeS5zZWFyY2hfcXVlcnlfZXhlY3V0ZWQgPSBcIkFjdHVhbCBDYWxlbmRhciBxdWVyeS9maWx0ZXIgYnVpbHQgYnkgY2FsZW5kYXJTa2lsbHNcIjtcblxuICAgICAgICAgIC8vIFBsYWNlaG9sZGVyIGltcGxlbWVudGF0aW9uIGZvciBDYWxlbmRhciBFdmVudHNcbiAgICAgICAgICBpZiAoXG4gICAgICAgICAgICBjYWxlbmRhclBhcmFtcy5yZWxhdGVkX3RvX2F0dGVuZGVlc19vZl9tZWV0aW5nX3JlZmVyZW5jZSAmJlxuICAgICAgICAgICAgYWdncmVnYXRlZFJlc3VsdHMuaWRlbnRpZmllZF9jYWxlbmRhcl9ldmVudD8uc3VtbWFyeT8uaW5jbHVkZXMoXG4gICAgICAgICAgICAgICdBY21lIENvcnAnXG4gICAgICAgICAgICApXG4gICAgICAgICAgKSB7XG4gICAgICAgICAgICBzb3VyY2VSZXN1bHRFbnRyeS5yZXN1bHRzID0gW1xuICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgaWQ6ICdyZWxhdGVkX2V2ZW50XzQ1NicsXG4gICAgICAgICAgICAgICAgc3VtbWFyeTogJ1Bhc3QgUTIgUmV2aWV3IC0gQWNtZSBDb3JwJyxcbiAgICAgICAgICAgICAgICBzdGFydDogbmV3IERhdGUoXG4gICAgICAgICAgICAgICAgICBEYXRlLm5vdygpIC0gMzAgKiAyNCAqIDM2MDAgKiAxMDAwXG4gICAgICAgICAgICAgICAgKS50b0lTT1N0cmluZygpLCAvLyBBcHByb3ggYSBtb250aCBhZ29cbiAgICAgICAgICAgICAgICBlbmQ6IG5ldyBEYXRlKFxuICAgICAgICAgICAgICAgICAgRGF0ZS5ub3coKSAtIDMwICogMjQgKiAzNjAwICogMTAwMCArIDM2MDAgKiAxMDAwXG4gICAgICAgICAgICAgICAgKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgICAgICAgIGh0bWxMaW5rOlxuICAgICAgICAgICAgICAgICAgJ2h0dHBzOi8vY2FsZW5kYXIuZ29vZ2xlLmNvbS9jYWxlbmRhci9ldmVudD9laWQ9c2ltXzQ1NicsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBdO1xuICAgICAgICAgICAgc291cmNlUmVzdWx0RW50cnkuY291bnQgPSAxO1xuICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBzb3VyY2VSZXN1bHRFbnRyeS5yZXN1bHRzID0gW107XG4gICAgICAgICAgICBzb3VyY2VSZXN1bHRFbnRyeS5jb3VudCA9IDA7XG4gICAgICAgICAgfVxuICAgICAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICAgICAgYFttZWV0aW5nUHJlcFNraWxsXSBDYWxlbmRhciBFdmVudHMgc291cmNlIHByb2Nlc3NpbmcgaXMgY3VycmVudGx5IHVzaW5nIHBsYWNlaG9sZGVyIGRhdGEuYFxuICAgICAgICAgICk7XG4gICAgICAgICAgLy8gRW5kIFBsYWNlaG9sZGVyXG4gICAgICAgICAgYnJlYWs7XG4gICAgICAgIGRlZmF1bHQ6XG4gICAgICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgICAgICBgW21lZXRpbmdQcmVwU2tpbGxdIFVua25vd24gc291cmNlIHR5cGU6ICR7cmVxdWVzdC5zb3VyY2V9YFxuICAgICAgICAgICk7XG4gICAgICAgICAgc291cmNlUmVzdWx0RW50cnkuZXJyb3JfbWVzc2FnZSA9IGBVbmtub3duIHNvdXJjZSB0eXBlOiAke3JlcXVlc3Quc291cmNlfWA7XG4gICAgICAgICAgY29uc3QgdW5rRXJyb3I6IFByZXBFcnJvck1lc3NhZ2UgPSB7XG4gICAgICAgICAgICBzb3VyY2VfYXR0ZW1wdGVkOiByZXF1ZXN0LnNvdXJjZSxcbiAgICAgICAgICAgIG1lc3NhZ2U6IGBVbmtub3duIHNvdXJjZSB0eXBlIHJlcXVlc3RlZDogJHtyZXF1ZXN0LnNvdXJjZX1gLFxuICAgICAgICAgIH07XG4gICAgICAgICAgYWdncmVnYXRlZFJlc3VsdHMuZXJyb3JzX2VuY291bnRlcmVkPy5wdXNoKHVua0Vycm9yKTtcbiAgICAgIH1cbiAgICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgIGBbbWVldGluZ1ByZXBTa2lsbF0gRXJyb3IgcHJvY2Vzc2luZyBzb3VyY2UgJHtyZXF1ZXN0LnNvdXJjZX06ICR7ZXJyb3IubWVzc2FnZX1gLFxuICAgICAgICBlcnJvclxuICAgICAgKTtcbiAgICAgIHNvdXJjZVJlc3VsdEVudHJ5LmVycm9yX21lc3NhZ2UgPSBgRXJyb3IgcHJvY2Vzc2luZyBzb3VyY2UgJHtyZXF1ZXN0LnNvdXJjZX06ICR7ZXJyb3IubWVzc2FnZX1gO1xuICAgICAgY29uc3QgcHJvY0Vycm9yOiBQcmVwRXJyb3JNZXNzYWdlID0ge1xuICAgICAgICBzb3VyY2VfYXR0ZW1wdGVkOiByZXF1ZXN0LnNvdXJjZSxcbiAgICAgICAgbWVzc2FnZTogZXJyb3IubWVzc2FnZSxcbiAgICAgICAgZGV0YWlsczogZXJyb3Iuc3RhY2ssXG4gICAgICB9O1xuICAgICAgYWdncmVnYXRlZFJlc3VsdHMuZXJyb3JzX2VuY291bnRlcmVkPy5wdXNoKHByb2NFcnJvcik7XG4gICAgfVxuICAgIGFnZ3JlZ2F0ZWRSZXN1bHRzLnJlc3VsdHNfYnlfc291cmNlLnB1c2goc291cmNlUmVzdWx0RW50cnkpO1xuICB9XG5cbiAgLy8gVE9ETzpcbiAgLy8gMi4gT3B0aW9uYWxseSwgZ2VuZXJhdGUgYW4gb3ZlcmFsbF9zdW1tYXJ5X25vdGVzIHVzaW5nIGFuIExMTSBiYXNlZCBvbiBhbGwgYWdncmVnYXRlZFJlc3VsdHMucmVzdWx0c19ieV9zb3VyY2UuXG4gIHRyeSB7XG4gICAgY29uc3QgZm91bmRJdGVtcyA9IGFnZ3JlZ2F0ZWRSZXN1bHRzLnJlc3VsdHNfYnlfc291cmNlLnJlZHVjZShcbiAgICAgIChhY2MsIHJzKSA9PiBhY2MgKyBycy5jb3VudCxcbiAgICAgIDBcbiAgICApO1xuICAgIGlmIChmb3VuZEl0ZW1zID4gMCkge1xuICAgICAgLy8gQ29uc3RydWN0IGEgc2ltcGxlIGR5bmFtaWMgc3VtbWFyeSBiYXNlZCBvbiBjb3VudHNcbiAgICAgIGNvbnN0IHN1bW1hcnlQYXJ0czogc3RyaW5nW10gPSBbXTtcbiAgICAgIGFnZ3JlZ2F0ZWRSZXN1bHRzLnJlc3VsdHNfYnlfc291cmNlLmZvckVhY2goKHJzKSA9PiB7XG4gICAgICAgIGlmIChycy5jb3VudCA+IDApIHtcbiAgICAgICAgICBzdW1tYXJ5UGFydHMucHVzaChgJHtycy5jb3VudH0gaXRlbShzKSBmcm9tICR7cnMuc291cmNlfWApO1xuICAgICAgICB9XG4gICAgICB9KTtcbiAgICAgIGlmIChzdW1tYXJ5UGFydHMubGVuZ3RoID4gMCkge1xuICAgICAgICBhZ2dyZWdhdGVkUmVzdWx0cy5vdmVyYWxsX3N1bW1hcnlfbm90ZXMgPSBgRm91bmQ6ICR7c3VtbWFyeVBhcnRzLmpvaW4oJywgJyl9LiAoRGV0YWlsZWQgQUkgc3VtbWFyeSBwZW5kaW5nIGZ1bGwgZGF0YSBzb3VyY2UgaW50ZWdyYXRpb24uKWA7XG4gICAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICAgIGBbbWVldGluZ1ByZXBTa2lsbF0gR2VuZXJhdGVkIGJhc2ljIHN1bW1hcnk6ICR7YWdncmVnYXRlZFJlc3VsdHMub3ZlcmFsbF9zdW1tYXJ5X25vdGVzfWBcbiAgICAgICAgKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIC8vIFRoaXMgY2FzZSBzaG91bGQgaWRlYWxseSBub3QgYmUgaGl0IGlmIGZvdW5kSXRlbXMgPiAwLCBidXQgYXMgYSBmYWxsYmFjazpcbiAgICAgICAgYWdncmVnYXRlZFJlc3VsdHMub3ZlcmFsbF9zdW1tYXJ5X25vdGVzID1cbiAgICAgICAgICAnU29tZSBpdGVtcyB3ZXJlIGZvdW5kLCBidXQgY291bnRzIHBlciBzb3VyY2UgYXJlIHplcm8uIChEZXRhaWxlZCBBSSBzdW1tYXJ5IHBlbmRpbmcuKSc7XG4gICAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICAgIGBbbWVldGluZ1ByZXBTa2lsbF0gSXRlbXMgZm91bmQgYnV0IG5vIGNvdW50cyBwZXIgc291cmNlIGZvciBzdW1tYXJ5LmBcbiAgICAgICAgKTtcbiAgICAgIH1cblxuICAgICAgLy8gS2VlcCBMTE0gc3VtbWFyaXphdGlvbiBjb21tZW50ZWQgb3V0IGZvciBub3dcbiAgICAgIC8vIGxvZ2dlci5pbmZvKGBbbWVldGluZ1ByZXBTa2lsbF0gUGxhY2Vob2xkZXIgZm9yIEFJIHN1bW1hcml6YXRpb24gb2YgY29sbGVjdGVkIGRhdGEuYCk7XG4gICAgICAvLyBjb25zdCBzdW1tYXJ5Q29udGV4dCA9IGFnZ3JlZ2F0ZWRSZXN1bHRzLnJlc3VsdHNfYnlfc291cmNlXG4gICAgICAvLyAgIC5maWx0ZXIocnMgPT4gcnMucmVzdWx0cy5sZW5ndGggPiAwKVxuICAgICAgLy8gICAubWFwKHJzID0+IGBTb3VyY2UgJHtycy5zb3VyY2V9IGZvdW5kICR7cnMuY291bnR9IGl0ZW1zOiAke0pTT04uc3RyaW5naWZ5KHJzLnJlc3VsdHMuc2xpY2UoMCwgMikpfS4uLmApXG4gICAgICAvLyAgIC5qb2luKCdcXG4nKTtcbiAgICAgIC8vIGFnZ3JlZ2F0ZWRSZXN1bHRzLm92ZXJhbGxfc3VtbWFyeV9ub3RlcyA9IGF3YWl0IGxsbVV0aWxpdGllcy5zdW1tYXJpemVUZXh0KFxuICAgICAgLy8gICBgU3VtbWFyaXplIHRoZSBrZXkgaW5mb3JtYXRpb24gZm91bmQgZm9yIHRoZSBtZWV0aW5nIHByZXBhcmF0aW9uIHJlZ2FyZGluZyBcIiR7YWdncmVnYXRlZFJlc3VsdHMubWVldGluZ19yZWZlcmVuY2VfaWRlbnRpZmllZH1cIi4gQ29udGV4dDogJHtzdW1tYXJ5Q29udGV4dH1gLFxuICAgICAgLy8gICAvLyBtYXhUb2tlbnM6IDIwMFxuICAgICAgLy8gKTtcbiAgICAgIC8vIGxvZ2dlci53YXJuKGBbbWVldGluZ1ByZXBTa2lsbF0gQUkgc3VtbWFyaXphdGlvbiBpcyBjdXJyZW50bHkgdXNpbmcgcGxhY2Vob2xkZXIgZGF0YS5gKTtcbiAgICB9IGVsc2Uge1xuICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgIGBbbWVldGluZ1ByZXBTa2lsbF0gTm8gZGF0YSBmb3VuZCBieSBhbnkgc291cmNlLCBza2lwcGluZyBzdW1tYXJ5IGdlbmVyYXRpb24uYFxuICAgICAgKTtcbiAgICAgIGFnZ3JlZ2F0ZWRSZXN1bHRzLm92ZXJhbGxfc3VtbWFyeV9ub3RlcyA9XG4gICAgICAgICdObyBzcGVjaWZpYyBpbmZvcm1hdGlvbiBpdGVtcyB3ZXJlIGZvdW5kIGZyb20gdGhlIHJlcXVlc3RlZCBzb3VyY2VzLic7XG4gICAgfVxuICB9IGNhdGNoIChzdW1tYXJ5RXJyb3I6IGFueSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbbWVldGluZ1ByZXBTa2lsbF0gRXJyb3IgZHVyaW5nIEFJIHN1bW1hcml6YXRpb246ICR7c3VtbWFyeUVycm9yLm1lc3NhZ2V9YCxcbiAgICAgIHN1bW1hcnlFcnJvclxuICAgICk7XG4gICAgYWdncmVnYXRlZFJlc3VsdHMuZXJyb3JzX2VuY291bnRlcmVkPy5wdXNoKHtcbiAgICAgIHNvdXJjZV9hdHRlbXB0ZWQ6ICdvdmVyYWxsX3N1bW1hcnknLFxuICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBnZW5lcmF0ZSBvdmVyYWxsIHN1bW1hcnk6ICR7c3VtbWFyeUVycm9yLm1lc3NhZ2V9YCxcbiAgICAgIGRldGFpbHM6IHN1bW1hcnlFcnJvci5zdGFjayxcbiAgICB9KTtcbiAgfVxuXG4gIGxvZ2dlci5pbmZvKFxuICAgIGBbbWVldGluZ1ByZXBTa2lsbF0gRmluaXNoZWQgbWVldGluZyBwcmVwYXJhdGlvbiBmb3IgdXNlciAke3VzZXJJZH0uIEZvdW5kICR7YWdncmVnYXRlZFJlc3VsdHMucmVzdWx0c19ieV9zb3VyY2UucmVkdWNlKChhY2MsIHIpID0+IGFjYyArIHIuY291bnQsIDApfSBpdGVtcyBhY3Jvc3MgJHthZ2dyZWdhdGVkUmVzdWx0cy5yZXN1bHRzX2J5X3NvdXJjZS5sZW5ndGh9IHNvdXJjZXMuYFxuICApO1xuICByZXR1cm4gYWdncmVnYXRlZFJlc3VsdHM7XG59XG4iXX0=