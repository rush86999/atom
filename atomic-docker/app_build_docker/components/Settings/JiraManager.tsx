import React, { useState, useEffect } from 'react';
import { Box, Button, Text, useToast } from '@chakra-ui/react';
import { useQuery, useMutation, gql } from '@apollo/client';

const GET_JIRA_CONNECTION_STATUS_QUERY = gql`
  query GetJiraConnectionStatus {
    getJiraConnectionStatus {
      isConnected
      username
    }
  }
`;

const DISCONNECT_JIRA_ACCOUNT_MUTATION = gql`
  mutation DisconnectJiraAccount {
    disconnectJiraAccount {
      success
      message
    }
  }
`;

const JiraManager = () => {
    const { data, loading, error } = useQuery(GET_JIRA_CONNECTION_STATUS_QUERY);
    const [disconnectJira, { loading: disconnecting }] = useMutation(DISCONNECT_JIRA_ACCOUNT_MUTATION, {
        refetchQueries: [{ query: GET_JIRA_CONNECTION_STATUS_QUERY }],
    });
    const toast = useToast();

    const handleConnect = () => {
        window.location.href = '/api/jira/start-handshake';
    };

    const handleDisconnect = async () => {
        try {
            await disconnectJira();
            toast({
                title: 'Jira account disconnected.',
                status: 'success',
                duration: 3000,
                isClosable: true,
            });
        } catch (error) {
            console.error('Error disconnecting Jira account:', error);
            toast({
                title: 'Error disconnecting Jira account.',
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
            <Text fontSize="xl" mb={4}>Jira Integration</Text>
            {data?.getJiraConnectionStatus?.isConnected ? (
                <>
                    <Text>Connected as: {data.getJiraConnectionStatus.username}</Text>
                    <Button onClick={handleDisconnect} isLoading={disconnecting} mt={4}>
                        Disconnect
                    </Button>
                </>
            ) : (
                <Button onClick={handleConnect}>Connect to Jira</Button>
            )}
        </Box>
    );
};

export default JiraManager;
