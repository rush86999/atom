import React, { useState, useEffect, useCallback } from 'react'
import Wizard from '@components/Wizard'

import { useToast } from '@chakra-ui/react'
import Box from '@components/common/Box'
import Text from '@components/common/Text'
import Button from '@components/Button'
import RegularCard from '@components/RegularCard'
import { dayjs } from '@lib/date-utils'

import {
  CategoryType
} from '@lib/dataTypes/CategoryType'
import {
  listCategoriesForEvent,
  listUserCategories,
} from '@lib/Category/CategoryHelper'

import {
  zoomAvailable
} from '@lib/zoom/zoomMeetingHelper'
import {
  googleMeetAvailable,
} from '@lib/calendarLib/googleCalendarHelper'
import { Person, RecurrenceFrequencyType } from '@lib/Calendar/types'
import { VisibilityType } from '@lib/calendarLib/types'

import EditEventAttendees from '@pages/Calendar/EditEventWizard/EditEventAttendees'
import EditEventBaseStep from '@pages/Calendar/EditEventWizard/EditEventBaseStep'
import EditEventBaseStep2 from '@pages/Calendar/EditEventWizard/EditEventBaseStep2'
import EditEventBaseStep3 from '@pages/Calendar/EditEventWizard/EditEventBaseStep3'
import EditEventRecurStep from '@pages/Calendar/EditEventWizard/EditEventRecurStepAlt'
import EditEventVirtualMeet from '@pages/Calendar/EditEventWizard/EditEventVirtualMeet'
import EditEventVisibilityAndAlarmsStep from '@pages/Calendar/EditEventWizard/EditEventVisibilityAndAlarmsStep'
import EditEventUpdateCategories from '@pages/Calendar/EditEventWizard/EditEventUpdateCategories'


import { updateEvent } from '@lib/Calendar/UserEditCalendarHelper'
import { CalendarType } from '@lib/dataTypes/CalendarType'
import { EventType } from '@lib/dataTypes/EventType'
import { listRemindersForEvent } from '@lib/Calendar/Reminder/ReminderHelper'
import { listAttendeesForEvent } from '@lib/Calendar/Attendee/AttendeeHelper'
import { TransparencyType } from '@lib/calendarLib/types';
import { Day } from '@lib/Schedule/constants'
import { ApolloClient, NormalizedCacheObject } from '@apollo/client'
import getGlobalPrimaryCalendar from '@lib/apollo/gql/getGlobalPrimaryCalendar'
import getEventById from '@lib/apollo/gql/getEventById'
import getConferenceById from '@lib/apollo/gql/getConferenceById'
import { ConferenceType } from '@lib/dataTypes/ConferenceType'
import getCalendarById from '@lib/apollo/gql/getCalendarById'
import { useFocusEffect } from '@chakra-ui/react'
import { useAppContext } from '@lib/user-context'
import { useRouter } from 'next/router'
import { NextApiRequest, NextApiResponse } from 'next';
import supertokensNode from 'supertokens-node'
import { backendConfig } from '../../config/backendConfig'
import Session from 'supertokens-node/recipe/session'

