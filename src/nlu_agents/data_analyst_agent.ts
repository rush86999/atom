import { TurnContext } from "botbuilder";
import { Application, ActionPlanner, PromptManager } from "@microsoft/teams-ai";
import { DataAnalystSkills } from "../skills/dataAnalystSkills";

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

export { app as dataAnalystAgent };
