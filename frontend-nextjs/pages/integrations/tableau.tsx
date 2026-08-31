import React from "react";
import TableauIntegration from "@/components/TableauIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const TableauPage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="tableau">
      <TableauIntegration />
    </WithIngestionStatus>
  );
};

export default TableauPage;
