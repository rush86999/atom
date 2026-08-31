import React from "react";
import IngestionStatusPanel from "@/components/integrations/IngestionStatusPanel";
import StripeIntegration from "../../components/StripeIntegration";

const StripeIntegrationPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-white dark:bg-gray-900 p-6">
      <div className="max-w-[1400px] mx-auto space-y-8">
    {/* Memory-ingestion progress (uniform across integration pages) */}
    <div className="p-6 pb-0 max-w-[1400px] mx-auto w-full">
      <IngestionStatusPanel integrationId="stripe" />
    </div>
        <div className="space-y-2">
          <h1 className="text-4xl font-bold">Stripe Integration</h1>
          <p className="text-gray-600 dark:text-gray-400 text-lg">
            Complete payment processing and financial management platform
          </p>
        </div>

        <StripeIntegration />
      </div>
    </div>
  );
};

export default StripeIntegrationPage;
