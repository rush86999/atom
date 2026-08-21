import React from "react";
import ZohoIntegrationDetail from "@/components/integrations/ZohoIntegrationDetail";

const ZohoinventoryPage: React.FC = () => (
  <ZohoIntegrationDetail
    appName="Zoho Inventory"
    description="Inventory management — items, stock levels and sales orders"
    category="ecommerce"
    coveredServices={["Zoho Inventory", "Zoho Inventory", "Zoho CRM", "Zoho WorkDrive"]}
  />
);

export default ZohoinventoryPage;
