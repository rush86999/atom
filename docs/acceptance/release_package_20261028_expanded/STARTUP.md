# Scoped pilot startup

This is a scoped pilot, not a global policy change. Use an isolated world/run
directory and a dedicated backend/frontend port.

1. Create or select the scratch world and back up its database first.
2. Export the values from `config.env.template` into the pilot process
   environment. Do not add API keys to the template; use the existing
   encrypted BYOK store.
3. Start the isolated backend and production frontend, for example with the
   acceptance launcher:

```bash
python backend/scripts/orchestration_acceptance/preview_stack.py \
  --world <world> up --backend-port 8061 --frontend-port 3114 \
  --byok-source-dir /path/to/existing/backend/data
```

4. Verify from the running process, not from the shell:
   - provider policy allowed = `["deepseek"]`;
   - preferred/review model = `deepseek-flash`;
   - structured review = on;
   - streaming = off;
   - turn and request deadlines = 180 s.
5. Run the post-start smoke check before inviting a pilot user.
