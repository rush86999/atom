import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  return (
    <div style={{
      background: '#f0f0f0',
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
        <strong>Flatten List</strong>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: '#555' }}
      />
    </div>
  );
});
