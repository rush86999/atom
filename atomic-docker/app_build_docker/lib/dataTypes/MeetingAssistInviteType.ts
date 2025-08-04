export type MeetingAssistInviteType = {
  id: string;
  hostId: string;
  email?: string;
  hostName?: string;
  meetingId: string;
  name: string;
  createdDate: string;
  updatedAt: string;
  userId?: string;
  response?: 'PENDING' | 'CANCELLED' | 'ATTENDING';
  contactId?: string;
};
