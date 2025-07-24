import { useState } from 'react';
import { invoke } from '@tauri-apps/api/tauri';

function LearningAssistant() {
  const [notionDatabaseId, setNotionDatabaseId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handleGeneratePlan = async () => {
    setIsLoading(true);
    setMessage('');
    setError('');
    try {
      await invoke('generate_learning_plan', {
        notionDatabaseId,
      });
      setMessage('Learning plan generated!');
    } catch (err: any) {
      setError(err.toString());
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="learning-assistant-container">
      <h2>Personalized Learning Assistant</h2>
      {isLoading && <p>Loading...</p>}
      {message && <p className="success">{message}</p>}
      {error && <p className="error">{error}</p>}
      <div className="setting">
        <label>Notion Database ID</label>
        <input
          type="text"
          value={notionDatabaseId}
          onChange={(e) => setNotionDatabaseId(e.target.value)}
          placeholder="Enter Notion Database ID for the report"
        />
      </div>
      <button onClick={handleGeneratePlan}>Generate Learning Plan</button>
    </div>
  );
}

export default LearningAssistant;
