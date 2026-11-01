# Unforced teaching interaction — stock build

**Result: passed** on clean source `bc164fb96632` (`dirty=false`, PID 77558).

This is the small smoke requested after the forced-fill finding. It uses only
ordinary browser actions:

1. normal login;
2. complete the welcome wizard with its visible **Next** / **Start
   Automating** buttons;
3. open **Agents → Teach** (normal click) and the Training tab if collapsed;
4. open **Applies to and output format** by clicking its `<summary>`;
5. type the lesson, topic, font, size, headings and check **Document**;
6. click **Teach**, wait for **Lesson recorded**;
7. reload and confirm the lesson is present in the canvas training context.

No `fill(..., force=True)`, `page.evaluate`, `dispatch_event`, coordinate click,
or `sessionStorage` shortcut is used. The script is
`scripts/acceptance/teaching_interaction_smoke.py`; `result.json` records the
9 checks and the serving identity; `teaching-recorded.png` is the UI after the
lesson was accepted; `health.json` is the captured runtime identity.

The lesson survived reload (`teaching_points` included the new marker). The
previous **blocked** result in `../employee-execution-training-actionability/`
was recorded on a string-retargeted build and is preserved as history; this
stock production build at the default ports passed.
