import React from 'react';
import GoogleDriveIntegration from '../components/integrations/GoogleDriveIntegration';
import Head from 'next/head';

const GoogleDrivePage: React.FC = () => {
  return (
    <>
      <Head>
        <title>Google Drive Integration | ATOM</title>
        <meta name="description" content="Connect and manage your Google Drive files with ATOM" />
      </Head>

      <div className="max-w-7xl mx-auto py-8 px-4">
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-4 text-blue-600">
            Google Drive Integration
          </h1>
          <p className="text-lg text-gray-600 max-w-3xl">
            Seamlessly connect your Google Drive account to search, manage, and ingest files directly within ATOM.
            Access your documents, spreadsheets, presentations, and more with powerful search capabilities.
          </p>
        </div>

        <GoogleDriveIntegration />
      </div>
    </>
  );
};

export default GoogleDrivePage;
