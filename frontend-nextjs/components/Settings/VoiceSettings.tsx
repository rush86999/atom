import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const VoiceSettings = () => {
  const [ttsProvider, setTtsProvider] = useState('elevenlabs');
  const [apiKey, setApiKey] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchSettings = async () => {
      setIsLoading(true);
      try {
        const response = await fetch('/api/integrations/credentials?service=tts_provider');
        const data = await response.json();
        if (response.ok && data.value) {
          setTtsProvider(data.value);
          const keyResponse = await fetch(`/api/integrations/credentials?service=${data.value}_api_key`);
          const keyData = await keyResponse.json();
          if (keyResponse.ok && keyData.isConnected) {
            setApiKey('********');
          }
        }
      } catch (err) {
        setError('Failed to fetch voice settings.');
      }
      setIsLoading(false);
    };
    fetchSettings();
  }, []);

  const handleSave = async () => {
    setMessage('');
    setError('');
    try {
      // Save the provider choice
      await fetch('/api/integrations/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: 'tts_provider', secret: ttsProvider }),
      });

      // Save the API key
      const response = await fetch('/api/integrations/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: `${ttsProvider}_api_key`, secret: apiKey }),
      });

      const data = await response.json();
      if (response.ok) {
        setMessage('Voice settings saved successfully.');
        setApiKey('********');
      } else {
        setError(data.message || 'Failed to save API key.');
      }
    } catch (err) {
      setError('Failed to connect to the server.');
    }
  };

  const providerOptions = [
    { label: 'ElevenLabs', value: 'elevenlabs' },
    { label: 'Deepgram', value: 'deepgram' },
  ];

  return (
    <div className="mt-6 pt-6 border-t border-gray-200">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Voice Settings
      </h3>

      {message && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded mb-4">
          {message}
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      <div className="space-y-4">
        <div>
          <label htmlFor="tts-provider" className="block text-sm font-medium text-gray-700 mb-2">
            TTS Provider
          </label>
          <select
            id="tts-provider"
            value={ttsProvider}
            onChange={(e) => {
              setTtsProvider(e.target.value);
              setApiKey(''); // Clear API key when provider changes
            }}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">Select a TTS provider</option>
            {providerOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="api-key" className="block text-sm font-medium text-gray-700 mb-2">
            API Key
          </label>
          <Input
            id="api-key"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={`Enter ${providerOptions.find(p => p.value === ttsProvider)?.label} API Key`}
          />
        </div>

        <Button onClick={handleSave} variant="default" className="w-full">
          Save Voice Settings
        </Button>
      </div>
    </div>
  );
};

export default VoiceSettings;
