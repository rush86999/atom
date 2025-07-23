


import _ from 'lodash'
import { v4 as uuid } from 'uuid'
import { Dispatch, SetStateAction } from 'react'
import { RRule } from 'rrule'

import { dayjs, } from '@lib/date-utils'

import {
  createGoogleEvent,
} from '@lib/calendarLib/googleCalendarHelper'

import { palette } from '@lib/theme/theme'

import {
  CalendarType,
} from '@lib/dataTypes/CalendarType'
import {
  Time,
  BufferTimeType,
} from '@lib/dataTypes/EventType'
import {
  CalendarIntegrationType,
} from '@lib/dataTypes/Calendar_IntegrationType'
import {
  EventType,
  RecurrenceRuleType,
  AttachmentType,
  LocationType,
  CreatorType,
  OrganizerType,
  ExtendedPropertiesType,
  SourceType,
  LinkType,
} from '@lib/dataTypes/EventType'
import {
  googleMeetName,
  googleResourceName,
  localCalendarName,
  localCalendarResource,
} from '@lib/calendarLib/constants'
import {
  GoogleAttendeeType,
  ConferenceDataType,
  GoogleReminderType,
  SendUpdatesType,
  TransparencyType,
  VisibilityType,
} from '@lib/calendarLib/types'
import {
  zoomName,
  zoomResourceName,
} from '@lib/zoom/constants'
import {
  zoomAvailable,
  createZoomMeeting,
} from '@lib/zoom/zoomMeetingHelper'
import {
  accessRole,
  Person,
  RecurrenceFrequencyType,
  TagType,
} from '@lib/Calendar/types'
import {
  upsertCategoryEventConnection,
} from '@lib/Category/CategoryHelper'
import {
  createReminderForEvent,
} from '@lib/Calendar/Reminder/ReminderHelper'
import {
  ParameterType,
  EntryPointType,
  AppType,
  ConferenceNameType,
  ConferenceType,
} from '@lib/dataTypes/ConferenceType'
import { upsertAttendeesInDb } from '@lib/Calendar/Attendee/AttendeeHelper'

import { ApolloClient, NormalizedCacheObject, gql } from '@apollo/client';
import getCalendarById from '@lib/apollo/gql/getCalendarById'
import getGlobalPrimaryCalendar from '@lib/apollo/gql/getGlobalPrimaryCalendar'
import getAnyCalendar from '@lib/apollo/gql/getAnyCalendar'
import getCalendarWithResource from '@lib/apollo/gql/getCalendarWithResource'
import getCalendarIntegrationByResource from '@lib/apollo/gql/getCalendarIntegrationByResourceAndName'
import listAllEvents from '@lib/apollo/gql/listAllEvents'
import listCategoriesForEvents from '@lib/apollo/gql/listCategoriesForEvents'
import getConferenceById from '@lib/apollo/gql/getConferenceById'
import deleteEventById from '@lib/apollo/gql/deleteEventById'
import { CategoryEventType } from '@lib/dataTypes/Category_EventType'
import {
  type Event as CalendarEvent,
  type stringOrDate,
} from 'react-big-calendar'
import { Day } from '@lib/Schedule/constants'

export type CalendarEventPro = CalendarEvent & {
  // eventId#calendarId
  id: string,
  calendarId: string,
  eventId: string,
  color?: string,
  notes?: string,
  tags: TagType[],
  unlink: boolean,
  modifiable: boolean,
  priority: number,
  recurringEndDate?: string,
  frequency?: RecurrenceFrequencyType,
  interval?: string,
}


export interface NewEventTime {
  hour: number;
  minutes: number;
  date?: string;
}

export const reformatToCalendarEventsUIWebForCalendarFromDb = async (
  events: EventType[],
  client: ApolloClient<NormalizedCacheObject>,
) => {
  try {

    console.log(events, ' events inside reformatToEventsUIForCalendarFromDb')
    if (!(events?.length > 0)) {
      return
    }

    const tags = (await client.query<{ Category_Event: CategoryEventType[] }>({
      query: listCategoriesForEvents,
      variables: {
        eventIds: events?.map(e => e.id),
      },
    }))?.data?.Category_Event?.map(c => ({
      id: c.Category.id,
      name: c.Category.name,
      color: c.Category.color,
      eventId: c.eventId,
    }))


    const eventsModified: CalendarEventPro[] = events?.map((e) => {

      const tagsForEvent = tags?.filter(t => (t.eventId === e.id))
      const tagsModified = tagsForEvent?.map(t => ({
        id: t.id,
        name: t.name,
        color: t.color
      }))

      return {
        id: e?.id,
        start: dayjs.tz(e?.startDate.slice(0, 19), e?.timezone || dayjs.tz.guess()).toDate(),
        end: dayjs.tz(e?.endDate.slice(0, 19), e?.timezone || dayjs.tz.guess()).toDate(),
        title: e?.title || e?.summary,
        allDay: e?.allDay,
        calendarId: e?.calendarId,
        eventId: e?.eventId,
        color: tagsForEvent?.[0]?.color || e?.backgroundColor,
        notes: e?.notes,
        tags: tagsModified,
        unlink: e?.unlink,
        modifiable: e?.modifiable,
        priority: e?.priority,
        recurringEndDate: e?.recurrenceRule?.endDate,
        frequency: e?.recurrenceRule?.frequency as RecurrenceFrequencyType,
        interval: `${e?.recurrenceRule?.interval}`,
      }

    })

    return eventsModified
  } catch (e) {
    console.log(e, ' unable to reformat to calendar events UI for web')
  }
}


export const setCurrentEventsForCalendarWeb = async (
  userId: string,
  client: ApolloClient<NormalizedCacheObject>,
  setCalendarEvents: Dispatch<SetStateAction<CalendarEventPro[]>>,

) => {
  try {
    // validate
    if (!userId) {
      console.log('no userId inside setCurrentEventsForCalendar')
      return
    }
    if (!client) {
      console.log('no client inside setCurrentEventsForCalendar')
      return
    }

    const eventsFromDb = await getCurrentEvents(client, userId)
    console.log(eventsFromDb, ' eventsFromDb inside setCurrentEventsForCalendar')

    const events = await reformatToCalendarEventsUIWebForCalendarFromDb(eventsFromDb, client)

    setCalendarEvents(events)
  } catch (e) {
    console.log(e, ' unable to set current for calendar web')
  }
}

// do it by limit operator
export const getCurrentEvents = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
) => {
  try {
    const { data } = await client.query<{ Event: EventType[] }>({
      query: listAllEvents,
      variables: {
        userId,
        start: dayjs().subtract(2, 'y').format(),
        end: dayjs().add(2, 'y').format(),
      },
      fetchPolicy: 'no-cache'
    })

    return data?.Event

  } catch (e) {
    console.log(e, ' unable to get current events')
  }
}


/**
{
  id?: string;
  start: string; format --> YY-MM-DD HH:MM:ss
  end: string;
  title: string;
  summary?: string;
  color?: string;
}
 */



export const getCalendarInDb = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  calendarId?: string,
  globalPrimary?: boolean,
  resource?: string,
) => {
  try {
    if (calendarId) {
      const calendar = (await client.query<{ Calendar_by_pk: CalendarType }>({
        query: getCalendarById,
        variables: {
          id: calendarId,
        },
      })).data?.Calendar_by_pk
      return calendar
    } else if (globalPrimary && !calendarId) {
      const calendar = (await client.query<{ Calendar: CalendarType[] }>({
        query: getGlobalPrimaryCalendar,
        variables: {
          userId,
        },
      })).data?.Calendar?.[0]
      return calendar
    } else if (!globalPrimary && !calendarId && !resource) {
      const calendar = (await client.query<{ Calendar: CalendarType[] }>({
        query: getAnyCalendar,
        variables: {
          userId,
        },
      })).data?.Calendar?.[0]
      return calendar
    } else if (!globalPrimary && !calendarId && resource?.length > 0) {
      const calendar = (await client.query<{ Calendar: CalendarType[] }>({
        query: getCalendarWithResource,
        variables: {
          userId,
          resource,
        },
      })).data?.Calendar?.[0]
      return calendar
    }

  } catch (e) {
    console.log(e, ' unable to get calendar from collection')
  }
}

