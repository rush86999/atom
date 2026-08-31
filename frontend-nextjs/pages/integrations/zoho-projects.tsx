import React from "react";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";
import ZohoIntegrationDetail from "@/components/integrations/ZohoIntegrationDetail";

const ZohoProjectsPage: React.FC = () => (
  <WithIngestionStatus integrationId="zoho-projects">
  <ZohoIntegrationDetail
    appName="Zoho Projects"
    description="Project management — portals, projects and tasks in the Zoho suite"
    category="productivity"
    coveredServices={["Zoho suite (Books, Inventory, CRM, WorkDrive)", "Zoho Projects"]}
  
    />
  </WithIngestionStatus>
);

export default ZohoProjectsPage;
