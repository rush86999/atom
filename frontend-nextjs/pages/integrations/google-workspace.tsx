import React from "react";
import GoogleWorkspaceIntegration from "@/components/GoogleWorkspaceIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const GoogleWorkspacePage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="google-workspace">
      <GoogleWorkspaceIntegration />
    </WithIngestionStatus>
  );
};

export default GoogleWorkspacePage;