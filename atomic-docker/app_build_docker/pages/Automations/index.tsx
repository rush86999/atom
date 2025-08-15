import React, { useMemo } from 'react';
import ReactFlow, {
  ReactFlowProvider,
  Controls,
} from 'reactflow';
import 'reactflow/dist/style.css';

import GenericNode from '../../../../src/ui-shared/components/workflows/nodes/GenericNode';
import Sidebar from '../../../../src/ui-shared/components/workflows/Sidebar';
import { useWorkflows } from '../../../../src/ui-shared/hooks/useWorkflows';
import DataMapper from '../../../../src/ui-shared/components/workflows/DataMapper';

const webApi = {
  getWorkflows: async () => {
    const response = await fetch('http://localhost:8003/workflows/');
    return response.json();
  },
  saveWorkflow: async (workflow) => {
    await fetch('http://localhost:8003/workflows/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(workflow),
    });
  },
  triggerWorkflow: async (workflowId) => {
    await fetch(`http://localhost:8003/workflows/${workflowId}/trigger`, {
      method: 'POST',
    });
  },
  updateWorkflow: async (workflowId, workflow) => {
    await fetch(`http://localhost:8003/workflows/${workflowId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(workflow),
    });
  },
  deleteWorkflow: async (workflowId) => {
    await fetch(`http://localhost:8003/workflows/${workflowId}`, {
      method: 'DELETE',
    });
  },
};

const AutomationsPage = () => {
  const {
    reactFlowWrapper,
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onConnect,
    onInit,
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
  } = useWorkflows(webApi);

  const nodeTypes = useMemo(
    () => ({
      genericNode: GenericNode,
    }),
    []
  );

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      <ReactFlowProvider>
        <Sidebar
          workflows={workflows}
          onLoadWorkflow={handleLoadWorkflow}
          onTriggerWorkflow={handleTriggerWorkflow}
          onDeleteWorkflow={handleDeleteWorkflow}
        />
        <div style={{ flex: 1 }} ref={reactFlowWrapper}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onInit={onInit}
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
      {dataMapperState.isOpen && (
        <DataMapper
          sourceSchema={dataMapperState.sourceNode.data.outputSchema}
          targetSchema={dataMapperState.targetNode.data.inputSchema}
          onSave={handleSaveMapping}
          onCancel={handleCancelMapping}
        />
      )}
    </div>
  );
};

export default AutomationsPage;