export const upsertLocalCalendar = async (
  client: ApolloClient<NormalizedCacheObject>,
  id: string,
  userId: string,
  title: string,
  backgroundColor: string,
  accessLevel?: accessRole,
  resource?: string,
  globalPrimary?: boolean,
  foregroundColor?: string,
) => {
  try {
    const calendarValueToUpsert = {
      id,
      userId,
      title,
      backgroundColor,
      accessLevel,
      resource,
      globalPrimary,
      deleted: false,
      createdDate: dayjs().toISOString(),
      updatedAt: dayjs().toISOString(),
    }

    // ASSUMPTION: A custom PG function 'upsertCalendar' handles the upsert logic.
    // Dynamic update_columns are now part of the PG function's ON CONFLICT clause.
    const upsertCalendarMutation = gql`
    mutation UpsertCalendar($calendar: CalendarInput!) { # Assuming CalendarInput is the type for a single calendar
      upsertCalendar(input: { calendar: $calendar }) { # Standard PostGraphile mutation input pattern
        calendar { # Assuming the payload returns the calendar
          id
          # Include other fields as needed from CalendarType if they are returned
        }
      }
    }
  `
    // The type for client.mutate and variable preparation will need to adjust.
    const result = await client.mutate<{ upsertCalendar: { calendar: { id: string } } }>({ // Adjust return type
      mutation: upsertCalendarMutation,
      variables: {
        calendar: calendarValueToUpsert, // Pass the single object
      },
    })

    return result.data?.upsertCalendar?.calendar // Adjust access to returned data

  } catch (e) {
    console.log(e, ' unable to save local calendar')
  }
}


export const getRruleFreq = (
  freq: RecurrenceFrequencyType
) => {
  switch (freq) {
    case 'daily':
      return RRule.DAILY
    case 'weekly':
      return RRule.WEEKLY
    case 'monthly':
      return RRule.MONTHLY
    case 'yearly':
      return RRule.YEARLY
  }
}

