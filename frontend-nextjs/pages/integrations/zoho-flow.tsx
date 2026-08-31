import React from "react";
import ZohoWebhookIntegrationDetail from "@/components/integrations/ZohoWebhookIntegrationDetail";

const ZohoFlowPage: React.FC = () => (
  <ZohoWebhookIntegrationDetail
    appName="Zoho Flow"
    description="Automation platform — flow execution events ingest into agent memory via webhook push"
    category="productivity"
    integrationId="zoho-flow"
    webhookPath="/webhooks/zoho-flow"
    secretEnv="ZOHOFLOW_WEBHOOK_SECRET"
    recordsLabel="events"
    recordsPath="/api/v1/integrations/zoho-flow/events"
  />
);

export default ZohoFlowPage;
