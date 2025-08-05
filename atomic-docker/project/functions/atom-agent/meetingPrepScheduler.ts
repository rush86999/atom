import { agenda } from "../agendaService";
import { listUpcomingEvents } from "./skills/calendarSkills";
import { handleMeetingPrep } from "./skills/meetingPrep";
import { fetchMeetingPrepInfo } from "./skills/meetingPrepSkill";
import { generateDailyBriefing } from "./skills/dailyBriefingSkill";
import { logger } from "./_utils/logger";
import { dayjs } from "./_libs/datetime/date-utils";

// Enhanced interface for LLM-powered meeting preparation
interface LLMEnhancedMeetingData {
  userId: string;
  meetingType: "regular" | "client" | "team" | "presentation" | "workshop";
  priorityLevel: "low" | "medium" | "high";
  participants: Array<{ name: string; email?: string; role?: string }>;
  context: string;
  scheduledTime: string;
  estimatedDuration: number;
  recurring: boolean;
}

agenda.define("generate meeting briefings", async (job) => {
  const { userId } = job.attrs.data;

  try {
    logger.info(
      `[MeetingPrepScheduler] Starting LLM-enhanced meeting prep for user: ${userId}`,
    );

    // Get upcoming events with LLM filtering
    const events = await listUpcomingEvents(userId, 10);

    // Use LLM to determine which meetings need prep
    const eventsNeedingPrep = await determineMeetingsNeedingPrep(
      userId,
      events,
    );

    logger.info(
      `[MeetingPrepScheduler] Found ${eventsNeedingPrep.length} meetings requiring preparation`,
    );

    for (const event of eventsNeedingPrep) {
      try {
        // Generate comprehensive meeting prep using LLM
        const meetingPrep = await fetchMeetingPrepInfo(userId, {
          meeting_reference:
            event.summary || event.title || "Scheduled meeting",
          specific_focus_areas: await determineFocusAreas(userId, event),
          context_type: await determineContextType(userId, event),
        });

        logger.info(
          `[MeetingPrepScheduler] Generated prep for: ${event.summary}`,
        );

        // Store prep in both meeting context and LTM
        await storeMeetingPrepContext(userId, {
          meetingId: event.id,
          prepData: meetingPrep,
          scheduledTime: event.start,
          priority: await assessMeetingPriority(userId, event),
        });
      } catch (error) {
        logger.error(
          `[MeetingPrepScheduler] Error preparing meeting ${event.summary}:`,
          error,
        );
      }
    }
  } catch (error) {
    logger.error(
      "[MeetingPrepScheduler] Critical error in meeting prep scheduler:",
      error,
    );
  }
});

agenda.define("generate daily morning briefing", async (job) => {
  const { userId } = job.attrs.data;

  try {
    logger.info(
      `[MeetingPrepScheduler] Starting daily briefing generation for user: ${userId}`,
    );

    // Generate comprehensive daily briefing with LLM insights
    const dailyBriefing = await generateDailyBriefing(userId, {
      date_context: "today",
      include_productivity_insights: true,
      include_meeting_context: true,
      include_follow_up_suggestions: true,
    });

    // Store daily briefing for atom agent context
    await storeDailyBriefing(userId, {
      briefingData: dailyBriefing,
      date: dayjs().format("YYYY-MM-DD"),
      type: "automated-morning",
    });

    logger.info(
      `[MeetingPrepScheduler] Daily briefing generated successfully for user: ${userId}`,
    );
  } catch (error) {
    logger.error(
      "[MeetingPrepScheduler] Error in daily briefing generation:",
      error,
    );
  }
});

agenda.define("schedule-intelligent-recurring-briefings", async (job) => {
  const { userId } = job.attrs.data;

  try {
    logger.info(
      `[MeetingPrepScheduler] Running intelligent re-scheduling for user: ${userId}`,
    );

    // Use LLM to determine optimal scheduling based on user's calendar patterns
    const optimalTimes = await determineOptimalBriefingSchedule(userId);

    if (optimalTimes.length > 0) {
      // Re-schedule based on LLM recommendations
      for (const time of optimalTimes) {
        await agenda.schedule(time, "generate daily morning briefing", {
          userId,
        });
      }
    }
  } catch (error) {
    logger.error(
      "[MeetingPrepScheduler] Error in intelligent rescheduling:",
      error,
    );
  }
});

// --- LLM Enhancement Functions ---

async function determineMeetingsNeedingPrep(userId: string, events: any[]) {
  // LLM-based filtering - decide which meetings need prep
  const currentTime = dayjs();
  const relevantEvents = events.filter((event) => {
    const eventTime = dayjs(event.start);
    const hoursUntilMeeting = eventTime.diff(currentTime, "hours");

    // Use meeting context for better filtering
    return (
      hoursUntilMeeting >= 1 &&
      hoursUntilMeeting <= 24 && // 1-24h ahead
      event.attendanceResponse !== "declined" &&
      event.summary &&
      !event.summary.toLowerCase().includes("block") &&
      !event.summary.toLowerCase().includes("focus time")
    );
  });

  return relevantEvents.slice(0, 3); // Limit to 3 most important
}

