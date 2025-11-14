/**
 * Salesforce Integration Page
 * Complete Salesforce CRM and sales platform integration
 */

import React from "react";
import { GetServerSideProps } from "next";
import Head from "next/head";
import Layout from "../../components/layout/Layout";
// import { SalesforceIntegration } from '../../../src/ui-shared/integrations/salesforce';

interface SalesforcePageProps {
  initialConfig?: {
    environment: "production" | "sandbox";
  };
}

const SalesforcePage: React.FC<SalesforcePageProps> = ({ initialConfig }) => {
  return (
    <>
      <Head>
        <title>Salesforce Integration | ATOM</title>
        <meta
          name="description"
          content="Customer relationship management and sales platform through Salesforce integration"
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />

        {/* Open Graph */}
        <meta property="og:title" content="Salesforce Integration | ATOM" />
        <meta
          property="og:description"
          content="Customer relationship management and sales platform through Salesforce integration"
        />
        <meta property="og:type" content="website" />
        <meta property="og:image" content="/images/integrations/salesforce-og.jpg" />

        {/* Twitter Card */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="Salesforce Integration | ATOM" />
        <meta
          name="twitter:description"
          content="Customer relationship management and sales platform through Salesforce integration"
        />
        <meta
          name="twitter:image"
          content="/images/integrations/salesforce-twitter.jpg"
        />

        {/* Salesforce Brand Colors */}
        <meta name="theme-color" content="#00A1E0" />
        <style>{`
          :root {
            --salesforce-primary: #00A1E0;
            --salesforce-secondary: #181E5C;
            --salesforce-accent: #FFB75D;
            --salesforce-success: #04844B;
            --salesforce-warning: #FFA500;
            --salesforce-error: #C23934;
          }
        `}</style>
      </Head>

      <Layout
        title="Salesforce Integration"
        description="Customer relationship management and sales platform through Salesforce integration"
      >
        {/* <SalesforceIntegration /> */}
        <div style={{ padding: "2rem", textAlign: "center" }}>
          <h2
            style={{
              fontSize: "1.5rem",
              fontWeight: "bold",
              marginBottom: "1rem",
            }}
          >
            Salesforce Integration
          </h2>
          <p style={{ color: "#6B7280" }}>
            Salesforce integration is temporarily unavailable. Please check back
            later.
          </p>
        </div>
      </Layout>
    </>
  );
};

export const getServerSideProps: GetServerSideProps<SalesforcePageProps> = async ({
  req,
}) => {
  // Get initial configuration from server-side
  const initialConfig = {
    environment:
      (process.env.SALESFORCE_ENVIRONMENT as "production" | "sandbox") ||
      "production",
  };

  return {
    props: {
      initialConfig,
    },
  };
};

export default SalesforcePage;