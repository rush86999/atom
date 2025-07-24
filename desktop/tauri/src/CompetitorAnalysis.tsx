import { useState } from 'react';
import { invoke } from '@tauri-apps/api/tauri';

function CompetitorAnalysis() {
  const [competitors, setCompetitors] = useState('');
  const [notionDatabaseId, setNotionDatabaseId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handleRunAnalysis = async () => {
    setIsLoading(true);
    setMessage('');
    setError('');
    try {
      await invoke('run_competitor_analysis', {
        competitors: competitors.split(',').map(c => c.trim()),
        notionDatabaseId,
      });
      setMessage('Competitor analysis complete!');
    } catch (err: any) {
      setError(err.toString());
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="competitor-analysis-container">
      <h2>Competitor Analysis</h2>
      {isLoading && <p>Loading...</p>}
      {message && <p className="success">{message}</p>}
      {error && <p className="error">{error}</p>}
      <div className="setting">
        <label>Competitors (comma-separated)</label>
        <input
          type="text"
          value={competitors}
          onChange={(e) => setCompetitors(e.target.value)}
          placeholder="e.g., Apple, Google, Microsoft"
        />
      </div>
      <div className="setting">
        <label>Notion Database ID</label>
        <input
          type="text"
          value={notionDatabaseId}
          onChange={(e) => setNotionDatabaseId(e.target.value)}
          placeholder="Enter Notion Database ID for the report"
        />
      </div>
      <button onClick={handleRunAnalysis}>Run Analysis</button>
    </div>
  );
}

export default CompetitorAnalysis;
