import { EnrichedIntent } from './nlu_types';
import { Pool } from 'pg';

async function getComponent(db: Pool, service: string, name: string, type: 'trigger' | 'action') {
    const result = await db.query(
      'SELECT * FROM workflow_components WHERE service = $1 AND name = $2 AND type = $3',
      [service, name, type]
    );
    if (result.rows.length === 0) {
      return null;
    }
    const component = result.rows[0];

    const schemaResult = await db.query(
      'SELECT * FROM workflow_component_schemas WHERE component_id = $1',
      [component.id]
    );

    component.schemas = {};
    for (const row of schemaResult.rows) {
        component.schemas[row.type] = row.schema;
    }

    return component;
  }

export class WorkflowGenerator {
    private db: Pool;

    constructor() {
        this.db = new Pool({
            connectionString: process.env.HASURA_GRAPHQL_DATABASE_URL,
        });
    }

  public async generate(intent: EnrichedIntent): Promise<object | null> {
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
    const triggerComponent = await getComponent(this.db, trigger.service, trigger.event, 'trigger');
    if (!triggerComponent) {
      console.error(`Unknown trigger: ${trigger.service}.${trigger.event}`);
      return null;
    }

    const triggerNode = {
        id: '1',
        type: 'genericNode', // Use the new generic node
        position: { x: 250, y: yPos },
        data: {
          name: triggerComponent.name,
          service: triggerComponent.service,
          description: triggerComponent.description,
          inputSchema: triggerComponent.schemas.input,
          values: trigger.parameters || {},
        },
      };
      nodes.push(triggerNode);
      lastNodeId = triggerNode.id;
      yPos += 250;


    // Create action nodes
    for (let i = 0; i < actions.length; i++) {
      const action = actions[i];
      const actionComponent = await getComponent(this.db, action.service, action.action, 'action');
      if (!actionComponent) {
        console.error(`Unknown action: ${action.service}.${action.action}`);
        continue;
      }

      const actionNode = {
        id: `${i + 2}`,
        type: 'genericNode',
        position: { x: 250, y: yPos },
        data: {
            name: actionComponent.name,
            service: actionComponent.service,
            description: actionComponent.description,
            inputSchema: actionComponent.schemas.input,
            values: action.parameters || {},
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
      yPos += 250;
    }

    return { nodes, edges };
  }
}
