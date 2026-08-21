import React from "react";
import ZohoIntegrationDetail from "@/components/integrations/ZohoIntegrationDetail";

const ZohoMailPage: React.FC = () => (
  <ZohoIntegrationDetail
    appName="Zoho Mail"
    description="Business email and communication in the Zoho suite"
    category="communication"
    coveredServices={["Zoho suite (Books, Inventory, CRM, WorkDrive)", "Zoho Mail"]}
  />
);

export default ZohoMailPage;