export const atomicUpsertEventInDb = async (
  client: ApolloClient<NormalizedCacheObject>,
  id: string,
  eventId: string,
  userId: string,
  startDate?: string,
  endDate?: string,
  createdDate?: string,
  deleted?: boolean,
  priority?: number,
  isFollowUp?: boolean,
  isPreEvent?: boolean,
  isPostEvent?: boolean,
  modifiable?: boolean,
  anyoneCanAddSelf?: boolean,
  guestsCanInviteOthers?: boolean,
  guestsCanSeeOtherGuests?: boolean,
  originalStartDate?: string,
  originalAllDay?: boolean,
  updatedAt?: string,
  calendarId?: string,
  title?: string,
  allDay?: boolean,
  recurrenceRule?: RecurrenceRuleType,
  location?: LocationType,
  notes?: string,
  attachments?: AttachmentType[],
  links?: LinkType[],
  // alarms?: alarms,
  timezone?: string,
  taskId?: string,
  taskType?: string,
  followUpEventId?: string,
  preEventId?: string,
  postEventId?: string,
  forEventId?: string,
  conferenceId?: string,
  maxAttendees?: number,
  sendUpdates?: SendUpdatesType,
  status?: string,
  summary?: string,
  transparency?: TransparencyType,
  visibility?: VisibilityType,
  recurringEventId?: string,
  iCalUID?: string,
  htmlLink?: string,
  colorId?: string,
  creator?: CreatorType,
  organizer?: OrganizerType,
  endTimeUnspecified?: boolean,
  recurrence?: string[],
  originalTimezone?: string,
  attendeesOmitted?: boolean,
  extendedProperties?: ExtendedPropertiesType,
  hangoutLink?: string,
  guestsCanModify?: boolean,
  locked?: boolean,
  source?: SourceType,
  eventType?: string,
  privateCopy?: boolean,
  backgroundColor?: string,
  foregroundColor?: string,
  useDefaultAlarms?: boolean,
  positiveImpactScore?: number,
  negativeImpactScore?: number,
  positiveImpactDayOfWeek?: number,
  positiveImpactTime?: Time,
  negativeImpactDayOfWeek?: number,
  negativeImpactTime?: Time,
  preferredDayOfWeek?: number,
  preferredTime?: Time,
  isExternalMeeting?: boolean,
  isExternalMeetingModifiable?: boolean,
  isMeetingModifiable?: boolean,
  isMeeting?: boolean,
  dailyTaskList?: boolean,
  weeklyTaskList?: boolean,
  isBreak?: boolean,
  preferredStartTimeRange?: Time,
  preferredEndTimeRange?: Time,
  copyAvailability?: boolean,
  copyTimeBlocking?: boolean,
  copyTimePreference?: boolean,
  copyReminders?: boolean,
  copyPriorityLevel?: boolean,
  copyModifiable?: boolean,
  copyCategories?: boolean,
  copyIsBreak?: boolean,
  timeBlocking?: BufferTimeType,
  userModifiedAvailability?: boolean,
  userModifiedTimeBlocking?: boolean,
  userModifiedTimePreference?: boolean,
  userModifiedReminders?: boolean,
  userModifiedPriorityLevel?: boolean,
  userModifiedCategories?: boolean,
  userModifiedModifiable?: boolean,
  userModifiedIsBreak?: boolean,
  hardDeadline?: string,
  softDeadline?: string,
  copyIsMeeting?: boolean,
  copyIsExternalMeeting?: boolean,
  userModifiedIsMeeting?: boolean,
  userModifiedIsExternalMeeting?: boolean,
  duration?: number,
  copyDuration?: boolean,
  userModifiedDuration?: boolean,
  method?: 'create' | 'update',
  unlink?: boolean,
  byWeekDay?: Day[],
  localSynced?: boolean,
  copyColor?: boolean,
  userModifiedColor?: boolean,
  meetingId?: string,
) => {
  try {
    console.log(hardDeadline, softDeadline, ' hardDeadline, softDeadline inside atomicUpsertEventInDb')
    // ASSUMPTION: A custom PG function 'upsertEvent' handles the complex upsert logic.
    // The extensive dynamic update_columns list is now part of the PG function's ON CONFLICT clause.
    // The input type will be something like EventInput!
    const upsertEventMutation = gql`
      mutation UpsertEvent($event: EventInput!) { # Assuming EventInput is the type for a single event
        upsertEvent(input: { event: $event }) { # Standard PostGraphile mutation input pattern
          event { # Assuming the payload returns the event
            # It's crucial that the 'returning' fields here match what PostGraphile actually returns
            # based on the PG function's RETURNING clause and PostGraphile's schema generation.
            # This is a best guess based on the original Hasura query.
            # Many of these might be objects or need different casing (camelCase).
            id
            startDate
            endDate
                  allDay
                  recurrence
                  recurrenceRule
                  location
                  notes
                  attachments
                  links
                  timezone
                  taskId
                  taskType
                  priority
                  followUpEventId
                  isFollowUp
                  isPreEvent
                  isPostEvent
                  preEventId
                  postEventId
                  modifiable
                  forEventId
                  conferenceId
                  maxAttendees
                  attendeesOmitted
                  sendUpdates
                  anyoneCanAddSelf
                  guestsCanInviteOthers
                  guestsCanSeeOtherGuests
                  originalStartDate
                  originalTimezone
                  originalAllDay
                  status
                  summary
                  title
                  transparency
                  visibility
                  recurringEventId
                  iCalUID
                  htmlLink
                  colorId
                  creator
                  organizer
                  endTimeUnspecified
                  extendedProperties
                  hangoutLink
                  guestsCanModify
                  locked
                  source
                  eventType
                  privateCopy
                  backgroundColor
                  foregroundColor
                  useDefaultAlarms
                  deleted
                  createdDate
                  updatedAt
                  userId
                  calendarId
                  positiveImpactScore
                  negativeImpactScore
                  positiveImpactDayOfWeek
                  positiveImpactTime
                  negativeImpactDayOfWeek
                  negativeImpactTime
                  preferredDayOfWeek
                  preferredTime
                  isExternalMeeting
                  isExternalMeetingModifiable
                  isMeetingModifiable
                  isMeeting
                  dailyTaskList
                  weeklyTaskList
                  isBreak
                  preferredStartTimeRange
                  preferredEndTimeRange
                  copyAvailability
                  copyTimeBlocking
                  copyTimePreference
                  copyReminders
                  copyPriorityLevel
                  copyModifiable
                  copyCategories
                  copyIsBreak
                  userModifiedAvailability
                  userModifiedTimeBlocking
                  userModifiedTimePreference
                  userModifiedReminders
                  userModifiedPriorityLevel
                  userModifiedCategories
                  userModifiedModifiable
                  userModifiedIsBreak
                  hardDeadline
                  softDeadline
                  copyIsMeeting
                  copyIsExternalMeeting
                  userModifiedIsMeeting
                  userModifiedIsExternalMeeting
                  duration
                  copyDuration
                  userModifiedDuration
                  method
                  unlink
                  copyColor
                  userModifiedColor
                  byWeekDay
                  localSynced
                  timeBlocking
                  meetingId
                  eventId
                }
                # affected_rows # This is not standard in PostGraphile return types for mutations like this.
                                # The upserted event itself is the primary return.
              }
            }
          `
    let event: EventType = { // This object is used to build the 'variables' for the mutation.
                             // Its structure must match 'EventInput' expected by PostGraphile.
                             // Many fields might be optional or have different casing (camelCase).
      id,
      eventId, // Ensure this and other IDs are correctly mapped if casing changes (e.g. eventID)
      meetingId,
      userId,
      startDate,
      endDate,
      createdDate, // Usually set by DB
      deleted,
      priority: 1,
      isFollowUp: false,
      isPreEvent: false,
      isPostEvent: false,
      modifiable: false,
      anyoneCanAddSelf: false,
      guestsCanInviteOthers: false,
      guestsCanSeeOtherGuests: false,
      originalStartDate: undefined,
      originalAllDay: false,
      updatedAt: undefined, // Usually set by DB
      calendarId: undefined,
      // Ensure all fields below are correctly cased (camelCase) and match EventInput
    }
    /**
     * 
        priority,
        isFollowUp,
        isPreEvent,
        isPostEvent,
        modifiable,
        anyoneCanAddSelf,
        guestsCanInviteOthers,
        guestsCanSeeOtherGuests,
        originalStartDate,
        originalAllDay,
        updatedAt,
        calendarId,
        title,
        allDay,
        recurrenceRule,
        location,
        notes,
        attachments,
        links,
        timezone,
        taskId,
        taskType,
        followUpEventId,
        preEventId,
        postEventId,
        forEventId,
        conferenceId,
        maxAttendees,
        sendUpdates,
        status,
        summary,
        transparency,
        visibility,
        recurringEventId,
        iCalUID,
        htmlLink,
        colorId,
        creator,
        organizer,
        endTimeUnspecified,
        recurrence,
        originalTimezone,
        attendeesOmitted,
        hangoutLink,
        guestsCanModify,
        locked,
        source,
        eventType,
        privateCopy,
        backgroundColor,
        foregroundColor,
        useDefaultAlarms,
        positiveImpactScore,
        negativeImpactScore,
        positiveImpactDayOfWeek,
        positiveImpactTime,
        negativeImpactDayOfWeek,
        negativeImpactTime,
        preferredDayOfWeek,
        preferredTime,
        isExternalMeeting,
        isExternalMeetingModifiable,
        isMeetingModifiable,
        isMeeting,
        dailyTaskList,
        weeklyTaskList,
        isBreak,
        preferredStartTimeRange,
        preferredEndTimeRange,
        copyAvailability,
        copyTimeBlocking,
        copyTimePreference,
        copyReminders,
        copyPriorityLevel,
        copyModifiable,
        copyCategories,
        copyIsBreak,
        timeBlocking,
        userModifiedAvailability,
        userModifiedTimeBlocking,
        userModifiedTimePreference,
        userModifiedReminders,
        userModifiedPriorityLevel,
        userModifiedCategories,
        userModifiedModifiable,
        userModifiedIsBreak,
        hardDeadline,
        softDeadline,
        copyIsMeeting,
        copyIsExternalMeeting,
        userModifiedIsMeeting,
        userModifiedIsExternalMeeting,
        duration,
        copyDuration,
        userModifiedDuration,
        method,
        unlink,
        copyColor,
        userModifiedColor,
        byWeekDay,
        localSynced,
     */

    if (priority) {
      event.priority = priority
    }

    if (isFollowUp !== undefined) {
      event.isFollowUp = isFollowUp
    }

    if (isPreEvent !== undefined) {
      event.isPreEvent = isPreEvent
    }

    if (isPostEvent !== undefined) {
      event.isPostEvent = isPostEvent
    }

    if (modifiable !== undefined) {
      event.modifiable = modifiable
    }

    if (anyoneCanAddSelf !== undefined) {
      event.anyoneCanAddSelf = anyoneCanAddSelf
    }

    if (guestsCanInviteOthers !== undefined) {
      event.guestsCanInviteOthers = guestsCanInviteOthers
    }

    if (guestsCanSeeOtherGuests !== undefined) {
      event.guestsCanSeeOtherGuests = guestsCanSeeOtherGuests
    }

    if (originalStartDate !== undefined) {
      event.originalStartDate = originalStartDate
    }

    if (originalAllDay !== undefined) {
      event.originalAllDay = originalAllDay
    }

    if (updatedAt !== undefined) {
      event.updatedAt = updatedAt
    }

    if (calendarId !== undefined) {
      event.calendarId = calendarId
    }

    if (title !== undefined) {
      event.title = title
    }

    if (allDay !== undefined) {
      event.allDay = allDay
    }

    if (recurrenceRule !== undefined) {
      event.recurrenceRule = recurrenceRule
    }

    if (location !== undefined) {
      event.location = location
    }

    if (notes !== undefined) {
      event.notes = notes
    }

    if (attachments !== undefined) {
      event.attachments = attachments
    }

    if (links !== undefined) {
      event.links = links
    }

    if (timezone !== undefined) {
      event.timezone = timezone
    }

    if (taskId !== undefined) {
      event.taskId = taskId
    }

    if (taskType !== undefined) {
      event.taskType = taskType
    }

    if (followUpEventId !== undefined) {
      event.followUpEventId = followUpEventId
    }

    if (preEventId !== undefined) {
      event.preEventId = preEventId
    }

    if (postEventId !== undefined) {
      event.postEventId = postEventId
    }

    if (forEventId !== undefined) {
      event.forEventId = forEventId
    }

    if (conferenceId !== undefined) {
      event.conferenceId = conferenceId
    }

    if (maxAttendees !== undefined) {
      event.maxAttendees = maxAttendees
    }

    if (sendUpdates !== undefined) {
      event.sendUpdates = sendUpdates
    }

    if (status !== undefined) {
      event.status = status
    }

    if (summary !== undefined) {
      event.summary = summary
    }

    if (transparency !== undefined) {
      event.transparency = transparency
    }

    if (visibility !== undefined) {
      event.visibility = visibility
    }

    if (recurringEventId !== undefined) {
      event.recurringEventId = recurringEventId
    }

    if (iCalUID !== undefined) {
      event.iCalUID = iCalUID
    }

    if (htmlLink !== undefined) {
      event.htmlLink = htmlLink
    }

    if (colorId !== undefined) {
      event.colorId = colorId
    }

    if (creator !== undefined) {
      event.creator = creator
    }

    if (organizer !== undefined) {
      event.organizer = organizer
    }

    if (endTimeUnspecified !== undefined) {
      event.endTimeUnspecified = endTimeUnspecified
    }

    if (recurrence !== undefined) {
      event.recurrence = recurrence
    }

    if (originalTimezone !== undefined) {
      event.originalTimezone = originalTimezone
    }

    if (attendeesOmitted !== undefined) {
      event.attendeesOmitted = attendeesOmitted
    }

    if (hangoutLink !== undefined) {
      event.hangoutLink = hangoutLink
    }

    if (guestsCanModify !== undefined) {
      event.guestsCanModify = guestsCanModify
    }

    if (locked !== undefined) {
      event.locked = locked
    }

    if (source !== undefined) {
      event.source = source
    }

    if (eventType !== undefined) {
      event.eventType = eventType
    }

    if (privateCopy !== undefined) {
      event.privateCopy = privateCopy
    }

    if (guestsCanSeeOtherGuests !== undefined) {
      event.guestsCanSeeOtherGuests = guestsCanSeeOtherGuests
    }

    if (backgroundColor !== undefined) {
      event.backgroundColor = backgroundColor
    }

    if (foregroundColor !== undefined) {
      event.foregroundColor = foregroundColor
    }

    if (useDefaultAlarms !== undefined) {
      event.useDefaultAlarms = useDefaultAlarms
    }

    if (positiveImpactScore !== undefined) {
      event.positiveImpactScore = positiveImpactScore
    }

    if (negativeImpactScore !== undefined) {
      event.negativeImpactScore = negativeImpactScore
    }

    if (positiveImpactDayOfWeek !== undefined) {
      event.positiveImpactDayOfWeek = positiveImpactDayOfWeek
    }

    if (negativeImpactDayOfWeek !== undefined) {
      event.negativeImpactDayOfWeek = negativeImpactDayOfWeek
    }

    if (positiveImpactTime !== undefined) {
      event.positiveImpactTime = positiveImpactTime
    }

    if (negativeImpactTime !== undefined) {
      event.negativeImpactTime = negativeImpactTime
    }

    if (preferredDayOfWeek !== undefined) {
      event.preferredDayOfWeek = preferredDayOfWeek
    }

    if (preferredTime !== undefined) {
      event.preferredTime = preferredTime
    }

    if (isExternalMeeting !== undefined) {
      event.isExternalMeeting = isExternalMeeting
    }

    if (isExternalMeetingModifiable !== undefined) {
      event.isExternalMeetingModifiable = isExternalMeetingModifiable
    }

    if (isMeetingModifiable !== undefined) {
      event.isMeetingModifiable = isMeetingModifiable
    }

    if (isMeeting !== undefined) {
      event.isMeeting = isMeeting
    }

    if (dailyTaskList !== undefined) {
      event.dailyTaskList = dailyTaskList
    }

    if (weeklyTaskList !== undefined) {
      event.weeklyTaskList = weeklyTaskList
    }

    if (isBreak !== undefined) {
      event.isBreak = isBreak
    }

    if (preferredStartTimeRange !== undefined) {
      event.preferredStartTimeRange = preferredStartTimeRange
    }

    if (preferredEndTimeRange !== undefined) {
      event.preferredEndTimeRange = preferredEndTimeRange
    }

    if (copyAvailability !== undefined) {
      event.copyAvailability = copyAvailability
    }

    if (copyTimeBlocking !== undefined) {
      event.copyTimeBlocking = copyTimeBlocking
    }

    if (copyTimePreference !== undefined) {
      event.copyTimePreference = copyTimePreference
    }

    if (copyReminders !== undefined) {
      event.copyReminders = copyReminders
    }

    if (copyPriorityLevel !== undefined) {
      event.copyPriorityLevel = copyPriorityLevel
    }

    if (copyModifiable !== undefined) {
      event.copyModifiable = copyModifiable
    }

    if (copyCategories !== undefined) {
      event.copyCategories = copyCategories
    }

    if (copyIsBreak !== undefined) {
      event.copyIsBreak = copyIsBreak
    }

    if (timeBlocking !== undefined) {
      event.timeBlocking = timeBlocking
    }

    if (userModifiedAvailability !== undefined) {
      event.userModifiedAvailability = userModifiedAvailability
    }

    if (userModifiedTimeBlocking !== undefined) {
      event.userModifiedTimeBlocking = userModifiedTimeBlocking
    }

    if (userModifiedTimePreference !== undefined) {
      event.userModifiedTimePreference = userModifiedTimePreference
    }

    if (userModifiedReminders !== undefined) {
      event.userModifiedReminders = userModifiedReminders
    }

    if (userModifiedPriorityLevel !== undefined) {
      event.userModifiedPriorityLevel = userModifiedPriorityLevel
    }

    if (userModifiedCategories !== undefined) {
      event.userModifiedCategories = userModifiedCategories
    }

    if (userModifiedModifiable !== undefined) {
      event.userModifiedModifiable = userModifiedModifiable
    }

    if (userModifiedIsBreak !== undefined) {
      event.userModifiedIsBreak = userModifiedIsBreak
    }

    if (hardDeadline !== undefined) {
      event.hardDeadline = hardDeadline
    }

    if (softDeadline !== undefined) {
      event.softDeadline = softDeadline
    }

    if (copyIsMeeting !== undefined) {
      event.copyIsMeeting = copyIsMeeting
    }

    if (copyIsExternalMeeting !== undefined) {
      event.copyIsExternalMeeting = copyIsExternalMeeting
    }

    if (userModifiedIsMeeting !== undefined) {
      event.userModifiedIsMeeting = userModifiedIsMeeting
    }

    if (userModifiedIsExternalMeeting !== undefined) {
      event.userModifiedIsExternalMeeting = userModifiedIsExternalMeeting
    }

    if (duration !== undefined) {
      event.duration = duration
    }

    if (copyDuration !== undefined) {
      event.copyDuration = copyDuration
    }

    if (userModifiedDuration !== undefined) {
      event.userModifiedDuration = userModifiedDuration
    }

    if (method !== undefined) {
      event.method = method
    }

    if (unlink !== undefined) {
      event.unlink = unlink
    }

    if (copyColor !== undefined) {
      event.copyColor = copyColor
    }

    if (userModifiedColor !== undefined) {
      event.userModifiedColor = userModifiedColor
    }

    if (byWeekDay !== undefined) {
      event.byWeekDay = byWeekDay
    }

    if (localSynced !== undefined) {
      event.localSynced = localSynced
    }

    event.eventId = eventId

    if (meetingId !== undefined) {
      event.meetingId = meetingId
    }

    console.log(event, ' event inside atomicUpsertEventInDb')
    const variables = {
      event: event // Pass the single event object, matching the $event: EventInput! in the mutation
    }

    // Adjust the generic type for client.mutate based on the actual PostGraphile mutation payload
    const response = await client.mutate<{ upsertEvent: { event: EventType } }>({
      mutation: upsertEventMutation, // Use the renamed mutation variable
      variables,
      // refetchQueries might be a more robust way to handle cache updates initially
      // refetchQueries: [
      //   { query: listAllEvents, variables: { /* appropriate variables for listAllEvents */ } }
      // ],
      update(cache, { data }) {
        const upsertedEvent = data?.upsertEvent?.event;
        if (upsertedEvent) {
          console.log('upsertEvent result', upsertedEvent);

          // The cache update logic here is highly speculative and needs verification.
          // It assumes a root field 'Event' for a list, which is unlikely with PostGraphile.
          // It would more likely be 'allEvents' or a similar connection field.
          cache.modify({
            fields: {
              // This field name 'Event' is likely incorrect for PostGraphile.
              Event: (existingEvents = [], { readField }) => { // Placeholder for existing cache update logic
                // Attempt to find and replace or add the new event.
                // This simple replacement might not work well with pagination or complex list structures.
                const newEventRef = cache.writeFragment({
                  data: upsertedEvent,
                  fragment: gql`
                    fragment NewEvent on Event { # Type name 'Event' should be checked against PostGraphile schema
                      id
                      startDate
                      endDate
                      allDay
                      recurrence
                      recurrenceRule
                      location
                      notes
                      attachments
                      links
                      timezone
                      taskId
                      taskType
                      priority
                      followUpEventId
                      isFollowUp
                      isPreEvent
                      isPostEvent
                      preEventId
                      postEventId
                      modifiable
                      forEventId
                      conferenceId
                      maxAttendees
                      attendeesOmitted
                      sendUpdates
                      anyoneCanAddSelf
                      guestsCanInviteOthers
                      guestsCanSeeOtherGuests
                      originalStartDate
                      originalTimezone
                      originalAllDay
                      status
                      summary
                      title
                      transparency
                      visibility
                      recurringEventId
                      iCalUID
                      htmlLink
                      colorId
                      creator
                      organizer
                      endTimeUnspecified
                      extendedProperties
                      hangoutLink
                      guestsCanModify
                      locked
                      source
                      eventType
                      privateCopy
                      backgroundColor
                      foregroundColor
                      useDefaultAlarms
                      deleted
                      createdDate
                      updatedAt
                      userId
                      calendarId
                      positiveImpactScore
                      negativeImpactScore
                      positiveImpactDayOfWeek
                      positiveImpactTime
                      negativeImpactDayOfWeek
                      negativeImpactTime
                      preferredDayOfWeek
                      preferredTime
                      isExternalMeeting
                      isExternalMeetingModifiable
                      isMeetingModifiable
                      isMeeting
                      dailyTaskList
                      weeklyTaskList
                      isBreak
                      preferredStartTimeRange
                      preferredEndTimeRange
                      copyAvailability
                      copyTimeBlocking
                      copyTimePreference
                      copyReminders
                      copyPriorityLevel
                      copyModifiable
                      copyCategories
                      copyIsBreak
                      userModifiedAvailability
                      userModifiedTimeBlocking
                      userModifiedTimePreference
                      userModifiedReminders
                      userModifiedPriorityLevel
                      userModifiedCategories
                      userModifiedModifiable
                      userModifiedIsBreak
                      hardDeadline
                      softDeadline
                      copyIsMeeting
                      copyIsExternalMeeting
                      userModifiedIsMeeting
                      userModifiedIsExternalMeeting
                      duration
                      copyDuration
                      userModifiedDuration
                      method
                      unlink
                      copyColor
                      userModifiedColor
                      byWeekDay
                      localSynced
                      timeBlocking
                      meetingId
                      eventId
                    }
                  `,
                });
              const filteredEvents = existingEvents?.filter((e: EventType) => (e?.id !== data?.insert_Event?.returning?.[0]?.id)) || []
              console.log(filteredEvents, ' filteredEvents inside atomicUpsertEventInDb')
              if (filteredEvents?.length > 0) {
                return filteredEvents.concat([newEventRef])
              }
              return [newEventRef]
            }
          }
        })
      }
    })
    console.log(response?.data?.insert_Event?.returning?.[0], ' response?.data?.insert_Event?.returning?.[0] inside atomiceupserteventindb')
    return response?.data?.insert_Event?.returning?.[0]
  } catch (e) {
    console.log(e, ' unable to save calendar event')
  }
}

export const getRRuleDay = (value: Day | undefined) => {
  switch (value) {
    case Day.MO:
      return RRule.MO
    case Day.TU:
      return RRule.TU
    case Day.WE:
      return RRule.WE
    case Day.TH:
      return RRule.TH
    case Day.FR:
      return RRule.FR
    case Day.SA:
      return RRule.SA
    case Day.SU:
      return RRule.SU
    default:
      return undefined
  }
}

export const createNewEventInGoogle = async (
  startDate: string,
  endDate: string,
  userId: string,
  client: ApolloClient<NormalizedCacheObject>,
  calendar: CalendarType,
  conferenceData?: ConferenceDataType,
  attendees?: GoogleAttendeeType[],
  title?: string,
  allDay?: boolean,
  recurringEndDate?: string,
  frequency?: RecurrenceFrequencyType,
  interval?: number,
  notes?: string,
  location?: LocationType,
  isFollowUp?: boolean,
  isPreEvent?: boolean,
  isPostEvent?: boolean,
  modifiable?: boolean,
  anyoneCanAddSelf?: boolean,
  guestsCanInviteOthers?: boolean,
  guestsCanSeeOtherGuests?: boolean,
  originalAllDay?: boolean,
  alarms?: string[] | number[],
  timezone?: string,
  taskId?: string,
  taskType?: string,
  followUpEventId?: string,
  preEventId?: string,
  postEventId?: string,
  forEventId?: string,
  maxAttendees?: number,
  sendUpdates?: SendUpdatesType,
  status?: string,
  transparency?: TransparencyType,
  visibility?: VisibilityType,
  iCalUID?: string,
  backgroundColor?: string,
  foregroundColor?: string,
  colorId?: string,
  originalTimezone?: string,
  useDefaultAlarms?: boolean,
  positiveImpactScore?: number,
  negativeImpactScore?: number,
  positiveImpactDayOfWeek?: number,
  positiveImpactTime?: Time,
  negativeImpactDayOfWeek?: number,
  negativeImpactTime?: Time,
  preferredDayOfWeek?: number,
  preferredTime?: Time,
  isExternalMeeting?: boolean,
  isExternalMeetingModifiable?: boolean,
  isMeetingModifiable?: boolean,
  isMeeting?: boolean,
  dailyTaskList?: boolean,
  weeklyTaskList?: boolean,
  isBreak?: boolean,
  preferredStartTimeRange?: Time,
  preferredEndTimeRange?: Time,
  copyAvailability?: boolean,
  copyTimeBlocking?: boolean,
  copyTimePreference?: boolean,
  copyReminders?: boolean,
  copyPriorityLevel?: boolean,
  copyModifiable?: boolean,
  copyCategories?: boolean,
  copyIsBreak?: boolean,
  timeBlocking?: BufferTimeType,
  userModifiedAvailability?: boolean,
  userModifiedTimeBlocking?: boolean,
  userModifiedTimePreference?: boolean,
  userModifiedReminders?: boolean,
  userModifiedPriorityLevel?: boolean,
  userModifiedCategories?: boolean,
  userModifiedModifiable?: boolean,
  userModifiedIsBreak?: boolean,
  hardDeadline?: string,
  softDeadline?: string,
  copyIsMeeting?: boolean,
  copyIsExternalMeeting?: boolean,
  userModifiedIsMeeting?: boolean,
  userModifiedIsExternalMeeting?: boolean,
  duration?: number,
  copyDuration?: boolean,
  userModifiedDuration?: boolean,
  method?: 'create' | 'update',
  unlink?: boolean,
  byWeekDay?: Day[],
  priority?: number,
) => {
  try {
    console.log(hardDeadline, softDeadline, ' hardDeadline, softDeadline inside createNewEventInGoogle')
    let rule: any = {}

    if ((recurringEndDate?.length > 0) && frequency) {
      rule = new RRule({
        freq: getRruleFreq(frequency),
        interval,
        until: dayjs(recurringEndDate).toDate(),
        byweekday: byWeekDay?.map(i => getRRuleDay(i))
      })
    }

    let modifiedAlarms: GoogleReminderType = null

    if (typeof alarms?.[0] === 'string') {
      modifiedAlarms = {
        useDefault: false, overrides: alarms.map(i => ({
          method: 'email',
          minutes: dayjs(startDate).diff(i, 'm'),
        }))
      }
    } else if (typeof alarms?.[0] === 'number') {
      modifiedAlarms = { useDefault: false, overrides: alarms.map(i => ({ method: 'email', minutes: i as number })) }
    }

    if (useDefaultAlarms) {
      modifiedAlarms = { useDefault: useDefaultAlarms }
    }

    console.log(modifiedAlarms, ' modifiedAlarms inside createNewEventInGoogle')

    const eventId = await createGoogleEvent(
      client,
      userId,
      calendar?.id,
      endDate,
      startDate,
      undefined,
      maxAttendees,
      sendUpdates,
      anyoneCanAddSelf,
      attendees,
      conferenceData,
      title,
      notes,
      timezone,
      allDay && dayjs(startDate).format('YYYY-MM-DD'),
      allDay && (endDate || startDate),
      undefined,
      guestsCanInviteOthers,
      false, // guestsCanModify
      guestsCanSeeOtherGuests,
      undefined,
      undefined,
      frequency
      && recurringEndDate
      && interval
      && [rule.toString()],
      modifiedAlarms,
      undefined,
      status,
      transparency,
      visibility,
      iCalUID,
      false,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      location?.title,
    )

    console.log(eventId, ' inside createNewEventInGoogle after createGoogleEvent')

    await atomicUpsertEventInDb(
      client,
      `${eventId}#${calendar?.id}`,
      eventId,
      userId,
      dayjs(startDate).format(),
      dayjs(endDate).format(),
      dayjs().toISOString(),
      false,
      priority || 1,
      isFollowUp ?? false,
      isPreEvent ?? false,
      isPostEvent ?? false,
      modifiable ?? true,
      anyoneCanAddSelf ?? false,
      guestsCanInviteOthers ?? false,
      guestsCanSeeOtherGuests ?? true,
      dayjs(startDate).format(),
      originalAllDay ?? false,
      dayjs().toISOString(),
      calendar?.id,
      title ?? 'New Event',
      allDay ?? false,
      frequency
      && recurringEndDate
      && interval
      && { frequency, endDate: recurringEndDate, interval },
      location,
      notes,
      undefined,
      undefined,
      // modifiedAlarms,
      timezone ?? dayjs.tz.guess(),
      taskId,
      taskType,
      followUpEventId,
      preEventId,
      postEventId,
      forEventId,
      conferenceData?.conferenceId,
      maxAttendees,
      sendUpdates,
      status,
      title,
      transparency,
      visibility,
      recurringEndDate
      && frequency
      && eventId,
      iCalUID,
      undefined,
      colorId,
      undefined, // creator - read only G-event
      undefined, // organizer - G-event import only
      false, // endTimeUnspecified - only for G-events
      frequency
      && recurringEndDate
      && interval
      && [rule.toString()],
      originalTimezone, //timezone of recurrence instance
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      backgroundColor,
      foregroundColor,
      useDefaultAlarms,
      positiveImpactScore,
      negativeImpactScore,
      positiveImpactDayOfWeek,
      positiveImpactTime,
      negativeImpactDayOfWeek,
      negativeImpactTime,
      preferredDayOfWeek,
      preferredTime,
      isExternalMeeting,
      isExternalMeetingModifiable,
      isMeetingModifiable,
      isMeeting,
      dailyTaskList,
      weeklyTaskList,
      isBreak,
      preferredStartTimeRange,
      preferredEndTimeRange,
      copyAvailability,
      copyTimeBlocking,
      copyTimePreference,
      copyReminders,
      copyPriorityLevel,
      copyModifiable,
      copyCategories,
      copyIsBreak,
      timeBlocking,
      userModifiedAvailability,
      userModifiedTimeBlocking,
      userModifiedTimePreference,
      userModifiedReminders,
      userModifiedPriorityLevel,
      userModifiedCategories,
      userModifiedModifiable,
      userModifiedIsBreak,
      hardDeadline,
      softDeadline,
      copyIsMeeting,
      copyIsExternalMeeting,
      userModifiedIsMeeting,
      userModifiedIsExternalMeeting,
      duration,
      copyDuration,
      userModifiedDuration,
      method,
      unlink,
      byWeekDay,
    )

    if (alarms?.length > 0) {
      const promises = alarms?.map((a: any) => createReminderForEvent(
        client,
        userId,
        `${eventId}#${calendar?.id}`,
        (typeof a === 'string') && a,
        timezone,
        (typeof a === 'number') && a,
        useDefaultAlarms,
      ))

      await Promise.all(promises)
    }

    console.log(eventId, ' eventId before returning inside createNewEventInGoogle')
    return eventId
  } catch (e) {
    console.log(e, ' unable to create new event in google calendar')
  }
}

export type meetingTypeStringType = 'scheduled' | 'recurring_fixed'
export type conferenceName = typeof zoomName | typeof googleMeetName
export type conferenceType = 'hangoutsMeet' | 'addOn'

export const getConferenceInDb = async (
  client: ApolloClient<NormalizedCacheObject>,
  conferenceId: string,
) => {
  try {
    const conference = (await client.query<{ Conference_by_pk: ConferenceType }>({
      query: getConferenceById,
      variables: {
        id: conferenceId,
      },
    })).data?.Conference_by_pk

    return conference
  } catch (e) {
    console.log(e, ' unable to get conference in db')
  }
}

export const upsertConferenceInDb = async (
  client: ApolloClient<NormalizedCacheObject>,
  id: string,
  userId: string,
  calendarId: string,
  app: AppType,
  requestId?: string | null,
  type?: meetingTypeStringType | null,
  status?: string | null,
  iconUri?: string,
  name?: ConferenceNameType | null,
  notes?: string | null,
  entryPoints?: EntryPointType[] | null,
  parameters?: {
    addOnParameters?: {
      parameters?: ParameterType[],
    }
  } | null,
  key?: string | null,
  hangoutLink?: string | null,
  joinUrl?: string | null,
  startUrl?: string | null,
  zoomPrivateMeeting?: boolean | null,
) => {
  try {
    const conferenceValuesToUpsert: any = {
      id,
      userId,
      // requestId,
      // type,
      calendarId,
      app,
      status,
      // iconUri,
      // name,
      // notes,
      // entryPoints,
      // parameters,
      // key,
      // hangoutLink,
      // joinUrl,
      // startUrl,
      // zoomPrivateMeeting,
      updatedAt: dayjs().toISOString(),
      createdDate: dayjs().toISOString(),
      deleted: false,
    }

    if (requestId) {
      conferenceValuesToUpsert.requestId = requestId
    }

    if (type) {
      conferenceValuesToUpsert.type = type
    }

    if (iconUri) {
      conferenceValuesToUpsert.iconUri = iconUri
    }

    if (name) {
      conferenceValuesToUpsert.name = name
    }

    if (entryPoints?.[0]) {
      conferenceValuesToUpsert.entryPoints = entryPoints
    }

    if (parameters) {
      conferenceValuesToUpsert.parameters = parameters
    }

    if (key) {
      conferenceValuesToUpsert.key = key
    }

    if (hangoutLink) {
      conferenceValuesToUpsert.hangoutLink = hangoutLink
    }


    if (joinUrl) {
      conferenceValuesToUpsert.joinUrl = joinUrl
    }

    if (startUrl) {
      conferenceValuesToUpsert.startUrl = startUrl
    }

    if (zoomPrivateMeeting) {
      conferenceValuesToUpsert.zoomPrivateMeeting = zoomPrivateMeeting
    }

    const upsertConference = gql`
      mutation InsertConference($conferences: [Conference_insert_input!]!) {
        insert_Conference(
            objects: $conferences,
            on_conflict: {
                constraint: Conference_pkey,
                update_columns: [
                  ${requestId ? 'requestId,' : ''}
                  ${type ? 'type,' : ''}
                  ${status ? 'status,' : ''}
                  calendarId,
                  ${iconUri ? 'iconUri,' : ''}
                  ${name ? 'name,' : ''}
                  ${notes ? 'notes,' : ''}
                  ${entryPoints ? 'entryPoints,' : ''}
                  ${parameters ? 'parameters,' : ''}
                  app,
                  ${key ? 'key,' : ''}
                  ${hangoutLink ? 'hangoutLink,' : ''}
                  ${joinUrl ? 'joinUrl,' : ''}
                  ${startUrl ? 'startUrl,' : ''}
                  ${zoomPrivateMeeting ? 'zoomPrivateMeeting,' : ''}
                  deleted,
                  updatedAt,
                ]
            }){
            returning {
              id
            }
          }
      }
    `
    const { data } = await client.mutate<{ insert_Conference: { returning: ConferenceType[] } }>({
      mutation: upsertConference,
      variables: {
        conferences: [conferenceValuesToUpsert],
      },
    })
    console.log(data.insert_Conference, ' data.insert_Conference')
    return data.insert_Conference.returning[0]
  } catch (e) {
    console.log(e, ' unable to save conference in db')
  }
}

export const createConference = async (
  startDate: string,
  endDate: string,
  client: ApolloClient<NormalizedCacheObject>,
  calendarId: string,
  zoomMeet: boolean = false,
  googleMeet: boolean = false,
  userId: string,
  meetingTypeString: meetingTypeStringType,
  attendees: GoogleAttendeeType[],
  requestId?: string,
  summary?: string,
  taskType?: string,
  notes?: string,
  zoomPassword?: string,
  zoomPrivateMeeting?: boolean,
) => {
  try {
    // validate
    if (zoomMeet && googleMeet) {
      throw new Error('cannot create both zoom and google meet')
    }

    if (!zoomMeet && !googleMeet) {
      throw new Error('must create either zoom or google meet')
    }

    if (!startDate || !endDate) {
      throw new Error('startDate and endDate are required')
    }

    if (!calendarId) {
      throw new Error('calendarId is required')
    }

    // create conference if any
    let newConferenceId: string | number = ''
    let newJoinUrl = ''
    let newStartUrl = ''
    let newConferenceStatus = ''
    let conferenceName: conferenceName = zoomName
    let conferenceType: conferenceType = 'addOn'
    let conferenceData: ConferenceDataType = {
      type: 'addOn',
      name: conferenceName,
      requestId: uuid(),
      conferenceId: newConferenceId,
      createRequest: false,
      entryPoints: [{
        label: zoomName,
        entryPointType: 'video',
        uri: newJoinUrl,
        password: zoomPassword,
      }]
    }
    let newRequestId = requestId || uuid()
    if (zoomMeet) {
      const isZoomAvailable = await zoomAvailable(client, userId)

      if (isZoomAvailable) {

        const zoomInteg = (await client.query<{ Calendar_Integration: CalendarIntegrationType[] }>({
          query: getCalendarIntegrationByResource,
          variables: {
            userId,
            name: zoomName,
            resource: zoomResourceName,
          }
        }))?.data?.Calendar_Integration?.[0]
        const {
          id: zoomConferenceId,
          join_url: zoomJoinUrl,
          start_url: zoomStartUrl,
          status: zoomStatus,
        } = await createZoomMeeting(
          userId,
          dayjs(startDate).format(),
          dayjs.tz.guess(),
          summary ?? taskType ?? notes,
          dayjs.duration({ hours: dayjs(endDate).hour(), minutes: dayjs(endDate).minute() }).asMinutes(),
          zoomInteg?.contactName,
          zoomInteg?.contactEmail,
          attendees.map(i => i?.email),
          zoomPrivateMeeting,
        )


        newConferenceId = zoomConferenceId
        newJoinUrl = zoomJoinUrl
        newStartUrl = zoomStartUrl
        newConferenceStatus = zoomStatus
        conferenceName = zoomName
        conferenceType = 'addOn'
        conferenceData = {
          type: conferenceType,
          name: conferenceName,
          requestId: newRequestId,
          conferenceId: `${newConferenceId}`,
          createRequest: false,
          entryPoints: [{
            label: zoomName,
            entryPointType: 'video',
            uri: newJoinUrl,
            password: zoomPassword,
          }]
        }
      }
    } else if (googleMeet) {
      newConferenceId = uuid()
      conferenceName = googleMeetName
      conferenceType = 'hangoutsMeet'
      conferenceData = {
        type: conferenceType,
        conferenceId: newConferenceId,
        name: conferenceName,
        requestId: newRequestId,
        createRequest: true,
      }
    }

    await upsertConferenceInDb(
      client,
      typeof newConferenceId === 'number' ? `${newConferenceId}` : newConferenceId,
      userId,
      calendarId,
      zoomMeet ? zoomResourceName : googleResourceName,
      newRequestId,
      meetingTypeString,
      undefined,
      undefined,
      zoomMeet ? zoomName : googleMeetName,
      notes,
      conferenceData?.entryPoints,
      undefined,
      undefined,
      undefined,
      newJoinUrl,
      newStartUrl,
      zoomPrivateMeeting,
    )

    return {
      newConferenceId,
      newJoinUrl,
      newStartUrl,
      newConferenceStatus,
      conferenceName,
      conferenceType,
      conferenceData,
    }
  } catch (e) {
    console.log(e, ' unable to create conference')
  }
}

export const createNewEvent = async (
  startDate: string,
  endDate: string,
  userId: string,
  client: ApolloClient<NormalizedCacheObject>,
  selectedCalendarId?: string,
  categoryIds?: string[],
  title?: string,
  allDay?: boolean,
  recurringEndDate?: string,
  frequency?: RecurrenceFrequencyType,
  interval?: number,
  alarms?: string[] | number[],
  notes?: string,
  location?: LocationType,
  isFollowUp?: boolean,
  isPreEvent?: boolean,
  isPostEvent?: boolean,
  modifiable?: boolean,
  anyoneCanAddSelf?: boolean,
  guestsCanInviteOthers?: boolean,
  guestsCanSeeOtherGuests?: boolean,
  originalAllDay?: boolean,
  timezone?: string,
  taskId?: string,
  taskType?: string,
  followUpEventId?: string,
  preEventId?: string,
  postEventId?: string,
  forEventId?: string,
  zoomMeet?: boolean,
  googleMeet?: boolean,
  meetingTypeString?: meetingTypeStringType,
  zoomPassword?: string,
  zoomPrivateMeeting?: boolean,
  attendees?: Person[],
  conferenceId?: string,
  maxAttendees?: number,
  sendUpdates?: SendUpdatesType,
  status?: string,
  summary?: string,
  transparency?: TransparencyType,
  visibility?: VisibilityType,
  recurringEventId?: string,
  iCalUID?: string,
  htmlLink?: string,
  colorId?: string,
  originalTimezone?: string,
  backgroundColor?: string,
  foregroundColor?: string,
  useDefaultAlarms?: boolean,
  positiveImpactScore?: number,
  negativeImpactScore?: number,
  positiveImpactDayOfWeek?: number,
  positiveImpactTime?: Time,
  negativeImpactDayOfWeek?: number,
  negativeImpactTime?: Time,
  preferredDayOfWeek?: number,
  preferredTime?: Time,
  isExternalMeeting?: boolean,
  isExternalMeetingModifiable?: boolean,
  isMeetingModifiable?: boolean,
  isMeeting?: boolean,
  dailyTaskList?: boolean,
  weeklyTaskList?: boolean,
  isBreak?: boolean,
  preferredStartTimeRange?: Time,
  preferredEndTimeRange?: Time,
  copyAvailability?: boolean,
  copyTimeBlocking?: boolean,
  copyTimePreference?: boolean,
  copyReminders?: boolean,
  copyPriorityLevel?: boolean,
  copyModifiable?: boolean,
  copyCategories?: boolean,
  copyIsBreak?: boolean,
  timeBlocking?: BufferTimeType,
  userModifiedAvailability?: boolean,
  userModifiedTimeBlocking?: boolean,
  userModifiedTimePreference?: boolean,
  userModifiedReminders?: boolean,
  userModifiedPriorityLevel?: boolean,
  userModifiedCategories?: boolean,
  userModifiedModifiable?: boolean,
  userModifiedIsBreak?: boolean,
  hardDeadline?: string,
  softDeadline?: string,
  copyIsMeeting?: boolean,
  copyIsExternalMeeting?: boolean,
  userModifiedIsMeeting?: boolean,
  userModifiedIsExternalMeeting?: boolean,
  duration?: number,
  copyDuration?: boolean,
  userModifiedDuration?: boolean,
  method?: 'create' | 'update',
  unlink?: boolean,
  byWeekDay?: Day[],
  priority?: number,
) => {
  try {
    /**
    2. check if any calendars are active
    3. create in global primary calendar
    if none create in any calendar available
    finally try create local calendar if none available
    and save to calendar db
     */

    let calendar: CalendarType | {} = {}

    if (selectedCalendarId?.length > 0) {
      calendar = await getCalendarInDb(client, userId, selectedCalendarId)
    }

    if (!selectedCalendarId) {
      // global primary if none selectedCalendarId
      calendar = await getCalendarInDb(client, userId, undefined, true)
    }

    // if no  calendar get google calendar
    if (!selectedCalendarId && !calendar && googleResourceName) {
      calendar = await getCalendarInDb(client, userId, undefined, undefined, googleResourceName)
    }

    if (!((calendar as CalendarType)?.id) && !selectedCalendarId) {
      // get any if none set to globalPrimary and no selectedCalendarId
      calendar = await getCalendarInDb(client, userId)
    }

    if ((calendar as CalendarType)?.resource === googleResourceName) {
      const modifiedAttendees: GoogleAttendeeType[] = attendees?.map(a => ({
        additionalGuests: a?.additionalGuests,
        displayName: a?.name,
        email: a?.emails?.[0]?.value,
        id: a?.id,
      }))
      let conferenceData = null
      // create conferece
      if (modifiedAttendees?.length > 0) {
        const {
          // newConferenceId,
          // newJoinUrl,
          // newStartUrl,
          // newConferenceStatus,
          // conferenceName,
          // conferenceType,
          conferenceData: conferenceData1,
        } = await createConference(
          startDate,
          endDate,
          client,
          (calendar as CalendarType)?.id,
          zoomMeet,
          googleMeet,
          userId,
          meetingTypeString,
          modifiedAttendees,
          undefined,
          summary,
          taskType,
          notes,
          zoomPassword,
          zoomPrivateMeeting,
        )
        conferenceData = conferenceData1
      }

      console.log(hardDeadline, softDeadline, ' hardDeadline, softDeadline inside createNewEvent')
      const eventId = await createNewEventInGoogle(
        startDate,
        endDate,
        userId,
        client,
        calendar as CalendarType,
        conferenceData,
        modifiedAttendees,
        title,
        allDay,
        recurringEndDate,
        frequency,
        interval,
        notes,
        location,
        isFollowUp,
        isPreEvent,
        isPostEvent,
        modifiable,
        anyoneCanAddSelf,
        guestsCanInviteOthers,
        guestsCanSeeOtherGuests,
        originalAllDay,
        alarms,
        timezone,
        taskId,
        taskType,
        followUpEventId,
        preEventId,
        postEventId,
        forEventId,
        maxAttendees,
        sendUpdates,
        status,
        transparency,
        visibility,
        iCalUID,
        backgroundColor,
        foregroundColor,
        colorId,
        originalTimezone,
        useDefaultAlarms,
        positiveImpactScore,
        negativeImpactScore,
        positiveImpactDayOfWeek,
        positiveImpactTime,
        negativeImpactDayOfWeek,
        negativeImpactTime,
        preferredDayOfWeek,
        preferredTime,
        isExternalMeeting,
        isExternalMeetingModifiable,
        isMeetingModifiable,
        isMeeting,
        dailyTaskList,
        weeklyTaskList,
        isBreak,
        preferredStartTimeRange,
        preferredEndTimeRange,
        copyAvailability,
        copyTimeBlocking,
        copyTimePreference,
        copyReminders,
        copyPriorityLevel,
        copyModifiable,
        copyCategories,
        copyIsBreak,
        timeBlocking,
        userModifiedAvailability,
        userModifiedTimeBlocking,
        userModifiedTimePreference,
        userModifiedReminders,
        userModifiedPriorityLevel,
        userModifiedCategories,
        userModifiedModifiable,
        userModifiedIsBreak,
        hardDeadline,
        softDeadline,
        copyIsMeeting,
        copyIsExternalMeeting,
        userModifiedIsMeeting,
        userModifiedIsExternalMeeting,
        duration,
        copyDuration,
        userModifiedDuration,
        method,
        unlink,
        byWeekDay,
        priority,
      )

      console.log(eventId, ' eventId inside createNewEvent after createNewEventInGoogle')

      // save attendees
      if (attendees?.length > 0) {
        const attendeePromises = attendees?.map(a => {
          return upsertAttendeesInDb(
            client,
            uuid(),
            userId,
            eventId,
            a?.emails,
            a?.name,
            a?.id,
            a?.phoneNumbers,
            a?.imAddresses,
            a?.additionalGuests,
            a?.optional,
            a?.resource,
          )
        })
        await Promise.all(attendeePromises)
      }

      if (categoryIds?.length > 0) {
        // create category_event connections
        const categoryPromises = categoryIds.map(i => upsertCategoryEventConnection(
          client, userId, i, eventId,
        ))

        await Promise.all(categoryPromises)
      }

      return eventId
    }

  } catch (e) {
    console.log(e, ' unable to create new event')
  }
}

export const deleteEventForTask = async (
  eventId: string,
  client: ApolloClient<NormalizedCacheObject>,
) => {
  try {
    const { data } = (await client.mutate<{ delete_Event_by_pk: EventType }>({
      mutation: deleteEventById,
      variables: {
        id: eventId,
      },
      // refetchQueries: [
      //   listAllEvents, // DocumentNode object parsed with gql
      //   'listAllEvents' // Query name
      // ],
      update(cache, { data }) {
        const deletedEvent = data?.delete_Event_by_pk
        const normalizedId = cache.identify({ id: deletedEvent.id, __typename: deletedEvent.__typename })
        cache.evict({ id: normalizedId })
        cache.gc()
      }
    }))
    console.log(data, ' delete event')
    return data?.delete_Event_by_pk?.id
  } catch (e) {
    console.log(e, 'error for deleteEvent')
  }
}


/**
end
 */
