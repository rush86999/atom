import React from "react";
import IngestionStatusPanel from "@/components/integrations/IngestionStatusPanel";
import Head from "next/head";
import WhatsAppBusinessIntegration from "@/components/integrations/WhatsAppBusinessIntegration";

const WhatsAppPage: React.FC = () => (
  <>
    <Head>
      <title>WhatsApp Business Integration | ATOM</title>
      <meta name="description" content="Connect WhatsApp Business to automate messaging" />
    </Head>
  {/* Memory-ingestion progress (uniform across integration pages) */}
  <div className="p-6 pb-0 max-w-[1400px] mx-auto w-full">
    <IngestionStatusPanel integrationId="whatsapp" />
  </div>

    <div className="p-6 max-w-5xl mx-auto">
      <WhatsAppBusinessIntegration />
    </div>
  </>
);

export default WhatsAppPage;
