import { fetchMeetingPrepInfo } from '../skills/meetingPrepSkill';
import { logger } from '../../_utils/logger';
function formatSourceResults(sourceEntry) {
    if (sourceEntry.error_message) {
        return `  Error fetching from ${sourceEntry.source}: ${sourceEntry.error_message}\n`;
    }
    if (sourceEntry.count === 0) {
        return `  No information found from ${sourceEntry.source}.\n`;
    }
    let details = '';
    switch (sourceEntry.source) {
        case 'gmail':
            const gmailResults = sourceEntry.results;
            details = gmailResults
                .map((r) => `    - Subject: ${r.subject || 'N/A'}, From: ${r.from || 'N/A'}, Snippet: ${r.snippet?.substring(0, 50)}...`)
                .join('\n');
            break;
        case 'slack':
            const slackResults = sourceEntry.results;
            details = slackResults
                .map((r) => `    - Channel: ${r.channel?.name || r.channel?.id || 'N/A'}, User: ${r.user?.name || r.user?.id || 'N/A'}, Text: ${r.text?.substring(0, 50)}...`)
                .join('\n');
            break;
        case 'notion':
            const notionResults = sourceEntry.results;
            details = notionResults
                .map((r) => `    - Title: ${r.title || 'N/A'}, URL: ${r.url || 'N/A'}`)
                .join('\n');
            break;
        case 'calendar_events':
            const calendarResults = sourceEntry.results;
            details = calendarResults
                .map((r) => `    - Summary: ${r.summary || 'N/A'}, Start: ${r.start ? new Date(r.start).toLocaleString() : 'N/A'}`)
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
export async function handleMeetingPreparationRequest(userId, entities) {
    logger.info(`[MeetingPrepCommandHandler] Handling meeting preparation request for user ${userId}, meeting reference: "${entities.meeting_reference}"`);
    logger.debug(`[MeetingPrepCommandHandler] Received NLU entities: ${JSON.stringify(entities)}`);
    try {
        const prepResults = await fetchMeetingPrepInfo(userId, entities);
        logger.info(`[MeetingPrepCommandHandler] Meeting preparation skill finished. Sources processed: ${prepResults.results_by_source.length}`);
        let responseText = `Okay, I've gathered some information for your meeting: "${prepResults.meeting_reference_identified}":\n\n`;
        if (prepResults.identified_calendar_event) {
            responseText += `I've identified this as the event: "${prepResults.identified_calendar_event.summary}" starting at ${prepResults.identified_calendar_event.start ? new Date(prepResults.identified_calendar_event.start).toLocaleString() : 'Unknown time'}.\n\n`;
        }
        else {
            responseText += `I couldn't definitively link this to a specific calendar event based on the reference provided.\n\n`;
        }
        if (prepResults.results_by_source.length > 0) {
            prepResults.results_by_source.forEach((sourceEntry) => {
                responseText += formatSourceResults(sourceEntry);
            });
        }
        else {
            responseText +=
                "I didn't find any specific items from the requested sources.\n";
        }
        if (prepResults.overall_summary_notes) {
            responseText += `\nSummary of Findings:\n${prepResults.overall_summary_notes}\n`;
        }
        if (prepResults.errors_encountered &&
            prepResults.errors_encountered.length > 0) {
            responseText += '\nSome issues were encountered during preparation:\n';
            prepResults.errors_encountered.forEach((err) => {
                responseText += `  - ${err.source_attempted || 'Overall'}: ${err.message}\n`;
            });
        }
        logger.debug(`[MeetingPrepCommandHandler] Final response text: ${responseText}`);
        return responseText;
    }
    catch (error) {
        logger.error(`[MeetingPrepCommandHandler] Critical error handling meeting preparation request: ${error.message}`, error);
        return `I encountered an unexpected error while trying to prepare for your meeting: ${error.message}. Please try again later.`;
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibWVldGluZ1ByZXBDb21tYW5kSGFuZGxlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIm1lZXRpbmdQcmVwQ29tbWFuZEhhbmRsZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBU0EsT0FBTyxFQUFFLG9CQUFvQixFQUFFLE1BQU0sNEJBQTRCLENBQUM7QUFDbEUsT0FBTyxFQUFFLE1BQU0sRUFBRSxNQUFNLHFCQUFxQixDQUFDO0FBRTdDLFNBQVMsbUJBQW1CLENBQUMsV0FBa0M7SUFDN0QsSUFBSSxXQUFXLENBQUMsYUFBYSxFQUFFLENBQUM7UUFDOUIsT0FBTyx5QkFBeUIsV0FBVyxDQUFDLE1BQU0sS0FBSyxXQUFXLENBQUMsYUFBYSxJQUFJLENBQUM7SUFDdkYsQ0FBQztJQUNELElBQUksV0FBVyxDQUFDLEtBQUssS0FBSyxDQUFDLEVBQUUsQ0FBQztRQUM1QixPQUFPLCtCQUErQixXQUFXLENBQUMsTUFBTSxLQUFLLENBQUM7SUFDaEUsQ0FBQztJQUVELElBQUksT0FBTyxHQUFHLEVBQUUsQ0FBQztJQUNqQixRQUFRLFdBQVcsQ0FBQyxNQUFNLEVBQUUsQ0FBQztRQUMzQixLQUFLLE9BQU87WUFDVixNQUFNLFlBQVksR0FBRyxXQUFXLENBQUMsT0FBZ0MsQ0FBQztZQUNsRSxPQUFPLEdBQUcsWUFBWTtpQkFDbkIsR0FBRyxDQUNGLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FDSixrQkFBa0IsQ0FBQyxDQUFDLE9BQU8sSUFBSSxLQUFLLFdBQVcsQ0FBQyxDQUFDLElBQUksSUFBSSxLQUFLLGNBQWMsQ0FBQyxDQUFDLE9BQU8sRUFBRSxTQUFTLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxLQUFLLENBQy9HO2lCQUNBLElBQUksQ0FBQyxJQUFJLENBQUMsQ0FBQztZQUNkLE1BQU07UUFDUixLQUFLLE9BQU87WUFDVixNQUFNLFlBQVksR0FBRyxXQUFXLENBQUMsT0FBZ0MsQ0FBQztZQUNsRSxPQUFPLEdBQUcsWUFBWTtpQkFDbkIsR0FB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QUUsQ0FBQztZQUM3QyxXQUFXLENBQUMsaUJBQWlCLENBQUMsT0FBTyxDQUFDLENBQUMsV0FBVyxFQUFFLEVBQUU7Z0JBQ3BELFlBQVksSUFBSSxtQkFBbUIsQ0FBQyxXQUFXLENBQUMsQ0FBQztZQUNuRCxDQUFDLENBQUMsQ0FBQztRQUNMLENBQUM7YUFBTSxDQUFDO1lBQ04sWUFBWTtnQkFDVixnRUFBZ0UsQ0FBQztRQUNyRSxDQUFDO1FBRUQsSUFBSSxXQUFXLENBQUMscUJBQXFCLEVBQUUsQ0FBQztZQUN0QyxZQUFZLElBQUksMkJBQTJCLFdBQVcsQ0FBQyxxQkFBcUIsSUFBSSxDQUFDO1FBQ25GLENBQUM7UUFFRCxJQUNFLFdBQVcsQ0FBQyxrQkFBa0I7WUFDOUIsV0FBVyxDQUFDLGtCQUFrQixDQUFDLE1BQU0sR0FBRyxDQUFDLEVBQ3pDLENBQUM7WUFDRCxZQUFZLElBQUksc0RBQXNELENBQUM7WUFDdkUsV0FBVyxDQUFDLGtCQUFrQixDQUFDLE9BQU8sQ0FBQyxDQUFDLEdBQUcsRUFBRSxFQUFFO2dCQUM3QyxZQUFZLElBQUksT0FBTyxHQUFHLENBQUMsZ0JBQWdCLElBQUksU0FBUyxLQUFLLEdBQUcsQ0FBQyxPQUFPLElBQUksQ0FBQztZQUMvRSxDQUFDLENBQUMsQ0FBQztRQUNMLENBQUM7UUFFRCxNQUFNLENBQUMsS0FBSyxDQUNWLG9EQUFvRCxZQUFZLEVBQUUsQ0FDbkUsQ0FBQztRQUNGLE9BQU8sWUFBWSxDQUFDO0lBQ3RCLENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLE1BQU0sQ0FBQyxLQUFLLENBQ1Ysb0ZBQW9GLEtBQUssQ0FBQyxPQUFPLEVBQUUsRUFDbkcsS0FBSyxDQUNOLENBQUM7UUFDRixPQUFPLCtFQUErRSxLQUFLLENBQUMsT0FBTywyQkFBMkIsQ0FBQztJQUNqSSxDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7XG4gIE1lZXRpbmdQcmVwTmx1RW50aXRpZXMsXG4gIEFnZ3JlZ2F0ZWRQcmVwUmVzdWx0cyxcbiAgUHJlcFJlc3VsdFNvdXJjZUVudHJ5LFxuICBHbWFpbE1lc3NhZ2VTbmlwcGV0LFxuICBTbGFja01lc3NhZ2VTbmlwcGV0LFxuICBOb3Rpb25QYWdlU3VtbWFyeSxcbiAgQ2FsZW5kYXJFdmVudFN1bW1hcnksXG59IGZyb20gJy4uL3R5cGVzJztcbmltcG9ydCB7IGZldGNoTWVldGluZ1ByZXBJbmZvIH0gZnJvbSAnLi4vc2tpbGxzL21lZXRpbmdQcmVwU2tpbGwnO1xuaW1wb3J0IHsgbG9nZ2VyIH0gZnJvbSAnLi4vLi4vX3V0aWxzL2xvZ2dlcic7XG5cbmZ1bmN0aW9uIGZvcm1hdFNvdXJjZVJlc3VsdHMoc291cmNlRW50cnk6IFByZXBSZXN1bHRTb3VyY2VFbnRyeSk6IHN0cmluZyB7XG4gIGlmIChzb3VyY2VFbnRyeS5lcnJvcl9tZXNzYWdlKSB7XG4gICAgcmV0dXJuIGAgIEVycm9yIGZldGNoaW5nIGZyb20gJHtzb3VyY2VFbnRyeS5zb3VyY2V9OiAke3NvdXJjZUVudHJ5LmVycm9yX21lc3NhZ2V9XFxuYDtcbiAgfVxuICBpZiAoc291cmNlRW50cnkuY291bnQgPT09IDApIHtcbiAgICByZXR1cm4gYCAgTm8gaW5mb3JtYXRpb24gZm91bmQgZnJvbSAke3NvdXJjZUVudHJ5LnNvdXJjZX0uXFxuYDtcbiAgfVxuXG4gIGxldCBkZXRhaWxzID0gJyc7XG4gIHN3aXRjaCAoc291cmNlRW50cnkuc291cmNlKSB7XG4gICAgY2FzZSAnZ21haWwnOlxuICAgICAgY29uc3QgZ21haWxSZXN1bHRzID0gc291cmNlRW50cnkucmVzdWx0cyBhcyBHbWFpbE1lc3NhZ2VTbmlwcGV0W107XG4gICAgICBkZXRhaWxzID0gZ21haWxSZXN1bHRzXG4gICAgICAgIC5tYXAoXG4gICAgICAgICAgKHIpID0+XG4gICAgICAgICAgICBgICAgIC0gU3ViamVjdDogJHtyLnN1YmplY3QgfHwgJ04vQSd9LCBGcm9tOiAke3IuZnJvbSB8fCAnTi9BJ30sIFNuaXBwZXQ6ICR7ci5zbmlwcGV0Py5zdWJzdHJpbmcoMCwgNTApfS4uLmBcbiAgICAgICAgKVxuICAgICAgICAuam9pbignXFxuJyk7XG4gICAgICBicmVhaztcbiAgICBjYXNlICdzbGFjayc6XG4gICAgICBjb25zdCBzbGFja1Jlc3VsdHMgPSBzb3VyY2VFbnRyeS5yZXN1bHRzIGFzIFNsYWNrTWVzc2FnZVNuaXBwZXRbXTtcbiAgICAgIGRldGFpbHMgPSBzbGFja1Jlc3VsdHNcbiAgICAgICAgLm1hcChcbiAgICAgICAgICAocikgPT5cbiAgICAgICAgICAgIGAgICAgLSBDaGFubmVsOiAke3IuY2hhbm5lbD8ubmFtZSB8fCByLmNoYW5uZWw/LmlkIHx8ICdOL0EnfSwgVXNlcjogJHtyLnVzZXI/Lm5hbWUgfHwgci51c2VyPy5pZCB8fCAnTi9BJ30sIFRleHQ6ICR7ci50ZXh0Py5zdWJzdHJpbmcoMCwgNTApfS4uLmBcbiAgICAgICAgKVxuICAgICAgICAuam9pbignXFxuJyk7XG4gICAgICBicmVhaztcbiAgICBjYXNlICdub3Rpb24nOlxuICAgICAgY29uc3Qgbm90aW9uUmVzdWx0cyA9IHNvdXJjZUVudHJ5LnJlc3VsdHMgYXMgTm90aW9uUGFnZVN1bW1hcnlbXTtcbiAgICAgIGRldGFpbHMgPSBub3Rpb25SZXN1bHRzXG4gICAgICAgIC5tYXAoKHIpID0+IGAgICAgLSBUaXRsZTogJHtyLnRpdGxlIHx8ICdOL0EnfSwgVVJMOiAke3IudXJsIHx8ICdOL0EnfWApXG4gICAgICAgIC5qb2luKCdcXG4nKTtcbiAgICAgIGJyZWFrO1xuICAgIGNhc2UgJ2NhbGVuZGFyX2V2ZW50cyc6XG4gICAgICBjb25zdCBjYWxlbmRhclJlc3VsdHMgPSBzb3VyY2VFbnRyeS5yZXN1bHRzIGFzIENhbGVuZGFyRXZlbnRTdW1tYXJ5W107XG4gICAgICBkZXRhaWxzID0gY2FsZW5kYXJSZXN1bHRzXG4gICAgICAgIC5tYXAoXG4gICAgICAgICAgKHIpID0+XG4gICAgICAgICAgICBgICAgIC0gU3VtbWFyeTogJHtyLnN1bW1hcnkgfHwgJ04vQSd9LCBTdGFydDogJHtyLnN0YXJ0ID8gbmV3IERhdGUoci5zdGFydCkudG9Mb2NhbGVTdHJpbmcoKSA6ICdOL0EnfWBcbiAgICAgICAgKVxuICAgICAgICAuam9pbignXFxuJyk7XG4gICAgICBicmVhaztcbiAgICBkZWZhdWx0OlxuICAgICAgZGV0YWlscyA9IGAgICAgUmF3IHJlc3VsdHM6ICR7SlNPTi5zdHJpbmdpZnkoc291cmNlRW50cnkucmVzdWx0cy5zbGljZSgwLCAyKSl9Li4uYDtcbiAgfVxuICByZXR1cm4gYCAgRnJvbSAke3NvdXJjZUVudHJ5LnNvdXJjZX0gKCR7c291cmNlRW50cnkuY291bnR9IGl0ZW0ocykpOlxcbiR7ZGV0YWlsc31cXG5gO1xufVxuXG4vKipcbiAqIEhhbmRsZXMgdGhlIFwiUmVxdWVzdE1lZXRpbmdQcmVwYXJhdGlvblwiIGludGVudC5cbiAqIENhbGxzIHRoZSBtZWV0aW5nIHByZXBhcmF0aW9uIHNraWxsIGFuZCBmb3JtYXRzIHRoZSByZXN1bHRzIGZvciB0aGUgdXNlci5cbiAqXG4gKiBAcGFyYW0gdXNlcklkIFRoZSBJRCBvZiB0aGUgdXNlci5cbiAqIEBwYXJhbSBlbnRpdGllcyBUaGUgTkxVIGVudGl0aWVzIGV4dHJhY3RlZCBmb3IgdGhlIFJlcXVlc3RNZWV0aW5nUHJlcGFyYXRpb24gaW50ZW50LlxuICogQHJldHVybnMgQSBwcm9taXNlIHRoYXQgcmVzb2x2ZXMgdG8gYSB1c2VyLWZhY2luZyBzdHJpbmcgcmVzcG9uc2UuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBoYW5kbGVNZWV0aW5nUHJlcGFyYXRpb25SZXF1ZXN0KFxuICB1c2VySWQ6IHN0cmluZyxcbiAgZW50aXRpZXM6IE1lZXRpbmdQcmVwTmx1RW50aXRpZXNcbik6IFByb21pc2U8c3RyaW5nPiB7XG4gIGxvZ2dlci5pbmZvKFxuICAgIGBbTWVldGluZ1ByZXBDb21tYW5kSGFuZGxlcl0gSGFuZGxpbmcgbWVldGluZyBwcmVwYXJhdGlvbiByZXF1ZXN0IGZvciB1c2VyICR7dXNlcklkfSwgbWVldGluZyByZWZlcmVuY2U6IFwiJHtlbnRpdGllcy5tZWV0aW5nX3JlZmVyZW5jZX1cImBcbiAgKTtcbiAgbG9nZ2VyLmRlYnVnKFxuICAgIGBbTWVldGluZ1ByZXBDb21tYW5kSGFuZGxlcl0gUmVjZWl2ZWQgTkxVIGVudGl0aWVzOiAke0pTT04uc3RyaW5naWZ5KGVudGl0aWVzKX1gXG4gICk7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCBwcmVwUmVzdWx0czogQWdncmVnYXRlZFByZXBSZXN1bHRzID0gYXdhaXQgZmV0Y2hNZWV0aW5nUHJlcEluZm8oXG4gICAgICB1c2VySWQsXG4gICAgICBlbnRpdGllc1xuICAgICk7XG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICBgW01lZXRpbmdQcmVwQ29tbWFuZEhhbmRsZXJdIE1lZXRpbmcgcHJlcGFyYXRpb24gc2tpbGwgZmluaXNoZWQuIFNvdXJjZXMgcHJvY2Vzc2VkOiAke3ByZXBSZXN1bHRzLnJlc3VsdHNfYnlfc291cmNlLmxlbmd0aH1gXG4gICAgKTtcblxuICAgIGxldCByZXNwb25zZVRleHQgPSBgT2theSwgSSd2ZSBnYXRoZXJlZCBzb21lIGluZm9ybWF0aW9uIGZvciB5b3VyIG1lZXRpbmc6IFwiJHtwcmVwUmVzdWx0cy5tZWV0aW5nX3JlZmVyZW5jZV9pZGVudGlmaWVkfVwiOlxcblxcbmA7XG5cbiAgICBpZiAocHJlcFJlc3VsdHMuaWRlbnRpZmllZF9jYWxlbmRhcl9ldmVudCkge1xuICAgICAgcmVzcG9uc2VUZXh0ICs9IGBJJ3ZlIGlkZW50aWZpZWQgdGhpcyBhcyB0aGUgZXZlbnQ6IFwiJHtwcmVwUmVzdWx0cy5pZGVudGlmaWVkX2NhbGVuZGFyX2V2ZW50LnN1bW1hcnl9XCIgc3RhcnRpbmcgYXQgJHtwcmVwUmVzdWx0cy5pZGVudGlmaWVkX2NhbGVuZGFyX2V2ZW50LnN0YXJ0ID8gbmV3IERhdGUocHJlcFJlc3VsdHMuaWRlbnRpZmllZF9jYWxlbmRhcl9ldmVudC5zdGFydCkudG9Mb2NhbGVTdHJpbmcoKSA6ICdVbmtub3duIHRpbWUnfS5cXG5cXG5gO1xuICAgIH0gZWxzZSB7XG4gICAgICByZXNwb25zZVRleHQgKz0gYEkgY291bGRuJ3QgZGVmaW5pdGl2ZWx5IGxpbmsgdGhpcyB0byBhIHNwZWNpZmljIGNhbGVuZGFyIGV2ZW50IGJhc2VkIG9uIHRoZSByZWZlcmVuY2UgcHJvdmlkZWQuXFxuXFxuYDtcbiAgICB9XG5cbiAgICBpZiAocHJlcFJlc3VsdHMucmVzdWx0c19ieV9zb3VyY2UubGVuZ3RoID4gMCkge1xuICAgICAgcHJlcFJlc3VsdHMucmVzdWx0c19ieV9zb3VyY2UuZm9yRWFjaCgoc291cmNlRW50cnkpID0+IHtcbiAgICAgICAgcmVzcG9uc2VUZXh0ICs9IGZvcm1hdFNvdXJjZVJlc3VsdHMoc291cmNlRW50cnkpO1xuICAgICAgfSk7XG4gICAgfSBlbHNlIHtcbiAgICAgIHJlc3BvbnNlVGV4dCArPVxuICAgICAgICBcIkkgZGlkbid0IGZpbmQgYW55IHNwZWNpZmljIGl0ZW1zIGZyb20gdGhlIHJlcXVlc3RlZCBzb3VyY2VzLlxcblwiO1xuICAgIH1cblxuICAgIGlmIChwcmVwUmVzdWx0cy5vdmVyYWxsX3N1bW1hcnlfbm90ZXMpIHtcbiAgICAgIHJlc3BvbnNlVGV4dCArPSBgXFxuU3VtbWFyeSBvZiBGaW5kaW5nczpcXG4ke3ByZXBSZXN1bHRzLm92ZXJhbGxfc3VtbWFyeV9ub3Rlc31cXG5gO1xuICAgIH1cblxuICAgIGlmIChcbiAgICAgIHByZXBSZXN1bHRzLmVycm9yc19lbmNvdW50ZXJlZCAmJlxuICAgICAgcHJlcFJlc3VsdHMuZXJyb3JzX2VuY291bnRlcmVkLmxlbmd0aCA+IDBcbiAgICApIHtcbiAgICAgIHJlc3BvbnNlVGV4dCArPSAnXFxuU29tZSBpc3N1ZXMgd2VyZSBlbmNvdW50ZXJlZCBkdXJpbmcgcHJlcGFyYXRpb246XFxuJztcbiAgICAgIHByZXBSZXN1bHRzLmVycm9yc19lbmNvdW50ZXJlZC5mb3JFYWNoKChlcnIpID0+IHtcbiAgICAgICAgcmVzcG9uc2VUZXh0ICs9IGAgIC0gJHtlcnIuc291cmNlX2F0dGVtcHRlZCB8fCAnT3ZlcmFsbCd9OiAke2Vyci5tZXNzYWdlfVxcbmA7XG4gICAgICB9KTtcbiAgICB9XG5cbiAgICBsb2dnZXIuZGVidWcoXG4gICAgICBgW01lZXRpbmdQcmVwQ29tbWFuZEhhbmRsZXJdIEZpbmFsIHJlc3BvbnNlIHRleHQ6ICR7cmVzcG9uc2VUZXh0fWBcbiAgICApO1xuICAgIHJldHVybiByZXNwb25zZVRleHQ7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgW01lZXRpbmdQcmVwQ29tbWFuZEhhbmRsZXJdIENyaXRpY2FsIGVycm9yIGhhbmRsaW5nIG1lZXRpbmcgcHJlcGFyYXRpb24gcmVxdWVzdDogJHtlcnJvci5tZXNzYWdlfWAsXG4gICAgICBlcnJvclxuICAgICk7XG4gICAgcmV0dXJuIGBJIGVuY291bnRlcmVkIGFuIHVuZXhwZWN0ZWQgZXJyb3Igd2hpbGUgdHJ5aW5nIHRvIHByZXBhcmUgZm9yIHlvdXIgbWVldGluZzogJHtlcnJvci5tZXNzYWdlfS4gUGxlYXNlIHRyeSBhZ2FpbiBsYXRlci5gO1xuICB9XG59XG4iXX0=