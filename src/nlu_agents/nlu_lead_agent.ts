import {
    SubAgentInput,
    AnalyticalAgentResponse,
    CreativeAgentResponse,
    PracticalAgentResponse,
    DataAnalystAgentResponse,
    EnrichedIntent
} from './nlu_types';
import { AnalyticalAgent } from './analytical_agent';
import { CreativeAgent } from './creative_agent';
import { PracticalAgent } from './practical_agent';
import { SynthesizingAgent } from './synthesizing_agent';
import { DataAnalystAgent } from './data_analyst_agent';

export class NLULeadAgent {
    private analyticalAgent: AnalyticalAgent;
    private creativeAgent: CreativeAgent;
    private practicalAgent: PracticalAgent;
    private synthesizingAgent: SynthesizingAgent;
    private dataAnalystAgent: DataAnalystAgent;
    private agentName: string = "NLULeadAgent";

    constructor(
        analyticalAgent: AnalyticalAgent,
        creativeAgent: CreativeAgent,
        practicalAgent: PracticalAgent,
        synthesizingAgent: SynthesizingAgent,
        dataAnalystAgent: DataAnalystAgent
    ) {
        this.analyticalAgent = analyticalAgent;
        this.creativeAgent = creativeAgent;
        this.practicalAgent = practicalAgent;
        this.synthesizingAgent = synthesizingAgent;
        this.dataAnalystAgent = dataAnalystAgent;
    }

    public async analyzeIntent(input: SubAgentInput): Promise<EnrichedIntent> {
        const P_LEAD_SUB_AGENTS_TIMER_LABEL = `[${this.agentName}] All Sub-Agents Processing Duration`;
        const P_LEAD_SYNTHESIS_TIMER_LABEL = `[${this.agentName}] Synthesis Duration`;

        console.time(P_LEAD_SUB_AGENTS_TIMER_LABEL);
        const [analyticalResponse, creativeResponse, practicalResponse, dataAnalystResponse] = await Promise.all([
            this.analyticalAgent.analyze(input).catch(e => { console.error("AnalyticalAgent failed:", e); return null; }),
            this.creativeAgent.analyze(input).catch(e => { console.error("CreativeAgent failed:", e); return null; }),
            this.practicalAgent.analyze(input).catch(e => { console.error("PracticalAgent failed:", e); return null; }),
            this.dataAnalystAgent.analyze(input).catch(e => { console.error("DataAnalystAgent failed:", e); return null; })
        ]);
        console.timeEnd(P_LEAD_SUB_AGENTS_TIMER_LABEL);

        console.time(P_LEAD_SYNTHESIS_TIMER_LABEL);
        const synthesisResult = await this.synthesizingAgent.synthesize(input, analyticalResponse, creativeResponse, practicalResponse, dataAnalystResponse);
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
                data_analyst: dataAnalystResponse,
            },
            synthesisLog: synthesisResult.synthesisLog || ["Synthesis log not initialized."],
        };
    }
}

console.log("NLULeadAgent class loaded.");
