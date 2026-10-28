# Post-start smoke

1. `GET /api/health` returns 200 and the expected isolated DB identity.
2. Login succeeds; the agent/canvas state is present.
3. Send one small assessment with the taught policy.
4. Confirm the actual response metadata and provider log show
   `deepseek-flash` / `deepseek`; reject any Pro/local/other route.
5. Confirm the review is certified and the rendered table cites the source row.
6. Confirm response, persisted result and fresh history agree.
7. Send one calculation ask and confirm the deterministic total/citations.
8. Confirm no unauthorized side-effect rows were created.
