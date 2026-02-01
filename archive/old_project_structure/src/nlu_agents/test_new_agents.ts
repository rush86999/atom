import { TurnContext } from 'botbuilder';
import { NLULeadAgent } from './nlu_lead_agent';
import { SubAgentInput } from './nlu_types';
import { MockLLMService } from '../lib/llmUtils';

async function testNewAgents() {
  const llmService = new MockLLMService();
  const context = new TurnContext({} as any, {} as any);
  const memory = {};
  const functions = {};
  const leadAgent = new NLULeadAgent(llmService, context, memory, functions);

  const testCases: SubAgentInput[] = [
    {
      userInput:
        'Research the latest trends in AI-powered personal assistants and summarize the key findings in a Notion document.',
    },
    {
      userInput:
        "Schedule a week's worth of social media posts about our new product launch.",
    },
    { userInput: "Find me a new laptop for work that's under $1000." },
    {
      userInput:
        'Analyze this contract and identify any potential risks: [URL/filepath].',
    },
    {
      userInput:
        'Find the best candidates for the Senior Software Engineer position.',
    },
    { userInput: 'Perform a red team test on our web application.' },
  ];

  for (const testCase of testCases) {
    console.log(`--- Testing with input: "${testCase.userInput}" ---`);
    const result = await leadAgent.analyzeIntent(testCase);
    console.log(JSON.stringify(result, null, 2));
  }
}

testNewAgents();
