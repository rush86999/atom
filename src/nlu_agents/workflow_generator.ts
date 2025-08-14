import { EnrichedIntent } from './nlu_types';

// A mapping from the service/action names from the NLU to the node types in React Flow.
const NODE_TYPE_MAP = {
  gmail: {
    new_email: 'gmailTrigger',
  },
  ai: {
    extract_action_items: 'aiTask',
  },
  notion: {
    create_task: 'notionAction',
  },
  asana: {
    create_task: 'asanaCreateTask',
  },
  trello: {
    create_card: 'trelloCreateCard',
  },
  slack: {
    send_message: 'slackSendMessage',
  },
  email: {
    send_email: 'sendEmail',
  },
  utils: {
    flatten: 'flatten',
  }
};

export class WorkflowGenerator {
  public generate(intent: EnrichedIntent): object | null {
    const { trigger, actions } = intent.extractedParameters as any;

    if (!trigger || !actions) {
      console.error("Missing trigger or actions in extracted parameters for workflow generation.");
      return null;
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
      id: '1',
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
}
