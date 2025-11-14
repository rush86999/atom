/**
 * Microsoft Teams Integration Page
 * Complete Microsoft Teams communication and collaboration integration
 */

import React from "react";
import { GetServerSideProps } from "next";
import Head from "next/head";
import Layout from "../../components/layout/Layout";
// import { TeamsIntegration } from '../../../src/ui-shared/integrations/teams';

interface TeamsPageProps {
  initialConfig?: {
    environment: "production" | "sandbox";
  };
}

const TeamsPage: React.FC<TeamsPageProps> = ({ initialConfig }) => {
  return (
    <>
      <Head>
        <title>Microsoft Teams Integration | ATOM</title>
        <meta
          name="description"
          content="Team messaging and collaboration platform through Microsoft Teams integration"
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />

        {/* Open Graph */}
        <meta property="og:title" content="Microsoft Teams Integration | ATOM" />
        <meta
          property="og:description"
          content="Team messaging and collaboration platform through Microsoft Teams integration"
        />
        <meta property="og:type" content="website" />
        <meta property="og:image" content="/images/integrations/teams-og.jpg" />

        {/* Twitter Card */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="Microsoft Teams Integration | ATOM" />
        <meta
          name="twitter:description"
          content="Team messaging and collaboration platform through Microsoft Teams integration"
        />
        <meta
          name="twitter:image"
          content="/images/integrations/teams-twitter.jpg"
        />

        {/* Microsoft Teams Brand Colors */}
        <meta name="theme-color" content="#464EB8" />
        <style>{`
          :root {
            --teams-primary: #464EB8;
            --teams-secondary: #5B5FC7;
            --teams-accent: #7B83EB;
            --teams-success: #50E3C2;
            --teams-warning: #FFA500;
            --teams-error: #E74C3C;
          }
        `}</style>
      </Head>

      <Layout
        title="Microsoft Teams Integration"
        description="Team messaging and collaboration platform through Microsoft Teams integration"
      >
        {/* <TeamsIntegration /> */}
        <div style={{ padding: "2rem", textAlign: "center" }}>
          <h2
            style={{
              fontSize: "1.5rem",
              fontWeight: "bold",
              marginBottom: "1rem",
            }}
          >
            Microsoft Teams Integration
          </h2>
          <p style={{ color: "#6B7280" }}>
            Microsoft Teams integration is temporarily unavailable. Please check back
            later.
          </p>
        </div>
      </Layout>
    </>
  );
};

export const getServerSideProps: GetServerSideProps<TeamsPageProps> = async ({
  req,
}) => {
  // Get initial configuration from server-side
  const initialConfig = {
    environment:
      (process.env.TEAMS_ENVIRONMENT as "production" | "sandbox") ||
      "production",
  };

  return {
    props: {
      initialConfig,
    },
  };
};

export default TeamsPage;