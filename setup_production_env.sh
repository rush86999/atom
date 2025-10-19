#!/bin/bash

# ATOM Personal Assistant - Production Environment Setup Script
# This script sets up the required environment variables for production deployment

echo "🚀 ATOM Personal Assistant - Production Environment Setup"
echo "=========================================================="

# Generate a secure Flask secret key
FLASK_SECRET_KEY=$(openssl rand -base64 32)
echo "Generated Flask Secret Key: $FLASK_SECRET_KEY"

# Generate a secure encryption key for OAuth tokens
ATOM_OAUTH_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
echo "Generated OAuth Encryption Key: $ATOM_OAUTH_ENCRYPTION_KEY"

# Database configuration
DATABASE_URL="postgresql://atom_user:atom_password@localhost:5432/atom_db"
echo "Database URL: $DATABASE_URL"

# API Keys (these should be set manually in production)
echo ""
echo "⚠️  IMPORTANT: Set the following API keys manually in your production environment:"
echo ""
echo "Required API Keys:"
echo "------------------"
echo "OPENAI_API_KEY=your_openai_api_key_here"
echo "NOTION_INTEGRATION_TOKEN=your_notion_token_here"
echo "TRELLO_API_KEY=your_trello_api_key_here"
echo "TRELLO_API_TOKEN=your_trello_token_here"
echo "ASANA_CLIENT_ID=your_asana_client_id_here"
echo "ASANA_CLIENT_SECRET=your_asana_client_secret_here"
echo "GOOGLE_CLIENT_ID=your_google_client_id_here"
echo "GOOGLE_CLIENT_SECRET=your_google_client_secret_here"
echo "DROPBOX_CLIENT_ID=your_dropbox_client_id_here"
echo "DROPBOX_CLIENT_SECRET=your_dropbox_client_secret_here"
echo ""

# Create .env file with generated values
cat > .env.production.generated << EOF
# ATOM Personal Assistant - Production Environment
# Generated on $(date)

# Flask Configuration
FLASK_SECRET_KEY=$FLASK_SECRET_KEY
PYTHON_API_PORT=5058

# Database Configuration
DATABASE_URL=$DATABASE_URL

# Encryption
ATOM_OAUTH_ENCRYPTION_KEY=$ATOM_OAUTH_ENCRYPTION_KEY

# API Keys (SET THESE MANUALLY)
# OPENAI_API_KEY=your_openai_api_key_here
# NOTION_INTEGRATION_TOKEN=your_notion_token_here
# TRELLO_API_KEY=your_trello_api_key_here
# TRELLO_API_TOKEN=your_trello_token_here
# ASANA_CLIENT_ID=your_asana_client_id_here
# ASANA_CLIENT_SECRET=your_asana_client_secret_here
# GOOGLE_CLIENT_ID=your_google_client_id_here
# GOOGLE_CLIENT_SECRET=your_google_client_secret_here
# DROPBOX_CLIENT_ID=your_dropbox_client_id_here
# DROPBOX_CLIENT_SECRET=your_dropbox_client_secret_here

# Service Configuration
LANCEDB_URI=./data/lancedb
LOG_LEVEL=INFO
DEBUG=false
EOF

echo "✅ Generated .env.production.generated file"
echo ""
echo "📋 Next Steps:"
echo "1. Copy the generated values to your production environment"
echo "2. Set the required API keys manually"
echo "3. Run: source .env.production.generated (or set as environment variables)"
echo "4. Start the application with: python backend/python-api-service/main_api_app.py"
echo ""
echo "🔒 Security Note: Keep these keys secure and never commit them to version control!"
