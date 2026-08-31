import React from "react";
import SlackIntegration from "@/components/SlackIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const SlackPage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="slack">
      <SlackIntegration />
    </WithIngestionStatus>
  );
};

export default SlackPage;
