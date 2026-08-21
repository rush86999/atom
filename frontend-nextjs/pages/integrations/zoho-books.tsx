import React from "react";
import ZohoIntegrationDetail from "@/components/integrations/ZohoIntegrationDetail";

const ZohobooksPage: React.FC = () => (
  <ZohoIntegrationDetail
    appName="Zoho Books"
    description="Accounting software — invoices, contacts and chart of accounts"
    category="finance"
    coveredServices={["Zoho Books", "Zoho Inventory", "Zoho CRM", "Zoho WorkDrive"]}
  />
);

export default ZohobooksPage;
