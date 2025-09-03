import React, { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  const [userId, setUserId] = useState(data.userId || '');
  const [query, setQuery] = useState(data.query || 'is:unread');
  const [maxResults, setMaxResults] = useState(data.maxResults || 10);
  const [schedule, setSchedule] = useState(data.schedule || '');

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
        <strong>Gmail Trigger</strong>
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>User ID:</label>
        <input
          type="text"
          value={userId}
          onChange={(e) => {
            setUserId(e.target.value);
            onConfigChange('userId', e.target.value);
          }}
          style={{ width: '100%', padding: '5px' }}
        />
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>Query:</label>
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            onConfigChange('query', e.target.value);
          }}
          style={{ width: '100%', padding: '5px' }}
        />
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>Max Results:</label>
        <input
          type="number"
          value={maxResults}
          onChange={(e) => {
            const val = parseInt(e.target.value, 10);
            setMaxResults(val);
            onConfigChange('maxResults', val);
          }}
          style={{ width: '100%', padding: '5px' }}
        />
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>Schedule (Cron):</label>
        <input
          type="text"
          value={schedule}
          onChange={(e) => {
            setSchedule(e.target.value);
            onConfigChange('schedule', e.target.value);
          }}
          style={{ width: '100%', padding: '5px' }}
          placeholder="e.g., 0 5 * * *"
        />
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
});

export const schema = {
  outputs: [
    { id: 'email_body', label: 'Email Body', type: 'string' },
    { id: 'subject', label: 'Subject', type: 'string' },
    { id: 'sender', label: 'Sender', type: 'string' },
  ],
};
