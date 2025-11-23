# NextAuth Production Setup Guide

## Prerequisites
- PostgreSQL database running
- `DATABASE_URL` environment variable configured

## Step 1: Run Database Migration

```bash
# Connect to your PostgreSQL database
psql $DATABASE_URL

# Run the migration
\i backend/migrations/001_create_users_table.sql

# Verify table creation
\dt users
```

## Step 2: Environment Variables

Ensure these variables are set in your `.env` file:

```bash
# Required for NextAuth
DATABASE_URL=postgresql://user:password@host:port/database
NEXTAUTH_SECRET=your-secret-key-here  # Generate with: openssl rand -base64 32
NEXTAUTH_URL=http://localhost:3000    # Or your production URL

# Optional: For encryption
ATOM_ENCRYPTION_KEY=your-encryption-key-here
```

## Step 3: Create Your First User

### Option A: Using the Registration API

```bash
curl -X POST http://localhost:3000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your@email.com",
    "password": "yourSecurePassword123",
    "name": "Your Name"
  }'
```

### Option B: Direct Database Insert (for testing)

```sql
-- Generate a hashed password (bcrypt with 10 rounds)
-- You can use an online bcrypt generator or Node.js:
-- node -e "const bcrypt = require('bcryptjs'); console.log(bcrypt.hashSync('your-password', 10));"

INSERT INTO users (email, password_hash, name)
VALUES (
  'admin@example.com',
  '$2a$10$YOUR_BCRYPT_HASH_HERE',
  'Admin User'
);
```

## Step 4: Test Login

1. Navigate to: `http://localhost:3000/auth/signin`
2. Enter your email and password
3. You should be redirected to the dashboard

## Verification Checklist

- [ ] Users table created successfully
- [ ] Can create new users via registration API
- [ ] Can login with created credentials
- [ ] Wrong password is rejected
- [ ] User ID appears in session (check browser dev tools → Application → Cookies)
- [ ] Net Worth API returns user-specific data (not empty)

## Troubleshooting

### "Cannot connect to database"
- Check `DATABASE_URL` is correct
- Ensure PostgreSQL is running
- Test connection: `psql $DATABASE_URL`

### "Authentication error" in logs
- Check `lib/auth.ts` imports are correct
- Verify `bcryptjs` is installed: `npm list bcryptjs`
- Check database has users table: `\dt users` in psql

### "User not found" after registration
- Check user was actually created: `SELECT * FROM users;`
- Verify email matches exactly (case-sensitive)

## Security Notes

- **Passwords**: Hashed with bcrypt (10 rounds) - never stored in plain text
- **Sessions**: JWT-based with `NEXTAUTH_SECRET` encryption
- **Database**: Use SSL in production (`DATABASE_URL` with `?sslmode=require`)
- **Email Validation**: Add email verification for production use

## Next Steps

1. **Email Verification**: Add email confirmation flow
2. **Password Reset**: Implement forgot password feature
3. **OAuth Providers**: Add Google/GitHub login (optional)
4. **Rate Limiting**: Add login attempt limits
5. **Session Management**: Implement logout functionality

## Migration from Mock Users

If you were using the demo user (demo@example.com), it no longer exists. Create a new user account using the registration API or database insert method above.
