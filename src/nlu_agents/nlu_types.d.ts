import { LLMServiceInterface, StructuredLLMPrompt } from '../lib/llmUtils';
export interface SubAgentInput {
    userInput: string;
    userId?: string;
}
export interface AnalyticalAgentResponse {
    identifiedEntities?: string[];
    explicitTasks?: string[];
    informationNeeded?: string[];
    logicalConsistency?: {
        isConsistent: boolean;
        reason?: string;
    };
    problemType?: string;
    rawLLMResponse?: string;
}
export interface CreativeAgentResponse {
    alternativeGoals?: string[];
    novelSolutionsSuggested?: string[];
    unstatedAssumptions?: string[];
    potentialEnhancements?: string[];
    ambiguityFlags?: {
        term: string;
        reason: string;
    }[];
    rawLLMResponse?: string;
}
export interface PracticalAgentResponse {
    contextualFactors?: string[];
    feasibilityAssessment?: {
        rating: 'High' | 'Medium' | 'Low' | 'Unknown';
        reason?: string;
        dependencies?: string[];
    };
    efficiencyTips?: string[];
    resourceImplications?: {
        timeEstimate?: string;
        toolsNeeded?: string[];
    };
    commonSenseValidation?: {
        isValid: boolean;
        reason?: string;
    };
    rawLLMResponse?: string;
}
export interface AdvancedResearchAgentResponse {
    researchSummary?: string;
    keyFindings?: string[];
    sources?: {
        title: string;
        url: string;
    }[];
    rawLLMResponse?: string;
}
export interface SocialMediaAgentResponse {
    scheduledPosts?: {
        platform: 'Twitter' | 'Facebook' | 'LinkedIn';
        content: string;
        scheduledTime: string;
    }[];
    engagementSummary?: string;
    rawLLMResponse?: string;
}
export interface ContentCreationAgentResponse {
    generatedContent?: string;
    contentType?: 'blog post' | 'article' | 'presentation' | 'code';
    rawLLMResponse?: string;
}
export interface PersonalizedShoppingAgentResponse {
    productRecommendations?: {
        productName: string;
        price: number;
        url: string;
        reasoning: string;
    }[];
    rawLLMResponse?: string;
}
export interface LegalDocumentAnalysisAgentResponse {
    riskAnalysis?: {
        clause: string;
        riskLevel: 'High' | 'Medium' | 'Low';
        explanation: string;
    }[];
    summary?: string;
    rawLLMResponse?: string;
}
export interface RecruitmentRecommendationAgentResponse {
    recommendedCandidates?: {
        name: string;
        resumeUrl: string;
        matchScore: number;
        summary: string;
    }[];
    rawLLMResponse?: string;
}
export interface VibeHackingAgentResponse {
    vulnerabilityReport?: {
        vulnerability: string;
        severity: 'Critical' | 'High' | 'Medium' | 'Low';
        description: string;
        remediation: string;
    }[];
    rawLLMResponse?: string;
}
export interface TaxAgentResponse {
    isTaxRelated: boolean;
    confidence: number;
    details: string;
}
export interface EnrichedIntent {
    originalQuery: string;
    userId?: string;
    primaryGoal?: string;
    primaryGoalConfidence?: number;
    extractedParameters?: Record<string, any>;
    identifiedTasks?: string[];
    suggestedNextAction?: {
        actionType: 'invoke_skill' | 'clarify_query' | 'perform_direct_action' | 'no_action_needed' | 'unable_to_determine';
        skillId?: string;
        clarificationQuestion?: string;
        directActionDetails?: any;
        reason?: string;
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
        socialMedia: SocialMediaAgentResponse | null;
        contentCreation: ContentCreationAgentResponse | null;
        personalizedShopping: PersonalizedShoppingAgentResponse | null;
        recruitmentRecommendation: RecruitmentRecommendationAgentResponse | null;
        vibeHacking: VibeHackingAgentResponse | null;
        tax: TaxAgentResponse | null;
    };
    synthesisLog?: string[];
}
export type AgentLLMService = LLMServiceInterface;
export type PromptConstructor = (input: SubAgentInput) => StructuredLLMPrompt;
export declare const DEFAULT_MODEL_FOR_AGENTS = "mixtral-8x7b-32768";
export declare const DEFAULT_MODEL_LEAD_SYNTHESIS = "mixtral-8x7b-32768";
export declare const DEFAULT_TEMPERATURE_ANALYTICAL = 0.2;
export declare const DEFAULT_TEMPERATURE_CREATIVE = 0.8;
export declare const DEFAULT_TEMPERATURE_PRACTICAL = 0.4;
export declare const DEFAULT_TEMPERATURE_LEAD_SYNTHESIS = 0.3;
export declare function safeParseJSON<T>(jsonString: string | undefined, agentName: string, task: string): T | null;
