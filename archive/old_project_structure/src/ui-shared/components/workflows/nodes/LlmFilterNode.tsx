import React, { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  const [condition, setCondition] = useState(data.condition || '');

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
        <strong>LLM Filter</strong>
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>Condition (Natural Language):</label>
        <textarea
          value={condition}
          onChange={(e) => {
            setCondition(e.target.value);
            onConfigChange('condition', e.target.value);
          }}
          style={{ width: '100%', padding: '5px', height: '80px' }}
          placeholder="e.g., emails that are from my boss"
        />
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
});

export const schema = {
  inputs: [],
  outputs: [],
};
