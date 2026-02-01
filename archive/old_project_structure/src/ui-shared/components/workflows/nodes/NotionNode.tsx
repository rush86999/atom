import React, { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  const [databaseId, setDatabaseId] = useState(data.databaseId || '');

  const onDatabaseIdChange = (evt) => {
    const newId = evt.target.value;
    setDatabaseId(newId);
    if (data.onChange) {
      data.onChange({ ...data, databaseId: newId });
    }
  };

  return (
    <div style={{
      background: '#fff',
      border: '1px solid #ddd',
      padding: '10px 15px',
      borderRadius: '5px',
      width: 200,
    }}>
      <Handle type="target" position={Position.Top} style={{ background: '#555' }} />
      <div>
        <strong>Notion Action</strong>
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>
          Database ID:
        </label>
        <input
          type="text"
          value={databaseId}
          onChange={onDatabaseIdChange}
          style={{ width: '100%', padding: '5px' }}
        />
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
});

export const schema = {
  inputs: [
    { id: 'task_name', label: 'Task Name', type: 'string' },
  ],
};
