import React from 'react';
import Head from 'next/head';

const GitlabEnhanced = () => {
  return (
    <>
      <Head>
        <title>GitLab Enhanced | ATOM</title>
      </Head>
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">GitLab Enhanced Integration</h1>
        <p className="text-gray-600 mb-4">Enterprise integration for GitLab services</p>
        <button className="bg-purple-600 hover:bg-purple-700 text-white font-medium px-4 py-2 rounded-md mt-4">
          Connect GitLab
        </button>
      </div>
    </>
  );
};

export default GitlabEnhanced;
