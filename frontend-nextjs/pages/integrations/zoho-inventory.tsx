import React from "react";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";
import ZohoIntegrationDetail from "@/components/integrations/ZohoIntegrationDetail";

const ZohoinventoryPage: React.FC = () => (
  <WithIngestionStatus integrationId="zoho-inventory">
  <ZohoIntegrationDetail
    appName="Zoho Inventory"
    description="Inventory management — items, stock levels and sales orders"
    category="ecommerce"
    coveredServices={["Zoho Inventory", "Zoho Inventory", "Zoho CRM", "Zoho WorkDrive"]}
  
    />
  </WithIngestionStatus>
);

export default ZohoinventoryPage;
