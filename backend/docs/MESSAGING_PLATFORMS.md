# ATOM Messaging Platforms Guide

Complete guide to all 9 fully implemented messaging platforms in ATOM.

**Last Updated**: February 4, 2026

---

## Overview

ATOM supports **9 fully implemented messaging platforms** with comprehensive features including:

- ✅ Proactive messaging (agents initiate conversations)
- ✅ Scheduled & recurring messages
- ✅ Condition monitoring & alerts
- ✅ Interactive components (buttons, cards, templates)
- ✅ Webhook integration
- ✅ Full governance integration

---

## Platform Matrix

| Platform | Status | Region | Users | Interactive | Webhooks | Auth |
|----------|--------|--------|-------|-------------|----------|------|
| Slack | ✅ 100% | Global | 75M+ | ✅ Buttons | ✅ | OAuth |
| Discord | ✅ 100% | Global | 150M+ | ✅ Components | ✅ | Bot Token |
| Teams | ✅ 100% | Enterprise | 280M+ | ✅ Cards | ✅ | OAuth |
| WhatsApp | ✅ 100% | Global | 2B+ | ✅ Lists | ✅ | API Key |
| Telegram | ✅ 100% | Global | 900M+ | ✅ Keyboards | ✅ | Bot Token |
| Google Chat | ✅ 100% | Enterprise | 30M+ | ✅ Cards/Dialogs | ✅ | OAuth 2.0 |
| Signal | ✅ 100% | Global | 100M+ | ❌ | ✅ | REST API |
| Messenger | ✅ 100% | Global | 1B+ | ✅ Quick Replies | ✅ | Page Token |
| LINE | ✅ 100% | Asia | 200M+ | ✅ Templates | ✅ | Channel Token |

**Interactive Components**: Buttons, keyboards, cards, dialogs, templates, quick replies

---

## Platform Details

### 1. Slack

**API Routes**: `/api/slack/*`
**Integration**: `integrations/atom_slack_integration.py`

#### Features
- **Messaging**: Full support with threading
- **Interactive Components**:
  - Buttons (clickable actions)
  - Select menus (dropdowns)
  - Modals (forms)
  - App Home (tab views)
- **Webhooks**: Events API with real-time updates
- **Authentication**: OAuth 2.0 with workspace installation
- **Rate Limits**: 1 message/second per workspace

#### Use Cases
- Enterprise team collaboration
- Rich interactive workflows
- Channel-based notifications
- App integrations with slash commands

#### Governance
- **STUDENT**: Blocked
- **INTERN**: Approval required
- **SUPERVISED**: Auto-approved + monitored
- **AUTONOMOUS**: Full access

---

### 2. Discord

**API Routes**: `/api/discord/*`
**Integration**: `integrations/atom_discord_integration.py`

#### Features
- **Messaging**: Full support with embeds
- **Interactive Components**:
  - Buttons (primary/secondary/danger/success)
  - Select menus (text/roles/users/channels)
  - Modals (multi-line forms)
  - Embeds (rich content)
- **Webhooks**: Gateway with intents
- **Authentication**: Bot token with OAuth2
- **Rate Limits**: 50 messages/channel/second

#### Use Cases
- Community engagement
- Gaming communities
- Rich embeds with images
- Role-based permissions

#### Governance
- **STUDENT**: Blocked
- **INTERN**: Approval required
- **SUPERVISED**: Auto-approved + monitored
- **AUTONOMOUS**: Full access

---

### 3. Microsoft Teams

**API Routes**: `/api/teams/*`
**Integration**: `integrations/atom_teams_integration.py`

#### Features
- **Messaging**: Full support with adaptive cards
- **Interactive Components**:
  - Adaptive Cards (rich UI)
  - Action Buttons (open URL, submit)
  - Input Sets (forms)
  - Task Modules (modals)
- **Webhooks**: Graph API with subscriptions
- **Authentication**: Azure AD OAuth 2.0
- **Rate Limits**: 2000 requests/tenant/second

#### Use Cases
- Enterprise workflows
- Microsoft 365 integration
- SharePoint collaboration
- Power Automate triggers

#### Governance
- **STUDENT**: Blocked
- **INTERN**: Approval required
- **SUPERVISED**: Auto-approved + monitored
- **AUTONOMOUS**: Full access

---

### 4. WhatsApp Business

**API Routes**: `/api/whatsapp/*`
**Integration**: `integrations/atom_whatsapp_integration.py`

