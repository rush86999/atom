import React from "react";
import JiraIntegration from "@/components/JiraIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const JiraPage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="jira">
      <JiraIntegration />
    </WithIngestionStatus>
  );
};

export default JiraPage;