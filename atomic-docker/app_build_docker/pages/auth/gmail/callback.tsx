// atomic-docker/app_build_docker/pages/auth/gmail/callback.tsx
import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { useMutation, gql } from '@apollo/client';
import Box from '@components/common/Box';
import Text from '@components/common/Text';
import { ActivityIndicator } from 'react-native';
import { useToast } from '@chakra-ui/react';
import { palette } from '@lib/theme/theme';

// Define the GraphQL mutation
const HANDLE_GMAIL_AUTH_CALLBACK_MUTATION = gql`
  mutation HandleGmailAuthCallback($code: String!) {
    handleGmailAuthCallback(input: { code: $code }) {
      success
      message
    }
  }
`;

const GmailAuthCallbackPage = () => {
  const router = useRouter();
  const toast = useToast();
  const [statusMessage, setStatusMessage] = useState('Processing Gmail authorization...');
  const [isLoading, setIsLoading] = useState(true); // General loading for page setup and redirects

  const [handleCallbackMutation, { loading: mutationInProgress }] = useMutation(
    HANDLE_GMAIL_AUTH_CALLBACK_MUTATION
  );

  useEffect(() => {
    if (!router.isReady) {
      return; // Wait for router to be ready to access query params
    }

    const { code, error: googleError, error_description: googleErrorDescription } = router.query;

    if (googleError) {
      const description = (googleErrorDescription as string) || (googleError as string) || 'Unknown Google error.';
      console.error('Error from Google OAuth:', googleError, description);
      setStatusMessage(`Error from Google: ${description}`);
      toast({
        title: 'Gmail Connection Error',
        description: `Google authentication failed: ${description}`,
        status: 'error',
        duration: 9000,
        isClosable: true,
      });
      setIsLoading(false);
      setTimeout(() => router.push('/Settings/UserViewCalendarAndContactIntegrations'), 5000);
      return;
    }

    if (typeof code === 'string' && code) {
      // Do not set isLoading to true here again if it's already true for the page
      // mutationInProgress will cover the mutation's loading state
      handleCallbackMutation({ variables: { code } })
        .then(response => {
          const { success, message } = response.data?.handleGmailAuthCallback || {};
          if (success) {
            setStatusMessage(message || 'Gmail connected successfully!');
            toast({
              title: 'Gmail Connected',
              description: message || 'Your Gmail account has been successfully connected.',
              status: 'success',
              duration: 5000,
              isClosable: true,
            });
          } else {
            // Use message from backend if available, otherwise a generic one
            throw new Error(message || 'Failed to process Gmail authorization with backend.');
          }
        })
        .catch(err => {
          console.error('Error handling Gmail auth callback mutation:', err);
          setStatusMessage(`Error: ${err.message || 'Could not complete Gmail connection.'}`);
          toast({
            title: 'Gmail Connection Failed',
            description: err.message || 'An unexpected error occurred while connecting your Gmail account.',
            status: 'error',
            duration: 9000,
            isClosable: true,
          });
        })
        .finally(() => {
          setIsLoading(false); // Page processing is done
          setTimeout(() => router.push('/Settings/UserViewCalendarAndContactIntegrations'), 3000);
        });
    } else if (router.isReady && !code) {
      // router.isReady but no code and no googleError
      setStatusMessage('Invalid callback state. No authorization code found.');
      toast({
        title: 'Gmail Connection Error',
        description: 'Invalid callback state. No authorization code provided by Google.',
        status: 'error',
        duration: 9000,
        isClosable: true,
      });
      setIsLoading(false);
      setTimeout(() => router.push('/Settings/UserViewCalendarAndContactIntegrations'), 5000);
    }
  }, [router.isReady, router.query, handleCallbackMutation, router, toast]);

  // The initial page load might show "Processing..." briefly even before router is ready.
  // Consider a more nuanced loading state if that's an issue.
  const displayLoading = isLoading || mutationInProgress;

  return (
    <Box flex={1} justifyContent="center" alignItems="center" minHeight="100vh" backgroundColor="primaryCardBackground">
      <Text variant="header" mb="l">{statusMessage}</Text>
      {displayLoading && <ActivityIndicator size="large" color={palette.primary} />}
      {!displayLoading && (
        <Text variant="body" mt="m">
          You will be redirected shortly...
        </Text>
      )}
    </Box>
  );
};

export default GmailAuthCallbackPage;
