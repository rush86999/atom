import { TurnContext } from "botbuilder";
import { Application, ActionPlanner, PromptManager } from "@microsoft/teams-ai";
import { DataAnalystSkills } from "../skills/dataAnalystSkills";
import { SubAgentInput, DataAnalystAgentResponse } from "./nlu_types";
import { DataAnalystUseCases } from "../use_cases/data_analyst_use_cases";

// Define a state object for the agent.
// This is used to track the conversation state.
interface ConversationState {
    // tracked properties
}
type ApplicationTurnState = {
    conversation: ConversationState;
};

// Create a new action planner
const planner = new ActionPlanner({
    prompts: new PromptManager({
        promptsFolder: './src/nlu_agents/prompts'
    }),
    defaultPrompt: 'chat'
});

// Create a new application
const app = new Application<ApplicationTurnState>({
    planner
});

// Register the data analyst skills
app.ai.addTool(new DataAnalystSkills(new TurnContext({} as any, {} as any), {} as any, {} as any));

export class DataAnalystAgent {
    private useCases: DataAnalystUseCases;

    constructor(context: TurnContext, memory: any, functions: any) {
        this.useCases = new DataAnalystUseCases(context, memory, functions);
    }

    public async analyze(input: SubAgentInput): Promise<DataAnalystAgentResponse> {
        // In a real scenario, you would have a more sophisticated way
        // of determining the use case and parameters.
        const useCase = "sales_report";
        const parameters = { quarter: "Q3" };
        const result = await this.useCases.executeUseCase(useCase, parameters);
        return {
            dataQueries: [result],
            requiredVisualizations: ['bar chart'],
            dataSources: ['database'],
        };
    }
}

export { app as dataAnalystAgentApp };
