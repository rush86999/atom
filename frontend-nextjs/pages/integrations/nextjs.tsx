/**
 * Next.js Integration Page
 * Dedicated page for Next.js/Vercel integration
 */

import React from "react";
import { Code, Rocket } from "lucide-react";

const NextjsIntegrationPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-8">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex flex-col items-center text-center space-y-8">
          <div className="p-4 bg-black dark:bg-white rounded-2xl">
            <Code className="w-12 h-12 text-white dark:text-black" />
          </div>

          <h1 className="text-5xl font-bold tracking-tight text-gray-900 dark:text-white">
            Next.js Integration
          </h1>

          <p className="text-xl text-gray-600 dark:text-gray-400 max-w-2xl">
            Next.js and Vercel integration is coming soon. This page will allow
            you to:
          </p>

          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-8 max-w-2xl w-full">
            <div className="space-y-4 text-left">
              <div className="flex items-start space-x-3">
                <Rocket className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
                <p className="text-gray-700 dark:text-gray-300">Deploy and manage Next.js applications</p>
              </div>
              <div className="flex items-start space-x-3">
                <Rocket className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
                <p className="text-gray-700 dark:text-gray-300">Monitor Vercel deployments and performance</p>
              </div>
              <div className="flex items-start space-x-3">
                <Rocket className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
                <p className="text-gray-700 dark:text-gray-300">Configure environment variables and domains</p>
              </div>
              <div className="flex items-start space-x-3">
                <Rocket className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
                <p className="text-gray-700 dark:text-gray-300">View build logs and analytics</p>
              </div>
              <div className="flex items-start space-x-3">
                <Rocket className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
                <p className="text-gray-700 dark:text-gray-300">Integrate with CI/CD pipelines</p>
              </div>
            </div>
          </div>

          <p className="text-gray-500 dark:text-gray-400 text-sm">
            Check back soon for updates on Next.js integration features.
          </p>
        </div>
      </div>
    </div>
  );
};

export default NextjsIntegrationPage;
