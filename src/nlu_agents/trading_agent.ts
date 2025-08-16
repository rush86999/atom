import { SubAgentInput, AgentLLMService } from './nlu_types';
import { tradingSkills } from '../skills/tradingSkills';

export class AutonomousTradingAgent {
  private agentName: string = 'AutonomousTradingAgent';
  private llmService: AgentLLMService;

  constructor(llmService: AgentLLMService) {
    this.llmService = llmService;
  }

  public async analyze(input: SubAgentInput): Promise<any> {
    const { userInput, userId } = input;

    const prompt = `You are an AI assistant responsible for managing an autonomous trading system. Your task is to analyze the user's request and determine if they want to start or stop the trading system.

    User request: "${userInput}"

    Possible actions:
    - "start_autonomous_trading": If the user wants to start the trading system.
    - "stop_autonomous_trading": If the user wants to stop the trading system.
    - "none": If the user's request is not related to the trading system.

    Respond with a JSON object containing the "action" and "confidence" (from 0 to 1).`;

    try {
        const llmResponse = await this.llmService.generate(prompt);
        const parsedResponse = JSON.parse(llmResponse);

        if (parsedResponse.action === 'start_autonomous_trading' && parsedResponse.confidence > 0.7) {
            const startSkill = tradingSkills.find(skill => skill.name === 'start_autonomous_trading');
            if (startSkill) {
                const result = await startSkill.handler({ userId });
                return {
                    action: 'start_autonomous_trading',
                    confidence: parsedResponse.confidence,
                    result,
                };
            }
        }

        if (parsedResponse.action === 'stop_autonomous_trading' && parsedResponse.confidence > 0.7) {
            const stopSkill = tradingSkills.find(skill => skill.name === 'stop_autonomous_trading');
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
    } catch (error) {
        console.error('Error in AutonomousTradingAgent.analyze:', error);
        return {
            action: 'none',
            confidence: 0,
            error: 'Failed to analyze trading intent.',
        };
    }
  }
}
