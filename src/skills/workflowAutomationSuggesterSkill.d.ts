/**
 * Represents a single observed user action.
 */
export interface UserAction {
    id: string;
    timestamp: Date;
    userId: string;
    application: string;
    actionType: string;
    details?: Record<string, any>;
}
/**
 * Represents a suggestion for automating a detected repetitive workflow.
 */
export interface AutomationSuggestion {
    id: string;
    title: string;
    description: string;
    basedOnActionIds: string[];
    suggestedMacro?: string;
    userBenefit?: string;
    confidence?: number;
}
/**
 * Input for the WorkflowAutomationSuggesterSkill.
 */
export interface WorkflowAutomationSuggesterSkillInput {
    userId: string;
    recentActions: UserAction[];
}
/**
 * Skill to observe repetitive user actions and suggest potential automations.
 */
export declare class WorkflowAutomationSuggesterSkill {
    constructor();
    /**
     * Analyzes recent user actions to find repetitive patterns and suggest automations.
     * @param input The input containing the userId and a list of recent actions.
     * @returns A Promise resolving to an array of AutomationSuggestion objects.
     */
    execute(input: WorkflowAutomationSuggesterSkillInput): Promise<AutomationSuggestion[]>;
}
