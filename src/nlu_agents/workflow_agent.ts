import { SubAgentInput, AgentLLMService } from "./nlu_types";

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
  conditions?: {
    type: "if_then" | "when_then" | "multi_step";
    condition?: string;
    then_actions?: string[];
    else_actions?: string[];
  }[];
  workflow_type?: "simple" | "conditional" | "multi_step";
  confidence: number;
}

export class WorkflowAgent {
  private agentName: string = "WorkflowAgent";

  constructor(private llmService: AgentLLMService) {}

  public async analyze(
    input: SubAgentInput,
  ): Promise<WorkflowAgentResponse | null> {
    const P_WORKFLOW_AGENT_TIMER_LABEL = `[${this.agentName}] Processing Duration`;
    console.time(P_WORKFLOW_AGENT_TIMER_LABEL);

    const prompt = `
      You are an expert in understanding user requests to create automated workflows.
      Analyze the following user request and determine if the user wants to create a workflow.
      A workflow is a sequence of automated steps, which can be:
      - Simple: "when X happens, do Y, then Z"
      - Conditional: "if X happens, then do Y, else do Z"
      - Multi-step: "first do A, then B, then C depending on D"

      If the user wants to create a workflow, identify:
      1. The trigger that starts it
      2. The sequence of actions to be performed
      3. Any conditional logic (if/then/else statements)
      4. The workflow type (simple, conditional, or multi-step)

      For conditional workflows, extract the condition and different action paths.
      For each action, extract the relevant parameters.

      Respond in JSON format with the following fields:
      - "isWorkflowRequest": boolean, true if the user is asking to create a workflow, false otherwise.
      - "trigger": object with "service" and "event" fields (e.g., {"service": "gmail", "event": "new_email"}). This should only be present if isWorkflowRequest is true.
      - "actions": a list of objects, each with "service", "action", and "parameters" fields. The "parameters" field should be an object containing the extracted parameters for the action.
      - "conditions": a list of conditional logic objects, each with "type" ("if_then", "when_then", or "multi_step"), "condition" (the condition text), "then_actions" (actions to perform if condition is true), and "else_actions" (actions to perform if condition is false, optional).
      - "workflow_type": "simple", "conditional", or "multi_step"
      - "confidence": number between 0 and 1 indicating confidence in the analysis

      Examples:
      - "If I receive an email from my boss, then create a task in Asana and send me a Slack notification" -> conditional workflow
      - "When a new task is created in Asana, send an email to the team" -> simple workflow
      - "First check my calendar for availability, then if I'm free, schedule a meeting, else send a decline email" -> multi-step conditional workflow

      User request: "${input.userInput}"
    `;

    try {
      const llmResponse = await this.llmService.generate(prompt);
      const parsedResponse = JSON.parse(llmResponse) as WorkflowAgentResponse;

      console.timeEnd(P_WORKFLOW_AGENT_TIMER_LABEL);
      return parsedResponse;
    } catch (error) {
      console.error("WorkflowAgent failed:", error);
      console.timeEnd(P_WORKFLOW_AGENT_TIMER_LABEL);
      return null;
    }
  }
}
