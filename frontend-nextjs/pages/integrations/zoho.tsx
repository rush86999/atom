import React from "react";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";
import ZohoIntegrationDetail from "@/components/integrations/ZohoIntegrationDetail";

// Suite-level landing page for /integrations/zoho. One Zoho app grant
// connects the whole suite via the unified
// GET /api/v1/auth/oauth/zoho/initiate flow, so this page reuses the same
// shared detail component as the per-app pages instead of adding a new one.
const ZohoPage: React.FC = () => (
  <WithIngestionStatus integrationId="zoho">
    <ZohoIntegrationDetail
      appName="Zoho"
      description="One consent connects the Zoho suite — pick any app below for its detail page"
      category="suite"
      coveredServices={["Zoho CRM", "Zoho Books", "Zoho Inventory", "Zoho WorkDrive", "Zoho Projects", "Zoho Mail"]}
      apps={[
        { name: "Zoho CRM", href: "/integrations/zoho-crm" },
        { name: "Zoho Books", href: "/integrations/zoho-books" },
        { name: "Zoho Inventory", href: "/integrations/zoho-inventory" },
        { name: "Zoho WorkDrive", href: "/integrations/zoho-workdrive" },
        { name: "Zoho Projects", href: "/integrations/zoho-projects" },
        { name: "Zoho Mail", href: "/integrations/zoho-mail" },
        { name: "Zoho Forms", href: "/integrations/zoho-forms" },
        { name: "Zoho Flow", href: "/integrations/zoho-flow" },
      ]}
    />
  </WithIngestionStatus>
);

export default ZohoPage;
