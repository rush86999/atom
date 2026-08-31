import React from "react";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";
import ZohoIntegrationDetail from "@/components/integrations/ZohoIntegrationDetail";

const ZohobooksPage: React.FC = () => (
  <WithIngestionStatus integrationId="zoho-books">
  <ZohoIntegrationDetail
    appName="Zoho Books"
    description="Accounting software — invoices, contacts and chart of accounts"
    category="finance"
    coveredServices={["Zoho Books", "Zoho Inventory", "Zoho CRM", "Zoho WorkDrive"]}
  
    />
  </WithIngestionStatus>
);

export default ZohobooksPage;
