import { ResolvedAttendee, ContactSkillResponse } from '../types';
export declare function resolveAttendees(attendeeStrings: string[], requesterId: string): Promise<ContactSkillResponse<ResolvedAttendee[]>>;
