import React, { useState, useEffect } from 'react';
import { Box, Button, Input, Text, useToast } from '@chakra-ui/react';

const GitHubManager = () => {
    const [apiKey, setApiKey] = useState('');
    const [isConnected, setIsConnected] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const toast = useToast();

    useEffect(() => {
        const checkConnection = async () => {
            try {
                const response = await fetch('/api/integrations/credentials?service=github');
                const data = await response.json();
                if (data.isConnected) {
                    setIsConnected(true);
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
            await fetch('/api/integrations/credentials', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ service: 'github', secret: apiKey }),
            });
            setIsConnected(true);
            toast({
                title: 'GitHub API key saved.',
                status: 'success',
                duration: 3000,
                isClosable: true,
            });
        } catch (error) {
            console.error('Error saving GitHub API key:', error);
            toast({
                title: 'Error saving GitHub API key.',
                status: 'error',
                duration: 3000,
                isClosable: true,
            });
        }
    };

    if (isLoading) {
        return <Text>Loading...</Text>;
    }

    return (
        <Box>
            <Text fontSize="xl" mb={4}>GitHub Integration</Text>
            {isConnected ? (
                <Text>You are connected to GitHub.</Text>
            ) : (
                <>
                    <Input
                        placeholder="Enter your GitHub API Key"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        mb={4}
                    />
                    <Button onClick={handleSaveApiKey}>Save API Key</Button>
                </>
            )}
        </Box>
    );
};

export default GitHubManager;
