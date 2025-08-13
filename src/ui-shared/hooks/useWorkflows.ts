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
  const [currentWorkflowId, setCurrentWorkflowId] = useState(null);
  const [dataMapperState, setDataMapperState] = useState({
    isOpen: false,
    sourceNode: null,
    targetNode: null,
    edgeParams: null,
  });

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
    setCurrentWorkflowId(workflow.id);
  };

  const onConnect = (params: Edge | Connection) => {
    const sourceNode = nodes.find(n => n.id === params.source);
    const targetNode = nodes.find(n => n.id === params.target);

    if (sourceNode && targetNode) {
      setDataMapperState({
        isOpen: true,
        sourceNode,
        targetNode,
        edgeParams: params,
      });
    }
  };

  const handleSaveMapping = (mappings) => {
    const { edgeParams } = dataMapperState;
    if (edgeParams) {
      const newEdge = { ...edgeParams, data: { mappings } };
      setEdges((els) => addEdge(newEdge, els));
    }
    setDataMapperState({ isOpen: false, sourceNode: null, targetNode: null, edgeParams: null });
  };

  const handleCancelMapping = () => {
    setDataMapperState({ isOpen: false, sourceNode: null, targetNode: null, edgeParams: null });
  };

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
      if (currentWorkflowId) {
        await api.updateWorkflow(currentWorkflowId, workflow);
      } else {
        await api.saveWorkflow(workflow);
      }
      console.log('Workflow saved successfully');
      // Refetch workflows to update the list
      const data = await api.getWorkflows();
      setWorkflows(data || []);
      setCurrentWorkflowId(null);
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

  const handleDeleteWorkflow = async (workflowId) => {
    if (window.confirm("Are you sure you want to delete this workflow?")) {
      try {
        await api.deleteWorkflow(workflowId);
        console.log('Workflow deleted successfully');
        // Refetch workflows to update the list
        const data = await api.getWorkflows();
        setWorkflows(data || []);
      } catch (error) {
        console.error('Failed to delete workflow', error);
      }
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
    handleDeleteWorkflow,
    dataMapperState,
    handleSaveMapping,
    handleCancelMapping,
  };
};