export async function getServerSideProps({ req, res }: { req: NextApiRequest, res: NextApiResponse }) {
  // Notice how the server uses `API` from `withSSRContext`, instead of the top-level `API`.
  // const SSR = withSSRContext({ req })
  // this runs on the backend, so we must call init on supertokens-node SDK
  supertokensNode.init(backendConfig())
  let session
  try {
    session = await Session.getSession(req, res, {
      overrideGlobalClaimValidators: async function () {
        return []
      },
    })
  } catch (err: any) {
    if (err.type === Session.Error.TRY_REFRESH_TOKEN) {
      return { props: { fromSupertokens: 'needs-refresh' } }
    } else if (err.type === Session.Error.UNAUTHORISED) {
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


type Props = {
  id: string,
  closeEditEvent: () => void,
  client: ApolloClient<NormalizedCacheObject>,
  sub: string,
}

function UserEditEvent(props: Props) {
  const [categories, setCategories] = useState<CategoryType[]>([])
  const [selectedCategories, setSelectedCategories] = useState<CategoryType[]>([])
  const [title, setTitle] = useState<string>()
  const [allDay, setAllDay] = useState<boolean>(false)
  const [isRecurring, setIsRecurring] = useState<boolean>(false)
  const [recurringEndDate, setRecurringEndDate] = useState<Date>(new Date())
  const [frequency, setFrequency] = useState<RecurrenceFrequencyType>('daily')
  const [interval, setInterval] = useState<string>('1')
  const [alarms, setAlarms] = useState<number[]>([]) // will be number for createEvent function
  const [notes, setNotes] = useState<string>()
  const [location, setLocation] = useState<string>()
  const [isZoomAvailable, setIsZoomAvailable] = useState<boolean>(false)
  const [isGoogleMeetAvailable, setIsGoogleMeetAvailable] = useState<boolean>(false)
  const [zoomMeet, setZoomMeet] = useState<boolean>()
  const [googleMeet, setGoogleMeet] = useState<boolean>()
  const [zoomPrivateMeeting, setZoomPrivateMeeting] = useState<boolean>(false)
  const [attendees, setAttendees] = useState<Person[]>([])
  const [visibility, setVisibility] = useState<VisibilityType>('default')
  const [isAttendees, setIsAttendees] = useState<boolean>(false)
  const [activeIndex, setActiveIndex] = useState<number>(0)
  const [completedStep, setCompletedStep] = useState<number | undefined>()
  const [selectedCalendarId, setSelectedCalendarId] = useState<string>()
  const [calendar, setCalendar] = useState<CalendarType>()
  const [isBreak, setIsBreak] = useState<boolean>(false)
  const [startDate, setStartDate] = useState<Date>(new Date())
  const [endDate, setEndDate] = useState<Date>(new Date())
  const [transparency, setTransparency] = useState<TransparencyType>('opaque')
  const [isExternalMeeting, setIsExternalMeeting] = useState<boolean>(false)
  const [isMeeting, setIsMeeting] = useState<boolean>(false)
  const [modifiable, setModifiable] = useState<boolean>(true)
  const [byWeekDay, setByWeekDay] = useState<Day[]>([])
  const [oldEvent, setOldEvent] = useState<EventType>()

  const router = useRouter()
  const toast = useToast()
  
  const userId = props?.sub
  const id = props?.id
  const closeEditEvent = props?.closeEditEvent
  const client = props?.client
  
  console.log(id, ' eventId prerender inside usereditevent')
  // get categories
  useEffect(() => {
    (async() => {
      try {
        if (!userId || !client) {
          console.log(userId, client, 'no userId or client')
          return
        }
        const results = await listUserCategories(client, userId)

        if (!results?.[0]?.id) {
          console.log(' no categories available')
          return
        }
        setCategories(results)
      } catch(e) {
        console.log(e, ' unable to get categories')
      }
    })()
  }, [client, userId])

  // get event selected categories
  useEffect(() => {
    (async () => {
      try {
        if (!id || !client) {
          console.log(userId, client, 'no userId or client')
          return
        }
        const results = await listCategoriesForEvent(client, id)
        console.log(results, ' listCategoriesForEvent inside usereditevent')
        if (!results?.[0]?.id) {
          console.log(' no selected categories available')
          return

        }
        setSelectedCategories(results)
      } catch (e) {
        console.log(e, ' unable to get selected categories')

      }
    })()
  }, [client, id, userId])

   // check if zoom available
  useEffect(() => {
    (async () => {
      if (!userId || !client) {
        console.log(userId, client, 'no userId or client')
        return
      }
      const isAvailable = await zoomAvailable(client, userId)
      if (isAvailable) {
        setIsZoomAvailable(true)
      }
    })()
  }, [client, userId])

   // check if google available
  useEffect(() => {
    (async () => {
      if (!userId || !client) {
        console.log(userId, client, 'no userId or client')
        return
      }
      const isAvailable = await googleMeetAvailable(client, userId)
      if (isAvailable) {
        setIsGoogleMeetAvailable(isAvailable)
      }
    })()
  }, [client, userId])

  // get event Calendar else global primary calendar
  useEffect(() => {
    (async () => {  
      if (!userId || !client) {
        return
      }
      if (!id) {
        console.log(' no eventId')
      }

      const event = (await client.query<{ Event_by_pk: EventType }>({
        query: getEventById,
        variables: {
            id: id,
        },
      })).data?.Event_by_pk
      if (!event?.id) {

        console.log(' no event available')
        return
      }
      const calendarDoc = (await client.query<{ Calendar_by_pk: CalendarType }>({
        query: getCalendarById,
        variables: {
          id: event?.calendarId,
        },
      })).data?.Calendar_by_pk

      if (!calendarDoc?.id) {
        const calendar = (await client.query<{ Calendar: CalendarType[] }>({
          query: getGlobalPrimaryCalendar, 
          variables: {
            userId,
          },
        })).data?.Calendar?.[0]
        if (!calendar?.id) {
          console.log(' no primary calendar available')
          return
        }
        setSelectedCalendarId(calendar?.id)
        setCalendar(calendar)
      } else {
        setSelectedCalendarId(calendarDoc?.id)
        setCalendar(calendarDoc)
      }
    })()
  }, [client, id, userId])


  // get alarms
  useEffect(() => {
    (async () => {
      if (!id || !client) {
        return
      }
      const results = await listRemindersForEvent(client, id)
      if (!results?.[0]?.minutes) {
        console.log(' no alarms available')
        return
      }
      setAlarms(results?.map(r => r.minutes))
    })()
  }, [client, id])

  
  // get event
  useEffect(() => {
    (async () => {
      console.log(' get event useEffect called inside usereditevent')
      if (!id || !client) {
        console.log('no eventId or client inside userEditEvent')
        return
      }
      const event = (await client.query<{ Event_by_pk: EventType }>({
        query: getEventById,
        variables: {
            id: id,
        },
      })).data?.Event_by_pk
      if (!event?.id) {

        console.log(' no event available')
        return
      }
      console.log(event, ' event inside usereditevent')
      setTitle(event?.title || event?.summary)
      setAllDay(event?.allDay)
      setIsRecurring(event?.recurrence?.length > 0)
      if (event?.recurrenceRule?.endDate) {
        setRecurringEndDate(dayjs(event?.recurrenceRule?.endDate?.slice(0, 19)).tz(event?.timezone, true).toDate())
        setFrequency(event?.recurrenceRule?.frequency as RecurrenceFrequencyType)
        setInterval(`${event?.recurrenceRule?.interval}`)
      }
      setStartDate(dayjs.tz(event?.startDate, event?.timezone || dayjs.tz.guess()).toDate())
      setEndDate(dayjs.tz(event?.endDate, event?.timezone || dayjs.tz.guess()).toDate())
      setNotes(event?.notes)
      setLocation(event?.location?.title)
      setVisibility(event?.visibility)
      setIsBreak(event?.isBreak)
      setTransparency(event?.transparency)
      setIsExternalMeeting(event?.isExternalMeeting)
      setIsMeeting(event?.isMeeting)
      setModifiable(event?.modifiable)
      setByWeekDay(event?.byWeekDay as Day[])
      setOldEvent(event)
    })()
  }, [client, id])


  // get conference in db
  useEffect(() => {
    (async () => {
      if (!id || !client) {
        return
      }
      const oldEvent = (await client.query<{ Event_by_pk: EventType }>({
        query: getEventById,
        variables: {
            id: id,
        },
      })).data?.Event_by_pk
      if (!oldEvent?.id) {
        console.log(' no event available')
        return
      }

      if (!oldEvent?.conferenceId) {
        console.log(oldEvent?.conferenceId, ' no conferenceId inside userEditEvent')
        return
      }
      const conference = (await client.query<{ Conference_by_pk: ConferenceType }>({
        query: getConferenceById,
        variables: {
            id: oldEvent?.conferenceId,
            },
        })).data?.Conference_by_pk
      if (!conference?.id) {
        console.log(' no conference available')
        return
      }
      if (conference?.app === 'zoom') {
        setZoomMeet(true)
      }
      if (conference?.app === 'google') {
        setGoogleMeet(true)
      }

      if (conference?.zoomPrivateMeeting === true) {
        setZoomPrivateMeeting(true)
      }
    })()
  }, [client, id])

  // get event attendees
  useEffect(() => {
    (async () => {
      if (!id || !client) {
        return
      }
      const results = await listAttendeesForEvent(client, id)
      if (!results?.[0]?.id) {
        console.log(' no attendees available')
        return
      }
      setAttendees(results.map(r => ({ id: r.id, name: r.name, emails: r.emails, phoneNumbers: r.phoneNumbers, imAddresses: r.imAddresses, additionalGuests: r.additionalGuests, optional: r.optional, resource: r.resource } as Person)))
      setIsAttendees(true)
    })()
  }, [client, id])


  const updateEventForUser = async () => {
    try {
      // validate before update
      if (!userId || !client) {
        console.log('no userId or client inside updateEventForUser')
        return
      }

      if (!id) {
        console.log('no eventId inside updateEventForUser')
        return
      }

      if (!selectedCalendarId) {
        console.log('no calendarId inside updateEventForUser')
        return
      }



      console.log(frequency, interval, byWeekDay, ' frequency, interval and byWeekDay inside updateEventForUser')
      await updateEvent(
        id,
        dayjs(startDate).format(),
        dayjs(endDate).format(),
        userId,
        client,
        selectedCalendarId,
        selectedCategories?.map(category => category.id),
        title,
        allDay,
        isRecurring ? dayjs(recurringEndDate).format() : null,
        isRecurring ? frequency : null,
        isRecurring ? parseInt (interval, 10) : null,
        alarms,
        notes,
        location ? { title: location } : undefined,
        false,
        false,
        false,
        modifiable,
        undefined,
        undefined,
        undefined,
        false,
        dayjs.tz.guess(),
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        zoomMeet,
        googleMeet,
        'scheduled',
        undefined,
        zoomPrivateMeeting,
        attendees,
        undefined,
        undefined,
        attendees?.[0]?.emails?.[0]?.value ? 'all' : undefined,
        undefined,
        title,
        transparency,
        visibility,
        undefined,
        undefined,
        undefined,
        calendar?.colorId,
        dayjs.tz.guess(),
        selectedCategories?.[0]?.color || oldEvent?.backgroundColor || calendar?.backgroundColor,
        oldEvent?.foregroundColor ||  calendar?.foregroundColor,
        alarms?.length > 0 ? false : true,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        isExternalMeeting,
        undefined,
        undefined,
        isMeeting,
        undefined,
        undefined,
        isBreak,
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
        true,
        undefined,
        undefined,
        alarms?.length > 0,
        undefined,
        true,
        true,
        true,
        undefined,
        undefined,
        undefined,
        undefined,
        true,
        true,
        dayjs.duration(dayjs(endDate).diff(dayjs(startDate))).asMinutes(),
        undefined,
        undefined,
        'update',
        undefined,
        byWeekDay,
      )

      toast({
        status: 'success',
        title: 'Event Edited',
        description: 'Event edited successfully',
        duration: 9000,
        isClosable: true,
      })
      closeEditEvent()
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

  const onActiveIndexChanged = (index: number) => setActiveIndex(index)

  const goToPrevStep = () => {
    const prevActiveIndex = activeIndex
    if (((activeIndex - 1) === 3) && (!isRecurring)) {
      setActiveIndex(prevActiveIndex - 2)
    } else {
      const newActiveIndex = prevActiveIndex === 0 ? 0 : prevActiveIndex - 1
      setActiveIndex(newActiveIndex)
    }
    
  }

  const renderPrevButton = () => {
    if (activeIndex === 0) {
      return <Box pt={{ phone: 'm', tablet: 's' }}/>
    }

    return (
    <Box p={{ phone: 's', tablet: 'm' }}>
      <Button onClick={goToPrevStep}>
        Back
      </Button>
    </Box>
  )}
  
  const goToNextStep = () => {
    const prevActiveIndex = activeIndex
    const prevCompletedStep = completedStep
    /**
     0 - EditEventBaseStep
     1 - EditEventBaseStep2
     2 - EditEventBaseStep3
     3 - EditEventRecurStep
     4 - EditEventVirtualMeet
     5 - EditEventAttendees
     6 - EditEventVisibilityAndAlarmsStep
     7 - EditEventUpdateCategories
     */
    if (prevActiveIndex === 8) {
      return
    }
    if (!isRecurring && isAttendees) {
      let newActiveIndex = prevActiveIndex + 1

      if (prevActiveIndex === 2) {
        newActiveIndex = 4
      }

      // validate user category list
      if (prevActiveIndex === 6) {
        if (categories?.length === 0) {
          toast({
            status: 'info',
            title: 'No categories available',
            description: 'Please add at least one category in your settings in order to add to your event',
            duration: 9000,
            isClosable: true,
          })
           newActiveIndex = 8
        }
      }

      if (prevActiveIndex === 8) {
        return
      }

      if (!prevCompletedStep || (prevCompletedStep < prevActiveIndex)) {
        const newCompletedStep = prevActiveIndex
        setCompletedStep(newCompletedStep)
      }

      if (newActiveIndex !== prevActiveIndex) {
        return setActiveIndex(newActiveIndex)
      }
      return
    }

    if (!isAttendees && isRecurring) {
      let newActiveIndex = prevActiveIndex + 1

      if (prevActiveIndex === 3) {
        newActiveIndex = 6
      }

      // validate user category list
      if (prevActiveIndex === 6) {
        if (categories?.length === 0) {
          toast({
            status: 'info',
            title: 'No categories available',
            description: 'Please add at least one category in your settings in order to add to your event',
            duration: 9000,
            isClosable: true,
          })
           newActiveIndex = 8
        }
      }

      if (!prevCompletedStep || (prevCompletedStep < prevActiveIndex)) {
        const newCompletedStep = prevActiveIndex
        setCompletedStep(newCompletedStep)
      }

      if (newActiveIndex !== prevActiveIndex) {
        return setActiveIndex(newActiveIndex)
      }
      return
    }

    if (!isAttendees && !isRecurring) {
      console.log('inside !isAttendees && !isRecurring')
      let newActiveIndex = prevActiveIndex + 1

      if (prevActiveIndex === 2) {
        newActiveIndex = 6
      }

      // validate user category list
      if (prevActiveIndex === 6) {
        if (categories?.length === 0) {
          toast({
            status: 'info',
            title: 'No categories available',
            description: 'Please add at least one category in your settings in order to add to your event',
            duration: 9000,
            isClosable: true,
          })
           newActiveIndex = 8
        }
      }

      if (!prevCompletedStep || (prevCompletedStep < prevActiveIndex)) {
        const newCompletedStep = prevActiveIndex
        setCompletedStep(newCompletedStep)
      }

      if (newActiveIndex !== prevActiveIndex) {
        return setActiveIndex(newActiveIndex)
      }
      return
    }

    let newActiveIndex = prevActiveIndex + 1

    // validate user category list
      if (prevActiveIndex === 6) {
        if (categories?.length === 0) {
          toast({
            status: 'info',
            title: 'No categories available',
            description: 'Please add at least one category in your settings in order to add to your event',
            duration: 9000,
            isClosable: true,
          })
           newActiveIndex = 8
        }
      }

    if (!prevCompletedStep || (prevCompletedStep < prevActiveIndex)) {
      const newCompletedStep = prevActiveIndex
      setCompletedStep(newCompletedStep)
    }

    if (newActiveIndex !== prevActiveIndex) {
      setActiveIndex(newActiveIndex)
    }
  }

  const renderNextButton = () => {
    if (activeIndex === 8) {
      return <Box pt={{ phone: 'm', tablet: 's' }}/>
    }

    return (
      <Box p={{ phone: 's', tablet: 'm' }}>
        <Button onClick={goToNextStep}>
          Next
        </Button>
      </Box>
    )
  }


  const renderCurrentStep = () => {
    /**
     0 - CreateEventBaseStep
     1 - CreateEventBaseStep2
     2 - CreateEventBaseStep3
     3 - CreateEventRecurStep
     4 - CreateEventVirtualMeet
     5 - CreateEventAttendees
     6 - CreateEventVisibilityAndAlarmsStep
     7 - CreateEventAddCategories
     */
     switch(activeIndex) {
      case 0:
        return (
          <Box style={{ width: '100%', height: '100%' }} flex={1} alignItems="center" justifyContent="center" minHeight="75vh" >
            <EditEventBaseStep
              title={title}
              notes={notes}
              location={location}
              startDate={startDate}
              endDate={endDate}
              setParentTitle={setTitle}
              setParentNotes={setNotes}
              setParentLocation={setLocation}
              setParentStartDate={setStartDate}
              setParentEndDate={setEndDate}
            />
            <Box px="m" width="90%" alignItems="center" mt="s">
                <Text variant="caption" textAlign="center" color="textSecondary">
                    Tip: Atomic can learn from your past events! After typing a title, see if Atomic suggests details from similar entries. You can also 'train' specific events to act as powerful templates.
                    <Text variant="link" onPress={() => router.push('https://docs.atomiclife.app/docs/features/smart-scheduling')}>
                        {' '}Learn more about smart scheduling
                    </Text>
                </Text>
            </Box>
            <Box flexDirection="row" justifyContent="space-between" alignItems="center" style={{ width: '95%'}}>
              <Box />
              {renderNextButton()}
            </Box>
          </Box>
        )
      case 1: 
      return (
          <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
            <EditEventBaseStep2
              allDay={allDay}
              isRecurring={isRecurring}
              isAttendees={isAttendees}
              isBreak={isBreak}
              setParentAllDay={setAllDay}
              setParentIsRecurring={setIsRecurring}
              setParentIsAttendees={setIsAttendees}
              setParentIsBreak={setIsBreak}        
            />
            <Box flexDirection="row" justifyContent="space-between" alignItems="center">
              {renderPrevButton()}
              {renderNextButton()}
            </Box>
          </Box>
      )
      case 2:
         return (
           <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
             <EditEventBaseStep3
               modifiable={modifiable}
               setParentModifiable={setModifiable}
               isMeeting={isMeeting}
               setParentIsMeeting={setIsMeeting}
               isExternalMeeting={isExternalMeeting}
               setParentIsExternalMeeting={setIsExternalMeeting}
               transparency={transparency}
               setParentTransparency={setTransparency}  
              />
             <Box flexDirection="row" justifyContent="space-between" alignItems="center">
              {renderPrevButton()}
              {renderNextButton()}
            </Box>
           </Box>
         )
      case 3:
        return (
          <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
            <EditEventRecurStep
              recurringEndDate={recurringEndDate}
              setParentRecurringEndDate={setRecurringEndDate}
              frequency={frequency}
              setParentFrequency={setFrequency}
              interval={interval}
              setParentInterval={setInterval}
              byWeekDay={byWeekDay}
              setParentByWeekDay={setByWeekDay}
            />
            <Box flexDirection="row" justifyContent="space-between" alignItems="center">
              {renderPrevButton()}
              {renderNextButton()}
            </Box>
          </Box>
        )
      case 4:
        return (
          <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
            <EditEventVirtualMeet
              isZoomAvailable={isZoomAvailable}
              isGoogleMeetAvailable={isGoogleMeetAvailable}
              zoomMeet={zoomMeet}
              googleMeet={googleMeet}
              setParentZoomMeet={setZoomMeet}
              setParentGoogleMeet={setGoogleMeet}
              zoomPrivateMeeting={zoomPrivateMeeting}
              setParentZoomPrivateMeeting={setZoomPrivateMeeting}
            />
            <Box flexDirection="row" justifyContent="space-between" alignItems="center">
              {renderPrevButton()}
              {renderNextButton()}
            </Box>
          </Box>
        )
      case 5:
         return (
          <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
            <EditEventAttendees
              attendees={attendees}
              setParentAttendees={setAttendees}
              userId={userId}
              client={client}
             />
             <Box flexDirection="row" justifyContent="space-between" alignItems="center">
              {renderPrevButton()}
              {renderNextButton()}
            </Box>
          </Box>
        )
      case 6:
         return (
          <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
            <EditEventVisibilityAndAlarmsStep
              alarms={alarms}
              setParentAlarms={setAlarms}
              visibility={visibility}
              setParentVisibility={setVisibility}
              userId={userId}
             />
             <Box flexDirection="row" justifyContent="space-between" alignItems="center">
               {renderPrevButton()}
               {renderNextButton()}
             </Box>
          </Box>
         )
      case 7:
        return (
          <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
            <EditEventUpdateCategories
              categories={categories}
              setParentSelectedCategories={setSelectedCategories}
              selectedCategories={selectedCategories}
            />
            <Box flexDirection="row" justifyContent="space-between" alignItems="center">
              {renderPrevButton()}
              {renderNextButton()}
            </Box>
          </Box>
        )        
      case 8: 
        return (
          <Box flex={1} alignItems="center" justifyContent="center">
            <Box flex={1} style={{ width: '100%' }} p={{ phone: 's', tablet: 'm' }} justifyContent="center" alignItems="center" minHeight="65vh" maxHeight="65vh">
              <Box p={{ phone: 'm', tablet: 'l'}}>
                <Text variant="subheaderNormal">
                  Update Event
                </Text>
              </Box>
              <Box pt={{ phone: 'm', tablet: 'l' }}>
                <Button onClick={updateEventForUser}>
                  Update
                </Button>
              </Box>
            </Box>
            <Box flexDirection="row" justifyContent="space-between" alignItems="center" style={{ width: '75%' }}>
              {renderPrevButton()}
              <Box />
            </Box>
          </Box>
        )
       default:
         return (
           <Box justifyContent="center" alignItems="center">
             <RegularCard>
               <Text variant="header">
                 Oops... something went wrong
               </Text>
             </RegularCard>
           </Box>
         )
     }
  }

  return (
    <Box flex={1} justifyContent="center" alignItems="center" width="100%" height="100%" minHeight="80vh">
      <Box flex={1} justifyContent="center" alignItems="center" width="100%" height="100%" minHeight="80vh">
        <Wizard
          items={[
              {
                  index: 0,
                  label: 'Update Base',
              },
              {
                  index: 1,
                  label: 'Continue Base',
              },
              {
                  index: 2,
                  label: 'Continue Base',
              },
                {
                  index: 3,
                  label: 'Update Recurrence',
              },
                {
                  index: 4,
                  label: 'Update Virtual Meet',
              },
                {
                  index: 5,
                  label: 'Update Event Attendees',
              },
              {
                  index: 6,
                  label: 'Update Visibility And Alarms',
              },
              {
                  index: 7,
                  label: 'Update Categories for Event',
              },
              {
                  index: 8,
                  label: 'Update Event',
              },
              
          ]}

          completed={completedStep}
          activeIndex={activeIndex}
        />
        {renderCurrentStep()}
      </Box>
      <Box>
        <button className="btn btn-link no-underline hover:no-underline" onClick={closeEditEvent}>
            Close
        </button>
      </Box>
    </Box>
  )
}

export default UserEditEvent



