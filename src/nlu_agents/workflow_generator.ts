import { EnrichedIntent } from "./nlu_types";

interface ConditionalLogic {
  type: "if_then" | "when_then" | "multi_step";
  condition?: string;
  then_actions?: string[];
  else_actions?: string[];
}

// A mapping from the service/action names from the NLU to the node types in React Flow.
const NODE_TYPE_MAP = {
  gmail: {
    new_email: "gmailTrigger",
  },
  ai: {
    extract_action_items: "aiTask",
  },
  notion: {
    create_task: "notionAction",
  },
  asana: {
    create_task: "asanaCreateTask",
  },
  trello: {
    create_card: "trelloCreateCard",
  },
  slack: {
    send_message: "slackSendMessage",
  },
  email: {
    send_email: "sendEmail",
  },
  reminder: {
    create_reminder: "reminder",
  },
  google_calendar: {
    create_event: "googleCalendarCreateEvent",
  },
  utils: {
    flatten: "flatten",
    delay: "delay",
    filter: "llmFilter",
  },
  conditional: {
    evaluate_condition: "branch",
    execute_conditional_action: "llmFilter",
  },
};

export class WorkflowGenerator {
  public generate(intent: EnrichedIntent): object | null {
    const { trigger, actions, conditions, workflow_type } =
      intent.extractedParameters as any;

    if (!trigger || !actions) {
      console.error(
        "Missing trigger or actions in extracted parameters for workflow generation.",
      );
      return null;
    }

    // Handle conditional workflows
    if (
      workflow_type === "conditional" &&
      conditions &&
      conditions.length > 0
    ) {
      return this.generateConditionalWorkflow(trigger, actions, conditions);
    }

    // Handle multi-step workflows
    if (workflow_type === "multi_step") {
      return this.generateMultiStepWorkflow(trigger, actions, conditions);
    }

    const nodes = [];
    const edges = [];
    let lastNodeId = null;
    let yPos = 50;

    // Create trigger node
    const triggerNodeType = NODE_TYPE_MAP[trigger.service]?.[trigger.event];
    if (!triggerNodeType) {
      console.error(`Unknown trigger: ${trigger.service}.${trigger.event}`);
      return null;
    }
    const triggerNode = {
      id: "1",
      type: triggerNodeType,
      position: { x: 250, y: yPos },
      data: { label: `${trigger.service} - ${trigger.event}` },
    };
    nodes.push(triggerNode);
    lastNodeId = triggerNode.id;
    yPos += 150;

    // Create action nodes
    for (let i = 0; i < actions.length; i++) {
      const action = actions[i];
      const actionNodeType = NODE_TYPE_MAP[action.service]?.[action.action];
      if (!actionNodeType) {
        console.error(`Unknown action: ${action.service}.${action.action}`);
        continue;
      }

      const actionNode = {
        id: `${i + 2}`,
        type: actionNodeType,
        position: { x: 250, y: yPos },
        data: {
          label: `${action.service} - ${action.action}`,
          ...action.parameters,
        },
      };
      nodes.push(actionNode);

      const edge = {
        id: `e${lastNodeId}-${actionNode.id}`,
        source: lastNodeId,
        target: actionNode.id,
      };
      edges.push(edge);

      lastNodeId = actionNode.id;
      yPos += 150;
    }

    return { nodes, edges };
  }

  private generateConditionalWorkflow(
    trigger: any,
    actions: any[],
    conditions: ConditionalLogic[],
  ): object | null {
    const nodes = [];
    const edges = [];
    let yPos = 50;

    // Create trigger node
    const triggerNodeType = NODE_TYPE_MAP[trigger.service]?.[trigger.event];
    if (!triggerNodeType) {
      console.error(`Unknown trigger: ${trigger.service}.${trigger.event}`);
      return null;
    }

    const triggerNode = {
      id: "1",
      type: triggerNodeType,
      position: { x: 250, y: yPos },
      data: { label: `${trigger.service} - ${trigger.event}` },
    };
    nodes.push(triggerNode);
    yPos += 150;

    // Create condition evaluation node
    const conditionNode = {
      id: "2",
      type: "branch",
      position: { x: 250, y: yPos },
      data: {
        label: "Evaluate Condition",
        condition: conditions[0].condition,
        conditionType: conditions[0].type,
      },
    };
    nodes.push(conditionNode);
    edges.push({ id: "e1-2", source: "1", target: "2" });
    yPos += 150;

    // Create then branch nodes
    let thenYPos = yPos;
    let thenLastNodeId = "2";
    if (conditions[0].then_actions && conditions[0].then_actions.length > 0) {
      for (let i = 0; i < conditions[0].then_actions.length; i++) {
        const action = this.findActionByDescription(
          actions,
          conditions[0].then_actions[i],
        );
        if (action) {
          const actionNodeType = NODE_TYPE_MAP[action.service]?.[action.action];
          if (actionNodeType) {
            const actionNode = {
              id: `then_${i + 3}`,
              type: actionNodeType,
              position: { x: 150, y: thenYPos },
              data: {
                label: `${action.service} - ${action.action}`,
                ...action.parameters,
              },
            };
            nodes.push(actionNode);
            edges.push({
              id: `e${thenLastNodeId}-then_${i + 3}`,
              source: thenLastNodeId,
              target: `then_${i + 3}`,
              data: { condition: "true" },
            });
            thenLastNodeId = `then_${i + 3}`;
            thenYPos += 150;
          }
        }
      }
    }

    // Create else branch nodes (if any)
    let elseYPos = yPos;
    let elseLastNodeId = "2";
    if (conditions[0].else_actions && conditions[0].else_actions.length > 0) {
      for (let i = 0; i < conditions[0].else_actions.length; i++) {
        const action = this.findActionByDescription(
          actions,
          conditions[0].else_actions[i],
        );
        if (action) {
          const actionNodeType = NODE_TYPE_MAP[action.service]?.[action.action];
          if (actionNodeType) {
            const actionNode = {
              id: `else_${i + 3}`,
              type: actionNodeType,
              position: { x: 350, y: elseYPos },
              data: {
                label: `${action.service} - ${action.action}`,
                ...action.parameters,
              },
            };
            nodes.push(actionNode);
            edges.push({
              id: `e${elseLastNodeId}-else_${i + 3}`,
              source: elseLastNodeId,
              target: `else_${i + 3}`,
              data: { condition: "false" },
            });
            elseLastNodeId = `else_${i + 3}`;
            elseYPos += 150;
          }
        }
      }
    }

    return { nodes, edges };
  }

  private generateMultiStepWorkflow(
    trigger: any,
    actions: any[],
    conditions?: ConditionalLogic[],
  ): object | null {
    // For multi-step workflows, we can use the standard generator but add sequencing logic
    const result = this.generate({
      extractedParameters: { trigger, actions },
    } as EnrichedIntent);
    if (result && "nodes" in result) {
      // Add sequencing metadata to nodes
      (result as any).nodes.forEach((node: any, index: number) => {
        node.data.sequenceOrder = index + 1;
      });
    }
    return result;
  }

  private findActionByDescription(
    actions: any[],
    description: string,
  ): any | null {
    return actions.find(
      (action) =>
        `${action.service} - ${action.action}`
          .toLowerCase()
          .includes(description.toLowerCase()) ||
        description.toLowerCase().includes(action.service.toLowerCase()) ||
        description.toLowerCase().includes(action.action.toLowerCase()),
    );
  }
}
