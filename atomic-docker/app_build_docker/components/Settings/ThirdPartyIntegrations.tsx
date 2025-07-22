import React, { useState } from 'react';
import Box from '@components/common/Box';
import Text from '@components/common/Text';
import Button from '@components/Button';

const ThirdPartyIntegrations = () => {
  const [zapierUrl, setZapierUrl] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handleSaveZapierUrl = async () => {
    try {
      // This is a placeholder for the actual API call.
      // In a real application, you would make a request to your backend to save the URL.
      console.log('Saving Zapier URL:', zapierUrl);
      setMessage('Zapier URL saved successfully.');
      setError('');
    } catch (err) {
      setError('Failed to save Zapier URL.');
      setMessage('');
    }
  };

  return (
    <Box marginTop="m" paddingTop="m" borderTopWidth={1} borderColor="hairline">
      <Text variant="subHeader" marginBottom="s">
        Third-Party Integrations
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
      <Box marginBottom="m">
        <Text variant="subHeader" marginBottom="s">
          Zapier Integration
        </Text>
        <input
          type="text"
          value={zapierUrl}
          onChange={(e) => setZapierUrl(e.target.value)}
          placeholder="Enter Zapier Webhook URL"
          style={{
            width: '100%',
            padding: '8px',
            marginBottom: '8px',
            border: '1px solid #ccc',
            borderRadius: '4px',
          }}
        />
        <Button onPress={handleSaveZapierUrl} variant="primary" title="Save Zapier URL" />
      </Box>
    </Box>
  );
};

export default ThirdPartyIntegrations;
