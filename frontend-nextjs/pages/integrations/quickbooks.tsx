/**
 * QuickBooks Integration Page
 * Complete QuickBooks financial management and accounting integration
 */

import React from "react";
import { GetServerSideProps } from "next";
import Head from "next/head";
import Layout from "../../components/layout/Layout";
// import { QuickBooksIntegration } from '../../../src/ui-shared/integrations/quickbooks';

interface QuickBooksPageProps {
  initialConfig?: {
    environment: "production" | "sandbox";
  };
}

const QuickBooksPage: React.FC<QuickBooksPageProps> = ({ initialConfig }) => {
  return (
    <>
      <Head>
        <title>QuickBooks Integration | ATOM</title>
        <meta
          name="description"
          content="Financial management and accounting through QuickBooks integration"
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />

        {/* Open Graph */}
        <meta property="og:title" content="QuickBooks Integration | ATOM" />
        <meta
          property="og:description"
          content="Financial management and accounting through QuickBooks integration"
        />
        <meta property="og:type" content="website" />
        <meta property="og:image" content="/images/integrations/quickbooks-og.jpg" />

        {/* Twitter Card */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="QuickBooks Integration | ATOM" />
        <meta
          name="twitter:description"
          content="Financial management and accounting through QuickBooks integration"
        />
        <meta
          name="twitter:image"
          content="/images/integrations/quickbooks-twitter.jpg"
        />

        {/* QuickBooks Brand Colors */}
        <meta name="theme-color" content="#2CA01C" />
        <style>{`
          :root {
            --quickbooks-primary: #2CA01C;
            --quickbooks-secondary: #6BAA75;
            --quickbooks-accent: #3498DB;
            --quickbooks-success: #2CA01C;
            --quickbooks-warning: #F39C12;
            --quickbooks-error: #E74C3C;
          }
        `}</style>
      </Head>

      <Layout
        title="QuickBooks Integration"
        description="Financial management and accounting through QuickBooks integration"
      >
        {/* <QuickBooksIntegration /> */}
        <div style={{ padding: "2rem", textAlign: "center" }}>
          <h2
            style={{
              fontSize: "1.5rem",
              fontWeight: "bold",
              marginBottom: "1rem",
            }}
          >
            QuickBooks Integration
          </h2>
          <p style={{ color: "#6B7280" }}>
            QuickBooks integration is temporarily unavailable. Please check back
            later.
          </p>
        </div>
      </Layout>
    </>
  );
};

export const getServerSideProps: GetServerSideProps<QuickBooksPageProps> = async ({
  req,
}) => {
  // Get initial configuration from server-side
  const initialConfig = {
    environment:
      (process.env.QUICKBOOKS_ENVIRONMENT as "production" | "sandbox") ||
      "production",
  };

  return {
    props: {
      initialConfig,
    },
  };
};

export default QuickBooksPage;