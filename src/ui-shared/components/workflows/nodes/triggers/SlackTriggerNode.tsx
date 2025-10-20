import React, { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  const [channelId, setChannelId] = useState(data.channelId || '');
  const [triggerType, setTriggerType] = useState(data.triggerType || 'new_message');
  const [keywordFilter, setKeywordFilter] = useState(data.keywordFilter || '');
  const [userFilter, setUserFilter] = useState(data.userFilter || '');
  const [schedule, setSchedule] = useState(data.schedule || '');
  const [maxMessages, setMaxMessages] = useState(data.maxMessages || 10);

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
          background: '#4A154B',
          borderRadius: '50%',
          marginRight: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          fontSize: '12px',
          fontWeight: 'bold'
        }}>
          S
        </div>
        <strong>Slack Trigger</strong>
      </div>

      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px', fontWeight: '500' }}>Channel ID:</label>
        <input
          type="text"
          value={channelId}
          onChange={(e) => {
            setChannelId(e.target.value);
            onConfigChange('channelId', e.target.value);
          }}
          style={{ width: '100%', padding: '6px', border: '1px solid #ddd', borderRadius: '3px' }}
          placeholder="C1234567890 or #general"
        />
      </div>

      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px', fontWeight: '500' }}>Trigger Type:</label>
        <select
          value={triggerType}
          onChange={(e) => {
            setTriggerType(e.target.value);
            onConfigChange('triggerType', e.target.value);
          }}
          style={{ width: '100%', padding: '6px', border: '1px solid #ddd', borderRadius: '3px' }}
        >
          <option value="new_message">New Message</option>
          <option value="message_reaction">Message Reaction</option>
          <option value="thread_reply">Thread Reply</option>
          <option value="user_joined">User Joined Channel</option>
          <option value="user_left">User Left Channel</option>
          <option value="channel_created">Channel Created</option>
        </select>
      </div>

      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px', fontWeight: '500' }}>Keyword Filter:</label>
        <input
          type="text"
          value={keywordFilter}
          onChange={(e) => {
            setKeywordFilter(e.target.value);
            onConfigChange('keywordFilter', e.target.value);
          }}
          style={{ width: '100%', padding: '6px', border: '1px solid #ddd', borderRadius: '3px' }}
          placeholder="e.g., urgent, help, question"
        />
      </div>

      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px', fontWeight: '500' }}>User Filter:</label>
        <input
          type="text"
          value={userFilter}
          onChange={(e) => {
            setUserFilter(e.target.value);
            onConfigChange('userFilter', e.target.value);
          }}
          style={{ width: '100%', padding: '6px', border: '1px solid #ddd', borderRadius: '3px' }}
          placeholder="e.g., U1234567890 or @username"
        />
      </div>

      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px', fontWeight: '500' }}>Max Messages:</label>
        <input
          type="number"
          value={maxMessages}
          onChange={(e) => {
            const val = parseInt(e.target.value, 10) || 10;
            setMaxMessages(val);
            onConfigChange('maxMessages', val);
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
          placeholder="e.g., */5 * * * * (every 5 minutes)"
        />
      </div>

      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
});

export const schema = {
  outputs: [
    { id: 'messages', label: 'Messages List', type: 'array' },
    { id: 'message_count', label: 'Message Count', type: 'number' },
    { id: 'latest_message', label: 'Latest Message', type: 'object' },
    { id: 'channel_info', label: 'Channel Info', type: 'object' },
  ],
};
