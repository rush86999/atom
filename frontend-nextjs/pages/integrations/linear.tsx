import React from "react";
import LinearIntegration from "@/components/LinearIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const LinearPage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="linear">
      <LinearIntegration />
    </WithIngestionStatus>
  );
};

export default LinearPage;
