import { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/tauri';

function ProjectHealth() {
  const [healthScore, setHealthScore] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchHealthScore = async () => {
    setIsLoading(true);
    setError('');
    try {
      const score = await invoke('get_project_health_score');
      setHealthScore(score as number);
    } catch (err: any) {
      setError(err.toString());
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHealthScore();
  }, []);

  return (
    <div className="project-health-container">
      <h2>Project Health Score</h2>
      {isLoading && <p>Loading...</p>}
      {error && <p className="error">{error}</p>}
      {healthScore !== null && (
        <div className="health-score">
          <p>{healthScore}</p>
        </div>
      )}
    </div>
  );
}

export default ProjectHealth;
