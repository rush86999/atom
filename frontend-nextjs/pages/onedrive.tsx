import React from 'react';
import { Box, Container, Heading, Text } from '@chakra-ui/react';
import OneDriveIntegration from '../components/integrations/OneDriveIntegration';
import Head from 'next/head';

const OneDrivePage: React.FC = () => {
  return (
    <>
      <Head>
        <title>OneDrive Integration | ATOM</title>
        <meta name="description" content="Connect and manage your OneDrive files with ATOM" />
      </Head>

      <Container maxW="container.xl" py={8}>
        <Box mb={8}>
          <Heading as="h1" size="2xl" mb={4} color="blue.600">
            OneDrive Integration
          </Heading>
          <Text fontSize="lg" color="gray.600" maxW="3xl">
            Seamlessly connect your OneDrive account to search, manage, and ingest files directly within ATOM.
            Access your documents, spreadsheets, presentations, and more with powerful search capabilities.
          </Text>
        </Box>

        <OneDriveIntegration />
      </Container>
    </>
  );
};

export default OneDrivePage;
