import React, { useMemo } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
import ReactFlow, {
  ReactFlowProvider,
  Controls,
} from 'reactflow';
import 'reactflow/dist/style.css';

import GmailTriggerNode from '../../src/ui-shared/components/workflows/nodes/GmailTriggerNode';
import GoogleCalendarNode from '../../src/ui-shared/components/workflows/nodes/GoogleCalendarNode';
import NotionNode from '../../src/ui-shared/components/workflows/nodes/NotionNode';
import AiTaskNode from '../../src/ui-shared/components/workflows/nodes/AiTaskNode';
import FlattenNode from '../../src/ui-shared/components/workflows/nodes/FlattenNode';
import Sidebar from '../../src/ui-shared/components/workflows/Sidebar';
import { useWorkflows } from '../../src/ui-shared/hooks/useWorkflows';
import DataMapper from '../../src/ui-shared/components/workflows/DataMapper';

const desktopApi = {
  getWorkflows: async () => {
    return invoke('get_workflows');
  },
  saveWorkflow: async (workflow) => {
    await invoke('save_workflow', { workflow });
  },
  triggerWorkflow: async (workflowId) => {
    await invoke('trigger_workflow', { workflowId });
  },
  updateWorkflow: async (workflowId, workflow) => {
    await invoke('update_workflow', { workflowId, workflow });
  },
  deleteWorkflow: async (workflowId) => {
    await invoke('delete_workflow', { workflowId });
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
  } = useWorkflows(desktopApi);

  const nodeTypes = useMemo(
    () => ({
      gmailTrigger: GmailTriggerNode,
      googleCalendarAction: GoogleCalendarNode,
      notionAction: NotionNode,
      aiTask: AiTaskNode,
      flatten: FlattenNode,
    }),
    []
  );

  const nodeSchemas = {
    gmailTrigger: GmailTriggerNode.schema,
    googleCalendarAction: GoogleCalendarNode.schema,
    notionAction: NotionNode.schema,
    aiTask: AiTaskNode.schema,
    flatten: FlattenNode.schema,
  };

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
          sourceSchema={nodeSchemas[dataMapperState.sourceNode.type]}
          targetSchema={nodeSchemas[dataMapperState.targetNode.type]}
          onSave={handleSaveMapping}
          onCancel={handleCancelMapping}
        />
      )}
    </div>
  );
};

export default AutomationsPage;