#### Features
- **Messaging**: Full support with templates
- **Interactive Components**:
  - List Messages (menu options)
  - Reply Buttons (quick actions)
  - Call-to-Action buttons
  - Message Templates (pre-approved)
- **Webhooks**: Real-time message updates
- **Authentication**: API key + phone number ID
- **Rate Limits**: Tiered (1000-100,000 conversations/day)

#### Use Cases
- Customer support at scale
- Business notifications
- E-commerce updates
- Appointment reminders

#### Governance
- **STUDENT**: Blocked
- **INTERN**: Approval required
- **SUPERVISED**: Auto-approved + monitored
- **AUTONOMOUS**: Full access

---

### 5. Telegram

**API Routes**: `/api/telegram/*`
**Integration**: `integrations/atom_telegram_integration.py`

#### Features
- **Messaging**: Full support with markdown
- **Interactive Components**:
  - Inline Keyboards (buttons under messages)
  - Reply Keyboards (custom keyboards)
  - Callback Query Handling (button clicks)
  - Inline Mode (external chat results)
  - Chat Actions (typing indicators)
  - Polls (interactive voting)
- **Webhooks**: Long polling or webhook mode
- **Authentication**: Bot token from BotFather
- **Rate Limits**: 30 messages/second (bot), 20/minute (group)

#### Use Cases
- Secure messaging
- Bot communities
- News broadcasts
- Interactive games

#### Governance
- **STUDENT**: Blocked
- **INTERN**: Approval required
- **SUPERVISED**: Auto-approved + monitored
- **AUTONOMOUS**: Full access

---

### 6. Google Chat

**API Routes**: `/api/google-chat/*`
**Integration**: `integrations/atom_google_chat_integration.py`

#### Features
- **Messaging**: Full support with threading
- **Interactive Components**:
  - Interactive Cards (rich UI)
  - Buttons (onClick actions)
  - Text Paragraphs
  - Image Content
  - Input Widgets
  - Decorated Text
  - Dialogs (modal forms)
- **Space Management**: Create, list, add/remove members
- **Webhooks**: Google Chat Events API
- **Authentication**: OAuth 2.0 with service account
- **Rate Limits**: API quota-based

#### Use Cases
- Google Workspace integration
- Enterprise team chats
- Space-based collaboration
- Workflow notifications

#### Governance
- **STUDENT**: Blocked
- **INTERN**: Approval required
- **SUPERVISED**: Auto-approved + monitored
- **AUTONOMOUS**: Full access

---

### 7. Signal

**API Routes**: `/api/signal/*`
**Integration**: `integrations/adapters/signal_adapter.py`

#### Features
- **Messaging**: Full support with attachments
- **Interactive Components**: None (text-based only)
- **Receipts**: Read and delivery receipts
- **Webhooks**: Signal REST API callbacks
- **Authentication**: Phone number-based
- **Rate Limits**: 60 messages/minute

#### Use Cases
- Secure communications
- Privacy-first messaging
- End-to-end encryption required
- Personal notifications

#### Governance
- **STUDENT**: Blocked
- **INTERN**: Approval required
- **SUPERVISED**: Auto-approved + monitored
- **AUTONOMOUS**: Full access

---

### 8. Facebook Messenger

**API Routes**: `/api/messenger/*`
**Integration**: `integrations/adapters/messenger_adapter.py`

#### Features
- **Messaging**: Full support with tags
- **Interactive Components**:
  - Quick Replies (button suggestions)
  - Persistent Menu
  - Webviews (embedded websites)
  - Templates (generic, button, list)
- **User Profiles**: First name, last name, profile pic
- **Webhooks**: Graph API with subscriptions
- **Authentication**: Page access token
- **Rate Limits**: 1000 messages/day

#### Use Cases
- Facebook Page integration
- Social media customer service
- Marketing campaigns
- E-commerce transactions

#### Governance
- **STUDENT**: Blocked
- **INTERN**: Approval required
- **SUPERVISED**: Auto-approved + monitored
- **AUTONOMOUS**: Full access

---

### 9. LINE

**API Routes**: `/api/line/*`
**Integration**: `integrations/adapters/line_adapter.py`

#### Features
- **Messaging**: Full support with rich content
- **Interactive Components**:
  - Quick Replies (button suggestions)
  - Template Messages:
    - Buttons (title + image + actions)
    - Carousel (scrollable cards)
    - Confirm (yes/no dialogs)
  - Flex Messages (custom layouts)
- **User Profiles**: Display name, picture, status
- **Webhooks**: Messaging API events
- **Authentication**: Channel access token
- **Rate Limits**: 1000 messages/minute

