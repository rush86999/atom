export type TimezoneObjectType = {
  value: string;
  label: string;
  key: string;
};

export type MeetingRequestBodyType = {
  userId: string;
  email: string;
  shareAvailability: boolean;
  receiver: string;
  sender: string;
  receiverCharacteristics?: string[];
  receiverGoals?: string[];
  senderCharacteristics?: string[];
  senderGoals?: string[];
  windowStartDate?: string;
  windowEndDate?: string;
  senderTimezone?: string;
  receiverTimezone?: string;
  slotDuration?: number;
};
