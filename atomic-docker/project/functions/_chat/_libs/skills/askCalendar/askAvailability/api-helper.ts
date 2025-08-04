import QueryCalendarExtractedJSONType from '@chat/_libs/datetime/QueryCalendarExtractedDateJSONType';
import {
  callOpenAI,
  extrapolateEndDateFromJSONData,
  extrapolateStartDateFromJSONData,
  generateAssistantMessageFromAPIResponseForUserQuery,
  generateDateTime,
  generateQueryDateFromUserInput,
  listEventsForUserGivenDates,
} from '@chat/_libs/api-helper';
import { dayjs, getISODay } from '@chat/_libs/datetime/date-utils';
import { NotAvailableSlotType, UserAvailabilityBodyType } from './types';
import { getUserPreferences } from '../api-helper';
import { UserPreferenceType } from '@chat/_libs/types/UserPreferenceType';
import { AvailableSlotType } from '@chat/_libs/skills/orderCalendar/generateMeetingInvite/availabilityTypes';
import { v4 as uuid } from 'uuid';
import DateTimeJSONType from '@chat/_libs/datetime/DateTimeJSONJSONType';
import _ from 'lodash';
import {
  summarizeAvailabilityPrompt,
  summarizeAvailabilityExampleInput,
  summarizeAvailabilityExampleOutput,
  summarizeAvailabilityResponsesPrompt,
  summarizeAvailabilityResponsesPromptExampleInput,
  summarizeAvailabilityResponsesPromptExampleOutput,
} from './prompts';
import {
  defaultOpenAIAPIKey,
  openAIChatGPT35LongModel,
} from '@chat/_libs/constants';

