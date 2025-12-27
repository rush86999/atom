
# Contributing New Integrations to Atom

Atom is designed to be highly extensible. We support two types of integrations:
1. **Catalog pieces**: Automated pieces from external ecosystems (Future support).
2. **Native implementations**: High-performance, deep integrations built directly into Atom's core.

## 1. Adding a New Integration (The Easy Way)

If you just want to add a piece that exists in the Activepieces ecosystem:
1. Find the piece name (e.g., `@activepieces/piece-slack`).
2. Add it to `frontend-nextjs/lib/auto-generated-pieces.ts`.
3. Run the seeding script:
   ```bash
   python backend/scripts/seed_integrations.py
   ```

## 2. Implementing a Native Integration (Full Power)

For deep functionality like ROI tracking, Unified Search, or AI behaviors, you should build a **Native Integration**.

### Backend Steps
1. **Create the router**: Add a new file in `backend/integrations/[service]_routes.py`.
2. **Register the router**: Add it to `INTEGRATION_REGISTRY` in `backend/core/lazy_integration_registry.py`.
   - Atom uses **Lazy Loading**. The backend won't load your code until someone actually calls the endpoint, keeping the system extremely fast.
3. **Map the Piece ID**: (Optional) In `backend/scripts/seed_integrations.py`, add a mapping from the catalog Piece ID to your native ID in `NATIVE_MAPPING`.

### Frontend Steps
1. **Add UI components**: Create a folder in `frontend-nextjs/components/integrations/[service]/`.
2. **Register in Sidebar**: Your integration will automatically show up if it's in the catalog OR if you add it to `MANUAL_PIECES` in `integrations-catalog.ts`.

## 3. Leverage Unified APIs

Atomic features should use our **Unified API Layer** whenever possible:
- **Tasks**: Map to `unified_task_endpoints.py` to get Asana/Jira/Monday support for free.
- **Calendar**: Map to `unified_calendar_endpoints.py`.
- **Search**: All content is automatically indexed via `unified_search_endpoints.py`.

## Need Help?
Open an issue or join our Discord!
