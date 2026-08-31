import React from "react";
import { ChevronRight, Home, Activity } from "lucide-react";
import IntegrationHealthDashboard from "../../components/integrations/IntegrationHealthDashboard";
import Link from "next/link";

const IntegrationHealthPage: React.FC = () => {
  return (
    <div className="max-w-[1200px] mx-auto p-6">
      {/* Breadcrumb Navigation */}
      <nav className="flex items-center space-x-2 text-sm text-gray-600 dark:text-gray-400 mb-6">
        <Link href="/" className="hover:text-gray-900 dark:text-gray-100 dark:hover:text-gray-100">
          Home
        </Link>
        <ChevronRight className="w-4 h-4" />
        <Link href="/integrations" className="hover:text-gray-900 dark:text-gray-100 dark:hover:text-gray-100">
          Integrations
        </Link>
        <ChevronRight className="w-4 h-4" />
        <span className="text-gray-900 dark:text-gray-100 font-medium">Health Status</span>
      </nav>

      {/* Page Header */}
      <div className="space-y-4 mb-8">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900 dark:text-white">
          Integration Health Dashboard
        </h1>
        <p className="text-lg text-gray-600 dark:text-gray-400 max-w-3xl">
          See which integrations are actually connected and whether their credentials
          still work. When a credential can be exercised directly, this dashboard makes
          one real read-only call to the provider and shows the result.
        </p>
      </div>

      {/* Health Dashboard Component */}
      <IntegrationHealthDashboard
        autoRefresh={true}
        refreshInterval={30000}
        showDetails={true}
      />

      {/* Additional Information */}
      <div className="mt-8 p-6 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
        <h2 className="text-xl font-semibold mb-3 text-blue-800 dark:text-blue-300">
          About This Dashboard
        </h2>
        <div className="space-y-3 text-blue-700 dark:text-blue-200">
          <p>
            • <strong>Auto-refresh:</strong> Status automatically re-checks every 30 seconds
          </p>
          <p>
            • <strong>Status Indicators:</strong> Green = verified healthy, Yellow = connected but unverified, Red = unreachable
          </p>
          <p>
            • <strong>Verification:</strong> One real read-only API call to the provider with the stored credential, where possible
          </p>
          <p>
            • <strong>Response Time:</strong> Real measured duration of that provider call (only shown for verified checks)
          </p>
          <p>
            • <strong>Connection Sources:</strong> In-app connections, tenant connectors, and backend environment credentials
          </p>
        </div>
      </div>
    </div>
  );
};

export default IntegrationHealthPage;