#### Use Cases
- Asian market dominance (Japan, Taiwan, Thailand)
- Rich customer engagement
- Loyalty programs
- E-commerce integration

#### Governance
- **STUDENT**: Blocked
- **INTERN**: Approval required
- **SUPERVISED**: Auto-approved + monitored
- **AUTONOMOUS**: Full access

---

## Platform Selection Guide

### For Enterprise Use
- **Microsoft Teams** - Best for Microsoft 365 environments
- **Google Chat** - Best for Google Workspace environments
- **Slack** - Best for tech companies and startups

### For Customer Engagement
- **WhatsApp** - Best for global reach (2B users)
- **Facebook Messenger** - Best for social media integration
- **LINE** - Best for Asian markets

### For Security/Privacy
- **Signal** - Best for end-to-end encryption
- **Telegram** - Best for secure messaging
- **WhatsApp** - Good balance of security and reach

### For Community Engagement
- **Discord** - Best for gaming and communities
- **Telegram** - Best for large groups and channels
- **Slack** - Best for organized communities

### For Rich Interactions
- **Discord** - Best for complex modals and embeds
- **Google Chat** - Best for cards and dialogs
- **LINE** - Best for template messages and carousels

---

## Webhook Security

All platforms implement webhook verification:

| Platform | Verification Method |
|----------|---------------------|
| Slack | Signing secret + timestamp |
| Discord | Bot token verification |
| Teams | Azure AD validation |
| WhatsApp | HMAC SHA256 |
| Telegram | No built-in verification |
| Google Chat | Google Auth |
| Signal | No built-in verification |
| Messenger | X-Hub-Signature (HMAC) |
| LINE | X-Line-Signature (HMAC) |

---

## Quick Start Examples

### Send a Message (Slack)
```bash
curl -X POST http://localhost:8000/api/slack/send-message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "C12345",
    "text": "Hello from ATOM!"
  }'
```

### Send a Message (WhatsApp)
```bash
curl -X POST http://localhost:8000/api/whatsapp/send-message \
  -H "Content-Type: application/json" \
  -d '{
    "to": "15551234567",
    "message": "Hello from ATOM!"
  }'
```

### Send a Message (Telegram)
```bash
curl -X POST http://localhost:8000/api/telegram/send-message \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "123456789",
    "text": "Hello from ATOM!"
  }'
```

---

## Performance Characteristics

| Platform | Message Latency | Max Throughput | Uptime SLA |
|----------|----------------|----------------|------------|
| Slack | <100ms | 1 msg/sec | 99.9% |
| Discord | <50ms | 50 msg/sec | 99.95% |
| Teams | <200ms | High | 99.9% |
| WhatsApp | <500ms | Tiered | 99.9% |
| Telegram | <100ms | 30 msg/sec | 99.9% |
| Google Chat | <150ms | Quota-based | 99.9% |
| Signal | <200ms | 60 msg/min | 99% |
| Messenger | <200ms | 1000/day | 99.9% |
| LINE | <100ms | 1000/min | 99.9% |

---

## Rate Limiting Strategy

ATOM implements intelligent rate limiting:

1. **Per-Platform Limits**: Respects each platform's limits
2. **Token Buckets**: Smooths out burst traffic
3. **Priority Queues**: High-priority messages first
4. **Retry Logic**: Exponential backoff on failures
5. **Governance Checks**: <1ms cached lookups

---

## Supported Languages

All platforms support Unicode and emojis. Additional language support:

| Platform | Right-to-Left | Asian Languages | Formatting |
|----------|---------------|-----------------|------------|
| Slack | ✅ | ✅ | Markdown |
| Discord | ✅ | ✅ | Markdown |
| Teams | ✅ | ✅ | Markdown |
| WhatsApp | ✅ | ✅ | Basic |
| Telegram | ✅ | ✅ | Markdown/HTML |
| Google Chat | ✅ | ✅ | Basic |
| Signal | ✅ | ✅ | Basic |
| Messenger | ✅ | ✅ | Basic |
| LINE | ✅ | ✅ | Basic |

---

## Environment Setup

Each platform requires specific environment variables. See individual platform documentation for details.

---

## Getting Help

- **Documentation**: `/docs/MESSAGING_GUIDE.md`
- **API Reference**: `/docs/api/`
- **Examples**: `/examples/messaging/`
- **Support**: Open GitHub issue

---

**Version**: 1.0.0
**Last Updated**: February 4, 2026
**Maintained By**: ATOM Platform Team
