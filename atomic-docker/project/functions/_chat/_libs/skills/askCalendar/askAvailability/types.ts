export type NotAvailableSlotType = {
  startDate: string;
  endDate: string;
};

export type UserAvailabilityBodyType = {
  userId: string;
  windowStartDate: string;
  windowEndDate: string;
  timezone: string;
  slotDuration: number;
  [key: string]: any;
};
