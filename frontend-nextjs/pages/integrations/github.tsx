import React from "react";
import GitHubIntegration from "@/components/GitHubIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const GitHubPage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="github">
      <GitHubIntegration />
    </WithIngestionStatus>
  );
};

export default GitHubPage;