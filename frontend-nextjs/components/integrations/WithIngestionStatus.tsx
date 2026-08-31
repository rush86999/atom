import React from "react";
import IngestionStatusPanel from "./IngestionStatusPanel";

/**
 * Wraps a bespoke integration detail component so every integration page
 * shows data-ingestion progress uniformly, without each bespoke component
 * having to know about it.
 *
 * Usage in a page file:
 *   <WithIngestionStatus integrationId="slack">
 *     <SlackIntegration />
 *   </WithIngestionStatus>
 */
interface WithIngestionStatusProps {
  integrationId: string;
  children: React.ReactNode;
}

const WithIngestionStatus: React.FC<WithIngestionStatusProps> = ({
  integrationId,
  children,
}) => (
  <>
    <div className="p-6 pb-0 max-w-[1400px] mx-auto w-full">
      <IngestionStatusPanel integrationId={integrationId} />
    </div>
    {children}
  </>
);

export default WithIngestionStatus;
