import React, { useState, useEffect } from 'react';
import Box from '@components/common/Box';
import Text from '@components/common/Text';
import Button from '@components/Button';
import TextField from '@components/TextField';
import { useToast } from '@components/ui/use-toast';

const GitHubManager = () => {
    const [apiKey, setApiKey] = useState('');
    const [isConnected, setIsConnected] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const { toast } = useToast();

    useEffect(() => {
        const checkConnection = async () => {
            try {
                const response = await fetch('/api/integrations/credentials?service=github');
                const data = await response.json();
                if (data.isConnected) {
                    setIsConnected(true);
                    setApiKey('********');
                }
            } catch (error) {
                console.error('Error checking GitHub connection:', error);
            } finally {
                setIsLoading(false);
            }
        };
        checkConnection();
    }, []);

    const handleSaveApiKey = async () => {
        try {
            const response = await fetch('/api/integrations/credentials', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ service: 'github', secret: apiKey }),
            });
            if (response.ok) {
                setIsConnected(true);
                toast({
                    title: 'GitHub API key saved.',
                    variant: 'default',
                });
            } else {
                throw new Error('Failed to save');
            }
        } catch (error) {
            console.error('Error saving GitHub API key:', error);
            toast({
                title: 'Error saving GitHub API key.',
                variant: 'destructive',
            });
        }
    };

    if (isLoading) {
        return <Text>Loading...</Text>;
    }

    return (
        <Box marginTop="m">
            <Text variant="subHeader" marginBottom="s">GitHub Integration</Text>
            {isConnected ? (
                <Text>You are connected to GitHub.</Text>
            ) : (
                <Box>
                    <TextField
                        label="GitHub API Key"
                        placeholder="Enter your GitHub API Key"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        marginBottom="s"
                    />
                    <Button onPress={handleSaveApiKey} title="Save API Key" />
                </Box>
            )}
        </Box>
    );
};

export default GitHubManager;
