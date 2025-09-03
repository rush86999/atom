import React, { useState, useEffect } from 'react';
import Box from '@components/common/Box';
import Text from '@components/common/Text';
import Button from '@components/Button';
import Select from '@components/common/Select';

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
    <Box marginTop="m" paddingTop="m" borderTopWidth={1} borderColor="hairline">
      <Text variant="subHeader" marginBottom="s">
        Voice Settings
      </Text>
      {message && (
        <Box backgroundColor="green.100" padding="s" marginBottom="m" borderRadius="s">
          <Text color="green.700">{message}</Text>
        </Box>
      )}
      {error && (
        <Box backgroundColor="red.100" padding="s" marginBottom="m" borderRadius="s">
          <Text color="red.700">{error}</Text>
        </Box>
      )}
      
      <Select
        label="TTS Provider"
        options={providerOptions}
        value={ttsProvider}
        onChange={(value) => {
          setTtsProvider(value as string);
          setApiKey(''); // Clear API key when provider changes
        }}
        placeholder="Select a TTS provider"
      />

      <input
        type="password"
        value={apiKey}
        onChange={(e) => setApiKey(e.target.value)}
        placeholder={`Enter ${providerOptions.find(p => p.value === ttsProvider)?.label} API Key`}
        style={{
          width: '100%',
          padding: '8px',
          marginTop: '8px',
          marginBottom: '8px',
          border: '1px solid #ccc',
          borderRadius: '4px',
        }}
      />
      <Button onPress={handleSave} variant="primary" title="Save Voice Settings" />
    </Box>
  );
};

export default VoiceSettings;
