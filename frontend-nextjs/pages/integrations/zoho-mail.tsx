import React from "react";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";
import ZohoIntegrationDetail from "@/components/integrations/ZohoIntegrationDetail";

const ZohoMailPage: React.FC = () => (
  <WithIngestionStatus integrationId="zoho-mail">
  <ZohoIntegrationDetail
    appName="Zoho Mail"
    description="Business email and communication in the Zoho suite"
    category="communication"
    coveredServices={["Zoho suite (Books, Inventory, CRM, WorkDrive)", "Zoho Mail"]}
  
    />
  </WithIngestionStatus>
);

export default ZohoMailPage;
