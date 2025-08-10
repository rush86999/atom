# Atomic User Guide

This guide provides an overview of the key features of the Atom application and how to use them.

## Glossary of Terms

This glossary defines common terms used within the Atomic application to help you understand its features and functionality.

*   **Semantic Search:**
    Atomic uses semantic search to understand the meaning behind your event titles or natural language queries. Instead of just matching keywords, it grasps the intent, allowing it to find genuinely similar past events. This is key for accurately applying trained event templates. For example, it can understand that "Team Catch-up" and "Weekly Sync with Team" might be similar types of events.

*   **Event Training:**
    The process of selecting an existing calendar event and designating it as a template for future, similar events. This involves telling Atomic which properties of the event (like its duration, color, or attendees) should be remembered and potentially reused.

*   **Event Template:**
    A previously "trained" event. Its specific attributes (e.g., duration, color, reminders, notes structure, etc.) are stored and can be automatically applied to new events that Atomic identifies as similar, based on your "Copy" Settings.

*   **"Copy" Settings (General Definition):**
    A collection of preferences that give you fine-grained control over event training. Each "copy" setting (like `copyAvailability`, `copyColor`, `copyReminders`) is a toggle that determines whether that specific attribute from a trained event template is actually transferred to a new, similar event during automated scheduling or when suggestions are made. These are managed in Onboarding ("Event Defaults") and general Settings.

*   **Autopilot:**
    Atomic's automated daily scheduling assistant. Autopilot uses AI to analyze your calendar, tasks, and preferences. It can automatically schedule new items, apply event templates, adjust your schedule for optimization, and help ensure your day is well-planned according to your trained settings.

*   **Time Blocking:**
    The practice of dedicating specific blocks of time in your calendar for particular tasks, projects, or types of work (e.g., "Focus Work," "Email Catch-up"). Atomic can assist in scheduling these blocks, potentially using trained templates for different types of time blocks.

*   **Smart Tags / Categories:**
    Labels or tags that you can apply to events for organization and automation. These categories can have their own default settings (like a specific color or default duration). When Atomic's AI or Autopilot assigns a category to an event, these default settings can be automatically applied. They also help in filtering and understanding your schedule.

*   **Primary Calendar:**
    The main calendar account (e.g., your primary Google Calendar) that Atomic is configured to use for most of its scheduling operations, event creation, and updates. This is the calendar Atomic primarily "writes" to.

*   **Working Hours:**
    The time range you define within Atomic as your typical availability for work, meetings, and other professional activities. This helps Atomic make smarter scheduling decisions, such as when to schedule focus time or suggest meeting slots.

## Event Training and Templating

Event Training in Atomic is a powerful feature that allows you to turn your past events into reusable templates. When you "train" an event, you're teaching Atomic to recognize similar events in the future and automatically apply preferred settings. This saves you time and ensures consistency across your schedule.

### How to Train an Event

You can train an event directly from your calendar. When viewing an event, you'll typically find an option like "Train Event" (this flow is managed on the `UserTrainEvent` page in the application). This will take you through a process where you can specify which attributes of the event should be part of its template.

### Understanding "Copy" Settings

When you train an event, Atomic uses a set of "copy" settings to determine which attributes from the trained event (the template) should be applied to new, similar events. These settings are crucial for customizing how templates work for you.

Here are the common "copy" settings you can manage:

*   **`copyAvailability`**: If enabled, the "free/busy" status (e.g., Opaque/Transparent) from the trained event will be applied to new similar events.
*   **`copyTimeBlocking`**: Determines if buffer times (time set aside before or after an event) from the template are applied.
*   **`copyColor`**: The event's background color will be reused for similar new events.
*   **`copyPriorityLevel`**: If you assign priority levels to tasks or events, this setting will carry over the priority from the template.
*   **`copyModifiable`**: Controls whether Atomic's assistant can modify the event. If a trained event is marked as not modifiable, new similar events will also be protected from automatic changes by the assistant.
*   **`copyCategories`**: Tags or categories assigned to the trained event will be automatically applied to new similar events.
*   **`copyIsBreak`**: If the trained event was a break, similar new events will also be marked as breaks.
*   **`copyIsMeeting`**: If the trained event was a meeting, similar new events will also be identified as meetings.
*   **`copyIsExternalMeeting`**: Specifies if the "external meeting" status is copied.
*   **`copyReminders`**: Custom reminder settings (e.g., notify 10 minutes before) from the template will be applied.
*   **`copyTimePreference`**: Copies preferences like "morning," "afternoon," or specific time slots if the event was scheduled with such a preference.
*   **`copyDuration`**: Ensures that new similar events default to the same duration as the trained event.

