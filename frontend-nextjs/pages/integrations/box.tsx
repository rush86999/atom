/**
 * Box Integration Page
 * Complete Box file storage and collaboration integration
 */

import React from "react";
import { GetServerSideProps } from "next";
import Head from "next/head";
import Layout from "../../components/layout/Layout";
// import { BoxIntegration } from '../../../src/ui-shared/integrations/box';

interface BoxPageProps {
  initialConfig?: {
    environment: "production" | "sandbox";
  };
}

const BoxPage: React.FC<BoxPageProps> = ({ initialConfig }) => {
  return (
    <>
      <Head>
        <title>Box Integration | ATOM</title>
        <meta
          name="description"
          content="Complete file storage and collaboration through Box integration"
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />

        {/* Open Graph */}
        <meta property="og:title" content="Box Integration | ATOM" />
        <meta
          property="og:description"
          content="Complete file storage and collaboration through Box integration"
        />
        <meta property="og:type" content="website" />
        <meta property="og:image" content="/images/integrations/box-og.jpg" />

        {/* Twitter Card */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="Box Integration | ATOM" />
        <meta
          name="twitter:description"
          content="Complete file storage and collaboration through Box integration"
        />
        <meta
          name="twitter:image"
          content="/images/integrations/box-twitter.jpg"
        />

        {/* Box Brand Colors */}
        <meta name="theme-color" content="#0061D5" />
        <style>{`
          :root {
            --box-primary: #0061D5;
            --box-secondary: #041E42;
            --box-accent: #28A868;
            --box-success: #28A868;
            --box-warning: #F7941D;
            --box-error: #D93848;
          }
        `}</style>
      </Head>

      <Layout
        title="Box Integration"
        description="Complete file storage and collaboration through Box integration"
      >
        {/* <BoxIntegration /> */}
        <div style={{ padding: "2rem", textAlign: "center" }}>
          <h2
            style={{
              fontSize: "1.5rem",
              fontWeight: "bold",
              marginBottom: "1rem",
            }}
          >
            Box Integration
          </h2>
          <p style={{ color: "#6B7280" }}>
            Box integration is temporarily unavailable. Please check back
            later.
          </p>
        </div>
      </Layout>
    </>
  );
};

export const getServerSideProps: GetServerSideProps<BoxPageProps> = async ({
  req,
}) => {
  // Get initial configuration from server-side
  const initialConfig = {
    environment:
      (process.env.BOX_ENVIRONMENT as "production" | "sandbox") ||
      "production",
  };

  return {
    props: {
      initialConfig,
    },
  };
};

export default BoxPage;