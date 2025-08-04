export type ScheduleAssistWithMeetingQueueBodyType = {
  userId: string;
  windowStartDate: string;
  windowEndDate: string;
  timezone: string;
};

export type AutopilotType = {
  id: string;
  userId: string;
  scheduleAt: string;
  timezone: string;
  payload: ScheduleAssistWithMeetingQueueBodyType;
  updatedAt: string;
  createdDate: string;
};
