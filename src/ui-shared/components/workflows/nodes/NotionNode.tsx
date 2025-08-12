import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  return (
    <div style={{
      background: '#fff',
      border: '1px solid #ddd',
      padding: '10px 15px',
      borderRadius: '5px',
      width: 150,
    }}>
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: '#555' }}
      />
      <div>
        <strong>Notion</strong>
      </div>
      <div style={{ marginTop: '5px' }}>
        <label style={{ fontSize: '12px' }}>Create Page</label>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: '#555' }}
      />
    </div>
  );
});
