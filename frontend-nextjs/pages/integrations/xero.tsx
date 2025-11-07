/**
 * Xero Accounting Integration Page
 * Next.js page for Xero small business accounting integration
 */

import React from 'react';
import { GetServerSideProps } from 'next';
import Head from 'next/head';
import { Layout } from '../../../components/layout/Layout';
import { XeroIntegration } from '../../../src/ui-shared/integrations/xero';

interface XeroPageProps {
  initialConfig?: {
    environment: 'production' | 'sandbox';
  };
}

const XeroPage: React.FC<XeroPageProps> = ({ initialConfig }) => {
  return (
    <>
      <Head>
        <title>Xero Integration | ATOM</title>
        <meta name="description" content="Complete small business accounting and financial management through Xero integration" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
        
        {/* Open Graph */}
        <meta property="og:title" content="Xero Integration | ATOM" />
        <meta property="og:description" content="Complete small business accounting and financial management through Xero integration" />
        <meta property="og:type" content="website" />
        <meta property="og:image" content="/images/integrations/xero-og.jpg" />
        
        {/* Twitter Card */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="Xero Integration | ATOM" />
        <meta name="twitter:description" content="Complete small business accounting and financial management through Xero integration" />
        <meta name="twitter:image" content="/images/integrations/xero-twitter.jpg" />
        
        {/* Xero Brand Colors */}
        <meta name="theme-color" content="#1EE5D8" />
        <style>{`
          :root {
            --xero-primary: #1EE5D8;
            --xero-secondary: #03B0F9;
            --xero-accent: #FF6B00;
            --xero-success: #13C4A3;
            --xero-warning: #F59E0B;
            --xero-error: #EF4444;
          }
        `}</style>
      </Head>

      <Layout 
        title="Xero Integration"
        description="Complete small business accounting and financial management through Xero integration"
      >
        <XeroIntegration />
      </Layout>
    </>
  );
};

export const getServerSideProps: GetServerSideProps<XeroPageProps> = async ({ req }) => {
  // Get initial configuration from server-side
  const initialConfig = {
    environment: (process.env.XERO_ENVIRONMENT as 'production' | 'sandbox') || 'production'
  };

  return {
    props: {
      initialConfig
    }
  };
};

export default XeroPage;