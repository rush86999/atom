# Atomic Glossary of Terms

This glossary defines common terms used within the Atomic application to help you understand its features and functionality.

*   **Semantic Search:**
    Atomic uses semantic search to understand the meaning behind your event titles or natural language queries. Instead of just matching keywords, it grasps the intent, allowing it to find genuinely similar past events. This is key for accurately applying trained event templates. For example, it can understand that "Team Catch-up" and "Weekly Sync with Team" might be similar types of events.

*   **Event Training:**
    The process of selecting an existing calendar event and designating it as a template for future, similar events. This involves telling Atomic which properties of the event (like its duration, color, or attendees) should be remembered and potentially reused.

*   **Event Template:**
    A previously "trained" event. Its specific attributes (e.g., duration, color, reminders, notes structure, etc.) are stored and can be automatically applied to new events that Atomic identifies as similar, based on your "Copy Settings."

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
