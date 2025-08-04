import { getUserPreferences } from '@features_apply/_libs/api-helper';
import {
  AvailableTimeSlotType,
  EventPartPlannerRequestBodyType,
  MonthDayType,
  Time,
  TimeSlotType,
  UserPreferenceType,
} from '@features_apply/_libs/types';
import { getISODay } from 'date-fns';

import { AvailableSlotType, NotAvailableSlotType } from './types';
import { dayjs } from '@features_apply/_libs/date-utils';
import { v4 as uuid } from 'uuid';

export const generateAvailableSlotsForDateForUser = (
  slotDuration: number,
  startDateInUserTimezone: string,
  userPreferences: UserPreferenceType,
  timezone: string,
  notAvailableSlotsInEventTimezone?: NotAvailableSlotType[],
  isFirstDay?: boolean,
  isLastDay?: boolean,
  endDateInUserTimezone?: string
) => {
  console.log(timezone, ' timezone');

  if (isFirstDay && isLastDay && endDateInUserTimezone) {
    const endTimes = userPreferences.endTimes;
    const dayOfWeekInt = getISODay(
      dayjs(startDateInUserTimezone).tz(timezone).toDate()
    );

    const dayOfMonth = dayjs(startDateInUserTimezone).tz(timezone).date();
    let startHourAsReceiver = dayjs(startDateInUserTimezone)
      .tz(timezone)
      .hour();

    const flooredValue = Math.floor(60 / slotDuration);

    let minuteValueAsReceiver = 0;
    if (dayjs(startDateInUserTimezone).tz(timezone).minute() !== 0) {
      for (let i = 0; i < flooredValue; i++) {
        const endMinutes = (i + 1) * slotDuration;
        const startMinutes = i * slotDuration;
        if (
          dayjs(startDateInUserTimezone)
            .tz(timezone)
            .isBetween(
              dayjs(startDateInUserTimezone).tz(timezone).minute(startMinutes),
              dayjs(startDateInUserTimezone).tz(timezone).minute(endMinutes),
              'minute',
              '[)'
            )
        ) {
          minuteValueAsReceiver = endMinutes;
        }
      }
    }

    if (
      dayjs(startDateInUserTimezone)
        .tz(timezone)
        .isBetween(
          dayjs(startDateInUserTimezone)
            .tz(timezone)
            .minute(flooredValue * slotDuration),
          dayjs(startDateInUserTimezone).tz(timezone).minute(59),
          'minute',
          '[)'
        )
    ) {
      startHourAsReceiver += 1;
      minuteValueAsReceiver = 0;
    }

    const startMinuteAsReceiver = minuteValueAsReceiver;

    const endHourWork =
      endTimes?.find((i) => i.day === dayOfWeekInt)?.hour ?? 20;
    const endMinuteWork =
      endTimes?.find((i) => i.day === dayOfWeekInt)?.minutes ?? 0;
    const endHour = dayjs(endDateInUserTimezone).tz(timezone).hour();
    const endMinute = dayjs(endDateInUserTimezone).tz(timezone).minute();

    // validate values before calculating
    const startTimes = userPreferences.startTimes;
    const workStartHour =
      startTimes?.find((i) => i.day === dayOfWeekInt)?.hour || 8;
    const workStartMinute =
      startTimes?.find((i) => i.day === dayOfWeekInt)?.minutes || 0;

    if (
      dayjs(startDateInUserTimezone)
        .tz(timezone)
        .isAfter(
          dayjs(startDateInUserTimezone)
            .tz(timezone)
            .hour(endHourWork)
            .minute(endMinuteWork)
        )
    ) {
      // return empty as outside of work time
      return [];
    }

    // change to work start time as sender start time before work start time
    if (
      dayjs(startDateInUserTimezone)
        .tz(timezone)
        .isBefore(
          dayjs(startDateInUserTimezone)
            .tz(timezone)
            .hour(workStartHour)
            .minute(workStartMinute)
        )
    ) {
      const startDuration = dayjs.duration({
        hours: workStartHour,
        minutes: workStartMinute,
      });
      const endDuration = dayjs.duration({
        hours: endHour,
        minutes: endMinute,
      });
      const totalDuration = endDuration.subtract(startDuration);
      const totalMinutes = totalDuration.asMinutes();

      const availableSlots: AvailableSlotType[] = [];
      console.log(
        startDateInUserTimezone,
        endTimes,
        dayOfWeekInt,
        dayOfMonth,
        startHourAsReceiver,
        startMinuteAsReceiver,
        endHour,
        endMinute,
        timezone,
        `startDate, endTimes, dayOfWeekIntByUser, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`
      );
      for (let i = 0; i < totalMinutes; i += slotDuration) {
        if (i > totalMinutes) {
          continue;
        }

        availableSlots.push({
          id: uuid(),
          startDate: dayjs(startDateInUserTimezone)
            .tz(timezone)
            .hour(workStartHour)
            .minute(workStartMinute)
            .add(i, 'minute')
            .second(0)
            .format(),
          endDate: dayjs(startDateInUserTimezone)
            .tz(timezone)
            .hour(workStartHour)
            .minute(workStartMinute)
            .add(i + slotDuration, 'minute')
            .second(0)
            .format(),
        });
      }
      console.log(
        availableSlots,
        ' timeSlots inside generateTimeSlots for first day where startDate is before work start time'
      );

      // filter out unavailable times
      const filteredAvailableSlotsInReceiverTimezone = availableSlots.filter(
        (a) => {
          const foundIndex = notAvailableSlotsInEventTimezone?.findIndex(
            (na) => {
              const partA = dayjs(a.endDate)
                .tz(timezone)
                .second(0)
                .isBetween(
                  dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'),
                  dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'),
                  'm',
                  '[]'
                );

              const partB = dayjs(a.startDate)
                .tz(timezone)
                .second(0)
                .isBetween(
                  dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'),
                  dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'),
                  'm',
                  '[]'
                );

              const partC =
                dayjs(na.startDate)
                  .tz(timezone)
                  .second(0)
                  .format('YYYY-MM-DDTHH:mm') ===
                  dayjs(a.startDate)
                    .tz(timezone)
                    .second(0)
                    .format('YYYY-MM-DDTHH:mm') &&
                dayjs(na.endDate)
                  .tz(timezone)
                  .second(0)
                  .format('YYYY-MM-DDTHH:mm') ===
                  dayjs(a.endDate)
                    .tz(timezone)
                    .second(0)
                    .format('YYYY-MM-DDTHH:mm');

              const isNotAvailable = partA || partB || partC;

              // console.log(a, na, ' a, na')
              return isNotAvailable;
            }
          );

          console.log(foundIndex, ' foundIndex');

          if (foundIndex !== undefined && foundIndex > -1) {
            return false;
          }

          return true;
        }
      );

      console.log(
        filteredAvailableSlotsInReceiverTimezone,
        ' filteredAvailableSlots'
      );

      return filteredAvailableSlotsInReceiverTimezone;
    }

    const startDuration = dayjs.duration({
      hours: startHourAsReceiver,
      minutes: startMinuteAsReceiver,
    });
    const endDuration = dayjs.duration({ hours: endHour, minutes: endMinute });
    const totalDuration = endDuration.subtract(startDuration);
    const totalMinutes = totalDuration.asMinutes();
    console.log(totalMinutes, ' totalMinutes inside first and last same day');
    const availableSlotsInReceiverTimezone: AvailableSlotType[] = [];
    console.log(
      startDateInUserTimezone,
      endTimes,
      dayOfWeekInt,
      endHourWork,
      endMinuteWork,
      timezone,
      `startDate, endTimes, dayOfWeekInt, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside first & last Day inside generateTimeslots`
    );
    for (let i = 0; i < totalMinutes; i += slotDuration) {
      if (i > totalMinutes) {
        continue;
      }
      availableSlotsInReceiverTimezone.push({
        id: uuid(),
        startDate: dayjs(startDateInUserTimezone)
          .tz(timezone)
          .hour(startHourAsReceiver)
          .minute(startMinuteAsReceiver)
          .add(i, 'minute')
          .second(0)
          .format(),
        endDate: dayjs(startDateInUserTimezone)
          .tz(timezone)
          .hour(startHourAsReceiver)
          .minute(startMinuteAsReceiver)
          .add(i + slotDuration, 'minute')
          .second(0)
          .format(),
      });
    }

    console.log(
      availableSlotsInReceiverTimezone,
      ' availableSlots inside first & last same day'
    );
    const filteredAvailableSlotsInReceiverTimezone =
      availableSlotsInReceiverTimezone.filter((a) => {
        const foundIndex = notAvailableSlotsInEventTimezone?.findIndex((na) => {
          const partA = dayjs(a.endDate)
            .tz(timezone)
            .second(0)
            .isBetween(
              dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'),
              dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'),
              'm',
              '[]'
            );

          const partB = dayjs(a.startDate)
            .tz(timezone)
            .second(0)
            .isBetween(
              dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'),
              dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'),
              'm',
              '[]'
            );

          const partC =
            dayjs(na.startDate)
              .tz(timezone)
              .second(0)
              .format('YYYY-MM-DDTHH:mm') ===
              dayjs(a.startDate)
                .tz(timezone)
                .second(0)
                .format('YYYY-MM-DDTHH:mm') &&
            dayjs(na.endDate)
              .tz(timezone)
              .second(0)
              .format('YYYY-MM-DDTHH:mm') ===
              dayjs(a.endDate)
                .tz(timezone)
                .second(0)
                .format('YYYY-MM-DDTHH:mm');

          const isNotAvailable = partA || partB || partC;

          // console.log(a, na, ' a, na')

          return isNotAvailable;
        });

        console.log(foundIndex, ' foundIndex');

        if (foundIndex !== undefined && foundIndex > -1) {
          return false;
        }

        return true;
      });

    console.log(
      filteredAvailableSlotsInReceiverTimezone,
      ' filteredAvailableSlots'
    );
    return filteredAvailableSlotsInReceiverTimezone;
  }

  if (isFirstDay) {
    // firstday can be started outside of work time
    // if firstDay start is after end time -- return []
    const endTimes = userPreferences.endTimes;
    const dayOfWeekInt = getISODay(
      dayjs(startDateInUserTimezone).tz(timezone).toDate()
    );

    // month is zero-indexed
    // const month = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).tz(userTimezone).month()
    const dayOfMonth = dayjs(startDateInUserTimezone).tz(timezone).date();
    let startHour = dayjs(startDateInUserTimezone).tz(timezone).hour();

    const startMinute = dayjs(startDateInUserTimezone).tz(timezone).minute();
    // create slot sizes
    const flooredValue = Math.floor(60 / slotDuration);

    let minuteValueAsReceiver = 0;
    if (dayjs(startDateInUserTimezone).tz(timezone).minute() !== 0) {
      for (let i = 0; i < flooredValue; i++) {
        const endMinutes = (i + 1) * slotDuration;
        const startMinutes = i * slotDuration;
        if (
          dayjs(startDateInUserTimezone)
            .tz(timezone)
            .isBetween(
              dayjs(startDateInUserTimezone).tz(timezone).minute(startMinutes),
              dayjs(startDateInUserTimezone).tz(timezone).minute(endMinutes),
              'minute',
              '[)'
            )
        ) {
          minuteValueAsReceiver = endMinutes;
        }
      }
    }

    if (
      dayjs(startDateInUserTimezone)
        .tz(timezone)
        .isBetween(
          dayjs(startDateInUserTimezone)
            .tz(timezone)
            .minute(flooredValue * slotDuration),
          dayjs(startDateInUserTimezone).tz(timezone).minute(59),
          'minute',
          '[)'
        )
    ) {
      startHour += 1;
      minuteValueAsReceiver = 0;
    }

    const startMinuteAsReceiver = minuteValueAsReceiver;

    // convert to user timezone so everything is linked to user timezone

    const endHour = endTimes?.find((i) => i.day === dayOfWeekInt)?.hour ?? 20;
    const endMinute =
      endTimes?.find((i) => i.day === dayOfWeekInt)?.minutes ?? 0;

    // validate values before calculating
    const startTimes = userPreferences.startTimes;
    const workStartHour =
      startTimes?.find((i) => i.day === dayOfWeekInt)?.hour || 8;
    const workStartMinute =
      startTimes?.find((i) => i.day === dayOfWeekInt)?.minutes || 0;

    if (
      dayjs(startDateInUserTimezone)
        .tz(timezone)
        .isAfter(
          dayjs(startDateInUserTimezone)
            .tz(timezone)
            .hour(endHour)
            .minute(endMinute)
        )
    ) {
      // return empty as outside of work time
      return [];
    }

    // change to work start time as host start time before work start time
    if (
      dayjs(startDateInUserTimezone)
        .tz(timezone)
        .isBefore(
          dayjs(startDateInUserTimezone)
            .tz(timezone)
            .hour(workStartHour)
            .minute(workStartMinute)
        )
    ) {
      const startDuration = dayjs.duration({
        hours: workStartHour,
        minutes: workStartMinute,
      });
      const endDuration = dayjs.duration({
        hours: endHour,
        minutes: endMinute,
      });
      const totalDuration = endDuration.subtract(startDuration);
      const totalMinutes = totalDuration.asMinutes();

      const availableSlotsInReceiverTimezone: AvailableSlotType[] = [];
      console.log(
        startDateInUserTimezone,
        endTimes,
        dayOfWeekInt,
        dayOfMonth,
        startHour,
        startMinuteAsReceiver,
        endHour,
        endMinute,
        timezone,
        `startDate, endTimes, dayOfWeekIntByUser, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`
      );
      for (let i = 0; i < totalMinutes; i += slotDuration) {
        if (i > totalMinutes) {
          continue;
        }

        availableSlotsInReceiverTimezone.push({
          id: uuid(),
          startDate: dayjs(startDateInUserTimezone)
            .tz(timezone)
            .hour(workStartHour)
            .minute(workStartMinute)
            .add(i, 'minute')
            .second(0)
            .format(),
          endDate: dayjs(startDateInUserTimezone)
            .tz(timezone)
            .hour(workStartHour)
            .minute(workStartMinute)
            .add(i + slotDuration, 'minute')
            .second(0)
            .format(),
        });
      }
      console.log(
        availableSlotsInReceiverTimezone,
        ' timeSlots inside generateTimeSlots for first day where startDate is before work start time'
      );

      // filter out unavailable times
      const filteredAvailableSlotsInReceiverTimezone =
        availableSlotsInReceiverTimezone.filter((a) => {
          const foundIndex = notAvailableSlotsInEventTimezone?.findIndex(
            (na) => {
              const partA = dayjs(a.endDate)
                .tz(timezone)
                .second(0)
                .isBetween(
                  dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'),
                  dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'),
                  'm',
                  '[]'
                );

              const partB = dayjs(a.startDate)
                .tz(timezone)
                .second(0)
                .isBetween(
                  dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'),
                  dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'),
                  'm',
                  '[]'
                );

              const partC =
                dayjs(na.startDate)
                  .tz(timezone)
                  .second(0)
                  .format('YYYY-MM-DDTHH:mm') ===
                  dayjs(a.startDate)
                    .tz(timezone)
                    .second(0)
                    .format('YYYY-MM-DDTHH:mm') &&
                dayjs(na.endDate)
                  .tz(timezone)
                  .second(0)
                  .format('YYYY-MM-DDTHH:mm') ===
                  dayjs(a.endDate)
                    .tz(timezone)
                    .second(0)
                    .format('YYYY-MM-DDTHH:mm');

              const isNotAvailable = partA || partB || partC;

              // console.log(a, na, ' a, na')
              return isNotAvailable;
            }
          );

          console.log(foundIndex, ' foundIndex');

          if (foundIndex !== undefined && foundIndex > -1) {
            return false;
          }

          return true;
        });

      console.log(
        filteredAvailableSlotsInReceiverTimezone,
        ' filteredAvailableSlots'
      );

      return filteredAvailableSlotsInReceiverTimezone;
    }

    const startDuration = dayjs.duration({
      hours: startHour,
      minutes: startMinute,
    });
    const endDuration = dayjs.duration({ hours: endHour, minutes: endMinute });
    const totalDuration = endDuration.subtract(startDuration);
    const totalMinutes = totalDuration.asMinutes();
    const availableSlotsInReceiverTimezone: AvailableSlotType[] = [];
    console.log(
      startDateInUserTimezone,
      endTimes,
      dayOfWeekInt,
      endHour,
      endMinute,
      timezone,
      `startDate, endTimes, dayOfWeekInt, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`
    );
    for (let i = 0; i < totalMinutes; i += slotDuration) {
      if (i > totalMinutes) {
        continue;
      }
      availableSlotsInReceiverTimezone.push({
        id: uuid(),
        startDate: dayjs(startDateInUserTimezone)
          .tz(timezone)
          .hour(startHour)
          .minute(startMinuteAsReceiver)
          .add(i, 'minute')
          .second(0)
          .format(),
        endDate: dayjs(startDateInUserTimezone)
          .tz(timezone)
          .hour(startHour)
          .minute(startMinuteAsReceiver)
          .add(i + slotDuration, 'minute')
          .second(0)
          .format(),
      });
    }
    const filteredAvailableSlotsInReceiverTimezone =
      availableSlotsInReceiverTimezone.filter((a) => {
        const foundIndex = notAvailableSlotsInEventTimezone?.findIndex((na) => {
          const partA = dayjs(a.endDate)
            .tz(timezone)
            .second(0)
            .isBetween(
              dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'),
              dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'),
              'm',
              '[]'
            );

          const partB = dayjs(a.startDate)
            .tz(timezone)
            .second(0)
            .isBetween(
              dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'),
              dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'),
              'm',
              '[]'
            );

          const partC =
            dayjs(na.startDate)
              .tz(timezone)
              .second(0)
              .format('YYYY-MM-DDTHH:mm') ===
              dayjs(a.startDate)
                .tz(timezone)
                .second(0)
                .format('YYYY-MM-DDTHH:mm') &&
            dayjs(na.endDate)
              .tz(timezone)
              .second(0)
              .format('YYYY-MM-DDTHH:mm') ===
              dayjs(a.endDate)
                .tz(timezone)
                .second(0)
                .format('YYYY-MM-DDTHH:mm');

          const isNotAvailable = partA || partB || partC;

          // console.log(a, na, ' a, na')

          return isNotAvailable;
        });

        console.log(foundIndex, ' foundIndex');

        if (foundIndex !== undefined && foundIndex > -1) {
          return false;
        }

        return true;
      });

    console.log(
      filteredAvailableSlotsInReceiverTimezone,
      ' filteredAvailableSlots server timezone'
    );
    return filteredAvailableSlotsInReceiverTimezone;
  }

  // not first day start from work start time schedule

  const startTimes = userPreferences.startTimes;

  const endTimes = userPreferences.endTimes;

  const dayOfWeekInt = getISODay(
    dayjs(startDateInUserTimezone).tz(timezone).toDate()
  );
  const dayOfMonth = dayjs(startDateInUserTimezone).tz(timezone).date();

  // convert to user timezone so everything is linked to user timezone
  let endHour = endTimes?.find((i) => i.day === dayOfWeekInt)?.hour ?? 20;
  let endMinute = endTimes?.find((i) => i.day === dayOfWeekInt)?.minutes ?? 0;

  // if last day change end time to hostStartDate provided
  if (isLastDay && endDateInUserTimezone) {
    endHour = dayjs(endDateInUserTimezone).tz(timezone).hour();
    // create slot sizes
    const flooredValue = Math.floor(60 / slotDuration);

    let minuteValueBySender = 0;
    for (let i = 0; i < flooredValue; i++) {
      const endMinutes = (i + 1) * slotDuration;
      const startMinutes = i * slotDuration;
      if (
        dayjs(endDateInUserTimezone)
          .tz(timezone)
          .isBetween(
            dayjs(endDateInUserTimezone).tz(timezone).minute(startMinutes),
            dayjs(endDateInUserTimezone).tz(timezone).minute(endMinutes),
            'minute',
            '[)'
          )
      ) {
        minuteValueBySender = startMinutes;
      }
    }

    endMinute = minuteValueBySender;
  }

  const startHourBySender =
    (startTimes?.find((i) => i.day === dayOfWeekInt)?.hour as number) || 8;
  const startMinuteBySender =
    (startTimes?.find((i) => i.day === dayOfWeekInt)?.minutes as number) || 0;

  const startDuration = dayjs.duration({
    hours: startHourBySender,
    minutes: startMinuteBySender,
  });
  const endDuration = dayjs.duration({ hours: endHour, minutes: endMinute });
  const totalDuration = endDuration.subtract(startDuration);
  const totalMinutes = totalDuration.asMinutes();

  const availableSlotsInReceiverTimezone: AvailableSlotType[] = [];
  console.log(
    startDateInUserTimezone,
    endTimes,
    dayOfWeekInt,
    dayOfMonth,
    startHourBySender,
    startMinuteBySender,
    endHour,
    endMinute,
    timezone,
    `startDate, endTimes, dayOfWeekIntByHost, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateAvailableslots`
  );
  for (let i = 0; i < totalMinutes; i += slotDuration) {
    if (i > totalMinutes) {
      continue;
    }

    availableSlotsInReceiverTimezone.push({
      id: uuid(),
      startDate: dayjs(startDateInUserTimezone)
        .tz(timezone)
        .hour(startHourBySender)
        .minute(startMinuteBySender)
        .add(i, 'minute')
        .second(0)
        .format(),
      endDate: dayjs(startDateInUserTimezone)
        .tz(timezone)
        .hour(startHourBySender)
        .minute(startMinuteBySender)
        .add(i + slotDuration, 'minute')
        .second(0)
        .format(),
    });
  }

  console.log(
    availableSlotsInReceiverTimezone,
    ' timeSlots inside generateTimeSlots not first day'
  );
  console.log(
    notAvailableSlotsInEventTimezone,
    ' notAvailableSlotsInEventTimezone not first day'
  );

  // filter out unavailable times
  const filteredAvailableSlotsInReceiverTimezone =
    availableSlotsInReceiverTimezone.filter((a) => {
      const foundIndex = notAvailableSlotsInEventTimezone?.findIndex((na) => {
        const partA = dayjs(a.endDate)
          .tz(timezone)
          .second(0)
          .isBetween(
            dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'),
            dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'),
            'm',
            '[]'
          );

        const partB = dayjs(a.startDate)
          .tz(timezone)
          .second(0)
          .isBetween(
            dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'),
            dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'),
            'm',
            '[]'
          );

        const partC =
          dayjs(na.startDate)
            .tz(timezone)
            .second(0)
            .format('YYYY-MM-DDTHH:mm') ===
            dayjs(a.startDate)
              .tz(timezone)
              .second(0)
              .format('YYYY-MM-DDTHH:mm') &&
          dayjs(na.endDate)
            .tz(timezone)
            .second(0)
            .format('YYYY-MM-DDTHH:mm') ===
            dayjs(a.endDate).tz(timezone).second(0).format('YYYY-MM-DDTHH:mm');

        const isNotAvailable = partA || partB || partC;

        // console.log(a, na, ' a, na')

        return isNotAvailable;
      });

      console.log(foundIndex, ' foundIndex');

      if (foundIndex !== undefined && foundIndex > -1) {
        return false;
      }

      return true;
    });

  console.log(
    filteredAvailableSlotsInReceiverTimezone,
    ' filteredAvailableSlots in receiverTimezone'
  );
  // convert to receiverTimezone before returning values
  return filteredAvailableSlotsInReceiverTimezone;
};

