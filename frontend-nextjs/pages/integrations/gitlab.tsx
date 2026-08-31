import React from "react";
import IngestionStatusPanel from "@/components/integrations/IngestionStatusPanel";
import Head from "next/head";
import IntegrationStatusCard from "@/components/integrations/IntegrationStatusCard";

const GitLabPage: React.FC = () => (
  <>
    <Head>
      <title>GitLab Integration | ATOM</title>
      <meta name="description" content="Connect GitLab to automate repositories, issues and pipelines" />
    </Head>
  {/* Memory-ingestion progress (uniform across integration pages) */}
  <div className="p-6 pb-0 max-w-[1400px] mx-auto w-full">
    <IngestionStatusPanel integrationId="gitlab" />
  </div>

    <div className="p-6 max-w-3xl mx-auto">
      <IntegrationStatusCard
        title="GitLab"
        description="Repositories, issues, merge requests and CI/CD pipelines your agents can operate on."
        statusEndpoint="/api/gitlab/status"
        connectUrl="/api/gitlab/auth/url"
        connectUrlIsJson
        connectLabel="Connect GitLab"
      />
    </div>
  </>
);

export default GitLabPage;
