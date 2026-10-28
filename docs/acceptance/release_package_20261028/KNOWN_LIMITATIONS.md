# Known limitations

- One passing core UI loop after four preserved failures is a bounded pilot
  result, not a universal reliability guarantee.
- The Flash qualification covers the fixed 7-case screening and one core loop;
  it does not certify every prompt or workbook shape.
- The launch configuration is DeepSeek-only with `deepseek-flash` pinned for
  review turns. A silent fallback to Pro, local 8B or another provider is not
  acceptable; verify the actual served route after startup.
- Local `llama3.1:8b` demonstrated substantive judgment errors on trained
  assessments. It remains outside the supported trained-assessment launch
  configuration.
- Structured review is required. If the structured transport fails, the turn
  must fail closed with a diagnostic, not deliver an uncertified prose answer.
- Client timeout is 300,000 ms; backend turn and request deadlines are both
  180 s. Earlier 95 s/120 s/240 s evidence does not transfer.
- Streaming, broader BYOK, additional model comparisons and whole-app
  certification are separate work.
