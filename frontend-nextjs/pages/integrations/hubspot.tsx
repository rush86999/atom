import React from "react";
import IngestionStatusPanel from "@/components/integrations/IngestionStatusPanel";
import HubSpotIntegration from "../../components/integrations/hubspot/HubSpotIntegration";
import Head from "next/head";

const HubSpotIntegrationPage: React.FC = () => {
  return (
    <>
      <Head>
        <title>HubSpot Integration | ATOM</title>
        <meta name="description" content="Complete CRM and marketing automation platform with advanced search capabilities" />
      </Head>
  {/* Memory-ingestion progress (uniform across integration pages) */}
  <div className="p-6 pb-0 max-w-[1400px] mx-auto w-full">
    <IngestionStatusPanel integrationId="hubspot" />
  </div>


      <div className="min-h-screen bg-white dark:bg-gray-900 p-6">
        <div className="max-w-[1400px] mx-auto space-y-8">
          <div className="flex flex-col space-y-2">
            <h1 className="text-4xl font-bold">HubSpot Integration</h1>
            <p className="text-lg text-gray-600 dark:text-gray-400">
              Complete CRM and marketing automation platform with advanced search
              capabilities
            </p>
          </div>

          <HubSpotIntegration />
        </div>
      </div>
    </>
  );
};

export default HubSpotIntegrationPage;
