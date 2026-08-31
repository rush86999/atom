import React from "react";
import AzureIntegration from "@/components/AzureIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const AzurePage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="azure">
      <AzureIntegration />
    </WithIngestionStatus>
  );
};

export default AzurePage;
