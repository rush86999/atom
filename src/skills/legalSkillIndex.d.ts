declare class LegalDocumentAnalysisSkill {
    handler: (input: import("../nlu_agents/nlu_types").SubAgentInput) => Promise<import("../nlu_agents/nlu_types").LegalDocumentAnalysisAgentResponse>;
}
export { LegalDocumentAnalysisSkill };
