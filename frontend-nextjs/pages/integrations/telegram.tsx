import React, { useState } from "react";
import IngestionStatusPanel from "@/components/integrations/IngestionStatusPanel";
import Head from "next/head";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";
import IntegrationStatusCard from "@/components/integrations/IntegrationStatusCard";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("auth_token") || window.localStorage.getItem("token");
}

const TelegramPage: React.FC = () => {
  const { toast } = useToast();
  const [channelId, setChannelId] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);

  const handleSend = async () => {
    if (!channelId.trim() || !message.trim()) {
      toast({ title: "Channel ID and message are required", variant: "destructive" });
      return;
    }
    setSending(true);
    try {
      const token = getToken();
      const res = await fetch("/api/telegram/send", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ channel_id: channelId.trim(), message: message.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        toast({ title: data?.detail || "Failed to send message", variant: "destructive" });
      } else {
        toast({ title: "Message sent", variant: "success" });
        setMessage("");
      }
    } catch (e: any) {
      toast({ title: e?.message || "Failed to send message", variant: "destructive" });
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      <Head>
        <title>Telegram Integration | ATOM</title>
        <meta name="description" content="Send and receive Telegram messages through your agents" />
      </Head>
  {/* Memory-ingestion progress (uniform across integration pages) */}
  <div className="p-6 pb-0 max-w-[1400px] mx-auto w-full">
    <IngestionStatusPanel integrationId="telegram" />
  </div>

      <div className="p-6 max-w-3xl mx-auto space-y-4">
        <IntegrationStatusCard
          title="Telegram"
          description="Communicate with contacts over Telegram. Reaching this page no longer requires the bot webhook to be pre-configured in the UI."
          statusEndpoint="/api/telegram/status"
          statusRequiresAuth
          statusKey="telegram"
        />
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Send Message</CardTitle>
            <CardDescription>Send a message to a Telegram chat (channel or user chat id).</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              placeholder="Channel / chat ID (e.g. @my_channel or 123456789)"
              value={channelId}
              onChange={(e) => setChannelId(e.target.value)}
            />
            <Textarea
              placeholder="Message text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={3}
            />
            <Button onClick={handleSend} disabled={sending}>
              {sending ? "Sending…" : "Send Message"}
            </Button>
          </CardContent>
        </Card>
      </div>
    </>
  );
};

export default TelegramPage;
