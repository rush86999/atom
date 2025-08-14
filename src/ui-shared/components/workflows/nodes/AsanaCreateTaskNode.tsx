import React, { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  const [projectId, setProjectId] = useState(data.projectId || '');
  const [taskName, setTaskName] = useState(data.taskName || '');

  const onConfigChange = (key, value) => {
    const newData = { ...data, [key]: value };
    if (data.onChange) {
      data.onChange(newData);
    }
  };

  return (
    <div style={{
      background: '#fff',
      border: '1px solid #ddd',
      padding: '10px 15px',
      borderRadius: '5px',
      width: 250,
    }}>
      <Handle type="target" position={Position.Top} style={{ background: '#555' }} />
      <div>
        <strong>Asana: Create Task</strong>
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>Project ID:</label>
        <input
          type="text"
          value={projectId}
          onChange={(e) => {
            setProjectId(e.target.value);
            onConfigChange('projectId', e.target.value);
          }}
          style={{ width: '100%', padding: '5px' }}
          placeholder="e.g., 120..."
        />
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>Task Name:</label>
        <input
          type="text"
          value={taskName}
          onChange={(e) => {
            setTaskName(e.target.value);
            onConfigChange('taskName', e.target.value);
          }}
          style={{ width: '100%', padding: '5px' }}
          placeholder="e.g., My new task"
        />
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
});

export const schema = {
  inputs: [
    { id: 'taskName', label: 'Task Name', type: 'string' },
  ],
  outputs: [],
};
