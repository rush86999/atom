import React from "react";
import QuickBooksIntegration from "@/components/QuickBooksIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const QuickBooksPage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="quickbooks">
      <QuickBooksIntegration />
    </WithIngestionStatus>
  );
};

export default QuickBooksPage;