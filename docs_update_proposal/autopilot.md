# Understanding Autopilot in Atomic

Autopilot is Atomic's intelligent scheduling assistant designed to proactively manage and optimize your calendar. When enabled, Autopilot runs daily, typically before your workday begins, to help you stay organized and ensure your schedule aligns with your priorities and preferences.

## What Autopilot Does

*   **Automated Planning:** Autopilot uses AI to analyze your existing events, tasks, and to-do items. It can then plan out your day by scheduling new items and optimizing the timing of existing ones.
*   **Applies Trained Templates:** A key feature of Autopilot is its ability to utilize your trained event templates. When it identifies events that match patterns from your trained templates (e.g., a "Project Update Meeting" title), it can automatically apply the settings (duration, color, reminders, etc.) you've defined in those templates.
*   **Leverages Smart Tags/Categories:** If you use smart tags or categories that have default settings (like a default duration or color for "Focus Work" blocks), Autopilot can apply these to relevant events, further automating your calendar setup.
*   **Daily Optimization:** Autopilot reviews your schedule for potential conflicts, opportunities for better time blocking, or unscheduled high-priority tasks, making adjustments to help you have a more productive day.

## Benefits of Using Autopilot

*   **Proactive Scheduling:** Reduces the manual effort of planning your days by having Atomic do the initial heavy lifting.
*   **Consistency:** Ensures that similar types of events are scheduled with consistent settings (duration, reminders, etc.) by applying your trained templates.
*   **Time-Saving:** Automates routine scheduling tasks, freeing you up to focus on your actual work rather than calendar management.
*   **Improved Organization:** Helps maintain a well-structured calendar by applying your predefined preferences and categorizations automatically.

## Configuring Autopilot

You can typically enable and manage Autopilot from the settings area within Atomic (often found under a section named "Autopilot" or similar, corresponding to the `UserViewAutopilotSettings.tsx` page in the application).

Key aspects of Autopilot configuration may include:

*   **Enabling/Disabling:** A primary toggle to turn Autopilot on or off.
*   **Run Frequency:** While Autopilot generally runs daily, there might be settings to adjust its behavior or confirm its operation. (Specific settings depend on the application's design).
*   **Integration with Event Defaults:** Autopilot's effectiveness is significantly enhanced by well-defined event templates and "copy" settings, as these provide the ruleset for how it should automate your event creation and modification.

By combining Autopilot with carefully trained event templates, you can create a highly personalized and automated scheduling system that works to keep your calendar aligned with your work style and priorities.
