import React, { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  const [databaseId, setDatabaseId] = useState(data.databaseId || '');
  const [properties, setProperties] = useState(data.properties || []);

  const onConfigChange = () => {
    if (data.onChange) {
      data.onChange({ ...data, databaseId, properties });
    }
  };

  const handlePropertyChange = (index, field, value) => {
    const newProperties = [...properties];
    newProperties[index][field] = value;
    setProperties(newProperties);
    onConfigChange();
  };

  const addProperty = () => {
    setProperties([...properties, { key: '', value: '' }]);
  };

  const removeProperty = (index) => {
    const newProperties = [...properties];
    newProperties.splice(index, 1);
    setProperties(newProperties);
    onConfigChange();
  };

  return (
    <div style={{
      background: '#fff',
      border: '1px solid #ddd',
      padding: '10px 15px',
      borderRadius: '5px',
      width: 300,
    }}>
      <Handle type="target" position={Position.Top} style={{ background: '#555' }} />
      <div>
        <strong>Notion Action</strong>
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>
          Database ID:
        </label>
        <input
          type="text"
          value={databaseId}
          onChange={(e) => {
            setDatabaseId(e.target.value);
            onConfigChange();
          }}
          style={{ width: '100%', padding: '5px' }}
        />
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>
          Properties:
        </label>
        {properties.map((prop, index) => (
          <div key={index} style={{ display: 'flex', marginBottom: '5px' }}>
            <input
              type="text"
              placeholder="Key"
              value={prop.key}
              onChange={(e) => handlePropertyChange(index, 'key', e.target.value)}
              style={{ width: '40%', padding: '5px' }}
            />
            <input
              type="text"
              placeholder="Value"
              value={prop.value}
              onChange={(e) => handlePropertyChange(index, 'value', e.target.value)}
              style={{ width: '40%', padding: '5px', marginLeft: '5px' }}
            />
            <button onClick={() => removeProperty(index)} style={{ width: '15%', marginLeft: '5px' }}>
              X
            </button>
          </div>
        ))}
        <button onClick={addProperty} style={{ width: '100%', marginTop: '5px' }}>
          Add Property
        </button>
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
});

export const schema = {
  inputs: [
    { id: 'task_name', label: 'Task Name', type: 'string' },
  ],
};
