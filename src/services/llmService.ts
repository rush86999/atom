import { AgentLLMService } from '../nlu_agents/nlu_types';
import { OpenAI } from 'openai';
import { ATOM_OPENAI_API_KEY } from '../../atomic-docker/project/functions/atom-agent/_libs/constants';

class ConcreteAgentLLMService implements AgentLLMService {
    private openai: OpenAI;

    constructor(apiKey: string) {
        if (!apiKey) {
            throw new Error("OpenAI API key is required.");
        }
        this.openai = new OpenAI({ apiKey });
    }

    async generate(prompt: any, model: string, options: any): Promise<any> {
        const response = await this.openai.chat.completions.create({
            model: model,
            messages: [{ role: 'system', content: prompt.data.system_prompt }, { role: 'user', content: prompt.data.user_query }],
            ...options
        });
        return { success: true, content: response.choices[0].message.content, usage: response.usage };
    }
}

let llmService: AgentLLMService;

export function getLLMService(): AgentLLMService {
  if (!llmService) {
    llmService = new ConcreteAgentLLMService(ATOM_OPENAI_API_KEY!);
  }
  return llmService;
}
