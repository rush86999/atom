import React, { useState, useEffect } from 'react';
import Box from '@components/common/Box';
import Text from '@components/common/Text';
import Button from '@components/Button';

const VoiceSettings = () => {
  const [elevenLabsApiKey, setElevenLabsApiKey] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchApiKey = async () => {
      try {
        const response = await fetch('/api/atom/voice/elevenlabs-api-key');
        const data = await response.json();
        if (response.ok) {
          setElevenLabsApiKey(data.apiKey || '');
        } else {
          setError(data.message || 'Failed to fetch API key.');
        }
      } catch (err) {
        setError('Failed to connect to the server.');
      }
    };
    fetchApiKey();
  }, []);

  const handleSave = async () => {
    try {
      const response = await fetch('/api/atom/voice/elevenlabs-api-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ apiKey: elevenLabsApiKey }),
      });
      const data = await response.json();
      if (response.ok) {
        setMessage(data.message);
        setError('');
      } else {
        setError(data.message || 'Failed to save API key.');
        setMessage('');
      }
    } catch (err) {
      setError('Failed to connect to the server.');
      setMessage('');
    }
  };

  return (
    <Box marginTop="m" paddingTop="m" borderTopWidth={1} borderColor="hairline">
      <Text variant="subHeader" marginBottom="s">
        Voice Settings (ElevenLabs)
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
      <input
        type="text"
        value={elevenLabsApiKey}
        onChange={(e) => setElevenLabsApiKey(e.target.value)}
        placeholder="Enter ElevenLabs API Key"
        style={{
          width: '100%',
          padding: '8px',
          marginBottom: '8px',
          border: '1px solid #ccc',
          borderRadius: '4px',
        }}
      />
      <Button onPress={handleSave} variant="primary" title="Save API Key" />
    </Box>
  );
};

export default VoiceSettings;
