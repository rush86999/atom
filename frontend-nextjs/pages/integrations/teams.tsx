import React from "react";
import TeamsIntegration from "@/components/TeamsIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const TeamsPage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="teams">
      <TeamsIntegration />
    </WithIngestionStatus>
  );
};

export default TeamsPage;
