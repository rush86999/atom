import React from "react";
import Head from "next/head";
import WhatsAppBusinessIntegration from "@/components/integrations/WhatsAppBusinessIntegration";

const WhatsAppPage: React.FC = () => (
  <>
    <Head>
      <title>WhatsApp Business Integration | ATOM</title>
      <meta name="description" content="Connect WhatsApp Business to automate messaging" />
    </Head>
    <div className="p-6 max-w-5xl mx-auto">
      <WhatsAppBusinessIntegration />
    </div>
  </>
);

export default WhatsAppPage;
