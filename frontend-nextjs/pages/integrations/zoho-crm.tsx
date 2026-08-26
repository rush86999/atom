import React from "react";
import ZohoIntegrationDetail from "@/components/integrations/ZohoIntegrationDetail";

const ZohocrmPage: React.FC = () => (
  <ZohoIntegrationDetail
    appName="Zoho CRM"
    description="Customer relationship management — leads and deals"
    category="crm"
    coveredServices={["Zoho CRM", "Zoho Books", "Zoho Inventory", "Zoho WorkDrive", "Zoho Projects"]}
  />
);

export default ZohocrmPage;
