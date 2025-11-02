/**
 * ATOM Jira OAuth Success and Error Pages
 * Handle OAuth flow completion
 */

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';

export default function JiraOAuthPage() {
  const router = useRouter();
  const [callbackData, setCallbackData] = useState({
    code: '',
    state: '',
    error: '',
    errorDescription: ''
  });

  useEffect(() => {
    if (typeof window !== 'undefined' && router.isReady) {
      const urlParams = new URLSearchParams(window.location.search);
      
      const data = {
        code: urlParams.get('code') || '',
        state: urlParams.get('state') || '',
        error: urlParams.get('error') || '',
        errorDescription: urlParams.get('description') || ''
      };
      
      setCallbackData(data);
      
      // Handle the callback
      if (data.code) {
        // Success - notify parent window
        if (window.opener) {
          window.opener.postMessage({
            type: 'JIRA_OAUTH_SUCCESS',
            code: data.code,
            state: data.state
          }, window.location.origin);
        }
        
        // Close popup after a brief delay
        setTimeout(() => {
          window.close();
        }, 2000);
      } else if (data.error) {
        // Error - notify parent window
        if (window.opener) {
          window.opener.postMessage({
            type: 'JIRA_OAUTH_ERROR',
            error: data.error,
            errorDescription: data.errorDescription
          }, window.location.origin);
        }
        
        // Close popup after a brief delay
        setTimeout(() => {
          window.close();
        }, 2000);
      }
    }
  }, [router.isReady]);

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full">
        <div className="text-center">
          {/* Success State */}
          {callbackData.code && (
            <>
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">✅</span>
              </div>
              <h1 className="text-2xl font-bold text-green-800 mb-2">Authorization Successful</h1>
              <p className="text-gray-600 mb-4">
                Your Jira workspace has been successfully connected to ATOM.
              </p>
              
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
                <div className="text-sm text-green-700">
                  <div className="font-semibold mb-1">Authorization Details:</div>
                  <div>Code: {callbackData.code.substring(0, 20)}...</div>
                  {callbackData.state && <div>State: {callbackData.state}</div>}
                </div>
              </div>
              
              <div className="text-sm text-gray-500">
                This window will close automatically in 2 seconds.
              </div>
            </>
          )}
          
          {/* Error State */}
          {callbackData.error && (
            <>
              <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">❌</span>
              </div>
              <h1 className="text-2xl font-bold text-red-800 mb-2">Authorization Failed</h1>
              <p className="text-gray-600 mb-4">
                There was an error connecting your Jira workspace to ATOM.
              </p>
              
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
                <div className="text-sm text-red-700">
                  <div className="font-semibold mb-1">Error Details:</div>
                  <div>Error: {callbackData.error}</div>
                  {callbackData.errorDescription && (
                    <div>Description: {callbackData.errorDescription}</div>
                  )}
                </div>
              </div>
              
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
                <div className="text-sm text-yellow-700">
                  <div className="font-semibold mb-1">Possible Solutions:</div>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Ensure you have granted all required permissions</li>
                    <li>Check that your Jira workspace is accessible</li>
                    <li>Verify the OAuth app is properly configured</li>
                    <li>Try the authorization process again</li>
                  </ul>
                </div>
              </div>
              
              <div className="text-sm text-gray-500">
                This window will close automatically in 2 seconds.
              </div>
            </>
          )}
          
          {/* Loading State */}
          {!callbackData.code && !callbackData.error && (
            <>
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4 animate-spin">
                <span className="text-2xl">⚙️</span>
              </div>
              <h1 className="text-2xl font-bold text-blue-800 mb-2">Processing Authorization</h1>
              <p className="text-gray-600">
                Please wait while we process your Jira authorization...
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export async function getServerSideProps() {
  // No server-side props needed for this page
  return {
    props: {}
  };
}