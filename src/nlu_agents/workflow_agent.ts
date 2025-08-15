import { SubAgentInput, AgentLLMService } from './nlu_types';

export interface WorkflowAgentResponse {
  isWorkflowRequest: boolean;
  trigger?: {
    service: string;
    event: string;
  };
  actions?: {
    service: string;
    action: string;
  }[];
}

export class WorkflowAgent {
  private agentName: string = 'WorkflowAgent';

  constructor(private llmService: AgentLLMService) {}

  public async analyze(input: SubAgentInput): Promise<WorkflowAgentResponse | null> {
    const P_WORKFLOW_AGENT_TIMER_LABEL = `[${this.agentName}] Processing Duration`;
    console.time(P_WORKFLOW_AGENT_TIMER_LABEL);

    const prompt = `
      You are an expert in understanding user requests to create automated workflows.
      Analyze the following user request and determine if the user wants to create a workflow.
      A workflow is a sequence of automated steps, usually in the format "when X happens, do Y, then Z".
      If the user wants to create a workflow, identify the trigger that starts it and the sequence of actions to be performed.
      For each action, extract the relevant parameters.
      Respond in JSON format with the following fields:
      - "isWorkflowRequest": boolean, true if the user is asking to create a workflow, false otherwise.
      - "trigger": object with "service" and "event" fields (e.g., {"service": "gmail", "event": "new_email"}). This should only be present if isWorkflowRequest is true.
      - "actions": a list of objects, each with "service", "action", and "parameters" fields. The "parameters" field should be an object containing the extracted parameters for the action (e.g., for Notion: {"service": "notion", "action": "create_task", "parameters": {"description": "My new task", "properties": {"Status": "In Progress", "Priority": "High"}}}). This should only be present if isWorkflowRequest is true.

      User request: "${input.userInput}"
    `;

    try {
      const llmResponse = await this.llmService.generate(prompt);
      const parsedResponse = JSON.parse(llmResponse) as WorkflowAgentResponse;

      console.timeEnd(P_WORKFLOW_AGENT_TIMER_LABEL);
      return parsedResponse;
    } catch (error) {
      console.error('WorkflowAgent failed:', error);
      console.timeEnd(P_WORKFLOW_AGENT_TIMER_LABEL);
      return null;
    }
  }
}
