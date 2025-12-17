import React from 'react';
import Head from 'next/head';
import { Box, Heading, Container } from '@chakra-ui/react';
import AIProviderSettings from '../../src/components/AIProviders/AIProviderSettings';
import Layout from '../../components/layout/Layout';

const AISettingsPage = () => {
    return (
        <Layout>
            <Head>
                <title>AI Provider Settings | Atom</title>
            </Head>
            <Container maxW="container.xl" py={8}>
                <Box mb={8}>
                    <Heading as="h1" size="xl" mb={4}>AI Provider Settings</Heading>
                </Box>
                <AIProviderSettings baseApiUrl="/api" />
            </Container>
        </Layout>
    );
};

export default AISettingsPage;
