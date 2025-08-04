import { logger } from '../../_utils/logger';
// Placeholder for importing other skills that might be needed:
// import * as notionSkills from './notionAndResearchSkills';
// import * as emailSkills from './emailSkills';
// import * as llmUtilities from './llmUtilities'; // For summarizing text or extracting insights
/**
 * Orchestrates the processing of meeting outcomes based on NLU entities.
 * This includes fetching meeting content, extracting insights, and performing requested actions.
 *
 * @param userId The ID of the user requesting the actions.
 * @param nluEntities The parsed NLU entities from the ProcessMeetingOutcomes intent.
 * @returns A promise that resolves to ProcessMeetingOutcomesSkillResponse containing results of actions.
 */
export async function executePostMeetingActions(userId, nluEntities) {
    logger.info(`[postMeetingWorkflowSkill] Starting post-meeting actions for user ${userId}, meeting reference: "${nluEntities.meeting_reference}"`);
    logger.debug(`[postMeetingWorkflowSkill] NLU Entities: ${JSON.stringify(nluEntities)}`);
    const results = {
        processed_meeting_reference: nluEntities.meeting_reference,
        errors_encountered: [],
    };
    // Step 1: Retrieve and process the source document (transcript, notes) to get insights.
    // This is a critical step and would likely involve an LLM call.
    let insights = null;
    try {
        logger.info(`[postMeetingWorkflowSkill] Placeholder: Fetching and processing source document for meeting: "${nluEntities.meeting_reference}", type: ${nluEntities.outcome_source_type || 'transcript'}, ID: ${nluEntities.source_document_id || 'N/A'}`);
        // const meetingContent = await fetchMeetingContent(userId, nluEntities.meeting_reference, nluEntities.source_document_id, nluEntities.outcome_source_type);
        // insights = await llmUtilities.extractInsightsFromMeetingContent(meetingContent);
        // Placeholder insights
        insights = {
            meeting_title_or_reference: nluEntities.meeting_reference,
            key_decisions: [
                'Placeholder: Decision 1 was made.',
                'Placeholder: Decision 2 was agreed upon.',
            ],
            action_items: [
                {
                    description: 'Placeholder: Action Item 1 for @Alice',
                    suggested_assignee: 'Alice',
                },
                {
                    description: 'Placeholder: Action Item 2 for @Bob by next Friday',
                    suggested_assignee: 'Bob',
                    suggested_due_date: 'next Friday',
                },
            ],
            overall_summary: 'Placeholder: This was a productive meeting discussing key project milestones.',
        };
        logger.warn(`[postMeetingWorkflowSkill] Meeting content fetching and insight extraction is using placeholder data.`);
        if (!insights)
            throw new Error('Failed to extract insights (placeholder).');
    }
    catch (error) {
        logger.error(`[postMeetingWorkflowSkill] Error fetching/processing meeting source: ${error.message}`, error);
        results.errors_encountered?.push({
            action_attempted: 'SOURCE_PROCESSING',
            message: `Failed to process meeting source: ${error.message}`,
            details: error.stack,
        });
        // If we can't get insights, we probably can't do much else.
        return {
            ok: false,
            error: {
                code: 'SOURCE_ERROR',
                message: 'Failed to process meeting source.',
            },
            data: results,
        };
    }
    // Step 2: Perform requested actions based on extracted insights.
    for (const action of nluEntities.requested_actions) {
        try {
            switch (action) {
                case 'SUMMARIZE_KEY_DECISIONS':
                    logger.info(`[postMeetingWorkflowSkill] Action: SUMMARIZE_KEY_DECISIONS`);
                    results.summary_of_decisions =
                        insights.key_decisions?.join('\n- ') ||
                            'No specific decisions extracted.';
                    if (insights.key_decisions && insights.key_decisions.length > 0) {
                        results.summary_of_decisions = '- ' + results.summary_of_decisions;
                    }
                    logger.warn(`[postMeetingWorkflowSkill] SUMMARIZE_KEY_DECISIONS is using placeholder data from insights.`);
                    break;
                case 'EXTRACT_ACTION_ITEMS':
                    logger.info(`[postMeetingWorkflowSkill] Action: EXTRACT_ACTION_ITEMS`);
                    if (insights.action_items && insights.action_items.length > 0) {
                        results.extracted_action_items_summary =
                            'Extracted Action Items:\n' +
                                insights.action_items
                                    .map((ai) => `- ${ai.description} (Assignee: ${ai.suggested_assignee || 'N/A'}, Due: ${ai.suggested_due_date || 'N/A'})`)
                                    .join('\n');
                    }
                    else {
                        results.extracted_action_items_summary =
                            'No specific action items were extracted.';
                    }
                    logger.warn(`[postMeetingWorkflowSkill] EXTRACT_ACTION_ITEMS is using placeholder data from insights.`);
                    break;
                case 'DRAFT_FOLLOW_UP_EMAIL':
                    logger.info(`[postMeetingWorkflowSkill] Action: DRAFT_FOLLOW_UP_EMAIL`);
                    // TODO: Implement actual email drafting logic, possibly calling another LLM utility or emailSkills.
                    // This would use insights.key_decisions, insights.action_items, nluEntities.email_draft_details.
                    results.drafted_email_content = {
                        subject: `Follow-up: ${insights.meeting_title_or_reference}`,
                        body: `Hi team,\n\nHere's a summary of our meeting "${insights.meeting_title_or_reference}":\n\nKey Decisions:\n- ${insights.key_decisions?.join('\n- ') || 'N/A'}\n\nAction Items:\n${insights.action_items?.map((ai) => `- ${ai.description} (Assignee: ${ai.suggested_assignee || 'N/A'})`).join('\n') || 'N/A'}\n\n${nluEntities.email_draft_details?.additional_instructions || ''}\n\nBest regards,\nAtom Agent`,
                        to: typeof nluEntities.email_draft_details?.recipients === 'string'
                            ? [nluEntities.email_draft_details.recipients]
                            : nluEntities.email_draft_details?.recipients || ['attendees'],
                    };
                    logger.warn(`[postMeetingWorkflowSkill] DRAFT_FOLLOW_UP_EMAIL is using placeholder data.`);
                    break;
                case 'CREATE_TASKS_IN_NOTION':
                    logger.info(`[postMeetingWorkflowSkill] Action: CREATE_TASKS_IN_NOTION`);
                    results.created_notion_tasks = [];
                    if (insights.action_items && insights.action_items.length > 0) {
                        for (const ai of insights.action_items) {
                            // TODO: Call actual notionSkills.createTask
                            // const notionTaskParams: CreateNotionTaskParams = {
                            //   description: ai.description,
                            //   dueDate: ai.suggested_due_date, // May need date parsing
                            //   assignee: ai.suggested_assignee, // May need resolution to Notion user
                            //   notionTasksDbId: nluEntities.task_creation_details?.notion_database_id || process.env.ATOM_NOTION_TASKS_DATABASE_ID,
                            // };
                            // const taskResult = await notionSkills.createNotionTask(userId, notionTaskParams);
                            // if (taskResult.ok && taskResult.data) {
                            //   results.created_notion_tasks.push({ taskId: taskResult.data.taskId, taskUrl: taskResult.data.taskUrl, description: ai.description });
                            // } else { ... handle error ... }
                            results.created_notion_tasks.push({
                                taskId: `sim_task_${Date.now()}_${results.created_notion_tasks.length}`,
                                taskUrl: `https://notion.so/sim_task_${Date.now()}`,
                                description: ai.description,
                                assignee: ai.suggested_assignee,
                                dueDate: ai.suggested_due_date,
                            });
                        }
                    }
                    logger.warn(`[postMeetingWorkflowSkill] CREATE_TASKS_IN_NOTION is using placeholder data.`);
                    break;
                default:
                    logger.warn(`[postMeetingWorkflowSkill] Unknown requested action: ${action}`);
                    results.errors_encountered?.push({
                        action_attempted: action,
                        message: `Unknown requested action: ${action}`,
                    });
            }
        }
        catch (actionError) {
            logger.error(`[postMeetingWorkflowSkill] Error performing action ${action}: ${actionError.message}`, actionError);
            results.errors_encountered?.push({
                action_attempted: action,
                message: `Error during action ${action}: ${actionError.message}`,
                details: actionError.stack,
            });
        }
    }
    logger.info(`[postMeetingWorkflowSkill] Finished post-meeting actions for user ${userId}.`);
    return { ok: true, data: results };
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicG9zdE1lZXRpbmdXb3JrZmxvd1NraWxsLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsicG9zdE1lZXRpbmdXb3JrZmxvd1NraWxsLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQVNBLE9BQU8sRUFBRSxNQUFNLEVBQUUsTUFBTSxxQkFBcUIsQ0FBQztBQUM3QywrREFBK0Q7QUFDL0QsNkRBQTZEO0FBQzdELGdEQUFnRDtBQUNoRCxpR0FBaUc7QUFFakc7Ozs7Ozs7R0FPRztBQUNILE1BQU0sQ0FBQyxLQUFLLFVBQVUseUJBQXlCLENBQzdDLE1BQWMsRUFDZCxXQUE4QztJQUU5QyxNQUFNLENBQUMsSUFBSSxDQUNULHFFQUFxRSxNQUFNLHlCQUF5QixXQUFXLENBQUMsaUJBQWlCLEdBQUcsQ0FDckksQ0FBQztJQUNGLE1BQU0sQ0FBQyxLQUFLLENBQ1YsNENBQTRDLElBQUksQ0FBQyxTQUFTLENBQUMsV0FBVyxDQUFDLEVBQUUsQ0FDMUUsQ0FBQztJQUVGLE1BQU0sT0FBTyxHQUE4QjtRQUN6QywyQkFBMkIsRUFBRSxXQUFXLENBQUMsaUJBQWlCO1FBQzFELGtCQUFrQixFQUFFLEVBQUU7S0FDdkIsQ0FBQztJQUVGLHdGQUF3RjtJQUN4RixnRUFBZ0U7SUFDaEUsSUFBSSxRQUFRLEdBQW9DLElBQUksQ0FBQztJQUNyRCxJQUFJLENBQUM7UUFDSCxNQUFNLENBQUMsSUFBSSxDQUNULGlHQUFpRyxXQUFXLENBQUMsaUJBQWlCLFlBQVksV0FBVyxDQUFDLG1CQUFtQixJQUFJLFlBQVksU0FBUyxXQUFXLENBQUMsa0JBQWtCLElBQUksS0FBSyxFQUFFLENBQzVPLENBQUM7UUFDRiw0SkFBNEo7UUFDNUosbUZBQW1GO1FBRW5GLHVCQUF1QjtRQUN2QixRQUFRLEdBQUc7WUFDVCwwQkFBMEIsRUFBRSxXQUFXLENBQUMsaUJBQWlCO1lBQ3pELGFBQWEsRUFBRTtnQkFDYixtQ0FBbUM7Z0JBQ25DLDBDQUEwQzthQUMzQztZQUNELFlBQVksRUFBRTtnQkFD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QUVELE1BQU0sQ0FBQyxJQUFJLENBQ1QscUVBQXFFLE1BQU0sR0FBRyxDQUMvRSxDQUFDO0lBQ0YsT0FBTyxFQUFFLEVBQUUsRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLE9BQU8sRUFBRSxDQUFDO0FBQ3JDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQge1xuICBQcm9jZXNzTWVldGluZ091dGNvbWVzTmx1RW50aXRpZXMsXG4gIEV4dHJhY3RlZE1lZXRpbmdJbnNpZ2h0cyxcbiAgUG9zdE1lZXRpbmdBY3Rpb25zUmVzdWx0cyxcbiAgUHJvY2Vzc01lZXRpbmdPdXRjb21lc1NraWxsUmVzcG9uc2UsXG4gIFNraWxsUmVzcG9uc2UsIC8vIEdlbmVyaWMgU2tpbGxSZXNwb25zZVxuICAvLyBQb3RlbnRpYWxseSBpbXBvcnQgdHlwZXMgZm9yIE5vdGlvbiB0YXNrcywgRW1haWwgZHJhZnRpbmcgaWYgdGhvc2Ugc2tpbGxzIGFyZSBjYWxsZWRcbiAgLy8gZS5nLiwgQ3JlYXRlTm90aW9uVGFza1BhcmFtcywgRW1haWxEZXRhaWxzXG59IGZyb20gJy4uL3R5cGVzJztcbmltcG9ydCB7IGxvZ2dlciB9IGZyb20gJy4uLy4uL191dGlscy9sb2dnZXInO1xuLy8gUGxhY2Vob2xkZXIgZm9yIGltcG9ydGluZyBvdGhlciBza2lsbHMgdGhhdCBtaWdodCBiZSBuZWVkZWQ6XG4vLyBpbXBvcnQgKiBhcyBub3Rpb25Ta2lsbHMgZnJvbSAnLi9ub3Rpb25BbmRSZXNlYXJjaFNraWxscyc7XG4vLyBpbXBvcnQgKiBhcyBlbWFpbFNraWxscyBmcm9tICcuL2VtYWlsU2tpbGxzJztcbi8vIGltcG9ydCAqIGFzIGxsbVV0aWxpdGllcyBmcm9tICcuL2xsbVV0aWxpdGllcyc7IC8vIEZvciBzdW1tYXJpemluZyB0ZXh0IG9yIGV4dHJhY3RpbmcgaW5zaWdodHNcblxuLyoqXG4gKiBPcmNoZXN0cmF0ZXMgdGhlIHByb2Nlc3Npbmcgb2YgbWVldGluZyBvdXRjb21lcyBiYXNlZCBvbiBOTFUgZW50aXRpZXMuXG4gKiBUaGlzIGluY2x1ZGVzIGZldGNoaW5nIG1lZXRpbmcgY29udGVudCwgZXh0cmFjdGluZyBpbnNpZ2h0cywgYW5kIHBlcmZvcm1pbmcgcmVxdWVzdGVkIGFjdGlvbnMuXG4gKlxuICogQHBhcmFtIHVzZXJJZCBUaGUgSUQgb2YgdGhlIHVzZXIgcmVxdWVzdGluZyB0aGUgYWN0aW9ucy5cbiAqIEBwYXJhbSBubHVFbnRpdGllcyBUaGUgcGFyc2VkIE5MVSBlbnRpdGllcyBmcm9tIHRoZSBQcm9jZXNzTWVldGluZ091dGNvbWVzIGludGVudC5cbiAqIEByZXR1cm5zIEEgcHJvbWlzZSB0aGF0IHJlc29sdmVzIHRvIFByb2Nlc3NNZWV0aW5nT3V0Y29tZXNTa2lsbFJlc3BvbnNlIGNvbnRhaW5pbmcgcmVzdWx0cyBvZiBhY3Rpb25zLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZXhlY3V0ZVBvc3RNZWV0aW5nQWN0aW9ucyhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIG5sdUVudGl0aWVzOiBQcm9jZXNzTWVldGluZ091dGNvbWVzTmx1RW50aXRpZXNcbik6IFByb21pc2U8UHJvY2Vzc01lZXRpbmdPdXRjb21lc1NraWxsUmVzcG9uc2U+IHtcbiAgbG9nZ2VyLmluZm8oXG4gICAgYFtwb3N0TWVldGluZ1dvcmtmbG93U2tpbGxdIFN0YXJ0aW5nIHBvc3QtbWVldGluZyBhY3Rpb25zIGZvciB1c2VyICR7dXNlcklkfSwgbWVldGluZyByZWZlcmVuY2U6IFwiJHtubHVFbnRpdGllcy5tZWV0aW5nX3JlZmVyZW5jZX1cImBcbiAgKTtcbiAgbG9nZ2VyLmRlYnVnKFxuICAgIGBbcG9zdE1lZXRpbmdXb3JrZmxvd1NraWxsXSBOTFUgRW50aXRpZXM6ICR7SlNPTi5zdHJpbmdpZnkobmx1RW50aXRpZXMpfWBcbiAgKTtcblxuICBjb25zdCByZXN1bHRzOiBQb3N0TWVldGluZ0FjdGlvbnNSZXN1bHRzID0ge1xuICAgIHByb2Nlc3NlZF9tZWV0aW5nX3JlZmVyZW5jZTogbmx1RW50aXRpZXMubWVldGluZ19yZWZlcmVuY2UsXG4gICAgZXJyb3JzX2VuY291bnRlcmVkOiBbXSxcbiAgfTtcblxuICAvLyBTdGVwIDE6IFJldHJpZXZlIGFuZCBwcm9jZXNzIHRoZSBzb3VyY2UgZG9jdW1lbnQgKHRyYW5zY3JpcHQsIG5vdGVzKSB0byBnZXQgaW5zaWdodHMuXG4gIC8vIFRoaXMgaXMgYSBjcml0aWNhbCBzdGVwIGFuZCB3b3VsZCBsaWtlbHkgaW52b2x2ZSBhbiBMTE0gY2FsbC5cbiAgbGV0IGluc2lnaHRzOiBFeHRyYWN0ZWRNZWV0aW5nSW5zaWdodHMgfCBudWxsID0gbnVsbDtcbiAgdHJ5IHtcbiAgICBsb2dnZXIuaW5mbyhcbiAgICAgIGBbcG9zdE1lZXRpbmdXb3JrZmxvd1NraWxsXSBQbGFjZWhvbGRlcjogRmV0Y2hpbmcgYW5kIHByb2Nlc3Npbmcgc291cmNlIGRvY3VtZW50IGZvciBtZWV0aW5nOiBcIiR7bmx1RW50aXRpZXMubWVldGluZ19yZWZlcmVuY2V9XCIsIHR5cGU6ICR7bmx1RW50aXRpZXMub3V0Y29tZV9zb3VyY2VfdHlwZSB8fCAndHJhbnNjcmlwdCd9LCBJRDogJHtubHVFbnRpdGllcy5zb3VyY2VfZG9jdW1lbnRfaWQgfHwgJ04vQSd9YFxuICAgICk7XG4gICAgLy8gY29uc3QgbWVldGluZ0NvbnRlbnQgPSBhd2FpdCBmZXRjaE1lZXRpbmdDb250ZW50KHVzZXJJZCwgbmx1RW50aXRpZXMubWVldGluZ19yZWZlcmVuY2UsIG5sdUVudGl0aWVzLnNvdXJjZV9kb2N1bWVudF9pZCwgbmx1RW50aXRpZXMub3V0Y29tZV9zb3VyY2VfdHlwZSk7XG4gICAgLy8gaW5zaWdodHMgPSBhd2FpdCBsbG1VdGlsaXRpZXMuZXh0cmFjdEluc2lnaHRzRnJvbU1lZXRpbmdDb250ZW50KG1lZXRpbmdDb250ZW50KTtcblxuICAgIC8vIFBsYWNlaG9sZGVyIGluc2lnaHRzXG4gICAgaW5zaWdodHMgPSB7XG4gICAgICBtZWV0aW5nX3RpdGxlX29yX3JlZmVyZW5jZTogbmx1RW50aXRpZXMubWVldGluZ19yZWZlcmVuY2UsXG4gICAgICBrZXlfZGVjaXNpb25zOiBbXG4gICAgICAgICdQbGFjZWhvbGRlcjogRGVjaXNpb24gMSB3YXMgbWFkZS4nLFxuICAgICAgICAnUGxhY2Vob2xkZXI6IERlY2lzaW9uIDIgd2FzIGFncmVlZCB1cG9uLicsXG4gICAgICBdLFxuICAgICAgYWN0aW9uX2l0ZW1zOiBbXG4gICAgICAgIHtcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ1BsYWNlaG9sZGVyOiBBY3Rpb24gSXRlbSAxIGZvciBAQWxpY2UnLFxuICAgICAgICAgIHN1Z2dlc3RlZF9hc3NpZ25lZTogJ0FsaWNlJyxcbiAgICAgICAgfSxcbiAgICAgICAge1xuICAgICAgICAgIGRlc2NyaXB0aW9uOiAnUGxhY2Vob2xkZXI6IEFjdGlvbiBJdGVtIDIgZm9yIEBCb2IgYnkgbmV4dCBGcmlkYXknLFxuICAgICAgICAgIHN1Z2dlc3RlZF9hc3NpZ25lZTogJ0JvYicsXG4gICAgICAgICAgc3VnZ2VzdGVkX2R1ZV9kYXRlOiAnbmV4dCBGcmlkYXknLFxuICAgICAgICB9LFxuICAgICAgXSxcbiAgICAgIG92ZXJhbGxfc3VtbWFyeTpcbiAgICAgICAgJ1BsYWNlaG9sZGVyOiBUaGlzIHdhcyBhIHByb2R1Y3RpdmUgbWVldGluZyBkaXNjdXNzaW5nIGtleSBwcm9qZWN0IG1pbGVzdG9uZXMuJyxcbiAgICB9O1xuICAgIGxvZ2dlci53YXJuKFxuICAgICAgYFtwb3N0TWVldGluZ1dvcmtmbG93U2tpbGxdIE1lZXRpbmcgY29udGVudCBmZXRjaGluZyBhbmQgaW5zaWdodCBleHRyYWN0aW9uIGlzIHVzaW5nIHBsYWNlaG9sZGVyIGRhdGEuYFxuICAgICk7XG4gICAgaWYgKCFpbnNpZ2h0cykgdGhyb3cgbmV3IEVycm9yKCdGYWlsZWQgdG8gZXh0cmFjdCBpbnNpZ2h0cyAocGxhY2Vob2xkZXIpLicpO1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFtwb3N0TWVldGluZ1dvcmtmbG93U2tpbGxdIEVycm9yIGZldGNoaW5nL3Byb2Nlc3NpbmcgbWVldGluZyBzb3VyY2U6ICR7ZXJyb3IubWVzc2FnZX1gLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIHJlc3VsdHMuZXJyb3JzX2VuY291bnRlcmVkPy5wdXNoKHtcbiAgICAgIGFjdGlvbl9hdHRlbXB0ZWQ6ICdTT1VSQ0VfUFJPQ0VTU0lORycsXG4gICAgICBtZXNzYWdlOiBgRmFpbGVkIHRvIHByb2Nlc3MgbWVldGluZyBzb3VyY2U6ICR7ZXJyb3IubWVzc2FnZX1gLFxuICAgICAgZGV0YWlsczogZXJyb3Iuc3RhY2ssXG4gICAgfSk7XG4gICAgLy8gSWYgd2UgY2FuJ3QgZ2V0IGluc2lnaHRzLCB3ZSBwcm9iYWJseSBjYW4ndCBkbyBtdWNoIGVsc2UuXG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdTT1VSQ0VfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnRmFpbGVkIHRvIHByb2Nlc3MgbWVldGluZyBzb3VyY2UuJyxcbiAgICAgIH0sXG4gICAgICBkYXRhOiByZXN1bHRzLFxuICAgIH07XG4gIH1cblxuICAvLyBTdGVwIDI6IFBlcmZvcm0gcmVxdWVzdGVkIGFjdGlvbnMgYmFzZWQgb24gZXh0cmFjdGVkIGluc2lnaHRzLlxuICBmb3IgKGNvbnN0IGFjdGlvbiBvZiBubHVFbnRpdGllcy5yZXF1ZXN0ZWRfYWN0aW9ucykge1xuICAgIHRyeSB7XG4gICAgICBzd2l0Y2ggKGFjdGlvbikge1xuICAgICAgICBjYXNlICdTVU1NQVJJWkVfS0VZX0RFQ0lTSU9OUyc6XG4gICAgICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgICAgICBgW3Bvc3RNZWV0aW5nV29ya2Zsb3dTa2lsbF0gQWN0aW9uOiBTVU1NQVJJWkVfS0VZX0RFQ0lTSU9OU2BcbiAgICAgICAgICApO1xuICAgICAgICAgIHJlc3VsdHMuc3VtbWFyeV9vZl9kZWNpc2lvbnMgPVxuICAgICAgICAgICAgaW5zaWdodHMua2V5X2RlY2lzaW9ucz8uam9pbignXFxuLSAnKSB8fFxuICAgICAgICAgICAgJ05vIHNwZWNpZmljIGRlY2lzaW9ucyBleHRyYWN0ZWQuJztcbiAgICAgICAgICBpZiAoaW5zaWdodHMua2V5X2RlY2lzaW9ucyAmJiBpbnNpZ2h0cy5rZXlfZGVjaXNpb25zLmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgIHJlc3VsdHMuc3VtbWFyeV9vZl9kZWNpc2lvbnMgPSAnLSAnICsgcmVzdWx0cy5zdW1tYXJ5X29mX2RlY2lzaW9ucztcbiAgICAgICAgICB9XG4gICAgICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgICAgICBgW3Bvc3RNZWV0aW5nV29ya2Zsb3dTa2lsbF0gU1VNTUFSSVpFX0tFWV9ERUNJU0lPTlMgaXMgdXNpbmcgcGxhY2Vob2xkZXIgZGF0YSBmcm9tIGluc2lnaHRzLmBcbiAgICAgICAgICApO1xuICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgJ0VYVFJBQ1RfQUNUSU9OX0lURU1TJzpcbiAgICAgICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgICAgIGBbcG9zdE1lZXRpbmdXb3JrZmxvd1NraWxsXSBBY3Rpb246IEVYVFJBQ1RfQUNUSU9OX0lURU1TYFxuICAgICAgICAgICk7XG4gICAgICAgICAgaWYgKGluc2lnaHRzLmFjdGlvbl9pdGVtcyAmJiBpbnNpZ2h0cy5hY3Rpb25faXRlbXMubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgcmVzdWx0cy5leHRyYWN0ZWRfYWN0aW9uX2l0ZW1zX3N1bW1hcnkgPVxuICAgICAgICAgICAgICAnRXh0cmFjdGVkIEFjdGlvbiBJdGVtczpcXG4nICtcbiAgICAgICAgICAgICAgaW5zaWdodHMuYWN0aW9uX2l0ZW1zXG4gICAgICAgICAgICAgICAgLm1hcChcbiAgICAgICAgICAgICAgICAgIChhaSkgPT5cbiAgICAgICAgICAgICAgICAgICAgYC0gJHthaS5kZXNjcmlwdGlvbn0gKEFzc2lnbmVlOiAke2FpLnN1Z2dlc3RlZF9hc3NpZ25lZSB8fCAnTi9BJ30sIER1ZTogJHthaS5zdWdnZXN0ZWRfZHVlX2RhdGUgfHwgJ04vQSd9KWBcbiAgICAgICAgICAgICAgICApXG4gICAgICAgICAgICAgICAgLmpvaW4oJ1xcbicpO1xuICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICByZXN1bHRzLmV4dHJhY3RlZF9hY3Rpb25faXRlbXNfc3VtbWFyeSA9XG4gICAgICAgICAgICAgICdObyBzcGVjaWZpYyBhY3Rpb24gaXRlbXMgd2VyZSBleHRyYWN0ZWQuJztcbiAgICAgICAgICB9XG4gICAgICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgICAgICBgW3Bvc3RNZWV0aW5nV29ya2Zsb3dTa2lsbF0gRVhUUkFDVF9BQ1RJT05fSVRFTVMgaXMgdXNpbmcgcGxhY2Vob2xkZXIgZGF0YSBmcm9tIGluc2lnaHRzLmBcbiAgICAgICAgICApO1xuICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgJ0RSQUZUX0ZPTExPV19VUF9FTUFJTCc6XG4gICAgICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgICAgICBgW3Bvc3RNZWV0aW5nV29ya2Zsb3dTa2lsbF0gQWN0aW9uOiBEUkFGVF9GT0xMT1dfVVBfRU1BSUxgXG4gICAgICAgICAgKTtcbiAgICAgICAgICAvLyBUT0RPOiBJbXBsZW1lbnQgYWN0dWFsIGVtYWlsIGRyYWZ0aW5nIGxvZ2ljLCBwb3NzaWJseSBjYWxsaW5nIGFub3RoZXIgTExNIHV0aWxpdHkgb3IgZW1haWxTa2lsbHMuXG4gICAgICAgICAgLy8gVGhpcyB3b3VsZCB1c2UgaW5zaWdodHMua2V5X2RlY2lzaW9ucywgaW5zaWdodHMuYWN0aW9uX2l0ZW1zLCBubHVFbnRpdGllcy5lbWFpbF9kcmFmdF9kZXRhaWxzLlxuICAgICAgICAgIHJlc3VsdHMuZHJhZnRlZF9lbWFpbF9jb250ZW50ID0ge1xuICAgICAgICAgICAgc3ViamVjdDogYEZvbGxvdy11cDogJHtpbnNpZ2h0cy5tZWV0aW5nX3RpdGxlX29yX3JlZmVyZW5jZX1gLFxuICAgICAgICAgICAgYm9keTogYEhpIHRlYW0sXFxuXFxuSGVyZSdzIGEgc3VtbWFyeSBvZiBvdXIgbWVldGluZyBcIiR7aW5zaWdodHMubWVldGluZ190aXRsZV9vcl9yZWZlcmVuY2V9XCI6XFxuXFxuS2V5IERlY2lzaW9uczpcXG4tICR7aW5zaWdodHMua2V5X2RlY2lzaW9ucz8uam9pbignXFxuLSAnKSB8fCAnTi9BJ31cXG5cXG5BY3Rpb24gSXRlbXM6XFxuJHtpbnNpZ2h0cy5hY3Rpb25faXRlbXM/Lm1hcCgoYWkpID0+IGAtICR7YWkuZGVzY3JpcHRpb259IChBc3NpZ25lZTogJHthaS5zdWdnZXN0ZWRfYXNzaWduZWUgfHwgJ04vQSd9KWApLmpvaW4oJ1xcbicpIHx8ICdOL0EnfVxcblxcbiR7bmx1RW50aXRpZXMuZW1haWxfZHJhZnRfZGV0YWlscz8uYWRkaXRpb25hbF9pbnN0cnVjdGlvbnMgfHwgJyd9XFxuXFxuQmVzdCByZWdhcmRzLFxcbkF0b20gQWdlbnRgLFxuICAgICAgICAgICAgdG86XG4gICAgICAgICAgICAgIHR5cGVvZiBubHVFbnRpdGllcy5lbWFpbF9kcmFmdF9kZXRhaWxzPy5yZWNpcGllbnRzID09PSAnc3RyaW5nJ1xuICAgICAgICAgICAgICAgID8gW25sdUVudGl0aWVzLmVtYWlsX2RyYWZ0X2RldGFpbHMucmVjaXBpZW50c11cbiAgICAgICAgICAgICAgICA6IG5sdUVudGl0aWVzLmVtYWlsX2RyYWZ0X2RldGFpbHM/LnJlY2lwaWVudHMgfHwgWydhdHRlbmRlZXMnXSxcbiAgICAgICAgICB9O1xuICAgICAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICAgICAgYFtwb3N0TWVldGluZ1dvcmtmbG93U2tpbGxdIERSQUZUX0ZPTExPV19VUF9FTUFJTCBpcyB1c2luZyBwbGFjZWhvbGRlciBkYXRhLmBcbiAgICAgICAgICApO1xuICAgICAgICAgIGJyZWFrO1xuXG4gICAgICAgIGNhc2UgJ0NSRUFURV9UQVNLU19JTl9OT1RJT04nOlxuICAgICAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICAgICAgYFtwb3N0TWVldGluZ1dvcmtmbG93U2tpbGxdIEFjdGlvbjogQ1JFQVRFX1RBU0tTX0lOX05PVElPTmBcbiAgICAgICAgICApO1xuICAgICAgICAgIHJlc3VsdHMuY3JlYXRlZF9ub3Rpb25fdGFza3MgPSBbXTtcbiAgICAgICAgICBpZiAoaW5zaWdodHMuYWN0aW9uX2l0ZW1zICYmIGluc2lnaHRzLmFjdGlvbl9pdGVtcy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgICBmb3IgKGNvbnN0IGFpIG9mIGluc2lnaHRzLmFjdGlvbl9pdGVtcykge1xuICAgICAgICAgICAgICAvLyBUT0RPOiBDYWxsIGFjdHVhbCBub3Rpb25Ta2lsbHMuY3JlYXRlVGFza1xuICAgICAgICAgICAgICAvLyBjb25zdCBub3Rpb25UYXNrUGFyYW1zOiBDcmVhdGVOb3Rpb25UYXNrUGFyYW1zID0ge1xuICAgICAgICAgICAgICAvLyAgIGRlc2NyaXB0aW9uOiBhaS5kZXNjcmlwdGlvbixcbiAgICAgICAgICAgICAgLy8gICBkdWVEYXRlOiBhaS5zdWdnZXN0ZWRfZHVlX2RhdGUsIC8vIE1heSBuZWVkIGRhdGUgcGFyc2luZ1xuICAgICAgICAgICAgICAvLyAgIGFzc2lnbmVlOiBhaS5zdWdnZXN0ZWRfYXNzaWduZWUsIC8vIE1heSBuZWVkIHJlc29sdXRpb24gdG8gTm90aW9uIHVzZXJcbiAgICAgICAgICAgICAgLy8gICBub3Rpb25UYXNrc0RiSWQ6IG5sdUVudGl0aWVzLnRhc2tfY3JlYXRpb25fZGV0YWlscz8ubm90aW9uX2RhdGFiYXNlX2lkIHx8IHByb2Nlc3MuZW52LkFUT01fTk9USU9OX1RBU0tTX0RBVEFCQVNFX0lELFxuICAgICAgICAgICAgICAvLyB9O1xuICAgICAgICAgICAgICAvLyBjb25zdCB0YXNrUmVzdWx0ID0gYXdhaXQgbm90aW9uU2tpbGxzLmNyZWF0ZU5vdGlvblRhc2sodXNlcklkLCBub3Rpb25UYXNrUGFyYW1zKTtcbiAgICAgICAgICAgICAgLy8gaWYgKHRhc2tSZXN1bHQub2sgJiYgdGFza1Jlc3VsdC5kYXRhKSB7XG4gICAgICAgICAgICAgIC8vICAgcmVzdWx0cy5jcmVhdGVkX25vdGlvbl90YXNrcy5wdXNoKHsgdGFza0lkOiB0YXNrUmVzdWx0LmRhdGEudGFza0lkLCB0YXNrVXJsOiB0YXNrUmVzdWx0LmRhdGEudGFza1VybCwgZGVzY3JpcHRpb246IGFpLmRlc2NyaXB0aW9uIH0pO1xuICAgICAgICAgICAgICAvLyB9IGVsc2UgeyAuLi4gaGFuZGxlIGVycm9yIC4uLiB9XG4gICAgICAgICAgICAgIHJlc3VsdHMuY3JlYXRlZF9ub3Rpb25fdGFza3MucHVzaCh7XG4gICAgICAgICAgICAgICAgdGFza0lkOiBgc2ltX3Rhc2tfJHtEYXRlLm5vdygpfV8ke3Jlc3VsdHMuY3JlYXRlZF9ub3Rpb25fdGFza3MubGVuZ3RofWAsXG4gICAgICAgICAgICAgICAgdGFza1VybDogYGh0dHBzOi8vbm90aW9uLnNvL3NpbV90YXNrXyR7RGF0ZS5ub3coKX1gLFxuICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiBhaS5kZXNjcmlwdGlvbixcbiAgICAgICAgICAgICAgICBhc3NpZ25lZTogYWkuc3VnZ2VzdGVkX2Fzc2lnbmVlLFxuICAgICAgICAgICAgICAgIGR1ZURhdGU6IGFpLnN1Z2dlc3RlZF9kdWVfZGF0ZSxcbiAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICAgICAgYFtwb3N0TWVldGluZ1dvcmtmbG93U2tpbGxdIENSRUFURV9UQVNLU19JTl9OT1RJT04gaXMgdXNpbmcgcGxhY2Vob2xkZXIgZGF0YS5gXG4gICAgICAgICAgKTtcbiAgICAgICAgICBicmVhaztcbiAgICAgICAgZGVmYXVsdDpcbiAgICAgICAgICBsb2dnZXIud2FybihcbiAgICAgICAgICAgIGBbcG9zdE1lZXRpbmdXb3JrZmxvd1NraWxsXSBVbmtub3duIHJlcXVlc3RlZCBhY3Rpb246ICR7YWN0aW9ufWBcbiAgICAgICAgICApO1xuICAgICAgICAgIHJlc3VsdHMuZXJyb3JzX2VuY291bnRlcmVkPy5wdXNoKHtcbiAgICAgICAgICAgIGFjdGlvbl9hdHRlbXB0ZWQ6IGFjdGlvbiBhcyBhbnksXG4gICAgICAgICAgICBtZXNzYWdlOiBgVW5rbm93biByZXF1ZXN0ZWQgYWN0aW9uOiAke2FjdGlvbn1gLFxuICAgICAgICAgIH0pO1xuICAgICAgfVxuICAgIH0gY2F0Y2ggKGFjdGlvbkVycm9yOiBhbnkpIHtcbiAgICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICAgYFtwb3N0TWVldGluZ1dvcmtmbG93U2tpbGxdIEVycm9yIHBlcmZvcm1pbmcgYWN0aW9uICR7YWN0aW9ufTogJHthY3Rpb25FcnJvci5tZXNzYWdlfWAsXG4gICAgICAgIGFjdGlvbkVycm9yXG4gICAgICApO1xuICAgICAgcmVzdWx0cy5lcnJvcnNfZW5jb3VudGVyZWQ/LnB1c2goe1xuICAgICAgICBhY3Rpb25fYXR0ZW1wdGVkOiBhY3Rpb24gYXMgYW55LFxuICAgICAgICBtZXNzYWdlOiBgRXJyb3IgZHVyaW5nIGFjdGlvbiAke2FjdGlvbn06ICR7YWN0aW9uRXJyb3IubWVzc2FnZX1gLFxuICAgICAgICBkZXRhaWxzOiBhY3Rpb25FcnJvci5zdGFjayxcbiAgICAgIH0pO1xuICAgIH1cbiAgfVxuXG4gIGxvZ2dlci5pbmZvKFxuICAgIGBbcG9zdE1lZXRpbmdXb3JrZmxvd1NraWxsXSBGaW5pc2hlZCBwb3N0LW1lZXRpbmcgYWN0aW9ucyBmb3IgdXNlciAke3VzZXJJZH0uYFxuICApO1xuICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogcmVzdWx0cyB9O1xufVxuIl19