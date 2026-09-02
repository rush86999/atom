import React from 'react';
import IngestionStatusPanel from "@/components/integrations/IngestionStatusPanel";
import ZohoWorkDriveIngestion from '../../components/Settings/ZohoWorkDriveIngestion';

export default function ZohoWorkDrivePage() {
    // Identity comes from the authenticated session server-side (JWT/cookie);
    // there is deliberately no demo-user fallback here.
    // No <Layout> wrapper — _app.tsx already provides the app shell; wrapping
    // again rendered a second nested sidebar (duplicate navbar bug, same as
    // documented on ZohoIntegrationDetail).
    return (
        <div className="container mx-auto py-8">
            {/* Memory-ingestion progress (uniform across integration pages) */}
            <div className="p-6 pb-0 max-w-[1400px] mx-auto w-full">
                <IngestionStatusPanel integrationId="zoho-workdrive" />
            </div>
            <ZohoWorkDriveIngestion />
        </div>
    );
}
