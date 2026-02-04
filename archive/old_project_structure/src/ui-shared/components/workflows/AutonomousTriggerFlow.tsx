import React, { useState, useCallback, useEffect } from 'react';
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Position,
  Handle,
  NodeProps
} from 'reactflow';
import 'reactflow/dist/style.css';

interface TriggerNodeData {
  label: string;
  triggerType: string;
  frequency: string;
  condition: string;
  status: 'active' | 'inactive' | 'error';
  lastRun?: string;
  nextRun?: string;
  successRate?: number;
}

interface AutonomousTriggerFlowProps {
  workflows: any[];
  triggers: any[];
  onTriggerChange: (triggerId: string, updates: Partial<TriggerNodeData>) => void;
  onCreateTrigger: (trigger: any) => void;
  onDeleteTrigger: (triggerId: string) => void;
}

const TriggerNode: React.FC<NodeProps<TriggerNodeData>> = ({ data }) => {
  const getStatusColor = () => {
    switch (data.status) {
      case 'active': return '#10b981';
      case 'inactive': return '#6b7280';
      case 'error': return '#ef4444';
      default: return '#6b7280';
    }
  };

  return (
    <div
      className="min-w-[200px] bg-white shadow-lg rounded-lg border-2"
      style={{ borderColor: getStatusColor() }}
    >
      <Handle type="target" position={Position.Left} />

      <div className="p-4">
        <div className="text-sm font-semibold mb-1">{data.label}</div>
        <div className="text-xs text-gray-600 mb-2">{data.triggerType}</div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="font-medium">Freq:</span> {data.frequency}
          </div>
          <div>
            <span className="font-medium">Cond:</span> {data.condition}
          </div>
        </div>

        {data.successRate !== undefined && (
          <div className="mt-2 text-xs">
            <span className="font-medium">Success:</span> {data.successRate}%
          </div>
        )}

        {data.lastRun && (
          <div className="mt-1 text-xs text-gray-500">
            Last: {new Date(data.lastRun).toLocaleString()}
          </div>
        )}
      </div>

      <Handle type="source" position={Position.Right} />
    </div>
  );
};

const nodeTypes = {
  triggerNode: TriggerNode,
};

const AutonomousTriggerFlow: React.FC<AutonomousTriggerFlowProps> = ({
  workflows,
  triggers,
  onTriggerChange,
  onCreateTrigger,
  onDeleteTrigger,
}) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedTrigger, setSelectedTrigger] = useState<string | null>(null);

  // Transform triggers to React Flow nodes
  useEffect(() => {
    const newNodes: Node[] = triggers.map((trigger, index) => ({
      id: trigger.id,
      type: 'triggerNode',
      position: {
        x: 100 + (index % 3) * 300,
        y: 100 + Math.floor(index / 3) * 150
      },
      data: {
        label: trigger.name || trigger.id,
        triggerType: trigger.triggerType || 'manual',
        frequency: trigger.schedule || 'On-demand',
        condition: trigger.conditions?.[0]?.type || 'None',
        status: trigger.status || 'active',
        lastRun: trigger.metadata?.lastRunAt,
        nextRun: trigger.schedule ? 'Scheduled' : 'Manual',
        successRate: trigger.metadata?.successRate || 100,
      },
    }));

    const newEdges: Edge[] = workflows.map((workflow, index) => ({
      id: `e-wf-${workflow.id}-${index}`,
      source: triggers.find(t => t.workflowId === workflow.id)?.id || '',
      target: `workflow-${workflow.id}`,
      animated: true,
      style: { stroke: '#3b82f6' },
    }));

    setNodes(newNodes);
    setEdges(newEdges);
  }, [triggers, workflows]);

  const onConnect = useCallback(
    (params: any) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const onNodeClick = useCallback((event: React.MouseEvent, node:
