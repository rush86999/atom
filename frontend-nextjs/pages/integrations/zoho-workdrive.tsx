import React from 'react';
import IngestionStatusPanel from "@/components/integrations/IngestionStatusPanel";
import { Layout } from '../../components/layout';
import ZohoWorkDriveIngestion from '../../components/Settings/ZohoWorkDriveIngestion';

export default function ZohoWorkDrivePage() {
    // Identity comes from the authenticated session server-side (JWT/cookie);
    // there is deliberately no demo-user fallback here.
    return (
        <Layout>
            <div className="container mx-auto py-8">
    {/* Memory-ingestion progress (uniform across integration pages) */}
    <div className="p-6 pb-0 max-w-[1400px] mx-auto w-full">
      <IngestionStatusPanel integrationId="zoho-workdrive" />
    </div>
                <ZohoWorkDriveIngestion />
            </div>
        </Layout>
    );
}
