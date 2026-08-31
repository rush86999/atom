import React from "react";
import FreshdeskIntegration from "@/components/FreshdeskIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const FreshdeskPage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="freshdesk">
      <FreshdeskIntegration />
    </WithIngestionStatus>
  );
};

export default FreshdeskPage;
