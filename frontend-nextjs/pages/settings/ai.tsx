import React from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { Box, Heading, Container, Text } from '@chakra-ui/react';
import AIProviderSettings from '@/src/components/AIProviders/AIProviderSettings';
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
                <Box mt={8}>
                    <Link href="/settings/routing">
                        <Text color="blue.500" _hover={{ textDecoration: 'underline' }} cursor="pointer">
                            Routing &amp; Learning Dashboard →
                        </Text>
                    </Link>
                </Box>
                <Box mt={4}>
                    <Link href="/settings/local-models">
                        <Text color="blue.500" _hover={{ textDecoration: 'underline' }} cursor="pointer">
                            Local Models (Ollama, LM Studio, vLLM) →
                        </Text>
                    </Link>
                </Box>
            </Container>
        </Layout>
    );
};

export default AISettingsPage;
