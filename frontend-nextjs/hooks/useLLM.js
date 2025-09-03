import { useState } from 'react';

const useLLM = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const generate = async (prompt) => {
    setLoading(true);
    setError(null);

    try {
      // Get API keys from storage
      let apiKeys = {};
      if (typeof window !== 'undefined') {
        const storedKeys = localStorage.getItem('apiKeys');
        if (storedKeys) {
          apiKeys = JSON.parse(storedKeys);
        }
      }

      const response = await fetch('http://localhost:8000/api/llm/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt,
          api_keys: apiKeys
        }),
      });

      if (!response.ok) {
        throw new Error('LLM request failed');
      }

      const data = await response.json();
      return data.response;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  return { generate, loading, error };
};

export default useLLM;