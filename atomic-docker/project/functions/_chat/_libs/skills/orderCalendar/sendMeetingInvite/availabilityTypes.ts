export type SummarizeDayAvailabilityType = {
  userId: string;
  dayAvailabilityList: string;
  userProvidedKey?: boolean;
};

export type DayAvailabilityType = {
  userId: string;
  windowStartDate: string;
  windowEndDate: string;
  senderTimezone: string;
  receiverTimezone: string;
  slotDuration: string;
  userProvidedKey?: boolean;
};

export type NotAvailableSlotType = {
  startDate: string;
  endDate: string;
};

export type AvailableSlotType = {
  id: string;
  startDate: string;
  endDate: string;
};
