import React from "react";
import IngestionStatusPanel from "@/components/integrations/IngestionStatusPanel";
import Head from "next/head";
import IntegrationStatusCard from "@/components/integrations/IntegrationStatusCard";

const XeroPage: React.FC = () => (
  <>
    <Head>
      <title>Xero Integration | ATOM</title>
      <meta name="description" content="Connect Xero accounting to automate invoices and contacts" />
    </Head>
  {/* Memory-ingestion progress (uniform across integration pages) */}
  <div className="p-6 pb-0 max-w-[1400px] mx-auto w-full">
    <IngestionStatusPanel integrationId="xero" />
  </div>

    <div className="p-6 max-w-3xl mx-auto">
      <IntegrationStatusCard
        title="Xero"
        description="Invoices, contacts and bank accounts your agents can reconcile and report on."
        statusEndpoint="/api/xero/status"
        connectUrl="/api/xero/auth/url"
        connectUrlIsJson
        connectLabel="Connect Xero"
      />
    </div>
  </>
);

export default XeroPage;
