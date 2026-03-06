# API Type Generation

**Last Updated:** 2026-03-06
**Phase:** 145 - Cross-Platform API Type Generation

## Overview

Atom uses automated TypeScript type generation from the backend FastAPI OpenAPI specification. This ensures compile-time type safety across the Next.js frontend, React Native mobile app, and Tauri desktop application.

**Key Benefits:**
- Single source of truth (backend OpenAPI spec)
- Zero type drift (types always match API contract)
- Compile-time error detection (type mismatches caught before runtime)
- Cross-platform consistency (web, mobile, desktop use same types)

## Architecture

```
Backend (FastAPI) → OpenAPI Spec → openapi-typescript → TypeScript Types
backend/main_api_app.py → backend/openapi.json → api-generated.ts
```

**Distribution Strategy:** Symlinks
- Frontend: `frontend-nextjs/src/types/api-generated.ts` (source of truth)
- Mobile: `mobile/src/types/api-generated.ts` → symlink to frontend
- Desktop: `frontend-nextjs/src-tauri/src-types/api-generated.ts` → symlink to frontend

## Local Development

### Generate Types

From the frontend directory:
```bash
cd frontend-nextjs
npm run generate:api-types
```

This regenerates types from the committed `backend/openapi.json` spec.

### Watch Mode (Auto-regenerate on backend changes)

```bash
cd frontend-nextjs
npm run generate:api-types:watch
```

Watch mode requires the backend server to be running:
```bash
cd backend
python -m uvicorn main_api_app:app --reload
```

### Verify Generated Types

```bash
cd frontend-nextjs
npx tsc --noEmit src/types/api-generated.ts
```

## Usage Examples

### Frontend (Next.js)

```typescript
import type { paths, components } from '@/types/api-generated';

// Extract response type for an endpoint
type AgentResponse = paths['/api/v1/agents/{agent_id}']['get']['responses']['200']['content']['application/json'];

// Use in component
function AgentProfile({ agentId }: { agentId: string }) {
  const [agent, setAgent] = useState<AgentResponse | null>(null);

  useEffect(() => {
    fetch(`/api/v1/agents/${agentId}`)
      .then(res => res.json())
      .then((data: AgentResponse) => setAgent(data));
  }, [agentId]);

  return <div>{agent?.name}</div>;
}
```

### Mobile (React Native)

```typescript
import type { paths, components } from '../../types/api-generated';

type Agent = components['schemas']['Agent'];

function AgentScreen({ agentId }: { agentId: string }) {
  const [agent, setAgent] = useState<Agent | null>(null);

  // Same fetch pattern as web
  // ...
}
```

### Desktop (Tauri)

```typescript
import type { paths, components } from '../src-types/api-generated';

// Tauri command with typed parameters
import { invoke } from '@tauri-apps/api/core';

type Agent = components['schemas']['Agent'];

async function getAgent(agentId: string): Promise<Agent> {
  return invoke('get_agent', { agentId });
}
```

## Type Extraction Patterns

### Path-based Types (Endpoint-specific)

```typescript
// Request body
type CreateAgentRequest = paths['/api/v1/agents']['post']['requestBody']['content']['application/json'];

// Response (200)
type AgentResponse = paths['/api/v1/agents/{agent_id}']['get']['responses']['200']['content']['application/json'];

// Error response (404)
type NotFoundResponse = paths['/api/v1/agents/{agent_id}']['get']['responses']['404']['content']['application/json'];
```

### Component Schemas (Reusable types)

```typescript
type Agent = components['schemas']['Agent'];
type Workflow = components['schemas']['Workflow'];
type Episode = components['schemas']['Episode'];
```

### Operation Types (Input parameters)

```typescript
type GetAgentParams = operations['getAgent']['parameters']['path'];
```

## CI/CD Integration

The `.github/workflows/api-type-generation.yml` workflow automatically:

1. Generates OpenAPI spec from backend routes
2. Runs openapi-typescript to generate TypeScript types
3. Verifies TypeScript compilation
4. Detects breaking changes with openapi-diff
5. Commits regenerated types to git

**Trigger Conditions:**
- Push to main/develop branches with backend Python file changes
- Pull requests modifying backend API routes
- Manual workflow dispatch

## Breaking Changes

When the backend API changes, the CI workflow:

1. Detects breaking changes via openapi-diff
2. Fails the build if breaking changes are found
3. Posts a PR comment with specific changes
4. Requires manual update of frontend code using affected types

**Handling Breaking Changes:**
1. Review the breaking change details in the CI logs
2. Update frontend/mobile/desktop code to use new API contracts
3. Regenerate types locally: `npm run generate:api-types`
4. Verify compilation: `npx tsc --noEmit`

## Troubleshooting

### Symlink Issues (macOS/Linux)

**Problem:** Types not updating in mobile or desktop after regeneration.

**Solution:** Verify symlinks point to correct location:
```bash
readlink mobile/src/types/api-generated.ts
readlink frontend-nextjs/src-tauri/src-types/api-generated.ts
```

Recreate if broken:
```bash
rm mobile/src/types/api-generated.ts
cd mobile/src/types
ln -s ../../../frontend-nextjs/src/types/api-generated.ts api-generated.ts
```

### Symlink Issues (Windows)

**Problem:** Symlink creation fails with "Permission denied" on Windows.

**Cause:** Windows requires Developer Mode or admin privileges for symlinks.

**Solutions:**
1. Enable Developer Mode (Settings → Update & Security → For developers)
2. Run terminal as Administrator
3. Fallback: Copy file instead of symlink (requires manual sync)

### TypeScript Compilation Errors

**Problem:** `npx tsc --noEmit` fails after type generation.

**Common causes:**
1. Namespace collisions (e.g., `User` type conflicts with existing type)
2. OpenAPI spec has invalid schema definitions
3. Generated file has syntax errors

**Solutions:**
1. Use `--namespace` flag: `npx openapi-typescript backend/openapi.json --namespace=Api`
2. Fix backend route definitions (Pydantic models, response models)
3. Regenerate types after fixes

### Missing Endpoints in Generated Types

**Problem:** Expected endpoint types are missing from api-generated.ts.

**Cause:** Backend route not included in OpenAPI spec (e.g., deprecated, hidden).

**Solution:** Verify route is included in OpenAPI spec:
```bash
cat backend/openapi.json | jq '.paths | keys'
```

### Type Import Errors

**Problem:** `Cannot find module '@/types/api-generated'`

**Cause:** TypeScript path mapping not configured.

**Solution:** Verify tsconfig.json has path mapping:
```json
{
  "compilerOptions": {
    "paths": {
      "@/types/*": ["./src/types/*"]
    }
  }
}
```

## Best Practices

1. **Never edit api-generated.ts manually** - Changes will be overwritten
2. **Commit generated types to git** - Fresh clones need types immediately
3. **Regenerate types after backend changes** - Run `npm run generate:api-types`
4. **Use type extraction patterns** - Prefer path-based types for endpoint-specific code
5. **Watch CI for breaking changes** - PR comments indicate required updates
6. **Use component schemas for reusable types** - `components['schemas']['Agent']`

## Related Documentation

- [API Contract Testing](./API_CONTRACT_TESTING.md) - Phase 128
- [OpenAPI Spec Generation](../backend/tests/scripts/generate_openapi_spec.py)
- [openapi-typescript Docs](https://www.npmjs.com/package/openapi-typescript)
