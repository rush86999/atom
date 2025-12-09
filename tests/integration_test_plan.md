# Integration Testing Plan - Phase 61-66 Fixes

## Test Environment Setup

### Prerequisites
1. Backend running: `cd backend && uvicorn main:app --reload`
2. Frontend running: `cd frontend-nextjs && npm run dev`
3. Browser: `http://localhost:3000`

## Test Cases

### 1. Slack Integration Tests

#### Test 1.1: List Channels
**Endpoint:** `GET /api/integrations/slack/channels`
**Expected:** Returns list of Slack channels
**Verification:**
```bash
curl -X GET "http://localhost:3000/api/integrations/slack/channels" \
  -H "Content-Type: application/json"
```
**Success Criteria:**
- ✅ Returns 200 status
- ✅ Returns JSON array of channels
- ✅ Each channel has `id` and `name` fields

#### Test 1.2: Get Messages from Channel
**Endpoint:** `GET /api/integrations/slack/messages?channelId=C123456`
**Expected:** Returns conversation history
**Verification:**
```bash
curl -X GET "http://localhost:3000/api/integrations/slack/messages?channelId=C123456" \
  -H "Content-Type: application/json"
```
**Success Criteria:**
- ✅ Returns 200 status
- ✅ Returns JSON array of messages
- ✅ Messages have proper timestamp and text fields

#### Test 1.3: Send Message
**Endpoint:** `POST /api/integrations/slack/messages/send`
**Expected:** Sends message successfully
**Verification:**
```bash
curl -X POST "http://localhost:3000/api/integrations/slack/messages/send" \
  -H "Content-Type: application/json" \
  -d '{"channel": "C123456", "text": "Test message"}'
```
**Success Criteria:**
- ✅ Returns 200 status
- ✅ Returns message confirmation with timestamp

#### Test 1.4: Get User Info
**Endpoint:** `GET /api/integrations/slack/users?userId=U123456`
**Expected:** Returns user information
**Verification:**
```bash
curl -X GET "http://localhost:3000/api/integrations/slack/users?userId=U123456" \
  -H "Content-Type: application/json"
```
**Success Criteria:**
- ✅ Returns 200 status
- ✅ Returns user object with profile data

---

### 2. HubSpot Integration Tests

#### Test 2.1: List Contacts
**Endpoint:** `GET /api/integrations/hubspot/contacts`
**Expected:** Returns list of contacts
**Verification:**
```bash
curl -X GET "http://localhost:3000/api/integrations/hubspot/contacts?limit=10" \
  -H "Content-Type: application/json"
```
**Success Criteria:**
- ✅ Returns 200 status
- ✅ Returns contacts array
- ✅ Each contact has email, firstName, lastName

#### Test 2.2: List Companies
**Endpoint:** `GET /api/integrations/hubspot/companies`
**Expected:** Returns list of companies
**Verification:**
```bash
curl -X GET "http://localhost:3000/api/integrations/hubspot/companies?limit=10" \
  -H "Content-Type: application/json"
```
**Success Criteria:**
- ✅ Returns 200 status
- ✅ Returns companies array with names and domains

#### Test 2.3: Analytics Dashboard
**Endpoint:** `GET /api/hubspot/analytics`
**Expected:** Returns comprehensive analytics
**Verification:**
```bash
curl -X GET "http://localhost:8000/api/hubspot/analytics" \
  -H "Content-Type: application/json"
```
**Success Criteria:**
- ✅ Returns 200 status
- ✅ Contains totalContacts, totalDeals, dealValue
- ✅ Contains pipeline stages and campaigns

#### Test 2.4: AI Predictions
**Endpoint:** `GET /api/hubspot/ai/predictions`
**Expected:** Returns ML models and predictions
**Verification:**
```bash
curl -X GET "http://localhost:8000/api/hubspot/ai/predictions" \
  -H "Content-Type: application/json"
```
**Success Criteria:**
- ✅ Returns 200 status
- ✅ Contains 3 ML models (conversion, churn, LTV)
- ✅ Each model has accuracy and performance metrics
- ✅ Contains predictions array
- ✅ Contains forecast data

#### Test 2.5: AI Lead Analysis
**Endpoint:** `POST /api/hubspot/ai/analyze-lead`
**Expected:** Returns AI lead scoring
**Verification:**
```bash
curl -X POST "http://localhost:8000/api/hubspot/ai/analyze-lead" \
  -H "Content-Type: application/json" \
  -d '{"contact_id": "contact123"}'
```
**Success Criteria:**
- ✅ Returns 200 status
- ✅ Contains leadScore and confidence
- ✅ Contains keyFactors array
- ✅ Contains recommendations array

---

### 3. Gmail Integration Tests

