import React, { useState, useEffect } from 'react';
import { Box, Button, Text, useToast } from '@chakra-ui/react';
import { useQuery, useMutation, gql } from '@apollo/client';

const GET_DISCORD_CONNECTION_STATUS_QUERY = gql`
  query GetDiscordConnectionStatus {
    getDiscordConnectionStatus {
      isConnected
      username
    }
  }
`;

const DISCONNECT_DISCORD_ACCOUNT_MUTATION = gql`
  mutation DisconnectDiscordAccount {
    disconnectDiscordAccount {
      success
      message
    }
  }
`;

const DiscordManager = () => {
    const { data, loading, error } = useQuery(GET_DISCORD_CONNECTION_STATUS_QUERY);
    const [disconnectDiscord, { loading: disconnecting }] = useMutation(DISCONNECT_DISCORD_ACCOUNT_MUTATION, {
        refetchQueries: [{ query: GET_DISCORD_CONNECTION_STATUS_QUERY }],
    });
    const toast = useToast();

    const handleConnect = () => {
        window.location.href = '/api/discord/start-handshake';
    };

    const handleDisconnect = async () => {
        try {
            await disconnectDiscord();
            toast({
                title: 'Discord account disconnected.',
                status: 'success',
                duration: 3000,
                isClosable: true,
            });
        } catch (error) {
            console.error('Error disconnecting Discord account:', error);
            toast({
                title: 'Error disconnecting Discord account.',
                status: 'error',
                duration: 3000,
                isClosable: true,
            });
        }
    };

    if (loading) {
        return <Text>Loading...</Text>;
    }

    if (error) {
        return <Text>Error: {error.message}</Text>;
    }

    return (
        <Box>
            <Text fontSize="xl" mb={4}>Discord Integration</Text>
            {data?.getDiscordConnectionStatus?.isConnected ? (
                <>
                    <Text>Connected as: {data.getDiscordConnectionStatus.username}</Text>
                    <Button onClick={handleDisconnect} isLoading={disconnecting} mt={4}>
                        Disconnect
                    </Button>
                </>
            ) : (
                <Button onClick={handleConnect}>Connect to Discord</Button>
            )}
        </Box>
    );
};

export default DiscordManager;