import ResponseActionType from '@chat/_libs/types/ResponseActionType';
import { SkillMessageHistoryType } from '@chat/_libs/types/Messaging/MessagingTypes';
import OpenAI from 'openai';

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
  userId: string,
  windowStartDate: string,
  windowEndDate: string,
  timezone: string,
  slotDuration: number
) => {
  try {
    const oldEventsInEventTimezone = await listEventsForUserGivenDates(
      userId,
      windowStartDate,
      windowEndDate
    );

    console.log(oldEventsInEventTimezone, ' oldEventsInEventTimezone');

    if (!oldEventsInEventTimezone || !(oldEventsInEventTimezone?.length > 0)) {
      console.log('no old events in generateAvailability');
    }

    const oldEventsInEventTimezoneFormatted = oldEventsInEventTimezone?.map(
      (e) => ({
        ...e,
        startDate: dayjs(e?.startDate.slice(0, 19))
          .tz(e?.timezone, true)
          .format(),
        endDate: dayjs(e?.endDate.slice(0, 19)).tz(e?.timezone, true).format(),
        timezone: e?.timezone,
      })
    );

    const notAvailableFromEvents: NotAvailableSlotType[] =
      oldEventsInEventTimezoneFormatted?.map((e) => ({
        startDate: e?.startDate,
        endDate: e?.endDate,
      }));

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

export const processAvailability = async (
  userId: string,
  timezone: string,
  dateTimeJSONBody: DateTimeJSONType,
  queryDateJSONBody: QueryCalendarExtractedJSONType,
  currentTime: string
): Promise<ResponseActionType> => {
  try {
    const windowStartDate = extrapolateStartDateFromJSONData(
      currentTime,
      timezone,
      queryDateJSONBody?.start_date?.year,
      queryDateJSONBody?.start_date?.month,
      queryDateJSONBody?.start_date?.day,
      undefined,
      queryDateJSONBody?.start_date?.hour,
      queryDateJSONBody?.start_date?.minute,
      queryDateJSONBody?.start_date?.time,
      queryDateJSONBody?.start_date?.relativeTimeChangeFromNow,
      queryDateJSONBody?.start_date?.relativeTimeFromNow
    );

    const windowEndDate = extrapolateEndDateFromJSONData(
      currentTime,
      timezone,
      queryDateJSONBody?.end_date?.year,
      queryDateJSONBody?.end_date?.month,
      queryDateJSONBody?.end_date?.day,
      undefined,
      queryDateJSONBody?.end_date?.hour,
      queryDateJSONBody?.end_date?.minute,
      queryDateJSONBody?.end_date?.time,
      queryDateJSONBody?.end_date?.relativeTimeChangeFromNow,
      queryDateJSONBody?.end_date?.relativeTimeFromNow
    );

    // get default values
    // const defaultMeetingPreferences = await getChatMeetingPreferenceGivenUserId(userId)

    const body: UserAvailabilityBodyType = {
      userId,
      windowStartDate: windowStartDate || dayjs().format(),
      windowEndDate: windowEndDate || dayjs().add(2, 'w').format(),
      timezone,
      slotDuration: dateTimeJSONBody?.duration || 30,
    };

    console.log(body, ' body inside processAvailability');

    const response: any = {
      query: '',
      data: {},
      skill: 'queryAvailability',
    };

    const availableSlots = await generateAvailabilityForUser(
      body?.userId,
      body?.windowStartDate,
      body?.windowEndDate,
      timezone,
      body?.slotDuration
    );

    response.query = 'completed';

    if (!(availableSlots?.length > 0)) {
      response.data = 'no free time slots available';
      return response;
    }

    const openai = new OpenAI({
      apiKey: defaultOpenAIAPIKey,
    });

    const uniqDates = _.uniqBy(availableSlots, (curr) =>
      dayjs(curr?.startDate?.slice(0, 19)).tz(timezone).format('YYYY-MM-DD')
    );

    // let availabilityText = ''

    const prompt = summarizeAvailabilityPrompt;

    const exampleInput = summarizeAvailabilityExampleInput;

    const exampleOutput = summarizeAvailabilityExampleOutput;

    let openAIAvailabilityRes = '';

    for (const uniqDate of uniqDates) {
      const filteredAvailability = availableSlots?.filter(
        (a) =>
          dayjs(a?.startDate).tz(timezone).format('YYYY-MM-DD') ===
          dayjs(uniqDate?.startDate).tz(timezone).format('YYYY-MM-DD')
      );

      if (filteredAvailability?.length > 0) {
        // availabilityText += `${dayjs(uniqDate?.startDate).tz(timezone).format('L')} - ${filteredAvailability?.map((curr) => (`${dayjs(curr?.startDate).tz(timezone).format('LT')} - ${dayjs(curr?.endDate).tz(timezone).format('LT')},`))?.reduce((prev, curr) => (`${prev} ${curr}`), '')}` + '\n\n'

        const miniAvailabilityText =
          `${dayjs(uniqDate?.startDate).tz(timezone).format('L')} - ${filteredAvailability?.map((curr) => `${dayjs(curr?.startDate).tz(timezone).format('LT')} - ${dayjs(curr?.endDate).tz(timezone).format('LT')},`)?.reduce((prev, curr) => `${prev} ${curr}`, '')}` +
          '\n\n';

        const miniUserData = `My availability: ` + miniAvailabilityText;

        console.log(miniUserData, ' newAvailabilityPrompt');

        const miniOpenAIAvailabilityRes = await callOpenAI(
          openai,
          prompt,
          openAIChatGPT35LongModel,
          miniUserData,
          exampleInput,
          exampleOutput
        );

        // validate openai res
        if (!miniOpenAIAvailabilityRes) {
          throw new Error(
            'no openAIAvailabilityRes present inside appointmentRequest'
          );
        }

        openAIAvailabilityRes += '\n' + miniOpenAIAvailabilityRes;
      }
    }

    // const availabilityFinalSummaryUserData = openAIAvailabilityRes

    // let finalOpenAIAvailabilitySummaryResponse = ''

    // if (availabilityFinalSummaryUserData) {
    //     finalOpenAIAvailabilitySummaryResponse = await callOpenAI(openai, summarizeAvailabilityResponsesPrompt, openAIChatGPT35LongModel, availabilityFinalSummaryUserData, summarizeAvailabilityResponsesPromptExampleInput, summarizeAvailabilityResponsesPromptExampleOutput)
    // }

    response.data = openAIAvailabilityRes;

    return response;
  } catch (e) {
    console.log(e, ' uanble to process availability');
  }
};

export const askAvailabilityControlCenterForPending = async (
  openai: OpenAI,
  userId: string,
  timezone: string,
  messageHistoryObject: SkillMessageHistoryType,
  userCurrentTime: string
) => {
  try {
    const messageLength = messageHistoryObject.messages?.length;
    let userMessage = '';
    for (let i = messageLength; i > 0; i--) {
      const message = messageHistoryObject.messages[i - 1];

      if (message.role === 'user') {
        userMessage = message.content;
        break;
      }
    }
    const userInput = userMessage;
    const dateTime = await generateDateTime(
      userInput,
      userCurrentTime,
      timezone
    );
    const queryDate = await generateQueryDateFromUserInput(
      userId,
      timezone,
      userInput,
      userCurrentTime
    );
    const availabilityRes = await processAvailability(
      userId,
      timezone,
      dateTime,
      queryDate,
      userCurrentTime
    );
    if (availabilityRes?.query === 'completed') {
      const assistantMessage =
        await generateAssistantMessageFromAPIResponseForUserQuery(
          openai,
          availabilityRes.data as string,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'completed';
      messageHistoryObject.required = null;
    }

    return messageHistoryObject;
  } catch (e) {
    console.log(e, ' uanble to ask availability control center');
  }
};
