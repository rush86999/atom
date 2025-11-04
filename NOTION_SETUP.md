# Notion Integration Setup Guide

## 1. Create Notion Integration

1. Go to: https://www.notion.so/my-integrations
2. Click "**+ New integration**"
3. Fill in the form:
   - **Name**: ATOM Agent Integration
   - **Associated workspace**: Your workspace
   - **Logo**: (Optional) Upload ATOM logo
   - **Description**: ATOM Agent integration for data ingestion and memory management
   - **Linked URLs**: (Optional) Your app URL
4. Click "**Submit**"

## 2. Configure Integration Permissions

After creating the integration, you'll need to configure permissions:

### Required Capabilities:
- ✅ **Read content**: Required for ingesting pages and blocks
- ✅ **Search content**: Required for discovering content
- ✅ **Read user information**: Required for metadata extraction
- ❌ **Update content**: Not required for ingestion
- ❌ **Insert content**: Not required for ingestion

### User Capabilities:
- ✅ **Read user information**: Required for user metadata

### Client-side Requirements:
- **JavaScript**: No specific requirements for ingestion

## 3. Get Integration Credentials

After creating the integration, you'll see:

```
✅ Your integration is now active! 🎉
Integration ID: "xxxx-xxxx-xxxx-xxxx"
Internal ID: "xxxx-xxxx-xxxx-xxxx"
```

**Important**: Notion integration uses a different approach - no client secret or redirect URI for public integrations.

## 4. Share Notion Pages with Integration

To allow your integration to access pages:

1. Go to the page/database you want to integrate
2. Click "**Share**" (top right)
3. Under "**Invite**", search for your integration name
4. Select your integration and click "**Invite**"
5. Grant appropriate permissions (Read, Write, etc.)

## 5. Environment Variables

Add to your `.env` file:

```bash
# Notion Integration
NOTION_CLIENT_ID=your_integration_id
NOTION_INTEGRATION_SECRET=your_internal_id  # Not the same as client secret

# For OAuth (if using OAuth instead of public integration)
NOTION_CLIENT_SECRET=your_oauth_client_secret
NOTION_REDIRECT_URI=https://localhost/oauth/notion/callback
```

## 6. API Token (Alternative Method)

If you prefer using API tokens instead of integration:

1. Go to: https://www.notion.so/my-integrations
2. Click "**+ New integration**" 
3. After creation, you'll get an **Internal Integration Token**
4. Copy this token and use it as your access token

## 7. Test Integration

Test with a simple API call:

```bash
curl -X GET 'https://api.notion.com/v1/users/me' \
  -H 'Authorization: Bearer YOUR_INTEGRATION_TOKEN' \
  -H 'Notion-Version: 2022-06-28'
```

## 8. Integration Permissions Matrix

| Feature | Required | Description |
|---------|----------|-------------|
| **Page Access** | ✅ Required | Read pages for ingestion |
| **Database Access** | ✅ Required | Query databases for structured data |
| **Block Access** | ✅ Required | Read blocks for content extraction |
| **Comment Access** | ✅ Required | Extract comments for context |
| **User Info** | ✅ Required | Get user metadata |
| **Search API** | ✅ Required | Discover content |
| **Webhooks** | ✅ Required | Real-time updates (if available) |

## 9. Rate Limits

- **API Calls**: 3 calls per second (standard)
- **Batch Requests**: 100 items per request
- **Pagination**: Use cursors for large datasets
- **Page Size**: Maximum 100 items per request

## 10. Best Practices

1. **Share Selectively**: Only share necessary pages/databases
2. **Use Filters**: Filter by date ranges to reduce API calls
3. **Cache Results**: Cache page metadata to avoid repeated calls
4. **Handle Rate Limits**: Implement exponential backoff
5. **Use Batch Requests**: Process multiple items in single calls

## 11. Troubleshooting

### Common Issues:
- **403 Forbidden**: Integration doesn't have access to page
- **404 Not Found**: Page ID doesn't exist or no access
- **429 Too Many Requests**: Rate limit exceeded
- **400 Bad Request**: Invalid request format

### Solutions:
- Share pages with integration
- Check page IDs and permissions
- Implement rate limiting
- Validate request format

## 12. Security Considerations

- Store integration tokens securely
- Use environment variables
- Rotate tokens regularly
- Monitor API usage
- Limit access to necessary pages only

---

**🚀 Your Notion integration is now ready for ATOM agent data ingestion!**