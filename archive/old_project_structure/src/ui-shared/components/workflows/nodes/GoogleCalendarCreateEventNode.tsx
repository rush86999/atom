import React, { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  const [calendarId, setCalendarId] = useState(data.calendarId || 'primary');
  const [summary, setSummary] = useState(data.summary || '');
  const [startTime, setStartTime] = useState(data.startTime || '');
  const [endTime, setEndTime] = useState(data.endTime || '');
  const [timezone, setTimezone] = useState(data.timezone || 'UTC');

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
        <strong>Google Calendar: Create Event</strong>
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
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>Start Time (ISO 8601):</label>
        <input
          type="text"
          value={startTime}
          onChange={(e) => {
            setStartTime(e.target.value);
            onConfigChange('startTime', e.target.value);
          }}
          style={{ width: '100%', padding: '5px' }}
          placeholder="e.g., 2024-08-13T14:00:00Z"
        />
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>End Time (ISO 8601):</label>
        <input
          type="text"
          value={endTime}
          onChange={(e) => {
            setEndTime(e.target.value);
            onConfigChange('endTime', e.target.value);
          }}
          style={{ width: '100%', padding: '5px' }}
          placeholder="e.g., 2024-08-13T15:00:00Z"
        />
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>Timezone:</label>
        <input
          type="text"
          value={timezone}
          onChange={(e) => {
            setTimezone(e.target.value);
            onConfigChange('timezone', e.target.value);
          }}
          style={{ width: '100%', padding: '5px' }}
          placeholder="e.g., America/New_York"
        />
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
});

export const schema = {
  inputs: [
    { id: 'summary', label: 'Summary', type: 'string' },
    { id: 'startTime', label: 'Start Time', type: 'string' },
    { id: 'endTime', label: 'End Time', type: 'string' },
  ],
  outputs: [
    { id: 'event_id', label: 'Event ID', type: 'string' },
    { id: 'html_link', label: 'HTML Link', type: 'string' },
  ],
};
