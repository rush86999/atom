import React, { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  const [conditionType, setConditionType] = useState(data.conditionType || 'field');
  const [fieldPath, setFieldPath] = useState(data.fieldPath || '');
  const [operator, setOperator] = useState(data.operator || 'equals');
  const [value, setValue] = useState(data.value || '');
  const [branches, setBranches] = useState(data.branches || [
    { id: 'true', label: 'True', condition: null },
    { id: 'false', label: 'False', condition: null }
  ]);

  const onChange = (updates) => {
    if (data.onChange) {
      data.onChange({ 
        ...data, 
        conditionType, 
        fieldPath, 
        operator, 
        value, 
        branches,
        ...updates 
      });
    }
  };

  const addBranch = () => {
    const newBranches = [...branches, {
      id: `branch_${branches.length}`,
      label: `Branch ${branches.length + 1}`,
      condition: null
    }];
    setBranches(newBranches);
    onChange({ branches: newBranches });
  };

  const updateBranch = (index, field, val) => {
    const newBranches = [...branches];
    newBranches[index] = { ...newBranches[index], [field]: val };
    setBranches(newBranches);
    onChange({ branches: newBranches });
  };

  const removeBranch = (index) => {
    if (branches.length > 2) {
      const newBranches = branches.filter((_, i) => i !== index);
      setBranches(newBranches);
      onChange({ branches: newBranches });
    }
  };

  return (
    <div style={{
      background: '#fff',
      border: '2px solid #4CAF50',
      padding: '15px',
      borderRadius: '8px',
      width: 320,
      boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
    }}>
      <Handle 
        type="target" 
        position={Position.Top} 
        style={{ background: '#4CAF50', width: 10, height: 10 }} 
      />
      
      <div style={{ marginBottom: '10px' }}>
        <strong style={{ color: '#4CAF50' }}>🔀 Branch Node</strong>
      </div>

      <div style={{ marginBottom: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '3px', fontWeight: 'bold' }}>
          Condition Type:
        </label>
        <select 
          value={conditionType}
          onChange={(e) => {
            setConditionType(e.target.value);
            onChange({ conditionType: e.target.value });
          }}
          style={{ width: '100%', padding: '4px', fontSize: '12px' }}
        >
          <option value="field">Field Comparison</option>
          <option value="expression">JavaScript Expression</option>
          <option value="ai">AI Evaluation</option>
        </select>
      </div>

      {conditionType === 'field' && (
        <>
          <div style={{ marginBottom: '10px' }}>
            <label style={{ fontSize: '12px', display: 'block', marginBottom: '3px' }}>
              Field Path:
            </label>
            <input
              type="text"
              value={fieldPath}
              onChange={(e) => {
                setFieldPath(e.target.value);
                onChange({ fieldPath: e.target.value });
              }}
              placeholder="e.g., user.age, data.status"
              style={{ width: '100%', padding: '4px', fontSize: '12px' }}
            />
          </div>

          <div style={{ marginBottom: '10px' }}>
            <label style={{ fontSize: '12px', display: 'block', marginBottom: '3px' }}>
              Operator:
            </label>
            <select 
              value={operator}
              onChange={(e) => {
                setOperator(e.target.value);
                onChange({ operator: e.target.value });
              }}
              style={{ width: '100%', padding: '4px', fontSize: '12px' }}
            >
              <option value="equals">Equals</option>
              <option value="not_equals">Not Equals</option>
              <option value="greater_than">Greater Than</option>
              <option value="less_than">Less Than</option>
              <option value="contains">Contains</option>
              <option value="starts_with">Starts With</option>
              <option value="ends_with">Ends With</option>
              <option value="is_null">Is Null</option>
              <option value="is_not_null">Is Not Null</option>
            </select>
          </div>

          <div style={{ marginBottom: '10px' }}>
            <label style={{ fontSize: '12px', display: 'block', marginBottom: '3px' }}>
              Value:
            </label>
            <input
              type="text"
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                onChange({ value: e.target.value });
              }}
              placeholder="Comparison value"
              style={{ width: '100%', padding: '4px', fontSize: '12px' }}
            />
          </div>
        </>
      )}

      {conditionType === 'expression' && (
        <div style={{ marginBottom: '10px' }}>
          <label style={{ fontSize: '12px', display: 'block', marginBottom: '3px' }}>
            JavaScript Expression:
          </label>
          <textarea
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              onChange({ value: e.target.value });
            }}
            placeholder="e.g., data.user.age >= 18 && data.user.active === true"
            style={{ width: '100%', height: '60px', padding: '4px', fontSize: '12px' }}
          />
        </div>
      )}

      {conditionType === 'ai' && (
        <div style={{ marginBottom: '10px' }}>
          <label style={{ fontSize: '12px', display: 'block', marginBottom: '3px' }}>
            AI Evaluation Prompt:
          </label>
          <textarea
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              onChange({ value: e.target.value });
            }}
            placeholder="e.g., Based on the customer data, should this be flagged for review? Answer only 'true' or 'false'"
            style={{ width: '100%', height: '60px', padding: '4px', fontSize: '12px' }}
          />
        </div>
      )}

      <div style={{ marginBottom: '10px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '5px' }}>
          <label style={{ fontSize: '12px', fontWeight: 'bold' }}>
            Branch Outputs:
          </label>
          <button
            onClick={addBranch}
            style={{
              fontSize: '10px',
              padding: '2px 6px',
              backgroundColor: '#4CAF50',
              color: 'white',
              border: 'none',
              borderRadius: '3px',
              cursor: 'pointer'
            }}
          >
            + Add
          </button>
        </div>
        
        {branches.map((branch, index) => (
          <div key={branch.id} style={{ 
            display: 'flex', 
            alignItems: 'center', 
            marginBottom: '5px',
            padding: '4px',
            backgroundColor: '#f5f5f5',
            borderRadius: '3px'
          }}>
            <div style={{ flex: 1 }}>
              <input
                type="text"
                value={branch.label}
                onChange={(e) => updateBranch(index, 'label', e.target.value)}
                style={{ 
                  width: '100%', 
                  padding: '2px', 
                  fontSize: '11px',
                  border: '1px solid #ddd',
                  borderRadius: '2px'
                }}
              />
            </div>
            {branches.length > 2 && (
              <button
                onClick={() => removeBranch(index)}
                style={{
                  marginLeft: '5px',
                  fontSize: '10px',
                  padding: '2px 4px',
                  backgroundColor: '#f44336',
                  color: 'white',
                  border: 'none',
                  borderRadius: '2px',
                  cursor: 'pointer'
                }}
              >
                ×
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Multiple output handles for each branch */}
      {branches.map((branch, index) => {
        const positions = [
          Position.BottomLeft,
          Position.Bottom, 
          Position.BottomRight
        ];
        const position = positions[index % positions.length];
        
        return (
          <Handle
            key={branch.id}
            type="source"
            position={position}
            id={branch.id}
            style={{ 
              background: '#4CAF50', 
              width: 8, 
              height: 8,
              left: index === 0 ? '25%' : index === branches.length - 1 ? '75%' : '50%'
            }}
            title={branch.label}
          />
        );
      })}
    </div>
  );
});

export const schema = {
  inputs: [
    { id: 'data', label: 'Input Data', type: 'object' },
  ],
  outputs: [], // Dynamic outputs based on branches
};
