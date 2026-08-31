import React from "react";
import Microsoft365Integration from "@/components/Microsoft365Integration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const Microsoft365Page: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="microsoft365">
      <Microsoft365Integration />
    </WithIngestionStatus>
  );
};

export default Microsoft365Page;
