import React from 'react';
import { Box, Container, Heading, Text } from '@chakra-ui/react';
import GoogleDriveIntegration from '../components/integrations/GoogleDriveIntegration';
import Head from 'next/head';

const GoogleDrivePage: React.FC = () => {
  return (
    <>
      <Head>
        <title>Google Drive Integration | ATOM</title>
        <meta name="description" content="Connect and manage your Google Drive files with ATOM" />
      </Head>

      <Container maxW="container.xl" py={8}>
        <Box mb={8}>
          <Heading as="h1" size="2xl" mb={4} color="blue.600">
            Google Drive Integration
          </Heading>
          <Text fontSize="lg" color="gray.600" maxW="3xl">
            Seamlessly connect your Google Drive account to search, manage, and ingest files directly within ATOM.
            Access your documents, spreadsheets, presentations, and more with powerful search capabilities.
          </Text>
        </Box>

        <GoogleDriveIntegration />
      </Container>
    </>
  );
};

export default GoogleDrivePage;
