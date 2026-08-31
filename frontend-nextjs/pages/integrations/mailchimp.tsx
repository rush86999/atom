import React from "react";
import MailchimpIntegration from "@/components/MailchimpIntegration";
import WithIngestionStatus from "@/components/integrations/WithIngestionStatus";

const MailchimpPage: React.FC = () => {
  return (
    <WithIngestionStatus integrationId="mailchimp">
      <MailchimpIntegration />
    </WithIngestionStatus>
  );
};

export default MailchimpPage;
