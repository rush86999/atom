import React, { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  const [databaseId, setDatabaseId] = useState(data.databaseId || '');
  const [triggerType, setTriggerType] = useState(data.triggerType || 'page_created');
  const [filterProperty, setFilterProperty] = useState(data.filterProperty || '');
  const [filterValue, setFilterValue] = useState(data.filterValue || '');
  const [schedule, setSchedule] = useState(data.schedule || '');
  const [maxResults, setMaxResults] = useState(data.maxResults || 10);

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
          background: '#000000',
          borderRadius: '50%',
          marginRight: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          fontSize: '12px',
          fontWeight: 'bold'
        }}>
          N
        </div>
        <strong>Notion Trigger</strong>
      </div>

      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px', fontWeight: '500' }}>Database ID:</label>
        <input
          type="text"
          value={databaseId}
          onChange={(e) => {
            setDatabaseId(e.target.value);
            onConfigChange('databaseId', e.target.value);
          }}
          style={{ width: '100%', padding: '6px', border: '1px solid #ddd', borderRadius: '3px' }}
          placeholder="Database ID or URL"
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
          <option value="page_created">Page Created</option>
          <option value="page_updated">Page Updated</option>
          <option value="property_changed">Property Changed</option>
          <option value="database_updated">Database Updated</option>
          <option value="new_comment">New Comment</option>
        </select>
      </div>

      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px', fontWeight: '500' }}>Filter Property:</label>
        <input
          type="text"
          value={filterProperty}
          onChange={(e) => {
            setFilterProperty(e.target.value);
            onConfigChange('filterProperty', e.target.value);
          }}
          style={{ width: '100%', padding: '6px', border: '1px solid #ddd', borderRadius: '3px' }}
          placeholder="e.g., Status, Priority, Type"
        />
      </div>

      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px', fontWeight: '500' }}>Filter Value:</label>
        <input
          type="text"
          value={filterValue}
          onChange={(e) => {
            setFilterValue(e.target.value);
            onConfigChange('filterValue', e.target.value);
          }}
          style={{ width: '100%', padding: '6px', border: '1px solid #ddd', borderRadius: '3px' }}
          placeholder="e.g., Done, High, Bug"
        />
      </div>

      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px', fontWeight: '500' }}>Max Results:</label>
        <input
          type="number"
          value={maxResults}
          onChange={(e) => {
            const val = parseInt(e.target.value, 10) || 10;
            setMaxResults(val);
            onConfigChange('maxResults', val);
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
          placeholder="e.g., 0 */2 * * * (every 2 hours)"
        />
      </div>

      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
});

export const schema = {
  outputs: [
    { id: 'pages', label: 'Pages List', type: 'array' },
    { id: 'page_count', label: 'Page Count', type: 'number' },
    { id: 'latest_page', label: 'Latest Page', type: 'object' },
    { id: 'database_info', label: 'Database Info', type: 'object' },
  ],
};
