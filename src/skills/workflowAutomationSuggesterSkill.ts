// import { invokeLLM } from '../lib/llmUtils'; // For future LLM-based enhancements

/**
 * Represents a single observed user action.
 */
export interface UserAction {
  id: string; // Unique ID for the action event
  timestamp: Date;
  userId: string;
  application: string; // e.g., "EmailClient", "SpreadsheetApp", "TextEditor", "Browser"
  actionType: string;  // e.g., "COPY_CELL_RANGE", "PASTE_INTO_BODY", "CREATE_NEW_EMAIL", "NAVIGATE_URL"
  details?: Record<string, any>; // Specifics of the action, e.g., { range: 'A1:B10', url: 'http://...' }
}

/**
 * Represents a suggestion for automating a detected repetitive workflow.
 */
export interface AutomationSuggestion {
  id: string; // Unique ID for the suggestion
  title: string; // User-friendly title, e.g., "Automate sending weekly report data"
  description: string; // Explanation of the repetitive pattern detected
  basedOnActionIds: string[]; // IDs of the UserAction events that form the detected pattern
  suggestedMacro?: string; // Pseudo-code or descriptive steps for the automation
  userBenefit?: string; // e.g., "Saves approximately 2 minutes per task"
  confidence?: number; // How confident the system is that this is a useful suggestion (0.0 to 1.0)
  // We could also add: estimatedTimeSavedPerInstance: number (in seconds/minutes)
  //                     frequencyOfPattern: number (how many times it was observed in a period)
}

/**
 * Input for the WorkflowAutomationSuggesterSkill.
 */
export interface WorkflowAutomationSuggesterSkillInput {
  userId: string;
  recentActions: UserAction[]; // A list of recent actions to analyze
  // Could also include: analysisTimeWindow: { startDate: Date, endDate: Date }
  //                     minPatternFrequency: number (to filter suggestions)
}

/**
 * Skill to observe repetitive user actions and suggest potential automations.
 */
export class WorkflowAutomationSuggesterSkill {
  constructor() {
    console.log("WorkflowAutomationSuggesterSkill initialized.");
    // In a real system, this might connect to an action logging service or a pattern mining engine.
  }

  /**
   * Analyzes recent user actions to find repetitive patterns and suggest automations.
   * @param input The input containing the userId and a list of recent actions.
   * @returns A Promise resolving to an array of AutomationSuggestion objects.
   */
  public async execute(input: WorkflowAutomationSuggesterSkillInput): Promise<AutomationSuggestion[]> {
    console.log(`[WorkflowAutomationSuggesterSkill] Received ${input.recentActions.length} actions for user: ${input.userId}`);

    const suggestions: AutomationSuggestion[] = [];

    // 1. Validate input (userId, recentActions) - Basic check
    if (!input.userId || !input.recentActions) {
      console.warn("[WorkflowAutomationSuggesterSkill] Missing userId or recentActions.");
      return [];
    }
    if (input.recentActions.length < 3) { // Need at least a few actions to find a pattern
        console.log("[WorkflowAutomationSuggesterSkill] Not enough actions to detect patterns meaningfully.");
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
    for (let i = 0; i < actions.length - 3; i++) { // Need at least 4 actions for this specific pattern
        const potentialPatternActions = actions.slice(i, i + 4);

        // Mock check for a specific hardcoded pattern: Copy from Spreadsheet, Create Email, Paste, Send.
        if (
            potentialPatternActions[0].application === 'SpreadsheetApp' && potentialPatternActions[0].actionType === 'COPY_CELL_RANGE' &&
            potentialPatternActions[1].application === 'EmailClient' && potentialPatternActions[1].actionType === 'CREATE_NEW_EMAIL' &&
            potentialPatternActions[2].application === 'EmailClient' && potentialPatternActions[2].actionType === 'PASTE_INTO_BODY' &&
            potentialPatternActions[3].application === 'EmailClient' && potentialPatternActions[3].actionType === 'SEND_EMAIL'
        ) {
            console.log(`[WorkflowAutomationSuggesterSkill] Mock pattern "Copy-Paste-Send Report" detected starting at action ID ${potentialPatternActions[0].id}`);

            // 4. If mock pattern is detected:
            //    a. Create a corresponding AutomationSuggestion object
            const suggestion: AutomationSuggestion = {
                id: `sugg-${Date.now()}-${Math.random().toString(36).substring(2,7)}`,
                title: "Automate Sending Copied Spreadsheet Data via Email",
                description: "Detected a pattern where you copy data from a spreadsheet, create a new email, paste the data, and send it. This could potentially be automated.",
                basedOnActionIds: potentialPatternActions.map(a => a.id),
                suggestedMacro: `
                  1. Get data from Spreadsheet (e.g., range specified in details: ${JSON.stringify(potentialPatternActions[0].details?.range || 'last copied range')}).
                  2. Create new Email.
                  3. (Optional) Set recipient (e.g., from details: ${JSON.stringify(potentialPatternActions[1].details?.to || 'common recipient')}).
                  4. (Optional) Set subject (e.g., "Data Report").
                  5. Paste/insert data into email body.
                  6. Send Email.
                `,
                userBenefit: "Could save a few minutes each time this task is performed.",
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
    } else {
        console.log("[WorkflowAutomationSuggesterSkill] No predefined mock patterns detected in the provided action sequence.");
    }
    return suggestions;
  }
}

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
