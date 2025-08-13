import React, { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  const [userId, setUserId] = useState(data.userId || '');
  const [calendarId, setCalendarId] = useState(data.calendarId || 'primary');

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
        <strong>Google Calendar Action</strong>
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
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>Calendar ID:</label>
        <input
          type="text"
          value={calendarId}
          onChange={(e) => {
            setCalendarId(e.target.value);
            onConfigChange('calendarId', e.target.value);
          }}
          style={{ width: '100%', padding: '5px' }}
        />
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
});

export const schema = {
  inputs: [
    { id: 'summary', label: 'Summary', type: 'string' },
    { id: 'description', label: 'Description', type: 'string' },
    { id: 'startDateTime', label: 'Start DateTime', type: 'string' },
    { id: 'endDateTime', label: 'End DateTime', type: 'string' },
    { id: 'timezone', label: 'Timezone', type: 'string' },
  ],
};
