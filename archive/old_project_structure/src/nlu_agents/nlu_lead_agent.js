"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.NLULeadAgent = void 0;
const analytical_agent_1 = require("./analytical_agent");
const creative_agent_1 = require("./creative_agent");
const practical_agent_1 = require("./practical_agent");
const synthesizing_agent_1 = require("./synthesizing_agent");
const dataAnalystSkill_1 = require("../skills/dataAnalystSkill");
const researchSkillIndex_1 = require("../skills/researchSkillIndex");
const legalSkillIndex_1 = require("../skills/legalSkillIndex");
const contentCreationSkill_1 = require("../skills/contentCreationSkill");
const personalizedShoppingSkill_1 = require("../skills/personalizedShoppingSkill");
const recruitmentRecommendationSkill_1 = require("../skills/recruitmentRecommendationSkill");
const vibeHackingSkill_1 = require("../skills/vibeHackingSkill");
const tax_agent_1 = require("./tax_agent");
const marketingAutomationSkill_1 = require("../skills/marketingAutomationSkill");
const workflow_agent_1 = require("./workflow_agent");
const workflow_generator_1 = require("./workflow_generator");
const devOpsOrchestrator_1 = require("../orchestration/devOpsOrchestrator");
const autonomousSystemOrchestrator_1 = require("../orchestration/autonomousSystemOrchestrator");
const socialMediaAgent_1 = require("./socialMediaAgent");
const trading_agent_1 = require("./trading_agent");
class NLULeadAgent {
    constructor(llmService, context, memory, functions) {
        this.agentName = "NLULeadAgent";
        this.analyticalAgent = new analytical_agent_1.AnalyticalAgent(llmService);
        this.creativeAgent = new creative_agent_1.CreativeAgent(llmService);
        this.practicalAgent = new practical_agent_1.PracticalAgent(llmService);
        this.synthesizingAgent = new synthesizing_agent_1.SynthesizingAgent(llmService);
        this.dataAnalystSkill = new dataAnalystSkill_1.DataAnalystSkill(context, memory, functions);
        this.advancedResearchSkill = new researchSkillIndex_1.AdvancedResearchSkill();
        this.legalDocumentAnalysisSkill = new legalSkillIndex_1.LegalDocumentAnalysisSkill();
        this.socialMediaAgent = new socialMediaAgent_1.SocialMediaAgent(llmService);
        this.contentCreationAgent = new contentCreationSkill_1.ContentCreationAgent(llmService);
        this.personalizedShoppingAgent = new personalizedShoppingSkill_1.PersonalizedShoppingAgent(llmService);
        this.recruitmentRecommendationAgent = new recruitmentRecommendationSkill_1.RecruitmentRecommendationAgent(llmService);
        this.vibeHackingAgent = new vibeHackingSkill_1.VibeHackingAgent(llmService);
        this.taxAgent = new tax_agent_1.TaxAgent(llmService);
        this.marketingAutomationAgent = new marketingAutomationSkill_1.MarketingAutomationAgent(llmService);
        this.workflowAgent = new workflow_agent_1.WorkflowAgent(llmService);
        this.workflowGenerator = new workflow_generator_1.WorkflowGenerator();
        this.tradingAgent = new trading_agent_1.AutonomousTradingAgent(llmService);
    }
    async analyzeIntent(input) {
        const P_LEAD_SUB_AGENTS_TIMER_LABEL = `[${this.agentName}] All Sub-Agents Processing Duration`;
        const P_LEAD_SYNTHESIS_TIMER_LABEL = `[${this.agentName}] Synthesis Duration`;
        console.time(P_LEAD_SUB_AGENTS_TIMER_LABEL);
        const [analyticalResponse, creativeResponse, practicalResponse, contentCreationResponse, personalizedShoppingResponse, recruitmentRecommendationResponse, vibeHackingResponse, taxResponse, marketingAutomationResponse, workflowResponse, tradingResponse,] = await Promise.all([
            this.analyticalAgent.analyze(input).catch((e) => {
                console.error("AnalyticalAgent failed:", e);
                return null;
            }),
            this.creativeAgent.analyze(input).catch((e) => {
                console.error("CreativeAgent failed:", e);
                return null;
            }),
            this.practicalAgent.analyze(input).catch((e) => {
                console.error("PracticalAgent failed:", e);
                return null;
            }),
            this.contentCreationAgent.analyze(input).catch((e) => {
                console.error("ContentCreationAgent failed:", e);
                return null;
            }),
            this.personalizedShoppingAgent.analyze(input).catch((e) => {
                console.error("PersonalizedShoppingAgent failed:", e);
                return null;
            }),
            this.recruitmentRecommendationAgent.analyze(input).catch((e) => {
                console.error("RecruitmentRecommendationAgent failed:", e);
                return null;
            }),
            this.vibeHackingAgent.analyze(input).catch((e) => {
                console.error("VibeHackingAgent failed:", e);
                return null;
            }),
            this.taxAgent.analyze(input).catch((e) => {
                console.error("TaxAgent failed:", e);
                return null;
            }),
            this.marketingAutomationAgent.analyze(input).catch((e) => {
                console.error("MarketingAutomationAgent failed:", e);
                return null;
            }),
            this.workflowAgent.analyze(input).catch((e) => {
                console.error("WorkflowAgent failed:", e);
                return null;
            }),
            this.tradingAgent.analyze(input).catch((e) => {
                console.error("TradingAgent failed:", e);
                return null;
            }),
            this.socialMediaAgent.analyzeAndAct(input).catch((e) => {
                console.error("SocialMediaAgent failed:", e);
                return null;
            }),
        ]);
        console.timeEnd(P_LEAD_SUB_AGENTS_TIMER_LABEL);
        const synthesisResult = await this.synthesizingAgent.synthesize(input, analyticalResponse, creativeResponse, practicalResponse, contentCreationResponse, personalizedShoppingResponse, recruitmentRecommendationResponse, vibeHackingResponse, taxResponse, marketingAutomationResponse, workflowResponse, tradingResponse);
        if (synthesisResult.suggestedNextAction?.actionType === "create_workflow") {
            const workflowDefinition = this.workflowGenerator.generate(synthesisResult);
            if (workflowDefinition) {
                await this.saveWorkflow(synthesisResult.primaryGoal, workflowDefinition);
                // We could potentially modify the enriched intent here to indicate success.
                synthesisResult.synthesisLog?.push("Successfully generated and saved the new workflow.");
            }
            else {
                synthesisResult.synthesisLog?.push("Failed to generate the workflow definition.");
            }
        }
        else if (synthesisResult.suggestedNextAction?.actionType === "invoke_skill") {
            const skillId = synthesisResult.suggestedNextAction.skillId;
            if (skillId === "advancedResearch") {
                // @ts-ignore
                const researchResult = await this.advancedResearchSkill.handler(synthesisResult.extractedParameters);
                console.log("Advanced Research Skill Result:", researchResult);
            }
            else if (skillId === "legalDocumentAnalysis") {
                // @ts-ignore
                const legalResult = await this.legalDocumentAnalysisSkill.handler(synthesisResult.extractedParameters);
                console.log("Legal Document Analysis Skill Result:", legalResult);
            }
            // Add similar blocks for other skills
        }
        if (synthesisResult.primaryGoal?.includes("create a web app") ||
            synthesisResult.primaryGoal?.includes("create a new project")) {
            const { owner, repo, jiraProjectKey, slackChannelId } = synthesisResult.extractedParameters;
            if (owner && repo && jiraProjectKey && slackChannelId) {
                console.log("Triggering autonomous web app flow...");
                const flowResult = await (0, devOpsOrchestrator_1.runAutonomousWebAppFlow)(input.userId, owner, repo, jiraProjectKey, slackChannelId);
                synthesisResult.synthesisLog?.push(`Autonomous web app flow triggered. Result: ${flowResult.message}`);
            }
        }
        if (synthesisResult.primaryGoal?.toLowerCase().includes("run shopify report")) {
            const { slackChannelId } = synthesisResult.extractedParameters;
            if (slackChannelId) {
                console.log("Triggering Shopify report flow...");
                const flowResult = await (0, autonomousSystemOrchestrator_1.runShopifyReport)(input.userId, slackChannelId);
                synthesisResult.synthesisLog?.push(`Shopify report flow triggered. Result: ${flowResult.message}`);
            }
            else {
                synthesisResult.synthesisLog?.push(`Missing slackChannelId to run Shopify report.`);
            }
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
                contentCreation: contentCreationResponse,
                personalizedShopping: personalizedShoppingResponse,
                recruitmentRecommendation: recruitmentRecommendationResponse,
                vibeHacking: vibeHackingResponse,
                tax: taxResponse,
                marketingAutomation: marketingAutomationResponse,
                workflow: workflowResponse,
                trading: tradingResponse,
            },
            synthesisLog: synthesisResult.synthesisLog || [
                "Synthesis log not initialized.",
            ],
        };
    }
    async saveWorkflow(name, definition) {
        const workflow = {
            name,
            definition,
            enabled: true,
        };
        try {
            // Assuming fetch is available in the environment.
            // In a real scenario, this URL should come from a config.
            const response = await fetch("http://localhost:8003/workflows/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(workflow),
            });
            if (!response.ok) {
                console.error("Failed to save workflow:", response.statusText);
            }
            else {
                console.log("Workflow saved successfully");
            }
        }
        catch (error) {
            console.error("Error saving workflow:", error);
        }
    }
}
exports.NLULeadAgent = NLULeadAgent;
console.log("NLULeadAgent class loaded.");
//# sourceMappingURL=nlu_lead_agent.js.map