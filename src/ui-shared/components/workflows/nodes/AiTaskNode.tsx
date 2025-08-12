import React, { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  const [prompt, setPrompt] = useState(data.prompt || '');

  const onPromptChange = (evt) => {
    const newPrompt = evt.target.value;
    setPrompt(newPrompt);
    if (data.onChange) {
      data.onChange({ ...data, prompt: newPrompt });
    }
  };

  return (
    <div style={{
      background: '#f0f0f0',
      border: '1px solid #ddd',
      padding: '10px 15px',
      borderRadius: '5px',
      width: 250,
    }}>
      <Handle type="target" position={Position.Top} style={{ background: '#555' }} />
      <div>
        <strong>AI Task</strong>
      </div>
      <div style={{ marginTop: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '5px' }}>
          Custom Prompt:
        </label>
        <textarea
          value={prompt}
          onChange={onPromptChange}
          style={{ width: '100%', height: '100px', padding: '5px' }}
          placeholder="e.g., Summarize the following text..."
        />
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
});
