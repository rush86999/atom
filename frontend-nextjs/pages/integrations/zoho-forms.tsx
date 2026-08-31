import React from "react";
import ZohoWebhookIntegrationDetail from "@/components/integrations/ZohoWebhookIntegrationDetail";

const ZohoFormsPage: React.FC = () => (
  <ZohoWebhookIntegrationDetail
    appName="Zoho Forms"
    description="Online form builder — form submissions ingest into agent memory via webhook push"
    category="productivity"
    integrationId="zoho-forms"
    webhookPath="/api/v1/integrations/zoho-forms/webhook"
    secretEnv="ZOHOFORMS_WEBHOOK_SECRET"
    recordsLabel="submissions"
    recordsPath="/api/v1/integrations/zoho-forms/submissions"
  />
);

export default ZohoFormsPage;
