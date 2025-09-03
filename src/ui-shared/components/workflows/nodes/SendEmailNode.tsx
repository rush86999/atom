import React, { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  const [to, setTo] = useState(data.to || '');
  const [subject, setSubject] = useState(data.subject || '');
  const [body, setBody] = useState(data.body || '');

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
        <strong>Send Email</strong>
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>To:</label>
        <input
          type="email"
          value={to}
          onChange={(e) => {
            setTo(e.target.value);
            onConfigChange('to', e.target.value);
          }}
          style={{ width: '100%', padding: '5px' }}
          placeholder="e.g., recipient@example.com"
        />
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>Subject:</label>
        <input
          type="text"
          value={subject}
          onChange={(e) => {
            setSubject(e.target.value);
            onConfigChange('subject', e.target.value);
          }}
          style={{ width: '100%', padding: '5px' }}
        />
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>Body:</label>
        <textarea
          value={body}
          onChange={(e) => {
            setBody(e.target.value);
            onConfigChange('body', e.target.value);
          }}
          style={{ width: '100%', padding: '5px', height: '100px' }}
        />
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
});

export const schema = {
  inputs: [
    { id: 'to', label: 'To', type: 'string' },
    { id: 'subject', label: 'Subject', type: 'string' },
    { id: 'body', label: 'Body', type: 'string' },
  ],
  outputs: [],
};