#### Test 3.1: OAuth Authorization
**Endpoint:** `GET /api/integrations/gmail/authorize`
**Expected:** Redirects to Google OAuth
**Verification:**
- Navigate to `/api/integrations/gmail/authorize`
**Success Criteria:**
- ✅ Redirects to `google.com/oauth`
- ✅ No 404 errors

#### Test 3.2: OAuth Callback
**Test manually:** Complete OAuth flow
**Success Criteria:**
- ✅ Successfully exchanges token
- ✅ Redirects back to app

#### Test 3.3: Memory Search
**Endpoint:** `GET /api/integrations/gmail/memory/search`
**Expected:** Returns search results from LanceDB
**Success Criteria:**
- ✅ Returns 200 status
- ✅ Uses correct LanceDB endpoint

---

### 4. Salesforce & Asana Profile Tests

#### Test 4.1: Salesforce Profile
**Endpoint:** `GET /api/integrations/salesforce/profile`
**Expected:** Returns user profile
**Verification:**
```bash
curl -X GET "http://localhost:3000/api/integrations/salesforce/profile" \
  -H "Content-Type: application/json"
```
**Success Criteria:**
- ✅ Returns 200 status (or mock data if not connected)
- ✅ No 405 Method Not Allowed errors

#### Test 4.2: Asana Profile
**Endpoint:** `GET /api/integrations/asana/profile`
**Expected:** Returns user profile
**Verification:**
```bash
curl -X GET "http://localhost:3000/api/integrations/asana/profile" \
  -H "Content-Type: application/json"
```
**Success Criteria:**
- ✅ Returns 200 status (or mock data)
- ✅ No 405 Method Not Allowed errors

---

### 5. Figma & Discord Profile Tests

#### Test 5.1: Figma Profile
**Endpoint:** `GET /api/integrations/figma/profile`
**Expected:** Returns Figma user info
**Success Criteria:**
- ✅ Uses GET method (not POST)
- ✅ Calls `/api/figma/user` backend endpoint

#### Test 5.2: Discord Profile
**Endpoint:** `GET /api/integrations/discord/profile`
**Expected:** Returns Discord user info
**Success Criteria:**
- ✅ Uses GET method (not POST)
- ✅ Calls `/api/discord/user` backend endpoint

---

## UI Testing (Manual)

### HubSpot Integration Page
**URL:** `http://localhost:3000/integrations/hubspot`

**Test Checklist:**
- [ ] Page loads without errors
- [ ] **8 tabs visible:** Overview, Contacts, Companies, Deals, Campaigns, Analytics, Predictive, AI Insights
- [ ] Analytics tab shows dashboard with metrics
- [ ] Predictive tab shows ML models (3 models)
- [ ] AI Insights tab shows lead scoring configuration
- [ ] All tabs load data correctly

### Integration Health Dashboard
**URL:** `http://localhost:3000/integrations`

**Test Checklist:**
- [ ] All integrations show health status
- [ ] "MOCK" badge appears for mock-mode integrations
- [ ] Refresh button works
- [ ] Status colors correct (green/yellow/red)

---

## Automated Test Script

Create file: `tests/test_integrations.sh`

```bash
#!/bin/bash

echo "Testing Integration Fixes - Phase 61-66"
echo "========================================"

# Test Slack endpoints
echo "\n1. Testing Slack Channels..."
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/integrations/slack/channels

echo "\n2. Testing HubSpot Contacts..."
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/integrations/hubspot/contacts

echo "\n3. Testing HubSpot Analytics..."
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/hubspot/analytics

echo "\n4. Testing HubSpot AI Predictions..."
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/hubspot/ai/predictions

echo "\n5. Testing Salesforce Profile..."
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/integrations/salesforce/profile

echo "\n6. Testing Figma Profile..."
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/integrations/figma/profile

echo "\n\nAll tests complete!"
```

---

## Expected Results Summary

| Integration | Endpoint | Method | Expected Status |
|------------|----------|--------|----------------|
| Slack | /channels | GET | 200 |
| Slack | /messages | GET | 200 |
| Slack | /messages/send | POST | 200 |
| Slack | /users | GET | 200 |
| HubSpot | /contacts | GET | 200 |
| HubSpot | /companies | GET | 200 |
| HubSpot | /analytics | GET | 200 |
| HubSpot | /ai/predictions | GET | 200 |
| HubSpot | /ai/analyze-lead | POST | 200 |
| Gmail | /authorize | GET | 302 redirect |
| Salesforce | /profile | GET | 200 |
| Asana | /profile | GET | 200 |
| Figma | /profile | GET | 200 |
| Discord | /profile | GET | 200 |

**All 14 endpoints should return success (200) or proper redirect (302)!**
