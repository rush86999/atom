import React from "react";
import ZohoIntegrationDetail from "@/components/integrations/ZohoIntegrationDetail";

const ZohoProjectsPage: React.FC = () => (
  <ZohoIntegrationDetail
    appName="Zoho Projects"
    description="Project management — portals, projects and tasks in the Zoho suite"
    category="productivity"
    coveredServices={["Zoho suite (Books, Inventory, CRM, WorkDrive)", "Zoho Projects"]}
  />
);

export default ZohoProjectsPage;