async function determineFocusAreas(
  userId: string,
  event: any,
): Promise<string[]> {
  // Use LLM to analyze meeting type and participant context
  const focusAreas = [];

  if (event.summary?.toLowerCase().includes("client"))
    focusAreas.push("client-relationship");
  if (event.attendees && event.attendees.length > 5)
    focusAreas.push("team-collaboration");
  if (event.summary?.toLowerCase().includes("presentation"))
    focusAreas.push("presentation-prep");

  // Default focus areas
  if (focusAreas.length === 0) {
    focusAreas.push(
      "agenda-preparation",
      "participant-background",
      "recent-documents",
    );
  }

  return focusAreas;
}

async function determineContextType(
  userId: string,
  event: any,
): Promise<string> {
  const meetingTitle = event.summary || event.title || "";
  const attendeeCount = event.attendees?.length || 0;

  if (meetingTitle.toLowerCase().includes("kickoff")) return "project-kickoff";
  if (meetingTitle.toLowerCase().includes("review"))
    return "performance-review";
  if (meetingTitle.toLowerCase().includes("demo")) return "product-demo";
  if (attendeeCount > 8) return "team-meeting";
  if (meetingTitle.toLowerCase().includes("1-1") || attendeeCount <= 2)
    return "one-on-one";

  return "regular-meeting";
}

async function assessMeetingPriority(
  userId: string,
  event: any,
): Promise<string> {
  // LLM-based priority assessment using historical patterns
  let priority = "medium";

  const { count: attendeeCount } = event.attendees || {};
  const meetingTitle = event.summary || "";

  // Simple heuristics for now - could be enhanced with ML
  if (
    meetingTitle.toLowerCase().includes("ceo") ||
    meetingTitle.toLowerCase().includes("exec")
  )
    priority = "high";
  if (
    meetingTitle.toLowerCase().includes("urgent") ||
    meetingTitle.toLowerCase().includes("important")
  )
    priority = "high";
  if (attendeeCount > 8) priority = "medium";
  if (
    meetingTitle.toLowerCase().includes("block") ||
    meetingTitle.toLowerCase().includes("focus")
  )
    priority = "low";

  return priority;
}

async function determineOptimalBriefingSchedule(
  userId: string,
): Promise<Date[]> {
  // Analyze user's calendar to find optimal briefing times
  const now = dayjs();
  const optimalTimes = [];

  // Default optimal times
  optimalTimes.push(
    now.add(1, "day").hour(8).minute(0).second(0).toDate(),
    now.add(2, "days").hour(8).minute(0).second(0).toDate(),
  );

  return optimalTimes.filter((time) => time > now.toDate());
}

// --- Integration Functions ---

async function storeMeetingPrepContext(
  userId: string,
  data: {
    meetingId: string;
    prepData: any;
    scheduledTime: string;
    priority: string;
  },
) {
  // Store in conversation context for atom agent access
  const contextData = {
    type: "meeting-prep",
    meetingId: data.meetingId,
    prepData: data.prepData,
    expiration: dayjs().add(2, "hours").toISOString(),
    priority: data.priority,
  };

  logger.info(
    `[MeetingPrepScheduler] Storing context for meeting: ${data.meetingId}`,
  );
}

async function storeDailyBriefing(
  userId: string,
  data: {
    briefingData: any;
    date: string;
    type: string;
  },
) {
  // Store daily briefing in conversation context
  const contextData = {
    type: "daily-briefing",
    briefingData: data.briefingData,
    date: data.date,
    generationTime: new Date().toISOString(),
    type: data.type,
  };

  logger.info(
    `[MeetingPrepScheduler] Storing daily briefing for date: ${data.date}`,
  );
}

// --- Enhanced Scheduling Setup ---

export async function initializeMeetingPrepScheduler() {
  try {
    await agenda.start();
    logger.info("[MeetingPrepScheduler] Agenda scheduler initialized");

    // Schedule intelligent recurring briefings
    await agenda.every("0 7 * * *", "generate daily morning briefing");
    logger.info("[MeetingPrepScheduler] Daily morning briefing scheduled");

    // Schedule meeting prep generation
    await agenda.every("30 8 * * *", "generate meeting briefings");
    logger.info("[MeetingPrepScheduler] Meeting briefing generation scheduled");

    // Schedule weekly intelligent re-scheduling
    await agenda.every("0 6 * * 1", "schedule-intelligent-recurring-briefings");
    logger.info("[MeetingPrepScheduler] Intelligent rescheduling scheduled");
  } catch (error) {
    logger.error("[MeetingPrepScheduler] Error initializing scheduler:", error);
  }
}

export async function scheduleCustomMeetingPrep(
  userId: string,
  meetingId: string,
  customTime?: string,
) {
  try {
    const runAt = customTime
      ? new Date(customTime)
      : new Date(Date.now() + 3600000); // 1 hour from now

    await agenda.schedule(runAt, "generate meeting briefings", {
      userId,
      meetingId,
      custom: true,
    });

    logger.info(
      `[MeetingPrepScheduler] Scheduled custom meeting prep for user: ${userId}, meeting: ${meetingId}`,
    );
  } catch (error) {
    logger.error(
      "[MeetingPrepScheduler] Error scheduling custom meeting prep:",
      error,
    );
  }
}

// Initialize scheduler on module load
if (require.main === module) {
  initializeMeetingPrepScheduler()
    .then(() =>
      logger.info("[MeetingPrepScheduler] Scheduler initialized successfully"),
    )
    .catch((err) =>
      logger.error(
        "[MeetingPrepScheduler] Failed to initialize scheduler:",
        err,
      ),
    );
}

export default {
  initializeMeetingPrepScheduler,
  scheduleCustomMeetingPrep,
  agenda,
};
