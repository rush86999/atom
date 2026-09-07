/**
 * Cross-component ping: a panel just ingested records for an integration.
 * The page's IngestionStatusPanel listens for this and refreshes
 * immediately instead of waiting for its next poll, so the per-app
 * "Records ingested / Last ingested" feedback is visible the moment an
 * ingest completes.
 */
export const INGESTION_UPDATED_EVENT = "atom:ingestion-updated";

export function notifyIngestionUpdated(integrationId: string): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent(INGESTION_UPDATED_EVENT, {
      detail: { integrationId },
    })
  );
}
