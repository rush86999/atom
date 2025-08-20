# Google OAuth
GOOGLE_CLIENT_ID=your_new_google_client_id
GOOGLE_CLIENT_SECRET=your_new_google_client_secret

# GitHub OAuth
GITHUB_CLIENT_ID=your_new_github_client_id
GITHUB_CLIENT_SECRET=your_new_github_client_secret

# Apple Sign-In (if applicable)
APPLE_CLIENT_ID=your_new_apple_service_id
APPLE_PRIVATE_KEY=your_new_apple_private_key
APPLE_KEY_ID=your_new_apple_key_id
APPLE_TEAM_ID=your_apple_team_id
```

## 💾 Environment Security

### Required `.env` Files
1. **Copy template**: `cp .env.example .env.local`
2. **Fill with your new credentials**
3. **Never commit `.env.local`**

### Environment Variables Checklist
- [ ] `POSTGRES_PASSWORD` set to secure password
- [ ] `JWT_SECRET` set to 32+ character random string
- [ ] `OPENAI_API_KEY` configured
- [ ] All OAuth credentials updated with rotated values

## 🔍 Security Verification

### Run Security Audit
```bash
# Check for any remaining secrets
grep -r "client.*secret\|secret.*=" src/ --exclude-dir=node_modules | grep -v "process.env"

# Verify .gitignore
grep -A 5 -B 5 "env" .gitignore

# Check for hardcoded keys
find . -type f -name "*.ts" -o -name "*.js" | xargs grep -l "sk-"
```

### Setup
```bash
# 1. Install dependencies
npm install

# 2. Setup environment
cp atomic-docker/app_build_docker/.env.example atomic-docker/app_build_docker/.env.local

# 3. Fill environment variables with rotated credentials
nano atomic-docker/app_build_docker/.env.local

# 4. Restart services
docker-compose down
docker-compose up -d
```

## 🚨 Post-Rotation Checklist

- [ ] **All exposed credentials have been rotated** in respective platforms
- [ ] **Environment variables updated** in `.env.local`
- [ **Services restarted** with new configuration
- [ ] **Application tested** to ensure authentication still works
- [ ] **Monitor authentication logs** for any suspicious activity
- [ ] **Verify OAuth redirect URLs** are correctly configured

## 📞 Need Help?

If you encounter issues during credential rotation:
1. Check respective platform documentation
2. Verify OAuth redirect URLs in your application
3. Ensure environment variables are loaded correctly
4. Test authentication flow with different providers

## 🔐 Best Practices

1. **Never commit credentials** to version control
2. **Use environment variables** for all sensitive data
3. **Rotate credentials** at least every 90 days
4. **Enable 2FA** on all developer accounts
5. **Use OAuth scopes** with minimal required permissions
6. **Monitor