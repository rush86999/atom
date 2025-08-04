import { TaskStatus } from '@libs/skills/orderCalendar/addTask/constants';

export type TaskSyncType = {
  id: string;
  name: string;
  syncDate: string;
};

export type TaskType = {
  id: string;
  userId: string;
  eventId?: string;
  type: string;
  notes?: string;
  completedDate?: string;
  important?: boolean;
  syncData?: TaskSyncType[];
  status?: TaskStatus;
  parentId?: string;
  order?: number;
  priority?: number;
  softDeadline?: string; // timestamp
  hardDeadline?: string;
  duration?: number;
  updatedAt?: string;
  createdDate?: string;
};
