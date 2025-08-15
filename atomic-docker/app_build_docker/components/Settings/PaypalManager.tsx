import React, { useState, useEffect } from 'react';
import { Box, Button, Text, useToast } from '@chakra-ui/react';
import { useQuery, useMutation, gql } from '@apollo/client';

const GET_PAYPAL_CONNECTION_STATUS_QUERY = gql`
  query GetPaypalConnectionStatus {
    getPaypalConnectionStatus {
      isConnected
    }
  }
`;

const CONNECT_PAYPAL_ACCOUNT_MUTATION = gql`
  mutation ConnectPaypalAccount {
    connectPaypalAccount {
      success
      message
    }
  }
`;

const DISCONNECT_PAYPAL_ACCOUNT_MUTATION = gql`
  mutation DisconnectPaypalAccount {
    disconnectPaypalAccount {
      success
      message
    }
  }
`;

const PaypalManager = () => {
    const { data, loading, error } = useQuery(GET_PAYPAL_CONNECTION_STATUS_QUERY);
    const [connectPaypal, { loading: connecting }] = useMutation(CONNECT_PAYPAL_ACCOUNT_MUTATION, {
        refetchQueries: [{ query: GET_PAYPAL_CONNECTION_STATUS_QUERY }],
    });
    const [disconnectPaypal, { loading: disconnecting }] = useMutation(DISCONNECT_PAYPAL_ACCOUNT_MUTATION, {
        refetchQueries: [{ query: GET_PAYPAL_CONNECTION_STATUS_QUERY }],
    });
    const toast = useToast();

    const handleConnect = async () => {
        try {
            await connectPaypal();
            toast({
                title: 'PayPal account connected.',
                status: 'success',
                duration: 3000,
                isClosable: true,
            });
        } catch (error) {
            console.error('Error connecting PayPal account:', error);
            toast({
                title: 'Error connecting PayPal account.',
                status: 'error',
                duration: 3000,
                isClosable: true,
            });
        }
    };

    const handleDisconnect = async () => {
        try {
            await disconnectPaypal();
            toast({
                title: 'PayPal account disconnected.',
                status: 'success',
                duration: 3000,
                isClosable: true,
            });
        } catch (error) {
            console.error('Error disconnecting PayPal account:', error);
            toast({
                title: 'Error disconnecting PayPal account.',
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
            <Text fontSize="xl" mb={4}>PayPal Integration</Text>
            {data?.getPaypalConnectionStatus?.isConnected ? (
                <>
                    <Text>You are connected to PayPal.</Text>
                    <Button onClick={handleDisconnect} isLoading={disconnecting} mt={4}>
                        Disconnect
                    </Button>
                </>
            ) : (
                <Button onClick={handleConnect} isLoading={connecting}>Connect to PayPal</Button>
            )}
        </Box>
    );
};

export default PaypalManager;
