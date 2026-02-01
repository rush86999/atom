import React, { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  const [summary, setSummary] = useState(data.summary || '');
  const [dateTime, setDateTime] = useState(data.dateTime || '');
  const [minutesBefore, setMinutesBefore] = useState(data.minutesBefore || 10);

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
        <strong>Reminder</strong>
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>Summary:</label>
        <input
          type="text"
          value={summary}
          onChange={(e) => {
            setSummary(e.target.value);
            onConfigChange('summary', e.target.value);
          }}
          style={{ width: '100%', padding: '5px' }}
        />
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>Date & Time (ISO 8601):</label>
        <input
          type="text"
          value={dateTime}
          onChange={(e) => {
            setDateTime(e.target.value);
            onConfigChange('dateTime', e.target.value);
          }}
          style={{ width: '100%', padding: '5px' }}
          placeholder="e.g., 2024-08-13T14:00:00Z"
        />
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>Minutes Before:</label>
        <input
          type="number"
          value={minutesBefore}
          onChange={(e) => {
            const val = parseInt(e.target.value, 10);
            setMinutesBefore(val);
            onConfigChange('minutesBefore', val);
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
    { id: 'dateTime', label: 'Date & Time', type: 'string' },
  ],
  outputs: [
    { id: 'reminder_id', label: 'Reminder ID', type: 'string' },
  ],
};
