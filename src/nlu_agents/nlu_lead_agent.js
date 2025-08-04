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
const socialMediaSkill_1 = require("../skills/socialMediaSkill");
const contentCreationSkill_1 = require("../skills/contentCreationSkill");
const personalizedShoppingSkill_1 = require("../skills/personalizedShoppingSkill");
const recruitmentRecommendationSkill_1 = require("../skills/recruitmentRecommendationSkill");
const vibeHackingSkill_1 = require("../skills/vibeHackingSkill");
const tax_agent_1 = require("./tax_agent");
const marketingAutomationSkill_1 = require("../skills/marketingAutomationSkill");
class NLULeadAgent {
    analyticalAgent;
    creativeAgent;
    practicalAgent;
    synthesizingAgent;
    dataAnalystSkill;
    advancedResearchSkill;
    legalDocumentAnalysisSkill;
    socialMediaAgent;
    contentCreationAgent;
    personalizedShoppingAgent;
    recruitmentRecommendationAgent;
    vibeHackingAgent;
    taxAgent;
    marketingAutomationAgent;
    agentName = 'NLULeadAgent';
    constructor(llmService, context, memory, functions) {
        this.analyticalAgent = new analytical_agent_1.AnalyticalAgent(llmService);
        this.creativeAgent = new creative_agent_1.CreativeAgent(llmService);
        this.practicalAgent = new practical_agent_1.PracticalAgent(llmService);
        this.synthesizingAgent = new synthesizing_agent_1.SynthesizingAgent(llmService);
        this.dataAnalystSkill = new dataAnalystSkill_1.DataAnalystSkill(context, memory, functions);
        this.advancedResearchSkill = new researchSkillIndex_1.AdvancedResearchSkill();
        this.legalDocumentAnalysisSkill = new legalSkillIndex_1.LegalDocumentAnalysisSkill();
        this.socialMediaAgent = new socialMediaSkill_1.SocialMediaAgent(llmService);
        this.contentCreationAgent = new contentCreationSkill_1.ContentCreationAgent(llmService);
        this.personalizedShoppingAgent = new personalizedShoppingSkill_1.PersonalizedShoppingAgent(llmService);
        this.recruitmentRecommendationAgent = new recruitmentRecommendationSkill_1.RecruitmentRecommendationAgent(llmService);
        this.vibeHackingAgent = new vibeHackingSkill_1.VibeHackingAgent(llmService);
        this.taxAgent = new tax_agent_1.TaxAgent(llmService);
        this.marketingAutomationAgent = new marketingAutomationSkill_1.MarketingAutomationAgent(llmService);
    }
    async analyzeIntent(input) {
        const P_LEAD_SUB_AGENTS_TIMER_LABEL = `[${this.agentName}] All Sub-Agents Processing Duration`;
        const P_LEAD_SYNTHESIS_TIMER_LABEL = `[${this.agentName}] Synthesis Duration`;
        console.time(P_LEAD_SUB_AGENTS_TIMER_LABEL);
        const [analyticalResponse, creativeResponse, practicalResponse, socialMediaResponse, contentCreationResponse, personalizedShoppingResponse, recruitmentRecommendationResponse, vibeHackingResponse, taxResponse, marketingAutomationResponse,] = await Promise.all([
            this.analyticalAgent.analyze(input).catch((e) => {
                console.error('AnalyticalAgent failed:', e);
                return null;
            }),
            this.creativeAgent.analyze(input).catch((e) => {
                console.error('CreativeAgent failed:', e);
                return null;
            }),
            this.practicalAgent.analyze(input).catch((e) => {
                console.error('PracticalAgent failed:', e);
                return null;
            }),
            this.socialMediaAgent.analyze(input).catch((e) => {
                console.error('SocialMediaAgent failed:', e);
                return null;
            }),
            this.contentCreationAgent.analyze(input).catch((e) => {
                console.error('ContentCreationAgent failed:', e);
                return null;
            }),
            this.personalizedShoppingAgent.analyze(input).catch((e) => {
                console.error('PersonalizedShoppingAgent failed:', e);
                return null;
            }),
            this.recruitmentRecommendationAgent.analyze(input).catch((e) => {
                console.error('RecruitmentRecommendationAgent failed:', e);
                return null;
            }),
            this.vibeHackingAgent.analyze(input).catch((e) => {
                console.error('VibeHackingAgent failed:', e);
                return null;
            }),
            this.taxAgent.analyze(input).catch((e) => {
                console.error('TaxAgent failed:', e);
                return null;
            }),
            this.marketingAutomationAgent.analyze(input).catch((e) => {
                console.error('MarketingAutomationAgent failed:', e);
                return null;
            }),
        ]);
        console.timeEnd(P_LEAD_SUB_AGENTS_TIMER_LABEL);
        if (analyticalResponse?.problemType === 'data_analysis') {
            const dataAnalystResult = await this.dataAnalystSkill.analyzeData(input.userInput);
            // You can decide how to incorporate the result of the data analyst skill.
            // For now, we'll just log it.
            console.log('Data Analyst Skill Result:', dataAnalystResult);
        }
        console.time(P_LEAD_SYNTHESIS_TIMER_LABEL);
        const synthesisResult = await this.synthesizingAgent.synthesize(input, analyticalResponse, creativeResponse, practicalResponse, socialMediaResponse, contentCreationResponse, personalizedShoppingResponse, recruitmentRecommendationResponse, vibeHackingResponse, taxResponse, marketingAutomationResponse);
        console.timeEnd(P_LEAD_SYNTHESIS_TIMER_LABEL);
        if (synthesisResult.suggestedNextAction?.actionType === 'invoke_skill') {
            const skillId = synthesisResult.suggestedNextAction.skillId;
            if (skillId === 'advancedResearch') {
                // @ts-ignore
                const researchResult = await this.advancedResearchSkill.handler(synthesisResult.extractedParameters);
                console.log('Advanced Research Skill Result:', researchResult);
            }
            else if (skillId === 'legalDocumentAnalysis') {
                // @ts-ignore
                const legalResult = await this.legalDocumentAnalysisSkill.handler(synthesisResult.extractedParameters);
                console.log('Legal Document Analysis Skill Result:', legalResult);
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
                marketingAutomation: marketingAutomationResponse,
            },
            synthesisLog: synthesisResult.synthesisLog || [
                'Synthesis log not initialized.',
            ],
        };
    }
}
exports.NLULeadAgent = NLULeadAgent;
console.log('NLULeadAgent class loaded.');
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibmx1X2xlYWRfYWdlbnQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJubHVfbGVhZF9hZ2VudC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7QUFPQSx5REFBcUQ7QUFDckQscURBQWlEO0FBQ2pELHVEQUFtRDtBQUNuRCw2REFBeUQ7QUFHekQsaUVBQThEO0FBQzlELHFFQUFxRTtBQUNyRSwrREFBdUU7QUFDdkUsaUVBQThEO0FBQzlELHlFQUFzRTtBQUN0RSxtRkFBZ0Y7QUFDaEYsNkZBQTBGO0FBQzFGLGlFQUE4RDtBQUM5RCwyQ0FBdUM7QUFDdkMsaUZBQThFO0FBRTlFLE1BQWEsWUFBWTtJQUNmLGVBQWUsQ0FBa0I7SUFDakMsYUFBYSxDQUFnQjtJQUM3QixjQUFjLENBQWlCO0lBQy9CLGlCQUFpQixDQUFvQjtJQUNyQyxnQkFBZ0IsQ0FBbUI7SUFDbkMscUJBQXFCLENBQXdCO0lBQzdDLDBCQUEwQixDQUE2QjtJQUN2RCxnQkFBZ0IsQ0FBbUI7SUFDbkMsb0JBQW9CLENBQXVCO0lBQzNDLHlCQUF5QixDQUE0QjtJQUNyRCw4QkFBOEIsQ0FBaUM7SUFDL0QsZ0JBQWdCLENBQW1CO0lBQ25DLFFBQVEsQ0FBVztJQUNuQix3QkFBd0IsQ0FBMkI7SUFDbkQsU0FBUyxHQUFXLGNBQWMsQ0FBQztJQUUzQyxZQUNFLFVBQTJCLEVBQzNCLE9BQW9CLEVBQ3BCLE1BQVcsRUFDWCxTQUFjO1FBRWQsSUFBSSxDQUFDLGVBQWUsR0FBRyxJQUFJLGtDQUFlLENBQUMsVUFBVSxDQUFDLENBQUM7UUFDdkQsSUFBSSxDQUFDLGFBQWEsR0FBRyxJQUFJLDhCQUFhLENBQUMsVUFBVSxDQUFDLENBQUM7UUFDbkQsSUFBSSxDQUFDLGNBQWMsR0FBRyxJQUFJLGdDQUFjLENBQUMsVUFBVSxDQUFDLENBQUM7UUFDckQsSUFBSSxDQUFDLGlCQUFpQixHQUFHLElBQUksc0NBQWlCLENBQUMsVUFBVSxDQUFDLENBQUM7UUFDM0QsSUFBSSxDQUFDLGdCQUFnQixHQUFH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O0lBQ0osQ0FBQztDQUNGO0FBL0tELG9DQStLQztBQUVELE9BQU8sQ0FBQyxHQUFHLENBQUMsNEJBQTRCLENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7XG4gIFN1YkFnZW50SW5wdXQsXG4gIEFuYWx5dGljYWxBZ2VudFJlc3BvbnNlLFxuICBDcmVhdGl2ZUFnZW50UmVzcG9uc2UsXG4gIFByYWN0aWNhbEFnZW50UmVzcG9uc2UsXG4gIEVucmljaGVkSW50ZW50LFxufSBmcm9tICcuL25sdV90eXBlcyc7XG5pbXBvcnQgeyBBbmFseXRpY2FsQWdlbnQgfSBmcm9tICcuL2FuYWx5dGljYWxfYWdlbnQnO1xuaW1wb3J0IHsgQ3JlYXRpdmVBZ2VudCB9IGZyb20gJy4vY3JlYXRpdmVfYWdlbnQnO1xuaW1wb3J0IHsgUHJhY3RpY2FsQWdlbnQgfSBmcm9tICcuL3ByYWN0aWNhbF9hZ2VudCc7XG5pbXBvcnQgeyBTeW50aGVzaXppbmdBZ2VudCB9IGZyb20gJy4vc3ludGhlc2l6aW5nX2FnZW50JztcbmltcG9ydCB7IFR1cm5Db250ZXh0IH0gZnJvbSAnYm90YnVpbGRlcic7XG5pbXBvcnQgeyBBZ2VudExMTVNlcnZpY2UgfSBmcm9tICcuL25sdV90eXBlcyc7XG5pbXBvcnQgeyBEYXRhQW5hbHlzdFNraWxsIH0gZnJvbSAnLi4vc2tpbGxzL2RhdGFBbmFseXN0U2tpbGwnO1xuaW1wb3J0IHsgQWR2YW5jZWRSZXNlYXJjaFNraWxsIH0gZnJvbSAnLi4vc2tpbGxzL3Jlc2VhcmNoU2tpbGxJbmRleCc7XG5pbXBvcnQgeyBMZWdhbERvY3VtZW50QW5hbHlzaXNTa2lsbCB9IGZyb20gJy4uL3NraWxscy9sZWdhbFNraWxsSW5kZXgnO1xuaW1wb3J0IHsgU29jaWFsTWVkaWFBZ2VudCB9IGZyb20gJy4uL3NraWxscy9zb2NpYWxNZWRpYVNraWxsJztcbmltcG9ydCB7IENvbnRlbnRDcmVhdGlvbkFnZW50IH0gZnJvbSAnLi4vc2tpbGxzL2NvbnRlbnRDcmVhdGlvblNraWxsJztcbmltcG9ydCB7IFBlcnNvbmFsaXplZFNob3BwaW5nQWdlbnQgfSBmcm9tICcuLi9za2lsbHMvcGVyc29uYWxpemVkU2hvcHBpbmdTa2lsbCc7XG5pbXBvcnQgeyBSZWNydWl0bWVudFJlY29tbWVuZGF0aW9uQWdlbnQgfSBmcm9tICcuLi9za2lsbHMvcmVjcnVpdG1lbnRSZWNvbW1lbmRhdGlvblNraWxsJztcbmltcG9ydCB7IFZpYmVIYWNraW5nQWdlbnQgfSBmcm9tICcuLi9za2lsbHMvdmliZUhhY2tpbmdTa2lsbCc7XG5pbXBvcnQgeyBUYXhBZ2VudCB9IGZyb20gJy4vdGF4X2FnZW50JztcbmltcG9ydCB7IE1hcmtldGluZ0F1dG9tYXRpb25BZ2VudCB9IGZyb20gJy4uL3NraWxscy9tYXJrZXRpbmdBdXRvbWF0aW9uU2tpbGwnO1xuXG5leHBvcnQgY2xhc3MgTkxVTGVhZEFnZW50IHtcbiAgcHJpdmF0ZSBhbmFseXRpY2FsQWdlbnQ6IEFuYWx5dGljYWxBZ2VudDtcbiAgcHJpdmF0ZSBjcmVhdGl2ZUFnZW50OiBDcmVhdGl2ZUFnZW50O1xuICBwcml2YXRlIHByYWN0aWNhbEFnZW50OiBQcmFjdGljYWxBZ2VudDtcbiAgcHJpdmF0ZSBzeW50aGVzaXppbmdBZ2VudDogU3ludGhlc2l6aW5nQWdlbnQ7XG4gIHByaXZhdGUgZGF0YUFuYWx5c3RTa2lsbDogRGF0YUFuYWx5c3RTa2lsbDtcbiAgcHJpdmF0ZSBhZHZhbmNlZFJlc2VhcmNoU2tpbGw6IEFkdmFuY2VkUmVzZWFyY2hTa2lsbDtcbiAgcHJpdmF0ZSBsZWdhbERvY3VtZW50QW5hbHlzaXNTa2lsbDogTGVnYWxEb2N1bWVudEFuYWx5c2lzU2tpbGw7XG4gIHByaXZhdGUgc29jaWFsTWVkaWFBZ2VudDogU29jaWFsTWVkaWFBZ2VudDtcbiAgcHJpdmF0ZSBjb250ZW50Q3JlYXRpb25BZ2VudDogQ29udGVudENyZWF0aW9uQWdlbnQ7XG4gIHByaXZhdGUgcGVyc29uYWxpemVkU2hvcHBpbmdBZ2VudDogUGVyc29uYWxpemVkU2hvcHBpbmdBZ2VudDtcbiAgcHJpdmF0ZSByZWNydWl0bWVudFJlY29tbWVuZGF0aW9uQWdlbnQ6IFJlY3J1aXRtZW50UmVjb21tZW5kYXRpb25BZ2VudDtcbiAgcHJpdmF0ZSB2aWJlSGFja2luZ0FnZW50OiBWaWJlSGFja2luZ0FnZW50O1xuICBwcml2YXRlIHRheEFnZW50OiBUYXhBZ2VudDtcbiAgcHJpdmF0ZSBtYXJrZXRpbmdBdXRvbWF0aW9uQWdlbnQ6IE1hcmtldGluZ0F1dG9tYXRpb25BZ2VudDtcbiAgcHJpdmF0ZSBhZ2VudE5hbWU6IHN0cmluZyA9ICdOTFVMZWFkQWdlbnQnO1xuXG4gIGNvbnN0cnVjdG9yKFxuICAgIGxsbVNlcnZpY2U6IEFnZW50TExNU2VydmljZSxcbiAgICBjb250ZXh0OiBUdXJuQ29udGV4dCxcbiAgICBtZW1vcnk6IGFueSxcbiAgICBmdW5jdGlvbnM6IGFueVxuICApIHtcbiAgICB0aGlzLmFuYWx5dGljYWxBZ2VudCA9IG5ldyBBbmFseXRpY2FsQWdlbnQobGxtU2VydmljZSk7XG4gICAgdGhpcy5jcmVhdGl2ZUFnZW50ID0gbmV3IENyZWF0aXZlQWdlbnQobGxtU2VydmljZSk7XG4gICAgdGhpcy5wcmFjdGljYWxBZ2VudCA9IG5ldyBQcmFjdGljYWxBZ2VudChsbG1TZXJ2aWNlKTtcbiAgICB0aGlzLnN5bnRoZXNpemluZ0FnZW50ID0gbmV3IFN5bnRoZXNpemluZ0FnZW50KGxsbVNlcnZpY2UpO1xuICAgIHRoaXMuZGF0YUFuYWx5c3RTa2lsbCA9IG5ldyBEYXRhQW5hbHlzdFNraWxsKGNvbnRleHQsIG1lbW9yeSwgZnVuY3Rpb25zKTtcbiAgICB0aGlzLmFkdmFuY2VkUmVzZWFyY2hTa2lsbCA9IG5ldyBBZHZhbmNlZFJlc2VhcmNoU2tpbGwoKTtcbiAgICB0aGlzLmxlZ2FsRG9jdW1lbnRBbmFseXNpc1NraWxsID0gbmV3IExlZ2FsRG9jdW1lbnRBbmFseXNpc1NraWxsKCk7XG4gICAgdGhpcy5zb2NpYWxNZWRpYUFnZW50ID0gbmV3IFNvY2lhbE1lZGlhQWdlbnQobGxtU2VydmljZSk7XG4gICAgdGhpcy5jb250ZW50Q3JlYXRpb25BZ2VudCA9IG5ldyBDb250ZW50Q3JlYXRpb25BZ2VudChsbG1TZXJ2aWNlKTtcbiAgICB0aGlzLnBlcnNvbmFsaXplZFNob3BwaW5nQWdlbnQgPSBuZXcgUGVyc29uYWxpemVkU2hvcHBpbmdBZ2VudChsbG1TZXJ2aWNlKTtcbiAgICB0aGlzLnJlY3J1aXRtZW50UmVjb21tZW5kYXRpb25BZ2VudCA9IG5ldyBSZWNydWl0bWVudFJlY29tbWVuZGF0aW9uQWdlbnQoXG4gICAgICBsbG1TZXJ2aWNlXG4gICAgKTtcbiAgICB0aGlzLnZpYmVIYWNraW5nQWdlbnQgPSBuZXcgVmliZUhhY2tpbmdBZ2VudChsbG1TZXJ2aWNlKTtcbiAgICB0aGlzLnRheEFnZW50ID0gbmV3IFRheEFnZW50KGxsbVNlcnZpY2UpO1xuICAgIHRoaXMubWFya2V0aW5nQXV0b21hdGlvbkFnZW50ID0gbmV3IE1hcmtldGluZ0F1dG9tYXRpb25BZ2VudChsbG1TZXJ2aWNlKTtcbiAgfVxuXG4gIHB1YmxpYyBhc3luYyBhbmFseXplSW50ZW50KGlucHV0OiBTdWJBZ2VudElucHV0KTogUHJvbWlzZTxFbnJpY2hlZEludGVudD4ge1xuICAgIGNvbnN0IFBfTEVBRF9TVUJfQUdFTlRTX1RJTUVSX0xBQkVMID0gYFske3RoaXMuYWdlbnROYW1lfV0gQWxsIFN1Yi1BZ2VudHMgUHJvY2Vzc2luZyBEdXJhdGlvbmA7XG4gICAgY29uc3QgUF9MRUFEX1NZTlRIRVNJU19USU1FUl9MQUJFTCA9IGBbJHt0aGlzLmFnZW50TmFtZX1dIFN5bnRoZXNpcyBEdXJhdGlvbmA7XG5cbiAgICBjb25zb2xlLnRpbWUoUF9MRUFEX1NVQl9BR0VOVFNfVElNRVJfTEFCRUwpO1xuICAgIGNvbnN0IFtcbiAgICAgIGFuYWx5dGljYWxSZXNwb25zZSxcbiAgICAgIGNyZWF0aXZlUmVzcG9uc2UsXG4gICAgICBwcmFjdGljYWxSZXNwb25zZSxcbiAgICAgIHNvY2lhbE1lZGlhUmVzcG9uc2UsXG4gICAgICBjb250ZW50Q3JlYXRpb25SZXNwb25zZSxcbiAgICAgIHBlcnNvbmFsaXplZFNob3BwaW5nUmVzcG9uc2UsXG4gICAgICByZWNydWl0bWVudFJlY29tbWVuZGF0aW9uUmVzcG9uc2UsXG4gICAgICB2aWJlSGFja2luZ1Jlc3BvbnNlLFxuICAgICAgdGF4UmVzcG9uc2UsXG4gICAgICBtYXJrZXRpbmdBdXRvbWF0aW9uUmVzcG9uc2UsXG4gICAgXSA9IGF3YWl0IFByb21pc2UuYWxsKFtcbiAgICAgIHRoaXMuYW5hbHl0aWNhbEFnZW50LmFuYWx5emUoaW5wdXQpLmNhdGNoKChlKSA9PiB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoJ0FuYWx5dGljYWxBZ2VudCBmYWlsZWQ6JywgZSk7XG4gICAgICAgIHJldHVybiBudWxsO1xuICAgICAgfSksXG4gICAgICB0aGlzLmNyZWF0aXZlQWdlbnQuYW5hbHl6ZShpbnB1dCkuY2F0Y2goKGUpID0+IHtcbiAgICAgICAgY29uc29sZS5lcnJvcignQ3JlYXRpdmVBZ2VudCBmYWlsZWQ6JywgZSk7XG4gICAgICAgIHJldHVybiBudWxsO1xuICAgICAgfSksXG4gICAgICB0aGlzLnByYWN0aWNhbEFnZW50LmFuYWx5emUoaW5wdXQpLmNhdGNoKChlKSA9PiB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoJ1ByYWN0aWNhbEFnZW50IGZhaWxlZDonLCBlKTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9KSxcbiAgICAgIHRoaXMuc29jaWFsTWVkaWFBZ2VudC5hbmFseXplKGlucHV0KS5jYXRjaCgoZSkgPT4ge1xuICAgICAgICBjb25zb2xlLmVycm9yKCdTb2NpYWxNZWRpYUFnZW50IGZhaWxlZDonLCBlKTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9KSxcbiAgICAgIHRoaXMuY29udGVudENyZWF0aW9uQWdlbnQuYW5hbHl6ZShpbnB1dCkuY2F0Y2goKGUpID0+IHtcbiAgICAgICAgY29uc29sZS5lcnJvcignQ29udGVudENyZWF0aW9uQWdlbnQgZmFpbGVkOicsIGUpO1xuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH0pLFxuICAgICAgdGhpcy5wZXJzb25hbGl6ZWRTaG9wcGluZ0FnZW50LmFuYWx5emUoaW5wdXQpLmNhdGNoKChlKSA9PiB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoJ1BlcnNvbmFsaXplZFNob3BwaW5nQWdlbnQgZmFpbGVkOicsIGUpO1xuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH0pLFxuICAgICAgdGhpcy5yZWNydWl0bWVudFJlY29tbWVuZGF0aW9uQWdlbnQuYW5hbHl6ZShpbnB1dCkuY2F0Y2goKGUpID0+IHtcbiAgICAgICAgY29uc29sZS5lcnJvcignUmVjcnVpdG1lbnRSZWNvbW1lbmRhdGlvbkFnZW50IGZhaWxlZDonLCBlKTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9KSxcbiAgICAgIHRoaXMudmliZUhhY2tpbmdBZ2VudC5hbmFseXplKGlucHV0KS5jYXRjaCgoZSkgPT4ge1xuICAgICAgICBjb25zb2xlLmVycm9yKCdWaWJlSGFja2luZ0FnZW50IGZhaWxlZDonLCBlKTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9KSxcbiAgICAgIHRoaXMudGF4QWdlbnQuYW5hbHl6ZShpbnB1dCkuY2F0Y2goKGUpID0+IHtcbiAgICAgICAgY29uc29sZS5lcnJvcignVGF4QWdlbnQgZmFpbGVkOicsIGUpO1xuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH0pLFxuICAgICAgdGhpcy5tYXJrZXRpbmdBdXRvbWF0aW9uQWdlbnQuYW5hbHl6ZShpbnB1dCkuY2F0Y2goKGUpID0+IHtcbiAgICAgICAgY29uc29sZS5lcnJvcignTWFya2V0aW5nQXV0b21hdGlvbkFnZW50IGZhaWxlZDonLCBlKTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9KSxcbiAgICBdKTtcbiAgICBjb25zb2xlLnRpbWVFbmQoUF9MRUFEX1NVQl9BR0VOVFNfVElNRVJfTEFCRUwpO1xuXG4gICAgaWYgKGFuYWx5dGljYWxSZXNwb25zZT8ucHJvYmxlbVR5cGUgPT09ICdkYXRhX2FuYWx5c2lzJykge1xuICAgICAgY29uc3QgZGF0YUFuYWx5c3RSZXN1bHQgPSBhd2FpdCB0aGlzLmRhdGFBbmFseXN0U2tpbGwuYW5hbHl6ZURhdGEoXG4gICAgICAgIGlucHV0LnVzZXJJbnB1dFxuICAgICAgKTtcbiAgICAgIC8vIFlvdSBjYW4gZGVjaWRlIGhvdyB0byBpbmNvcnBvcmF0ZSB0aGUgcmVzdWx0IG9mIHRoZSBkYXRhIGFuYWx5c3Qgc2tpbGwuXG4gICAgICAvLyBGb3Igbm93LCB3ZSdsbCBqdXN0IGxvZyBpdC5cbiAgICAgIGNvbnNvbGUubG9nKCdEYXRhIEFuYWx5c3QgU2tpbGwgUmVzdWx0OicsIGRhdGFBbmFseXN0UmVzdWx0KTtcbiAgICB9XG5cbiAgICBjb25zb2xlLnRpbWUoUF9MRUFEX1NZTlRIRVNJU19USU1FUl9MQUJFTCk7XG4gICAgY29uc3Qgc3ludGhlc2lzUmVzdWx0ID0gYXdhaXQgdGhpcy5zeW50aGVzaXppbmdBZ2VudC5zeW50aGVzaXplKFxuICAgICAgaW5wdXQsXG4gICAgICBhbmFseXRpY2FsUmVzcG9uc2UsXG4gICAgICBjcmVhdGl2ZVJlc3BvbnNlLFxuICAgICAgcHJhY3RpY2FsUmVzcG9uc2UsXG4gICAgICBzb2NpYWxNZWRpYVJlc3BvbnNlLFxuICAgICAgY29udGVudENyZWF0aW9uUmVzcG9uc2UsXG4gICAgICBwZXJzb25hbGl6ZWRTaG9wcGluZ1Jlc3BvbnNlLFxuICAgICAgcmVjcnVpdG1lbnRSZWNvbW1lbmRhdGlvblJlc3BvbnNlLFxuICAgICAgdmliZUhhY2tpbmdSZXNwb25zZSxcbiAgICAgIHRheFJlc3BvbnNlLFxuICAgICAgbWFya2V0aW5nQXV0b21hdGlvblJlc3BvbnNlXG4gICAgKTtcbiAgICBjb25zb2xlLnRpbWVFbmQoUF9MRUFEX1NZTlRIRVNJU19USU1FUl9MQUJFTCk7XG5cbiAgICBpZiAoc3ludGhlc2lzUmVzdWx0LnN1Z2dlc3RlZE5leHRBY3Rpb24/LmFjdGlvblR5cGUgPT09ICdpbnZva2Vfc2tpbGwnKSB7XG4gICAgICBjb25zdCBza2lsbElkID0gc3ludGhlc2lzUmVzdWx0LnN1Z2dlc3RlZE5leHRBY3Rpb24uc2tpbGxJZDtcbiAgICAgIGlmIChza2lsbElkID09PSAnYWR2YW5jZWRSZXNlYXJjaCcpIHtcbiAgICAgICAgLy8gQHRzLWlnbm9yZVxuICAgICAgICBjb25zdCByZXNlYXJjaFJlc3VsdCA9IGF3YWl0IHRoaXMuYWR2YW5jZWRSZXNlYXJjaFNraWxsLmhhbmRsZXIoXG4gICAgICAgICAgc3ludGhlc2lzUmVzdWx0LmV4dHJhY3RlZFBhcmFtZXRlcnNcbiAgICAgICAgKTtcbiAgICAgICAgY29uc29sZS5sb2coJ0FkdmFuY2VkIFJlc2VhcmNoIFNraWxsIFJlc3VsdDonLCByZXNlYXJjaFJlc3VsdCk7XG4gICAgICB9IGVsc2UgaWYgKHNraWxsSWQgPT09ICdsZWdhbERvY3VtZW50QW5hbHlzaXMnKSB7XG4gICAgICAgIC8vIEB0cy1pZ25vcmVcbiAgICAgICAgY29uc3QgbGVnYWxSZXN1bHQgPSBhd2FpdCB0aGlzLmxlZ2FsRG9jdW1lbnRBbmFseXNpc1NraWxsLmhhbmRsZXIoXG4gICAgICAgICAgc3ludGhlc2lzUmVzdWx0LmV4dHJhY3RlZFBhcmFtZXRlcnNcbiAgICAgICAgKTtcbiAgICAgICAgY29uc29sZS5sb2coJ0xlZ2FsIERvY3VtZW50IEFuYWx5c2lzIFNraWxsIFJlc3VsdDonLCBsZWdhbFJlc3VsdCk7XG4gICAgICB9XG4gICAgICAvLyBBZGQgc2ltaWxhciBibG9ja3MgZm9yIG90aGVyIHNraWxsc1xuICAgIH1cblxuICAgIHJldHVybiB7XG4gICAgICBvcmlnaW5hbFF1ZXJ5OiBpbnB1dC51c2VySW5wdXQsXG4gICAgICB1c2VySWQ6IGlucHV0LnVzZXJJZCxcbiAgICAgIHByaW1hcnlHb2FsOiBzeW50aGVzaXNSZXN1bHQucHJpbWFyeUdvYWwsXG4gICAgICBwcmltYXJ5R29hbENvbmZpZGVuY2U6IHN5bnRoZXNpc1Jlc3VsdC5wcmltYXJ5R29hbENvbmZpZGVuY2UsXG4gICAgICBleHRyYWN0ZWRQYXJhbWV0ZXJzOiBzeW50aGVzaXNSZXN1bHQuZXh0cmFjdGVkUGFyYW1ldGVycyxcbiAgICAgIGlkZW50aWZpZWRUYXNrczogc3ludGhlc2lzUmVzdWx0LmlkZW50aWZpZWRUYXNrcyxcbiAgICAgIHN1Z2dlc3RlZE5leHRBY3Rpb246IHN5bnRoZXNpc1Jlc3VsdC5zdWdnZXN0ZWROZXh0QWN0aW9uLFxuICAgICAgYWx0ZXJuYXRpdmVJbnRlcnByZXRhdGlvbnM6IGNyZWF0aXZlUmVzcG9uc2U/LmFsdGVybmF0aXZlR29hbHMsXG4gICAgICBwb3RlbnRpYWxBbWJpZ3VpdGllczogY3JlYXRpdmVSZXNwb25zZT8uYW1iaWd1aXR5RmxhZ3MsXG4gICAgICBwcmFjdGljYWxDb25zaWRlcmF0aW9uczoge1xuICAgICAgICBmZWFzaWJpbGl0eTogcHJhY3RpY2FsUmVzcG9uc2U/LmZlYXNpYmlsaXR5QXNzZXNzbWVudCxcbiAgICAgICAgZWZmaWNpZW5jeVRpcHM6IHByYWN0aWNhbFJlc3BvbnNlPy5lZmZpY2llbmN5VGlwcyxcbiAgICAgIH0sXG4gICAgICByYXdTdWJBZ2VudFJlc3BvbnNlczoge1xuICAgICAgICBhbmFseXRpY2FsOiBhbmFseXRpY2FsUmVzcG9uc2UsXG4gICAgICAgIGNyZWF0aXZlOiBjcmVhdGl2ZVJlc3BvbnNlLFxuICAgICAgICBwcmFjdGljYWw6IHByYWN0aWNhbFJlc3BvbnNlLFxuICAgICAgICBzb2NpYWxNZWRpYTogc29jaWFsTWVkaWFSZXNwb25zZSxcbiAgICAgICAgY29udGVudENyZWF0aW9uOiBjb250ZW50Q3JlYXRpb25SZXNwb25zZSxcbiAgICAgICAgcGVyc29uYWxpemVkU2hvcHBpbmc6IHBlcnNvbmFsaXplZFNob3BwaW5nUmVzcG9uc2UsXG4gICAgICAgIHJlY3J1aXRtZW50UmVjb21tZW5kYXRpb246IHJlY3J1aXRtZW50UmVjb21tZW5kYXRpb25SZXNwb25zZSxcbiAgICAgICAgdmliZUhhY2tpbmc6IHZpYmVIYWNraW5nUmVzcG9uc2UsXG4gICAgICAgIHRheDogdGF4UmVzcG9uc2UsXG4gICAgICAgIG1hcmtldGluZ0F1dG9tYXRpb246IG1hcmtldGluZ0F1dG9tYXRpb25SZXNwb25zZSxcbiAgICAgIH0sXG4gICAgICBzeW50aGVzaXNMb2c6IHN5bnRoZXNpc1Jlc3VsdC5zeW50aGVzaXNMb2cgfHwgW1xuICAgICAgICAnU3ludGhlc2lzIGxvZyBub3QgaW5pdGlhbGl6ZWQuJyxcbiAgICAgIF0sXG4gICAgfTtcbiAgfVxufVxuXG5jb25zb2xlLmxvZygnTkxVTGVhZEFnZW50IGNsYXNzIGxvYWRlZC4nKTtcbiJdfQ==