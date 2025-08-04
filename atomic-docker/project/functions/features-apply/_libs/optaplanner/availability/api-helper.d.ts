import { EventPartPlannerRequestBodyType, TimeSlotType, UserPreferenceType } from '@features_apply/_libs/types';
import { AvailableSlotType, NotAvailableSlotType } from './types';
export declare const generateAvailableSlotsForDateForUser: (slotDuration: number, startDateInUserTimezone: string, userPreferences: UserPreferenceType, timezone: string, notAvailableSlotsInEventTimezone?: NotAvailableSlotType[], isFirstDay?: boolean, isLastDay?: boolean, endDateInUserTimezone?: string) => AvailableSlotType[];
export declare const generateAvailableSlotsforTimeWindowForUser: (windowStartDate: string, windowEndDate: string, slotDuration: number, userPreferences: UserPreferenceType, timezone: string, notAvailableSlotsInEventTimezone?: NotAvailableSlotType[]) => {
    availableSlots: AvailableSlotType[];
};
export declare const generateAvailabilityForUser: (eventParts: EventPartPlannerRequestBodyType[], userId: string, windowStartDate: string, windowEndDate: string, timezone: string, slotDuration: number) => Promise<AvailableSlotType[] | undefined>;
export declare const convertAvailableSlotsToTimeSlotLike: (availableSlots: AvailableSlotType[], timezone: string) => AvailableTimeSlotType[];
export declare const filterTimeslotsGivenImmodifiableEvents: (eventParts: EventPartPlannerRequestBodyType[], timeslots: TimeSlotType[], userId: string, windowStartDate: string, windowEndDate: string, timezone: any, slotDuration: number) => Promise<TimeSlotType[] | undefined>;
