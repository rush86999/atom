#!/bin/bash
# OAuth Service Setup Script
# Generated: 2025-11-01 14:12:23

echo "🚀 Setting up OAuth Services for Production"
echo "=========================================="

echo ""
echo "📋 Remaining Services to Configure:"
echo "   - Microsoft Outlook"
echo "   - Microsoft Teams"
echo "   - GitHub"
echo ""

echo "🔧 Setup Instructions:"
echo ""
echo "1. Microsoft Azure (Outlook & Teams):"
echo "   - Go to: https://portal.azure.com"
echo "   - Create app registration"
echo "   - Add redirect URIs:"
echo "     - https://your-production-domain.com/api/auth/outlook/oauth2callback"
echo "     - https://your-production-domain.com/api/auth/teams/oauth2callback"
echo "   - Configure API permissions:"
echo "     - Mail.Read, Calendars.Read, Team.ReadBasic.All"
echo ""

echo "2. GitHub:"
echo "   - Go to: https://github.com/settings/developers"
echo "   - Create OAuth App"
echo "   - Set callback URL:"
echo "     - https://your-production-domain.com/api/auth/github/oauth2callback"
echo "   - Configure scopes: repo, user, read:org"
echo ""

echo "📝 Update .env.production with:"
echo "OUTLOOK_CLIENT_ID=your_microsoft_client_id"
echo "OUTLOOK_CLIENT_SECRET=your_microsoft_client_secret"
echo "TEAMS_CLIENT_ID=your_teams_client_id"
echo "TEAMS_CLIENT_SECRET=your_teams_client_secret"
echo "GITHUB_CLIENT_ID=your_github_client_id"
echo "GITHUB_CLIENT_SECRET=your_github_client_secret"
echo ""

echo "✅ After configuration:"
echo "   - Restart backend server"
echo "   - Run: python test_oauth_validation.py"
echo "   - Verify all 10 services show as connected"
echo ""

echo "🎉 Setup script completed"
