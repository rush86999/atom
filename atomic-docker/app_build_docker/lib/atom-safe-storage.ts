import { exec } from 'child_process';

// For demonstration, we're using environment variables.
// In a real-world application, use a secure key management service.

export const getElevenLabsApiKey = (): Promise<string> => {
  return new Promise((resolve) => {
    // This is a placeholder for retrieving the key.
    // In a real app, you might fetch this from a secure vault or a database.
    resolve(process.env.ELEVENLABS_API_KEY || '');
  });
};

export const updateElevenLabsApiKey = (apiKey: string): Promise<void> => {
  return new Promise((resolve, reject) => {
    // This is a placeholder for updating the key.
    // In a real app, this would update the value in your secure vault or database.
    // For this example, we'll simulate updating a local environment variable.
    // This is NOT recommended for production environments.
    const command = `export ELEVENLABS_API_KEY=${apiKey}`;
    exec(command, (error) => {
      if (error) {
        console.error('Failed to set environment variable:', error);
        return reject(new Error('Failed to update API key.'));
      }
      process.env.ELEVENLABS_API_KEY = apiKey;
      resolve();
    });
  });
};