export const generateAvailableSlotsforTimeWindowForUser = (
  windowStartDate: string,
  windowEndDate: string,
  slotDuration: number,
  userPreferences: UserPreferenceType,
  timezone: string,
  notAvailableSlotsInEventTimezone?: NotAvailableSlotType[]
) => {
  const diffDays = dayjs(windowEndDate).diff(dayjs(windowStartDate), 'd');

  const startDatesForEachDay = [];
  const availableSlots: AvailableSlotType[] = [];

  for (let i = 0; i <= diffDays; i++) {
    startDatesForEachDay.push(
      dayjs(windowStartDate.slice(0, 19))
        .tz(timezone, true)
        .add(i, 'day')
        .format()
    );
  }

  if (diffDays < 1) {
    const generatedSlots = generateAvailableSlotsForDateForUser(
      slotDuration,
      dayjs(windowStartDate.slice(0, 19)).tz(timezone, true).format(),
      userPreferences,
      timezone,
      notAvailableSlotsInEventTimezone,
      true,
      true,
      dayjs(windowEndDate.slice(0, 19)).tz(timezone, true).format()
    );
    //  0123456789
    //  2020-04-02T08:02:17-05:00
    availableSlots.push(...generatedSlots);
  } else {
    for (let i = 0; i < startDatesForEachDay.length; i++) {
      const filteredNotAvailableSlotsInEventTimezone =
        notAvailableSlotsInEventTimezone?.filter(
          (na) =>
            dayjs(na?.startDate).tz(timezone).format('YYYY-MM-DD') ===
            dayjs(startDatesForEachDay?.[i]).tz(timezone).format('YYYY-MM-DD')
        );
      if (i === 0) {
        const generatedSlots = generateAvailableSlotsForDateForUser(
          slotDuration,
          startDatesForEachDay?.[i],
          userPreferences,
          timezone,
          filteredNotAvailableSlotsInEventTimezone,
          true,
          false,
          dayjs(windowEndDate.slice(0, 19)).tz(timezone, true).format()
        );
        //  0123456789
        //  2020-04-02T08:02:17-05:00
        availableSlots.push(...generatedSlots);

        continue;
      }

      if (i === startDatesForEachDay.length - 1) {
        const generatedSlots = generateAvailableSlotsForDateForUser(
          slotDuration,
          startDatesForEachDay?.[i],
          userPreferences,
          timezone,
          filteredNotAvailableSlotsInEventTimezone,
          false,
          true,
          dayjs(windowEndDate.slice(0, 19)).tz(timezone, true).format()
        );

        availableSlots.push(...generatedSlots);

        continue;
      }

      const generatedSlots = generateAvailableSlotsForDateForUser(
        slotDuration,
        startDatesForEachDay?.[i],
        userPreferences,
        timezone,
        filteredNotAvailableSlotsInEventTimezone
      );

      availableSlots.push(...generatedSlots);
    }
  }

  return { availableSlots };
};

