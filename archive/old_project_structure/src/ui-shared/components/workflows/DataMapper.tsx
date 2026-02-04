import React, { useState } from 'react';

const DataMapper = ({ sourceSchema, targetSchema, onSave, onCancel }) => {
  const [mappings, setMappings] = useState([]);

  const handleMappingChange = (targetId, sourceId) => {
    const newMappings = mappings.filter(m => m.target !== targetId);
    if (sourceId) {
      newMappings.push({ source: sourceId, target: targetId });
    }
    setMappings(newMappings);
  };

  return (
    <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
      <div style={{ background: 'white', padding: 20, borderRadius: 5 }}>
        <h2>Map Data</h2>
        <div style={{ display: 'flex' }}>
          <div style={{ marginRight: 20 }}>
            <h4>Source Outputs</h4>
            {sourceSchema.outputs.map(output => <div key={output.id}>{output.label}</div>)}
          </div>
          <div>
            <h4>Target Inputs</h4>
            {targetSchema.inputs.map(input => (
              <div key={input.id}>
                <span>{input.label}: </span>
                <select onChange={(e) => handleMappingChange(input.id, e.target.value)}>
                  <option value="">-- Select Source --</option>
                  {sourceSchema.outputs.map(output => (
                    <option key={output.id} value={output.id}>{output.label}</option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </div>
        <div style={{ marginTop: 20 }}>
          <button onClick={() => onSave(mappings)}>Save</button>
          <button onClick={onCancel} style={{ marginLeft: 10 }}>Cancel</button>
        </div>
      </div>
    </div>
  );
};

export default DataMapper;