You can typically manage these "copy" settings during the onboarding process in the "Event Defaults" step. They are also usually available in the main application settings, often under a section related to event preferences or defaults.

### Use-Case Example: Weekly Team Sync

Imagine you have a "Weekly Team Sync" meeting every Monday.

1.  **Create and Train:** You create the first instance of this meeting, set its duration to 60 minutes, assign it a specific color (e.g., blue), and add a reminder for 15 minutes before. You then use the "Train Event" feature.
2.  **Configure Copy Settings:** In your settings, you ensure `copyDuration`, `copyColor`, and `copyReminders` are enabled. You might disable `copyTitle` (if that were an option) or simply expect to modify the title for each specific week's agenda.
3.  **Future Scheduling:** The next time you type "Weekly Team Sync" or something very similar when creating an event for a Monday, Atomic recognizes it.
4.  **Automatic Application:** Atomic automatically sets the duration to 60 minutes, colors the event blue, and adds the 15-minute reminder. You only need to fill in any unique details for that week's meeting, like the agenda in the notes.

This significantly speeds up the process of populating your calendar with recurring or similar event types, ensuring they all follow your preferred setup.

## Autopilot

Autopilot is Atomic's intelligent scheduling assistant designed to proactively manage and optimize your calendar. When enabled, Autopilot runs daily, typically before your workday begins, to help you stay organized and ensure your schedule aligns with your priorities and preferences.

### What Autopilot Does

*   **Automated Planning:** Autopilot uses AI to analyze your existing events, tasks, and to-do items. It can then plan out your day by scheduling new items and optimizing the timing of existing ones.
*   **Applies Trained Templates:** A key feature of Autopilot is its ability to utilize your trained event templates. When it identifies events that match patterns from your trained templates (e.g., a "Project Update Meeting" title), it can automatically apply the settings (duration, color, reminders, etc.) you've defined in those templates.
*   **Leverages Smart Tags/Categories:** If you use smart tags or categories that have default settings (like a default duration or color for "Focus Work" blocks), Autopilot can apply these to relevant events, further automating your calendar setup.
*   **Daily Optimization:** Autopilot reviews your schedule for potential conflicts, opportunities for better time blocking, or unscheduled high-priority tasks, making adjustments to help you have a more productive day.

### Benefits of Using Autopilot

*   **Proactive Scheduling:** Reduces the manual effort of planning your days by having Atomic do the initial heavy lifting.
*   **Consistency:** Ensures that similar types of events are scheduled with consistent settings (duration, reminders, etc.) by applying your trained templates.
*   **Time-Saving:** Automates routine scheduling tasks, freeing you up to focus on your actual work rather than calendar management.
*   **Improved Organization:** Helps maintain a well-structured calendar by applying your predefined preferences and categorizations automatically.

### Configuring Autopilot

You can typically enable and manage Autopilot from the settings area within Atomic (often found under a section named "Autopilot" or similar, corresponding to the `UserViewAutopilotSettings.tsx` page in the application).

Key aspects of Autopilot configuration may include:

*   **Enabling/Disabling:** A primary toggle to turn Autopilot on or off.
*   **Run Frequency:** While Autopilot generally runs daily, there might be settings to adjust its behavior or confirm its operation. (Specific settings depend on the application's design).
*   **Integration with Event Defaults:** Autopilot's effectiveness is significantly enhanced by well-defined event templates and "copy" settings, as these provide the ruleset for how it should automate your event creation and modification.

By combining Autopilot with carefully trained event templates, you can create a highly personalized and automated scheduling system that works to keep your calendar aligned with your work style and priorities.

## Wake Word Detection

Atom supports hands-free operation through wake word detection. When you say the wake word (e.g., "Atom"), the application will start listening for your commands. This feature is implemented differently in the web and desktop versions:

*   **Web Version:** When enabled in the settings, the web version continuously listens for the wake word using your browser's microphone and a WebSocket-based Speech-to-Text (STT) service.
*   **Desktop Version:** The desktop version uses a more resource-friendly approach. Wake word detection is not always on. Instead, it's activated by a specific event within the application.

## Integrations

Atom can connect to a variety of third-party applications to extend its functionality. For a complete list of all available integrations and their setup guides, please see the [Integrations](./INTEGRATIONS.md) document.
