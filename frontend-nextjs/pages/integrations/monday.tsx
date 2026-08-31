import React, { useState, useEffect, useCallback } from "react";
import IngestionStatusPanel from "@/components/integrations/IngestionStatusPanel";
import Head from "next/head";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import MondayIntegration from "@/components/integrations/monday/MondayIntegration";

const TOKEN_KEY = "monday_access_token";

const MondayPage: React.FC = () => {
  const [accessToken, setAccessToken] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setAccessToken(window.localStorage.getItem(TOKEN_KEY));
  }, []);

  const handleConnect = useCallback(async () => {
    try {
      const res = await fetch("/api/monday/auth/url");
      const data = await res.json();
      if (data?.url) {
        window.location.href = data.url;
      }
    } catch (e) {
      // fall back to the provider home page if the endpoint is unreachable
      window.location.href = "https://auth.monday.com/oauth2/authorize";
    }
  }, []);

  const handleDisconnect = useCallback(() => {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(TOKEN_KEY);
    setAccessToken(null);
  }, []);

  return (
    <>
      <Head>
        <title>Monday.com Integration | ATOM</title>
        <meta name="description" content="Connect Monday work OS to automate boards and items" />
      </Head>
  {/* Memory-ingestion progress (uniform across integration pages) */}
  <div className="p-6 pb-0 max-w-[1400px] mx-auto w-full">
    <IngestionStatusPanel integrationId="monday" />
  </div>

      <div className="p-6 max-w-5xl mx-auto">
        <Card className="mb-4">
          <CardHeader>
            <CardTitle className="text-lg">Monday.com</CardTitle>
            <CardDescription>
              Boards, items and analytics your agents can operate on.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <MondayIntegration
              accessToken={accessToken || undefined}
              onConnect={handleConnect}
              onDisconnect={handleDisconnect}
            />
          </CardContent>
        </Card>
      </div>
    </>
  );
};

export default MondayPage;
