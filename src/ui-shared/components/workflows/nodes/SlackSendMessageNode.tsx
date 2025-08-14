import React, { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  const [channelId, setChannelId] = useState(data.channelId || '');
  const [text, setText] = useState(data.text || '');

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
        <strong>Slack: Send Message</strong>
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>Channel ID:</label>
        <input
          type="text"
          value={channelId}
          onChange={(e) => {
            setChannelId(e.target.value);
            onConfigChange('channelId', e.target.value);
          }}
          style={{ width: '100%', padding: '5px' }}
          placeholder="e.g., C12345678"
        />
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>Message Text:</label>
        <textarea
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            onConfigChange('text', e.target.value);
          }}
          style={{ width: '100%', padding: '5px', height: '80px' }}
          placeholder="Enter your message here"
        />
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
});

export const schema = {
  inputs: [
    { id: 'text', label: 'Message Text', type: 'string' },
  ],
  outputs: [],
};
