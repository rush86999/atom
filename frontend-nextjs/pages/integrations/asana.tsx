import React from "react";
import AsanaIntegration from "@/components/AsanaIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const AsanaPage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="asana">
      <AsanaIntegration />
    </WithIngestionStatus>
  );
};

export default AsanaPage;
