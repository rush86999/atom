import React from 'react';
import { Layout } from '../../components/layout';
import ZohoWorkDriveIngestion from '../../components/Settings/ZohoWorkDriveIngestion';

export default function ZohoWorkDrivePage() {
    // Identity comes from the authenticated session server-side (JWT/cookie);
    // there is deliberately no demo-user fallback here.
    return (
        <Layout>
            <div className="container mx-auto py-8">
                <ZohoWorkDriveIngestion />
            </div>
        </Layout>
    );
}
