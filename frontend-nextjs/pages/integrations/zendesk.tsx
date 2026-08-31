import React from "react";
import ZendeskIntegration from "@/components/ZendeskIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const ZendeskPage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="zendesk">
      <ZendeskIntegration />
    </WithIngestionStatus>
  );
};

export default ZendeskPage;