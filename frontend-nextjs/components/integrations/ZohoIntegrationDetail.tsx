import React from "react";
import { Layout } from "../../components/layout";
import { cn } from "../../lib/utils";

interface ZohoAppDetailProps {
  appName: string;
  description: string;
  category: string;
  /** Scopes/services this app's connect flow grants (all via one consent). */
  coveredServices: string[];
}

/**
 * Shared detail page for every Zoho suite app (Books, Inventory, CRM,
 * WorkDrive, Projects, Mail). One Server-based Zoho app consent connects the
 * whole suite — the Connect button opens the platform's unified
 * `GET /api/v1/auth/oauth/zoho/initiate` flow (same as the pilot doc).
 */
const ZohoIntegrationDetail: React.FC<ZohoAppDetailProps> = ({
  appName,
  description,
  category,
  coveredServices,
}) => {
  const connectUrl = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"}/api/v1/auth/oauth/zoho/initiate`;

  return (
    <Layout>
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-2">{appName} Integration</h1>
        <p className="text-gray-600 dark:text-gray-400 mb-4">{description}</p>

        <div className="mb-4">
          <span className="text-xs uppercase tracking-wide text-gray-500">
            Category
          </span>
          <span className="ml-2 text-sm">{category}</span>
        </div>

        <div className="mb-6">
          <span className="text-xs uppercase tracking-wide text-gray-500">
            Connected in this grant
          </span>
          <div className="mt-2 flex flex-wrap gap-2">
            {coveredServices.map((s) => (
              <span
                key={s}
                className={cn(
                  "px-2 py-1 rounded-md text-xs font-medium",
                  "bg-gray-100 dark:bg-gray-800",
                  "text-gray-700 dark:text-gray-300",
                )}
              >
                {s}
              </span>
            ))}
          </div>
        </div>

        <a
          href={connectUrl}
          data-testid="zoho-connect-link"
          className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 rounded-md"
        >
          Connect {appName}
        </a>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-3">
          One consent flow connects the entire Zoho suite (Books, Inventory,
          CRM, WorkDrive) with a single Zoho app grant. You must be signed in
          to the platform to start the flow.
        </p>
      </div>
    </Layout>
  );
};

export default ZohoIntegrationDetail;