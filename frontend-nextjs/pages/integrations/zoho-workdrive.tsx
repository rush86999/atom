import React from 'react';
import ZohoWorkDriveIngestion from '../../components/Settings/ZohoWorkDriveIngestion';
import { useSession } from 'next-auth/react';

export default function ZohoWorkDrivePage() {
    const { data: session } = useSession();
    const userId = (session?.user as any)?.id || 'demo-user';

    return (
        <div className="container mx-auto py-8">
            <ZohoWorkDriveIngestion userId={userId} />
        </div>
    );
}
