import React, { useState, useEffect } from 'react';
import { GetServerSideProps } from 'next';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { ToastProvider } from '@/components/ui/use-toast';
import MCPIntegration from '@/components/integrations/MCPIntegration';

const MCPPage: React.FC = () => {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Simulate loading
    const timer = setTimeout(() => {
      setIsLoading(false);
    }, 500);

    return () => clearTimeout(timer);
  }, []);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex flex-col items-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          <p className="text-gray-600">Loading MCP Integration...</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <Head>
        <title>MCP Servers - ATOM Platform</title>
        <meta name="description" content="Model Context Protocol (MCP) Server Integration" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <div className="min-h-screen bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Header */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-2">
              <h1 className="text-3xl font-bold text-gray-900">MCP Servers</h1>
              <button
                onClick={() => router.push('/dashboard')}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
              >
                ← Back to Dashboard
              </button>
            </div>
            <p className="text-lg text-gray-600">
              Manage Model Context Protocol (MCP) servers to extend your agent's capabilities
            </p>
          </div>

          {/* MCP Integration Component */}
          <ToastProvider>
            <MCPIntegration />
          </ToastProvider>
        </div>
      </div>
    </>
  );
};

export const getServerSideProps: GetServerSideProps = async (context) => {
  // You can perform server-side authentication checks here
  // For now, we'll just pass the props

  return {
    props: {
      // Pass any server-side props here
    },
  };
};

export default MCPPage;