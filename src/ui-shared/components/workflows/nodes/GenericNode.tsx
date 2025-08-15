import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

const renderInput = (key, param, value, onValueChange) => {
  const handleChange = (e) => {
    let newValue = e.target.value;
    if (param.type === 'number') {
      newValue = parseInt(newValue, 10);
    } else if (param.type === 'boolean') {
        newValue = e.target.checked;
    }
    onValueChange(key, newValue);
  };

  switch (param.type) {
    case 'string':
      return (
        <input
          type="text"
          value={value || ''}
          onChange={handleChange}
          placeholder={param.default}
          style={{ width: '100%', padding: '5px' }}
        />
      );
    case 'number':
      return (
        <input
          type="number"
          value={value || ''}
          onChange={handleChange}
          placeholder={param.default}
          style={{ width: '100%', padding: '5px' }}
        />
      );
    case 'boolean':
        return (
            <input
            type="checkbox"
            checked={value || false}
            onChange={handleChange}
            />
        );
    default:
      return (
        <input
          type="text"
          value={value || ''}
          onChange={handleChange}
          placeholder={param.default}
          style={{ width: '100%', padding: '5px' }}
        />
      );
  }
};

export default memo(({ data }) => {
  const { name, service, description, inputSchema, values, onChange } = data;

  const onValueChange = (key, newValue) => {
    if (onChange) {
      const newValues = { ...values, [key]: newValue };
      onChange({ ...data, values: newValues });
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
        <strong>{name}</strong>
        <div style={{ fontSize: '10px', color: '#777' }}>{service}</div>
        {description && <p style={{ fontSize: '12px', color: '#555' }}>{description}</p>}
      </div>
      <div style={{ marginTop: '10px' }}>
        {inputSchema?.properties && Object.entries(inputSchema.properties).map(([key, param]: [string, any]) => (
          <div key={key} style={{ marginTop: '10px' }}>
            <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>{param.title}</label>
            {renderInput(key, param, values?.[key], onValueChange)}
          </div>
        ))}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
});
