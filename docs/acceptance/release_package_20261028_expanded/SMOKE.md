# Post-start smoke

1. `GET /api/health` returns 200 and the expected isolated DB identity.
2. Login succeeds; the pilot canvas/agent state is present.
3. Send one small assessment and confirm response metadata/provider logs show
   `deepseek-flash` / `deepseek`; reject Pro/local/other.
4. Open the workbook canvas; confirm headers, values, formula source and a
   supported dependent calculation.
5. Import the EML fixture; confirm sender/To/Cc/attachment and reply draft.
   Do not send.
6. Open the DOCX/PPTX canvases; confirm tables/notes and a download.
7. Open a capability canvas; confirm effective operations and run one
   select/calculate/assess/edit/export from the structured receipt.
8. Confirm response, persisted state and fresh history agree.
