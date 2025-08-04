"use strict";
// import { invokeLLM } from '../lib/llmUtils'; // For future LLM-based enhancements
Object.defineProperty(exports, "__esModule", { value: true });
exports.WorkflowAutomationSuggesterSkill = void 0;
/**
 * Skill to observe repetitive user actions and suggest potential automations.
 */
class WorkflowAutomationSuggesterSkill {
    constructor() {
        console.log('WorkflowAutomationSuggesterSkill initialized.');
        // In a real system, this might connect to an action logging service or a pattern mining engine.
    }
    /**
     * Analyzes recent user actions to find repetitive patterns and suggest automations.
     * @param input The input containing the userId and a list of recent actions.
     * @returns A Promise resolving to an array of AutomationSuggestion objects.
     */
    async execute(input) {
        console.log(`[WorkflowAutomationSuggesterSkill] Received ${input.recentActions.length} actions for user: ${input.userId}`);
        const suggestions = [];
        // 1. Validate input (userId, recentActions) - Basic check
        if (!input.userId || !input.recentActions) {
            console.warn('[WorkflowAutomationSuggesterSkill] Missing userId or recentActions.');
            return [];
        }
        if (input.recentActions.length < 3) {
            // Need at least a few actions to find a pattern
            console.log('[WorkflowAutomationSuggesterSkill] Not enough actions to detect patterns meaningfully.');
            return [];
        }
        console.log(`[WorkflowAutomationSuggesterSkill] Analyzing ${input.recentActions.length} actions for user: ${input.userId}`);
        // 2. Implement mock pattern detection:
        //    Define a simple target pattern, e.g., sequence:
        //      Action1: { application: 'SpreadsheetApp', actionType: 'COPY_CELL_RANGE' }
        //      Action2: { application: 'EmailClient', actionType: 'CREATE_NEW_EMAIL' }
        //      Action3: { application: 'EmailClient', actionType: 'PASTE_INTO_BODY' }
        //      Action4: { application: 'EmailClient', actionType: 'SEND_EMAIL' }
        //    (This is a very basic stand-in for complex pattern mining algorithms or LLM-based sequence analysis).
        const actions = input.recentActions;
        for (let i = 0; i < actions.length - 3; i++) {
            // Need at least 4 actions for this specific pattern
            const potentialPatternActions = actions.slice(i, i + 4);
            // Mock check for a specific hardcoded pattern: Copy from Spreadsheet, Create Email, Paste, Send.
            if (potentialPatternActions[0].application === 'SpreadsheetApp' &&
                potentialPatternActions[0].actionType === 'COPY_CELL_RANGE' &&
                potentialPatternActions[1].application === 'EmailClient' &&
                potentialPatternActions[1].actionType === 'CREATE_NEW_EMAIL' &&
                potentialPatternActions[2].application === 'EmailClient' &&
                potentialPatternActions[2].actionType === 'PASTE_INTO_BODY' &&
                potentialPatternActions[3].application === 'EmailClient' &&
                potentialPatternActions[3].actionType === 'SEND_EMAIL') {
                console.log(`[WorkflowAutomationSuggesterSkill] Mock pattern "Copy-Paste-Send Report" detected starting at action ID ${potentialPatternActions[0].id}`);
                // 4. If mock pattern is detected:
                //    a. Create a corresponding AutomationSuggestion object
                const suggestion = {
                    id: `sugg-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
                    title: 'Automate Sending Copied Spreadsheet Data via Email',
                    description: 'Detected a pattern where you copy data from a spreadsheet, create a new email, paste the data, and send it. This could potentially be automated.',
                    basedOnActionIds: potentialPatternActions.map((a) => a.id),
                    suggestedMacro: `
                  1. Get data from Spreadsheet (e.g., range specified in details: ${JSON.stringify(potentialPatternActions[0].details?.range || 'last copied range')}).
                  2. Create new Email.
                  3. (Optional) Set recipient (e.g., from details: ${JSON.stringify(potentialPatternActions[1].details?.to || 'common recipient')}).
                  4. (Optional) Set subject (e.g., "Data Report").
                  5. Paste/insert data into email body.
                  6. Send Email.
                `,
                    userBenefit: 'Could save a few minutes each time this task is performed.',
                    confidence: 0.7, // Mock confidence
                };
                suggestions.push(suggestion);
                // For this mock, let's only find the first instance of the pattern to keep it simple.
                // In a real system, you'd find all occurrences or use more sophisticated frequency analysis.
                break;
            }
        }
        // 5. Return the suggestions array.
        if (suggestions.length > 0) {
            console.log(`[WorkflowAutomationSuggesterSkill] Generated ${suggestions.length} automation suggestion(s).`);
        }
        else {
            console.log('[WorkflowAutomationSuggesterSkill] No predefined mock patterns detected in the provided action sequence.');
        }
        return suggestions;
    }
}
exports.WorkflowAutomationSuggesterSkill = WorkflowAutomationSuggesterSkill;
// Example Usage (for testing or demonstration)
/*
async function testWorkflowAutomationSuggesterSkill() {
  const skill = new WorkflowAutomationSuggesterSkill();

  // Sample actions that might form a pattern
  const sampleActions: UserAction[] = [
    { id: "act1", timestamp: new Date(), userId: "user123", application: "SpreadsheetApp", actionType: "COPY_CELL_RANGE", details: { sheet: "Sheet1", range: "A1:B10" } },
    { id: "act2", timestamp: new Date(), userId: "user123", application: "EmailClient", actionType: "CREATE_NEW_EMAIL", details: { to: "report_distribution@example.com" } },
    { id: "act3", timestamp: new Date(), userId: "user123", application: "EmailClient", actionType: "SET_SUBJECT", details: { subject: "Weekly Sales Data" } },
    { id: "act4", timestamp: new Date(), userId: "user123", application: "EmailClient", actionType: "PASTE_INTO_BODY" },
    { id: "act5", timestamp: new Date(), userId: "user123", application: "EmailClient", actionType: "SEND_EMAIL" },
    // ... more actions, some repetitive, some not ...
    { id: "act6", timestamp: new Date(), userId: "user123", application: "Browser", actionType: "NAVIGATE_URL", details: { url: "http://example.com/dashboard" } },
    { id: "act7", timestamp: new Date(), userId: "user123", application: "SpreadsheetApp", actionType: "COPY_CELL_RANGE", details: { sheet: "Sheet1", range: "A1:B10" } },
    { id: "act8", timestamp: new Date(), userId: "user123", application: "EmailClient", actionType: "CREATE_NEW_EMAIL", details: { to: "report_distribution@example.com" } },
    { id: "act9", timestamp: new Date(), userId: "user123", application: "EmailClient", actionType: "SET_SUBJECT", details: { subject: "Weekly Sales Data" } },
    { id: "act10", timestamp: new Date(), userId: "user123", application: "EmailClient", actionType: "PASTE_INTO_BODY" },
    { id: "act11", timestamp: new Date(), userId: "user123", application: "EmailClient", actionType: "SEND_EMAIL" },
  ];

  const input: WorkflowAutomationSuggesterSkillInput = {
    userId: "user123",
    recentActions: sampleActions
  };

  try {
    console.log("\\n--- Test Case: Workflow Automation Suggester ---");
    const suggestions = await skill.execute(input);
    if (suggestions.length > 0) {
      console.log("Found suggestions:");
      console.log(JSON.stringify(suggestions, null, 2));
    } else {
      console.log("No automation suggestions found for the given actions.");
    }
  } catch (error) {
    console.error("Error during skill execution (Workflow Automation Suggester):", error);
  }
}

// testWorkflowAutomationSuggesterSkill();
*/
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoid29ya2Zsb3dBdXRvbWF0aW9uU3VnZ2VzdGVyU2tpbGwuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ3b3JrZmxvd0F1dG9tYXRpb25TdWdnZXN0ZXJTa2lsbC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiO0FBQUEsb0ZBQW9GOzs7QUF1Q3BGOztHQUVHO0FBQ0gsTUFBYSxnQ0FBZ0M7SUFDM0M7UUFDRSxPQUFPLENBQUMsR0FBRyxDQUFDLCtDQUErQyxDQUFDLENBQUM7UUFDN0QsZ0dBQWdHO0lBQ2xHLENBQUM7SUFFRDs7OztPQUlHO0lBQ0ksS0FBSyxDQUFDLE9BQU8sQ0FDbEIsS0FBNEM7UUFFNUMsT0FBTyxDQUFDLEdBQUcsQ0FDVCwrQ0FBK0MsS0FBSyxDQUFDLGFBQWEsQ0FBQyxNQUFNLHNCQUFzQixLQUFLLENBQUMsTUFBTSxFQUFFLENBQzlHLENBQUM7UUFFRixNQUFNLFdBQVcsR0FBMkIsRUFBRSxDQUFDO1FBRS9DLDBEQUEwRDtRQUMxRCxJQUFJLENBQUMsS0FBSyxDQUFDLE1BQU0sSUFBSSxDQUFDLEtBQUssQ0FBQyxhQUFhLEVBQUUsQ0FBQztZQUMxQyxPQUFPLENBQUMsSUFBSSxDQUNWLHFFQUFxRSxDQUN0RSxDQUFDO1lBQ0YsT0FBTyxFQUFFLENBQUM7UUFDWixDQUFDO1FBQ0QsSUFBSSxLQUFLLENBQUMsYUFBYSxDQUFDLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztZQUNuQyxnREFBZ0Q7WUFDaEQsT0FBTyxDQUFDLEdBQUcsQ0FDVCx3RkFBd0YsQ0FDekYsQ0FBQztZQUNGLE9BQU8sRUFBRSxDQUFDO1FBQ1osQ0FBQztRQUNELE9BQU8sQ0FBQyxHQUFHLENBQ1QsZ0RBQWdELEtBQUssQ0FBQyxhQUFhLENBQUMsTUFBTSxzQkFBc0IsS0FBSyxDQUFDLE1BQU0sRUFBRSxDQUMvRyxDQUFDO1FBRUYsdUNBQXVDO1FBQ3ZDLHFEQUFxRDtRQUNyRCxpRkFBaUY7UUFDakYsK0VBQStFO1FBQy9FLDhFQUE4RTtRQUM5RSx5RUFB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L2xpYi9sbG1VdGlscyc7IC8vIEZvciBmdXR1cmUgTExNLWJhc2VkIGVuaGFuY2VtZW50c1xuXG4vKipcbiAqIFJlcHJlc2VudHMgYSBzaW5nbGUgb2JzZXJ2ZWQgdXNlciBhY3Rpb24uXG4gKi9cbmV4cG9ydCBpbnRlcmZhY2UgVXNlckFjdGlvbiB7XG4gIGlkOiBzdHJpbmc7IC8vIFVuaXF1ZSBJRCBmb3IgdGhlIGFjdGlvbiBldmVudFxuICB0aW1lc3RhbXA6IERhdGU7XG4gIHVzZXJJZDogc3RyaW5nO1xuICBhcHBsaWNhdGlvbjogc3RyaW5nOyAvLyBlLmcuLCBcIkVtYWlsQ2xpZW50XCIsIFwiU3ByZWFkc2hlZXRBcHBcIiwgXCJUZXh0RWRpdG9yXCIsIFwiQnJvd3NlclwiXG4gIGFjdGlvblR5cGU6IHN0cmluZzsgLy8gZS5nLiwgXCJDT1BZX0NFTExfUkFOR0VcIiwgXCJQQVNURV9JTlRPX0JPRFlcIiwgXCJDUkVBVEVfTkVXX0VNQUlMXCIsIFwiTkFWSUdBVEVfVVJMXCJcbiAgZGV0YWlscz86IFJlY29yZDxzdHJpbmcsIGFueT47IC8vIFNwZWNpZmljcyBvZiB0aGUgYWN0aW9uLCBlLmcuLCB7IHJhbmdlOiAnQTE6QjEwJywgdXJsOiAnaHR0cDovLy4uLicgfVxufVxuXG4vKipcbiAqIFJlcHJlc2VudHMgYSBzdWdnZXN0aW9uIGZvciBhdXRvbWF0aW5nIGEgZGV0ZWN0ZWQgcmVwZXRpdGl2ZSB3b3JrZmxvdy5cbiAqL1xuZXhwb3J0IGludGVyZmFjZSBBdXRvbWF0aW9uU3VnZ2VzdGlvbiB7XG4gIGlkOiBzdHJpbmc7IC8vIFVuaXF1ZSBJRCBmb3IgdGhlIHN1Z2dlc3Rpb25cbiAgdGl0bGU6IHN0cmluZzsgLy8gVXNlci1mcmllbmRseSB0aXRsZSwgZS5nLiwgXCJBdXRvbWF0ZSBzZW5kaW5nIHdlZWtseSByZXBvcnQgZGF0YVwiXG4gIGRlc2NyaXB0aW9uOiBzdHJpbmc7IC8vIEV4cGxhbmF0aW9uIG9mIHRoZSByZXBldGl0aXZlIHBhdHRlcm4gZGV0ZWN0ZWRcbiAgYmFzZWRPbkFjdGlvbklkczogc3RyaW5nW107IC8vIElEcyBvZiB0aGUgVXNlckFjdGlvbiBldmVudHMgdGhhdCBmb3JtIHRoZSBkZXRlY3RlZCBwYXR0ZXJuXG4gIHN1Z2dlc3RlZE1hY3JvPzogc3RyaW5nOyAvLyBQc2V1ZG8tY29kZSBvciBkZXNjcmlwdGl2ZSBzdGVwcyBmb3IgdGhlIGF1dG9tYXRpb25cbiAgdXNlckJlbmVmaXQ/OiBzdHJpbmc7IC8vIGUuZy4sIFwiU2F2ZXMgYXBwcm94aW1hdGVseSAyIG1pbnV0ZXMgcGVyIHRhc2tcIlxuICBjb25maWRlbmNlPzogbnVtYmVyOyAvLyBIb3cgY29uZmlkZW50IHRoZSBzeXN0ZW0gaXMgdGhhdCB0aGlzIGlzIGEgdXNlZnVsIHN1Z2dlc3Rpb24gKDAuMCB0byAxLjApXG4gIC8vIFdlIGNvdWxkIGFsc28gYWRkOiBlc3RpbWF0ZWRUaW1lU2F2ZWRQZXJJbnN0YW5jZTogbnVtYmVyIChpbiBzZWNvbmRzL21pbnV0ZXMpXG4gIC8vICAgICAgICAgICAgICAgICAgICAgZnJlcXVlbmN5T2ZQYXR0ZXJuOiBudW1iZXIgKGhvdyBtYW55IHRpbWVzIGl0IHdhcyBvYnNlcnZlZCBpbiBhIHBlcmlvZClcbn1cblxuLyoqXG4gKiBJbnB1dCBmb3IgdGhlIFdvcmtmbG93QXV0b21hdGlvblN1Z2dlc3RlclNraWxsLlxuICovXG5leHBvcnQgaW50ZXJmYWNlIFdvcmtmbG93QXV0b21hdGlvblN1Z2dlc3RlclNraWxsSW5wdXQge1xuICB1c2VySWQ6IHN0cmluZztcbiAgcmVjZW50QWN0aW9uczogVXNlckFjdGlvbltdOyAvLyBBIGxpc3Qgb2YgcmVjZW50IGFjdGlvbnMgdG8gYW5hbHl6ZVxuICAvLyBDb3VsZCBhbHNvIGluY2x1ZGU6IGFuYWx5c2lzVGltZVdpbmRvdzogeyBzdGFydERhdGU6IERhdGUsIGVuZERhdGU6IERhdGUgfVxuICAvLyAgICAgICAgICAgICAgICAgICAgIG1pblBhdHRlcm5GcmVxdWVuY3k6IG51bWJlciAodG8gZmlsdGVyIHN1Z2dlc3Rpb25zKVxufVxuXG4vKipcbiAqIFNraWxsIHRvIG9ic2VydmUgcmVwZXRpdGl2ZSB1c2VyIGFjdGlvbnMgYW5kIHN1Z2dlc3QgcG90ZW50aWFsIGF1dG9tYXRpb25zLlxuICovXG5leHBvcnQgY2xhc3MgV29ya2Zsb3dBdXRvbWF0aW9uU3VnZ2VzdGVyU2tpbGwge1xuICBjb25zdHJ1Y3RvcigpIHtcbiAgICBjb25zb2xlLmxvZygnV29ya2Zsb3dBdXRvbWF0aW9uU3VnZ2VzdGVyU2tpbGwgaW5pdGlhbGl6ZWQuJyk7XG4gICAgLy8gSW4gYSByZWFsIHN5c3RlbSwgdGhpcyBtaWdodCBjb25uZWN0IHRvIGFuIGFjdGlvbiBsb2dnaW5nIHNlcnZpY2Ugb3IgYSBwYXR0ZXJuIG1pbmluZyBlbmdpbmUuXG4gIH1cblxuICAvKipcbiAgICogQW5hbHl6ZXMgcmVjZW50IHVzZXIgYWN0aW9ucyB0byBmaW5kIHJlcGV0aXRpdmUgcGF0dGVybnMgYW5kIHN1Z2dlc3QgYXV0b21hdGlvbnMuXG4gICAqIEBwYXJhbSBpbnB1dCBUaGUgaW5wdXQgY29udGFpbmluZyB0aGUgdXNlcklkIGFuZCBhIGxpc3Qgb2YgcmVjZW50IGFjdGlvbnMuXG4gICAqIEByZXR1cm5zIEEgUHJvbWlzZSByZXNvbHZpbmcgdG8gYW4gYXJyYXkgb2YgQXV0b21hdGlvblN1Z2dlc3Rpb24gb2JqZWN0cy5cbiAgICovXG4gIHB1YmxpYyBhc3luYyBleGVjdXRlKFxuICAgIGlucHV0OiBXb3JrZmxvd0F1dG9tYXRpb25TdWdnZXN0ZXJTa2lsbElucHV0XG4gICk6IFByb21pc2U8QXV0b21hdGlvblN1Z2dlc3Rpb25bXT4ge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYFtXb3JrZmxvd0F1dG9tYXRpb25TdWdnZXN0ZXJTa2lsbF0gUmVjZWl2ZWQgJHtpbnB1dC5yZWNlbnRBY3Rpb25zLmxlbmd0aH0gYWN0aW9ucyBmb3IgdXNlcjogJHtpbnB1dC51c2VySWR9YFxuICAgICk7XG5cbiAgICBjb25zdCBzdWdnZXN0aW9uczogQXV0b21hdGlvblN1Z2dlc3Rpb25bXSA9IFtdO1xuXG4gICAgLy8gMS4gVmFsaWRhdGUgaW5wdXQgKHVzZXJJZCwgcmVjZW50QWN0aW9ucykgLSBCYXNpYyBjaGVja1xuICAgIGlmICghaW5wdXQudXNlcklkIHx8ICFpbnB1dC5yZWNlbnRBY3Rpb25zKSB7XG4gICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICdbV29ya2Zsb3dBdXRvbWF0aW9uU3VnZ2VzdGVyU2tpbGxdIE1pc3NpbmcgdXNlcklkIG9yIHJlY2VudEFjdGlvbnMuJ1xuICAgICAgKTtcbiAgICAgIHJldHVybiBbXTtcbiAgICB9XG4gICAgaWYgKGlucHV0LnJlY2VudEFjdGlvbnMubGVuZ3RoIDwgMykge1xuICAgICAgLy8gTmVlZCBhdCBsZWFzdCBhIGZldyBhY3Rpb25zIHRvIGZpbmQgYSBwYXR0ZXJuXG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgJ1tXb3JrZmxvd0F1dG9tYXRpb25TdWdnZXN0ZXJTa2lsbF0gTm90IGVub3VnaCBhY3Rpb25zIHRvIGRldGVjdCBwYXR0ZXJucyBtZWFuaW5nZnVsbHkuJ1xuICAgICAgKTtcbiAgICAgIHJldHVybiBbXTtcbiAgICB9XG4gICAgY29uc29sZS5sb2coXG4gICAgICBgW1dvcmtmbG93QXV0b21hdGlvblN1Z2dlc3RlclNraWxsXSBBbmFseXppbmcgJHtpbnB1dC5yZWNlbnRBY3Rpb25zLmxlbmd0aH0gYWN0aW9ucyBmb3IgdXNlcjogJHtpbnB1dC51c2VySWR9YFxuICAgICk7XG5cbiAgICAvLyAyLiBJbXBsZW1lbnQgbW9jayBwYXR0ZXJuIGRldGVjdGlvbjpcbiAgICAvLyAgICBEZWZpbmUgYSBzaW1wbGUgdGFyZ2V0IHBhdHRlcm4sIGUuZy4sIHNlcXVlbmNlOlxuICAgIC8vICAgICAgQWN0aW9uMTogeyBhcHBsaWNhdGlvbjogJ1NwcmVhZHNoZWV0QXBwJywgYWN0aW9uVHlwZTogJ0NPUFlfQ0VMTF9SQU5HRScgfVxuICAgIC8vICAgICAgQWN0aW9uMjogeyBhcHBsaWNhdGlvbjogJ0VtYWlsQ2xpZW50JywgYWN0aW9uVHlwZTogJ0NSRUFURV9ORVdfRU1BSUwnIH1cbiAgICAvLyAgICAgIEFjdGlvbjM6IHsgYXBwbGljYXRpb246ICdFbWFpbENsaWVudCcsIGFjdGlvblR5cGU6ICdQQVNURV9JTlRPX0JPRFknIH1cbiAgICAvLyAgICAgIEFjdGlvbjQ6IHsgYXBwbGljYXRpb246ICdFbWFpbENsaWVudCcsIGFjdGlvblR5cGU6ICdTRU5EX0VNQUlMJyB9XG4gICAgLy8gICAgKFRoaXMgaXMgYSB2ZXJ5IGJhc2ljIHN0YW5kLWluIGZvciBjb21wbGV4IHBhdHRlcm4gbWluaW5nIGFsZ29yaXRobXMgb3IgTExNLWJhc2VkIHNlcXVlbmNlIGFuYWx5c2lzKS5cblxuICAgIGNvbnN0IGFjdGlvbnMgPSBpbnB1dC5yZWNlbnRBY3Rpb25zO1xuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgYWN0aW9ucy5sZW5ndGggLSAzOyBpKyspIHtcbiAgICAgIC8vIE5lZWQgYXQgbGVhc3QgNCBhY3Rpb25zIGZvciB0aGlzIHNwZWNpZmljIHBhdHRlcm5cbiAgICAgIGNvbnN0IHBvdGVudGlhbFBhdHRlcm5BY3Rpb25zID0gYWN0aW9ucy5zbGljZShpLCBpICsgNCk7XG5cbiAgICAgIC8vIE1vY2sgY2hlY2sgZm9yIGEgc3BlY2lmaWMgaGFyZGNvZGVkIHBhdHRlcm46IENvcHkgZnJvbSBTcHJlYWRzaGVldCwgQ3JlYXRlIEVtYWlsLCBQYXN0ZSwgU2VuZC5cbiAgICAgIGlmIChcbiAgICAgICAgcG90ZW50aWFsUGF0dGVybkFjdGlvbnNbMF0uYXBwbGljYXRpb24gPT09ICdTcHJlYWRzaGVldEFwcCcgJiZcbiAgICAgICAgcG90ZW50aWFsUGF0dGVybkFjdGlvbnNbMF0uYWN0aW9uVHlwZSA9PT0gJ0NPUFlfQ0VMTF9SQU5HRScgJiZcbiAgICAgICAgcG90ZW50aWFsUGF0dGVybkFjdGlvbnNbMV0uYXBwbGljYXRpb24gPT09ICdFbWFpbENsaWVudCcgJiZcbiAgICAgICAgcG90ZW50aWFsUGF0dGVybkFjdGlvbnNbMV0uYWN0aW9uVHlwZSA9PT0gJ0NSRUFURV9ORVdfRU1BSUwnICYmXG4gICAgICAgIHBvdGVudGlhbFBhdHRlcm5BY3Rpb25zWzJdLmFwcGxpY2F0aW9uID09PSAnRW1haWxDbGllbnQnICYmXG4gICAgICAgIHBvdGVudGlhbFBhdHRlcm5BY3Rpb25zWzJdLmFjdGlvblR5cGUgPT09ICdQQVNURV9JTlRPX0JPRFknICYmXG4gICAgICAgIHBvdGVudGlhbFBhdHRlcm5BY3Rpb25zWzNdLmFwcGxpY2F0aW9uID09PSAnRW1haWxDbGllbnQnICYmXG4gICAgICAgIHBvdGVudGlhbFBhdHRlcm5BY3Rpb25zWzNdLmFjdGlvblR5cGUgPT09ICdTRU5EX0VNQUlMJ1xuICAgICAgKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIGBbV29ya2Zsb3dBdXRvbWF0aW9uU3VnZ2VzdGVyU2tpbGxdIE1vY2sgcGF0dGVybiBcIkNvcHktUGFzdGUtU2VuZCBSZXBvcnRcIiBkZXRlY3RlZCBzdGFydGluZyBhdCBhY3Rpb24gSUQgJHtwb3RlbnRpYWxQYXR0ZXJuQWN0aW9uc1swXS5pZH1gXG4gICAgICAgICk7XG5cbiAgICAgICAgLy8gNC4gSWYgbW9jayBwYXR0ZXJuIGlzIGRldGVjdGVkOlxuICAgICAgICAvLyAgICBhLiBDcmVhdGUgYSBjb3JyZXNwb25kaW5nIEF1dG9tYXRpb25TdWdnZXN0aW9uIG9iamVjdFxuICAgICAgICBjb25zdCBzdWdnZXN0aW9uOiBBdXRvbWF0aW9uU3VnZ2VzdGlvbiA9IHtcbiAgICAgICAgICBpZDogYHN1Z2ctJHtEYXRlLm5vdygpfS0ke01hdGgucmFuZG9tKCkudG9TdHJpbmcoMzYpLnN1YnN0cmluZygyLCA3KX1gLFxuICAgICAgICAgIHRpdGxlOiAnQXV0b21hdGUgU2VuZGluZyBDb3BpZWQgU3ByZWFkc2hlZXQgRGF0YSB2aWEgRW1haWwnLFxuICAgICAgICAgIGRlc2NyaXB0aW9uOlxuICAgICAgICAgICAgJ0RldGVjdGVkIGEgcGF0dGVybiB3aGVyZSB5b3UgY29weSBkYXRhIGZyb20gYSBzcHJlYWRzaGVldCwgY3JlYXRlIGEgbmV3IGVtYWlsLCBwYXN0ZSB0aGUgZGF0YSwgYW5kIHNlbmQgaXQuIFRoaXMgY291bGQgcG90ZW50aWFsbHkgYmUgYXV0b21hdGVkLicsXG4gICAgICAgICAgYmFzZWRPbkFjdGlvbklkczogcG90ZW50aWFsUGF0dGVybkFjdGlvbnMubWFwKChhKSA9PiBhLmlkKSxcbiAgICAgICAgICBzdWdnZXN0ZWRNYWNybzogYFxuICAgICAgICAgICAgICAgICAgMS4gR2V0IGRhdGEgZnJvbSBTcHJlYWRzaGVldCAoZS5nLiwgcmFuZ2Ugc3BlY2lmaWVkIGluIGRldGFpbHM6ICR7SlNPTi5zdHJpbmdpZnkocG90ZW50aWFsUGF0dGVybkFjdGlvbnNbMF0uZGV0YWlscz8ucmFuZ2UgfHwgJ2xhc3QgY29waWVkIHJhbmdlJyl9KS5cbiAgICAgICAgICAgICAgICAgIDIuIENyZWF0ZSBuZXcgRW1haWwuXG4gICAgICAgICAgICAgICAgICAzLiAoT3B0aW9uYWwpIFNldCByZWNpcGllbnQgKGUuZy4sIGZyb20gZGV0YWlsczogJHtKU09OLnN0cmluZ2lmeShwb3RlbnRpYWxQYXR0ZXJuQWN0aW9uc1sxXS5kZXRhaWxzPy50byB8fCAnY29tbW9uIHJlY2lwaWVudCcpfSkuXG4gICAgICAgICAgICAgICAgICA0LiAoT3B0aW9uYWwpIFNldCBzdWJqZWN0IChlLmcuLCBcIkRhdGEgUmVwb3J0XCIpLlxuICAgICAgICAgICAgICAgICAgNS4gUGFzdGUvaW5zZXJ0IGRhdGEgaW50byBlbWFpbCBib2R5LlxuICAgICAgICAgICAgICAgICAgNi4gU2VuZCBFbWFpbC5cbiAgICAgICAgICAgICAgICBgLFxuICAgICAgICAgIHVzZXJCZW5lZml0OlxuICAgICAgICAgICAgJ0NvdWxkIHNhdmUgYSBmZXcgbWludXRlcyBlYWNoIHRpbWUgdGhpcyB0YXNrIGlzIHBlcmZvcm1lZC4nLFxuICAgICAgICAgIGNvbmZpZGVuY2U6IDAuNywgLy8gTW9jayBjb25maWRlbmNlXG4gICAgICAgIH07XG4gICAgICAgIHN1Z2dlc3Rpb25zLnB1c2goc3VnZ2VzdGlvbik7XG5cbiAgICAgICAgLy8gRm9yIHRoaXMgbW9jaywgbGV0J3Mgb25seSBmaW5kIHRoZSBmaXJzdCBpbnN0YW5jZSBvZiB0aGUgcGF0dGVybiB0byBrZWVwIGl0IHNpbXBsZS5cbiAgICAgICAgLy8gSW4gYSByZWFsIHN5c3RlbSwgeW91J2QgZmluZCBhbGwgb2NjdXJyZW5jZXMgb3IgdXNlIG1vcmUgc29waGlzdGljYXRlZCBmcmVxdWVuY3kgYW5hbHlzaXMuXG4gICAgICAgIGJyZWFrO1xuICAgICAgfVxuICAgIH1cblxuICAgIC8vIDUuIFJldHVybiB0aGUgc3VnZ2VzdGlvbnMgYXJyYXkuXG4gICAgaWYgKHN1Z2dlc3Rpb25zLmxlbmd0aCA+IDApIHtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBgW1dvcmtmbG93QXV0b21hdGlvblN1Z2dlc3RlclNraWxsXSBHZW5lcmF0ZWQgJHtzdWdnZXN0aW9ucy5sZW5ndGh9IGF1dG9tYXRpb24gc3VnZ2VzdGlvbihzKS5gXG4gICAgICApO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgJ1tXb3JrZmxvd0F1dG9tYXRpb25TdWdnZXN0ZXJTa2lsbF0gTm8gcHJlZGVmaW5lZCBtb2NrIHBhdHRlcm5zIGRldGVjdGVkIGluIHRoZSBwcm92aWRlZCBhY3Rpb24gc2VxdWVuY2UuJ1xuICAgICAgKTtcbiAgICB9XG4gICAgcmV0dXJuIHN1Z2dlc3Rpb25zO1xuICB9XG59XG5cbi8vIEV4YW1wbGUgVXNhZ2UgKGZvciB0ZXN0aW5nIG9yIGRlbW9uc3RyYXRpb24pXG4vKlxuYXN5bmMgZnVuY3Rpb24gdGVzdFdvcmtmbG93QXV0b21hdGlvblN1Z2dlc3RlclNraWxsKCkge1xuICBjb25zdCBza2lsbCA9IG5ldyBXb3JrZmxvd0F1dG9tYXRpb25TdWdnZXN0ZXJTa2lsbCgpO1xuXG4gIC8vIFNhbXBsZSBhY3Rpb25zIHRoYXQgbWlnaHQgZm9ybSBhIHBhdHRlcm5cbiAgY29uc3Qgc2FtcGxlQWN0aW9uczogVXNlckFjdGlvbltdID0gW1xuICAgIHsgaWQ6IFwiYWN0MVwiLCB0aW1lc3RhbXA6IG5ldyBEYXRlKCksIHVzZXJJZDogXCJ1c2VyMTIzXCIsIGFwcGxpY2F0aW9uOiBcIlNwcmVhZHNoZWV0QXBwXCIsIGFjdGlvblR5cGU6IFwiQ09QWV9DRUxMX1JBTkdFXCIsIGRldGFpbHM6IHsgc2hlZXQ6IFwiU2hlZXQxXCIsIHJhbmdlOiBcIkExOkIxMFwiIH0gfSxcbiAgICB7IGlkOiBcImFjdDJcIiwgdGltZXN0YW1wOiBuZXcgRGF0ZSgpLCB1c2VySWQ6IFwidXNlcjEyM1wiLCBhcHBsaWNhdGlvbjogXCJFbWFpbENsaWVudFwiLCBhY3Rpb25UeXBlOiBcIkNSRUFURV9ORVdfRU1BSUxcIiwgZGV0YWlsczogeyB0bzogXCJyZXBvcnRfZGlzdHJpYnV0aW9uQGV4YW1wbGUuY29tXCIgfSB9LFxuICAgIHsgaWQ6IFwiYWN0M1wiLCB0aW1lc3RhbXA6IG5ldyBEYXRlKCksIHVzZXJJZDogXCJ1c2VyMTIzXCIsIGFwcGxpY2F0aW9uOiBcIkVtYWlsQ2xpZW50XCIsIGFjdGlvblR5cGU6IFwiU0VUX1NVQkpFQ1RcIiwgZGV0YWlsczogeyBzdWJqZWN0OiBcIldlZWtseSBTYWxlcyBEYXRhXCIgfSB9LFxuICAgIHsgaWQ6IFwiYWN0NFwiLCB0aW1lc3RhbXA6IG5ldyBEYXRlKCksIHVzZXJJZDogXCJ1c2VyMTIzXCIsIGFwcGxpY2F0aW9uOiBcIkVtYWlsQ2xpZW50XCIsIGFjdGlvblR5cGU6IFwiUEFTVEVfSU5UT19CT0RZXCIgfSxcbiAgICB7IGlkOiBcImFjdDVcIiwgdGltZXN0YW1wOiBuZXcgRGF0ZSgpLCB1c2VySWQ6IFwidXNlcjEyM1wiLCBhcHBsaWNhdGlvbjogXCJFbWFpbENsaWVudFwiLCBhY3Rpb25UeXBlOiBcIlNFTkRfRU1BSUxcIiB9LFxuICAgIC8vIC4uLiBtb3JlIGFjdGlvbnMsIHNvbWUgcmVwZXRpdGl2ZSwgc29tZSBub3QgLi4uXG4gICAgeyBpZDogXCJhY3Q2XCIsIHRpbWVzdGFtcDogbmV3IERhdGUoKSwgdXNlcklkOiBcInVzZXIxMjNcIiwgYXBwbGljYXRpb246IFwiQnJvd3NlclwiLCBhY3Rpb25UeXBlOiBcIk5BVklHQVRFX1VSTFwiLCBkZXRhaWxzOiB7IHVybDogXCJodHRwOi8vZXhhbXBsZS5jb20vZGFzaGJvYXJkXCIgfSB9LFxuICAgIHsgaWQ6IFwiYWN0N1wiLCB0aW1lc3RhbXA6IG5ldyBEYXRlKCksIHVzZXJJZDogXCJ1c2VyMTIzXCIsIGFwcGxpY2F0aW9uOiBcIlNwcmVhZHNoZWV0QXBwXCIsIGFjdGlvblR5cGU6IFwiQ09QWV9DRUxMX1JBTkdFXCIsIGRldGFpbHM6IHsgc2hlZXQ6IFwiU2hlZXQxXCIsIHJhbmdlOiBcIkExOkIxMFwiIH0gfSxcbiAgICB7IGlkOiBcImFjdDhcIiwgdGltZXN0YW1wOiBuZXcgRGF0ZSgpLCB1c2VySWQ6IFwidXNlcjEyM1wiLCBhcHBsaWNhdGlvbjogXCJFbWFpbENsaWVudFwiLCBhY3Rpb25UeXBlOiBcIkNSRUFURV9ORVdfRU1BSUxcIiwgZGV0YWlsczogeyB0bzogXCJyZXBvcnRfZGlzdHJpYnV0aW9uQGV4YW1wbGUuY29tXCIgfSB9LFxuICAgIHsgaWQ6IFwiYWN0OVwiLCB0aW1lc3RhbXA6IG5ldyBEYXRlKCksIHVzZXJJZDogXCJ1c2VyMTIzXCIsIGFwcGxpY2F0aW9uOiBcIkVtYWlsQ2xpZW50XCIsIGFjdGlvblR5cGU6IFwiU0VUX1NVQkpFQ1RcIiwgZGV0YWlsczogeyBzdWJqZWN0OiBcIldlZWtseSBTYWxlcyBEYXRhXCIgfSB9LFxuICAgIHsgaWQ6IFwiYWN0MTBcIiwgdGltZXN0YW1wOiBuZXcgRGF0ZSgpLCB1c2VySWQ6IFwidXNlcjEyM1wiLCBhcHBsaWNhdGlvbjogXCJFbWFpbENsaWVudFwiLCBhY3Rpb25UeXBlOiBcIlBBU1RFX0lOVE9fQk9EWVwiIH0sXG4gICAgeyBpZDogXCJhY3QxMVwiLCB0aW1lc3RhbXA6IG5ldyBEYXRlKCksIHVzZXJJZDogXCJ1c2VyMTIzXCIsIGFwcGxpY2F0aW9uOiBcIkVtYWlsQ2xpZW50XCIsIGFjdGlvblR5cGU6IFwiU0VORF9FTUFJTFwiIH0sXG4gIF07XG5cbiAgY29uc3QgaW5wdXQ6IFdvcmtmbG93QXV0b21hdGlvblN1Z2dlc3RlclNraWxsSW5wdXQgPSB7XG4gICAgdXNlcklkOiBcInVzZXIxMjNcIixcbiAgICByZWNlbnRBY3Rpb25zOiBzYW1wbGVBY3Rpb25zXG4gIH07XG5cbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZyhcIlxcXFxuLS0tIFRlc3QgQ2FzZTogV29ya2Zsb3cgQXV0b21hdGlvbiBTdWdnZXN0ZXIgLS0tXCIpO1xuICAgIGNvbnN0IHN1Z2dlc3Rpb25zID0gYXdhaXQgc2tpbGwuZXhlY3V0ZShpbnB1dCk7XG4gICAgaWYgKHN1Z2dlc3Rpb25zLmxlbmd0aCA+IDApIHtcbiAgICAgIGNvbnNvbGUubG9nKFwiRm91bmQgc3VnZ2VzdGlvbnM6XCIpO1xuICAgICAgY29uc29sZS5sb2coSlNPTi5zdHJpbmdpZnkoc3VnZ2VzdGlvbnMsIG51bGwsIDIpKTtcbiAgICB9IGVsc2Uge1xuICAgICAgY29uc29sZS5sb2coXCJObyBhdXRvbWF0aW9uIHN1Z2dlc3Rpb25zIGZvdW5kIGZvciB0aGUgZ2l2ZW4gYWN0aW9ucy5cIik7XG4gICAgfVxuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGNvbnNvbGUuZXJyb3IoXCJFcnJvciBkdXJpbmcgc2tpbGwgZXhlY3V0aW9uIChXb3JrZmxvdyBBdXRvbWF0aW9uIFN1Z2dlc3Rlcik6XCIsIGVycm9yKTtcbiAgfVxufVxuXG4vLyB0ZXN0V29ya2Zsb3dBdXRvbWF0aW9uU3VnZ2VzdGVyU2tpbGwoKTtcbiovXG4iXX0=