import { getUserPreferences } from '@features_apply/_libs/api-helper';
import { getISODay } from 'date-fns';
import { dayjs } from '@features_apply/_libs/date-utils';
import { v4 as uuid } from 'uuid';
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
export const generateAvailabilityForUser = async (eventParts, userId, windowStartDate, windowEndDate, timezone, slotDuration) => {
    try {
        console.log(eventParts, ' eventParts');
        if (!eventParts || !(eventParts?.length > 0)) {
            console.log('no old events in generateAvailability');
        }
        const notAvailableFromEvents = eventParts?.map((e) => ({
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
export const convertAvailableSlotsToTimeSlotLike = (availableSlots, timezone) => {
    // AvailableTimeSlotType
    // AvailableSlotType[]
    if (!(availableSlots?.length > 0)) {
        throw new Error('no available slots provided inside convertAvailableSlotsToTimeSlotLike');
    }
    const availableTimeSlots = [];
    for (const availableSlot of availableSlots) {
        const availableTimeSlot = {
            startTime: `${dayjs(availableSlot?.startDate).tz(timezone).format('HH:mm')}`,
            endTime: `${dayjs(availableSlot?.endDate).tz(timezone).format('HH:mm')}`,
            monthDay: `--${dayjs(availableSlot?.startDate).tz(timezone).format('MM-DD')}`,
        };
        availableTimeSlots.push(availableTimeSlot);
    }
    return availableTimeSlots;
};
export const filterTimeslotsGivenImmodifiableEvents = async (eventParts, timeslots, userId, windowStartDate, windowEndDate, timezone, slotDuration) => {
    try {
        const availableSlots = await generateAvailabilityForUser(eventParts, userId, windowStartDate, windowEndDate, timezone, slotDuration);
        const availableTimeSlots = convertAvailableSlotsToTimeSlotLike(availableSlots, timezone);
        const filteredTimeSlots = [];
        for (const availableTimeSlot of availableTimeSlots) {
            for (const timeslot of timeslots) {
                if (availableTimeSlot?.startTime === timeslot?.startTime &&
                    availableTimeSlot?.endTime === timeslot?.endTime &&
                    availableTimeSlot?.monthDay === timeslot?.monthDay) {
                    filteredTimeSlots.push(timeslot);
                }
            }
        }
        console.log(filteredTimeSlots, ' filteredTimeSlots');
        return filteredTimeSlots;
    }
    catch (e) {
        console.log(e, ' unable filterTimeslotsGivenImmodifiableEvents');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUFFLGtCQUFrQixFQUFFLE1BQU0sa0NBQWtDLENBQUM7QUFTdEUsT0FBTyxFQUFFLFNBQVMsRUFBRSxNQUFNLFVBQVUsQ0FBQztBQUdyQyxPQUFPLEVBQUUsS0FBSyxFQUFFLE1BQU0sa0NBQWtDLENBQUM7QUFDekQsT0FBTyxFQUFFLEVBQUUsSUFBSSxJQUFJLEVBQUUsTUFBTSxNQUFNLENBQUM7QUFFbEMsTUFBTSxDQUFDLE1BQU0sb0NBQW9DLEdBQUcsQ0FDbEQsWUFBb0IsRUFDcEIsdUJBQStCLEVBQy9CLGVBQW1DLEVBQ25DLFFBQWdCLEVBQ2hCLGdDQUF5RCxFQUN6RCxVQUFvQixFQUNwQixTQUFtQixFQUNuQixxQkFBOEIsRUFDOUIsRUFBRTtJQUNGLE9BQU8sQ0FBQyxHQUFHLENBQUMsUUFBUSxFQUFFLFdBQVcsQ0FBQyxDQUFDO0lBRW5DLElBQUksVUFBVSxJQUFJLFNBQVMsSUFBSSxxQkFBcUIsRUFBRSxDQUFDO1FBQ3JELE1BQU0sUUFBUSxHQUFHLGVBQWUsQ0FBQyxRQUFRLENBQUM7UUFDMUMsTUFBTSxZQUFZLEdBQUcsU0FBUyxDQUM1QixLQUFLLENBQUMsdUJBQXVCLENBQUMsQ0FBQyxFQUFFLENBQUMsUUFBUSxDQUFDLENBQUMsTUFBTSxFQUFFLENBQ3JELENBQUM7UUFFRixNQUFNLFVBQVUsR0FBRyxLQUFLLENBQUMsdUJBQXVCLENBQUMsQ0FBQyxFQUFFLENBQUMsUUFBUSxDQUFDLENBQUMsSUFBSSxFQUFFLENBQUM7UUFDdEUsSUFBSSxtQkFBbUIsR0FBRyxLQUFLLENBQUMsdUJBQXVCLENBQUM7YUFDckQsRUFBRSxDQUFDLFFBQVEsQ0FBQzthQUNaLElBQUksRUFBRSxDQUFDO1FBRVYsTUFBTSxZQUFZLEdBQUcsSUFBSSxDQUFDLEtBQUssQ0FBQyxFQUFFLEdBQUcsWUFB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QUM1QyxnQ0FBZ0MsQ0FBQyxNQUFNLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRTtZQUM1QyxNQUFNLFVBQVUsR0FBRyxnQ0FBZ0MsRUFBRSxTQUFTLENBQUMsQ0FBQyxFQUFFLEVBQUUsRUFBRTtnQkFDcEUsTUFBTSxLQUFLLEdBQUcsS0FBSyxDQUFDLENBQUMsQ0FBQyxPQUFPLENBQUM7cUJBQzNCLEVBQUUsQ0FBQyxRQUFRLENBQUM7cUJBQ1osTUFBTSxDQUFDLENBQUMsQ0FBQztxQkFDVCxTQUFTLENBQ1IsS0FBSyxDQUFDLEVBQUUsQ0FBQyxTQUFTLENBQUMsQ0FBQyxFQUFFLENBQUMsUUFBUSxDQUFDLENBQUMsTUFBTSxDQUFDLENBQUMsQ0FBQyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsR0FBRyxDQUFDLEVBQ3RELEtBQUssQ0FBQyxFQUFFLENBQUMsT0FBTyxDQUFDLENBQUMsRUFBRSxDQUFDLFFBQVEsQ0FBQyxDQUFDLE1BQU0sQ0FBQyxDQUFDLENBQUMsQ0FBQyxRQUFRLENBQUMsQ0FBQyxFQUFFLEdBQUcsQ0FBQyxFQUN6RCxHQUFHLEVBQ0gsSUFBSSxDQUNMLENBQUM7Z0JBRUosTUFBTSxLQUFLLEdBQUcsS0FBSyxDQUFDLENBQUMsQ0FBQyxTQUFTLENBQUM7cUJBQzdCLEVBQUUsQ0FBQyxRQUFRLENBQUM7cUJBQ1osTUFBTSxDQUFDLENBQUMsQ0FBQztxQkFDVCxTQUFTLENBQ1IsS0FBSyxDQUFDLEVBQUUsQ0FBQyxTQUFTLENBQUMsQ0FBQyxFQUFFLENBQUMsUUFBUSxDQUFDLENBQUMsTUFBTSxDQUFDLENBQUMsQ0FBQyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsR0FBRyxDQUFDLEVBQ3RELEtBQUssQ0FBQyxFQUFFLENBQUMsT0FBTyxDQUFDLENBQUMsRUFBRSxDQUFDLFFBQVEsQ0FBQyxDQUFDLE1BQU0sQ0FBQyxDQUFDLENBQUMsQ0FBQyxRQUFRLENBQUMsQ0FBQyxFQUFFLEdBQUcsQ0FBQyxFQUN6RCxHQUFHLEVBQ0gsSUFBSSxDQUNMLENBQUM7Z0JBRUosTUFBTSxLQUFL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QUksa0JBQWtCLEVBQUUsQ0FBQztZQUNuRCxLQUFLLE1BQU0sUUFBUSxJQUFJLFNBQVMsRUFBRSxDQUFDO2dCQUNqQyxJQUNFLGlCQUFpQixFQUFFLFNBQVMsS0FBSyxRQUFRLEVBQUUsU0FBUztvQkFDcEQsaUJBQWlCLEVBQUUsT0FBTyxLQUFLLFFBQVEsRUFBRSxPQUFPO29CQUNoRCxpQkFBaUIsRUFBRSxRQUFRLEtBQUssUUFBUSxFQUFFLFFBQVEsRUFDbEQsQ0FBQztvQkFDRCxpQkFBaUIsQ0FBQyxJQUFJLENBQUMsUUFBUSxDQUFDLENBQUM7Z0JBQ25DLENBQUM7WUFDSCxDQUFDO1FBQ0gsQ0FBQztRQUVELE9BQU8sQ0FBQyxHQUFHLENBQUMsaUJBQWlCLEVBQUUsb0JBQW9CLENBQUMsQ0FBQztRQUVyRCxPQUFPLGlCQUFpQixDQUFDO0lBQzNCLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsZ0RBQWdELENBQUMsQ0FBQztJQUNuRSxDQUFDO0FBQ0gsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ2V0VXNlclByZWZlcmVuY2VzIH0gZnJvbSAnQGZlYXR1cmVzX2FwcGx5L19saWJzL2FwaS1oZWxwZXInO1xuaW1wb3J0IHtcbiAgQXZhaWxhYmxlVGltZVNsb3RUeXBlLFxuICBFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlLFxuICBNb250aERheVR5cGUsXG4gIFRpbWUsXG4gIFRpbWVTbG90VHlwZSxcbiAgVXNlclByZWZlcmVuY2VUeXBlLFxufSBmcm9tICdAZmVhdHVyZXNfYXBwbHkvX2xpYnMvdHlwZXMnO1xuaW1wb3J0IHsgZ2V0SVNPRGF5IH0gZnJvbSAnZGF0ZS1mbnMnO1xuXG5pbXBvcnQgeyBBdmFpbGFibGVTbG90VHlwZSwgTm90QXZhaWxhYmxlU2xvdFR5cGUgfSBmcm9tICcuL3R5cGVzJztcbmltcG9ydCB7IGRheWpzIH0gZnJvbSAnQGZlYXR1cmVzX2FwcGx5L19saWJzL2RhdGUtdXRpbHMnO1xuaW1wb3J0IHsgdjQgYXMgdXVpZCB9IGZyb20gJ3V1aWQnO1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVBdmFpbGFibGVTbG90c0ZvckRhdGVGb3JVc2VyID0gKFxuICBzbG90RHVyYXRpb246IG51bWJlcixcbiAgc3RhcnREYXRlSW5Vc2VyVGltZXpvbmU6IHN0cmluZyxcbiAgdXNlclByZWZlcmVuY2VzOiBVc2VyUHJlZmVyZW5jZVR5cGUsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIG5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lPzogTm90QXZhaWxhYmxlU2xvdFR5cGVbXSxcbiAgaXNGaXJzdERheT86IGJvb2xlYW4sXG4gIGlzTGFzdERheT86IGJvb2xlYW4sXG4gIGVuZERhdGVJblVzZXJUaW1lem9uZT86IHN0cmluZ1xuKSA9PiB7XG4gIGNvbnNvbGUubG9nKHRpbWV6b25lLCAnIHRpbWV6b25lJyk7XG5cbiAgaWYgKGlzRmlyc3REYXkgJiYgaXNMYXN0RGF5ICYmIGVuZERhdGVJblVzZXJUaW1lem9uZSkge1xuICAgIGNvbnN0IGVuZFRpbWVzID0gdXNlclByZWZlcmVuY2VzLmVuZFRpbWVzO1xuICAgIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICAgIGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKS50eih0aW1lem9uZSkudG9EYXRlKClcbiAgICApO1xuXG4gICAgY29uc3QgZGF5T2ZNb250aCA9IGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKS50eih0aW1lem9uZSkuZGF0ZSgpO1xuICAgIGxldCBzdGFydEhvdXJBc1JlY2VpdmVyID0gZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAudHoodGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuXG4gICAgY29uc3QgZmxvb3JlZFZhbHVlID0gTWF0aC5mbG9vcig2MCAvIHNsb3REdXJhdGlvbik7XG5cbiAgICBsZXQgbWludXRlVmFsdWVBc1JlY2VpdmVyID0gMDtcbiAgICBpZiAoZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpLnR6KHRpbWV6b25lKS5taW51dGUoKSAhPT0gMCkge1xuICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCBmbG9vcmVkVmFsdWU7IGkrKykge1xuICAgICAgICBjb25zdCBlbmRNaW51dGVzID0gKGkgKyAxKSAqIHNsb3REdXJhdGlvbjtcbiAgICAgICAgY29uc3Qgc3RhcnRNaW51dGVzID0gaSAqIHNsb3REdXJhdGlvbjtcbiAgICAgICAgaWYgKFxuICAgICAgICAgIGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpLnR6KHRpbWV6b25lKS5taW51dGUoc3RhcnRNaW51dGVzKSxcbiAgICAgICAgICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpLnR6KHRpbWV6b25lKS5taW51dGUoZW5kTWludXRlcyksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApXG4gICAgICAgICkge1xuICAgICAgICAgIG1pbnV0ZVZhbHVlQXNSZWNlaXZlciA9IGVuZE1pbnV0ZXM7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSlcbiAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgIGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgLm1pbnV0ZShmbG9vcmVkVmFsdWUgKiBzbG90RHVyYXRpb24pLFxuICAgICAgICAgIGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKS50eih0aW1lem9uZSkubWludXRlKDU5KSxcbiAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAnWyknXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIHN0YXJ0SG91ckFzUmVjZWl2ZXIgKz0gMTtcbiAgICAgIG1pbnV0ZVZhbHVlQXNSZWNlaXZlciA9IDA7XG4gICAgfVxuXG4gICAgY29uc3Qgc3RhcnRNaW51dGVBc1JlY2VpdmVyID0gbWludXRlVmFsdWVBc1JlY2VpdmVyO1xuXG4gICAgY29uc3QgZW5kSG91cldvcmsgPVxuICAgICAgZW5kVGltZXM/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpPy5ob3VyID8/IDIwO1xuICAgIGNvbnN0IGVuZE1pbnV0ZVdvcmsgPVxuICAgICAgZW5kVGltZXM/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpPy5taW51dGVzID8/IDA7XG4gICAgY29uc3QgZW5kSG91ciA9IGRheWpzKGVuZERhdGVJblVzZXJUaW1lem9uZSkudHoodGltZXpvbmUpLmhvdXIoKTtcbiAgICBjb25zdCBlbmRNaW51dGUgPSBkYXlqcyhlbmREYXRlSW5Vc2VyVGltZXpvbmUpLnR6KHRpbWV6b25lKS5taW51dGUoKTtcblxuICAgIC8vIHZhbGlkYXRlIHZhbHVlcyBiZWZvcmUgY2FsY3VsYXRpbmdcbiAgICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2VzLnN0YXJ0VGltZXM7XG4gICAgY29uc3Qgd29ya1N0YXJ0SG91ciA9XG4gICAgICBzdGFydFRpbWVzPy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KT8uaG91ciB8fCA4O1xuICAgIGNvbnN0IHdvcmtTdGFydE1pbnV0ZSA9XG4gICAgICBzdGFydFRpbWVzPy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KT8ubWludXRlcyB8fCAwO1xuXG4gICAgaWYgKFxuICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmlzQWZ0ZXIoXG4gICAgICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAuaG91cihlbmRIb3VyV29yaylcbiAgICAgICAgICAgIC5taW51dGUoZW5kTWludXRlV29yaylcbiAgICAgICAgKVxuICAgICkge1xuICAgICAgLy8gcmV0dXJuIGVtcHR5IGFzIG91dHNpZGUgb2Ygd29yayB0aW1lXG4gICAgICByZXR1cm4gW107XG4gICAgfVxuXG4gICAgLy8gY2hhbmdlIHRvIHdvcmsgc3RhcnQgdGltZSBhcyBzZW5kZXIgc3RhcnQgdGltZSBiZWZvcmUgd29yayBzdGFydCB0aW1lXG4gICAgaWYgKFxuICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmlzQmVmb3JlKFxuICAgICAgICAgIGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgLmhvdXIod29ya1N0YXJ0SG91cilcbiAgICAgICAgICAgIC5taW51dGUod29ya1N0YXJ0TWludXRlKVxuICAgICAgICApXG4gICAgKSB7XG4gICAgICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgICBob3Vyczogd29ya1N0YXJ0SG91cixcbiAgICAgICAgbWludXRlczogd29ya1N0YXJ0TWludXRlLFxuICAgICAgfSk7XG4gICAgICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgICAgaG91cnM6IGVuZEhvdXIsXG4gICAgICAgIG1pbnV0ZXM6IGVuZE1pbnV0ZSxcbiAgICAgIH0pO1xuICAgICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgICAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcblxuICAgICAgY29uc3QgYXZhaWxhYmxlU2xvdHM6IEF2YWlsYWJsZVNsb3RUeXBlW10gPSBbXTtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBzdGFydERhdGVJblVzZXJUaW1lem9uZSxcbiAgICAgICAgZW5kVGltZXMsXG4gICAgICAgIGRheU9mV2Vla0ludCxcbiAgICAgICAgZGF5T2ZNb250aCxcbiAgICAgICAgc3RhcnRIb3VyQXNSZWNlaXZlcixcbiAgICAgICAgc3RhcnRNaW51dGVBc1JlY2VpdmVyLFxuICAgICAgICBlbmRIb3VyLFxuICAgICAgICBlbmRNaW51dGUsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBgc3RhcnREYXRlLCBlbmRUaW1lcywgZGF5T2ZXZWVrSW50QnlVc2VyLCBkYXlPZk1vbnRoLCBzdGFydEhvdXIsIHN0YXJ0TWludXRlLCBlbmRIb3VyLCBlbmRNaW51dGUgdG90YWxNaW51dGVzLCB0aW1lem9uZSwgaW5zaWRlIGZpcnN0RGF5IGluc2lkZSBnZW5lcmF0ZVRpbWVzbG90c2BcbiAgICAgICk7XG4gICAgICBmb3IgKGxldCBpID0gMDsgaSA8IHRvdGFsTWludXRlczsgaSArPSBzbG90RHVyYXRpb24pIHtcbiAgICAgICAgaWYgKGkgPiB0b3RhbE1pbnV0ZXMpIHtcbiAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgfVxuXG4gICAgICAgIGF2YWlsYWJsZVNsb3RzLnB1c2goe1xuICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgc3RhcnREYXRlOiBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXIpXG4gICAgICAgICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZSlcbiAgICAgICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICAgICAgZW5kRGF0ZTogZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyKVxuICAgICAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGUpXG4gICAgICAgICAgICAuYWRkKGkgKyBzbG90RHVyYXRpb24sICdtaW51dGUnKVxuICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICB9KTtcbiAgICAgIH1cbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBhdmFpbGFibGVTbG90cyxcbiAgICAgICAgJyB0aW1lU2xvdHMgaW5zaWRlIGdlbmVyYXRlVGltZVNsb3RzIGZvciBmaXJzdCBkYXkgd2hlcmUgc3RhcnREYXRlIGlzIGJlZm9yZSB3b3JrIHN0YXJ0IHRpbWUnXG4gICAgICApO1xuXG4gICAgICAvLyBmaWx0ZXIgb3V0IHVuYXZhaWxhYmxlIHRpbWVzXG4gICAgICBjb25zdCBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lID0gYXZhaWxhYmxlU2xvdHMuZmlsdGVyKFxuICAgICAgICAoYSkgPT4ge1xuICAgICAgICAgIGNvbnN0IGZvdW5kSW5kZXggPSBub3RBdmFpbGFibGVTbG90c0luRXZlbnRUaW1lem9uZT8uZmluZEluZGV4KFxuICAgICAgICAgICAgKG5hKSA9PiB7XG4gICAgICAgICAgICAgIGNvbnN0IHBhcnRBID0gZGF5anMoYS5lbmREYXRlKVxuICAgICAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLnNlY29uZCgwKS5hZGQoMSwgJ20nKSxcbiAgICAgICAgICAgICAgICAgIGRheWpzKG5hLmVuZERhdGUpLnR6KHRpbWV6b25lKS5zZWNvbmQoMCkuc3VidHJhY3QoMSwgJ20nKSxcbiAgICAgICAgICAgICAgICAgICdtJyxcbiAgICAgICAgICAgICAgICAgICdbXSdcbiAgICAgICAgICAgICAgICApO1xuXG4gICAgICAgICAgICAgIGNvbnN0IHBhcnRCID0gZGF5anMoYS5zdGFydERhdGUpXG4gICAgICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKS50eih0aW1lem9uZSkuc2Vjb25kKDApLmFkZCgxLCAnbScpLFxuICAgICAgICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSkudHoodGltZXpvbmUpLnNlY29uZCgwKS5zdWJ0cmFjdCgxLCAnbScpLFxuICAgICAgICAgICAgICAgICAgJ20nLFxuICAgICAgICAgICAgICAgICAgJ1tdJ1xuICAgICAgICAgICAgICAgICk7XG5cbiAgICAgICAgICAgICAgY29uc3QgcGFydEMgPVxuICAgICAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSA9PT1cbiAgICAgICAgICAgICAgICAgIGRheWpzKGEuc3RhcnREYXRlKVxuICAgICAgICAgICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpICYmXG4gICAgICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSA9PT1cbiAgICAgICAgICAgICAgICAgIGRheWpzKGEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKTtcblxuICAgICAgICAgICAgICBjb25zdCBpc05vdEF2YWlsYWJsZSA9IHBhcnRBIHx8IHBhcnRCIHx8IHBhcnRDO1xuXG4gICAgICAgICAgICAgIC8vIGNvbnNvbGUubG9nKGEsIG5hLCAnIGEsIG5hJylcbiAgICAgICAgICAgICAgcmV0dXJuIGlzTm90QXZhaWxhYmxlO1xuICAgICAgICAgICAgfVxuICAgICAgICAgICk7XG5cbiAgICAgICAgICBjb25zb2xlLmxvZyhmb3VuZEluZGV4LCAnIGZvdW5kSW5kZXgnKTtcblxuICAgICAgICAgIGlmIChmb3VuZEluZGV4ICE9PSB1bmRlZmluZWQgJiYgZm91bmRJbmRleCA+IC0xKSB7XG4gICAgICAgICAgICByZXR1cm4gZmFsc2U7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgcmV0dXJuIHRydWU7XG4gICAgICAgIH1cbiAgICAgICk7XG5cbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lLFxuICAgICAgICAnIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHMnXG4gICAgICApO1xuXG4gICAgICByZXR1cm4gZmlsdGVyZWRBdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZTtcbiAgICB9XG5cbiAgICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgaG91cnM6IHN0YXJ0SG91ckFzUmVjZWl2ZXIsXG4gICAgICBtaW51dGVzOiBzdGFydE1pbnV0ZUFzUmVjZWl2ZXIsXG4gICAgfSk7XG4gICAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7IGhvdXJzOiBlbmRIb3VyLCBtaW51dGVzOiBlbmRNaW51dGUgfSk7XG4gICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG4gICAgY29uc29sZS5sb2codG90YWxNaW51dGVzLCAnIHRvdGFsTWludXRlcyBpbnNpZGUgZmlyc3QgYW5kIGxhc3Qgc2FtZSBkYXknKTtcbiAgICBjb25zdCBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZTogQXZhaWxhYmxlU2xvdFR5cGVbXSA9IFtdO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUsXG4gICAgICBlbmRUaW1lcyxcbiAgICAgIGRheU9mV2Vla0ludCxcbiAgICAgIGVuZEhvdXJXb3JrLFxuICAgICAgZW5kTWludXRlV29yayxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgYHN0YXJ0RGF0ZSwgZW5kVGltZXMsIGRheU9mV2Vla0ludCwgZGF5T2ZNb250aCwgc3RhcnRIb3VyLCBzdGFydE1pbnV0ZSwgZW5kSG91ciwgZW5kTWludXRlIHRvdGFsTWludXRlcywgdGltZXpvbmUsIGluc2lkZSBmaXJzdCAmIGxhc3QgRGF5IGluc2lkZSBnZW5lcmF0ZVRpbWVzbG90c2BcbiAgICApO1xuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IHNsb3REdXJhdGlvbikge1xuICAgICAgaWYgKGkgPiB0b3RhbE1pbnV0ZXMpIHtcbiAgICAgICAgY29udGludWU7XG4gICAgICB9XG4gICAgICBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZS5wdXNoKHtcbiAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgc3RhcnREYXRlOiBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSlcbiAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQXNSZWNlaXZlcilcbiAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlQXNSZWNlaXZlcilcbiAgICAgICAgICAuYWRkKGksICdtaW51dGUnKVxuICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICAgIGVuZERhdGU6IGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAuaG91cihzdGFydEhvdXJBc1JlY2VpdmVyKVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVBc1JlY2VpdmVyKVxuICAgICAgICAgIC5hZGQoaSArIHNsb3REdXJhdGlvbiwgJ21pbnV0ZScpXG4gICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgIH0pO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUsXG4gICAgICAnIGF2YWlsYWJsZVNsb3RzIGluc2lkZSBmaXJzdCAmIGxhc3Qgc2FtZSBkYXknXG4gICAgKTtcbiAgICBjb25zdCBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lID1cbiAgICAgIGF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lLmZpbHRlcigoYSkgPT4ge1xuICAgICAgICBjb25zdCBmb3VuZEluZGV4ID0gbm90QXZhaWxhYmxlU2xvdHNJbkV2ZW50VGltZXpvbmU/LmZpbmRJbmRleCgobmEpID0+IHtcbiAgICAgICAgICBjb25zdCBwYXJ0QSA9IGRheWpzKGEuZW5kRGF0ZSlcbiAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLnNlY29uZCgwKS5hZGQoMSwgJ20nKSxcbiAgICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSkudHoodGltZXpvbmUpLnNlY29uZCgwKS5zdWJ0cmFjdCgxLCAnbScpLFxuICAgICAgICAgICAgICAnbScsXG4gICAgICAgICAgICAgICdbXSdcbiAgICAgICAgICAgICk7XG5cbiAgICAgICAgICBjb25zdCBwYXJ0QiA9IGRheWpzKGEuc3RhcnREYXRlKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKS50eih0aW1lem9uZSkuc2Vjb25kKDApLmFkZCgxLCAnbScpLFxuICAgICAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKS50eih0aW1lem9uZSkuc2Vjb25kKDApLnN1YnRyYWN0KDEsICdtJyksXG4gICAgICAgICAgICAgICdtJyxcbiAgICAgICAgICAgICAgJ1tdJ1xuICAgICAgICAgICAgKTtcblxuICAgICAgICAgIGNvbnN0IHBhcnRDID1cbiAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSA9PT1cbiAgICAgICAgICAgICAgZGF5anMoYS5zdGFydERhdGUpXG4gICAgICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgJiZcbiAgICAgICAgICAgIGRheWpzKG5hLmVuZERhdGUpXG4gICAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgPT09XG4gICAgICAgICAgICAgIGRheWpzKGEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKTtcblxuICAgICAgICAgIGNvbnN0IGlzTm90QXZhaWxhYmxlID0gcGFydEEgfHwgcGFydEIgfHwgcGFydEM7XG5cbiAgICAgICAgICAvLyBjb25zb2xlLmxvZyhhLCBuYSwgJyBhLCBuYScpXG5cbiAgICAgICAgICByZXR1cm4gaXNOb3RBdmFpbGFibGU7XG4gICAgICAgIH0pO1xuXG4gICAgICAgIGNvbnNvbGUubG9nKGZvdW5kSW5kZXgsICcgZm91bmRJbmRleCcpO1xuXG4gICAgICAgIGlmIChmb3VuZEluZGV4ICE9PSB1bmRlZmluZWQgJiYgZm91bmRJbmRleCA+IC0xKSB7XG4gICAgICAgICAgcmV0dXJuIGZhbHNlO1xuICAgICAgICB9XG5cbiAgICAgICAgcmV0dXJuIHRydWU7XG4gICAgICB9KTtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZmlsdGVyZWRBdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZSxcbiAgICAgICcgZmlsdGVyZWRBdmFpbGFibGVTbG90cydcbiAgICApO1xuICAgIHJldHVybiBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lO1xuICB9XG5cbiAgaWYgKGlzRmlyc3REYXkpIHtcbiAgICAvLyBmaXJzdGRheSBjYW4gYmUgc3RhcnRlZCBvdXRzaWRlIG9mIHdvcmsgdGltZVxuICAgIC8vIGlmIGZpcnN0RGF5IHN0YXJ0IGlzIGFmdGVyIGVuZCB0aW1lIC0tIHJldHVybiBbXVxuICAgIGNvbnN0IGVuZFRpbWVzID0gdXNlclByZWZlcmVuY2VzLmVuZFRpbWVzO1xuICAgIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICAgIGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKS50eih0aW1lem9uZSkudG9EYXRlKClcbiAgICApO1xuXG4gICAgLy8gbW9udGggaXMgemVyby1pbmRleGVkXG4gICAgLy8gY29uc3QgbW9udGggPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS50eih1c2VyVGltZXpvbmUpLm1vbnRoKClcbiAgICBjb25zdCBkYXlPZk1vbnRoID0gZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpLnR6KHRpbWV6b25lKS5kYXRlKCk7XG4gICAgbGV0IHN0YXJ0SG91ciA9IGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKS50eih0aW1lem9uZSkuaG91cigpO1xuXG4gICAgY29uc3Qgc3RhcnRNaW51dGUgPSBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSkudHoodGltZXpvbmUpLm1pbnV0ZSgpO1xuICAgIC8vIGNyZWF0ZSBzbG90IHNpemVzXG4gICAgY29uc3QgZmxvb3JlZFZhbHVlID0gTWF0aC5mbG9vcig2MCAvIHNsb3REdXJhdGlvbik7XG5cbiAgICBsZXQgbWludXRlVmFsdWVBc1JlY2VpdmVyID0gMDtcbiAgICBpZiAoZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpLnR6KHRpbWV6b25lKS5taW51dGUoKSAhPT0gMCkge1xuICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCBmbG9vcmVkVmFsdWU7IGkrKykge1xuICAgICAgICBjb25zdCBlbmRNaW51dGVzID0gKGkgKyAxKSAqIHNsb3REdXJhdGlvbjtcbiAgICAgICAgY29uc3Qgc3RhcnRNaW51dGVzID0gaSAqIHNsb3REdXJhdGlvbjtcbiAgICAgICAgaWYgKFxuICAgICAgICAgIGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpLnR6KHRpbWV6b25lKS5taW51dGUoc3RhcnRNaW51dGVzKSxcbiAgICAgICAgICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpLnR6KHRpbWV6b25lKS5taW51dGUoZW5kTWludXRlcyksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApXG4gICAgICAgICkge1xuICAgICAgICAgIG1pbnV0ZVZhbHVlQXNSZWNlaXZlciA9IGVuZE1pbnV0ZXM7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSlcbiAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgIGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgLm1pbnV0ZShmbG9vcmVkVmFsdWUgKiBzbG90RHVyYXRpb24pLFxuICAgICAgICAgIGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKS50eih0aW1lem9uZSkubWludXRlKDU5KSxcbiAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAnWyknXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIHN0YXJ0SG91ciArPSAxO1xuICAgICAgbWludXRlVmFsdWVBc1JlY2VpdmVyID0gMDtcbiAgICB9XG5cbiAgICBjb25zdCBzdGFydE1pbnV0ZUFzUmVjZWl2ZXIgPSBtaW51dGVWYWx1ZUFzUmVjZWl2ZXI7XG5cbiAgICAvLyBjb252ZXJ0IHRvIHVzZXIgdGltZXpvbmUgc28gZXZlcnl0aGluZyBpcyBsaW5rZWQgdG8gdXNlciB0aW1lem9uZVxuXG4gICAgY29uc3QgZW5kSG91ciA9IGVuZFRpbWVzPy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KT8uaG91ciA/PyAyMDtcbiAgICBjb25zdCBlbmRNaW51dGUgPVxuICAgICAgZW5kVGltZXM/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpPy5taW51dGVzID8/IDA7XG5cbiAgICAvLyB2YWxpZGF0ZSB2YWx1ZXMgYmVmb3JlIGNhbGN1bGF0aW5nXG4gICAgY29uc3Qgc3RhcnRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlcy5zdGFydFRpbWVzO1xuICAgIGNvbnN0IHdvcmtTdGFydEhvdXIgPVxuICAgICAgc3RhcnRUaW1lcz8uZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCk/LmhvdXIgfHwgODtcbiAgICBjb25zdCB3b3JrU3RhcnRNaW51dGUgPVxuICAgICAgc3RhcnRUaW1lcz8uZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCk/Lm1pbnV0ZXMgfHwgMDtcblxuICAgIGlmIChcbiAgICAgIGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5pc0FmdGVyKFxuICAgICAgICAgIGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgLmhvdXIoZW5kSG91cilcbiAgICAgICAgICAgIC5taW51dGUoZW5kTWludXRlKVxuICAgICAgICApXG4gICAgKSB7XG4gICAgICAvLyByZXR1cm4gZW1wdHkgYXMgb3V0c2lkZSBvZiB3b3JrIHRpbWVcbiAgICAgIHJldHVybiBbXTtcbiAgICB9XG5cbiAgICAvLyBjaGFuZ2UgdG8gd29yayBzdGFydCB0aW1lIGFzIGhvc3Qgc3RhcnQgdGltZSBiZWZvcmUgd29yayBzdGFydCB0aW1lXG4gICAgaWYgKFxuICAgICAgZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmlzQmVmb3JlKFxuICAgICAgICAgIGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgLmhvdXIod29ya1N0YXJ0SG91cilcbiAgICAgICAgICAgIC5taW51dGUod29ya1N0YXJ0TWludXRlKVxuICAgICAgICApXG4gICAgKSB7XG4gICAgICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgICBob3Vyczogd29ya1N0YXJ0SG91cixcbiAgICAgICAgbWludXRlczogd29ya1N0YXJ0TWludXRlLFxuICAgICAgfSk7XG4gICAgICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgICAgaG91cnM6IGVuZEhvdXIsXG4gICAgICAgIG1pbnV0ZXM6IGVuZE1pbnV0ZSxcbiAgICAgIH0pO1xuICAgICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgICAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcblxuICAgICAgY29uc3QgYXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmU6IEF2YWlsYWJsZVNsb3RUeXBlW10gPSBbXTtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBzdGFydERhdGVJblVzZXJUaW1lem9uZSxcbiAgICAgICAgZW5kVGltZXMsXG4gICAgICAgIGRheU9mV2Vla0ludCxcbiAgICAgICAgZGF5T2ZNb250aCxcbiAgICAgICAgc3RhcnRIb3VyLFxuICAgICAgICBzdGFydE1pbnV0ZUFzUmVjZWl2ZXIsXG4gICAgICAgIGVuZEhvdXIsXG4gICAgICAgIGVuZE1pbnV0ZSxcbiAgICAgICAgdGltZXpvbmUsXG4gICAgICAgIGBzdGFydERhdGUsIGVuZFRpbWVzLCBkYXlPZldlZWtJbnRCeVVzZXIsIGRheU9mTW9udGgsIHN0YXJ0SG91ciwgc3RhcnRNaW51dGUsIGVuZEhvdXIsIGVuZE1pbnV0ZSB0b3RhbE1pbnV0ZXMsIHRpbWV6b25lLCBpbnNpZGUgZmlyc3REYXkgaW5zaWRlIGdlbmVyYXRlVGltZXNsb3RzYFxuICAgICAgKTtcbiAgICAgIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IHNsb3REdXJhdGlvbikge1xuICAgICAgICBpZiAoaSA+IHRvdGFsTWludXRlcykge1xuICAgICAgICAgIGNvbnRpbnVlO1xuICAgICAgICB9XG5cbiAgICAgICAgYXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUucHVzaCh7XG4gICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgICBzdGFydERhdGU6IGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgLmhvdXIod29ya1N0YXJ0SG91cilcbiAgICAgICAgICAgIC5taW51dGUod29ya1N0YXJ0TWludXRlKVxuICAgICAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgICBlbmREYXRlOiBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXIpXG4gICAgICAgICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZSlcbiAgICAgICAgICAgIC5hZGQoaSArIHNsb3REdXJhdGlvbiwgJ21pbnV0ZScpXG4gICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICAgIH0pO1xuICAgICAgfVxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lLFxuICAgICAgICAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMgZm9yIGZpcnN0IGRheSB3aGVyZSBzdGFydERhdGUgaXMgYmVmb3JlIHdvcmsgc3RhcnQgdGltZSdcbiAgICAgICk7XG5cbiAgICAgIC8vIGZpbHRlciBvdXQgdW5hdmFpbGFibGUgdGltZXNcbiAgICAgIGNvbnN0IGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUgPVxuICAgICAgICBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZS5maWx0ZXIoKGEpID0+IHtcbiAgICAgICAgICBjb25zdCBmb3VuZEluZGV4ID0gbm90QXZhaWxhYmxlU2xvdHNJbkV2ZW50VGltZXpvbmU/LmZpbmRJbmRleChcbiAgICAgICAgICAgIChuYSkgPT4ge1xuICAgICAgICAgICAgICBjb25zdCBwYXJ0QSA9IGRheWpzKGEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpLnR6KHRpbWV6b25lKS5zZWNvbmQoMCkuYWRkKDEsICdtJyksXG4gICAgICAgICAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKS50eih0aW1lem9uZSkuc2Vjb25kKDApLnN1YnRyYWN0KDEsICdtJyksXG4gICAgICAgICAgICAgICAgICAnbScsXG4gICAgICAgICAgICAgICAgICAnW10nXG4gICAgICAgICAgICAgICAgKTtcblxuICAgICAgICAgICAgICBjb25zdCBwYXJ0QiA9IGRheWpzKGEuc3RhcnREYXRlKVxuICAgICAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLnNlY29uZCgwKS5hZGQoMSwgJ20nKSxcbiAgICAgICAgICAgICAgICAgIGRheWpzKG5hLmVuZERhdGUpLnR6KHRpbWV6b25lKS5zZWNvbmQoMCkuc3VidHJhY3QoMSwgJ20nKSxcbiAgICAgICAgICAgICAgICAgICdtJyxcbiAgICAgICAgICAgICAgICAgICdbXSdcbiAgICAgICAgICAgICAgICApO1xuXG4gICAgICAgICAgICAgIGNvbnN0IHBhcnRDID1cbiAgICAgICAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpXG4gICAgICAgICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgPT09XG4gICAgICAgICAgICAgICAgICBkYXlqcyhhLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSAmJlxuICAgICAgICAgICAgICAgIGRheWpzKG5hLmVuZERhdGUpXG4gICAgICAgICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgPT09XG4gICAgICAgICAgICAgICAgICBkYXlqcyhhLmVuZERhdGUpXG4gICAgICAgICAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJyk7XG5cbiAgICAgICAgICAgICAgY29uc3QgaXNOb3RBdmFpbGFibGUgPSBwYXJ0QSB8fCBwYXJ0QiB8fCBwYXJ0QztcblxuICAgICAgICAgICAgICAvLyBjb25zb2xlLmxvZyhhLCBuYSwgJyBhLCBuYScpXG4gICAgICAgICAgICAgIHJldHVybiBpc05vdEF2YWlsYWJsZTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICApO1xuXG4gICAgICAgICAgY29uc29sZS5sb2coZm91bmRJbmRleCwgJyBmb3VuZEluZGV4Jyk7XG5cbiAgICAgICAgICBpZiAoZm91bmRJbmRleCAhPT0gdW5kZWZpbmVkICYmIGZvdW5kSW5kZXggPiAtMSkge1xuICAgICAgICAgICAgcmV0dXJuIGZhbHNlO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIHJldHVybiB0cnVlO1xuICAgICAgICB9KTtcblxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUsXG4gICAgICAgICcgZmlsdGVyZWRBdmFpbGFibGVTbG90cydcbiAgICAgICk7XG5cbiAgICAgIHJldHVybiBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lO1xuICAgIH1cblxuICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICBob3Vyczogc3RhcnRIb3VyLFxuICAgICAgbWludXRlczogc3RhcnRNaW51dGUsXG4gICAgfSk7XG4gICAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7IGhvdXJzOiBlbmRIb3VyLCBtaW51dGVzOiBlbmRNaW51dGUgfSk7XG4gICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG4gICAgY29uc3QgYXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmU6IEF2YWlsYWJsZVNsb3RUeXBlW10gPSBbXTtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lLFxuICAgICAgZW5kVGltZXMsXG4gICAgICBkYXlPZldlZWtJbnQsXG4gICAgICBlbmRIb3VyLFxuICAgICAgZW5kTWludXRlLFxuICAgICAgdGltZXpvbmUsXG4gICAgICBgc3RhcnREYXRlLCBlbmRUaW1lcywgZGF5T2ZXZWVrSW50LCBkYXlPZk1vbnRoLCBzdGFydEhvdXIsIHN0YXJ0TWludXRlLCBlbmRIb3VyLCBlbmRNaW51dGUgdG90YWxNaW51dGVzLCB0aW1lem9uZSwgaW5zaWRlIGZpcnN0RGF5IGluc2lkZSBnZW5lcmF0ZVRpbWVzbG90c2BcbiAgICApO1xuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IHNsb3REdXJhdGlvbikge1xuICAgICAgaWYgKGkgPiB0b3RhbE1pbnV0ZXMpIHtcbiAgICAgICAgY29udGludWU7XG4gICAgICB9XG4gICAgICBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZS5wdXNoKHtcbiAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgc3RhcnREYXRlOiBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSlcbiAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyKVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVBc1JlY2VpdmVyKVxuICAgICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgZW5kRGF0ZTogZGF5anMoc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUpXG4gICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91cilcbiAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlQXNSZWNlaXZlcilcbiAgICAgICAgICAuYWRkKGkgKyBzbG90RHVyYXRpb24sICdtaW51dGUnKVxuICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICB9KTtcbiAgICB9XG4gICAgY29uc3QgZmlsdGVyZWRBdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZSA9XG4gICAgICBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZS5maWx0ZXIoKGEpID0+IHtcbiAgICAgICAgY29uc3QgZm91bmRJbmRleCA9IG5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lPy5maW5kSW5kZXgoKG5hKSA9PiB7XG4gICAgICAgICAgY29uc3QgcGFydEEgPSBkYXlqcyhhLmVuZERhdGUpXG4gICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpLnR6KHRpbWV6b25lKS5zZWNvbmQoMCkuYWRkKDEsICdtJyksXG4gICAgICAgICAgICAgIGRheWpzKG5hLmVuZERhdGUpLnR6KHRpbWV6b25lKS5zZWNvbmQoMCkuc3VidHJhY3QoMSwgJ20nKSxcbiAgICAgICAgICAgICAgJ20nLFxuICAgICAgICAgICAgICAnW10nXG4gICAgICAgICAgICApO1xuXG4gICAgICAgICAgY29uc3QgcGFydEIgPSBkYXlqcyhhLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLnNlY29uZCgwKS5hZGQoMSwgJ20nKSxcbiAgICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSkudHoodGltZXpvbmUpLnNlY29uZCgwKS5zdWJ0cmFjdCgxLCAnbScpLFxuICAgICAgICAgICAgICAnbScsXG4gICAgICAgICAgICAgICdbXSdcbiAgICAgICAgICAgICk7XG5cbiAgICAgICAgICBjb25zdCBwYXJ0QyA9XG4gICAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpXG4gICAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgPT09XG4gICAgICAgICAgICAgIGRheWpzKGEuc3RhcnREYXRlKVxuICAgICAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpICYmXG4gICAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKVxuICAgICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpID09PVxuICAgICAgICAgICAgICBkYXlqcyhhLmVuZERhdGUpXG4gICAgICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJyk7XG5cbiAgICAgICAgICBjb25zdCBpc05vdEF2YWlsYWJsZSA9IHBhcnRBIHx8IHBhcnRCIHx8IHBhcnRDO1xuXG4gICAgICAgICAgLy8gY29uc29sZS5sb2coYSwgbmEsICcgYSwgbmEnKVxuXG4gICAgICAgICAgcmV0dXJuIGlzTm90QXZhaWxhYmxlO1xuICAgICAgICB9KTtcblxuICAgICAgICBjb25zb2xlLmxvZyhmb3VuZEluZGV4LCAnIGZvdW5kSW5kZXgnKTtcblxuICAgICAgICBpZiAoZm91bmRJbmRleCAhPT0gdW5kZWZpbmVkICYmIGZvdW5kSW5kZXggPiAtMSkge1xuICAgICAgICAgIHJldHVybiBmYWxzZTtcbiAgICAgICAgfVxuXG4gICAgICAgIHJldHVybiB0cnVlO1xuICAgICAgfSk7XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUsXG4gICAgICAnIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHMgc2VydmVyIHRpbWV6b25lJ1xuICAgICk7XG4gICAgcmV0dXJuIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmU7XG4gIH1cblxuICAvLyBub3QgZmlyc3QgZGF5IHN0YXJ0IGZyb20gd29yayBzdGFydCB0aW1lIHNjaGVkdWxlXG5cbiAgY29uc3Qgc3RhcnRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlcy5zdGFydFRpbWVzO1xuXG4gIGNvbnN0IGVuZFRpbWVzID0gdXNlclByZWZlcmVuY2VzLmVuZFRpbWVzO1xuXG4gIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSkudHoodGltZXpvbmUpLnRvRGF0ZSgpXG4gICk7XG4gIGNvbnN0IGRheU9mTW9udGggPSBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSkudHoodGltZXpvbmUpLmRhdGUoKTtcblxuICAvLyBjb252ZXJ0IHRvIHVzZXIgdGltZXpvbmUgc28gZXZlcnl0aGluZyBpcyBsaW5rZWQgdG8gdXNlciB0aW1lem9uZVxuICBsZXQgZW5kSG91ciA9IGVuZFRpbWVzPy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KT8uaG91ciA/PyAyMDtcbiAgbGV0IGVuZE1pbnV0ZSA9IGVuZFRpbWVzPy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KT8ubWludXRlcyA/PyAwO1xuXG4gIC8vIGlmIGxhc3QgZGF5IGNoYW5nZSBlbmQgdGltZSB0byBob3N0U3RhcnREYXRlIHByb3ZpZGVkXG4gIGlmIChpc0xhc3REYXkgJiYgZW5kRGF0ZUluVXNlclRpbWV6b25lKSB7XG4gICAgZW5kSG91ciA9IGRheWpzKGVuZERhdGVJblVzZXJUaW1lem9uZSkudHoodGltZXpvbmUpLmhvdXIoKTtcbiAgICAvLyBjcmVhdGUgc2xvdCBzaXplc1xuICAgIGNvbnN0IGZsb29yZWRWYWx1ZSA9IE1hdGguZmxvb3IoNjAgLyBzbG90RHVyYXRpb24pO1xuXG4gICAgbGV0IG1pbnV0ZVZhbHVlQnlTZW5kZXIgPSAwO1xuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgZmxvb3JlZFZhbHVlOyBpKyspIHtcbiAgICAgIGNvbnN0IGVuZE1pbnV0ZXMgPSAoaSArIDEpICogc2xvdER1cmF0aW9uO1xuICAgICAgY29uc3Qgc3RhcnRNaW51dGVzID0gaSAqIHNsb3REdXJhdGlvbjtcbiAgICAgIGlmIChcbiAgICAgICAgZGF5anMoZW5kRGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgZGF5anMoZW5kRGF0ZUluVXNlclRpbWV6b25lKS50eih0aW1lem9uZSkubWludXRlKHN0YXJ0TWludXRlcyksXG4gICAgICAgICAgICBkYXlqcyhlbmREYXRlSW5Vc2VyVGltZXpvbmUpLnR6KHRpbWV6b25lKS5taW51dGUoZW5kTWludXRlcyksXG4gICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICdbKSdcbiAgICAgICAgICApXG4gICAgICApIHtcbiAgICAgICAgbWludXRlVmFsdWVCeVNlbmRlciA9IHN0YXJ0TWludXRlcztcbiAgICAgIH1cbiAgICB9XG5cbiAgICBlbmRNaW51dGUgPSBtaW51dGVWYWx1ZUJ5U2VuZGVyO1xuICB9XG5cbiAgY29uc3Qgc3RhcnRIb3VyQnlTZW5kZXIgPVxuICAgIChzdGFydFRpbWVzPy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KT8uaG91ciBhcyBudW1iZXIpIHx8IDg7XG4gIGNvbnN0IHN0YXJ0TWludXRlQnlTZW5kZXIgPVxuICAgIChzdGFydFRpbWVzPy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KT8ubWludXRlcyBhcyBudW1iZXIpIHx8IDA7XG5cbiAgY29uc3Qgc3RhcnREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICBob3Vyczogc3RhcnRIb3VyQnlTZW5kZXIsXG4gICAgbWludXRlczogc3RhcnRNaW51dGVCeVNlbmRlcixcbiAgfSk7XG4gIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oeyBob3VyczogZW5kSG91ciwgbWludXRlczogZW5kTWludXRlIH0pO1xuICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbik7XG4gIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG5cbiAgY29uc3QgYXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmU6IEF2YWlsYWJsZVNsb3RUeXBlW10gPSBbXTtcbiAgY29uc29sZS5sb2coXG4gICAgc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUsXG4gICAgZW5kVGltZXMsXG4gICAgZGF5T2ZXZWVrSW50LFxuICAgIGRheU9mTW9udGgsXG4gICAgc3RhcnRIb3VyQnlTZW5kZXIsXG4gICAgc3RhcnRNaW51dGVCeVNlbmRlcixcbiAgICBlbmRIb3VyLFxuICAgIGVuZE1pbnV0ZSxcbiAgICB0aW1lem9uZSxcbiAgICBgc3RhcnREYXRlLCBlbmRUaW1lcywgZGF5T2ZXZWVrSW50QnlIb3N0LCBkYXlPZk1vbnRoLCBzdGFydEhvdXIsIHN0YXJ0TWludXRlLCBlbmRIb3VyLCBlbmRNaW51dGUgdG90YWxNaW51dGVzLCB0aW1lem9uZSwgaW5zaWRlIGZpcnN0RGF5IGluc2lkZSBnZW5lcmF0ZUF2YWlsYWJsZXNsb3RzYFxuICApO1xuICBmb3IgKGxldCBpID0gMDsgaSA8IHRvdGFsTWludXRlczsgaSArPSBzbG90RHVyYXRpb24pIHtcbiAgICBpZiAoaSA+IHRvdGFsTWludXRlcykge1xuICAgICAgY29udGludWU7XG4gICAgfVxuXG4gICAgYXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUucHVzaCh7XG4gICAgICBpZDogdXVpZCgpLFxuICAgICAgc3RhcnREYXRlOiBkYXlqcyhzdGFydERhdGVJblVzZXJUaW1lem9uZSlcbiAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAuaG91cihzdGFydEhvdXJCeVNlbmRlcilcbiAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUJ5U2VuZGVyKVxuICAgICAgICAuYWRkKGksICdtaW51dGUnKVxuICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgIC5mb3JtYXQoKSxcbiAgICAgIGVuZERhdGU6IGRheWpzKHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5U2VuZGVyKVxuICAgICAgICAubWludXRlKHN0YXJ0TWludXRlQnlTZW5kZXIpXG4gICAgICAgIC5hZGQoaSArIHNsb3REdXJhdGlvbiwgJ21pbnV0ZScpXG4gICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgLmZvcm1hdCgpLFxuICAgIH0pO1xuICB9XG5cbiAgY29uc29sZS5sb2coXG4gICAgYXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUsXG4gICAgJyB0aW1lU2xvdHMgaW5zaWRlIGdlbmVyYXRlVGltZVNsb3RzIG5vdCBmaXJzdCBkYXknXG4gICk7XG4gIGNvbnNvbGUubG9nKFxuICAgIG5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lLFxuICAgICcgbm90QXZhaWxhYmxlU2xvdHNJbkV2ZW50VGltZXpvbmUgbm90IGZpcnN0IGRheSdcbiAgKTtcblxuICAvLyBmaWx0ZXIgb3V0IHVuYXZhaWxhYmxlIHRpbWVzXG4gIGNvbnN0IGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUgPVxuICAgIGF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lLmZpbHRlcigoYSkgPT4ge1xuICAgICAgY29uc3QgZm91bmRJbmRleCA9IG5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lPy5maW5kSW5kZXgoKG5hKSA9PiB7XG4gICAgICAgIGNvbnN0IHBhcnRBID0gZGF5anMoYS5lbmREYXRlKVxuICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLnNlY29uZCgwKS5hZGQoMSwgJ20nKSxcbiAgICAgICAgICAgIGRheWpzKG5hLmVuZERhdGUpLnR6KHRpbWV6b25lKS5zZWNvbmQoMCkuc3VidHJhY3QoMSwgJ20nKSxcbiAgICAgICAgICAgICdtJyxcbiAgICAgICAgICAgICdbXSdcbiAgICAgICAgICApO1xuXG4gICAgICAgIGNvbnN0IHBhcnRCID0gZGF5anMoYS5zdGFydERhdGUpXG4gICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKS50eih0aW1lem9uZSkuc2Vjb25kKDApLmFkZCgxLCAnbScpLFxuICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSkudHoodGltZXpvbmUpLnNlY29uZCgwKS5zdWJ0cmFjdCgxLCAnbScpLFxuICAgICAgICAgICAgJ20nLFxuICAgICAgICAgICAgJ1tdJ1xuICAgICAgICAgICk7XG5cbiAgICAgICAgY29uc3QgcGFydEMgPVxuICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSA9PT1cbiAgICAgICAgICAgIGRheWpzKGEuc3RhcnREYXRlKVxuICAgICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpICYmXG4gICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSlcbiAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSA9PT1cbiAgICAgICAgICAgIGRheWpzKGEuZW5kRGF0ZSkudHoodGltZXpvbmUpLnNlY29uZCgwKS5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKTtcblxuICAgICAgICBjb25zdCBpc05vdEF2YWlsYWJsZSA9IHBhcnRBIHx8IHBhcnRCIHx8IHBhcnRDO1xuXG4gICAgICAgIC8vIGNvbnNvbGUubG9nKGEsIG5hLCAnIGEsIG5hJylcblxuICAgICAgICByZXR1cm4gaXNOb3RBdmFpbGFibGU7XG4gICAgICB9KTtcblxuICAgICAgY29uc29sZS5sb2coZm91bmRJbmRleCwgJyBmb3VuZEluZGV4Jyk7XG5cbiAgICAgIGlmIChmb3VuZEluZGV4ICE9PSB1bmRlZmluZWQgJiYgZm91bmRJbmRleCA+IC0xKSB7XG4gICAgICAgIHJldHVybiBmYWxzZTtcbiAgICAgIH1cblxuICAgICAgcmV0dXJuIHRydWU7XG4gICAgfSk7XG5cbiAgY29uc29sZS5sb2coXG4gICAgZmlsdGVyZWRBdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZSxcbiAgICAnIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHMgaW4gcmVjZWl2ZXJUaW1lem9uZSdcbiAgKTtcbiAgLy8gY29udmVydCB0byByZWNlaXZlclRpbWV6b25lIGJlZm9yZSByZXR1cm5pbmcgdmFsdWVzXG4gIHJldHVybiBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lO1xufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlQXZhaWxhYmxlU2xvdHNmb3JUaW1lV2luZG93Rm9yVXNlciA9IChcbiAgd2luZG93U3RhcnREYXRlOiBzdHJpbmcsXG4gIHdpbmRvd0VuZERhdGU6IHN0cmluZyxcbiAgc2xvdER1cmF0aW9uOiBudW1iZXIsXG4gIHVzZXJQcmVmZXJlbmNlczogVXNlclByZWZlcmVuY2VUeXBlLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBub3RBdmFpbGFibGVTbG90c0luRXZlbnRUaW1lem9uZT86IE5vdEF2YWlsYWJsZVNsb3RUeXBlW11cbikgPT4ge1xuICBjb25zdCBkaWZmRGF5cyA9IGRheWpzKHdpbmRvd0VuZERhdGUpLmRpZmYoZGF5anMod2luZG93U3RhcnREYXRlKSwgJ2QnKTtcblxuICBjb25zdCBzdGFydERhdGVzRm9yRWFjaERheSA9IFtdO1xuICBjb25zdCBhdmFpbGFibGVTbG90czogQXZhaWxhYmxlU2xvdFR5cGVbXSA9IFtdO1xuXG4gIGZvciAobGV0IGkgPSAwOyBpIDw9IGRpZmZEYXlzOyBpKyspIHtcbiAgICBzdGFydERhdGVzRm9yRWFjaERheS5wdXNoKFxuICAgICAgZGF5anMod2luZG93U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuYWRkKGksICdkYXknKVxuICAgICAgICAuZm9ybWF0KClcbiAgICApO1xuICB9XG5cbiAgaWYgKGRpZmZEYXlzIDwgMSkge1xuICAgIGNvbnN0IGdlbmVyYXRlZFNsb3RzID0gZ2VuZXJhdGVBdmFpbGFibGVTbG90c0ZvckRhdGVGb3JVc2VyKFxuICAgICAgc2xvdER1cmF0aW9uLFxuICAgICAgZGF5anMod2luZG93U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLmZvcm1hdCgpLFxuICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgdGltZXpvbmUsXG4gICAgICBub3RBdmFpbGFibGVTbG90c0luRXZlbnRUaW1lem9uZSxcbiAgICAgIHRydWUsXG4gICAgICB0cnVlLFxuICAgICAgZGF5anMod2luZG93RW5kRGF0ZS5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoKVxuICAgICk7XG4gICAgLy8gIDAxMjM0NTY3ODlcbiAgICAvLyAgMjAyMC0wNC0wMlQwODowMjoxNy0wNTowMFxuICAgIGF2YWlsYWJsZVNsb3RzLnB1c2goLi4uZ2VuZXJhdGVkU2xvdHMpO1xuICB9IGVsc2Uge1xuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgc3RhcnREYXRlc0ZvckVhY2hEYXkubGVuZ3RoOyBpKyspIHtcbiAgICAgIGNvbnN0IGZpbHRlcmVkTm90QXZhaWxhYmxlU2xvdHNJbkV2ZW50VGltZXpvbmUgPVxuICAgICAgICBub3RBdmFpbGFibGVTbG90c0luRXZlbnRUaW1lem9uZT8uZmlsdGVyKFxuICAgICAgICAgIChuYSkgPT5cbiAgICAgICAgICAgIGRheWpzKG5hPy5zdGFydERhdGUpLnR6KHRpbWV6b25lKS5mb3JtYXQoJ1lZWVktTU0tREQnKSA9PT1cbiAgICAgICAgICAgIGRheWpzKHN0YXJ0RGF0ZXNGb3JFYWNoRGF5Py5baV0pLnR6KHRpbWV6b25lKS5mb3JtYXQoJ1lZWVktTU0tREQnKVxuICAgICAgICApO1xuICAgICAgaWYgKGkgPT09IDApIHtcbiAgICAgICAgY29uc3QgZ2VuZXJhdGVkU2xvdHMgPSBnZW5lcmF0ZUF2YWlsYWJsZVNsb3RzRm9yRGF0ZUZvclVzZXIoXG4gICAgICAgICAgc2xvdER1cmF0aW9uLFxuICAgICAgICAgIHN0YXJ0RGF0ZXNGb3JFYWNoRGF5Py5baV0sXG4gICAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgIGZpbHRlcmVkTm90QXZhaWxhYmxlU2xvdHNJbkV2ZW50VGltZXpvbmUsXG4gICAgICAgICAgdHJ1ZSxcbiAgICAgICAgICBmYWxzZSxcbiAgICAgICAgICBkYXlqcyh3aW5kb3dFbmREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLmZvcm1hdCgpXG4gICAgICAgICk7XG4gICAgICAgIC8vICAwMTIzNDU2Nzg5XG4gICAgICAgIC8vICAyMDIwLTA0LTAyVDA4OjAyOjE3LTA1OjAwXG4gICAgICAgIGF2YWlsYWJsZVNsb3RzLnB1c2goLi4uZ2VuZXJhdGVkU2xvdHMpO1xuXG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfVxuXG4gICAgICBpZiAoaSA9PT0gc3RhcnREYXRlc0ZvckVhY2hEYXkubGVuZ3RoIC0gMSkge1xuICAgICAgICBjb25zdCBnZW5lcmF0ZWRTbG90cyA9IGdlbmVyYXRlQXZhaWxhYmxlU2xvdHNGb3JEYXRlRm9yVXNlcihcbiAgICAgICAgICBzbG90RHVyYXRpb24sXG4gICAgICAgICAgc3RhcnREYXRlc0ZvckVhY2hEYXk/LltpXSxcbiAgICAgICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgZmlsdGVyZWROb3RBdmFpbGFibGVTbG90c0luRXZlbnRUaW1lem9uZSxcbiAgICAgICAgICBmYWxzZSxcbiAgICAgICAgICB0cnVlLFxuICAgICAgICAgIGRheWpzKHdpbmRvd0VuZERhdGUuc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSkuZm9ybWF0KClcbiAgICAgICAgKTtcblxuICAgICAgICBhdmFpbGFibGVTbG90cy5wdXNoKC4uLmdlbmVyYXRlZFNsb3RzKTtcblxuICAgICAgICBjb250aW51ZTtcbiAgICAgIH1cblxuICAgICAgY29uc3QgZ2VuZXJhdGVkU2xvdHMgPSBnZW5lcmF0ZUF2YWlsYWJsZVNsb3RzRm9yRGF0ZUZvclVzZXIoXG4gICAgICAgIHNsb3REdXJhdGlvbixcbiAgICAgICAgc3RhcnREYXRlc0ZvckVhY2hEYXk/LltpXSxcbiAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgZmlsdGVyZWROb3RBdmFpbGFibGVTbG90c0luRXZlbnRUaW1lem9uZVxuICAgICAgKTtcblxuICAgICAgYXZhaWxhYmxlU2xvdHMucHVzaCguLi5nZW5lcmF0ZWRTbG90cyk7XG4gICAgfVxuICB9XG5cbiAgcmV0dXJuIHsgYXZhaWxhYmxlU2xvdHMgfTtcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZUF2YWlsYWJpbGl0eUZvclVzZXIgPSBhc3luYyAoXG4gIGV2ZW50UGFydHM6IEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHdpbmRvd1N0YXJ0RGF0ZTogc3RyaW5nLFxuICB3aW5kb3dFbmREYXRlOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIHNsb3REdXJhdGlvbjogbnVtYmVyXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZyhldmVudFBhcnRzLCAnIGV2ZW50UGFydHMnKTtcblxuICAgIGlmICghZXZlbnRQYXJ0cyB8fCAhKGV2ZW50UGFydHM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gb2xkIGV2ZW50cyBpbiBnZW5lcmF0ZUF2YWlsYWJpbGl0eScpO1xuICAgIH1cblxuICAgIGNvbnN0IG5vdEF2YWlsYWJsZUZyb21FdmVudHM6IE5vdEF2YWlsYWJsZVNsb3RUeXBlW10gPSBldmVudFBhcnRzPy5tYXAoXG4gICAgICAoZSkgPT4gKHtcbiAgICAgICAgc3RhcnREYXRlOiBlPy5zdGFydERhdGUsXG4gICAgICAgIGVuZERhdGU6IGU/LmVuZERhdGUsXG4gICAgICB9KVxuICAgICk7XG5cbiAgICBjb25zdCB1c2VyUHJlZmVyZW5jZXMgPSBhd2FpdCBnZXRVc2VyUHJlZmVyZW5jZXModXNlcklkKTtcblxuICAgIGNvbnN0IHsgYXZhaWxhYmxlU2xvdHM6IGF2YWlsYWJsZVNsb3RzIH0gPVxuICAgICAgYXdhaXQgZ2VuZXJhdGVBdmFpbGFibGVTbG90c2ZvclRpbWVXaW5kb3dGb3JVc2VyKFxuICAgICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICAgIHNsb3REdXJhdGlvbixcbiAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgbm90QXZhaWxhYmxlRnJvbUV2ZW50cz8ubGVuZ3RoID4gMCA/IG5vdEF2YWlsYWJsZUZyb21FdmVudHMgOiB1bmRlZmluZWRcbiAgICAgICk7XG5cbiAgICByZXR1cm4gYXZhaWxhYmxlU2xvdHM7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZW5lcmF0ZSBhdmFpbGFiaWxpdHknKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGNvbnZlcnRBdmFpbGFibGVTbG90c1RvVGltZVNsb3RMaWtlID0gKFxuICBhdmFpbGFibGVTbG90czogQXZhaWxhYmxlU2xvdFR5cGVbXSxcbiAgdGltZXpvbmU6IHN0cmluZ1xuKSA9PiB7XG4gIC8vIEF2YWlsYWJsZVRpbWVTbG90VHlwZVxuICAvLyBBdmFpbGFibGVTbG90VHlwZVtdXG5cbiAgaWYgKCEoYXZhaWxhYmxlU2xvdHM/Lmxlbmd0aCA+IDApKSB7XG4gICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgJ25vIGF2YWlsYWJsZSBzbG90cyBwcm92aWRlZCBpbnNpZGUgY29udmVydEF2YWlsYWJsZVNsb3RzVG9UaW1lU2xvdExpa2UnXG4gICAgKTtcbiAgfVxuXG4gIGNvbnN0IGF2YWlsYWJsZVRpbWVTbG90czogQXZhaWxhYmxlVGltZVNsb3RUeXBlW10gPSBbXTtcbiAgZm9yIChjb25zdCBhdmFpbGFibGVTbG90IG9mIGF2YWlsYWJsZVNsb3RzKSB7XG4gICAgY29uc3QgYXZhaWxhYmxlVGltZVNsb3Q6IEF2YWlsYWJsZVRpbWVTbG90VHlwZSA9IHtcbiAgICAgIHN0YXJ0VGltZTpcbiAgICAgICAgYCR7ZGF5anMoYXZhaWxhYmxlU2xvdD8uc3RhcnREYXRlKS50eih0aW1lem9uZSkuZm9ybWF0KCdISDptbScpfWAgYXMgVGltZSxcbiAgICAgIGVuZFRpbWU6XG4gICAgICAgIGAke2RheWpzKGF2YWlsYWJsZVNsb3Q/LmVuZERhdGUpLnR6KHRpbWV6b25lKS5mb3JtYXQoJ0hIOm1tJyl9YCBhcyBUaW1lLFxuICAgICAgbW9udGhEYXk6XG4gICAgICAgIGAtLSR7ZGF5anMoYXZhaWxhYmxlU2xvdD8uc3RhcnREYXRlKS50eih0aW1lem9uZSkuZm9ybWF0KCdNTS1ERCcpfWAgYXMgTW9udGhEYXlUeXBlLFxuICAgIH07XG5cbiAgICBhdmFpbGFibGVUaW1lU2xvdHMucHVzaChhdmFpbGFibGVUaW1lU2xvdCk7XG4gIH1cblxuICByZXR1cm4gYXZhaWxhYmxlVGltZVNsb3RzO1xufTtcblxuZXhwb3J0IGNvbnN0IGZpbHRlclRpbWVzbG90c0dpdmVuSW1tb2RpZmlhYmxlRXZlbnRzID0gYXN5bmMgKFxuICBldmVudFBhcnRzOiBFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlW10sXG4gIHRpbWVzbG90czogVGltZVNsb3RUeXBlW10sXG4gIHVzZXJJZDogc3RyaW5nLFxuICB3aW5kb3dTdGFydERhdGU6IHN0cmluZyxcbiAgd2luZG93RW5kRGF0ZTogc3RyaW5nLFxuICB0aW1lem9uZSxcbiAgc2xvdER1cmF0aW9uOiBudW1iZXJcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGF2YWlsYWJsZVNsb3RzID0gYXdhaXQgZ2VuZXJhdGVBdmFpbGFiaWxpdHlGb3JVc2VyKFxuICAgICAgZXZlbnRQYXJ0cyxcbiAgICAgIHVzZXJJZCxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHNsb3REdXJhdGlvblxuICAgICk7XG4gICAgY29uc3QgYXZhaWxhYmxlVGltZVNsb3RzID0gY29udmVydEF2YWlsYWJsZVNsb3RzVG9UaW1lU2xvdExpa2UoXG4gICAgICBhdmFpbGFibGVTbG90cyxcbiAgICAgIHRpbWV6b25lXG4gICAgKTtcblxuICAgIGNvbnN0IGZpbHRlcmVkVGltZVNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBhdmFpbGFibGVUaW1lU2xvdCBvZiBhdmFpbGFibGVUaW1lU2xvdHMpIHtcbiAgICAgIGZvciAoY29uc3QgdGltZXNsb3Qgb2YgdGltZXNsb3RzKSB7XG4gICAgICAgIGlmIChcbiAgICAgICAgICBhdmFpbGFibGVUaW1lU2xvdD8uc3RhcnRUaW1lID09PSB0aW1lc2xvdD8uc3RhcnRUaW1lICYmXG4gICAgICAgICAgYXZhaWxhYmxlVGltZVNsb3Q/LmVuZFRpbWUgPT09IHRpbWVzbG90Py5lbmRUaW1lICYmXG4gICAgICAgICAgYXZhaWxhYmxlVGltZVNsb3Q/Lm1vbnRoRGF5ID09PSB0aW1lc2xvdD8ubW9udGhEYXlcbiAgICAgICAgKSB7XG4gICAgICAgICAgZmlsdGVyZWRUaW1lU2xvdHMucHVzaCh0aW1lc2xvdCk7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhmaWx0ZXJlZFRpbWVTbG90cywgJyBmaWx0ZXJlZFRpbWVTbG90cycpO1xuXG4gICAgcmV0dXJuIGZpbHRlcmVkVGltZVNsb3RzO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgZmlsdGVyVGltZXNsb3RzR2l2ZW5JbW1vZGlmaWFibGVFdmVudHMnKTtcbiAgfVxufTtcbiJdfQ==