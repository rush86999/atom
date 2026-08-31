import React from "react";
import ZoomIntegration from "@/components/ZoomIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const ZoomPage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="zoom">
      <ZoomIntegration />
    </WithIngestionStatus>
  );
};

export default ZoomPage;
