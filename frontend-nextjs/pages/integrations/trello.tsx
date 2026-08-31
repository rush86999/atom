import React from "react";
import TrelloIntegration from "@/components/TrelloIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const TrelloPage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="trello">
      <TrelloIntegration />
    </WithIngestionStatus>
  );
};

export default TrelloPage;