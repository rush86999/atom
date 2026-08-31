import React from "react";
import BoxIntegration from "@/components/BoxIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const BoxPage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="box">
      <BoxIntegration />
    </WithIngestionStatus>
  );
};

export default BoxPage;
