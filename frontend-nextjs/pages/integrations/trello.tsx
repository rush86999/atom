/**
 * Trello Integration Page
 * Complete Trello project management and task tracking integration
 */

import React from "react";
import { GetServerSideProps } from "next";
import Head from "next/head";
import Layout from "../../components/layout/Layout";
// import { TrelloIntegration } from '../../../src/ui-shared/integrations/trello';

interface TrelloPageProps {
  initialConfig?: {
    environment: "production" | "sandbox";
  };
}

const TrelloPage: React.FC<TrelloPageProps> = ({ initialConfig }) => {
  return (
    <>
      <Head>
        <title>Trello Integration | ATOM</title>
        <meta
          name="description"
          content="Project management and task tracking through Trello integration"
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />

        {/* Open Graph */}
        <meta property="og:title" content="Trello Integration | ATOM" />
        <meta
          property="og:description"
          content="Project management and task tracking through Trello integration"
        />
        <meta property="og:type" content="website" />
        <meta property="og:image" content="/images/integrations/trello-og.jpg" />

        {/* Twitter Card */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="Trello Integration | ATOM" />
        <meta
          name="twitter:description"
          content="Project management and task tracking through Trello integration"
        />
        <meta
          name="twitter:image"
          content="/images/integrations/trello-twitter.jpg"
        />

        {/* Trello Brand Colors */}
        <meta name="theme-color" content="#0079BF" />
        <style>{`
          :root {
            --trello-primary: #0079BF;
            --trello-secondary: #026AA7;
            --trello-accent: #61BD4F;
            --trello-success: #61BD4F;
            --trello-warning: #F2D600;
            --trello-error: #EB5A46;
          }
        `}</style>
      </Head>

      <Layout
        title="Trello Integration"
        description="Project management and task tracking through Trello integration"
      >
        {/* <TrelloIntegration /> */}
        <div style={{ padding: "2rem", textAlign: "center" }}>
          <h2
            style={{
              fontSize: "1.5rem",
              fontWeight: "bold",
              marginBottom: "1rem",
            }}
          >
            Trello Integration
          </h2>
          <p style={{ color: "#6B7280" }}>
            Trello integration is temporarily unavailable. Please check back
            later.
          </p>
        </div>
      </Layout>
    </>
  );
};

export const getServerSideProps: GetServerSideProps<TrelloPageProps> = async ({
  req,
}) => {
  // Get initial configuration from server-side
  const initialConfig = {
    environment:
      (process.env.TRELLO_ENVIRONMENT as "production" | "sandbox") ||
      "production",
  };

  return {
    props: {
      initialConfig,
    },
  };
};

export default TrelloPage;