export const generateAvailabilityForUser = async (
  eventParts: EventPartPlannerRequestBodyType[],
  userId: string,
  windowStartDate: string,
  windowEndDate: string,
  timezone: string,
  slotDuration: number
) => {
  try {
    console.log(eventParts, ' eventParts');

    if (!eventParts || !(eventParts?.length > 0)) {
      console.log('no old events in generateAvailability');
    }

    const notAvailableFromEvents: NotAvailableSlotType[] = eventParts?.map(
      (e) => ({
        startDate: e?.startDate,
        endDate: e?.endDate,
      })
    );

    const userPreferences = await getUserPreferences(userId);

    const { availableSlots: availableSlots } =
      await generateAvailableSlotsforTimeWindowForUser(
        windowStartDate,
        windowEndDate,
        slotDuration,
        userPreferences,
        timezone,
        notAvailableFromEvents?.length > 0 ? notAvailableFromEvents : undefined
      );

    return availableSlots;
  } catch (e) {
    console.log(e, ' unable to generate availability');
  }
};

export const convertAvailableSlotsToTimeSlotLike = (
  availableSlots: AvailableSlotType[],
  timezone: string
) => {
  // AvailableTimeSlotType
  // AvailableSlotType[]

  if (!(availableSlots?.length > 0)) {
    throw new Error(
      'no available slots provided inside convertAvailableSlotsToTimeSlotLike'
    );
  }

  const availableTimeSlots: AvailableTimeSlotType[] = [];
  for (const availableSlot of availableSlots) {
    const availableTimeSlot: AvailableTimeSlotType = {
      startTime:
        `${dayjs(availableSlot?.startDate).tz(timezone).format('HH:mm')}` as Time,
      endTime:
        `${dayjs(availableSlot?.endDate).tz(timezone).format('HH:mm')}` as Time,
      monthDay:
        `--${dayjs(availableSlot?.startDate).tz(timezone).format('MM-DD')}` as MonthDayType,
    };

    availableTimeSlots.push(availableTimeSlot);
  }

  return availableTimeSlots;
};

export const filterTimeslotsGivenImmodifiableEvents = async (
  eventParts: EventPartPlannerRequestBodyType[],
  timeslots: TimeSlotType[],
  userId: string,
  windowStartDate: string,
  windowEndDate: string,
  timezone,
  slotDuration: number
) => {
  try {
    const availableSlots = await generateAvailabilityForUser(
      eventParts,
      userId,
      windowStartDate,
      windowEndDate,
      timezone,
      slotDuration
    );
    const availableTimeSlots = convertAvailableSlotsToTimeSlotLike(
      availableSlots,
      timezone
    );

    const filteredTimeSlots: TimeSlotType[] = [];

    for (const availableTimeSlot of availableTimeSlots) {
      for (const timeslot of timeslots) {
        if (
          availableTimeSlot?.startTime === timeslot?.startTime &&
          availableTimeSlot?.endTime === timeslot?.endTime &&
          availableTimeSlot?.monthDay === timeslot?.monthDay
        ) {
          filteredTimeSlots.push(timeslot);
        }
      }
    }

    console.log(filteredTimeSlots, ' filteredTimeSlots');

    return filteredTimeSlots;
  } catch (e) {
    console.log(e, ' unable filterTimeslotsGivenImmodifiableEvents');
  }
};
