import { LLMServiceInterface, StructuredLLMPrompt } from '../lib/llmUtils'; // Assuming llmUtils is accessible

export interface SubAgentInput {
    userInput: string;
    userId?: string; // Optional, but can be useful for context
    // Potentially add other contextual information here, like:
    // currentApplication?: string;
    // recentDocuments?: { title: string, id: string }[];
    // userProfile?: { role: string, expertise?: string[] };
}

// --- Analytical Agent ---
export interface AnalyticalAgentResponse {
    identifiedEntities?: string[];
    explicitTasks?: string[];
    informationNeeded?: string[];
    logicalConsistency?: {
        isConsistent: boolean;
        reason?: string;
    };
    problemType?: string; // e.g., "information_retrieval", "task_execution", "comparison", "problem_solving", "advanced_research", "social_media_management", "content_creation", "personalized_shopping", "legal_document_analysis", "recruitment_recommendation", "vibe_hacking"
    rawLLMResponse?: string; // For debugging
}

// --- Creative Agent ---
export interface CreativeAgentResponse {
    alternativeGoals?: string[];
    novelSolutionsSuggested?: string[];
    unstatedAssumptions?: string[];
    potentialEnhancements?: string[];
    ambiguityFlags?: {
        term: string;
        reason: string;
    }[];
    rawLLMResponse?: string; // For debugging
}

// --- Practical Agent ---
export interface PracticalAgentResponse {
    contextualFactors?: string[]; // e.g., "User is in 'Project Alpha' context"
    feasibilityAssessment?: {
        rating: 'High' | 'Medium' | 'Low' | 'Unknown';
        reason?: string;
        dependencies?: string[]; // e.g., "Requires access to Database X"
    };
    efficiencyTips?: string[];
    resourceImplications?: {
        timeEstimate?: string; // e.g., "Quick", "Moderate", "Significant"
        toolsNeeded?: string[];
    };
    commonSenseValidation?: {
        isValid: boolean;
        reason?: string; // If not valid, why?
    };
    rawLLMResponse?: string; // For debugging
}

// --- NLU Lead Agent Output ---
export interface EnrichedIntent {
    originalQuery: string;
    userId?: string;
    primaryGoal?: string; // e.g., "retrieve_budget_info_for_q3_marketing"
    primaryGoalConfidence?: number; // 0.0 to 1.0
    extractedParameters?: Record<string, any>; // e.g., { "quarter": "Q3", "department": "marketing" }
    identifiedTasks?: string[]; // From Analytical Agent primarily
    suggestedNextAction?: {
        actionType: 'invoke_skill' | 'clarify_query' | 'perform_direct_action' | 'no_action_needed' | 'unable_to_determine';
        skillId?: string; // if actionType is 'invoke_skill'
        clarificationQuestion?: string; // if actionType is 'clarify_query'
        directActionDetails?: any; // if actionType is 'perform_direct_action'
        reason?: string; // Why this action is suggested
    };
    alternativeInterpretations?: CreativeAgentResponse['alternativeGoals'];
    potentialAmbiguities?: CreativeAgentResponse['ambiguityFlags'];
    practicalConsiderations?: {
        feasibility?: PracticalAgentResponse['feasibilityAssessment'];
        efficiencyTips?: PracticalAgentResponse['efficiencyTips'];
    };
    rawSubAgentResponses: {
        analytical: AnalyticalAgentResponse | null;
        creative: CreativeAgentResponse | null;
        practical: PracticalAgentResponse | null;
    };
    synthesisLog?: string[]; // Log of how synthesis was performed
}


// Interface for the LLM service each agent will use
// This can be the existing LLMServiceInterface or a more specific one if needed
export type AgentLLMService = LLMServiceInterface;

// A helper function type for constructing prompts, if we want to centralize this logic later
export type PromptConstructor = (input: SubAgentInput) => StructuredLLMPrompt;

export const DEFAULT_MODEL_FOR_AGENTS = "mixtral-8x7b-32768"; // Or any other preferred model
export const DEFAULT_MODEL_LEAD_SYNTHESIS = "mixtral-8x7b-32768"; // Could be a more powerful model
export const DEFAULT_TEMPERATURE_ANALYTICAL = 0.2;
export const DEFAULT_TEMPERATURE_CREATIVE = 0.8;
export const DEFAULT_TEMPERATURE_PRACTICAL = 0.4;
export const DEFAULT_TEMPERATURE_LEAD_SYNTHESIS = 0.3;


// Helper to safely parse JSON from LLM
export function safeParseJSON<T>(jsonString: string | undefined, agentName: string, task: string): T | null {
    if (!jsonString) {
        console.warn(`[${agentName}] LLM response for task '${task}' was empty.`);
        return null;
    }
    try {
        return JSON.parse(jsonString) as T;
    } catch (error) {
        console.error(`[${agentName}] Failed to parse JSON response for task '${task}'. Error: ${error}. Response: ${jsonString.substring(0, 200)}...`);
        return null;
    }
}
