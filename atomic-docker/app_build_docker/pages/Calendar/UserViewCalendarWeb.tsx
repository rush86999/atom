import { dayjs } from '@lib/date-utils'
import React, { useEffect, useState, useMemo, useCallback } from 'react'
import withDragAndDrop from 'react-big-calendar/lib/addons/dragAndDrop'
import {
    Calendar,
    dayjsLocalizer,
    EventPropGetter,
    SlotInfo,
    type Event as CalendarEvent,
    type stringOrDate,
} from 'react-big-calendar'
import _ from 'lodash'
import { EventType } from '@lib/dataTypes/EventType'

import { esResponseBody, RecurrenceFrequencyType, TagType } from '@lib/Calendar/types'
import SpeedDial from '@mui/material/SpeedDial';
import SpeedDialIcon from '@mui/material/SpeedDialIcon';
import SpeedDialAction from '@mui/material/SpeedDialAction';
import { pink } from '@mui/material/colors'
import FileCopyIcon from '@mui/icons-material/FileCopyOutlined';
import { useToast } from '@chakra-ui/react'
import Session from "supertokens-web-js/recipe/session"

import axios from 'axios'

import Box from '@components/common/Box'
import Text from '@components/common/Text'

import UserEditCategoryEventModal from '@pages/Calendar/UserEditCategoryEventModal'
import UserPreAndPostForEventModal from '@pages/Calendar/UserPreAndPostForEventModal'
import UserEditEventPriorityModal from  '@pages/Calendar/UserEditEventPriorityModal'

import QueryStatsIcon from '@mui/icons-material/QueryStats';
import MeetingRoomIcon from '@mui/icons-material/MeetingRoom';
import ScheduleIcon from '@mui/icons-material/Schedule';
import { CalendarEventPro } from '../../lib/Calendar/UserCreateCalendarHelper'
import { setCurrentEventsForCalendarWeb } from '@lib/Calendar/UserCreateCalendarHelper'
import { methodToSearchIndexAuthUrl, calendarToQueueAuthUrl, eventToQueueAuthUrl, featuresApplyToEventsAuthUrl } from '@lib/constants'
import Button from '@components/Button'

import UserRateEvent from '@pages/Calendar/UserRateEvent'
import { CategoryEventType } from '@lib/dataTypes/Category_EventType'
import { googleResourceName } from '@lib/calendarLib/constants'
import { checkIfCalendarWebhookExpired, deleteGoogleEvent } from '@lib/calendarLib/googleCalendarHelper'


import { palette } from '@lib/theme/theme'
import subscribeEventUpdated from '@lib/apollo/gql/subscribeEventUpdated'
import { ApolloClient, gql, NormalizedCacheObject } from '@apollo/client'
import listCategoriesForEventId from '@lib/apollo/gql/listCategoriesForEventId'

import { CategoryType } from '@lib/dataTypes/CategoryType'
import subscribeEventAdded from '@lib/apollo/gql/subscribeEventAdded'
import getEventById from '@lib/apollo/gql/getEventById'
import updateEventForUnlink from '@lib/apollo/gql/updateEventForUnlink'
import updateEventForModifiable from '@lib/apollo/gql/updateEventForModifiable'
import getCalendarById from '@lib/apollo/gql/getCalendarById'
import deleteEventById from '@lib/apollo/gql/deleteEventById'
import { CalendarType } from '@lib/dataTypes/CalendarType'

import { getEventWithId } from '@lib/calendarLib/calendarDbHelper'
import { atomicUpsertEventInDb } from '../../lib/Calendar/UserCreateCalendarHelper';
import { deleteAttendeesForEvent } from '@lib/Calendar/Attendee/AttendeeHelper';
import { deleteConferencesWithIds } from '@lib/Calendar/Conference/ConferenceHelper';
import { removeRemindersForEvent } from '@lib/Calendar/Reminder/ReminderHelper'

// import DateTimePicker from 'react-datetime-picker/dist/entry.nostyle'
import { Input } from '@chakra-ui/react'

import { deleteMeetingAssistGivenId, getMeetingAssistGivenId } from '@lib/Assist/UserMeetingAssistHelper'
import { deleteZoomConferenceUrl } from '@lib/Assist/constants'
import { ActivityIndicator, Appearance, Pressable, StyleSheet } from 'react-native'
import { useRouter } from 'next/router'
import { useAppContext } from '@lib/user-context'
import Modal from 'react-modal'
import UserCreateEvent from '@pages/Calendar/UserCreateEvent'
import UserEditEvent from '@pages/Calendar/UserEditEvent'
import UserTrainEvent from '@pages/Calendar/UserTrainEvent'
import UserAddFollowUp from '@pages/Calendar/UserAddFollowUp'
import UserEventTimePreferences from '@pages/Calendar/UserEventTimePreferences'
import TextField from '@components/TextField'

import { updateEvent } from '../../lib/Calendar/UserEditCalendarHelper'
import {
    MdOutlineEditCalendar, 
    MdOutlineAccessTime,
    MdStarRate,
    MdCalendarMonth,
    MdOutlineLowPriority,
    MdLockOpen,
    MdLockOutline,
    MdLink,
    MdLinkOff,
    MdClose,
} from 'react-icons/md'
import { IoMdPricetag } from "react-icons/io";
import { GiArtificialIntelligence } from "react-icons/gi"
import { BsCalendarPlus, BsCalendarMinus } from "react-icons/bs"
import { HiOutlineClock } from "react-icons/hi2";
// MdOutlineAccessTime
// const dark = Appearance.getColorScheme() === 'dark'
// BsCalendarPlus
// HiOutlineClock
const styles = {
  container: {
    ...StyleSheet.absoluteFillObject,
        justifyContent: 'flex-end',
  } as any,
}

const styles2 = {
  centeredView: {
    
    justifyContent: "center",
    alignItems: "center",
    marginTop: 22
  } as any,
  modalView: {
    margin: 20,
    backgroundColor: "white",
    borderRadius: 20,
    padding: 35,
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: {
      width: 0,
      height: 2
    } as any,
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 5
  } as any,
}


const customModalStyles = {
  content: {
    top: '50%',
    left: '50%',
    right: 'auto',
    bottom: 'auto',
    marginRight: '-50%',
    transform: 'translate(-50%, -50%)',
    zIndex: 0,
  },
  overlay: {
    zIndex: 9999,
  }
}

const customModalStyles2 = {
  overlay: {
    zIndex: 9999,
  }
}

const localizer = dayjsLocalizer(dayjs)

const DnDCalendar = withDragAndDrop(Calendar)


type OnCallBackArgType = { event: CalendarEventPro, start: stringOrDate, end: stringOrDate, isAllDay: boolean }

import { NextApiRequest, NextApiResponse } from 'next';
import supertokensNode from 'supertokens-node'
import { backendConfig } from '../../config/backendConfig'
import Session1 from 'supertokens-node/recipe/session'
import { getUserPreference } from '@lib/OnBoard/OnBoardHelper'


// GraphQL Mutations for Agent Actions
const ATTEND_LIVE_MEETING_MUTATION = gql`
  mutation AttendLiveMeeting($platform: String!, $meetingIdentifier: String!, $notionNoteTitle: String!, $notionSource: String!, $linkedEventId: String) {
    attendLiveMeeting(platform: $platform, meeting_id: $meetingIdentifier, notion_note_title: $notionNoteTitle, notion_source: $notionSource, linked_event_id: $linkedEventId) {
      status
      note_id
      error_message
    }
  }
`;

const PROCESS_MEETING_ARTIFACTS_MUTATION = gql`
  mutation ProcessMeetingArtifacts($platform: String!, $meetingIdentifier: String!, $artifactType: String!, $notionNoteTitle: String!, $notionSource: String!, $linkedEventId: String) {
    processMeetingArtifacts(platform: $platform, meeting_id: $meetingIdentifier, artifact_type: $artifactType, notion_note_title: $notionNoteTitle, notion_source: $notionSource, linked_event_id: $linkedEventId) {
      status
      note_id
      error_message
    }
  }
`;

const STOP_AGENT_FOR_MEETING_MUTATION = gql`
  mutation StopAgentForMeeting($meetingIdentifier: String!) {
    stopAgentForMeeting(meeting_id: $meetingIdentifier) {
      status
      error_message
    }
  }
`;


