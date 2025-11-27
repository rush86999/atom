import React from "react";
import HubSpotIntegration from "../../components/integrations/hubspot/HubSpotIntegration";
import Head from "next/head";

const HubSpotIntegrationPage: React.FC = () => {
  return (
    <>
      <Head>
        <title>HubSpot Integration | ATOM</title>
        <meta name="description" content="Complete CRM and marketing automation platform with advanced search capabilities" />
      </Head>

      <div className="min-h-screen bg-white p-6">
        <div className="max-w-[1400px] mx-auto space-y-8">
          <div className="flex flex-col space-y-2">
            <h1 className="text-4xl font-bold">HubSpot Integration</h1>
            <p className="text-lg text-gray-600">
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
