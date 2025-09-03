"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AutonomousTradingAgent = void 0;
const tradingSkills_1 = require("../skills/tradingSkills");
class AutonomousTradingAgent {
    constructor(llmService) {
        this.agentName = 'AutonomousTradingAgent';
        this.llmService = llmService;
    }
    async analyze(input) {
        const { userInput, userId } = input;
        const prompt = `You are an AI assistant responsible for managing an autonomous trading system. Your task is to analyze the user's request and determine if they want to start or stop the trading system.

    User request: "${userInput}"

    Possible actions:
    - "start_autonomous_trading": If the user wants to start the trading system.
    - "stop_autonomous_trading": If the user wants to stop the trading system.
    - "none": If the user's request is not related to the trading system.

    If the action is "start_autonomous_trading", you must also identify the trading strategy the user wants to use.
    Available strategies:
    - "moving_average_crossover"
    - "rsi"
    - "bollinger_bands"

    If the user does not specify a strategy, use "moving_average_crossover" as the default.

    Respond with a JSON object containing the "action", "confidence" (from 0 to 1), and "strategyName" (if applicable).`;
        try {
            const llmResponse = await this.llmService.generate(prompt);
            const parsedResponse = JSON.parse(llmResponse);
            if (parsedResponse.action === 'start_autonomous_trading' && parsedResponse.confidence > 0.7) {
                const startSkill = tradingSkills_1.tradingSkills.find(skill => skill.name === 'start_autonomous_trading');
                if (startSkill) {
                    const result = await startSkill.handler({ userId, strategyName: parsedResponse.strategyName });
                    return {
                        action: 'start_autonomous_trading',
                        confidence: parsedResponse.confidence,
                        strategyName: parsedResponse.strategyName,
                        result,
                    };
                }
            }
            if (parsedResponse.action === 'stop_autonomous_trading' && parsedResponse.confidence > 0.7) {
                const stopSkill = tradingSkills_1.tradingSkills.find(skill => skill.name === 'stop_autonomous_trading');
                if (stopSkill) {
                    const result = await stopSkill.handler({ userId });
                    return {
                        action: 'stop_autonomous_trading',
                        confidence: parsedResponse.confidence,
                        result,
                    };
                }
            }
            return {
                action: 'none',
                confidence: parsedResponse.confidence || 0,
            };
        }
        catch (error) {
            console.error('Error in AutonomousTradingAgent.analyze:', error);
            return {
                action: 'none',
                confidence: 0,
                error: 'Failed to analyze trading intent.',
            };
        }
    }
}
exports.AutonomousTradingAgent = AutonomousTradingAgent;
//# sourceMappingURL=trading_agent.js.map