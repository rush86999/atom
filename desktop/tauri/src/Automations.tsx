import React, { useState, useMemo, useRef, useCallback, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
import ReactFlow, {
  ReactFlowProvider,
  addEdge,
  useNodesState,
  useEdgesState,
  Controls,
  Connection,
  Edge,
} from 'reactflow';
import 'reactflow/dist/style.css';

import GmailTriggerNode from '../../src/ui-shared/components/workflows/nodes/GmailTriggerNode';
import GoogleCalendarNode from '../../src/ui-shared/components/workflows/nodes/GoogleCalendarNode';
import NotionNode from '../../src/ui-shared/components/workflows/nodes/NotionNode';
import AiTaskNode from '../../src/ui-shared/components/workflows/nodes/AiTaskNode';
import FlattenNode from '../../src/ui-shared/components/workflows/nodes/FlattenNode';
import Sidebar from '../../src/ui-shared/components/workflows/Sidebar';

let id = 1;
const getId = () => `${id++}`;

const AutomationsPage = () => {
  const reactFlowWrapper = useRef(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [reactFlowInstance, setReactFlowInstance] = useState(null);
  const [workflows, setWorkflows] = useState([]);

  useEffect(() => {
    const fetchWorkflows = async () => {
      try {
        const data = await invoke('get_workflows');
        setWorkflows(data as any[]);
      } catch (error) {
        console.error('Failed to fetch workflows', error);
      }
    };
    fetchWorkflows();
  }, []);

  const handleLoadWorkflow = (workflow) => {
    const { nodes, edges } = workflow.definition;
    setNodes(nodes || []);
    setEdges(edges || []);
  };

  const handleTriggerWorkflow = async (workflowId) => {
    try {
      await invoke('trigger_workflow', { workflowId });
      console.log('Workflow triggered successfully');
    } catch (error) {
      console.error('Failed to trigger workflow', error);
    }
  };

  const onConnect = (params: Edge | Connection) => setEdges((els) => addEdge(params, els));

  const nodeTypes = useMemo(
    () => ({
      gmailTrigger: GmailTriggerNode,
      googleCalendarTrigger: GoogleCalendarNode,
      notionAction: NotionNode,
      aiTask: AiTaskNode,
      flatten: FlattenNode,
    }),
    []
  );

  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event) => {
      event.preventDefault();

      const reactFlowBounds = reactFlowWrapper.current.getBoundingClientRect();
      const type = event.dataTransfer.getData('application/reactflow');

      if (typeof type === 'undefined' || !type) {
        return;
      }

      const position = reactFlowInstance.project({
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      });
      const newNode = {
        id: getId(),
        type,
        position,
        data: {
          label: `${type} node`,
          onChange: (newData) => {
            setNodes((nds) =>
              nds.map((node) => {
                if (node.id === newNode.id) {
                  return { ...node, data: { ...node.data, ...newData } };
                }
                return node;
              })
            );
          },
        },
      };

      setNodes((nds) => nds.concat(newNode));
    },
    [reactFlowInstance, setNodes]
  );

  const handleSave = async () => {
    const workflow = {
      name: 'My Workflow',
      definition: {
        nodes,
        edges,
      },
      enabled: true,
    };

    try {
      await invoke('save_workflow', { workflow });
      console.log('Workflow saved successfully');
    } catch (error) {
      console.error('Failed to save workflow', error);
    }
  };

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      <ReactFlowProvider>
        <Sidebar
          workflows={workflows}
          onLoadWorkflow={handleLoadWorkflow}
          onTriggerWorkflow={handleTriggerWorkflow}
        />
        <div style={{ flex: 1 }} ref={reactFlowWrapper}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onInit={setReactFlowInstance}
            onDrop={onDrop}
            onDragOver={onDragOver}
            nodeTypes={nodeTypes}
          >
            <Controls />
          </ReactFlow>
        </div>
      </ReactFlowProvider>
      <button onClick={handleSave} style={{ position: 'absolute', top: 10, right: 10 }}>
        Save Workflow
      </button>
    </div>
  );
};

export default AutomationsPage;
