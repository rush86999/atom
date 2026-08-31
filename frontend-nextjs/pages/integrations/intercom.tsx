import React from "react";
import IntercomIntegration from "@/components/IntercomIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const IntercomPage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="intercom">
      <IntercomIntegration />
    </WithIngestionStatus>
  );
};

export default IntercomPage;
