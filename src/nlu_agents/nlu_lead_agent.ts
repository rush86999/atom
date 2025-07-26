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

export class NLULeadAgent {
    private analyticalAgent: AnalyticalAgent;
    private creativeAgent: CreativeAgent;
    private practicalAgent: PracticalAgent;
    private synthesizingAgent: SynthesizingAgent;
    private dataAnalystSkill: DataAnalystSkill;
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
    }

    public async analyzeIntent(input: SubAgentInput): Promise<EnrichedIntent> {
        const P_LEAD_SUB_AGENTS_TIMER_LABEL = `[${this.agentName}] All Sub-Agents Processing Duration`;
        const P_LEAD_SYNTHESIS_TIMER_LABEL = `[${this.agentName}] Synthesis Duration`;

        console.time(P_LEAD_SUB_AGENTS_TIMER_LABEL);
        const [analyticalResponse, creativeResponse, practicalResponse] = await Promise.all([
            this.analyticalAgent.analyze(input).catch(e => { console.error("AnalyticalAgent failed:", e); return null; }),
            this.creativeAgent.analyze(input).catch(e => { console.error("CreativeAgent failed:", e); return null; }),
            this.practicalAgent.analyze(input).catch(e => { console.error("PracticalAgent failed:", e); return null; })
        ]);
        console.timeEnd(P_LEAD_SUB_AGENTS_TIMER_LABEL);

        if (analyticalResponse?.problemType === 'data_analysis') {
            const dataAnalystResult = await this.dataAnalystSkill.analyzeData(input.userInput);
            // You can decide how to incorporate the result of the data analyst skill.
            // For now, we'll just log it.
            console.log("Data Analyst Skill Result:", dataAnalystResult);
        }

        console.time(P_LEAD_SYNTHESIS_TIMER_LABEL);
        const synthesisResult = await this.synthesizingAgent.synthesize(input, analyticalResponse, creativeResponse, practicalResponse);
        console.timeEnd(P_LEAD_SYNTHESIS_TIMER_LABEL);

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
            },
            synthesisLog: synthesisResult.synthesisLog || ["Synthesis log not initialized."],
        };
    }
}

console.log("NLULeadAgent class loaded.");
