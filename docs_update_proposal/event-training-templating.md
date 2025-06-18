# Event Training and Templating with Atomic

Event Training in Atomic is a powerful feature that allows you to turn your past events into reusable templates. When you "train" an event, you're teaching Atomic to recognize similar events in the future and automatically apply preferred settings. This saves you time and ensures consistency across your schedule.

## How to Train an Event

You can train an event directly from your calendar. When viewing an event, you'll typically find an option like "Train Event" (this flow is managed on the `UserTrainEvent` page within Atomic). This will take you through a process where you can specify which attributes of the event should be part of its template.

## Understanding "Copy" Settings

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

## Use-Case Example: Weekly Team Sync

Imagine you have a "Weekly Team Sync" meeting every Monday.

1.  **Create and Train:** You create the first instance of this meeting, set its duration to 60 minutes, assign it a specific color (e.g., blue), and add a reminder for 15 minutes before. You then use the "Train Event" feature.
2.  **Configure Copy Settings:** In your settings, you ensure `copyDuration`, `copyColor`, and `copyReminders` are enabled. You might disable `copyTitle` (if that were an option) or simply expect to modify the title for each specific week's agenda.
3.  **Future Scheduling:** The next time you type "Weekly Team Sync" or something very similar when creating an event for a Monday, Atomic recognizes it.
4.  **Automatic Application:** Atomic automatically sets the duration to 60 minutes, colors the event blue, and adds the 15-minute reminder. You only need to fill in any unique details for that week's meeting, like the agenda in the notes.

This significantly speeds up the process of populating your calendar with recurring or similar event types, ensuring they all follow your preferred setup.
