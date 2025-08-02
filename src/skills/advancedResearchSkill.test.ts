import { AdvancedResearchAgent } from './advancedResearchSkill';
import { AgentLLMService, SubAgentInput } from '../nlu_agents/nlu_types';
import * as canvaSkills from './canvaSkills';

jest.mock('./canvaSkills');

const mockedCreateDesign = canvaSkills.createDesign as jest.Mock;

describe('AdvancedResearchAgent', () => {
    let agent: AdvancedResearchAgent;
    let llmService: AgentLLMService;

    beforeEach(() => {
        llmService = {
            generate: jest.fn(),
        };
        agent = new AdvancedResearchAgent(llmService);
    });

    it('should call createCanvaDesign when the chat command is detected', async () => {
        const input: SubAgentInput = {
            userInput: 'create canva design with title "My Test Design"',
            userId: 'test-user-id',
        };
        const designData = { id: 'design-id', title: 'My Test Design', urls: { edit_url: 'edit-url' } };
        mockedCreateDesign.mockResolvedValue(designData);

        const result = await agent.analyze(input);

        expect(mockedCreateDesign).toHaveBeenCalledWith('test-user-id', 'My Test Design');
        expect(result.researchSummary).toBe('Successfully created Canva design: "My Test Design"');
    });

    it('should call the LLM service when no Canva command is detected', async () => {
        const input: SubAgentInput = {
            userInput: 'what is the capital of France?',
            userId: 'test-user-id',
        };
        const llmResponse = {
            success: true,
            content: JSON.stringify({
                researchSummary: 'Paris',
                keyFindings: ['Paris is the capital of France'],
                sources: [],
            }),
        };
        (llmService.generate as jest.Mock).mockResolvedValue(llmResponse);

        const result = await agent.analyze(input);

        expect(llmService.generate).toHaveBeenCalled();
        expect(result.researchSummary).toBe('Paris');
    });
});
