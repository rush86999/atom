import React from "react";
import DiscordIntegration from "@/components/DiscordIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const DiscordPage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="discord">
      <DiscordIntegration />
    </WithIngestionStatus>
  );
};

export default DiscordPage;
