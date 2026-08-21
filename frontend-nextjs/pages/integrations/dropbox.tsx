import React from "react";
import Head from "next/head";
import IntegrationStatusCard from "@/components/integrations/IntegrationStatusCard";

const DropboxPage: React.FC = () => (
  <>
    <Head>
      <title>Dropbox Integration | ATOM</title>
      <meta name="description" content="Connect Dropbox to sync and analyze files" />
    </Head>
    <div className="p-6 max-w-3xl mx-auto">
      <IntegrationStatusCard
        title="Dropbox"
        description="Cloud storage and file sharing. Files you connect are analyzed and synced by your agents."
        statusEndpoint="/api/dropbox/oauth/status"
        connectUrl="/api/dropbox/oauth/url"
        connectUrlIsJson
        connectLabel="Connect Dropbox"
      />
    </div>
  </>
);

export default DropboxPage;
