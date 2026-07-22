# Atom Showcase — 5 "Wow" Scenarios

Real scenarios that demonstrate Atom's value. Each is designed to be
shareable as a video/GIF for social media, documentation, or demos.

## 1. 📊 Excel Formula Evaluation (Workbook Runtime)

**Setup:** Agent creates a spreadsheet with `=SUM(A1:A10)` and immediately sees the computed result — not a formula string.

**What to show:**
1. Ask the agent: "Create a budget spreadsheet with SUM and AVERAGE formulas"
2. Watch the agent write cells with formulas
3. Show the response: `=SUM(A1:A10) → 450` (computed instantly)
4. Insert a row → all formula references update automatically
5. Canvas renders with evaluated values + conditional formatting

**Why it's impressive:** Most AI tools write formula strings that don't evaluate until Excel opens the file. Atom runs the workbook.

**Recording script:** `examples/create_excel_spreadsheet.py`

---

## 2. 🖥️ Canvas Co-Editing with Agent

**Setup:** Open a standalone canvas at `/canvas`, edit a spreadsheet, chat with the agent in the side panel to modify it live.

**What to show:**
1. Navigate to Canvases → open a spreadsheet canvas
2. Type in the side chat: "Add a new column called 'Revenue' with values"
3. Watch the agent update the canvas in real-time (WebSocket)
4. Chat again: "Now add a SUM formula at the bottom"
5. Show the model badge on the agent's response

**Why it's impressive:** The agent and user co-edit the same canvas simultaneously. No context switching.

---

## 3. 🦙 100% Local AI (No Cloud, No API Key)

**Setup:** Start Atom with Ollama, chat with a local model, zero cloud dependency.

**What to show:**
1. Terminal: `ollama pull llama3:8b && ATOM_LOCAL_ONLY=true make backend`
   (Note: `scripts/dev.sh` launches the minimal smoke app; `make backend` runs
   the full `main_api_app:app` — recommended for demos.)
2. Open the app, log in
3. Send a message — the response comes from the local model
4. Show the routing dashboard: local model serving at $0.00 cost
5. Show Settings → Local Models: model registered, capabilities set

**Why it's impressive:** Full AI agent platform running on a laptop with zero cloud cost and zero data leaving the machine.

---

## 4. 📈 Learning Router Dashboard

**Setup:** Enable `ATOM_LEARNING_ROUTER=true`, interact with the app, watch the router learn.

**What to show:**
1. Go to Settings → Routing & Learning
2. Show the "Learning Router is off" banner → flip the flag
3. Send several chat messages with different complexity
4. Return to the dashboard — show per-model success rates updating
5. Show feedback samples accumulating
6. Give a thumbs-down on a response → dashboard updates

**Why it's impressive:** The routing dashboard makes the "learning" tangible — users can see the system adapting to their preferences.

---

## 5. 🏢 Office Automation (Word/Excel/PPTX)

**Setup:** Agent creates and modifies real Office documents — no Microsoft Office or LibreOffice desktop app needed.

**What to show:**
1. Ask: "Create a Word document with a meeting agenda"
2. Watch the agent generate the .docx file
3. Open it in the Canvas — fully rendered HTML preview
4. Edit inline → file syncs back to disk
5. Ask: "Convert this to a PowerPoint presentation"
6. Show the .pptx with slides

**Why it's impressive:** No native Office installation. Python-only (python-docx, openpyxl, python-pptx) + LibreOffice headless for rendering. The workbook runtime evaluates formulas.

---

## Sharing These Scenarios

- **X/Twitter:** 30-second screen recordings of scenarios 1, 3, and 5
- **YouTube:** 5-minute walkthrough of all 5 scenarios
- **GitHub README:** Link to this doc + embed GIFs
- **Reddit (r/LocalLLaMA, r/selfhosted):** Focus on scenario 3 (local model)
- **Hacker News:** "Show HN: Open-source AI agent platform with learning-based routing"
