import React from "react";
import NotionIntegration from "@/components/NotionIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const NotionPage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="notion">
      <NotionIntegration />
    </WithIngestionStatus>
  );
};

export default NotionPage;
