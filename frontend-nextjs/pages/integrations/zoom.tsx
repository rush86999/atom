/**
 * Zoom Integration Page
 * Complete Zoom video conferencing and collaboration integration
 */

import React from "react";
import { GetServerSideProps } from "next";
import Head from "next/head";
import Layout from "../../components/layout/Layout";
// import { ZoomIntegration } from '../../../src/ui-shared/integrations/zoom';

interface ZoomPageProps {
  initialConfig?: {
    environment: "production" | "sandbox";
  };
}

const ZoomPage: React.FC<ZoomPageProps> = ({ initialConfig }) => {
  return (
    <>
      <Head>
        <title>Zoom Integration | ATOM</title>
        <meta
          name="description"
          content="Video conferencing and collaboration platform through Zoom integration"
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />

        {/* Open Graph */}
        <meta property="og:title" content="Zoom Integration | ATOM" />
        <meta
          property="og:description"
          content="Video conferencing and collaboration platform through Zoom integration"
        />
        <meta property="og:type" content="website" />
        <meta property="og:image" content="/images/integrations/zoom-og.jpg" />

        {/* Twitter Card */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="Zoom Integration | ATOM" />
        <meta
          name="twitter:description"
          content="Video conferencing and collaboration platform through Zoom integration"
        />
        <meta
          name="twitter:image"
          content="/images/integrations/zoom-twitter.jpg"
        />

        {/* Zoom Brand Colors */}
        <meta name="theme-color" content="#2D8CFF" />
        <style>{`
          :root {
            --zoom-primary: #2D8CFF;
            --zoom-secondary: #0B5CFF;
            --zoom-accent: #F8681C;
            --zoom-success: #0EAD69;
            --zoom-warning: #F8681C;
            --zoom-error: #D83B01;
          }
        `}</style>
      </Head>

      <Layout
        title="Zoom Integration"
        description="Video conferencing and collaboration platform through Zoom integration"
      >
        {/* <ZoomIntegration /> */}
        <div style={{ padding: "2rem", textAlign: "center" }}>
          <h2
            style={{
              fontSize: "1.5rem",
              fontWeight: "bold",
              marginBottom: "1rem",
            }}
          >
            Zoom Integration
          </h2>
          <p style={{ color: "#6B7280" }}>
            Zoom integration is temporarily unavailable. Please check back
            later.
          </p>
        </div>
      </Layout>
    </>
  );
};

export const getServerSideProps: GetServerSideProps<ZoomPageProps> = async ({
  req,
}) => {
  // Get initial configuration from server-side
  const initialConfig = {
    environment:
      (process.env.ZOOM_ENVIRONMENT as "production" | "sandbox") ||
      "production",
  };

  return {
    props: {
      initialConfig,
    },
  };
};

export default ZoomPage;