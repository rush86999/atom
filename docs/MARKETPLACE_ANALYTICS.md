# Marketplace Analytics & Synchronization

This document describes the bidirectional synchronization and aggregated analytics system between self-hosted Atom instances and the Atom SaaS platform.

## Overview

Atom provides a federated marketplace where users can discover and install Skills, Agents, Workflows, and Specialist Domains. To improve the ecosystem, self-hosted instances can optionally share **aggregated, anonymized usage metrics** with the SaaS platform.

### Privacy-First Analytics

- **Aggregated Data Only**: We do not collect individual user data, message contents, or specific task details. We only collect execution counts, success/failure rates, and average durations per marketplace item.
- **Opt-In**: Analytics reporting is disabled by default. It can be enabled via environment variables.
- **Transparency**: All reported data is stored locally in the `marketplace_usage_local` table before being pushed, allowing administrators to audit what is being shared.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANALYTICS_ENABLED` | `false` | Set to `true` to enable usage reporting to SaaS. |
| `ATOM_SAAS_API_TOKEN` | (empty) | Your API token from `atomagentos.com`. Required for sync. |
| `INSTANCE_NAME` | `unnamed` | Friendly name for this instance in the SaaS dashboard. |

## Data Flow

1. **Local Tracking**: When a marketplace item (e.g., an Agent) is executed, the `MarketplaceUsageTracker` increments a local counter in the SQLite/PostgreSQL database.
2. **Registration**: Upon the first access to the Marketplace UI, the instance automatically registers itself with the SaaS backend using the provided `ATOM_SAAS_API_TOKEN`.
3. **Periodic Sync**: The `AnalyticsSyncWorker` runs periodically to push the aggregated local counts to the SaaS analytics ingestion layer.
4. **Ingestion**: The SaaS backend stores these metrics in a DuckDB analytical database for high-performance retrieval and reporting.

## Tracked Metrics

For each marketplace item, we track:
- `execution_count`: Total number of times the item was triggered.
- `success_count`: Number of successful completions.
- `total_duration_ms`: Cumulative execution time (used to calculate averages).

## Opting Out

To disable all analytics reporting:
1. Set `ANALYTICS_ENABLED=false` in your environment.
2. Restart the Atom services.

No further data will be collected or transmitted to the SaaS platform.

## Technical Details

- **Local Storage**: `MarketplaceUsage` model in `core/models.py`.
- **Sync Logic**: `AnalyticsSyncWorker` in `core/marketplace_sync_worker.py`.
- **API Client**: `AtomAgentOSMarketplaceClient` in `core/atom_saas_client.py`.
