import { useState, useMemo, useRef, useCallback, useEffect } from 'react';
import {
  addEdge,
  useNodesState,
  useEdgesState,
  Connection,
  Edge,
} from 'reactflow';

let id = 1;
const getId = () => `${id++}`;

export const useWorkflows = (api) => {
  const reactFlowWrapper = useRef(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [reactFlowInstance, setReactFlowInstance] = useState(null);
  const [workflows, setWorkflows] = useState([]);

  useEffect(() => {
    const fetchWorkflows = async () => {
      try {
        const data = await api.getWorkflows();
        setWorkflows(data || []);
      } catch (error) {
        console.error('Failed to fetch workflows', error);
      }
    };
    fetchWorkflows();
  }, [api]);

  const handleLoadWorkflow = (workflow) => {
    const { nodes, edges } = workflow.definition;
    setNodes(nodes || []);
    setEdges(edges || []);
  };

  const onConnect = (params: Edge | Connection) => setEdges((els) => addEdge(params, els));

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
    const name = window.prompt("Enter a name for your workflow:");
    if (!name) {
      return;
    }
    const workflow = {
      name,
      definition: { nodes, edges },
      enabled: true,
    };
    try {
      await api.saveWorkflow(workflow);
      console.log('Workflow saved successfully');
      // Refetch workflows to update the list
      const data = await api.getWorkflows();
      setWorkflows(data || []);
    } catch (error) {
      console.error('Failed to save workflow', error);
    }
  };

  const handleTriggerWorkflow = async (workflowId) => {
    try {
      await api.triggerWorkflow(workflowId);
      console.log('Workflow triggered successfully');
    } catch (error) {
      console.error('Failed to trigger workflow', error);
    }
  };

  return {
    reactFlowWrapper,
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onConnect,
    onInit: setReactFlowInstance,
    onDrop,
    onDragOver,
    workflows,
    handleLoadWorkflow,
    handleSave,
    handleTriggerWorkflow,
  };
};
