# Frontend High-Impact Component Prioritization v11.0

**Generated**: 2026-04-24T17:35:58Z
**Phase**: 292-02

## Executive Summary

- **Total components analyzed**: 707
- **Overall line coverage**: 15.14%

| Criticality | Components | Definition |
|-------------|------------|------------|
| Critical | 19 | Core user-facing features (Canvas presentations, Chat interface, Agent Dashboard) |
| High | 17 | Integration components (WhatsApp, Slack, etc.) |
| Medium | 631 | UI components, page layouts, utility libraries |
| Low | 40 | Custom hooks, shared utilities |

## Criticality Definitions

| Tier | Score | Patterns | Description |
|------|-------|----------|-------------|
| Critical | 10 | components/canvas/, components/chat/, components/agent-dashboard/ | Core user-facing features |
| High | 7 | components/integrations/ | Integration components |
| Medium | 5 | components/ui/, pages/, lib/ | UI, pages, lib |
| Low | 3 | hooks/, shared/ | Hooks, shared utilities |

## Critical (Canvas, Chat, Agent Dashboard)

**19 components** — Core user-facing features with highest business impact

| Rank | Component | Coverage% | Lines | Uncovered | Priority Score |
|------|-----------|-----------|-------|-----------|----------------|
| 1 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/canvas-host.tsx | 0.00% | 93 | 93 | 930.00 |
| 2 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/CanvasHost.tsx | 0.00% | 53 | 53 | 530.00 |
| 3 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/AgentWorkspace.tsx | 0.00% | 51 | 51 | 510.00 |
| 4 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/ChatHistorySidebar.tsx | 0.00% | 48 | 48 | 480.00 |
| 5 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/ChatInterface.tsx | 0.00% | 45 | 45 | 450.00 |
| 6 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/ArtifactSidebar.tsx | 0.00% | 36 | 36 | 360.00 |
| 7 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/SearchResults.tsx | 0.00% | 32 | 32 | 320.00 |
| 8 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/ChatInput.tsx | 0.00% | 30 | 30 | 300.00 |
| 9 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/ChatHeader.tsx | 0.00% | 18 | 18 | 180.00 |
| 10 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/MessageList.tsx | 0.00% | 16 | 16 | 160.00 |
| 11 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/canvas/AgentOperationTracker.tsx | 26.92% | 52 | 38 | 13.61 |
| 12 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/canvas/IntegrationConnectionGuide.tsx | 72.05% | 68 | 19 | 2.60 |
| 13 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/canvas/AgentRequestPrompt.tsx | 79.48% | 78 | 16 | 1.99 |
| 14 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/canvas/PieChart.tsx | 69.69% | 33 | 10 | 1.41 |
| 15 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/canvas/BarChart.tsx | 70.00% | 30 | 9 | 1.27 |
| 16 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/canvas/LineChart.tsx | 70.00% | 30 | 9 | 1.27 |
| 17 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/canvas/ViewOrchestrator.tsx | 88.63% | 88 | 10 | 1.12 |
| 18 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/canvas/InteractiveForm.tsx | 92.77% | 83 | 6 | 0.64 |
| 19 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/canvas/OperationErrorGuide.tsx | 98.03% | 51 | 1 | 0.10 |

## High (Integrations)

**17 components** — Integration components with significant business impact

| Rank | Component | Coverage% | Lines | Uncovered | Priority Score |
|------|-----------|-----------|-------|-----------|----------------|
| 1 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/hubspot/HubSpotSearch.tsx | 0.00% | 144 | 144 | 1008.00 |
| 2 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/ZoomIntegration.tsx | 0.00% | 135 | 135 | 945.00 |
| 3 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/GoogleDriveIntegration.tsx | 0.00% | 121 | 121 | 847.00 |
| 4 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/OneDriveIntegration.tsx | 0.00% | 111 | 111 | 777.00 |
| 5 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/hubspot/HubSpotIntegration.tsx | 0.00% | 104 | 104 | 728.00 |
| 6 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/IntegrationHealthDashboard.tsx | 0.00% | 88 | 88 | 616.00 |
| 7 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/hubspot/HubSpotAIService.tsx | 0.00% | 77 | 77 | 539.00 |
| 8 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/monday/MondayIntegration.tsx | 0.00% | 68 | 68 | 476.00 |
| 9 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/hubspot/HubSpotPredictiveAnalytics.tsx | 0.00% | 61 | 61 | 427.00 |
| 10 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/hubspot/HubSpotWorkflowAutomation.tsx | 0.00% | 61 | 61 | 427.00 |
| 11 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/hubspot/HubSpotDashboard.tsx | 0.00% | 24 | 24 | 168.00 |
| 12 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/hubspot/HubSpotTest.tsx | 0.00% | 12 | 12 | 84.00 |
| 13 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/hubspot/index.ts | 0.00% | 6 | 6 | 42.00 |
| 14 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/monday/index.ts | 0.00% | 1 | 1 | 7.00 |
| 15 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/WhatsAppBusinessIntegration.tsx | 47.19% | 89 | 47 | 6.83 |
| 16 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/WhatsAppRealtimeStatus.tsx | 100.00% | 6 | 0 | 0.00 |
| 17 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/EnhancedWhatsAppBusinessIntegration.tsx | 100.00% | 1 | 0 | 0.00 |

