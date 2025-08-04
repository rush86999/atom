import { callOpenAI, extrapolateEndDateFromJSONData, extrapolateStartDateFromJSONData, generateAssistantMessageFromAPIResponseForUserQuery, generateDateTime, generateQueryDateFromUserInput, listEventsForUserGivenDates, } from '@chat/_libs/api-helper';
import { dayjs, getISODay } from '@chat/_libs/datetime/date-utils';
import { getUserPreferences } from '../api-helper';
import { v4 as uuid } from 'uuid';
import _ from 'lodash';
import { summarizeAvailabilityPrompt, summarizeAvailabilityExampleInput, summarizeAvailabilityExampleOutput, } from './prompts';
import { defaultOpenAIAPIKey, openAIChatGPT35LongModel, } from '@chat/_libs/constants';
import OpenAI from 'openai';
export const generateAvailableSlotsForDateForUser = (slotDuration, startDateInUserTimezone, userPreferences, timezone, notAvailableSlotsInEventTimezone, isFirstDay, isLastDay, endDateInUserTimezone) => {
    console.log(timezone, ' timezone');
    if (isFirstDay && isLastDay && endDateInUserTimezone) {
        const endTimes = userPreferences.endTimes;
        const dayOfWeekInt = getISODay(dayjs(startDateInUserTimezone).tz(timezone).toDate());
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
                if (dayjs(startDateInUserTimezone)
                    .tz(timezone)
                    .isBetween(dayjs(startDateInUserTimezone).tz(timezone).minute(startMinutes), dayjs(startDateInUserTimezone).tz(timezone).minute(endMinutes), 'minute', '[)')) {
                    minuteValueAsReceiver = endMinutes;
                }
            }
        }
        if (dayjs(startDateInUserTimezone)
            .tz(timezone)
            .isBetween(dayjs(startDateInUserTimezone)
            .tz(timezone)
            .minute(flooredValue * slotDuration), dayjs(startDateInUserTimezone).tz(timezone).minute(59), 'minute', '[)')) {
            startHourAsReceiver += 1;
            minuteValueAsReceiver = 0;
        }
        const startMinuteAsReceiver = minuteValueAsReceiver;
        const endHourWork = endTimes?.find((i) => i.day === dayOfWeekInt)?.hour ?? 20;
        const endMinuteWork = endTimes?.find((i) => i.day === dayOfWeekInt)?.minutes ?? 0;
        const endHour = dayjs(endDateInUserTimezone).tz(timezone).hour();
        const endMinute = dayjs(endDateInUserTimezone).tz(timezone).minute();
        // validate values before calculating
        const startTimes = userPreferences.startTimes;
        const workStartHour = startTimes?.find((i) => i.day === dayOfWeekInt)?.hour || 8;
        const workStartMinute = startTimes?.find((i) => i.day === dayOfWeekInt)?.minutes || 0;
        if (dayjs(startDateInUserTimezone)
            .tz(timezone)
            .isAfter(dayjs(startDateInUserTimezone)
            .tz(timezone)
            .hour(endHourWork)
            .minute(endMinuteWork))) {
            // return empty as outside of work time
            return [];
        }
        // change to work start time as sender start time before work start time
        if (dayjs(startDateInUserTimezone)
            .tz(timezone)
            .isBefore(dayjs(startDateInUserTimezone)
            .tz(timezone)
            .hour(workStartHour)
            .minute(workStartMinute))) {
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
            const availableSlots = [];
            console.log(startDateInUserTimezone, endTimes, dayOfWeekInt, dayOfMonth, startHourAsReceiver, startMinuteAsReceiver, endHour, endMinute, timezone, `startDate, endTimes, dayOfWeekIntByUser, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`);
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
            console.log(availableSlots, ' timeSlots inside generateTimeSlots for first day where startDate is before work start time');
            // filter out unavailable times
            const filteredAvailableSlotsInReceiverTimezone = availableSlots.filter((a) => {
                const foundIndex = notAvailableSlotsInEventTimezone?.findIndex((na) => {
                    const partA = dayjs(a.endDate)
                        .tz(timezone)
                        .second(0)
                        .isBetween(dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'), dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'), 'm', '[]');
                    const partB = dayjs(a.startDate)
                        .tz(timezone)
                        .second(0)
                        .isBetween(dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'), dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'), 'm', '[]');
                    const partC = dayjs(na.startDate)
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
            console.log(filteredAvailableSlotsInReceiverTimezone, ' filteredAvailableSlots');
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
        const availableSlotsInReceiverTimezone = [];
        console.log(startDateInUserTimezone, endTimes, dayOfWeekInt, endHourWork, endMinuteWork, timezone, `startDate, endTimes, dayOfWeekInt, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside first & last Day inside generateTimeslots`);
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
        console.log(availableSlotsInReceiverTimezone, ' availableSlots inside first & last same day');
        const filteredAvailableSlotsInReceiverTimezone = availableSlotsInReceiverTimezone.filter((a) => {
            const foundIndex = notAvailableSlotsInEventTimezone?.findIndex((na) => {
                const partA = dayjs(a.endDate)
                    .tz(timezone)
                    .second(0)
                    .isBetween(dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'), dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'), 'm', '[]');
                const partB = dayjs(a.startDate)
                    .tz(timezone)
                    .second(0)
                    .isBetween(dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'), dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'), 'm', '[]');
                const partC = dayjs(na.startDate)
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
        console.log(filteredAvailableSlotsInReceiverTimezone, ' filteredAvailableSlots');
        return filteredAvailableSlotsInReceiverTimezone;
    }
    if (isFirstDay) {
        // firstday can be started outside of work time
        // if firstDay start is after end time -- return []
        const endTimes = userPreferences.endTimes;
        const dayOfWeekInt = getISODay(dayjs(startDateInUserTimezone).tz(timezone).toDate());
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
                if (dayjs(startDateInUserTimezone)
                    .tz(timezone)
                    .isBetween(dayjs(startDateInUserTimezone).tz(timezone).minute(startMinutes), dayjs(startDateInUserTimezone).tz(timezone).minute(endMinutes), 'minute', '[)')) {
                    minuteValueAsReceiver = endMinutes;
                }
            }
        }
        if (dayjs(startDateInUserTimezone)
            .tz(timezone)
            .isBetween(dayjs(startDateInUserTimezone)
            .tz(timezone)
            .minute(flooredValue * slotDuration), dayjs(startDateInUserTimezone).tz(timezone).minute(59), 'minute', '[)')) {
            startHour += 1;
            minuteValueAsReceiver = 0;
        }
        const startMinuteAsReceiver = minuteValueAsReceiver;
        // convert to user timezone so everything is linked to user timezone
        const endHour = endTimes?.find((i) => i.day === dayOfWeekInt)?.hour ?? 20;
        const endMinute = endTimes?.find((i) => i.day === dayOfWeekInt)?.minutes ?? 0;
        // validate values before calculating
        const startTimes = userPreferences.startTimes;
        const workStartHour = startTimes?.find((i) => i.day === dayOfWeekInt)?.hour || 8;
        const workStartMinute = startTimes?.find((i) => i.day === dayOfWeekInt)?.minutes || 0;
        if (dayjs(startDateInUserTimezone)
            .tz(timezone)
            .isAfter(dayjs(startDateInUserTimezone)
            .tz(timezone)
            .hour(endHour)
            .minute(endMinute))) {
            // return empty as outside of work time
            return [];
        }
        // change to work start time as host start time before work start time
        if (dayjs(startDateInUserTimezone)
            .tz(timezone)
            .isBefore(dayjs(startDateInUserTimezone)
            .tz(timezone)
            .hour(workStartHour)
            .minute(workStartMinute))) {
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
            const availableSlotsInReceiverTimezone = [];
            console.log(startDateInUserTimezone, endTimes, dayOfWeekInt, dayOfMonth, startHour, startMinuteAsReceiver, endHour, endMinute, timezone, `startDate, endTimes, dayOfWeekIntByUser, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`);
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
            console.log(availableSlotsInReceiverTimezone, ' timeSlots inside generateTimeSlots for first day where startDate is before work start time');
            // filter out unavailable times
            const filteredAvailableSlotsInReceiverTimezone = availableSlotsInReceiverTimezone.filter((a) => {
                const foundIndex = notAvailableSlotsInEventTimezone?.findIndex((na) => {
                    const partA = dayjs(a.endDate)
                        .tz(timezone)
                        .second(0)
                        .isBetween(dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'), dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'), 'm', '[]');
                    const partB = dayjs(a.startDate)
                        .tz(timezone)
                        .second(0)
                        .isBetween(dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'), dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'), 'm', '[]');
                    const partC = dayjs(na.startDate)
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
            console.log(filteredAvailableSlotsInReceiverTimezone, ' filteredAvailableSlots');
            return filteredAvailableSlotsInReceiverTimezone;
        }
        const startDuration = dayjs.duration({
            hours: startHour,
            minutes: startMinute,
        });
        const endDuration = dayjs.duration({ hours: endHour, minutes: endMinute });
        const totalDuration = endDuration.subtract(startDuration);
        const totalMinutes = totalDuration.asMinutes();
        const availableSlotsInReceiverTimezone = [];
        console.log(startDateInUserTimezone, endTimes, dayOfWeekInt, endHour, endMinute, timezone, `startDate, endTimes, dayOfWeekInt, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`);
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
        const filteredAvailableSlotsInReceiverTimezone = availableSlotsInReceiverTimezone.filter((a) => {
            const foundIndex = notAvailableSlotsInEventTimezone?.findIndex((na) => {
                const partA = dayjs(a.endDate)
                    .tz(timezone)
                    .second(0)
                    .isBetween(dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'), dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'), 'm', '[]');
                const partB = dayjs(a.startDate)
                    .tz(timezone)
                    .second(0)
                    .isBetween(dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'), dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'), 'm', '[]');
                const partC = dayjs(na.startDate)
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
        console.log(filteredAvailableSlotsInReceiverTimezone, ' filteredAvailableSlots server timezone');
        return filteredAvailableSlotsInReceiverTimezone;
    }
    // not first day start from work start time schedule
    const startTimes = userPreferences.startTimes;
    const endTimes = userPreferences.endTimes;
    const dayOfWeekInt = getISODay(dayjs(startDateInUserTimezone).tz(timezone).toDate());
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
            if (dayjs(endDateInUserTimezone)
                .tz(timezone)
                .isBetween(dayjs(endDateInUserTimezone).tz(timezone).minute(startMinutes), dayjs(endDateInUserTimezone).tz(timezone).minute(endMinutes), 'minute', '[)')) {
                minuteValueBySender = startMinutes;
            }
        }
        endMinute = minuteValueBySender;
    }
    const startHourBySender = startTimes?.find((i) => i.day === dayOfWeekInt)?.hour || 8;
    const startMinuteBySender = startTimes?.find((i) => i.day === dayOfWeekInt)?.minutes || 0;
    const startDuration = dayjs.duration({
        hours: startHourBySender,
        minutes: startMinuteBySender,
    });
    const endDuration = dayjs.duration({ hours: endHour, minutes: endMinute });
    const totalDuration = endDuration.subtract(startDuration);
    const totalMinutes = totalDuration.asMinutes();
    const availableSlotsInReceiverTimezone = [];
    console.log(startDateInUserTimezone, endTimes, dayOfWeekInt, dayOfMonth, startHourBySender, startMinuteBySender, endHour, endMinute, timezone, `startDate, endTimes, dayOfWeekIntByHost, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateAvailableslots`);
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
    console.log(availableSlotsInReceiverTimezone, ' timeSlots inside generateTimeSlots not first day');
    console.log(notAvailableSlotsInEventTimezone, ' notAvailableSlotsInEventTimezone not first day');
    // filter out unavailable times
    const filteredAvailableSlotsInReceiverTimezone = availableSlotsInReceiverTimezone.filter((a) => {
        const foundIndex = notAvailableSlotsInEventTimezone?.findIndex((na) => {
            const partA = dayjs(a.endDate)
                .tz(timezone)
                .second(0)
                .isBetween(dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'), dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'), 'm', '[]');
            const partB = dayjs(a.startDate)
                .tz(timezone)
                .second(0)
                .isBetween(dayjs(na.startDate).tz(timezone).second(0).add(1, 'm'), dayjs(na.endDate).tz(timezone).second(0).subtract(1, 'm'), 'm', '[]');
            const partC = dayjs(na.startDate)
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
    console.log(filteredAvailableSlotsInReceiverTimezone, ' filteredAvailableSlots in receiverTimezone');
    // convert to receiverTimezone before returning values
    return filteredAvailableSlotsInReceiverTimezone;
};
export const generateAvailableSlotsforTimeWindowForUser = (windowStartDate, windowEndDate, slotDuration, userPreferences, timezone, notAvailableSlotsInEventTimezone) => {
    const diffDays = dayjs(windowEndDate).diff(dayjs(windowStartDate), 'd');
    const startDatesForEachDay = [];
    const availableSlots = [];
    for (let i = 0; i <= diffDays; i++) {
        startDatesForEachDay.push(dayjs(windowStartDate.slice(0, 19))
            .tz(timezone, true)
            .add(i, 'day')
            .format());
    }
    if (diffDays < 1) {
        const generatedSlots = generateAvailableSlotsForDateForUser(slotDuration, dayjs(windowStartDate.slice(0, 19)).tz(timezone, true).format(), userPreferences, timezone, notAvailableSlotsInEventTimezone, true, true, dayjs(windowEndDate.slice(0, 19)).tz(timezone, true).format());
        //  0123456789
        //  2020-04-02T08:02:17-05:00
        availableSlots.push(...generatedSlots);
    }
    else {
        for (let i = 0; i < startDatesForEachDay.length; i++) {
            const filteredNotAvailableSlotsInEventTimezone = notAvailableSlotsInEventTimezone?.filter((na) => dayjs(na?.startDate).tz(timezone).format('YYYY-MM-DD') ===
                dayjs(startDatesForEachDay?.[i]).tz(timezone).format('YYYY-MM-DD'));
            if (i === 0) {
                const generatedSlots = generateAvailableSlotsForDateForUser(slotDuration, startDatesForEachDay?.[i], userPreferences, timezone, filteredNotAvailableSlotsInEventTimezone, true, false, dayjs(windowEndDate.slice(0, 19)).tz(timezone, true).format());
                //  0123456789
                //  2020-04-02T08:02:17-05:00
                availableSlots.push(...generatedSlots);
                continue;
            }
            if (i === startDatesForEachDay.length - 1) {
                const generatedSlots = generateAvailableSlotsForDateForUser(slotDuration, startDatesForEachDay?.[i], userPreferences, timezone, filteredNotAvailableSlotsInEventTimezone, false, true, dayjs(windowEndDate.slice(0, 19)).tz(timezone, true).format());
                availableSlots.push(...generatedSlots);
                continue;
            }
            const generatedSlots = generateAvailableSlotsForDateForUser(slotDuration, startDatesForEachDay?.[i], userPreferences, timezone, filteredNotAvailableSlotsInEventTimezone);
            availableSlots.push(...generatedSlots);
        }
    }
    return { availableSlots };
};
export const generateAvailabilityForUser = async (userId, windowStartDate, windowEndDate, timezone, slotDuration) => {
    try {
        const oldEventsInEventTimezone = await listEventsForUserGivenDates(userId, windowStartDate, windowEndDate);
        console.log(oldEventsInEventTimezone, ' oldEventsInEventTimezone');
        if (!oldEventsInEventTimezone || !(oldEventsInEventTimezone?.length > 0)) {
            console.log('no old events in generateAvailability');
        }
        const oldEventsInEventTimezoneFormatted = oldEventsInEventTimezone?.map((e) => ({
            ...e,
            startDate: dayjs(e?.startDate.slice(0, 19))
                .tz(e?.timezone, true)
                .format(),
            endDate: dayjs(e?.endDate.slice(0, 19)).tz(e?.timezone, true).format(),
            timezone: e?.timezone,
        }));
        const notAvailableFromEvents = oldEventsInEventTimezoneFormatted?.map((e) => ({
            startDate: e?.startDate,
            endDate: e?.endDate,
        }));
        const userPreferences = await getUserPreferences(userId);
        const { availableSlots: availableSlots } = await generateAvailableSlotsforTimeWindowForUser(windowStartDate, windowEndDate, slotDuration, userPreferences, timezone, notAvailableFromEvents?.length > 0 ? notAvailableFromEvents : undefined);
        return availableSlots;
    }
    catch (e) {
        console.log(e, ' unable to generate availability');
    }
};
export const processAvailability = async (userId, timezone, dateTimeJSONBody, queryDateJSONBody, currentTime) => {
    try {
        const windowStartDate = extrapolateStartDateFromJSONData(currentTime, timezone, queryDateJSONBody?.start_date?.year, queryDateJSONBody?.start_date?.month, queryDateJSONBody?.start_date?.day, undefined, queryDateJSONBody?.start_date?.hour, queryDateJSONBody?.start_date?.minute, queryDateJSONBody?.start_date?.time, queryDateJSONBody?.start_date?.relativeTimeChangeFromNow, queryDateJSONBody?.start_date?.relativeTimeFromNow);
        const windowEndDate = extrapolateEndDateFromJSONData(currentTime, timezone, queryDateJSONBody?.end_date?.year, queryDateJSONBody?.end_date?.month, queryDateJSONBody?.end_date?.day, undefined, queryDateJSONBody?.end_date?.hour, queryDateJSONBody?.end_date?.minute, queryDateJSONBody?.end_date?.time, queryDateJSONBody?.end_date?.relativeTimeChangeFromNow, queryDateJSONBody?.end_date?.relativeTimeFromNow);
        // get default values
        // const defaultMeetingPreferences = await getChatMeetingPreferenceGivenUserId(userId)
        const body = {
            userId,
            windowStartDate: windowStartDate || dayjs().format(),
            windowEndDate: windowEndDate || dayjs().add(2, 'w').format(),
            timezone,
            slotDuration: dateTimeJSONBody?.duration || 30,
        };
        console.log(body, ' body inside processAvailability');
        const response = {
            query: '',
            data: {},
            skill: 'queryAvailability',
        };
        const availableSlots = await generateAvailabilityForUser(body?.userId, body?.windowStartDate, body?.windowEndDate, timezone, body?.slotDuration);
        response.query = 'completed';
        if (!(availableSlots?.length > 0)) {
            response.data = 'no free time slots available';
            return response;
        }
        const openai = new OpenAI({
            apiKey: defaultOpenAIAPIKey,
        });
        const uniqDates = _.uniqBy(availableSlots, (curr) => dayjs(curr?.startDate?.slice(0, 19)).tz(timezone).format('YYYY-MM-DD'));
        // let availabilityText = ''
        const prompt = summarizeAvailabilityPrompt;
        const exampleInput = summarizeAvailabilityExampleInput;
        const exampleOutput = summarizeAvailabilityExampleOutput;
        let openAIAvailabilityRes = '';
        for (const uniqDate of uniqDates) {
            const filteredAvailability = availableSlots?.filter((a) => dayjs(a?.startDate).tz(timezone).format('YYYY-MM-DD') ===
                dayjs(uniqDate?.startDate).tz(timezone).format('YYYY-MM-DD'));
            if (filteredAvailability?.length > 0) {
                // availabilityText += `${dayjs(uniqDate?.startDate).tz(timezone).format('L')} - ${filteredAvailability?.map((curr) => (`${dayjs(curr?.startDate).tz(timezone).format('LT')} - ${dayjs(curr?.endDate).tz(timezone).format('LT')},`))?.reduce((prev, curr) => (`${prev} ${curr}`), '')}` + '\n\n'
                const miniAvailabilityText = `${dayjs(uniqDate?.startDate).tz(timezone).format('L')} - ${filteredAvailability?.map((curr) => `${dayjs(curr?.startDate).tz(timezone).format('LT')} - ${dayjs(curr?.endDate).tz(timezone).format('LT')},`)?.reduce((prev, curr) => `${prev} ${curr}`, '')}` +
                    '\n\n';
                const miniUserData = `My availability: ` + miniAvailabilityText;
                console.log(miniUserData, ' newAvailabilityPrompt');
                const miniOpenAIAvailabilityRes = await callOpenAI(openai, prompt, openAIChatGPT35LongModel, miniUserData, exampleInput, exampleOutput);
                // validate openai res
                if (!miniOpenAIAvailabilityRes) {
                    throw new Error('no openAIAvailabilityRes present inside appointmentRequest');
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
    }
    catch (e) {
        console.log(e, ' uanble to process availability');
    }
};
export const askAvailabilityControlCenterForPending = async (openai, userId, timezone, messageHistoryObject, userCurrentTime) => {
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
        const dateTime = await generateDateTime(userInput, userCurrentTime, timezone);
        const queryDate = await generateQueryDateFromUserInput(userId, timezone, userInput, userCurrentTime);
        const availabilityRes = await processAvailability(userId, timezone, dateTime, queryDate, userCurrentTime);
        if (availabilityRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, availabilityRes.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        return messageHistoryObject;
    }
    catch (e) {
        console.log(e, ' uanble to ask availability control center');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQ0EsT0FBTyxFQUNMLFVBQVUsRUFDViw4QkFBOEIsRUFDOUIsZ0NBQWdDLEVBQ2hDLG1EQUFtRCxFQUNuRCxnQkFBZ0IsRUFDaEIsOEJBQThCLEVBQzlCLDJCQUEyQixHQUM1QixNQUFNLHdCQUF3QixDQUFDO0FBQ2hDLE9BQU8sRUFBRSxLQUFLLEVBQUUsU0FBUyxFQUFFLE1BQU0saUNBQWlDLENBQUM7QUFFbkUsT0FBTyxFQUFFLGtCQUFrQixFQUFFLE1BQU0sZUFBZSxDQUFDO0FBR25ELE9BQU8sRUFBRSxFQUFFLElBQUksSUFBSSxFQUFFLE1BQU0sTUFBTSxDQUFDO0FBRWxDLE9BQU8sQ0FBQyxNQUFNLFFBQVEsQ0FBQztBQUN2QixPQUFPLEVBQ0wsMkJBQTJCLEVBQzNCLGlDQUFpQyxFQUNqQyxrQ0FBa0MsR0FJbkMsTUFBTSxXQUFXLENBQUM7QUFDbkIsT0FBTyxFQUNMLG1CQUFtQixFQUNuQix3QkFBd0IsR0FDekIsTUFBTSx1QkFBdUIsQ0FBQztBQUkvQixPQUFPLE1BQU0sTUFBTSxRQUFRLENBQUM7QUFFNUIsTUFBTSxDQUFDLE1BQU0sb0NBQW9DLEdBQUcsQ0FDbEQsWUFBb0IsRUFDcEIsdUJBQStCLEVBQy9CLGVBQW1DLEVBQ25DLFFBQWdCLEVBQ2hCLGdDQUF5RCxFQUN6RCxVQUFvQixFQUNwQixTQUFtQixFQUNuQixxQkFBOEIsRUFDOUIsRUFBRTtJQUNGLE9BQU8sQ0FBQyxHQUFHLENBQUMsUUFBUSxFQUFFLFdBQVcsQ0FBQyxDQUFDO0lBRW5DLElBQUksVUFBVSxJQUFJLFNBQVMsSUFBSSxxQkFBcUIsRUFBRSxDQUFDO1FBQ3JELE1BQU0sUUFBUSxHQUFHLGVBQWUsQ0FBQyxRQUFRLENBQUM7UUFDMUMsTUFBTSxZQUFZLEdBQUcsU0FBUyxDQUM1QixLQUFLLENBQUMsdUJBQXVCLENBQUMsQ0FB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RyxNQUFNLDhCQUE4QixDQUNwRCxNQUFNLEVBQ04sUUFBUSxFQUNSLFNBQVMsRUFDVCxlQUFlLENBQ2hCLENBQUM7UUFDRixNQUFNLGVBQWUsR0FBRyxNQUFNLG1CQUFtQixDQUMvQyxNQUFNLEVBQ04sUUFBUSxFQUNSLFFBQVEsRUFDUixTQUFTLEVBQ1QsZUFBZSxDQUNoQixDQUFDO1FBQ0YsSUFBSSxlQUFlLEVBQUUsS0FBSyxLQUFLLFdBQVcsRUFBRSxDQUFDO1lBQzNDLE1BQU0sZ0JBQWdCLEdBQ3BCLE1BQU0sbURBQW1ELENBQ3ZELE1BQU0sRUFDTixlQUFlLENBQUMsSUFBYyxFQUM5QixvQkFBb0IsQ0FDckIsQ0FBQztZQUVKLG9CQUFvQixDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUMsZ0JBQWdCLENBQUMsQ0FBQztZQUNyRCxvQkFBb0IsQ0FBQyxLQUFLLEdBQUcsV0FBVyxDQUFDO1lBQ3pDLG9CQUFvQixDQUFDLFFBQVEsR0FBRyxJQUFJLENBQUM7UUFDdkMsQ0FBQztRQUVELE9BQU8sb0JBQW9CLENBQUM7SUFDOUIsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSw0Q0FBNEMsQ0FBQyxDQUFDO0lBQy9ELENBQUM7QUFDSCxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgUXVlcnlDYWxlbmRhckV4dHJhY3RlZEpTT05UeXBlIGZyb20gJ0BjaGF0L19saWJzL2RhdGV0aW1lL1F1ZXJ5Q2FsZW5kYXJFeHRyYWN0ZWREYXRlSlNPTlR5cGUnO1xuaW1wb3J0IHtcbiAgY2FsbE9wZW5BSSxcbiAgZXh0cmFwb2xhdGVFbmREYXRlRnJvbUpTT05EYXRhLFxuICBleHRyYXBvbGF0ZVN0YXJ0RGF0ZUZyb21KU09ORGF0YSxcbiAgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlRnJvbUFQSVJlc3BvbnNlRm9yVXNlclF1ZXJ5LFxuICBnZW5lcmF0ZURhdGVUaW1lLFxuICBnZW5lcmF0ZVF1ZXJ5RGF0ZUZyb21Vc2VySW5wdXQsXG4gIGxpc3RFdmVudHNGb3JVc2VyR2l2ZW5EYXRlcyxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvYXBpLWhlbHBlcic7XG5pbXBvcnQgeyBkYXlqcywgZ2V0SVNPRGF5IH0gZnJvbSAnQGNoYXQvX2xpYnMvZGF0ZXRpbWUvZGF0ZS11dGlscyc7XG5pbXBvcnQgeyBOb3RBdmFpbGFibGVTbG90VHlwZSwgVXNlckF2YWlsYWJpbGl0eUJvZHlUeXBlIH0gZnJvbSAnLi90eXBlcyc7XG5pbXBvcnQgeyBnZXRVc2VyUHJlZmVyZW5jZXMgfSBmcm9tICcuLi9hcGktaGVscGVyJztcbmltcG9ydCB7IFVzZXJQcmVmZXJlbmNlVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1VzZXJQcmVmZXJlbmNlVHlwZSc7XG5pbXBvcnQgeyBBdmFpbGFibGVTbG90VHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3NraWxscy9vcmRlckNhbGVuZGFyL2dlbmVyYXRlTWVldGluZ0ludml0ZS9hdmFpbGFiaWxpdHlUeXBlcyc7XG5pbXBvcnQgeyB2NCBhcyB1dWlkIH0gZnJvbSAndXVpZCc7XG5pbXBvcnQgRGF0ZVRpbWVKU09OVHlwZSBmcm9tICdAY2hhdC9fbGlicy9kYXRldGltZS9EYXRlVGltZUpTT05KU09OVHlwZSc7XG5pbXBvcnQgXyBmcm9tICdsb2Rhc2gnO1xuaW1wb3J0IHtcbiAgc3VtbWFyaXplQXZhaWxhYmlsaXR5UHJvbXB0LFxuICBzdW1tYXJpemVBdmFpbGFiaWxpdHlFeGFtcGxlSW5wdXQsXG4gIHN1bW1hcml6ZUF2YWlsYWJpbGl0eUV4YW1wbGVPdXRwdXQsXG4gIHN1bW1hcml6ZUF2YWlsYWJpbGl0eVJlc3BvbnNlc1Byb21wdCxcbiAgc3VtbWFyaXplQXZhaWxhYmlsaXR5UmVzcG9uc2VzUHJvbXB0RXhhbXBsZUlucHV0LFxuICBzdW1tYXJpemVBdmFpbGFiaWxpdHlSZXNwb25zZXNQcm9tcHRFeGFtcGxlT3V0cHV0LFxufSBmcm9tICcuL3Byb21wdHMnO1xuaW1wb3J0IHtcbiAgZGVmYXVsdE9wZW5BSUFQSUtleSxcbiAgb3BlbkFJQ2hhdEdQVDM1TG9uZ01vZGVsLFxufSBmcm9tICdAY2hhdC9fbGlicy9jb25zdGFudHMnO1xuXG5pbXBvcnQgUmVzcG9uc2VBY3Rpb25UeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1Jlc3BvbnNlQWN0aW9uVHlwZSc7XG5pbXBvcnQgeyBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL01lc3NhZ2luZy9NZXNzYWdpbmdUeXBlcyc7XG5pbXBvcnQgT3BlbkFJIGZyb20gJ29wZW5haSc7XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZUF2YWlsYWJsZVNsb3RzRm9yRGF0ZUZvclVzZXIgPSAoXG4gIHNsb3REdXJhdGlvbjogbnVtYmVyLFxuICBzdGFydERhdGVJblVzZXJUaW1lem9uZTogc3RyaW5nLFxuICB1c2VyUHJlZmVyZW5jZXM6IFVzZXJQcmVmZXJlbmNlVHlwZSxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAgbm90QXZhaWxhYmxlU2xvdHNJbkV2ZW50VGltZXpvbmU/OiBOb3RBdmFpbGFibGVTbG90VHlwZVtdLFxuICBpc0ZpcnN0RGF5PzogYm9vbGVhbixcbiAgaXNMYXN0RGF5PzogYm9vbGVhbixcbiAgZW5kRGF0ZUluVXNlclRpbWV6b25lPzogc3RyaW5nXG4pID0+IHtcbiAgY29uc29sZS5sb2codGltZXpvbmUsICcgdGltZXpvbmUnKTtcblxuICBpZiAoaXNGaXJzdERheSAmJiBpc0xhc3REYXkgJiYgZW5kRGF0ZUluVXNlclRpbWV6b25lKSB7XG4gICAgY29uc3QgZW5kVGltZXMgPSB1c2VyUHJlZmVyZW5jZXMuZW5kVGltZXM7XG4gICAgY29uc3QgZGF5T2ZXZWVrSW50ID0gZ2V0SVNPRGF5KFxuICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpLnR6KHRpbWV6b25lKS50b0RhdGUoKVxuICAgICk7XG5cbiAgICBjb25zdCBkYXlPZk1vbnRoID0gZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpLnR6KHRpbWV6b25lKS5kYXRlKCk7XG4gICAgbGV0IHN0YXJ0SG91ckFzUmVjZWl2ZXIgPSBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSlcbiAgICAgIC50eih0aW1lem9uZSlcbiAgICAgIC5ob3VyKCk7XG5cbiAgICBjb25zdCBmbG9vcmVkVmFsdWUgPSBNYXRoLmZsb29yKDYwIC8gc2xvdER1cmF0aW9uKTtcblxuICAgIGxldCBtaW51dGVWYWx1ZUFzUmVjZWl2ZXIgPSAwO1xuICAgIGlmIChkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSkudHoodGltZXpvbmUpLm1pbnV0ZSgpICE9PSAwKSB7XG4gICAgICBmb3IgKGxldCBpID0gMDsgaSA8IGZsb29yZWRWYWx1ZTsgaSsrKSB7XG4gICAgICAgIGNvbnN0IGVuZE1pbnV0ZXMgPSAoaSArIDEpICogc2xvdER1cmF0aW9uO1xuICAgICAgICBjb25zdCBzdGFydE1pbnV0ZXMgPSBpICogc2xvdER1cmF0aW9uO1xuICAgICAgICBpZiAoXG4gICAgICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSkudHoodGltZXpvbmUpLm1pbnV0ZShzdGFydE1pbnV0ZXMpLFxuICAgICAgICAgICAgICBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSkudHoodGltZXpvbmUpLm1pbnV0ZShlbmRNaW51dGVzKSxcbiAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgIClcbiAgICAgICAgKSB7XG4gICAgICAgICAgbWludXRlVmFsdWVBc1JlY2VpdmVyID0gZW5kTWludXRlcztcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cblxuICAgIGlmIChcbiAgICAgIGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAubWludXRlKGZsb29yZWRWYWx1ZSAqIHNsb3REdXJhdGlvbiksXG4gICAgICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpLnR6KHRpbWV6b25lKS5taW51dGUoNTkpLFxuICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICdbKSdcbiAgICAgICAgKVxuICAgICkge1xuICAgICAgc3RhcnRIb3VyQXNSZWNlaXZlciArPSAxO1xuICAgICAgbWludXRlVmFsdWVBc1JlY2VpdmVyID0gMDtcbiAgICB9XG5cbiAgICBjb25zdCBzdGFydE1pbnV0ZUFzUmVjZWl2ZXIgPSBtaW51dGVWYWx1ZUFzUmVjZWl2ZXI7XG5cbiAgICBjb25zdCBlbmRIb3VyV29yayA9XG4gICAgICBlbmRUaW1lcz8uZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCk/LmhvdXIgPz8gMjA7XG4gICAgY29uc3QgZW5kTWludXRlV29yayA9XG4gICAgICBlbmRUaW1lcz8uZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCk/Lm1pbnV0ZXMgPz8gMDtcbiAgICBjb25zdCBlbmRIb3VyID0gZGF5anMoZW5kRGF0ZUluVXNlclRpbWV6b25lKS50eih0aW1lem9uZSkuaG91cigpO1xuICAgIGNvbnN0IGVuZE1pbnV0ZSA9IGRheWpzKGVuZERhdGVJblVzZXJUaW1lem9uZSkudHoodGltZXpvbmUpLm1pbnV0ZSgpO1xuXG4gICAgLy8gdmFsaWRhdGUgdmFsdWVzIGJlZm9yZSBjYWxjdWxhdGluZ1xuICAgIGNvbnN0IHN0YXJ0VGltZXMgPSB1c2VyUHJlZmVyZW5jZXMuc3RhcnRUaW1lcztcbiAgICBjb25zdCB3b3JrU3RhcnRIb3VyID1cbiAgICAgIHN0YXJ0VGltZXM/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpPy5ob3VyIHx8IDg7XG4gICAgY29uc3Qgd29ya1N0YXJ0TWludXRlID1cbiAgICAgIHN0YXJ0VGltZXM/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpPy5taW51dGVzIHx8IDA7XG5cbiAgICBpZiAoXG4gICAgICBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSlcbiAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAuaXNBZnRlcihcbiAgICAgICAgICBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgIC5ob3VyKGVuZEhvdXJXb3JrKVxuICAgICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGVXb3JrKVxuICAgICAgICApXG4gICAgKSB7XG4gICAgICAvLyByZXR1cm4gZW1wdHkgYXMgb3V0c2lkZSBvZiB3b3JrIHRpbWVcbiAgICAgIHJldHVybiBbXTtcbiAgICB9XG5cbiAgICAvLyBjaGFuZ2UgdG8gd29yayBzdGFydCB0aW1lIGFzIHNlbmRlciBzdGFydCB0aW1lIGJlZm9yZSB3b3JrIHN0YXJ0IHRpbWVcbiAgICBpZiAoXG4gICAgICBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSlcbiAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAuaXNCZWZvcmUoXG4gICAgICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyKVxuICAgICAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGUpXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICAgIGhvdXJzOiB3b3JrU3RhcnRIb3VyLFxuICAgICAgICBtaW51dGVzOiB3b3JrU3RhcnRNaW51dGUsXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgICBob3VyczogZW5kSG91cixcbiAgICAgICAgbWludXRlczogZW5kTWludXRlLFxuICAgICAgfSk7XG4gICAgICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbik7XG4gICAgICBjb25zdCB0b3RhbE1pbnV0ZXMgPSB0b3RhbER1cmF0aW9uLmFzTWludXRlcygpO1xuXG4gICAgICBjb25zdCBhdmFpbGFibGVTbG90czogQXZhaWxhYmxlU2xvdFR5cGVbXSA9IFtdO1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lLFxuICAgICAgICBlbmRUaW1lcyxcbiAgICAgICAgZGF5T2ZXZWVrSW50LFxuICAgICAgICBkYXlPZk1vbnRoLFxuICAgICAgICBzdGFydEhvdXJBc1JlY2VpdmVyLFxuICAgICAgICBzdGFydE1pbnV0ZUFzUmVjZWl2ZXIsXG4gICAgICAgIGVuZEhvdXIsXG4gICAgICAgIGVuZE1pbnV0ZSxcbiAgICAgICAgdGltZXpvbmUsXG4gICAgICAgIGBzdGFydERhdGUsIGVuZFRpbWVzLCBkYXlPZldlZWtJbnRCeVVzZXIsIGRheU9mTW9udGgsIHN0YXJ0SG91ciwgc3RhcnRNaW51dGUsIGVuZEhvdXIsIGVuZE1pbnV0ZSB0b3RhbE1pbnV0ZXMsIHRpbWV6b25lLCBpbnNpZGUgZmlyc3REYXkgaW5zaWRlIGdlbmVyYXRlVGltZXNsb3RzYFxuICAgICAgKTtcbiAgICAgIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IHNsb3REdXJhdGlvbikge1xuICAgICAgICBpZiAoaSA+IHRvdGFsTWludXRlcykge1xuICAgICAgICAgIGNvbnRpbnVlO1xuICAgICAgICB9XG5cbiAgICAgICAgYXZhaWxhYmxlU2xvdHMucHVzaCh7XG4gICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgICBzdGFydERhdGU6IGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgLmhvdXIod29ya1N0YXJ0SG91cilcbiAgICAgICAgICAgIC5taW51dGUod29ya1N0YXJ0TWludXRlKVxuICAgICAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgICBlbmREYXRlOiBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXIpXG4gICAgICAgICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZSlcbiAgICAgICAgICAgIC5hZGQoaSArIHNsb3REdXJhdGlvbiwgJ21pbnV0ZScpXG4gICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICAgIH0pO1xuICAgICAgfVxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGF2YWlsYWJsZVNsb3RzLFxuICAgICAgICAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMgZm9yIGZpcnN0IGRheSB3aGVyZSBzdGFydERhdGUgaXMgYmVmb3JlIHdvcmsgc3RhcnQgdGltZSdcbiAgICAgICk7XG5cbiAgICAgIC8vIGZpbHRlciBvdXQgdW5hdmFpbGFibGUgdGltZXNcbiAgICAgIGNvbnN0IGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUgPSBhdmFpbGFibGVTbG90cy5maWx0ZXIoXG4gICAgICAgIChhKSA9PiB7XG4gICAgICAgICAgY29uc3QgZm91bmRJbmRleCA9IG5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lPy5maW5kSW5kZXgoXG4gICAgICAgICAgICAobmEpID0+IHtcbiAgICAgICAgICAgICAgY29uc3QgcGFydEEgPSBkYXlqcyhhLmVuZERhdGUpXG4gICAgICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKS50eih0aW1lem9uZSkuc2Vjb25kKDApLmFkZCgxLCAnbScpLFxuICAgICAgICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSkudHoodGltZXpvbmUpLnNlY29uZCgwKS5zdWJ0cmFjdCgxLCAnbScpLFxuICAgICAgICAgICAgICAgICAgJ20nLFxuICAgICAgICAgICAgICAgICAgJ1tdJ1xuICAgICAgICAgICAgICAgICk7XG5cbiAgICAgICAgICAgICAgY29uc3QgcGFydEIgPSBkYXlqcyhhLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpLnR6KHRpbWV6b25lKS5zZWNvbmQoMCkuYWRkKDEsICdtJyksXG4gICAgICAgICAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKS50eih0aW1lem9uZSkuc2Vjb25kKDApLnN1YnRyYWN0KDEsICdtJyksXG4gICAgICAgICAgICAgICAgICAnbScsXG4gICAgICAgICAgICAgICAgICAnW10nXG4gICAgICAgICAgICAgICAgKTtcblxuICAgICAgICAgICAgICBjb25zdCBwYXJ0QyA9XG4gICAgICAgICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKVxuICAgICAgICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpID09PVxuICAgICAgICAgICAgICAgICAgZGF5anMoYS5zdGFydERhdGUpXG4gICAgICAgICAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgJiZcbiAgICAgICAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKVxuICAgICAgICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpID09PVxuICAgICAgICAgICAgICAgICAgZGF5anMoYS5lbmREYXRlKVxuICAgICAgICAgICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpO1xuXG4gICAgICAgICAgICAgIGNvbnN0IGlzTm90QXZhaWxhYmxlID0gcGFydEEgfHwgcGFydEIgfHwgcGFydEM7XG5cbiAgICAgICAgICAgICAgLy8gY29uc29sZS5sb2coYSwgbmEsICcgYSwgbmEnKVxuICAgICAgICAgICAgICByZXR1cm4gaXNOb3RBdmFpbGFibGU7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgKTtcblxuICAgICAgICAgIGNvbnNvbGUubG9nKGZvdW5kSW5kZXgsICcgZm91bmRJbmRleCcpO1xuXG4gICAgICAgICAgaWYgKGZvdW5kSW5kZXggIT09IHVuZGVmaW5lZCAmJiBmb3VuZEluZGV4ID4gLTEpIHtcbiAgICAgICAgICAgIHJldHVybiBmYWxzZTtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICByZXR1cm4gdHJ1ZTtcbiAgICAgICAgfVxuICAgICAgKTtcblxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUsXG4gICAgICAgICcgZmlsdGVyZWRBdmFpbGFibGVTbG90cydcbiAgICAgICk7XG5cbiAgICAgIHJldHVybiBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lO1xuICAgIH1cblxuICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICBob3Vyczogc3RhcnRIb3VyQXNSZWNlaXZlcixcbiAgICAgIG1pbnV0ZXM6IHN0YXJ0TWludXRlQXNSZWNlaXZlcixcbiAgICB9KTtcbiAgICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHsgaG91cnM6IGVuZEhvdXIsIG1pbnV0ZXM6IGVuZE1pbnV0ZSB9KTtcbiAgICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbik7XG4gICAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcbiAgICBjb25zb2xlLmxvZyh0b3RhbE1pbnV0ZXMsICcgdG90YWxNaW51dGVzIGluc2lkZSBmaXJzdCBhbmQgbGFzdCBzYW1lIGRheScpO1xuICAgIGNvbnN0IGF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lOiBBdmFpbGFibGVTbG90VHlwZVtdID0gW107XG4gICAgY29uc29sZS5sb2coXG4gICAgICBzdGFydERhdGVJblVzZXJUaW1lem9uZSxcbiAgICAgIGVuZFRpbWVzLFxuICAgICAgZGF5T2ZXZWVrSW50LFxuICAgICAgZW5kSG91cldvcmssXG4gICAgICBlbmRNaW51dGVXb3JrLFxuICAgICAgdGltZXpvbmUsXG4gICAgICBgc3RhcnREYXRlLCBlbmRUaW1lcywgZGF5T2ZXZWVrSW50LCBkYXlPZk1vbnRoLCBzdGFydEhvdXIsIHN0YXJ0TWludXRlLCBlbmRIb3VyLCBlbmRNaW51dGUgdG90YWxNaW51dGVzLCB0aW1lem9uZSwgaW5zaWRlIGZpcnN0ICYgbGFzdCBEYXkgaW5zaWRlIGdlbmVyYXRlVGltZXNsb3RzYFxuICAgICk7XG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gc2xvdER1cmF0aW9uKSB7XG4gICAgICBpZiAoaSA+IHRvdGFsTWludXRlcykge1xuICAgICAgICBjb250aW51ZTtcbiAgICAgIH1cbiAgICAgIGF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lLnB1c2goe1xuICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICBzdGFydERhdGU6IGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAuaG91cihzdGFydEhvdXJBc1JlY2VpdmVyKVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVBc1JlY2VpdmVyKVxuICAgICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgZW5kRGF0ZTogZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ckFzUmVjZWl2ZXIpXG4gICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUFzUmVjZWl2ZXIpXG4gICAgICAgICAgLmFkZChpICsgc2xvdER1cmF0aW9uLCAnbWludXRlJylcbiAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgfSk7XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZSxcbiAgICAgICcgYXZhaWxhYmxlU2xvdHMgaW5zaWRlIGZpcnN0ICYgbGFzdCBzYW1lIGRheSdcbiAgICApO1xuICAgIGNvbnN0IGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUgPVxuICAgICAgYXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUuZmlsdGVyKChhKSA9PiB7XG4gICAgICAgIGNvbnN0IGZvdW5kSW5kZXggPSBub3RBdmFpbGFibGVTbG90c0luRXZlbnRUaW1lem9uZT8uZmluZEluZGV4KChuYSkgPT4ge1xuICAgICAgICAgIGNvbnN0IHBhcnRBID0gZGF5anMoYS5lbmREYXRlKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKS50eih0aW1lem9uZSkuc2Vjb25kKDApLmFkZCgxLCAnbScpLFxuICAgICAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKS50eih0aW1lem9uZSkuc2Vjb25kKDApLnN1YnRyYWN0KDEsICdtJyksXG4gICAgICAgICAgICAgICdtJyxcbiAgICAgICAgICAgICAgJ1tdJ1xuICAgICAgICAgICAgKTtcblxuICAgICAgICAgIGNvbnN0IHBhcnRCID0gZGF5anMoYS5zdGFydERhdGUpXG4gICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpLnR6KHRpbWV6b25lKS5zZWNvbmQoMCkuYWRkKDEsICdtJyksXG4gICAgICAgICAgICAgIGRheWpzKG5hLmVuZERhdGUpLnR6KHRpbWV6b25lKS5zZWNvbmQoMCkuc3VidHJhY3QoMSwgJ20nKSxcbiAgICAgICAgICAgICAgJ20nLFxuICAgICAgICAgICAgICAnW10nXG4gICAgICAgICAgICApO1xuXG4gICAgICAgICAgY29uc3QgcGFydEMgPVxuICAgICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKVxuICAgICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpID09PVxuICAgICAgICAgICAgICBkYXlqcyhhLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSAmJlxuICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSA9PT1cbiAgICAgICAgICAgICAgZGF5anMoYS5lbmREYXRlKVxuICAgICAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpO1xuXG4gICAgICAgICAgY29uc3QgaXNOb3RBdmFpbGFibGUgPSBwYXJ0QSB8fCBwYXJ0QiB8fCBwYXJ0QztcblxuICAgICAgICAgIC8vIGNvbnNvbGUubG9nKGEsIG5hLCAnIGEsIG5hJylcblxuICAgICAgICAgIHJldHVybiBpc05vdEF2YWlsYWJsZTtcbiAgICAgICAgfSk7XG5cbiAgICAgICAgY29uc29sZS5sb2coZm91bmRJbmRleCwgJyBmb3VuZEluZGV4Jyk7XG5cbiAgICAgICAgaWYgKGZvdW5kSW5kZXggIT09IHVuZGVmaW5lZCAmJiBmb3VuZEluZGV4ID4gLTEpIHtcbiAgICAgICAgICByZXR1cm4gZmFsc2U7XG4gICAgICAgIH1cblxuICAgICAgICByZXR1cm4gdHJ1ZTtcbiAgICAgIH0pO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lLFxuICAgICAgJyBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzJ1xuICAgICk7XG4gICAgcmV0dXJuIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmU7XG4gIH1cblxuICBpZiAoaXNGaXJzdERheSkge1xuICAgIC8vIGZpcnN0ZGF5IGNhbiBiZSBzdGFydGVkIG91dHNpZGUgb2Ygd29yayB0aW1lXG4gICAgLy8gaWYgZmlyc3REYXkgc3RhcnQgaXMgYWZ0ZXIgZW5kIHRpbWUgLS0gcmV0dXJuIFtdXG4gICAgY29uc3QgZW5kVGltZXMgPSB1c2VyUHJlZmVyZW5jZXMuZW5kVGltZXM7XG4gICAgY29uc3QgZGF5T2ZXZWVrSW50ID0gZ2V0SVNPRGF5KFxuICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpLnR6KHRpbWV6b25lKS50b0RhdGUoKVxuICAgICk7XG5cbiAgICAvLyBtb250aCBpcyB6ZXJvLWluZGV4ZWRcbiAgICAvLyBjb25zdCBtb250aCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnR6KHVzZXJUaW1lem9uZSkubW9udGgoKVxuICAgIGNvbnN0IGRheU9mTW9udGggPSBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSkudHoodGltZXpvbmUpLmRhdGUoKTtcbiAgICBsZXQgc3RhcnRIb3VyID0gZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpLnR6KHRpbWV6b25lKS5ob3VyKCk7XG5cbiAgICBjb25zdCBzdGFydE1pbnV0ZSA9IGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKS50eih0aW1lem9uZSkubWludXRlKCk7XG4gICAgLy8gY3JlYXRlIHNsb3Qgc2l6ZXNcbiAgICBjb25zdCBmbG9vcmVkVmFsdWUgPSBNYXRoLmZsb29yKDYwIC8gc2xvdER1cmF0aW9uKTtcblxuICAgIGxldCBtaW51dGVWYWx1ZUFzUmVjZWl2ZXIgPSAwO1xuICAgIGlmIChkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSkudHoodGltZXpvbmUpLm1pbnV0ZSgpICE9PSAwKSB7XG4gICAgICBmb3IgKGxldCBpID0gMDsgaSA8IGZsb29yZWRWYWx1ZTsgaSsrKSB7XG4gICAgICAgIGNvbnN0IGVuZE1pbnV0ZXMgPSAoaSArIDEpICogc2xvdER1cmF0aW9uO1xuICAgICAgICBjb25zdCBzdGFydE1pbnV0ZXMgPSBpICogc2xvdER1cmF0aW9uO1xuICAgICAgICBpZiAoXG4gICAgICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSkudHoodGltZXpvbmUpLm1pbnV0ZShzdGFydE1pbnV0ZXMpLFxuICAgICAgICAgICAgICBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSkudHoodGltZXpvbmUpLm1pbnV0ZShlbmRNaW51dGVzKSxcbiAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgIClcbiAgICAgICAgKSB7XG4gICAgICAgICAgbWludXRlVmFsdWVBc1JlY2VpdmVyID0gZW5kTWludXRlcztcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cblxuICAgIGlmIChcbiAgICAgIGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAubWludXRlKGZsb29yZWRWYWx1ZSAqIHNsb3REdXJhdGlvbiksXG4gICAgICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpLnR6KHRpbWV6b25lKS5taW51dGUoNTkpLFxuICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICdbKSdcbiAgICAgICAgKVxuICAgICkge1xuICAgICAgc3RhcnRIb3VyICs9IDE7XG4gICAgICBtaW51dGVWYWx1ZUFzUmVjZWl2ZXIgPSAwO1xuICAgIH1cblxuICAgIGNvbnN0IHN0YXJ0TWludXRlQXNSZWNlaXZlciA9IG1pbnV0ZVZhbHVlQXNSZWNlaXZlcjtcblxuICAgIC8vIGNvbnZlcnQgdG8gdXNlciB0aW1lem9uZSBzbyBldmVyeXRoaW5nIGlzIGxpbmtlZCB0byB1c2VyIHRpbWV6b25lXG5cbiAgICBjb25zdCBlbmRIb3VyID0gZW5kVGltZXM/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpPy5ob3VyID8/IDIwO1xuICAgIGNvbnN0IGVuZE1pbnV0ZSA9XG4gICAgICBlbmRUaW1lcz8uZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCk/Lm1pbnV0ZXMgPz8gMDtcblxuICAgIC8vIHZhbGlkYXRlIHZhbHVlcyBiZWZvcmUgY2FsY3VsYXRpbmdcbiAgICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2VzLnN0YXJ0VGltZXM7XG4gICAgY29uc3Qgd29ya1N0YXJ0SG91ciA9XG4gICAgICBzdGFydFRpbWVzPy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KT8uaG91ciB8fCA4O1xuICAgIGNvbnN0IHdvcmtTdGFydE1pbnV0ZSA9XG4gICAgICBzdGFydFRpbWVzPy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KT8ubWludXRlcyB8fCAwO1xuXG4gICAgaWYgKFxuICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmlzQWZ0ZXIoXG4gICAgICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAuaG91cihlbmRIb3VyKVxuICAgICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGUpXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIC8vIHJldHVybiBlbXB0eSBhcyBvdXRzaWRlIG9mIHdvcmsgdGltZVxuICAgICAgcmV0dXJuIFtdO1xuICAgIH1cblxuICAgIC8vIGNoYW5nZSB0byB3b3JrIHN0YXJ0IHRpbWUgYXMgaG9zdCBzdGFydCB0aW1lIGJlZm9yZSB3b3JrIHN0YXJ0IHRpbWVcbiAgICBpZiAoXG4gICAgICBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSlcbiAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAuaXNCZWZvcmUoXG4gICAgICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyKVxuICAgICAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGUpXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICAgIGhvdXJzOiB3b3JrU3RhcnRIb3VyLFxuICAgICAgICBtaW51dGVzOiB3b3JrU3RhcnRNaW51dGUsXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgICBob3VyczogZW5kSG91cixcbiAgICAgICAgbWludXRlczogZW5kTWludXRlLFxuICAgICAgfSk7XG4gICAgICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbik7XG4gICAgICBjb25zdCB0b3RhbE1pbnV0ZXMgPSB0b3RhbER1cmF0aW9uLmFzTWludXRlcygpO1xuXG4gICAgICBjb25zdCBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZTogQXZhaWxhYmxlU2xvdFR5cGVbXSA9IFtdO1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lLFxuICAgICAgICBlbmRUaW1lcyxcbiAgICAgICAgZGF5T2ZXZWVrSW50LFxuICAgICAgICBkYXlPZk1vbnRoLFxuICAgICAgICBzdGFydEhvdXIsXG4gICAgICAgIHN0YXJ0TWludXRlQXNSZWNlaXZlcixcbiAgICAgICAgZW5kSG91cixcbiAgICAgICAgZW5kTWludXRlLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgYHN0YXJ0RGF0ZSwgZW5kVGltZXMsIGRheU9mV2Vla0ludEJ5VXNlciwgZGF5T2ZNb250aCwgc3RhcnRIb3VyLCBzdGFydE1pbnV0ZSwgZW5kSG91ciwgZW5kTWludXRlIHRvdGFsTWludXRlcywgdGltZXpvbmUsIGluc2lkZSBmaXJzdERheSBpbnNpZGUgZ2VuZXJhdGVUaW1lc2xvdHNgXG4gICAgICApO1xuICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gc2xvdER1cmF0aW9uKSB7XG4gICAgICAgIGlmIChpID4gdG90YWxNaW51dGVzKSB7XG4gICAgICAgICAgY29udGludWU7XG4gICAgICAgIH1cblxuICAgICAgICBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZS5wdXNoKHtcbiAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgIHN0YXJ0RGF0ZTogZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyKVxuICAgICAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGUpXG4gICAgICAgICAgICAuYWRkKGksICdtaW51dGUnKVxuICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICAgIGVuZERhdGU6IGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgLmhvdXIod29ya1N0YXJ0SG91cilcbiAgICAgICAgICAgIC5taW51dGUod29ya1N0YXJ0TWludXRlKVxuICAgICAgICAgICAgLmFkZChpICsgc2xvdER1cmF0aW9uLCAnbWludXRlJylcbiAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgfSk7XG4gICAgICB9XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUsXG4gICAgICAgICcgdGltZVNsb3RzIGluc2lkZSBnZW5lcmF0ZVRpbWVTbG90cyBmb3IgZmlyc3QgZGF5IHdoZXJlIHN0YXJ0RGF0ZSBpcyBiZWZvcmUgd29yayBzdGFydCB0aW1lJ1xuICAgICAgKTtcblxuICAgICAgLy8gZmlsdGVyIG91dCB1bmF2YWlsYWJsZSB0aW1lc1xuICAgICAgY29uc3QgZmlsdGVyZWRBdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZSA9XG4gICAgICAgIGF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lLmZpbHRlcigoYSkgPT4ge1xuICAgICAgICAgIGNvbnN0IGZvdW5kSW5kZXggPSBub3RBdmFpbGFibGVTbG90c0luRXZlbnRUaW1lem9uZT8uZmluZEluZGV4KFxuICAgICAgICAgICAgKG5hKSA9PiB7XG4gICAgICAgICAgICAgIGNvbnN0IHBhcnRBID0gZGF5anMoYS5lbmREYXRlKVxuICAgICAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLnNlY29uZCgwKS5hZGQoMSwgJ20nKSxcbiAgICAgICAgICAgICAgICAgIGRheWpzKG5hLmVuZERhdGUpLnR6KHRpbWV6b25lKS5zZWNvbmQoMCkuc3VidHJhY3QoMSwgJ20nKSxcbiAgICAgICAgICAgICAgICAgICdtJyxcbiAgICAgICAgICAgICAgICAgICdbXSdcbiAgICAgICAgICAgICAgICApO1xuXG4gICAgICAgICAgICAgIGNvbnN0IHBhcnRCID0gZGF5anMoYS5zdGFydERhdGUpXG4gICAgICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKS50eih0aW1lem9uZSkuc2Vjb25kKDApLmFkZCgxLCAnbScpLFxuICAgICAgICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSkudHoodGltZXpvbmUpLnNlY29uZCgwKS5zdWJ0cmFjdCgxLCAnbScpLFxuICAgICAgICAgICAgICAgICAgJ20nLFxuICAgICAgICAgICAgICAgICAgJ1tdJ1xuICAgICAgICAgICAgICAgICk7XG5cbiAgICAgICAgICAgICAgY29uc3QgcGFydEMgPVxuICAgICAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSA9PT1cbiAgICAgICAgICAgICAgICAgIGRheWpzKGEuc3RhcnREYXRlKVxuICAgICAgICAgICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpICYmXG4gICAgICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSA9PT1cbiAgICAgICAgICAgICAgICAgIGRheWpzKGEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKTtcblxuICAgICAgICAgICAgICBjb25zdCBpc05vdEF2YWlsYWJsZSA9IHBhcnRBIHx8IHBhcnRCIHx8IHBhcnRDO1xuXG4gICAgICAgICAgICAgIC8vIGNvbnNvbGUubG9nKGEsIG5hLCAnIGEsIG5hJylcbiAgICAgICAgICAgICAgcmV0dXJuIGlzTm90QXZhaWxhYmxlO1xuICAgICAgICAgICAgfVxuICAgICAgICAgICk7XG5cbiAgICAgICAgICBjb25zb2xlLmxvZyhmb3VuZEluZGV4LCAnIGZvdW5kSW5kZXgnKTtcblxuICAgICAgICAgIGlmIChmb3VuZEluZGV4ICE9PSB1bmRlZmluZWQgJiYgZm91bmRJbmRleCA+IC0xKSB7XG4gICAgICAgICAgICByZXR1cm4gZmFsc2U7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgcmV0dXJuIHRydWU7XG4gICAgICAgIH0pO1xuXG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgZmlsdGVyZWRBdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZSxcbiAgICAgICAgJyBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzJ1xuICAgICAgKTtcblxuICAgICAgcmV0dXJuIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmU7XG4gICAgfVxuXG4gICAgY29uc3Qgc3RhcnREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgIGhvdXJzOiBzdGFydEhvdXIsXG4gICAgICBtaW51dGVzOiBzdGFydE1pbnV0ZSxcbiAgICB9KTtcbiAgICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHsgaG91cnM6IGVuZEhvdXIsIG1pbnV0ZXM6IGVuZE1pbnV0ZSB9KTtcbiAgICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbik7XG4gICAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcbiAgICBjb25zdCBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZTogQXZhaWxhYmxlU2xvdFR5cGVbXSA9IFtdO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUsXG4gICAgICBlbmRUaW1lcyxcbiAgICAgIGRheU9mV2Vla0ludCxcbiAgICAgIGVuZEhvdXIsXG4gICAgICBlbmRNaW51dGUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIGBzdGFydERhdGUsIGVuZFRpbWVzLCBkYXlPZldlZWtJbnQsIGRheU9mTW9udGgsIHN0YXJ0SG91ciwgc3RhcnRNaW51dGUsIGVuZEhvdXIsIGVuZE1pbnV0ZSB0b3RhbE1pbnV0ZXMsIHRpbWV6b25lLCBpbnNpZGUgZmlyc3REYXkgaW5zaWRlIGdlbmVyYXRlVGltZXNsb3RzYFxuICAgICk7XG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gc2xvdER1cmF0aW9uKSB7XG4gICAgICBpZiAoaSA+IHRvdGFsTWludXRlcykge1xuICAgICAgICBjb250aW51ZTtcbiAgICAgIH1cbiAgICAgIGF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lLnB1c2goe1xuICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICBzdGFydERhdGU6IGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAuaG91cihzdGFydEhvdXIpXG4gICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUFzUmVjZWl2ZXIpXG4gICAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICBlbmREYXRlOiBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSlcbiAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyKVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVBc1JlY2VpdmVyKVxuICAgICAgICAgIC5hZGQoaSArIHNsb3REdXJhdGlvbiwgJ21pbnV0ZScpXG4gICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgIH0pO1xuICAgIH1cbiAgICBjb25zdCBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lID1cbiAgICAgIGF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lLmZpbHRlcigoYSkgPT4ge1xuICAgICAgICBjb25zdCBmb3VuZEluZGV4ID0gbm90QXZhaWxhYmxlU2xvdHNJbkV2ZW50VGltZXpvbmU/LmZpbmRJbmRleCgobmEpID0+IHtcbiAgICAgICAgICBjb25zdCBwYXJ0QSA9IGRheWpzKGEuZW5kRGF0ZSlcbiAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLnNlY29uZCgwKS5hZGQoMSwgJ20nKSxcbiAgICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSkudHoodGltZXpvbmUpLnNlY29uZCgwKS5zdWJ0cmFjdCgxLCAnbScpLFxuICAgICAgICAgICAgICAnbScsXG4gICAgICAgICAgICAgICdbXSdcbiAgICAgICAgICAgICk7XG5cbiAgICAgICAgICBjb25zdCBwYXJ0QiA9IGRheWpzKGEuc3RhcnREYXRlKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKS50eih0aW1lem9uZSkuc2Vjb25kKDApLmFkZCgxLCAnbScpLFxuICAgICAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKS50eih0aW1lem9uZSkuc2Vjb25kKDApLnN1YnRyYWN0KDEsICdtJyksXG4gICAgICAgICAgICAgICdtJyxcbiAgICAgICAgICAgICAgJ1tdJ1xuICAgICAgICAgICAgKTtcblxuICAgICAgICAgIGNvbnN0IHBhcnRDID1cbiAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSA9PT1cbiAgICAgICAgICAgICAgZGF5anMoYS5zdGFydERhdGUpXG4gICAgICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgJiZcbiAgICAgICAgICAgIGRheWpzKG5hLmVuZERhdGUpXG4gICAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgPT09XG4gICAgICAgICAgICAgIGRheWpzKGEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKTtcblxuICAgICAgICAgIGNvbnN0IGlzTm90QXZhaWxhYmxlID0gcGFydEEgfHwgcGFydEIgfHwgcGFydEM7XG5cbiAgICAgICAgICAvLyBjb25zb2xlLmxvZyhhLCBuYSwgJyBhLCBuYScpXG5cbiAgICAgICAgICByZXR1cm4gaXNOb3RBdmFpbGFibGU7XG4gICAgICAgIH0pO1xuXG4gICAgICAgIGNvbnNvbGUubG9nKGZvdW5kSW5kZXgsICcgZm91bmRJbmRleCcpO1xuXG4gICAgICAgIGlmIChmb3VuZEluZGV4ICE9PSB1bmRlZmluZWQgJiYgZm91bmRJbmRleCA+IC0xKSB7XG4gICAgICAgICAgcmV0dXJuIGZhbHNlO1xuICAgICAgICB9XG5cbiAgICAgICAgcmV0dXJuIHRydWU7XG4gICAgICB9KTtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZmlsdGVyZWRBdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZSxcbiAgICAgICcgZmlsdGVyZWRBdmFpbGFibGVTbG90cyBzZXJ2ZXIgdGltZXpvbmUnXG4gICAgKTtcbiAgICByZXR1cm4gZmlsdGVyZWRBdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZTtcbiAgfVxuXG4gIC8vIG5vdCBmaXJzdCBkYXkgc3RhcnQgZnJvbSB3b3JrIHN0YXJ0IHRpbWUgc2NoZWR1bGVcblxuICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2VzLnN0YXJ0VGltZXM7XG5cbiAgY29uc3QgZW5kVGltZXMgPSB1c2VyUHJlZmVyZW5jZXMuZW5kVGltZXM7XG5cbiAgY29uc3QgZGF5T2ZXZWVrSW50ID0gZ2V0SVNPRGF5KFxuICAgIGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKS50eih0aW1lem9uZSkudG9EYXRlKClcbiAgKTtcbiAgY29uc3QgZGF5T2ZNb250aCA9IGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKS50eih0aW1lem9uZSkuZGF0ZSgpO1xuXG4gIC8vIGNvbnZlcnQgdG8gdXNlciB0aW1lem9uZSBzbyBldmVyeXRoaW5nIGlzIGxpbmtlZCB0byB1c2VyIHRpbWV6b25lXG4gIGxldCBlbmRIb3VyID0gZW5kVGltZXM/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpPy5ob3VyID8/IDIwO1xuICBsZXQgZW5kTWludXRlID0gZW5kVGltZXM/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpPy5taW51dGVzID8/IDA7XG5cbiAgLy8gaWYgbGFzdCBkYXkgY2hhbmdlIGVuZCB0aW1lIHRvIGhvc3RTdGFydERhdGUgcHJvdmlkZWRcbiAgaWYgKGlzTGFzdERheSAmJiBlbmREYXRlSW5Vc2VyVGltZXpvbmUpIHtcbiAgICBlbmRIb3VyID0gZGF5anMoZW5kRGF0ZUluVXNlclRpbWV6b25lKS50eih0aW1lem9uZSkuaG91cigpO1xuICAgIC8vIGNyZWF0ZSBzbG90IHNpemVzXG4gICAgY29uc3QgZmxvb3JlZFZhbHVlID0gTWF0aC5mbG9vcig2MCAvIHNsb3REdXJhdGlvbik7XG5cbiAgICBsZXQgbWludXRlVmFsdWVCeVNlbmRlciA9IDA7XG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCBmbG9vcmVkVmFsdWU7IGkrKykge1xuICAgICAgY29uc3QgZW5kTWludXRlcyA9IChpICsgMSkgKiBzbG90RHVyYXRpb247XG4gICAgICBjb25zdCBzdGFydE1pbnV0ZXMgPSBpICogc2xvdER1cmF0aW9uO1xuICAgICAgaWYgKFxuICAgICAgICBkYXlqcyhlbmREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICBkYXlqcyhlbmREYXRlSW5Vc2VyVGltZXpvbmUpLnR6KHRpbWV6b25lKS5taW51dGUoc3RhcnRNaW51dGVzKSxcbiAgICAgICAgICAgIGRheWpzKGVuZERhdGVJblVzZXJUaW1lem9uZSkudHoodGltZXpvbmUpLm1pbnV0ZShlbmRNaW51dGVzKSxcbiAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgIClcbiAgICAgICkge1xuICAgICAgICBtaW51dGVWYWx1ZUJ5U2VuZGVyID0gc3RhcnRNaW51dGVzO1xuICAgICAgfVxuICAgIH1cblxuICAgIGVuZE1pbnV0ZSA9IG1pbnV0ZVZhbHVlQnlTZW5kZXI7XG4gIH1cblxuICBjb25zdCBzdGFydEhvdXJCeVNlbmRlciA9XG4gICAgKHN0YXJ0VGltZXM/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpPy5ob3VyIGFzIG51bWJlcikgfHwgODtcbiAgY29uc3Qgc3RhcnRNaW51dGVCeVNlbmRlciA9XG4gICAgKHN0YXJ0VGltZXM/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpPy5taW51dGVzIGFzIG51bWJlcikgfHwgMDtcblxuICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgIGhvdXJzOiBzdGFydEhvdXJCeVNlbmRlcixcbiAgICBtaW51dGVzOiBzdGFydE1pbnV0ZUJ5U2VuZGVyLFxuICB9KTtcbiAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7IGhvdXJzOiBlbmRIb3VyLCBtaW51dGVzOiBlbmRNaW51dGUgfSk7XG4gIGNvbnN0IHRvdGFsRHVyYXRpb24gPSBlbmREdXJhdGlvbi5zdWJ0cmFjdChzdGFydER1cmF0aW9uKTtcbiAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcblxuICBjb25zdCBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZTogQXZhaWxhYmxlU2xvdFR5cGVbXSA9IFtdO1xuICBjb25zb2xlLmxvZyhcbiAgICBzdGFydERhdGVJblVzZXJUaW1lem9uZSxcbiAgICBlbmRUaW1lcyxcbiAgICBkYXlPZldlZWtJbnQsXG4gICAgZGF5T2ZNb250aCxcbiAgICBzdGFydEhvdXJCeVNlbmRlcixcbiAgICBzdGFydE1pbnV0ZUJ5U2VuZGVyLFxuICAgIGVuZEhvdXIsXG4gICAgZW5kTWludXRlLFxuICAgIHRpbWV6b25lLFxuICAgIGBzdGFydERhdGUsIGVuZFRpbWVzLCBkYXlPZldlZWtJbnRCeUhvc3QsIGRheU9mTW9udGgsIHN0YXJ0SG91ciwgc3RhcnRNaW51dGUsIGVuZEhvdXIsIGVuZE1pbnV0ZSB0b3RhbE1pbnV0ZXMsIHRpbWV6b25lLCBpbnNpZGUgZmlyc3REYXkgaW5zaWRlIGdlbmVyYXRlQXZhaWxhYmxlc2xvdHNgXG4gICk7XG4gIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IHNsb3REdXJhdGlvbikge1xuICAgIGlmIChpID4gdG90YWxNaW51dGVzKSB7XG4gICAgICBjb250aW51ZTtcbiAgICB9XG5cbiAgICBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZS5wdXNoKHtcbiAgICAgIGlkOiB1dWlkKCksXG4gICAgICBzdGFydERhdGU6IGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5U2VuZGVyKVxuICAgICAgICAubWludXRlKHN0YXJ0TWludXRlQnlTZW5kZXIpXG4gICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgZW5kRGF0ZTogZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlTZW5kZXIpXG4gICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeVNlbmRlcilcbiAgICAgICAgLmFkZChpICsgc2xvdER1cmF0aW9uLCAnbWludXRlJylcbiAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAuZm9ybWF0KCksXG4gICAgfSk7XG4gIH1cblxuICBjb25zb2xlLmxvZyhcbiAgICBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZSxcbiAgICAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMgbm90IGZpcnN0IGRheSdcbiAgKTtcbiAgY29uc29sZS5sb2coXG4gICAgbm90QXZhaWxhYmxlU2xvdHNJbkV2ZW50VGltZXpvbmUsXG4gICAgJyBub3RBdmFpbGFibGVTbG90c0luRXZlbnRUaW1lem9uZSBub3QgZmlyc3QgZGF5J1xuICApO1xuXG4gIC8vIGZpbHRlciBvdXQgdW5hdmFpbGFibGUgdGltZXNcbiAgY29uc3QgZmlsdGVyZWRBdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZSA9XG4gICAgYXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUuZmlsdGVyKChhKSA9PiB7XG4gICAgICBjb25zdCBmb3VuZEluZGV4ID0gbm90QXZhaWxhYmxlU2xvdHNJbkV2ZW50VGltZXpvbmU/LmZpbmRJbmRleCgobmEpID0+IHtcbiAgICAgICAgY29uc3QgcGFydEEgPSBkYXlqcyhhLmVuZERhdGUpXG4gICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKS50eih0aW1lem9uZSkuc2Vjb25kKDApLmFkZCgxLCAnbScpLFxuICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSkudHoodGltZXpvbmUpLnNlY29uZCgwKS5zdWJ0cmFjdCgxLCAnbScpLFxuICAgICAgICAgICAgJ20nLFxuICAgICAgICAgICAgJ1tdJ1xuICAgICAgICAgICk7XG5cbiAgICAgICAgY29uc3QgcGFydEIgPSBkYXlqcyhhLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpLnR6KHRpbWV6b25lKS5zZWNvbmQoMCkuYWRkKDEsICdtJyksXG4gICAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKS50eih0aW1lem9uZSkuc2Vjb25kKDApLnN1YnRyYWN0KDEsICdtJyksXG4gICAgICAgICAgICAnbScsXG4gICAgICAgICAgICAnW10nXG4gICAgICAgICAgKTtcblxuICAgICAgICBjb25zdCBwYXJ0QyA9XG4gICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpID09PVxuICAgICAgICAgICAgZGF5anMoYS5zdGFydERhdGUpXG4gICAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgJiZcbiAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpID09PVxuICAgICAgICAgICAgZGF5anMoYS5lbmREYXRlKS50eih0aW1lem9uZSkuc2Vjb25kKDApLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpO1xuXG4gICAgICAgIGNvbnN0IGlzTm90QXZhaWxhYmxlID0gcGFydEEgfHwgcGFydEIgfHwgcGFydEM7XG5cbiAgICAgICAgLy8gY29uc29sZS5sb2coYSwgbmEsICcgYSwgbmEnKVxuXG4gICAgICAgIHJldHVybiBpc05vdEF2YWlsYWJsZTtcbiAgICAgIH0pO1xuXG4gICAgICBjb25zb2xlLmxvZyhmb3VuZEluZGV4LCAnIGZvdW5kSW5kZXgnKTtcblxuICAgICAgaWYgKGZvdW5kSW5kZXggIT09IHVuZGVmaW5lZCAmJiBmb3VuZEluZGV4ID4gLTEpIHtcbiAgICAgICAgcmV0dXJuIGZhbHNlO1xuICAgICAgfVxuXG4gICAgICByZXR1cm4gdHJ1ZTtcbiAgICB9KTtcblxuICBjb25zb2xlLmxvZyhcbiAgICBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lLFxuICAgICcgZmlsdGVyZWRBdmFpbGFibGVTbG90cyBpbiByZWNlaXZlclRpbWV6b25lJ1xuICApO1xuICAvLyBjb252ZXJ0IHRvIHJlY2VpdmVyVGltZXpvbmUgYmVmb3JlIHJldHVybmluZyB2YWx1ZXNcbiAgcmV0dXJuIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmU7XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVBdmFpbGFibGVTbG90c2ZvclRpbWVXaW5kb3dGb3JVc2VyID0gKFxuICB3aW5kb3dTdGFydERhdGU6IHN0cmluZyxcbiAgd2luZG93RW5kRGF0ZTogc3RyaW5nLFxuICBzbG90RHVyYXRpb246IG51bWJlcixcbiAgdXNlclByZWZlcmVuY2VzOiBVc2VyUHJlZmVyZW5jZVR5cGUsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIG5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lPzogTm90QXZhaWxhYmxlU2xvdFR5cGVbXVxuKSA9PiB7XG4gIGNvbnN0IGRpZmZEYXlzID0gZGF5anMod2luZG93RW5kRGF0ZSkuZGlmZihkYXlqcyh3aW5kb3dTdGFydERhdGUpLCAnZCcpO1xuXG4gIGNvbnN0IHN0YXJ0RGF0ZXNGb3JFYWNoRGF5ID0gW107XG4gIGNvbnN0IGF2YWlsYWJsZVNsb3RzOiBBdmFpbGFibGVTbG90VHlwZVtdID0gW107XG5cbiAgZm9yIChsZXQgaSA9IDA7IGkgPD0gZGlmZkRheXM7IGkrKykge1xuICAgIHN0YXJ0RGF0ZXNGb3JFYWNoRGF5LnB1c2goXG4gICAgICBkYXlqcyh3aW5kb3dTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoodGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5hZGQoaSwgJ2RheScpXG4gICAgICAgIC5mb3JtYXQoKVxuICAgICk7XG4gIH1cblxuICBpZiAoZGlmZkRheXMgPCAxKSB7XG4gICAgY29uc3QgZ2VuZXJhdGVkU2xvdHMgPSBnZW5lcmF0ZUF2YWlsYWJsZVNsb3RzRm9yRGF0ZUZvclVzZXIoXG4gICAgICBzbG90RHVyYXRpb24sXG4gICAgICBkYXlqcyh3aW5kb3dTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSkuZm9ybWF0KCksXG4gICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIG5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lLFxuICAgICAgdHJ1ZSxcbiAgICAgIHRydWUsXG4gICAgICBkYXlqcyh3aW5kb3dFbmREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLmZvcm1hdCgpXG4gICAgKTtcbiAgICAvLyAgMDEyMzQ1Njc4OVxuICAgIC8vICAyMDIwLTA0LTAyVDA4OjAyOjE3LTA1OjAwXG4gICAgYXZhaWxhYmxlU2xvdHMucHVzaCguLi5nZW5lcmF0ZWRTbG90cyk7XG4gIH0gZWxzZSB7XG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCBzdGFydERhdGVzRm9yRWFjaERheS5sZW5ndGg7IGkrKykge1xuICAgICAgY29uc3QgZmlsdGVyZWROb3RBdmFpbGFibGVTbG90c0luRXZlbnRUaW1lem9uZSA9XG4gICAgICAgIG5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lPy5maWx0ZXIoXG4gICAgICAgICAgKG5hKSA9PlxuICAgICAgICAgICAgZGF5anMobmE/LnN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpID09PVxuICAgICAgICAgICAgZGF5anMoc3RhcnREYXRlc0ZvckVhY2hEYXk/LltpXSkudHoodGltZXpvbmUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpXG4gICAgICAgICk7XG4gICAgICBpZiAoaSA9PT0gMCkge1xuICAgICAgICBjb25zdCBnZW5lcmF0ZWRTbG90cyA9IGdlbmVyYXRlQXZhaWxhYmxlU2xvdHNGb3JEYXRlRm9yVXNlcihcbiAgICAgICAgICBzbG90RHVyYXRpb24sXG4gICAgICAgICAgc3RhcnREYXRlc0ZvckVhY2hEYXk/LltpXSxcbiAgICAgICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgZmlsdGVyZWROb3RBdmFpbGFibGVTbG90c0luRXZlbnRUaW1lem9uZSxcbiAgICAgICAgICB0cnVlLFxuICAgICAgICAgIGZhbHNlLFxuICAgICAgICAgIGRheWpzKHdpbmRvd0VuZERhdGUuc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSkuZm9ybWF0KClcbiAgICAgICAgKTtcbiAgICAgICAgLy8gIDAxMjM0NTY3ODlcbiAgICAgICAgLy8gIDIwMjAtMDQtMDJUMDg6MDI6MTctMDU6MDBcbiAgICAgICAgYXZhaWxhYmxlU2xvdHMucHVzaCguLi5nZW5lcmF0ZWRTbG90cyk7XG5cbiAgICAgICAgY29udGludWU7XG4gICAgICB9XG5cbiAgICAgIGlmIChpID09PSBzdGFydERhdGVzRm9yRWFjaERheS5sZW5ndGggLSAxKSB7XG4gICAgICAgIGNvbnN0IGdlbmVyYXRlZFNsb3RzID0gZ2VuZXJhdGVBdmFpbGFibGVTbG90c0ZvckRhdGVGb3JVc2VyKFxuICAgICAgICAgIHNsb3REdXJhdGlvbixcbiAgICAgICAgICBzdGFydERhdGVzRm9yRWFjaERheT8uW2ldLFxuICAgICAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICBmaWx0ZXJlZE5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lLFxuICAgICAgICAgIGZhbHNlLFxuICAgICAgICAgIHRydWUsXG4gICAgICAgICAgZGF5anMod2luZG93RW5kRGF0ZS5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoKVxuICAgICAgICApO1xuXG4gICAgICAgIGF2YWlsYWJsZVNsb3RzLnB1c2goLi4uZ2VuZXJhdGVkU2xvdHMpO1xuXG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfVxuXG4gICAgICBjb25zdCBnZW5lcmF0ZWRTbG90cyA9IGdlbmVyYXRlQXZhaWxhYmxlU2xvdHNGb3JEYXRlRm9yVXNlcihcbiAgICAgICAgc2xvdER1cmF0aW9uLFxuICAgICAgICBzdGFydERhdGVzRm9yRWFjaERheT8uW2ldLFxuICAgICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBmaWx0ZXJlZE5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lXG4gICAgICApO1xuXG4gICAgICBhdmFpbGFibGVTbG90cy5wdXNoKC4uLmdlbmVyYXRlZFNsb3RzKTtcbiAgICB9XG4gIH1cblxuICByZXR1cm4geyBhdmFpbGFibGVTbG90cyB9O1xufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlQXZhaWxhYmlsaXR5Rm9yVXNlciA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHdpbmRvd1N0YXJ0RGF0ZTogc3RyaW5nLFxuICB3aW5kb3dFbmREYXRlOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIHNsb3REdXJhdGlvbjogbnVtYmVyXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvbGRFdmVudHNJbkV2ZW50VGltZXpvbmUgPSBhd2FpdCBsaXN0RXZlbnRzRm9yVXNlckdpdmVuRGF0ZXMoXG4gICAgICB1c2VySWQsXG4gICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICB3aW5kb3dFbmREYXRlXG4gICAgKTtcblxuICAgIGNvbnNvbGUubG9nKG9sZEV2ZW50c0luRXZlbnRUaW1lem9uZSwgJyBvbGRFdmVudHNJbkV2ZW50VGltZXpvbmUnKTtcblxuICAgIGlmICghb2xkRXZlbnRzSW5FdmVudFRpbWV6b25lIHx8ICEob2xkRXZlbnRzSW5FdmVudFRpbWV6b25lPy5sZW5ndGggPiAwKSkge1xuICAgICAgY29uc29sZS5sb2coJ25vIG9sZCBldmVudHMgaW4gZ2VuZXJhdGVBdmFpbGFiaWxpdHknKTtcbiAgICB9XG5cbiAgICBjb25zdCBvbGRFdmVudHNJbkV2ZW50VGltZXpvbmVGb3JtYXR0ZWQgPSBvbGRFdmVudHNJbkV2ZW50VGltZXpvbmU/Lm1hcChcbiAgICAgIChlKSA9PiAoe1xuICAgICAgICAuLi5lLFxuICAgICAgICBzdGFydERhdGU6IGRheWpzKGU/LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGU/LnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgZW5kRGF0ZTogZGF5anMoZT8uZW5kRGF0ZS5zbGljZSgwLCAxOSkpLnR6KGU/LnRpbWV6b25lLCB0cnVlKS5mb3JtYXQoKSxcbiAgICAgICAgdGltZXpvbmU6IGU/LnRpbWV6b25lLFxuICAgICAgfSlcbiAgICApO1xuXG4gICAgY29uc3Qgbm90QXZhaWxhYmxlRnJvbUV2ZW50czogTm90QXZhaWxhYmxlU2xvdFR5cGVbXSA9XG4gICAgICBvbGRFdmVudHNJbkV2ZW50VGltZXpvbmVGb3JtYXR0ZWQ/Lm1hcCgoZSkgPT4gKHtcbiAgICAgICAgc3RhcnREYXRlOiBlPy5zdGFydERhdGUsXG4gICAgICAgIGVuZERhdGU6IGU/LmVuZERhdGUsXG4gICAgICB9KSk7XG5cbiAgICBjb25zdCB1c2VyUHJlZmVyZW5jZXMgPSBhd2FpdCBnZXRVc2VyUHJlZmVyZW5jZXModXNlcklkKTtcblxuICAgIGNvbnN0IHsgYXZhaWxhYmxlU2xvdHM6IGF2YWlsYWJsZVNsb3RzIH0gPVxuICAgICAgYXdhaXQgZ2VuZXJhdGVBdmFpbGFibGVTbG90c2ZvclRpbWVXaW5kb3dGb3JVc2VyKFxuICAgICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICAgIHNsb3REdXJhdGlvbixcbiAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgbm90QXZhaWxhYmxlRnJvbUV2ZW50cz8ubGVuZ3RoID4gMCA/IG5vdEF2YWlsYWJsZUZyb21FdmVudHMgOiB1bmRlZmluZWRcbiAgICAgICk7XG5cbiAgICByZXR1cm4gYXZhaWxhYmxlU2xvdHM7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZW5lcmF0ZSBhdmFpbGFiaWxpdHknKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHByb2Nlc3NBdmFpbGFiaWxpdHkgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBkYXRlVGltZUpTT05Cb2R5OiBEYXRlVGltZUpTT05UeXBlLFxuICBxdWVyeURhdGVKU09OQm9keTogUXVlcnlDYWxlbmRhckV4dHJhY3RlZEpTT05UeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nXG4pOiBQcm9taXNlPFJlc3BvbnNlQWN0aW9uVHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHdpbmRvd1N0YXJ0RGF0ZSA9IGV4dHJhcG9sYXRlU3RhcnREYXRlRnJvbUpTT05EYXRhKFxuICAgICAgY3VycmVudFRpbWUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy55ZWFyLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/Lm1vbnRoLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/LmRheSxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy5ob3VyLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/Lm1pbnV0ZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy50aW1lLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uc3RhcnRfZGF0ZT8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICk7XG5cbiAgICBjb25zdCB3aW5kb3dFbmREYXRlID0gZXh0cmFwb2xhdGVFbmREYXRlRnJvbUpTT05EYXRhKFxuICAgICAgY3VycmVudFRpbWUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8ueWVhcixcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8ubW9udGgsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/LmRheSxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8uaG91cixcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8ubWludXRlLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LmVuZF9kYXRlPy50aW1lLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LmVuZF9kYXRlPy5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93LFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LmVuZF9kYXRlPy5yZWxhdGl2ZVRpbWVGcm9tTm93XG4gICAgKTtcblxuICAgIC8vIGdldCBkZWZhdWx0IHZhbHVlc1xuICAgIC8vIGNvbnN0IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXMgPSBhd2FpdCBnZXRDaGF0TWVldGluZ1ByZWZlcmVuY2VHaXZlblVzZXJJZCh1c2VySWQpXG5cbiAgICBjb25zdCBib2R5OiBVc2VyQXZhaWxhYmlsaXR5Qm9keVR5cGUgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICB3aW5kb3dTdGFydERhdGU6IHdpbmRvd1N0YXJ0RGF0ZSB8fCBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgd2luZG93RW5kRGF0ZTogd2luZG93RW5kRGF0ZSB8fCBkYXlqcygpLmFkZCgyLCAndycpLmZvcm1hdCgpLFxuICAgICAgdGltZXpvbmUsXG4gICAgICBzbG90RHVyYXRpb246IGRhdGVUaW1lSlNPTkJvZHk/LmR1cmF0aW9uIHx8IDMwLFxuICAgIH07XG5cbiAgICBjb25zb2xlLmxvZyhib2R5LCAnIGJvZHkgaW5zaWRlIHByb2Nlc3NBdmFpbGFiaWxpdHknKTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiBhbnkgPSB7XG4gICAgICBxdWVyeTogJycsXG4gICAgICBkYXRhOiB7fSxcbiAgICAgIHNraWxsOiAncXVlcnlBdmFpbGFiaWxpdHknLFxuICAgIH07XG5cbiAgICBjb25zdCBhdmFpbGFibGVTbG90cyA9IGF3YWl0IGdlbmVyYXRlQXZhaWxhYmlsaXR5Rm9yVXNlcihcbiAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgIGJvZHk/LndpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIGJvZHk/LndpbmRvd0VuZERhdGUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIGJvZHk/LnNsb3REdXJhdGlvblxuICAgICk7XG5cbiAgICByZXNwb25zZS5xdWVyeSA9ICdjb21wbGV0ZWQnO1xuXG4gICAgaWYgKCEoYXZhaWxhYmxlU2xvdHM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICByZXNwb25zZS5kYXRhID0gJ25vIGZyZWUgdGltZSBzbG90cyBhdmFpbGFibGUnO1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIGNvbnN0IG9wZW5haSA9IG5ldyBPcGVuQUkoe1xuICAgICAgYXBpS2V5OiBkZWZhdWx0T3BlbkFJQVBJS2V5LFxuICAgIH0pO1xuXG4gICAgY29uc3QgdW5pcURhdGVzID0gXy51bmlxQnkoYXZhaWxhYmxlU2xvdHMsIChjdXJyKSA9PlxuICAgICAgZGF5anMoY3Vycj8uc3RhcnREYXRlPy5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lKS5mb3JtYXQoJ1lZWVktTU0tREQnKVxuICAgICk7XG5cbiAgICAvLyBsZXQgYXZhaWxhYmlsaXR5VGV4dCA9ICcnXG5cbiAgICBjb25zdCBwcm9tcHQgPSBzdW1tYXJpemVBdmFpbGFiaWxpdHlQcm9tcHQ7XG5cbiAgICBjb25zdCBleGFtcGxlSW5wdXQgPSBzdW1tYXJpemVBdmFpbGFiaWxpdHlFeGFtcGxlSW5wdXQ7XG5cbiAgICBjb25zdCBleGFtcGxlT3V0cHV0ID0gc3VtbWFyaXplQXZhaWxhYmlsaXR5RXhhbXBsZU91dHB1dDtcblxuICAgIGxldCBvcGVuQUlBdmFpbGFiaWxpdHlSZXMgPSAnJztcblxuICAgIGZvciAoY29uc3QgdW5pcURhdGUgb2YgdW5pcURhdGVzKSB7XG4gICAgICBjb25zdCBmaWx0ZXJlZEF2YWlsYWJpbGl0eSA9IGF2YWlsYWJsZVNsb3RzPy5maWx0ZXIoXG4gICAgICAgIChhKSA9PlxuICAgICAgICAgIGRheWpzKGE/LnN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpID09PVxuICAgICAgICAgIGRheWpzKHVuaXFEYXRlPy5zdGFydERhdGUpLnR6KHRpbWV6b25lKS5mb3JtYXQoJ1lZWVktTU0tREQnKVxuICAgICAgKTtcblxuICAgICAgaWYgKGZpbHRlcmVkQXZhaWxhYmlsaXR5Py5sZW5ndGggPiAwKSB7XG4gICAgICAgIC8vIGF2YWlsYWJpbGl0eVRleHQgKz0gYCR7ZGF5anModW5pcURhdGU/LnN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgnTCcpfSAtICR7ZmlsdGVyZWRBdmFpbGFiaWxpdHk/Lm1hcCgoY3VycikgPT4gKGAke2RheWpzKGN1cnI/LnN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgnTFQnKX0gLSAke2RheWpzKGN1cnI/LmVuZERhdGUpLnR6KHRpbWV6b25lKS5mb3JtYXQoJ0xUJyl9LGApKT8ucmVkdWNlKChwcmV2LCBjdXJyKSA9PiAoYCR7cHJldn0gJHtjdXJyfWApLCAnJyl9YCArICdcXG5cXG4nXG5cbiAgICAgICAgY29uc3QgbWluaUF2YWlsYWJpbGl0eVRleHQgPVxuICAgICAgICAgIGAke2RheWpzKHVuaXFEYXRlPy5zdGFydERhdGUpLnR6KHRpbWV6b25lKS5mb3JtYXQoJ0wnKX0gLSAke2ZpbHRlcmVkQXZhaWxhYmlsaXR5Py5tYXAoKGN1cnIpID0+IGAke2RheWpzKGN1cnI/LnN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgnTFQnKX0gLSAke2RheWpzKGN1cnI/LmVuZERhdGUpLnR6KHRpbWV6b25lKS5mb3JtYXQoJ0xUJyl9LGApPy5yZWR1Y2UoKHByZXYsIGN1cnIpID0+IGAke3ByZXZ9ICR7Y3Vycn1gLCAnJyl9YCArXG4gICAgICAgICAgJ1xcblxcbic7XG5cbiAgICAgICAgY29uc3QgbWluaVVzZXJEYXRhID0gYE15IGF2YWlsYWJpbGl0eTogYCArIG1pbmlBdmFpbGFiaWxpdHlUZXh0O1xuXG4gICAgICAgIGNvbnNvbGUubG9nKG1pbmlVc2VyRGF0YSwgJyBuZXdBdmFpbGFiaWxpdHlQcm9tcHQnKTtcblxuICAgICAgICBjb25zdCBtaW5pT3BlbkFJQXZhaWxhYmlsaXR5UmVzID0gYXdhaXQgY2FsbE9wZW5BSShcbiAgICAgICAgICBvcGVuYWksXG4gICAgICAgICAgcHJvbXB0LFxuICAgICAgICAgIG9wZW5BSUNoYXRHUFQzNUxvbmdNb2RlbCxcbiAgICAgICAgICBtaW5pVXNlckRhdGEsXG4gICAgICAgICAgZXhhbXBsZUlucHV0LFxuICAgICAgICAgIGV4YW1wbGVPdXRwdXRcbiAgICAgICAgKTtcblxuICAgICAgICAvLyB2YWxpZGF0ZSBvcGVuYWkgcmVzXG4gICAgICAgIGlmICghbWluaU9wZW5BSUF2YWlsYWJpbGl0eVJlcykge1xuICAgICAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgICAgICdubyBvcGVuQUlBdmFpbGFiaWxpdHlSZXMgcHJlc2VudCBpbnNpZGUgYXBwb2ludG1lbnRSZXF1ZXN0J1xuICAgICAgICAgICk7XG4gICAgICAgIH1cblxuICAgICAgICBvcGVuQUlBdmFpbGFiaWxpdHlSZXMgKz0gJ1xcbicgKyBtaW5pT3BlbkFJQXZhaWxhYmlsaXR5UmVzO1xuICAgICAgfVxuICAgIH1cblxuICAgIC8vIGNvbnN0IGF2YWlsYWJpbGl0eUZpbmFsU3VtbWFyeVVzZXJEYXRhID0gb3BlbkFJQXZhaWxhYmlsaXR5UmVzXG5cbiAgICAvLyBsZXQgZmluYWxPcGVuQUlBdmFpbGFiaWxpdHlTdW1tYXJ5UmVzcG9uc2UgPSAnJ1xuXG4gICAgLy8gaWYgKGF2YWlsYWJpbGl0eUZpbmFsU3VtbWFyeVVzZXJEYXRhKSB7XG4gICAgLy8gICAgIGZpbmFsT3BlbkFJQXZhaWxhYmlsaXR5U3VtbWFyeVJlc3BvbnNlID0gYXdhaXQgY2FsbE9wZW5BSShvcGVuYWksIHN1bW1hcml6ZUF2YWlsYWJpbGl0eVJlc3BvbnNlc1Byb21wdCwgb3BlbkFJQ2hhdEdQVDM1TG9uZ01vZGVsLCBhdmFpbGFiaWxpdHlGaW5hbFN1bW1hcnlVc2VyRGF0YSwgc3VtbWFyaXplQXZhaWxhYmlsaXR5UmVzcG9uc2VzUHJvbXB0RXhhbXBsZUlucHV0LCBzdW1tYXJpemVBdmFpbGFiaWxpdHlSZXNwb25zZXNQcm9tcHRFeGFtcGxlT3V0cHV0KVxuICAgIC8vIH1cblxuICAgIHJlc3BvbnNlLmRhdGEgPSBvcGVuQUlBdmFpbGFiaWxpdHlSZXM7XG5cbiAgICByZXR1cm4gcmVzcG9uc2U7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVhbmJsZSB0byBwcm9jZXNzIGF2YWlsYWJpbGl0eScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgYXNrQXZhaWxhYmlsaXR5Q29udHJvbENlbnRlckZvclBlbmRpbmcgPSBhc3luYyAoXG4gIG9wZW5haTogT3BlbkFJLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAgbWVzc2FnZUhpc3RvcnlPYmplY3Q6IFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlLFxuICB1c2VyQ3VycmVudFRpbWU6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgbWVzc2FnZUxlbmd0aCA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzPy5sZW5ndGg7XG4gICAgbGV0IHVzZXJNZXNzYWdlID0gJyc7XG4gICAgZm9yIChsZXQgaSA9IG1lc3NhZ2VMZW5ndGg7IGkgPiAwOyBpLS0pIHtcbiAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlc1tpIC0gMV07XG5cbiAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICd1c2VyJykge1xuICAgICAgICB1c2VyTWVzc2FnZSA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgYnJlYWs7XG4gICAgICB9XG4gICAgfVxuICAgIGNvbnN0IHVzZXJJbnB1dCA9IHVzZXJNZXNzYWdlO1xuICAgIGNvbnN0IGRhdGVUaW1lID0gYXdhaXQgZ2VuZXJhdGVEYXRlVGltZShcbiAgICAgIHVzZXJJbnB1dCxcbiAgICAgIHVzZXJDdXJyZW50VGltZSxcbiAgICAgIHRpbWV6b25lXG4gICAgKTtcbiAgICBjb25zdCBxdWVyeURhdGUgPSBhd2FpdCBnZW5lcmF0ZVF1ZXJ5RGF0ZUZyb21Vc2VySW5wdXQoXG4gICAgICB1c2VySWQsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHVzZXJJbnB1dCxcbiAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICk7XG4gICAgY29uc3QgYXZhaWxhYmlsaXR5UmVzID0gYXdhaXQgcHJvY2Vzc0F2YWlsYWJpbGl0eShcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgZGF0ZVRpbWUsXG4gICAgICBxdWVyeURhdGUsXG4gICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICApO1xuICAgIGlmIChhdmFpbGFiaWxpdHlSZXM/LnF1ZXJ5ID09PSAnY29tcGxldGVkJykge1xuICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZSA9XG4gICAgICAgIGF3YWl0IGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZUZyb21BUElSZXNwb25zZUZvclVzZXJRdWVyeShcbiAgICAgICAgICBvcGVuYWksXG4gICAgICAgICAgYXZhaWxhYmlsaXR5UmVzLmRhdGEgYXMgc3RyaW5nLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdjb21wbGV0ZWQnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBudWxsO1xuICAgIH1cblxuICAgIHJldHVybiBtZXNzYWdlSGlzdG9yeU9iamVjdDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdWFuYmxlIHRvIGFzayBhdmFpbGFiaWxpdHkgY29udHJvbCBjZW50ZXInKTtcbiAgfVxufTtcbiJdfQ==