import {
    SubAgentInput,
    AnalyticalAgentResponse,
    CreativeAgentResponse,
    PracticalAgentResponse,
    EnrichedIntent
} from './nlu_types';
import { AnalyticalAgent } from './analytical_agent';
import { CreativeAgent } from './creative_agent';
import { PracticalAgent } from './practical_agent';
import { SynthesizingAgent } from './synthesizing_agent';
import { TurnContext } from 'botbuilder';
import { AgentLLMService } from './nlu_types';
import { DataAnalystSkill } from '../skills/dataAnalystSkill';
import { AdvancedResearchSkill } from '../skills/researchSkillIndex';
import { LegalDocumentAnalysisSkill } from '../skills/legalSkillIndex';
import { SocialMediaAgent } from '../skills/socialMediaSkill';
import { ContentCreationAgent } from '../skills/contentCreationSkill';
import { PersonalizedShoppingAgent } from '../skills/personalizedShoppingSkill';
import { RecruitmentRecommendationAgent } from '../skills/recruitmentRecommendationSkill';
import { VibeHackingAgent } from '../skills/vibeHackingSkill';
import { TaxAgent } from './tax_agent';

export class NLULeadAgent {
    private analyticalAgent: AnalyticalAgent;
    private creativeAgent: CreativeAgent;
    private practicalAgent: PracticalAgent;
    private synthesizingAgent: SynthesizingAgent;
    private dataAnalystSkill: DataAnalystSkill;
    private advancedResearchSkill: AdvancedResearchSkill;
    private legalDocumentAnalysisSkill: LegalDocumentAnalysisSkill;
    private socialMediaAgent: SocialMediaAgent;
    private contentCreationAgent: ContentCreationAgent;
    private personalizedShoppingAgent: PersonalizedShoppingAgent;
    private recruitmentRecommendationAgent: RecruitmentRecommendationAgent;
    private vibeHackingAgent: VibeHackingAgent;
    private taxAgent: TaxAgent;
    private agentName: string = "NLULeadAgent";

    constructor(
        llmService: AgentLLMService,
        context: TurnContext,
        memory: any,
        functions: any
    ) {
        this.analyticalAgent = new AnalyticalAgent(llmService);
        this.creativeAgent = new CreativeAgent(llmService);
        this.practicalAgent = new PracticalAgent(llmService);
        this.synthesizingAgent = new SynthesizingAgent(llmService);
        this.dataAnalystSkill = new DataAnalystSkill(context, memory, functions);
        this.advancedResearchSkill = new AdvancedResearchSkill();
        this.legalDocumentAnalysisSkill = new LegalDocumentAnalysisSkill();
        this.socialMediaAgent = new SocialMediaAgent(llmService);
        this.contentCreationAgent = new ContentCreationAgent(llmService);
        this.personalizedShoppingAgent = new PersonalizedShoppingAgent(llmService);
        this.recruitmentRecommendationAgent = new RecruitmentRecommendationAgent(llmService);
        this.vibeHackingAgent = new VibeHackingAgent(llmService);
        this.taxAgent = new TaxAgent(llmService);
    }