export async function getServerSideProps({ req, res }: { req: NextApiRequest, res: NextApiResponse }) {
  // Notice how the server uses `API` from `withSSRContext`, instead of the top-level `API`.
  // const SSR = withSSRContext({ req })
  // this runs on the backend, so we must call init on supertokens-node SDK
  supertokensNode.init(backendConfig())
  let session
  try {
    session = await Session1.getSession(req, res, {
      overrideGlobalClaimValidators: async function () {
        return []
      },
    })
  } catch (err: any) {
    if (err.type === Session1.Error.TRY_REFRESH_TOKEN) {
      return { props: { fromSupertokens: 'needs-refresh' } }
    } else if (err.type === Session1.Error.UNAUTHORISED) {
      // this will force the frontend to try and refresh which will fail
      // clearing all cookies and redirecting the user to the login screen.
      return { props: { fromSupertokens: 'needs-refresh' } }
    }
    throw err
  }

  if (!session?.getUserId()) {
    return {
      redirect: {
        destination: '/User/Login/UserLogin',
        permanent: false,
      },
    }
  }

  return {
    props: {
      sub: session.getUserId(),
    }
  }
}

function UserViewCalendarWeb() {
    const [calendarEvents, setCalendarEvents] = useState<CalendarEventPro[]>([])
    const [isDelete, setIsDelete] = useState<boolean>(false)
    const [toDeleteId, setToDeleteId] = useState<string | undefined>()
    const [isEventTags, setIsEventTags] = useState<boolean>(false)
    const [toTagId, setToTagId] = useState<string | undefined>()
    const [isRateEvent, setIsRateEvent] = useState<boolean>(false)
    const [toRateId, setToRateId] = useState<string | undefined>()
    const [isPrepAndReview, setIsPrepAndRev] = useState<boolean>(false)
    const [toPrepAndRevEvent, setToPrepAndReviewEvent] = useState<EventType>()
    const [isPriority, setIsPriority] = useState<boolean>(false)
    const [toPriorityId, setToPriorityId] = useState<string | undefined>()
    const [oldPriority, setOldPriority] = useState<number>(1)
    const [isLoading, setIsLoading] = useState<boolean>(false)
    const [startScheduleDate, setStartScheduleDate] = useState<Date>(new Date())
    const [endScheduleDate, setEndScheduleDate] = useState<Date>(dayjs().add(7, 'd').toDate())
    const [isScheduleAssist, setIsScheduleAssist] = useState<boolean>(false)
    const [isFeaturesApply, setIsFeaturesApply] = useState<boolean>(false)
    const [isStartDatePicker, setIsStartDatePicker] = useState<boolean>(false)
    const [isEndDatePicker, setIsEndDatePicker] = useState<boolean>(false)

    const [isDialOpen, setIsDialOpen] = useState<boolean>(false)
    const [selectedSlot, setSelectedSlot] = useState<SlotInfo>()
    const [isCreateEvent, setIsCreateEvent] = useState<boolean>(false)
    const [selectedEditEventId, setSelectedEditEventId] = useState<string>('')
    const [isEditEvent, setIsEditEvent] = useState<boolean>(false)
    const [selectedTrainEventId, setSelectedTrainEventId] = useState<string>('')
    const [isTrainEvent, setIsTrainEvent] = useState<boolean>(false)
    const [selectedAddFollowUpId, setSelectedAddFollowUpId] = useState<string>('')
    const [isAddFollowUp, setIsAddFollowUp] = useState<boolean>(false)
    const [selectedEventIdForTimePreferences, setSelectedEventIdForTimePreferences] = useState<string>('')
    const [isAddTimePreferences, setIsAddTimePreferences] = useState<boolean>(false)
    const [isMenu, setIsMenu] = useState<boolean>(false)
    const [eventOfMenu, setEventOfMenu] = useState<CalendarEventPro>()
    const [title, setTitle] = useState<string>()
    const [notes, setNotes] = useState<string>()
    const [allDay, setAllDay] = useState<boolean>(false)
    const [isRecurring, setIsRecurring] = useState<boolean>(false)
    const [recurringEndDate, setRecurringEndDate] = useState<Date>(new Date())
    const [frequency, setFrequency] = useState<RecurrenceFrequencyType>('daily')
    // State for Agent Meeting Attendance
    const [isAgentAttendingMeeting, setIsAgentAttendingMeeting] = useState<boolean>(false);
    const [agentMeetingStatus, setAgentMeetingStatus] = useState<string>('');
    const [selectedMeetingForAgentId, setSelectedMeetingForAgentId] = useState<string | null>(null);
    const [interval, setInterval] = useState<string>('1')
    const [startDate, setStartDate] = useState<Date>(new Date())
    const [endDate, setEndDate] = useState<Date>(new Date())
    const [isEventEditSuccess, setIsEventEditSuccess] = useState<boolean>(false)
    
    const router = useRouter()
    const { sub, client } = useAppContext()

    const userId = sub
    const toast = useToast()

    const getMeetingPlatformAndIdentifier = (event: CalendarEventPro | undefined): { platform: string; identifier: string } | null => {
        if (!event) return null;

        // Check Google Meet hangoutLink first
        if (event.hangoutLink) {
            return { platform: 'google', identifier: event.hangoutLink };
        }

        // Check location for Zoom or Teams links
        if (event.location) {
            const location = event.location.toLowerCase();
            // Basic Zoom ID parsing (e.g., zoom.us/j/1234567890)
            const zoomMatch = location.match(/zoom.us\/j\/(\d+)/);
            if (zoomMatch && zoomMatch[1]) {
                return { platform: 'zoom', identifier: zoomMatch[1] };
            }
            // Basic Teams URL parsing
            if (location.includes('teams.microsoft.com/l/meetup-join/')) {
                return { platform: 'teams', identifier: event.location }; // Return the full URL as identifier
            }
        }

        // Check description for Zoom or Teams links if not found in location
        if (event.notes) { // Assuming description is in 'notes' field based on UserCreateMeetingAssist
            const description = event.notes.toLowerCase();
            const zoomMatchDesc = description.match(/zoom.us\/j\/(\d+)/);
            if (zoomMatchDesc && zoomMatchDesc[1]) {
                return { platform: 'zoom', identifier: zoomMatchDesc[1] };
            }
            if (description.includes('teams.microsoft.com/l/meetup-join/')) {
                 // Extract the full Teams URL from description if possible, might need more robust regex
                const teamsUrlMatch = event.notes.match(/(https?:\/\/teams\.microsoft\.com\/l\/meetup-join\/[^ \n\r\t<]+)/);
                if (teamsUrlMatch && teamsUrlMatch[1]) {
                    return { platform: 'teams', identifier: teamsUrlMatch[1] };
                }
            }
            // Google Meet links in description (less common if hangoutLink is primary)
            const googleMeetMatchDesc = event.notes.match(/(https?:\/\/meet\.google\.com\/[a-z\-]+)/);
            if (googleMeetMatchDesc && googleMeetMatchDesc[1]) {
                return { platform: 'google', identifier: googleMeetMatchDesc[1] };
            }
        }

        return null;
    };
    
    const {defaultDate} = useMemo(() => ({
        defaultDate: new Date()
    }), [])

    const handleAttendWithAgent = async (event: CalendarEventPro | undefined) => {
        if (!event) return;

        const meetingInfo = getMeetingPlatformAndIdentifier(event);

        if (!meetingInfo) {
            toast({ title: "Not a recognized online meeting", description: "No valid Google Meet, Zoom, or Teams link found in the event details.", status: "error", duration: 5000, isClosable: true });
            return;
        }

        setSelectedMeetingForAgentId(event.id);
        setIsAgentAttendingMeeting(true);
        setAgentMeetingStatus(`Agent joining ${meetingInfo.platform} meeting...`);

        try {
            const { data, errors } = await client.mutate({
                mutation: ATTEND_LIVE_MEETING_MUTATION,
                variables: {
                    platform: meetingInfo.platform,
                    meetingIdentifier: meetingInfo.identifier,
                    notionNoteTitle: event.title || `Meeting Notes for ${event.id}`,
                    notionSource: `Live from ${meetingInfo.platform} meeting - ${event.title || event.id}`,
                    linkedEventId: event.id,
                },
            });

            if (errors && errors.length > 0) {
                throw new Error(errors.map(e => e.message).join(', '));
            }

            if (data?.attendLiveMeeting?.status === 'success' || data?.attendLiveMeeting?.status?.startsWith('Connected')) {
                setAgentMeetingStatus(`Agent connected: ${data.attendLiveMeeting.status}. Note ID: ${data.attendLiveMeeting.note_id || 'N/A'}`);
                toast({ title: "Agent Action", description: `Agent connected: ${data.attendLiveMeeting.status}`, status: "success", duration: 5000, isClosable: true });
            } else {
                const errorMessage = data?.attendLiveMeeting?.error_message || "Unknown error from agent.";
                setAgentMeetingStatus(`Agent connection failed: ${errorMessage}`);
                toast({ title: "Agent Action Failed", description: errorMessage, status: "error", duration: 5000, isClosable: true });
                // setIsAgentAttendingMeeting(false); // Optionally reset if connection failed outright
                // setSelectedMeetingForAgentId(null);
            }
        } catch (error: any) {
            console.error("Error calling AttendLiveMeeting mutation:", error);
            setAgentMeetingStatus(`Error: ${error.message}`);
            toast({ title: "Error Attending Meeting", description: error.message, status: "error", duration: 5000, isClosable: true });
            // Reset state on error to allow retry
            // setIsAgentAttendingMeeting(false); // Keep it true to show status and allow stop? Or false to allow retry?
            // setSelectedMeetingForAgentId(null); // For now, keep meeting selected to show error status
        }
    };

    const handleStopAgent = async (event: CalendarEventPro | undefined) => {
        if (!event) return;

        const meetingInfo = getMeetingPlatformAndIdentifier(event);
        // meetingIdentifier might be needed if the stop action requires it.
        // For now, the mutation only takes meeting_id which is event.id
        // const meetingIdentifier = meetingInfo?.identifier;

        setAgentMeetingStatus('Stopping agent...');

        try {
            // Conceptual: Call STOP_AGENT_FOR_MEETING_MUTATION
            // For this subtask, we simulate the stop action as Hasura action might not exist yet.
            console.log(`Simulating call to STOP_AGENT_FOR_MEETING_MUTATION for event ID: ${event.id}`);
            // const { data } = await client.mutate({
            //     mutation: STOP_AGENT_FOR_MEETING_MUTATION,
            //     variables: { meetingIdentifier: event.id }, // Assuming meetingIdentifier is the event.id for stopping purposes
            // });
            // if (data?.stopAgentForMeeting?.status === 'success') {
            //   toast({ title: "Agent stopped successfully.", status: "info", duration: 3000, isClosable: true });
            // } else {
            //   throw new Error(data?.stopAgentForMeeting?.error_message || "Failed to stop agent via backend.");
            // }

            // Simulate immediate success for frontend state reset
            setIsAgentAttendingMeeting(false);
            setAgentMeetingStatus('Agent stopped.');
            setSelectedMeetingForAgentId(null);
            toast({ title: "Agent stopped (simulated).", status: "info", duration: 3000, isClosable: true });

        } catch (error: any) {
            console.error("Error calling StopAgentForMeeting mutation (simulated):", error);
            setAgentMeetingStatus(`Error stopping agent: ${error.message}`);
            toast({ title: "Error Stopping Agent", description: error.message, status: "error", duration: 5000, isClosable: true });
            // Decide if we should reset all agent states even if stop fails, or leave them for retry.
            // For now, we reset to allow user to try "Attend" again if stop failed.
            setIsAgentAttendingMeeting(false); // Attempt to reset to a clean state
            setSelectedMeetingForAgentId(null);
        }
    };

    // renew push notifictions
    useEffect(() => {
        if (userId) {
        (async () => checkIfCalendarWebhookExpired(client, userId))()
        }
        
    }, [client, userId])

    // check onboarding
    useEffect(() => {
        (async () => {
          if (!sub) {
              return
          }
          const user_preferenceDoc = await getUserPreference(client, sub)
          console.log(user_preferenceDoc?.onBoarded, ' user_preferenceDoc?.onBoarded')
          if (!user_preferenceDoc?.onBoarded) {
            console.log(' no user preference created')
            return router.push({ pathname: '/OnBoard/UserOnBoard'})
          }
            
        })()
      }, [client, router, sub])

    // get current events
    useEffect(() => {
        if (!userId) {
            return
        }
        (async () => setCurrentEventsForCalendarWeb(
            userId,
            client,
            setCalendarEvents,
        )
        )()
    }, [client, userId])

    // update event subscription
    useEffect(() => {
        if (!client) {
        return
        }

        if (!userId) {
            return
        }
        const subscription = client.subscribe<{ Event: EventType[] }>({
        query: subscribeEventUpdated,
        variables: {
            userId,
            currentDate: dayjs().format(),
        }
        })
        .subscribe({
            next: async (event) => {
            console.log(event, ' event inside subscribeEventUpdated')
            console.log(event?.data?.Event?.[0], ' event.data.Event[0]')
            const newEvent = event?.data?.Event?.[0]
            console.log(newEvent, ' newEvent inside updateEventSubscription')
            
            if (!newEvent?.id) {
                
                return
            }
            const newEvents = _.cloneDeep(calendarEvents)
            try {
                const tags = (await client.query<{ Category: CategoryType[] }>({
                query: listCategoriesForEventId,
                variables: {
                    eventId: newEvent?.id,
                },
                }))?.data?.Category?.map((c) => ({
                id: c.id, 
                name: c.name, 
                color: c.color,
                }))
                console.log(tags, ' tags inside subscribeEventUpdated')
                console.log(calendarEvents?.[0]?.id, ' first Event inside calendarEvents')
                const index = calendarEvents.findIndex((e) => (e.id === newEvent?.id))
                if (index > -1) {
                newEvents[index] = {
                    ...newEvent,
                    id: newEvent?.id,
                    start: dayjs(newEvent?.startDate?.slice(0, 19)).tz(newEvent?.timezone, true).toDate(),
                    end: dayjs(newEvent?.endDate?.slice(0, 19)).tz(newEvent?.timezone, true).toDate(),
                    title: newEvent?.title || newEvent?.summary,
                    eventId: newEvent?.eventId,
                    calendarId: newEvent?.calendarId,
                    notes: newEvent?.notes,
                    color: tags?.[0]?.color || newEvent?.backgroundColor,
                    tags,
                    unlink: newEvent?.unlink,
                    priority: newEvent?.priority,
                    modifiable: newEvent?.modifiable,
                }
                setCalendarEvents(newEvents)
                } 
            } catch (e) {
                console.log(e, ' unable to get tags inside subscribeEventUpdated')
            }
            }
        })
        return () => subscription.unsubscribe()
    }, [client, calendarEvents, userId])

    // insert event subscription
    useEffect(() => {
        if (!client) {
        return
        }
        if (!userId) {
            return
        }

        const subscription = client.subscribe<{ Event: EventType[] }>({
        query: subscribeEventAdded,
        variables: {
            userId,
            currentDate: dayjs().format(),
        }
        })
        .subscribe({
        next: async (event) => {
          console.log(event, ' event 3 inside subscribeEventAdded')
          console.log(event?.data?.Event?.[0], ' event.data.Event[0] 3')
          const newEvent = event?.data?.Event?.[0]
          if (!newEvent?.id) {
            return
          }

          try {
            await setCurrentEventsForCalendarWeb(
              userId,
              client,
              setCalendarEvents,
            )
          } catch (e) {
            console.log(e, ' unable to get event lists inside subscribeEventAdded ')
          }
        }
        })
        return () => subscription.unsubscribe()
    }, [client, userId])

    // insert category Event subscription
    useEffect(() => {
        if (!userId) {
            return
        }

        const subscription = client.subscribe<{ Category_Event: CategoryEventType[] }>({
        query: subscribeEventAdded,
        variables: {
            userId,
            currentDate: dayjs().format(),
        }
        })
        .subscribe({
            next: async(event) => {
            try {
                console.log(event?.data?.Category_Event?.[0], ' event.data.Category_Event[0] 5')
                const newCategoryEvent = event?.data?.Category_Event?.[0]
                if (!newCategoryEvent?.id) {
                return
                }
                const newTags = (await client.query<{ Category: CategoryType[] }>({
                query: listCategoriesForEventId,
                variables: {
                    eventId: newCategoryEvent.eventId,
                },
                }))?.data?.Category?.map((c) => ({
                    id: c.id, 
                    name: c.name, 
                    color: c.color,
                }))
                const index = _.findIndex(calendarEvents, e => e.id === newCategoryEvent.eventId)
                if (index >= 0) {
                const newEvents = _.cloneDeep(calendarEvents)
                newEvents[index] = {
                    ...calendarEvents[index],
                    tags: newTags,
                    color: newTags?.[0]?.color || calendarEvents[index].color,
                }

                setCalendarEvents(newEvents)
                }
            } catch(e) {
                console.log(e)
            }
            }
        })
        return () => subscription.unsubscribe()
    }, [client, calendarEvents, userId])

    const changeLink = async (event: CalendarEventPro) => {
        try {
        const eventId = event?.id
        const existingEvent = (await client.query<{ Event_by_pk: EventType }>({
            query: getEventById,
            variables: {
                id: eventId,
            },
        })).data?.Event_by_pk
        if (existingEvent) {
            await client.mutate({
            mutation: updateEventForUnlink,
            variables: {
                id: existingEvent.id,
                unlink: !existingEvent.unlink,
            },
            })
        }
        } catch (e) {
        console.log(e, 'error for changeLink')
        }
    }

    const submitForPlan = async (event: CalendarEventPro) => {
        try {
                const existingEvent = (await client.query<{ Event_by_pk: EventType }>({
                query: getEventById,
                variables: {
                    id: event?.id,
                },
                })).data?.Event_by_pk
                if (existingEvent) {
                const filteredExistingEvent: EventType = _.omit(existingEvent, ['__typename']) as EventType
                const token = await Session.getAccessToken()
                const url = eventToQueueAuthUrl
                const config = {
                    headers: {
                    Authorization: `Bearer ${token}`,
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    },
                }
                // add method
                const eventWithMethod: EventType = { ...filteredExistingEvent, method: 'update' }
                const results = await axios.post(url, eventWithMethod, config)
                    if (results.data.message) {
                        toast({
                            status: 'success',
                            title: 'Event added to queue',
                            description: 'Event added to queue',
                            duration: 9000,
                            isClosable: true,
                        })
                    }
                }
        
        } catch (e) {
        console.log(e, 'error for changeLink')
        }
    }

    const changedModifiable = async (event: CalendarEventPro) => {
        try {
        const existingEvent = (await client.query<{ Event_by_pk: EventType }>({
            query: getEventById,
            variables: {
                id: event?.id,
            },
        })).data?.Event_by_pk
        console.log(existingEvent, ' existingEvent inside changedModifiable')
        if (existingEvent) {
            const res = await client.mutate({
            mutation: updateEventForModifiable,
            variables: {
                id: existingEvent.id,
                modifiable: !existingEvent.modifiable,
            },
            fetchPolicy: 'no-cache',
            update(cache, { data }) {
                if (data?.update_Event_by_pk?.id) {
                console.log('update_Event_by_pk?.id', data)
                }

                cache.modify({
                fields: {
                    Event(existingEvents = []) {
                    const newEventRef = cache.writeFragment({
                        data: data?.update_Event_by_pk,
                        fragment: gql`
                            fragment NewEvent on Event {
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
                        `
                    });
                    const filteredEvents = existingEvents?.filter((e: EventType) => (e?.id !== data?.update_Event_by_pk?.id)) || []
                    console.log(filteredEvents, ' filteredEvents inside updateEventForModifiable')
                    if (filteredEvents?.length > 0) {
                        return filteredEvents.concat([newEventRef])
                    }
                    return [newEventRef]
                    }
                }
                })
            }
            })
            console.log(res, ' res inside changedModifiable')
        }
        } catch (e) {
        console.log(e, 'error for changeLink')
        }
    }

    const onSelectSlot = useCallback((slotInfo: SlotInfo) => {
        setSelectedSlot(slotInfo)
        setIsCreateEvent(true)
    }, [])

    const hideIsCreateEvent = () => {
        setSelectedSlot(undefined)
        setIsCreateEvent(false)
    }

    const editEvent = (event: CalendarEventPro) => {
        setSelectedEditEventId(event?.id)
        setIsEditEvent(true)
    }

    const hideIsEditEvent = () => {
        setSelectedEditEventId('')
        setIsEditEvent(false)
    }

    const trainEvent = (event: CalendarEventPro) => {
        setSelectedTrainEventId(event?.id)
        setIsTrainEvent(true)
    }

    const hideIsTrainEvent = () => {
        setSelectedTrainEventId('')
        setIsTrainEvent(false)
    }

    const addFollowUp = (event: CalendarEventPro) => {
        setSelectedAddFollowUpId(event?.id)
        setIsAddFollowUp(true)
    }

    const hideIsAddFollowUp = () => {
        setSelectedAddFollowUpId('')
        setIsAddFollowUp(false)
    }

    const addTimePreferences = (event: CalendarEventPro) => {
        setSelectedEventIdForTimePreferences(event?.id)
        setIsAddTimePreferences(true)
    }

    const hideIsAddTimePreferences = () => {
        setSelectedEventIdForTimePreferences('')
        setIsAddTimePreferences(false)
    }

    const navigateToMeetingAssist =  () => {
        router.push({ pathname: '/Assist/UserCreateMeetingAssist' })
    }

    const featuresApplyToEvents = async () => {
        try {
        // validate start date && end date
        if (startScheduleDate && endScheduleDate) {
            if (startScheduleDate > endScheduleDate) {
            toast({
                status: 'error',
                title: 'Invalid start date',
                description: 'Start date must be before end date',
                duration: 9000,
                isClosable: true,
            })
            return
            }
        }

        const duration = dayjs(endScheduleDate).diff(dayjs(startScheduleDate), 'm')
        
        if ((duration < 120)) {
            toast({
                status: 'error',
                title: 'Invalid duration',
                description: 'Duration must be at least 120 minutes',
                duration: 9000,
                isClosable: true,
            })
            return
        }

        const durationDays = dayjs(endScheduleDate).diff(dayjs(startScheduleDate), 'd')
        if ((durationDays > 7)) {
            toast({
                status: 'error',
                title: 'Invalid duration',
                description: 'Duration must be less than a week',
                duration: 9000,
                isClosable: true,
            })
            return
        }

            const token = await Session.getAccessToken()
            const url = featuresApplyToEventsAuthUrl
            const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            }

            const results = await axios.post(url, { userId, windowStartDate: dayjs(startScheduleDate).format(), windowEndDate: dayjs(endScheduleDate).format(), timezone: dayjs.tz.guess() }, config)
            if (results.data.message) {
            toast({
                status: 'success',
                title: 'Applying Features to Events',
                description: 'Applying Features to Events. Check calendar in a bit.',
                duration: 9000,
                isClosable: true,
            })
            }
        
        } catch (e) {
        console.log(e, ' unable to features apply to events')
        }

        hideFeaturesApply()
    }

    const scheduleAssist = async () => {
        try {

        // validate start date && end date
        if (startScheduleDate && endScheduleDate) {
            if (startScheduleDate > endScheduleDate) {
            toast({
                status: 'error',
                title: 'Invalid start date',
                description: 'Start date must be before end date',
                duration: 9000,
                isClosable: true,
            })
            return
            }
        }

        const duration = dayjs(endScheduleDate).diff(dayjs(startScheduleDate), 'm')
        if ((duration < 120)) {
            toast({
                status: 'error',
                title: 'Invalid duration',
                description: 'Duration must be at least 120 minutes',
            })
            return
        }

        const durationDays = dayjs(endScheduleDate).diff(dayjs(startScheduleDate), 'd')
        if ((durationDays > 7)) {
            toast({
                status: 'error',
                title: 'Invalid duration',
                description: 'Duration must be less than a week',
                duration: 9000,
                isClosable: true,
            })
            return
        }
            const token = await Session.getAccessToken()
            const url = calendarToQueueAuthUrl
            const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            }

            const results = await axios.post(url, { userId, windowStartDate: dayjs(startScheduleDate).format(), windowEndDate: dayjs(endScheduleDate).format(), timezone: dayjs.tz.guess() }, config)
            if (results.data.message) {
            toast({
                status: 'success',
                description: 'Schedule assist started',
                title: 'Planning week. Check calendar in a bit.',
                duration: 9000,
                isClosable: true,
            })
            }
       
        
        } catch (e) {
        console.log(e, ' unable to schedule assist')
        }
        hideScheduleAssist()
    }



    const deleteEvent = async (id: string) => {
        try {
            hideDelete()
        
            const newEvents = _.filter(calendarEvents, e => e.id !== id)
            const newEventsByDate = _.groupBy(newEvents, e => dayjs(e?.start).format('YYYY-MM-DD'))

            const oldEvent = calendarEvents.find(e => (e?.id === id))
            
            setCalendarEvents(newEvents)
            if (oldEvent?.id) {
                const oldEventOriginal = await getEventWithId(client, oldEvent?.id)
                const forEvent = calendarEvents.find(e => (e?.id === oldEventOriginal?.forEventId))

                if (forEvent?.id) {
                
                const forEventOriginal = await getEventWithId(client, forEvent?.id)

                // preEvent
                if (forEventOriginal?.preEventId === id) {
                    // remove preEventId
                    await atomicUpsertEventInDb(
                    client,
                    forEventOriginal?.id,
                    forEventOriginal?.eventId,
                    forEventOriginal?.userId,
                    forEventOriginal?.startDate,
                    forEventOriginal?.endDate,
                    forEventOriginal?.createdDate,
                    forEventOriginal?.deleted,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    dayjs().format(),
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    null,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    { ...forEventOriginal?.timeBlocking, beforeEvent: 0 },

                    )
                }

                // postEvent
                if (forEventOriginal?.postEventId === id) {
                    // remove postEventId
                    await atomicUpsertEventInDb(
                    client,
                    forEventOriginal?.id,
                    forEventOriginal?.eventId,
                    forEventOriginal?.userId,
                    forEventOriginal?.startDate,
                    forEventOriginal?.endDate,
                    forEventOriginal?.createdDate,
                    forEventOriginal?.deleted,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    dayjs().format(),
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    null,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    { ...forEventOriginal?.timeBlocking, afterEvent: 0 },
                    )
                }
                }
            }

            // delete conference,  attendees and reminders
            await deleteAttendeesForEvent(client, id)
            const originalEvent = await getEventWithId(client, id)

            console.log(originalEvent, ' originalEvent')
            console.log(originalEvent?.meetingId, ' originalEvent?.meetingId')
            
            if (originalEvent?.conferenceId) {
                await deleteConferencesWithIds(client, [originalEvent?.conferenceId])
            }

            await removeRemindersForEvent(client, id)

            // remove search index after Delete
            // The deletion from the vector index (now LanceDB) is handled by the _event2VectorsWorker_
            // when the event is deleted from the primary database (via Kafka message).
            // So, no direct calls to a search/delete index URL are needed here anymore.

            // delete meeting assist given meeting id
            if (originalEvent?.meetingId) {
                const token = await Session.getAccessToken() // Keep token and config if needed for other calls below
                const config = {
                    headers: {
                        Authorization: `Bearer ${token}`,
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                    },
                }
                const meetingAssist = await getMeetingAssistGivenId(client, originalEvent.meetingId)
                await deleteMeetingAssistGivenId(client, originalEvent.meetingId)
                if (meetingAssist?.conferenceApp === 'zoom') {
                    const tokenCheck = await Session.getAccessToken() // Ensure token is still valid if time passed
                    if (!tokenCheck) throw new Error("Session expired, please log in again.");

                    const res = await axios.post(deleteZoomConferenceUrl, {
                        meetingId: originalEvent?.meetingId,
                        userId,
                    }, config) // config already defined if originalEvent.meetingId is true

                    console.log(res, ' successfully deleted zoom conference')
                }
            }
            await delEventInAppForTask(id, client, userId)
        } catch (e) {
            console.log(e, 'error for deleteEvent')
        }
    }

    const delEventInAppForTask = async (
        id: string,
        client: ApolloClient<NormalizedCacheObject>,
        userId: string,
    ) => {
        try {
            const eventDoc = (await client.query<{ Event_by_pk: EventType }>({
                query: getEventById,
                variables: {
                    id: id,
                },
            })).data?.Event_by_pk
            
            if (eventDoc?.id) {
                const calendarId = eventDoc?.calendarId
                const calendarDoc = (await client.query<{ Calendar_by_pk: CalendarType }>({
                    query: getCalendarById,
                    variables: {
                        id: calendarId,
                    },
                })).data?.Calendar_by_pk
                
                if (calendarDoc?.id) {
                  const resource = calendarDoc?.resource

                    if (resource === googleResourceName) {
                      await deleteGoogleEvent(client, userId, calendarId, id.split('#')[0])
                      await client.mutate<{ delete_Event_by_pk: EventType }>({
                        mutation: deleteEventById,
                        variables: {
                          id: id,
                        },
                        update(cache, { data }) {
                          const deletedEvent = data?.delete_Event_by_pk
                          const normalizedId = cache.identify({ id: deletedEvent.id, __typename: deletedEvent.__typename })
                          cache.evict({ id: normalizedId })
                          cache.gc()
                        },
                        // refetchQueries: [
                        //   listAllEvents, // DocumentNode object parsed with gql
                        //   'listAllEvents' // Query name
                        // ],
                        })
                    }
                }
            }
        } catch (e) {
          console.log(e, ' unable to delete event in app')
        }
    }

    const hideDelete = () => {
        setToDeleteId('')
        setIsDelete(false)
    }

    const showDelete = () => {
        setIsDelete(true)
    }

    const enableDelete = (event: CalendarEventPro) => {
        setToDeleteId(event?.id)
        // closeMenu(date, index)
        showDelete()
    }

    const hideTags = () => {
        setToTagId('')
        setIsEventTags(false)
        
    }

    const showTags = () => {
        setIsEventTags(true)
    }

    const enableTag = (event: CalendarEventPro) => {
        setToTagId(event?.id)
        // closeMenu(date, index)
        showTags()
    }
    
    const hideRating = () => {
        setToRateId('')
        setIsRateEvent(false)
    }

    const showRating = () => {
        setIsRateEvent(true)
    }

    const enableRate = async (event: CalendarEventPro) => {
        setToRateId(event?.id)
        // closeMenu(date, index)
        showRating()
    }

    const hidePrepAndReview = () => {
        setToPrepAndReviewEvent(null)
        setIsPrepAndRev(false)
    }

    const showPrepAndReview = () => {
        setIsPrepAndRev(true)
    }

    const enablePrepAndReview = async (event: CalendarEventPro) => {
        try {
            // closeMenu(date, index)
            showPrepAndReview()
            const eventDoc = (await client.query<{ Event_by_pk: EventType }>({
                query: getEventById,
                variables: {
                    id: event?.id,
                },
            })).data?.Event_by_pk
            setToPrepAndReviewEvent(eventDoc)
        } catch (e) {
            console.log(e, ' error in enablePrepAndReview')
        }
    }

    const hidePriority = () => {
        console.log('hid Priority called')
        setToPriorityId('')
        setIsPriority(false)
    }

    const showPriority = () => {
        setIsPriority(true)
    }

    const hideFeaturesApply = () => {
        setIsFeaturesApply(false)
    }

    const showFeaturesApply = () => {
        setStartScheduleDate(new Date())
        setIsFeaturesApply(true)
    }

    const hideScheduleAssist = () => {
        setIsScheduleAssist(false)
    }

    const showScheduleAssist = () => {
        setStartScheduleDate(new Date())
        setIsScheduleAssist(true)
    }

    const enablePriority = async (event: CalendarEventPro) => {
        try {
            // closeMenu(date, index)
            setToPriorityId(event?.id)
            setOldPriority(event?.priority)
            showPriority()
        } catch (e) {
        console.log(e, ' error in enablePriority')
        }
    }

    // event moved from another location
    const onEventMove = useCallback(async (args: OnCallBackArgType) => {
        try {
            const { event, start, end, isAllDay: droppedOnAllDaySlot = false } = args
            const newEvent = _.clone({...event, start: dayjs(start).toDate(), end: dayjs(end).toDate(), allDay: droppedOnAllDaySlot })
            
            const foundIndex = calendarEvents?.findIndex(e => (e?.id === event?.id))

            if (foundIndex > -1) {

                 await updateEvent(
                    newEvent?.id,
                    dayjs(start).format(),
                    dayjs(end).format(),
                    userId,
                    client,
                    newEvent?.calendarId,
                    undefined,
                    undefined,
                    droppedOnAllDaySlot,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    dayjs.tz.guess(),
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    dayjs.tz.guess(),
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    dayjs.duration(dayjs(end).diff(dayjs(start))).asMinutes(),
                    undefined,
                    undefined,
                    'update',
                    undefined,
                    undefined,
                )

                const firstPart = calendarEvents?.slice(0, foundIndex)
                const lastPart = calendarEvents?.slice(foundIndex + 1)

                const newCalendarEvents = firstPart?.concat([newEvent]).concat(lastPart)

                setCalendarEvents(newCalendarEvents)
            }

        } catch (e) {
            console.log(e, ' unable to event drop')
        }
    }, [calendarEvents, client, userId])

    // event is resized
    const onEventResize = useCallback(async (args: OnCallBackArgType) => {
        try {
            const { event, start, end } = args
            const newEvent = _.clone({ ...event, start: dayjs(start).toDate(), end: dayjs(end).toDate() })
            
            const foundIndex = calendarEvents?.findIndex(e => (e?.id === event?.id))

            if (foundIndex > -1) {

                await updateEvent(
                    newEvent?.id,
                    dayjs(start).format(),
                    dayjs(end).format(),
                    userId,
                    client,
                    newEvent?.calendarId,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    dayjs.tz.guess(),
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    dayjs.tz.guess(),
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    dayjs.duration(dayjs(end).diff(dayjs(start))).asMinutes(),
                    undefined,
                    undefined,
                    'update',
                    undefined,
                    undefined,
                )   

                const firstPart = calendarEvents?.slice(0, foundIndex)
                const lastPart = calendarEvents?.slice(foundIndex + 1)

                const newCalendarEvents = firstPart?.concat([newEvent]).concat(lastPart)

                setCalendarEvents(newCalendarEvents)
            }
        } catch (e) {
            console.log(e, ' unable to event resize')
        }
    }, [calendarEvents, client, userId])


    // clicked on existing event
    const onSelectEvent = useCallback(async (event: CalendarEventPro) => {
        try {
            setEventOfMenu(event)
            setTitle(event?.title as string)
            setAllDay(event?.allDay)
            setIsRecurring(!!event?.recurringEndDate)
            setInterval(event?.interval)
            setFrequency(event?.frequency)
            setNotes(event?.notes)
            setStartDate(dayjs(event?.start).toDate())
            setEndDate(dayjs(event?.end).toDate())
            setIsMenu(true)
            
        } catch (e) {
            console.log(e, ' unable to process event inside onDoubleClickEvent')
        }
    }, [])

    const closeMenu = useCallback(() => {
        setIsMenu(false)
    }, [])
    
    const editEventChild = () => {
        closeMenu()
        editEvent(eventOfMenu)
    }

    const trainEventChild = () => {
        closeMenu()
        trainEvent(eventOfMenu)
    }

    const enableTagChild = () => {
        closeMenu()
        enableTag(eventOfMenu)
    }

    const enableRateChild = () => {
        closeMenu()
        enableRate(eventOfMenu)
    }

    const enablePrepAndReviewChild = () => {
        closeMenu()
        enablePrepAndReview(eventOfMenu)
    }

    const addFollowUpChild = () => {
        closeMenu()
        addFollowUp(eventOfMenu)
    }

    const enablePriorityChild = () => {
        closeMenu()
        enablePriority(eventOfMenu)
    }

    const submitForPlanChild = async () => {
        closeMenu()
        return submitForPlan(eventOfMenu)
    }

    const changedModifiableChild = async () => {
        closeMenu()
        await changedModifiable(eventOfMenu)  
    }

    const changeLinkChild = async () => {
        closeMenu()
        return changeLink(eventOfMenu)
    }

    const enableDeleteChild = () => {
        closeMenu()
        enableDelete(eventOfMenu)
    }

    // addTimePreferences
    const addTimePreferencesChild = () => {
        closeMenu()
        addTimePreferences(eventOfMenu)
    }

    const updateEventForUser = async () => {
        try {
        // validate before update
        if (!userId || !client) {
            console.log('no userId or client inside updateEventForUser')
            return
        }

        if (!eventOfMenu?.id) {
            console.log('no eventId inside updateEventForUser')
            return
        }

        if (!eventOfMenu?.calendarId) {
            console.log('no calendarId inside updateEventForUser')
            return
        }



        console.log(frequency, interval,  ' frequency, interval inside updateEventForUser')
        await updateEvent(
            eventOfMenu?.id,
            dayjs(startDate).format(),
            dayjs(endDate).format(),
            userId,
            client,
            eventOfMenu?.calendarId,
            undefined,
            title,
            allDay,
            isRecurring ? dayjs(recurringEndDate).format() : null,
            isRecurring ? frequency : null,
            isRecurring ? parseInt (interval, 10) : null,
            undefined,
            notes,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            dayjs.tz.guess(),
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            title,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            dayjs.tz.guess(),
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            dayjs.duration(dayjs(endDate).diff(dayjs(startDate))).asMinutes(),
            undefined,
            undefined,
            'update',
            undefined,
            undefined,
        )

        toast({
            status: 'success',
            title: 'Event Edited',
            description: 'Event edited successfully',
            duration: 9000,
            isClosable: true,
        })

        setIsEventEditSuccess(true)
        setTimeout(() => setIsEventEditSuccess(false), 3000)
        
        } catch (e) {
        console.log(e, ' createEventForUser')
            toast({
                status: 'error',
                title: 'Event Editing failed',
                description: 'Unable to edit event. Please try again',
                duration: 9000,
                isClosable: true,
            })
        }
    }

    const eventPropGetter: EventPropGetter<CalendarEventPro> = useCallback((event: CalendarEventPro) => {

        return {
            style: {
                border: 'none',
                WebkitBoxSizing: 'border-box',
                boxSizing: 'border-box',
                WebkitBoxShadow: 'none',
                boxShadow: 'none',
                margin: '0',
                padding: '2px 5px',
                backgroundColor: event?.color ?? '#0B9CE5',
                borderRadius: '5px',
                color: '#000',
                cursor: 'pointer',
                width: '100%',
                textAlign: 'left',
            }
        }
    }, [])

    const actions = [
        { icon: <QueryStatsIcon color="secondary" />, name: 'Search & Apply Features', method: showFeaturesApply },
        { icon: <MeetingRoomIcon color="secondary" />, name: 'Meeting Assist', method: navigateToMeetingAssist },
        { icon: <ScheduleIcon color="secondary" />, name: 'Schedule Assist', method: showScheduleAssist }
    ];

    if (!calendarEvents?.[0]?.id) {
        return (
            <div className="flex w-full h-full justify-center items-center">
                <Box flex={1} backgroundColor="primaryCardBackground"  justifyContent="center" alignItems="center" style={{ width: '100%'}} minHeight="80vh">
                    <ActivityIndicator size="large" color={palette.white} />
                </Box>
            </div>
        )
    }
    
    return (
        <div>
            <DnDCalendar
                localizer={localizer}
                events={calendarEvents}
                style={{ height: 500 }}
                defaultDate={defaultDate}
                draggableAccessor={(event) => true}
                onEventDrop={onEventMove as any}
                onEventResize={onEventResize as any}
                selectable
                onSelectEvent={onSelectEvent as any}
                eventPropGetter={eventPropGetter as any}
                onSelectSlot={onSelectSlot}
            />
            <Modal
                isOpen={isCreateEvent}
                onRequestClose={hideIsCreateEvent}
                style={customModalStyles2}
                contentLabel="Create Event"
            >
                <UserCreateEvent
                    start={selectedSlot?.start}
                    end={selectedSlot?.end}
                    closeCreateEvent={hideIsCreateEvent}
                    client={client}
                    sub={sub}
                />
            </Modal>
            <Modal
                isOpen={isEditEvent}
                onRequestClose={hideIsEditEvent}
                style={customModalStyles2}
                contentLabel="Edit Event"
            >
                <UserEditEvent
                    id={selectedEditEventId}
                    closeEditEvent={hideIsEditEvent}
                    client={client}
                    sub={sub}
                />
            </Modal>
            <Modal
                isOpen={isTrainEvent}
                onRequestClose={hideIsTrainEvent}
                style={customModalStyles2}
                contentLabel="Train Event"
            >
                <UserTrainEvent
                    id={selectedTrainEventId}
                    closeTrainEvent={hideIsTrainEvent}
                    client={client}
                    sub={sub}
                />
            </Modal>
            <Modal
                isOpen={isAddFollowUp}
                onRequestClose={hideIsAddFollowUp}
                style={customModalStyles}
                contentLabel="Add Follow Up Event"
            >
                <UserAddFollowUp
                    id={selectedAddFollowUpId}
                    closeAddFollowUp={hideIsAddFollowUp}
                    client={client}
                    sub={sub}
                />
            </Modal>
            <Modal
                isOpen={isAddTimePreferences}
                onRequestClose={hideIsAddTimePreferences}
                style={customModalStyles2}
                contentLabel="Add Time Preferences"
            >
                <UserEventTimePreferences
                    id={selectedEventIdForTimePreferences}
                    closeTimePreferences={hideIsAddTimePreferences}
                    client={client}
                    sub={sub}
                />
            </Modal>
            <Modal
                isOpen={isDelete}
                onRequestClose={hideDelete}
                style={customModalStyles}

            >
                <Box justifyContent="center" alignItems="center">
                    <Text p={{ phone: 'm', tablet: 'l' }} variant="subheaderNormal">
                    Delete this event?
                    </Text>
                <Box justifyContent="center" alignItems="center">
                  <Box p={{ phone: 's', tablet: 'm'}}  justifyContent="center" alignItems="center">
                    <Button onClick={() => deleteEvent(toDeleteId)}>
                      Delete
                    </Button>
                  </Box>
                  <Box p={{ phone: 's', tablet: 'm'}}  justifyContent="center" alignItems="center">
                    <button className="btn btn-link no-underline hover:no-underline" onClick={hideDelete}>
                      Cancel
                    </button>
                  </Box>
                </Box>
                </Box>
            </Modal>
            <Modal
                isOpen={isEventTags}
                onRequestClose={hideTags}
                style={customModalStyles}
            >
                <UserEditCategoryEventModal
                    eventId={toTagId}
                    hideTags={hideTags}
                    sub={userId}
                    client={client}
                />
            </Modal>
            <Modal
                isOpen={isRateEvent}
                onRequestClose={hideRating}
                style={customModalStyles}
            >
                <UserRateEvent
                    eventId={toRateId}
                    hideRating={hideRating}
                    userId={userId}
                    isRateEvent={isRateEvent}
                    client={client}
                />
            </Modal>
            <Modal
                isOpen={isPrepAndReview}
                onRequestClose={hidePrepAndReview}
                style={customModalStyles}
            >
                <UserPreAndPostForEventModal
                    event={toPrepAndRevEvent as EventType}
                    hidePrepAndReview={hidePrepAndReview}
                    client={client}
                />
            </Modal>
            <Modal
                isOpen={isPriority}
                onRequestClose={hidePriority}
                style={customModalStyles}
            >
                <UserEditEventPriorityModal
                    eventId={toPriorityId}
                    hidePriority={hidePriority}
                    priority={oldPriority}
                    client={client}
                />
            </Modal>
            <Modal
                isOpen={(isFeaturesApply)}
                onRequestClose={hideFeaturesApply}
                style={customModalStyles}
            >
                <Box p={{ phone: 's', tablet: 'm' }} justifyContent="center" alignItems="center" width="90%" height="100%">
                    <Text variant="optionHeader">Start Date</Text>

                    <Input
                        placeholder="Select Date and Time"
                        size="md"
                        type="datetime-local"
                        onChange={(e) => {
                        setStartScheduleDate(dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm").toDate())
                        if (dayjs(e?.target?.value).isAfter(dayjs(endScheduleDate))) {
                            setEndScheduleDate(dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm").add(120, 'm').toDate())
                        }
                        const duration = dayjs(endScheduleDate).diff(dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm"), 'm')
                        if (duration < 120) {
                            setEndScheduleDate(dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm").add(120, 'm').toDate())
                        }
                        const durationDays = dayjs(endScheduleDate).diff(dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm"), 'd')
                        if (durationDays > 7) {
                            setEndScheduleDate(dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm").add(6, 'd').toDate())
                        }
                        
                        }}
                        value={dayjs(startScheduleDate).format("YYYY-MM-DDTHH:mm")}
                    />
                </Box>
                <Box p={{ phone: 's', tablet: 'm' }} justifyContent="center" alignItems="center" width="90%">
                <Text variant="optionHeader">End Date</Text>
                <Input
                    placeholder="Select Date and Time"
                    size="md"
                    type="datetime-local"
                    onChange={(e) => {
                        setEndScheduleDate(dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm").toDate())
                    
                    }}
                    value={dayjs(endScheduleDate).format("YYYY-MM-DDTHH:mm")}
                />
                </Box>
                <Box p={{ phone: 'm', tablet: 'l' }} justifyContent="center" alignItems="center">
                <Button onClick={featuresApplyToEvents}>
                    Apply Features
                </Button>
                </Box>
                <Box p={{ phone: 'm', tablet: 'l' }} justifyContent="center" alignItems="center">
                    <button className="btn btn-link no-underline hover:no-underline" onClick={hideFeaturesApply}>
                        Close
                    </button>
                </Box>
            </Modal>
            <Modal
                isOpen={isScheduleAssist}
                onRequestClose={hideScheduleAssist}
                style={customModalStyles}
            >
                <Box pt={{ phone: 'm', tablet: 's' }} justifyContent="center" alignItems="center" width="90%">
                    <div className="flex flex-col items-start">
                        <Text variant="optionHeader">Start Date</Text>
                        <Input
                            placeholder="Select Date and Time"
                            size="md"
                            type="datetime-local"
                            onChange={(e) => {
                                setStartScheduleDate(dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm").toDate())
                                if (dayjs(e?.target?.value).isAfter(dayjs(endScheduleDate))) {
                                    setEndScheduleDate(dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm").add(120, 'm').toDate())
                                }
                                const duration = dayjs(endScheduleDate).diff(dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm"), 'm')
                                if (duration < 120) {
                                    setEndScheduleDate(dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm").add(120, 'm').toDate())
                                }
                                const durationDays = dayjs(endScheduleDate).diff(dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm"), 'd')
                                if (durationDays > 7) {
                                    setEndScheduleDate(dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm").add(6, 'd').toDate())
                                }
                            
                            }}
                            value={dayjs(startScheduleDate).format("YYYY-MM-DDTHH:mm")}
                        />
                    </div>
                </Box>
                <Box p={{ phone: 's', tablet: 'm' }} justifyContent="center" alignItems="center" width="90%">
                    <div className="flex flex-col items-start">
                        <Text variant="optionHeader">End Date</Text>
                        <Input
                            placeholder="Select Date and Time"
                            size="md"
                            type="datetime-local"
                            onChange={(e) => {
                                setEndScheduleDate(dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm").toDate())
                            
                            }}
                            value={dayjs(endScheduleDate).format("YYYY-MM-DDTHH:mm")}
                        />
                    </div>
                </Box>
                <Box p={{ phone: 'm', tablet: 'l' }} justifyContent="center" alignItems="center">
                <Button onClick={scheduleAssist}>
                    Schedule Assist
                </Button>
                </Box>
                <Box p={{ phone: 'm', tablet: 'l' }} justifyContent="center" alignItems="center">
                    <button className="btn btn-link no-underline hover:no-underline" onClick={hideScheduleAssist}>
                        Close
                    </button>
                </Box>
            </Modal>
            <Modal
                isOpen={isMenu}
                onRequestClose={closeMenu}
                style={customModalStyles2}
                contentLabel="Menu"
            >
                <div className="flex flex-col items-center md:m-6 m-3 h-full w-full">
                    {isEventEditSuccess && (<div className="alert alert-success shadow-lg">
                        <div>
                            <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current flex-shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                            <span>Successfully edited event!</span>
                        </div>
                    </div>)}
                    <div className="md:flex-auto md:basis-1/4 md:w-1/2 w-full">
                        <div className="flex flex-col flex-start items-start w-full">
                            <TextField
                                label="Title or Summary"
                                onChange={(e: { target: { value: React.SetStateAction<string> } }) => setTitle(e?.target?.value)}
                                value={title || ''}
                            />
                            <TextField
                                label="Notes"
                                onChange={(e: { target: { value: React.SetStateAction<string> } }) => setNotes(e?.target?.value)}
                                value={notes || ''}
                                multiline
                                numberOfLines={3}
                            />
                        </div>
                        <div className="flex justify-between items-center w-full">
                            <div className="flex flex-col items-start">
                                <label className="label">
                                    <span className="label-text">
                                    Start
                                    </span>
                                </label>
                               <Input
                                    placeholder="Select Date and Time"
                                    size="md"
                                    type="datetime-local"
                                    onChange={(e) => {
                                        const durationMinutes = dayjs.duration(dayjs(endDate).diff(dayjs(startDate))).asMinutes()
                                        const newEndDate = dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm").add(durationMinutes, 'minutes').toDate()
                                        setStartDate(dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm").toDate())
                                        setEndDate(newEndDate)
                                    }}
                                    value={dayjs(startDate).format("YYYY-MM-DDTHH:mm")}
                                />
                            </div>
                            <div className="flex flex-col items-start">
                                <label className="label">
                                    <span className="label-text">
                                    End
                                    </span>
                                </label>
                                <Input
                                    placeholder="Select Date and Time"
                                    size="md"
                                    type="datetime-local"
                                    onChange={(e) => {
                                        setEndDate(dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm").toDate())
                                    }}
                                    value={dayjs(endDate).format("YYYY-MM-DDTHH:mm")}
                                />
                            </div>
                        </div>
                         <div className="flex justify-between items-center w-full">
                            <div />
                            <div className="form-control w-52">
                                <label className="cursor-pointer label">
                                    <span className="label-text">All day</span> 
                                    <input type="checkbox" className="toggle toggle-primary" onChange={(e) => setAllDay(e?.target?.checked)}  checked={allDay} />
                                </label>
                            </div>
                        </div>
                        <div className="flex justify-between items-center w-full">
                            <div />
                            <div className="form-control w-52">
                                <label className="cursor-pointer label">
                                    <span className="label-text">Recurring</span> 
                                    <input type="checkbox" className="toggle toggle-primary" onChange={(e) => setIsRecurring(e?.target?.checked)}  checked={isRecurring} />
                                </label>
                            </div>
                        </div>
                        {isRecurring && (
                            <div className="flex justify-between items-center w-full">
                                <TextField
                                    className="w-24"
                                    onChange={(e: { target: { value: string } }) => setInterval(e?.target?.value?.replace(/[^0-9.]/g, '') || '0')}
                                    value={interval}
                                />
                                <select name="frequency" className="select select-primary w-full max-w-xs" onChange={(e) => setFrequency(e?.target?.value as RecurrenceFrequencyType)} value={frequency}>
                                    <option disabled selected>Select your frequency</option>
                                    <option>daily</option>
                                    <option>weekly</option>
                                    <option>monthly</option>
                                    <option>yearly</option>
                                </select>
                            </div>
                        )}
                    </div>
                    <div className="md:basis-1/2 md:w-1/2 w-full">
                        <div className=" flex justify-between w-full">
                            <div className="flex justify-between w-full ">
                                <div />
                                <Button className="m-3" onClick={closeMenu}>
                                    Close
                                </Button>
                            </div>
                            <div className="flex justify-between w-full">
                                <div />
                                <Button className="m-3" onClick={updateEventForUser}>
                                    Save
                                </Button>
                            </div>
                        </div>
                    </div>
                    <div className="md:flex-auto md:basis-3/4 md:w-1/2 md:flex md:flex-wrap w-full">
                        <button className="btn btn-link no-underline hover:no-underline md:my-3" onClick={editEventChild}>
                            <span className="md:my-3 flex justify-start items-center">
                                <MdOutlineEditCalendar size="3em" />
                                <span className="ml-4">Edit</span>
                            </span>
                        </button>
                        
                        <button className="btn btn-link no-underline hover:no-underline md:my-3" onClick={trainEventChild}>
                            <span className="md:my-3 flex justify-start items-center">
                                <GiArtificialIntelligence size="3em" />
                                <span className="ml-4">Train</span>
                            </span>
                        </button>
                        <button className="btn btn-link no-underline hover:no-underline md:my-3" onClick={addTimePreferencesChild}>
                            <span className="md:my-3 flex justify-start items-center">
                                <MdOutlineAccessTime size="3em" />
                                <span className="ml-4">Time Preferences</span>
                            </span>
                        </button>
                        
                        <button className="btn btn-link no-underline hover:no-underline md:my-3" onClick={enableTagChild}>
                            <span className="md:my-3 flex justify-start items-center">
                                <IoMdPricetag size="3em" />
                                <span className="ml-4">Tags</span>
                            </span>
                        </button>
                        {/* {MdStarRate} */}
                        <button className="btn btn-link no-underline hover:no-underline md:my-3" onClick={enableRateChild}>
                            <span className="md:my-3 flex justify-start items-center">
                                <MdStarRate size="3em" />
                                <span className="ml-4">Rate</span>
                            </span>
                        </button>
                        {/* {MdCalendarMonth} */}
                        <button className="btn btn-link no-underline hover:no-underline md:my-3" onClick={enablePrepAndReviewChild}>
                            <span className="md:my-3 flex justify-start items-center">
                                <MdCalendarMonth size="3em" />
                                <span className="ml-4">Buffer</span>
                            </span>
                        </button>
                        {/* {BsCalendarPlus} */}
                        <button className="btn btn-link no-underline hover:no-underline md:my-3" onClick={addFollowUpChild}>
                            <span className="md:my-3 flex justify-start items-center">
                                <BsCalendarPlus size="3em" />
                                <span className="ml-4">Add Follow Up</span>
                            </span>
                        </button>
                        {/* {MdOutlineLowPriority} */}
                        <button className="btn btn-link no-underline hover:no-underline md:my-3" onClick={enablePriorityChild}>
                            <span className="md:my-3 flex justify-start items-center">
                                <MdOutlineLowPriority size="3em" />
                                <span className="ml-4">Priority</span>
                            </span>
                        </button>
                        {eventOfMenu?.modifiable
                        ? (
                            <div>
                                
                                <button className="btn btn-link no-underline hover:no-underline md:my-3" onClick={changedModifiableChild}>
                                    <span className="md:my-3 flex justify-start items-center">
                                        <MdLockOpen size="3em" />
                                        <span className="ml-4">Time Modifiable</span>
                                    </span>
                                </button>
                            </div>
                        ): (
                                <div>
                                    <button className="btn btn-link no-underline hover:no-underline md:my-3" onClick={changedModifiableChild}>
                                        <span className="md:my-3 flex justify-start items-center">
                                            <MdLockOutline size="3em" />
                                            <span className="ml-4">Time Not Modifiable</span>
                                        </span>
                                    </button>
                               </div> 
                        )}
                        {/* {MdLink} */}
                        {eventOfMenu?.unlink
                        ? (
                            <div>
                                <button className="btn btn-link no-underline hover:no-underline md:my-3" onClick={changeLinkChild}>
                                    <span className="md:my-3 flex justify-start items-center">
                                        <MdLinkOff size="3em" />
                                        <span className="ml-4">Link Off</span>
                                    </span>
                                </button>
                            </div>
                        ) : (
                                <div>
                                    <button className="btn btn-link no-underline hover:no-underline md:my-3" onClick={changeLinkChild}>
                                        <span className="md:my-3 flex justify-start items-center">
                                            <MdLink size="3em" />
                                            <span className="ml-4">Link On</span>
                                        </span>
                                    </button>
                                </div>
                            )}
                        {/* {BsCalendarMinus} */}
                        <button className="btn btn-link no-underline hover:no-underline md:my-3" onClick={enableDeleteChild}>
                            <span className="md:my-3 flex justify-start items-center">
                                <BsCalendarMinus size="3em" />
                                <span className="ml-4">Delete</span>
                            </span>
                        </button>
                        {/* Agent Attendance Buttons and Status */}
                        <Box width="100%" my={{phone: 's', tablet: 'm'}} p={{phone: 's', tablet: 'm'}} borderWidth="1px" borderRadius="md" borderColor="gray.300">
                            <Text variant="label" mb="s">Agent Assistance</Text>
                            {isAgentAttendingMeeting && selectedMeetingForAgentId === eventOfMenu?.id ? (
                                <Button colorScheme="red" onClick={() => handleStopAgent(eventOfMenu)} width="100%">
                                    Stop Agent Notes
                                </Button>
                            ) : (
                                <Button
                                    colorScheme="teal"
                                    onClick={() => handleAttendWithAgent(eventOfMenu)}
                                    isDisabled={!getMeetingPlatformAndIdentifier(eventOfMenu)}
                                    width="100%"
                                >
                                    Attend with Agent
                                </Button>
                            )}
                            {isAgentAttendingMeeting && selectedMeetingForAgentId === eventOfMenu?.id && agentMeetingStatus && (
                                <Text mt="s" fontSize="sm" color="gray.600">{agentMeetingStatus}</Text>
                            )}
                            {!getMeetingPlatformAndIdentifier(eventOfMenu) && !(isAgentAttendingMeeting && selectedMeetingForAgentId === eventOfMenu?.id) && (
                                <Text mt="s" fontSize="xs" color="gray.500">
                                    No recognizable meeting link (Google Meet, Zoom, Teams) found in event details for live attendance.
                                </Text>
                            )}
                        </Box>
                        {/* End Agent Attendance Buttons and Status */}
                    </div>
                    
                </div>
            </Modal>
            <div className="absolute inset-0 z-20 pointer-events-none">
                <SpeedDial
                    ariaLabel="Calendar SpeedDial"
                    sx={{ position: 'absolute', bottom: 24, right: 24, zIndex: 'speedDial' }}
                    icon={<SpeedDialIcon sx={{ color: pink[500] }} />}
                >
                    {actions.map((action) => (
                        <SpeedDialAction
                            key={action.name}
                            icon={action.icon}
                            tooltipTitle={action.name}
                            FabProps={{
                                onClick: action.method,
                            }}
                        />
                    ))}
                </SpeedDial>
            </div>
        </div>
    )
}

export default UserViewCalendarWeb
