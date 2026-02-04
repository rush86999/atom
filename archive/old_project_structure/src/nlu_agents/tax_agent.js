"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TaxAgent = void 0;
class TaxAgent {
    constructor(llmService) {
        this.llmService = llmService;
        this.agentName = 'TaxAgent';
    }
    async analyze(input) {
        const normalizedQuery = input.userInput.toLowerCase().trim();
        if (normalizedQuery.includes('tax') || normalizedQuery.includes('taxes')) {
            return {
                isTaxRelated: true,
                confidence: 0.9,
                details: 'The query contains tax-related keywords.',
            };
        }
        return null;
    }
}
exports.TaxAgent = TaxAgent;
//# sourceMappingURL=tax_agent.js.map