    public async analyzeIntent(input: SubAgentInput): Promise<EnrichedIntent> {
        const P_LEAD_SUB_AGENTS_TIMER_LABEL = `[${this.agentName}] All Sub-Agents Processing Duration`;
        const P_LEAD_SYNTHESIS_TIMER_LABEL = `[${this.agentName}] Synthesis Duration`;

        console.time(P_LEAD_SUB_AGENTS_TIMER_LABEL);
        const [
            analyticalResponse,
            creativeResponse,
            practicalResponse,
            socialMediaResponse,
            contentCreationResponse,
            personalizedShoppingResponse,
            recruitmentRecommendationResponse,
            vibeHackingResponse,
            taxResponse
        ] = await Promise.all([
            this.analyticalAgent.analyze(input).catch(e => { console.error("AnalyticalAgent failed:", e); return null; }),
            this.creativeAgent.analyze(input).catch(e => { console.error("CreativeAgent failed:", e); return null; }),
            this.practicalAgent.analyze(input).catch(e => { console.error("PracticalAgent failed:", e); return null; }),
            this.socialMediaAgent.analyze(input).catch(e => { console.error("SocialMediaAgent failed:", e); return null; }),
            this.contentCreationAgent.analyze(input).catch(e => { console.error("ContentCreationAgent failed:", e); return null; }),
            this.personalizedShoppingAgent.analyze(input).catch(e => { console.error("PersonalizedShoppingAgent failed:", e); return null; }),
            this.recruitmentRecommendationAgent.analyze(input).catch(e => { console.error("RecruitmentRecommendationAgent failed:", e); return null; }),
            this.vibeHackingAgent.analyze(input).catch(e => { console.error("VibeHackingAgent failed:", e); return null; }),
            this.taxAgent.analyze(input).catch(e => { console.error("TaxAgent failed:", e); return null; })
        ]);
        console.timeEnd(P_LEAD_SUB_AGENTS_TIMER_LABEL);

        if (analyticalResponse?.problemType === 'data_analysis') {
            const dataAnalystResult = await this.dataAnalystSkill.analyzeData(input.userInput);
            // You can decide how to incorporate the result of the data analyst skill.
            // For now, we'll just log it.
            console.log("Data Analyst Skill Result:", dataAnalystResult);
        }

        console.time(P_LEAD_SYNTHESIS_TIMER_LABEL);
        const synthesisResult = await this.synthesizingAgent.synthesize(input, analyticalResponse, creativeResponse, practicalResponse, socialMediaResponse, contentCreationResponse, personalizedShoppingResponse, recruitmentRecommendationResponse, vibeHackingResponse, taxResponse);
        console.timeEnd(P_LEAD_SYNTHESIS_TIMER_LABEL);

        if (synthesisResult.suggestedNextAction?.actionType === 'invoke_skill') {
            const skillId = synthesisResult.suggestedNextAction.skillId;
            if (skillId === 'advancedResearch') {
                // @ts-ignore
                const researchResult = await this.advancedResearchSkill.handler(synthesisResult.extractedParameters);
                console.log("Advanced Research Skill Result:", researchResult);
            } else if (skillId === 'legalDocumentAnalysis') {
                // @ts-ignore
                const legalResult = await this.legalDocumentAnalysisSkill.handler(synthesisResult.extractedParameters);
                console.log("Legal Document Analysis Skill Result:", legalResult);
            }
            // Add similar blocks for other skills
        }

        return {
            originalQuery: input.userInput,
            userId: input.userId,
            primaryGoal: synthesisResult.primaryGoal,
            primaryGoalConfidence: synthesisResult.primaryGoalConfidence,
            extractedParameters: synthesisResult.extractedParameters,
            identifiedTasks: synthesisResult.identifiedTasks,
            suggestedNextAction: synthesisResult.suggestedNextAction,
            alternativeInterpretations: creativeResponse?.alternativeGoals,
            potentialAmbiguities: creativeResponse?.ambiguityFlags,
            practicalConsiderations: {
                feasibility: practicalResponse?.feasibilityAssessment,
                efficiencyTips: practicalResponse?.efficiencyTips,
            },
            rawSubAgentResponses: {
                analytical: analyticalResponse,
                creative: creativeResponse,
                practical: practicalResponse,
                socialMedia: socialMediaResponse,
                contentCreation: contentCreationResponse,
                personalizedShopping: personalizedShoppingResponse,
                recruitmentRecommendation: recruitmentRecommendationResponse,
                vibeHacking: vibeHackingResponse,
                tax: taxResponse,
            },
            synthesisLog: synthesisResult.synthesisLog || ["Synthesis log not initialized."],
        };
    }
}

console.log("NLULeadAgent class loaded.");
