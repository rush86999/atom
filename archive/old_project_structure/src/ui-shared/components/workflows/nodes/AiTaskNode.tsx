import React, { memo, useState } from 'react';
import { Handle, Position } from 'reactflow';

export default memo(({ data }) => {
  const [aiType, setAiType] = useState(data.aiType || 'custom');
  const [prompt, setPrompt] = useState(data.prompt || '');
  const [model, setModel] = useState(data.model || 'gpt-3.5-turbo');
  const [temperature, setTemperature] = useState(data.temperature || 0.7);
  const [maxTokens, setMaxTokens] = useState(data.maxTokens || 1000);
  const [prebuiltTask, setPrebuiltTask] = useState(data.prebuiltTask || '');

  const onChange = (updates) => {
    if (data.onChange) {
      data.onChange({ 
        ...data, 
        aiType, 
        prompt, 
        model, 
        temperature, 
        maxTokens, 
        prebuiltTask,
        ...updates 
      });
    }
  };

  const prebuiltTasks = [
    { id: 'summarize', label: 'Summarize Text', prompt: 'Summarize the following text in a concise manner:' },
    { id: 'extract', label: 'Extract Information', prompt: 'Extract the following information from the text:' },
    { id: 'classify', label: 'Classify Content', prompt: 'Classify the following content into categories:' },
    { id: 'translate', label: 'Translate Text', prompt: 'Translate the following text to {target_language}:' },
    { id: 'sentiment', label: 'Analyze Sentiment', prompt: 'Analyze the sentiment of the following text (positive/negative/neutral):' },
    { id: 'generate', label: 'Generate Content', prompt: 'Generate content based on the following context:' },
    { id: 'validate', label: 'Validate Data', prompt: 'Validate the following data and identify any issues:' },
    { id: 'transform', label: 'Transform Data', prompt: 'Transform the following data according to these rules:' }
  ];

  const currentTask = prebuiltTasks.find(task => task.id === prebuiltTask);

  return (
    <div style={{
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      border: '2px solid #5a67d8',
      padding: '15px',
      borderRadius: '8px',
      width: 320,
      color: 'white',
      boxShadow: '0 4px 15px rgba(102, 126, 234, 0.3)'
    }}>
      <Handle 
        type="target" 
        position={Position.Top} 
        style={{ background: '#5a67d8', width: 10, height: 10 }} 
      />
      
      <div style={{ marginBottom: '12px' }}>
        <strong style={{ fontSize: '14px' }}>🤖 AI Task Node</strong>
      </div>

      <div style={{ marginBottom: '10px' }}>
        <label style={{ fontSize: '12px', display: 'block', marginBottom: '3px', fontWeight: 'bold' }}>
          AI Type:
        </label>
        <select 
          value={aiType}
          onChange={(e) => {
            setAiType(e.target.value);
            onChange({ aiType: e.target.value });
          }}
          style={{ 
            width: '100%', 
            padding: '4px', 
            fontSize: '12px',
            backgroundColor: 'rgba(255,255,255,0.9)',
            border: 'none',
            borderRadius: '4px'
          }}
        >
          <option value="custom">Custom Prompt</option>
          <option value="prebuilt">Prebuilt Task</option>
          <option value="workflow">Workflow Analysis</option>
          <option value="decision">Decision Making</option>
        </select>
      </div>

      {aiType === 'prebuilt' && (
        <div style={{ marginBottom: '10px' }}>
          <label style={{ fontSize: '12px', display: 'block', marginBottom: '3px', fontWeight: 'bold' }}>
            Prebuilt Task:
          </label>
          <select 
            value={prebuiltTask}
            onChange={(e) => {
              const task = e.target.value;
              setPrebuiltTask(task);
              const selectedTask = prebuiltTasks.find(t => t.id === task);
              onChange({ 
                prebuiltTask: task,
                prompt: selectedTask?.prompt || ''
              });
            }}
            style={{ 
              width: '100%', 
              padding: '4px', 
              fontSize: '12px',
              backgroundColor: 'rgba(255,255,255,0.9)',
              border: 'none',
              borderRadius: '4px'
            }}
          >
            <option value="">Select a task...</option>
            {prebuiltTasks.map(task => (
              <option key={task.id} value={task.id}>{task.label}</option>
            ))}
          </select>
        </div>
      )}

      {aiType === 'workflow' && (
        <div style={{ marginBottom: '10px' }}>
          <label style={{ fontSize: '12px', display: 'block', marginBottom: '3px', fontWeight: 'bold' }}>
            Workflow Analysis Type:
          </label>
          <select 
            value={prebuiltTask}
            onChange={(e) => {
              setPrebuiltTask(e.target.value);
              onChange({ prebuiltTask: e.target.value });
            }}
            style={{ 
              width: '100%', 
              padding: '4px', 
              fontSize: '12px',
              backgroundColor: 'rgba(255,255,255,0.9)',
              border: 'none',
              borderRadius: '4px'
            }}
          >
            <option value="optimize">Optimize Workflow</option>
            <option value="debug">Debug Issues</option>
            <option value="predict">Predict Outcomes</option>
            <option value="improve">Suggest Improvements</option>
          </select>
        </div>
      )}

      {(aiType === 'custom' || (aiType === 'prebuilt' && currentTask)) && (
        <div style={{ marginBottom: '10px' }}>
          <label style={{ fontSize: '12px', display: 'block', marginBottom: '3px', fontWeight: 'bold' }}>
            {aiType === 'prebuilt' ? 'Task Prompt:' : 'Custom Prompt:'}
          </label>
          <textarea
            value={prompt}
            onChange={(e) => {
              setPrompt(e.target.value);
              onChange({ prompt: e.target.value });
            }}
            placeholder={aiType === 'prebuilt' && currentTask ? currentTask.prompt : "e.g., Analyze the following data and provide insights..."}
            style={{ 
              width: '100%', 
              height: '80px', 
              padding: '6px', 
              fontSize: '12px',
              backgroundColor: 'rgba(255,255,255,0.9)',
              border: 'none',
              borderRadius: '4px',
              resize: 'vertical'
            }}
          />
        </div>
      )}

      {aiType === 'decision' && (
        <div style={{ marginBottom: '10px' }}>
          <label style={{ fontSize: '12px', display: 'block', marginBottom: '3px', fontWeight: 'bold' }}>
            Decision Criteria:
          </label>
          <textarea
            value={prompt}
            onChange={(e) => {
              setPrompt(e.target.value);
              onChange({ prompt: e.target.value });
            }}
            placeholder="e.g., Approve if risk_score < 0.3 and budget < 10000"
            style={{ 
              width: '100%', 
              height: '60px', 
              padding: '6px', 
              fontSize: '12px',
              backgroundColor: 'rgba(255,255,255,0.9)',
              border: 'none',
              borderRadius: '4px',
              resize: 'vertical'
            }}
          />
        </div>
      )}

      <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
        <div style={{ flex: 1 }}>
          <label style={{ fontSize: '11px', display: 'block', marginBottom: '2px' }}>
            Model:
          </label>
          <select 
            value={model}
            onChange={(e) => {
              setModel(e.target.value);
              onChange({ model: e.target.value });
            }}
            style={{ 
              width: '100%', 
              padding: '3px', 
              fontSize: '11px',
              backgroundColor: 'rgba(255,255,255,0.9)',
              border: 'none',
              borderRadius: '3px'
            }}
          >
            <option value="gpt-3.5-turbo">GPT-3.5</option>
            <option value="gpt-4">GPT-4</option>
            <option value="gpt-4-turbo">GPT-4 Turbo</option>
            <option value="claude-3">Claude 3</option>
            <option value="llama-2">Llama 2</option>
            <option value="local">Local Model</option>
          </select>
        </div>
        
        <div style={{ width: '80px' }}>
          <label style={{ fontSize: '11px', display: 'block', marginBottom: '2px' }}>
            Temperature:
          </label>
          <input
            type="number"
            value={temperature}
            onChange={(e) => {
              setTemperature(parseFloat(e.target.value));
              onChange({ temperature: parseFloat(e.target.value) });
            }}
            min="0"
            max="2"
            step="0.1"
            style={{ 
              width: '100%', 
              padding: '3px', 
              fontSize: '11px',
              backgroundColor: 'rgba(255,255,255,0.9)',
              border: 'none',
              borderRadius: '3px'
            }}
          />
        </div>
        
        <div style={{ width: '80px' }}>
          <label style={{ fontSize: '11px', display: 'block', marginBottom: '2px' }}>
            Max Tokens:
          </label>
          <input
            type="number"
            value={maxTokens}
            onChange={(e) => {
              setMaxTokens(parseInt(e.target.value));
              onChange({ maxTokens: parseInt(e.target.value) });
            }}
            min="100"
            max="4000"
            step="100"
            style={{ 
              width: '100%', 
              padding: '3px', 
              fontSize: '11px',
              backgroundColor: 'rgba(255,255,255,0.9)',
              border: 'none',
              borderRadius: '3px'
            }}
          />
        </div>
      </div>

      <div style={{ 
        fontSize: '10px', 
        opacity: 0.8,
        fontStyle: 'italic',
        textAlign: 'center'
      }}>
        {aiType === 'prebuilt' && currentTask && currentTask.label}
        {aiType === 'workflow' && 'AI will analyze workflow context'}
        {aiType === 'decision' && 'AI will make decision based on criteria'}
        {aiType === 'custom' && 'Custom AI processing'}
      </div>

      <Handle 
        type="source" 
        position={Position.Bottom} 
        style={{ background: '#5a67d8', width: 10, height: 10 }} 
      />
    </div>
  );
});

export const schema = {
  inputs: [
    { id: 'input_data', label: 'Input Data', type: 'any' },
    { id: 'context', label: 'Context', type: 'object' },
  ],
  outputs: [
    { id: 'result', label: 'AI Result', type: 'any' },
    { id: 'confidence', label: 'Confidence Score', type: 'number' },
    { id: 'reasoning', label: 'AI Reasoning', type: 'string' },
  ],
};
