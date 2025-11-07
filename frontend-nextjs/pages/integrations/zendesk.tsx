/**
 * Zendesk Integration Page
 * Next.js page for Zendesk customer support integration
 */

import React from 'react';
import { GetServerSideProps } from 'next';
import Head from 'next/head';
import { Layout } from '../../../components/layout/Layout';
import { ZendeskIntegration } from '../../../src/ui-shared/integrations/zendesk';

interface ZendeskPageProps {
  initialConfig?: {
    environment: 'production' | 'sandbox';
  };
}

const ZendeskPage: React.FC<ZendeskPageProps> = ({ initialConfig }) => {
  return (
    <>
      <Head>
        <title>Zendesk Integration | ATOM</title>
        <meta name="description" content="Complete customer support and ticketing management through Zendesk integration" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
        
        {/* Open Graph */}
        <meta property="og:title" content="Zendesk Integration | ATOM" />
        <meta property="og:description" content="Complete customer support and ticketing management through Zendesk integration" />
        <meta property="og:type" content="website" />
        <meta property="og:image" content="/images/integrations/zendesk-og.jpg" />
        
        {/* Twitter Card */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="Zendesk Integration | ATOM" />
        <meta name="twitter:description" content="Complete customer support and ticketing management through Zendesk integration" />
        <meta name="twitter:image" content="/images/integrations/zendesk-twitter.jpg" />
        
        {/* Zendesk Brand Colors */}
        <meta name="theme-color" content="#03363d" />
        <style>{`
          :root {
            --zendesk-primary: #03363d;
            --zendesk-secondary: #68a38c;
            --zendesk-accent: #f47a25;
            --zendesk-success: #68a38c;
            --zendesk-warning: #f47a25;
            --zendesk-error: #e30074;
          }
        `}</style>
      </Head>

      <Layout 
        title="Zendesk Integration"
        description="Complete customer support and ticketing management through Zendesk integration"
      >
        <ZendeskIntegration />
      </Layout>
    </>
  );
};

export const getServerSideProps: GetServerSideProps<ZendeskPageProps> = async ({ req }) => {
  // Get initial configuration from server-side
  const initialConfig = {
    environment: (process.env.ZENDESK_ENVIRONMENT as 'production' | 'sandbox') || 'production'
  };

  return {
    props: {
      initialConfig
    }
  };
};

export default ZendeskPage;