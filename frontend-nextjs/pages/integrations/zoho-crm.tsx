import React from "react";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";
import ZohoIntegrationDetail from "@/components/integrations/ZohoIntegrationDetail";

const ZohocrmPage: React.FC = () => (
  <WithIngestionStatus integrationId="zoho-crm">
  <ZohoIntegrationDetail
    appName="Zoho CRM"
    description="Customer relationship management — leads and deals"
    category="crm"
    coveredServices={["Zoho CRM", "Zoho Books", "Zoho Inventory", "Zoho WorkDrive", "Zoho Projects"]}
  
    />
  </WithIngestionStatus>
);

export default ZohocrmPage;