## Medium (UI, Pages, Lib)

**631 components** — Supporting UI, page layouts, and utility libraries

| Rank | Component | Coverage% | Lines | Uncovered | Priority Score |
|------|-----------|-----------|-------|-----------|----------------|
| 1 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/WorkflowAutomation.tsx | 0.00% | 304 | 304 | 1520.00 |
| 2 | /Users/rushiparikh/projects/atom/frontend-nextjs/pages/integrations/salesforce.tsx | 0.00% | 277 | 277 | 1385.00 |
| 3 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/TeamsIntegration.tsx | 0.00% | 266 | 266 | 1330.00 |
| 4 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/Audio/AudioRecorder.tsx | 0.00% | 194 | 194 | 970.00 |
| 5 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/entity/EntitySchemaModal.tsx | 0.00% | 158 | 158 | 790.00 |
| 6 | /Users/rushiparikh/projects/atom/frontend-nextjs/pages/agents/index.tsx | 0.00% | 149 | 149 | 745.00 |
| 7 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/Voice/WakeWordDetector.tsx | 0.00% | 147 | 147 | 735.00 |
| 8 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/LinearIntegration.tsx | 0.00% | 145 | 145 | 725.00 |
| 9 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/MailchimpIntegration.tsx | 0.00% | 142 | 142 | 710.00 |
| 10 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/FreshdeskIntegration.tsx | 0.00% | 141 | 141 | 705.00 |
| 11 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/StripeIntegration.tsx | 0.00% | 138 | 138 | 690.00 |
| 12 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/GlobalChatWidget.tsx | 0.00% | 130 | 130 | 650.00 |
| 13 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/IntercomIntegration.tsx | 0.00% | 124 | 124 | 620.00 |
| 14 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/JiraOAuthFlow.tsx | 0.00% | 123 | 123 | 615.00 |
| 15 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/finance/TransactionsList.tsx | 0.00% | 115 | 115 | 575.00 |
| 16 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/dashboard/AnalyticsDashboard.tsx | 0.00% | 110 | 110 | 550.00 |
| 17 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/finance/InvoiceManager.tsx | 0.00% | 110 | 110 | 550.00 |
| 18 | /Users/rushiparikh/projects/atom/frontend-nextjs/lib/auth.ts | 0.00% | 109 | 109 | 545.00 |
| 19 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/Versioning/VersionHistoryTimeline.tsx | 0.00% | 107 | 107 | 535.00 |
| 20 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/Templates/TemplateEditor.tsx | 0.00% | 105 | 105 | 525.00 |
| 21 | /Users/rushiparikh/projects/atom/frontend-nextjs/pages/settings/account.tsx | 0.00% | 104 | 104 | 520.00 |
| 22 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/UnifiedServicesManager.tsx | 0.00% | 102 | 102 | 510.00 |
| 23 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/TableauIntegration.tsx | 0.00% | 100 | 100 | 500.00 |
| 24 | /Users/rushiparikh/projects/atom/frontend-nextjs/pages/integrations/bitbucket.tsx | 0.00% | 100 | 100 | 500.00 |
| 25 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/Templates/MyTemplatesPage.tsx | 0.00% | 96 | 96 | 480.00 |
| 26 | /Users/rushiparikh/projects/atom/frontend-nextjs/pages/dev-studio.tsx | 0.00% | 95 | 95 | 475.00 |
| 27 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/supervision/LiveMonitoringPanel.tsx | 0.00% | 94 | 94 | 470.00 |
| 28 | /Users/rushiparikh/projects/atom/frontend-nextjs/pages/workflows/builder.tsx | 0.00% | 94 | 94 | 470.00 |
| 29 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/Projects/KanbanBoard.tsx | 0.00% | 92 | 92 | 460.00 |
| 30 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/Versioning/VersionComparisonMetrics.tsx | 0.00% | 92 | 92 | 460.00 |

