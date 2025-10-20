import React, { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  const [calendarId, setCalendarId] = useState(data.calendarId || 'primary');
  const [eventType, setEventType] = useState(data.eventType || 'all');
  const [timeRange, setTimeRange] = useState(data.timeRange || 'upcoming');
  const [schedule, setSchedule] = useState(data.schedule || '');
  const [maxEvents, setMaxEvents] = useState(data.maxEvents || 10);

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
      width: 280,
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
    }}>
      <Handle type="target" position={Position.Top} style={{ background: '#555' }} />
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '10px' }}>
        <div style={{
          width: '20px',
          height: '20px',
          background: '#4285F4',
          borderRadius: '50%',
          marginRight: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          fontSize: '12px',
          fontWeight: 'bold'
        }}>
          G
        </div>
        <strong>Google Calendar Trigger</strong>
      </div>

      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px', fontWeight: '500' }}>Calendar ID:</label>
        <input
          type="text"
          value={calendarId}
          onChange={(e) => {
            setCalendarId(e.target.value);
            onConfigChange('calendarId', e.target.value);
          }}
          style={{ width: '100%', padding: '6px', border: '1px solid #ddd', borderRadius: '3px' }}
          placeholder="primary"
        />
      </div>

      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px', fontWeight: '500' }}>Event Type:</label>
        <select
          value={eventType}
          onChange={(e) => {
            setEventType(e.target.value);
            onConfigChange('eventType', e.target.value);
          }}
          style={{ width: '100%', padding: '6px', border: '1px solid #ddd', borderRadius: '3px' }}
        >
          <option value="all">All Events</option>
          <option value="created">New Events</option>
          <option value="updated">Updated Events</option>
          <option value="cancelled">Cancelled Events</option>
          <option value="starting_soon">Starting Soon</option>
        </select>
      </div>

      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px', fontWeight: '500' }}>Time Range:</label>
        <select
          value={timeRange}
          onChange={(e) => {
            setTimeRange(e.target.value);
            onConfigChange('timeRange', e.target.value);
          }}
          style={{ width: '100%', padding: '6px', border: '1px solid #ddd', borderRadius: '3px' }}
        >
          <option value="upcoming">Upcoming Events</option>
          <option value="today">Today's Events</option>
          <option value="tomorrow">Tomorrow's Events</option>
          <option value="this_week">This Week</option>
          <option value="next_week">Next Week</option>
        </select>
      </div>

      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px', fontWeight: '500' }}>Max Events:</label>
        <input
          type="number"
          value={maxEvents}
          onChange={(e) => {
            const val = parseInt(e.target.value, 10) || 10;
            setMaxEvents(val);
            onConfigChange('maxEvents', val);
          }}
          style={{ width: '100%', padding: '6px', border: '1px solid #ddd', borderRadius: '3px' }}
          min="1"
          max="50"
        />
      </div>

      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px', fontWeight: '500' }}>Schedule (Cron):</label>
        <input
          type="text"
          value={schedule}
          onChange={(e) => {
            setSchedule(e.target.value);
            onConfigChange('schedule', e.target.value);
          }}
          style={{ width: '100%', padding: '6px', border: '1px solid #ddd', borderRadius: '3px' }}
          placeholder="e.g., 0 9 * * * (9 AM daily)"
        />
      </div>

      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
});

export const schema = {
  outputs: [
    { id: 'events', label: 'Events List', type: 'array' },
    { id: 'event_count', label: 'Event Count', type: 'number' },
    { id: 'next_event', label: 'Next Event', type: 'object' },
  ],
};
