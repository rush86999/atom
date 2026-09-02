import React from 'react';
import IngestionStatusPanel from "@/components/integrations/IngestionStatusPanel";
import ZohoWorkDriveIngestion from '../../components/Settings/ZohoWorkDriveIngestion';

export default function ZohoWorkDrivePage() {
    // _app.tsx already wraps every page in <Layout> — including one here
    // rendered the sidebar twice.
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