*Showing top 30 of 631 components*

## Low (Hooks, Shared)

**40 components** — Custom hooks and shared utilities

| Rank | Component | Coverage% | Lines | Uncovered | Priority Score |
|------|-----------|-----------|-------|-----------|----------------|
| 1 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/shared/CommunicationHub.tsx | 0.00% | 173 | 173 | 519.00 |
| 2 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/shared/TaskManagement.tsx | 0.00% | 167 | 167 | 501.00 |
| 3 | /Users/rushiparikh/projects/atom/frontend-nextjs/hooks/chat/useChatInterface.ts | 0.00% | 133 | 133 | 399.00 |
| 4 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/shared/CalendarManagement.tsx | 0.00% | 124 | 124 | 372.00 |
| 5 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/shared/CommentSection.tsx | 0.00% | 63 | 63 | 189.00 |
| 6 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/shared/PipelineSettingsPanel.tsx | 0.00% | 39 | 39 | 117.00 |
| 7 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/admin/shared/KeyboardShortcuts.tsx | 0.00% | 37 | 37 | 111.00 |
| 8 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/admin/shared/ErrorBoundary.tsx | 0.00% | 23 | 23 | 69.00 |
| 9 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/admin/shared/RetryWrapper.tsx | 0.00% | 21 | 21 | 63.00 |
| 10 | /Users/rushiparikh/projects/atom/frontend-nextjs/hooks/useFileUpload.ts | 0.00% | 19 | 19 | 57.00 |

*Showing top 10 of 40 components*

## Priority Score Formula

```
priority_score = (uncovered_lines * criticality_score) / (coverage_pct + 1)
```

### Why This Formula?

- **uncovered_lines**: More uncovered lines = more potential coverage gain
- **criticality_score**: Higher business criticality = more value per test
- **coverage_pct + 1**: Lower current coverage = higher priority
  - Adding 1 prevents division by zero for 0% coverage components

## Quick Wins (0% Coverage in Critical/High Tiers)

These 24 components have **zero coverage** but Critical or High business impact.

| Rank | Component | Uncovered Lines | Criticality | Priority Score |
|------|-----------|-----------------|-------------|----------------|
| 1 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/hubspot/HubSpotSearch.tsx | 144 | High | 1008.00 |
| 2 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/ZoomIntegration.tsx | 135 | High | 945.00 |
| 3 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/GoogleDriveIntegration.tsx | 121 | High | 847.00 |
| 4 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/OneDriveIntegration.tsx | 111 | High | 777.00 |
| 5 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/hubspot/HubSpotIntegration.tsx | 104 | High | 728.00 |
| 6 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/canvas-host.tsx | 93 | Critical | 930.00 |
| 7 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/IntegrationHealthDashboard.tsx | 88 | High | 616.00 |
| 8 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/hubspot/HubSpotAIService.tsx | 77 | High | 539.00 |
| 9 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/monday/MondayIntegration.tsx | 68 | High | 476.00 |
| 10 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/hubspot/HubSpotPredictiveAnalytics.tsx | 61 | High | 427.00 |
| 11 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/hubspot/HubSpotWorkflowAutomation.tsx | 61 | High | 427.00 |
| 12 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/CanvasHost.tsx | 53 | Critical | 530.00 |
| 13 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/AgentWorkspace.tsx | 51 | Critical | 510.00 |
| 14 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/ChatHistorySidebar.tsx | 48 | Critical | 480.00 |
| 15 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/ChatInterface.tsx | 45 | Critical | 450.00 |
| 16 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/ArtifactSidebar.tsx | 36 | Critical | 360.00 |
| 17 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/SearchResults.tsx | 32 | Critical | 320.00 |
| 18 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/ChatInput.tsx | 30 | Critical | 300.00 |
| 19 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/hubspot/HubSpotDashboard.tsx | 24 | High | 168.00 |
| 20 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/ChatHeader.tsx | 18 | Critical | 180.00 |
| 21 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/chat/MessageList.tsx | 16 | Critical | 160.00 |
| 22 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/hubspot/HubSpotTest.tsx | 12 | High | 84.00 |
| 23 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/hubspot/index.ts | 6 | High | 42.00 |
| 24 | /Users/rushiparikh/projects/atom/frontend-nextjs/components/integrations/monday/index.ts | 1 | High | 7.00 |

---

*Generated by prioritize_frontend_components.py*
*Phase: 292-02*
*Timestamp: 2026-04-24T17:35:58Z*