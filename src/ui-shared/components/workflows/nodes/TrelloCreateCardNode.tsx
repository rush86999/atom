import React, { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  const [listId, setListId] = useState(data.listId || '');
  const [cardName, setCardName] = useState(data.cardName || '');

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
        <strong>Trello: Create Card</strong>
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>List ID:</label>
        <input
          type="text"
          value={listId}
          onChange={(e) => {
            setListId(e.target.value);
            onConfigChange('listId', e.target.value);
          }}
          style={{ width: '100%', padding: '5px' }}
          placeholder="e.g., 5f9b3b3b3b3b3b3b3b3b3b3b"
        />
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>Card Name:</label>
        <input
          type="text"
          value={cardName}
          onChange={(e) => {
            setCardName(e.target.value);
            onConfigChange('cardName', e.target.value);
          }}
          style={{ width: '100%', padding: '5px' }}
          placeholder="e.g., My new card"
        />
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
});

export const schema = {
  inputs: [
    { id: 'cardName', label: 'Card Name', type: 'string' },
  ],
  outputs: [],
};
