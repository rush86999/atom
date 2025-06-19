import React, { useState, useEffect } from 'react'

import Wizard from '@components/Wizard'

import { useToast } from '@chakra-ui/react'
import { ApolloClient, NormalizedCacheObject } from '@apollo/client'
import { dayjs } from '@lib/date-utils'
import { v4 as uuid } from 'uuid'
import Box from '@components/common/Box'
import Button from '@components/Button'

import {
    ConferenceAppType,
    MeetingAssistType
} from '@lib/dataTypes/MeetingAssistType'

import {
  MeetingAssistAttendeeType
} from '@lib/dataTypes/MeetingAssistAttendeeType'

import {
  MeetingAssistInviteType
} from '@lib/dataTypes/MeetingAssistInviteType'


import {
  zoomAvailable
} from '@lib/zoom/zoomMeetingHelper'

import {
  googleMeetAvailable,
} from '@lib/calendarLib/googleCalendarHelper'

import getGlobalPrimaryCalendar from '@lib/apollo/gql/getGlobalPrimaryCalendar'
import { CalendarType } from '@lib/dataTypes/CalendarType'
import { convertInviteeTypeToInviteEmailRecipients, getUserGivenId, insertMeetingAssistAttendee, sendBulkMeetingInviteEmail, sendMeetingInfoToHostEmail, updateUserNameGivenId, upsertMeetingAssistInviteMany, upsertMeetingAssistOne } from '@lib/Assist/UserMeetingAssistHelper'
import { ContactType } from '@lib/dataTypes/ContactType'
import { UserType } from '@lib/dataTypes/UserType'
import { RecurrenceFrequencyType } from '@lib/Calendar/types'
import CreateMeetingAssistBaseStep from '@pages/Assist/CreateMeetingAssistWizard/CreateMeetingAssistBaseStep'
import CreateMeetingAssistVirtualMeet from '@pages/Assist/CreateMeetingAssistWizard/CreateMeetingAssistVirtualMeet'
import CreateMeetingAssistBaseStep3 from '@pages/Assist/CreateMeetingAssistWizard/CreateMeetingAssistBaseStep3'
import CreateMeetingAssistAlarms from '@pages/Assist/CreateMeetingAssistWizard/CreateMeetingAssistAlarms'
import CreateMeetingAssistBaseStep5 from '@pages/Assist/CreateMeetingAssistWizard/CreateMeetingAssistBaseStep5'
import CreateMeetingAssistBaseStep6 from '@pages/Assist/CreateMeetingAssistWizard/CreateMeetingAssistBaseStep6'
import CreateMeetingAssistBaseStep7 from '@pages/Assist/CreateMeetingAssistWizard/CreateMeetingAssistBaseStep7'
import CreateMeetingAssistRecurStepAlt from '@pages/Assist/CreateMeetingAssistWizard/CreateMeetingAssistRecurStepAlt'
import CreateMeetingAssistInvitees from '@pages/Assist/CreateMeetingAssistWizard/CreateMeetingAssistInvitees'
import Text from '@components/common/Text'
import RegularCard from '@components/RegularCard'
import { UserContactInfoType } from '@lib/dataTypes/UserContactInfoType'
import { listUserContactInfosGivenUserId } from '@lib/Contact/ContactHelper'
import { useRouter } from 'next/router'

import { useAppContext } from '@lib/user-context'
import { NextApiRequest, NextApiResponse } from 'next';
import supertokensNode from 'supertokens-node'
import { backendConfig } from '../../config/backendConfig'
import Session from 'supertokens-node/recipe/session'
import { gql } from '@apollo/client' // Added for defining GraphQL mutation

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


const PROCESS_AUDIO_FOR_NOTE = gql`
  mutation ProcessAudioForNote($audioFilePath: String!, $noteId: String, $title: String, $content: String, $source: String, $linkedTaskId: String, $linkedEventId: String) {
    processAudioForNote(input: {
      audio_file_path: $audioFilePath,
      note_id: $noteId,
      title: $title,
      content: $content,
      source: $source,
      linked_task_id: $linkedTaskId,
      linked_event_id: $linkedEventId
    }) {
      note_id # This is what the action currently returns
      status
      error
      # Anticipating that the action might be updated to return full note details
      # If not, a separate query would be needed using the returned note_id
      # For this subtask, we assume the backend might provide this structure:
      # note_details {
      #   notes # or original_content
      #   summary
      #   transcription
      #   key_points
      # }
      # For now, let's assume we get these directly for simplicity in this step,
      # even if it's not what the current Hasura action provides.
      # This part of the response structure is speculative based on frontend needs.
      # The actual implementation of processAudioFile will need to be robust
      # to what the backend *actually* returns.
      # Let's assume for now the backend is enhanced like so:
      transcription_text: String
      summary_text: String
      key_points_text: String
      # The above are hypothetical direct fields. If they are nested, adjust parsing.
    }
  }
`;


function UserCreateMeetingAssist() {
    const [notes, setNotes] = useState<string>('')
    const [summary, setSummary] = useState<string>('')
    const [transcription, setTranscription] = useState<string>('')
    const [keyPoints, setKeyPoints] = useState<string>('')
    const [isRecording, setIsRecording] = useState<boolean>(false)
    const [audioFilePath, setAudioFilePath] = useState<string | null>(null)
    const [isLoadingAudio, setIsLoadingAudio] = useState<boolean>(false)
    const [windowStartDate, setWindowStartDate] = useState<Date>(new Date())
    const [windowEndDate, setWindowEndDate] = useState<Date>(new Date())
    const [location, setLocation] = useState<string>('')
    const [isZoomAvailable, setIsZoomAvailable] = useState<boolean>(false)
    const [isGoogleMeetAvailable, setIsGoogleMeetAvailable] = useState<boolean>(false)
    const [zoomMeet, setZoomMeet] = useState<boolean>(false)
    const [googleMeet, setGoogleMeet] = useState<boolean>(false)
    // const [priority, setPriority] = useState<number>(1)
    const [sendUpdates, setSendUpdates] = useState<'all' | 'externalOnly'>('all')
    const [guestsCanInviteOthers, setGuestsCanInviteOthers] = useState<boolean>(true)
    const [transparency, setTransparency] = useState<'opaque' | 'transparent'>('opaque')
    const [visibility, setVisibility] = useState<'default' | 'public' | 'private'>('default')
    const [useDefaultAlarms, setUseDefaultAlarms] = useState<boolean>(true)
    const [alarms, setAlarms] = useState<number[]>([])
    const [cancelIfAnyRefuse, setCancelIfAnyRefuse] = useState<boolean>(false)
    const [enableAttendeePreferences, setEnableAttendeePreferences] = useState<boolean>(true)
    const [attendeeCanModify, setAttendeeCanModify] = useState<boolean>(false)
    const [expireDate, setExpireDate] = useState<Date>(dayjs().add(6, 'd').toDate())
    const [duration, setDuration] = useState<number>(30)
    const [enableConference, setEnableConference] = useState<boolean>(false)
    const [conferenceApp, setConferenceApp] = useState<ConferenceAppType | null | undefined>('google')
    // const [calendarId, setCalendarId] = useState<string>()
    const [isBufferTime, setIsBufferTime] = useState<boolean>(false)
    const [beforeEventMinutes, setBeforeEventMinutes] = useState<number>(0)
    const [afterEventMinutes, setAfterEventMinutes] = useState<number>(0)
    const [anyoneCanAddSelf, setAnyoneCanAddSelf] = useState<boolean>(true)
    const [guestsCanSeeOtherGuests, setGuestsCanSeeOtherGuests] = useState<boolean>(true)
    const [minThresholdCount, setMinThresholdCount] = useState<number>(2)
    const [guaranteeAvailability, setGuaranteeAvailability] = useState<boolean>(false)
    const [isRecurring, setIsRecurring] = useState<boolean>(false)
    const [frequency, setFrequency] = useState<RecurrenceFrequencyType>('daily')
    const [interval, setInterval] = useState<number>(1) // every 1, 2... weeks 
    const [until, setUntil] = useState<Date>(new Date())
    // const [selectedCalendarId, setSelectedCalendarId] = useState<string>()
    const [calendar, setCalendar] = useState<CalendarType>()
    const [searchName, setSearchName] = useState<string>('')
    const [contactResults, setContactResults] = useState<ContactType[]>()
    const [invitees, setInvitees] = useState<MeetingAssistInviteType[]>([])
    const [activeIndex, setActiveIndex] = useState<number>(0)
    const [completedStep, setCompletedStep] = useState<number | undefined>()
    const [hostName, setHostName] = useState<string>('')
    const [user, setUser] = useState<UserType>()
    const [meetingId, setMeetingId] = useState<string>(uuid())
    const [userInfoItems, setUserInfoItems] = useState<UserContactInfoType[]>()
    const [lockAfter, setLockAfter] = useState<boolean>(false)
    
    // const userId = props?.sub
    // const client = props?.client
    const { sub, client } = useAppContext()
    const userId = sub
    const router = useRouter()
    const toast = useToast()

    // --- Audio Processing Functions ---

    const processAudioFile = async (filePath: string) => {
        if (!filePath) {
            toast({ title: "No audio file selected.", status: "warning", duration: 3000, isClosable: true });
            return;
        }
        setIsLoadingAudio(true);
        try {
            console.log(`Processing audio file: ${filePath}`);
            // For now, we pass the existing notes and summary as content and title respectively
            // if we want the audio processing to potentially use them or add to them.
            // Or, they could be separate if the backend handles merging.
            // Let's assume the action might create a new note or update based on filePath alone for now.
            // The action `processAudioForNote` can take existing note_id, title, content.
            // If we have a note_id from a previously created meeting assist, we could pass it.
            // For a new meeting assist, these would likely be null or defaults.

            const { data } = await client.mutate({
                mutation: PROCESS_AUDIO_FOR_NOTE,
                variables: {
                    audioFilePath: filePath,
                    // Potentially pass other details if relevant for the audio processing context
                    // For example, if audio processing should be linked to an *existing* note:
                    // noteId: existingNoteIdIfAny,
                    // title: summary, // or a dedicated title for the audio note
                    // content: notes, // or leave blank if transcription is the main content
                },
            });

            const result = data?.processAudioForNote;

            if (result?.status === 'success') {
                // ASSUMPTION: Backend returns transcription, summary, key_points
                // Adjust based on actual backend response structure.
                // The GQL mutation above speculatively added these fields to the response.
                const returnedTranscription = result.transcription_text || "Transcription not available.";
                const returnedSummary = result.summary_text || summary; // Keep existing summary if not returned
                const returnedKeyPoints = result.key_points_text || "Key points not available.";
                // const returnedNotes = result.note_details?.notes || notes; // If backend returns original notes

                setTranscription(returnedTranscription);
                setSummary(returnedSummary); // Update summary if backend provides a new one
                setKeyPoints(returnedKeyPoints);
                // setNotes(returnedNotes); // Update notes if backend provides new/merged notes

                // If a note_id is returned, it might be useful for subsequent operations
                // e.g., if the audio processing created a new note in Notion.
                console.log("Audio processed, note_id:", result.note_id);

                toast({ title: "Audio processed successfully!", status: "success", duration: 3000, isClosable: true });
            } else {
                console.error("Error processing audio:", result?.error);
                toast({ title: "Error processing audio", description: result?.error || "Unknown error", status: "error", duration: 5000, isClosable: true });
                // Clear fields on error? Or leave them as they are?
                // setTranscription(''); setKeyPoints(''); // Optionally clear
            }
        } catch (error: any) {
            console.error("GraphQL mutation error:", error);
            toast({ title: "Audio processing failed", description: error.message || "Please try again.", status: "error", duration: 5000, isClosable: true });
        } finally {
            setIsLoadingAudio(false);
        }
    };

    const handleAudioRecordToggle = () => {
        if (isRecording) {
            // Stop recording
            console.log("Stop recording (simulated)");
            setIsRecording(false);
            const dummyFilePath = "simulated_audio_from_record.wav";
            setAudioFilePath(dummyFilePath); // Store dummy path
            processAudioFile(dummyFilePath);
        } else {
            // Start recording
            console.log("Start recording (simulated)");
            setIsRecording(true);
            // Actual recording logic would go here (e.g., MediaRecorder API)
            // For now, we just set the state. The file will be "available" on stop.
        }
    };

    const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (file) {
            console.log(`File uploaded: ${file.name} (simulated processing)`);
            // In a real app, you'd upload this file to a server/S3 and get back a URL/path.
            // For this subtask, we'll simulate it with a dummy path.
            const dummyFilePath = `uploaded_${file.name}`;
            setAudioFilePath(dummyFilePath); // Store dummy path or file name
            processAudioFile(dummyFilePath);

            // Reset file input value so the same file can be selected again if needed
            event.target.value = '';
        }
    };

    // --- End Audio Processing Functions ---

    // list old info items
    useEffect(() => {
        (async () => {
            try {
                if (!userId) {
                    return
                }
                const oldDbInfoItems = await listUserContactInfosGivenUserId(client, userId)
                if (oldDbInfoItems && oldDbInfoItems?.length > 0) {
                    setUserInfoItems(oldDbInfoItems)
                }
            } catch (e) {
                console.log(e, ' unable to list user contact info items')
            }
        })()
    }, [client, userId])

    // check if zoom available
    useEffect(() => {
        (async () => {
        if (!userId || !client) {
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
            return
        }
        const isAvailable = await googleMeetAvailable(client, userId)
        if (isAvailable) {
            setIsGoogleMeetAvailable(isAvailable)
        }
        })()
    }, [client, userId])

    // get global primary calendar
    useEffect(() => {
        (async () => {  
        if (!userId || !client) {
            return
        }
        const result = (await client.query<{ Calendar: CalendarType[] }>({
            query: getGlobalPrimaryCalendar, 
            variables: {
                userId,
            },
            fetchPolicy: 'no-cache',
        })).data?.Calendar?.[0]
        
        console.log(result, ' primary calendar')
        if (!result?.id) {
            console.log(' no primary calendar available')
            toast({
                status: 'error',
                title: 'Forgot to set Primary Calendar',
                description: 'Please go to Settings to Set Primary Calendar. This will not work otherwise.',
                duration: 9000,
                isClosable: true,
            })
            return
        }
        // setSelectedCalendarId(result?.id)
        setCalendar(result)
        })()
    }, [client, toast, userId])

    // get user and update if necessary
    useEffect(() => {
        (async () => {
            try {
                if (!userId) {
                    return
                }
                const oldUser = await getUserGivenId(client, userId)
                setUser(oldUser)
                if (oldUser?.name) {
                    setHostName(oldUser?.name)
                }
            } catch (e) {
                console.log(e, ' unable to get user')
            }
        })()
    }, [client, userId])

    const createMeetingAssistInvitees = async () => {
        try {
            console.log(invitees, ' invitees')
            await upsertMeetingAssistInviteMany(client, invitees)
        } catch (e) {
            console.log(e, ' unable to create meeting assist invitees')
        }
    }

    const createHostAttendee = async (
        meetingId: string,
    ) => {
        try {
            console.log(userInfoItems, ' userInfoItems inside createHostAttendee')
            // validate
            if (!userInfoItems || !user) {
                console.log('user object not present inside UserCreateMeetingAssist')
                toast({
                    status: 'error',
                    title: 'Oops...',
                    description: 'Something went wrong, please let us know so we can fix it',
                    duration: 9000,
                    isClosable: true,
                })
                return
            }

            const attendeeId = uuid()

            const primaryInfoItem = userInfoItems?.find(u => (u.primary && (u.type === 'email')))

            const hostAttendee: MeetingAssistAttendeeType = {
                id: attendeeId,
                name: hostName || primaryInfoItem?.name || user?.name,
                hostId: userId,
                userId,
                emails: [{ primary: true, value: primaryInfoItem?.id || user?.email || '', type: 'email', displayName: primaryInfoItem?.name || user?.name || '' }],
                meetingId,
                createdDate: dayjs().format(),
                timezone: dayjs.tz.guess(),
                updatedAt: dayjs().format(),
                externalAttendee: false,
                primaryEmail: primaryInfoItem?.id || user?.email,
            }

            await insertMeetingAssistAttendee(client, hostAttendee)

            return attendeeId
            
        } catch (e) {
            console.log(e, ' unable to create host attendee')
        }
    }

    const createSingleMeetingAssist = async () => {
        try {
            // Combine notes, transcription, and key points for storage
            let combinedNotes = notes;
            if (transcription) {
                combinedNotes += `\n\n--- Transcription ---\n${transcription}`;
            }
            if (keyPoints) {
                combinedNotes += `\n\n--- Key Points ---\n${keyPoints}`;
            }

            const meetingAssist: MeetingAssistType = {
                id: meetingId,
                userId,
                summary,
                notes: combinedNotes, // Use combined notes
                windowStartDate: dayjs(windowStartDate).format(),
                windowEndDate: dayjs(windowEndDate).format(),
                timezone: dayjs.tz.guess(),
                location: { title: (location || '') },
                priority: 1,
                enableConference,
                conferenceApp,
                sendUpdates,
                guestsCanInviteOthers,
                transparency,
                visibility,
                createdDate: dayjs().format(),
                updatedAt: dayjs().format(),
                useDefaultAlarms,
                reminders: alarms,
                cancelIfAnyRefuse,
                enableAttendeePreferences,
                attendeeCanModify,
                expireDate: dayjs(expireDate).format(),
                duration,
                calendarId: calendar?.id || '',
                bufferTime: isBufferTime ? {
                    beforeEvent: beforeEventMinutes,
                    afterEvent: afterEventMinutes,
                } : undefined,
                anyoneCanAddSelf,
                guestsCanSeeOtherGuests,
                minThresholdCount,
                guaranteeAvailability,
                attendeeRespondedCount: 1,
                attendeeCount: 1,
                cancelled: false,
                frequency,
                interval,
                until: dayjs(until).format(),
                originalMeetingId: isRecurring ? meetingId : undefined,
                lockAfter,
            }

            await upsertMeetingAssistOne(
                client,
                meetingAssist,
            )


            await createHostAttendee(meetingId)

            await createMeetingAssistInvitees()

            const inviteeEmails = convertInviteeTypeToInviteEmailRecipients(invitees, meetingId)

            await sendMeetingInfoToHostEmail(inviteeEmails, user?.email || '', hostName || user?.name || '', summary, notes, dayjs(windowStartDate).format(), dayjs(windowEndDate).format(), dayjs.tz.guess())

            const filteredInviteeEmails = inviteeEmails?.filter(i => !!(i?.email))

            await sendBulkMeetingInviteEmail(filteredInviteeEmails, user?.email || '', hostName || user?.name || '')

            if (hostName && (user?.name !== hostName)) {
                await updateUserNameGivenId(
                    client,
                    userId,
                    hostName
                )
            }

        } catch (e) {
            console.log(e, ' unable to create single meeting assist')
        }
    }

    const createMeetingAssist = async () => {
        try {
            // validate
            if (!(invitees?.length > 0)) {
                toast({
                    status: 'error',
                    title: 'No invitees set',
                    description: 'Please add at least 1 invitee',
                    duration: 9000,
                    isClosable: true,
                })
            }

            await createSingleMeetingAssist()

            toast({
                status: 'success',
                title: 'Meeting Assist Created',
                description: 'Meeting Assist created successfully',
                duration: 9000,
                isClosable: true,
            })

            router.push('/Calendar/UserViewCalendar')
        
        } catch (e) {
            console.log(e, ' unable to create meeting assist')
        }
    }

    const goToPrevStep = () => {
        const prevActiveIndex = activeIndex
        const newActiveIndex = prevActiveIndex === 0 ? 0 : prevActiveIndex - 1

        if ((activeIndex === 8) && !isRecurring) {
            return setActiveIndex(6)
        }

        setActiveIndex(newActiveIndex)
    }
    
    const renderPrevButton = () => {
        if (activeIndex === 0) {
            return <Box pt={{ phone: 'm', tablet: 's' }}/>
        }

        return (
            <Box ml={{ phone: 's', tablet: 'm' }} mb={{ phone: 's', tablet: 'm' }} pt={{ phone: 'm', tablet: 's' }}>
                <Button onClick={goToPrevStep}>
                    Back
                </Button>
            </Box>
        )
    }

    const goToNextStep = () => {
        const prevActiveIndex = activeIndex
        const prevCompletedStep = completedStep
        /**
         * 0 - CreateMeetingAssistBaseStep
         * 1 - CreateMeetingAssistVirtualMeet
         * 2 - CreateMeetingAssistBaseStep3
         * 3 - CreateMeetingAssistAlarms
         * 4 - CreateMeetingAssistBaseStep5
         * 5 - CreateMeetingAssistBaseStep6
         * 6 - CreateMeetingAssistBaseStep7
         * 7 - CreateMeetingAssistRecurStepAlt
         * 8 - createMeetingAssistInvitees
         */
        if (!isRecurring) {
          let newActiveIndex = prevActiveIndex + 1
    
          if (prevActiveIndex === 6) {
            newActiveIndex = 8
          }
    
          // validate invitees list
          if (prevActiveIndex === 8) {
            if (invitees?.length === 0) {
              toast({
                status: 'info',
                title: 'No invitees added',
                description: 'Please add at least one invitee in order to add your meeting',
                duration: 9000,
                isClosable: true,
              })
               newActiveIndex = 8
            }
          }
    
          if (prevActiveIndex === 9) {
            return
          }
    
          if (!prevCompletedStep || (prevCompletedStep < prevActiveIndex)) {
            const newCompletedStep = prevActiveIndex
            setCompletedStep(newCompletedStep)
          }
    
          if (newActiveIndex !== prevActiveIndex) {
            return setActiveIndex(newActiveIndex)
          }
    
        }
    
        
    
        if (prevActiveIndex === 9) {
          return
        }
    
        let newActiveIndex = prevActiveIndex + 1
    
        // validate invitees list
        if (prevActiveIndex === 8) {
            if (invitees?.length === 0) {
              toast({
                status: 'info',
                title: 'No invitees added',
                description: 'Please add at least one invitee in order to add your meeting',
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
        if (activeIndex === 9) {
          return <Box pt={{ phone: 'm', tablet: 's' }}/>
        }

        if ((activeIndex === 8) && (invitees?.length === 0)) {
            return <Box pt={{ phone: 'm', tablet: 's' }}/>
        }
    
        return (
          <Box mr={{ phone: 's', tablet: 'm' }} mb={{ phone: 's', tablet: 'm' }} pt={{ phone: 's', tablet: 'm'}}>
            <Button onClick={goToNextStep}>
              Next
            </Button>
          </Box>
        )
    }

    const renderCurrentStep = () => {
        /**
         * 0 - CreateMeetingAssistBaseStep
         * 1 - CreateMeetingAssistVirtualMeet
         * 2 - CreateMeetingAssistBaseStep3
         * 3 - CreateMeetingAssistAlarms
         * 4 - CreateMeetingAssistBaseStep5
         * 5 - CreateMeetingAssistBaseStep6
         * 6 - CreateMeetingAssistBaseStep7
         * 7 - CreateMeetingAssistRecurStepAlt
         * 8 - CreateMeetingAssistInvitees
         */

        switch(activeIndex) {
            case 0: 
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <CreateMeetingAssistBaseStep
                            notes={notes}
                            summary={summary}
                            windowStartDate={windowStartDate}
                            windowEndDate={windowEndDate}
                            location={location}
                            setParentNotes={setNotes}
                            setParentSummary={setSummary}
                            setParentWindowStartDate={setWindowStartDate}
                            setParentWindowEndDate={setWindowEndDate}
                            setParentLocation={setLocation}
                        />

                        {/* Audio Processing UI Elements */}
                        <Box mt="m" p="m" borderWidth="1px" borderRadius="md" borderColor="gray.200" width="100%">
                            <Text variant="label" mb="s">Audio Processing (Optional)</Text>
                            <Box display="flex" flexDirection={{ phone: "column", tablet: "row" }} alignItems="center" gap="m" mb="m">
                                <Button onClick={handleAudioRecordToggle} variant={isRecording ? "danger" : "primary"}>
                                    {isRecording ? 'Stop Recording' : 'Record Audio (Simulated)'}
                                </Button>
                                <Box>
                                    <Text as="label" htmlFor="audio-upload" variant="label" mr="s">Or Upload Audio:</Text>
                                    <input
                                        id="audio-upload"
                                        type="file"
                                        accept="audio/*"
                                        onChange={handleFileUpload}
                                        style={{ display: 'block', marginTop: '4px' }} // Basic styling
                                    />
                                </Box>
                            </Box>

                            {isLoadingAudio && (
                                <Box display="flex" alignItems="center" justifyContent="center" my="m">
                                    {/* Assuming a CircularProgress or similar component exists or can be added */}
                                    <Text>Loading audio data...</Text>
                                    {/* Replace with <CircularProgress isIndeterminate /> if using Chakra/MUI */}
                                </Box>
                            )}

                            {transcription && (
                                <Box mb="s">
                                    <Text variant="label">Transcription:</Text>
                                    <Box p="s" borderWidth="1px" borderRadius="md" maxHeight="150px" overflowY="auto" bg="gray.50">
                                        <Text whiteSpace="pre-wrap">{transcription}</Text>
                                    </Box>
                                </Box>
                            )}
                            {/* Summary is already handled by CreateMeetingAssistBaseStep, but if audio processing specifically updates it, display it here too or ensure CreateMeetingAssistBaseStep reflects it.*/}
                            {/* For now, assuming summary from audio is handled by setSummary and reflected in the main summary field. */}
                            {/* If summary needs a separate display area:
                            {summary && ( // This summary is the main state one
                                <Box mb="s">
                                    <Text variant="label">Summary (from audio if processed):</Text>
                                    <Box p="s" borderWidth="1px" borderRadius="md" maxHeight="100px" overflowY="auto"  bg="gray.50">
                                        <Text whiteSpace="pre-wrap">{summary}</Text>
                                    </Box>
                                </Box>
                            )}
                            */}
                             {keyPoints && (
                                <Box>
                                    <Text variant="label">Key Points:</Text>
                                    <Box p="s" borderWidth="1px" borderRadius="md" maxHeight="150px" overflowY="auto" bg="gray.50">
                                        <Text whiteSpace="pre-wrap">{keyPoints}</Text>
                                    </Box>
                                </Box>
                            )}
                        </Box>
                        {/* End Audio Processing UI Elements */}

                        <Box style={{ width: '100%' }} flexDirection="row" justifyContent="space-between" alignItems="center">
                            <Box />
                            {renderNextButton()}
                        </Box>
                    </Box>
                )
            
            case 1: 
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <CreateMeetingAssistVirtualMeet
                            isZoomAvailable={isZoomAvailable}
                            isGoogleMeetAvailable={isGoogleMeetAvailable}
                            zoomMeet={zoomMeet}
                            googleMeet={googleMeet}
                            enableConference={enableConference}
                            setParentZoomMeet={setZoomMeet}
                            setParentGoogleMeet={setGoogleMeet}
                            setParentEnableConference={setEnableConference}
                            setParentConferenceApp={setConferenceApp}
                        />
                        <Box flexDirection="row" justifyContent="space-between" alignItems="center"  style={{ width: '100%'}}>
                            {renderPrevButton()}
                            {renderNextButton()}
                        </Box>
                    </Box>
                )
            case 2:
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <CreateMeetingAssistBaseStep3
                            sendUpdates={sendUpdates}
                            guestsCanInviteOthers={guestsCanInviteOthers}
                            transparency={transparency}
                            visibility={visibility}
                            hostName={hostName}
                            setParentSendUpdates={setSendUpdates}
                            setParentGuestsCanInviteOthers={setGuestsCanInviteOthers}
                            setParentTransparency={setTransparency}
                            setParentVisibility={setVisibility}
                            setParentHostName={setHostName}
                        />
                        <Box flexDirection="row" justifyContent="space-between" alignItems="center"  style={{ width: '100%'}}>
                            {renderPrevButton()}
                            {renderNextButton()}
                        </Box>
                    </Box>
                )
            case 3:
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <CreateMeetingAssistAlarms
                            useDefaultAlarms={useDefaultAlarms}
                            alarms={alarms}
                            setParentAlarms={setAlarms}
                            setParentUseDefaultAlarms={setUseDefaultAlarms}
                        />
                        <Box flexDirection="row" justifyContent="space-between" alignItems="center"  style={{ width: '100%'}}>
                            {renderPrevButton()}
                            {renderNextButton()}
                        </Box>
                    </Box>
                )
            case 4:
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <CreateMeetingAssistBaseStep5
                            cancelIfAnyRefuse={cancelIfAnyRefuse}
                            enableAttendeePreferences={enableAttendeePreferences}
                            attendeeCanModify={attendeeCanModify}
                            expireDate={expireDate}
                            duration={duration}
                            setParentCancelIfAnyRefuse={setCancelIfAnyRefuse}
                            setParentEnableAttendeePreferences={setEnableAttendeePreferences}
                            setParentAttendeeCanModify={setAttendeeCanModify}
                            setParentExpireDate={setExpireDate}
                            setParentDuration={setDuration}
                        />
                        <Box flexDirection="row" justifyContent="space-between" alignItems="center"  style={{ width: '100%'}}>
                            {renderPrevButton()}
                            {renderNextButton()}
                        </Box>
                    </Box>
                )
            case 5:
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <CreateMeetingAssistBaseStep6
                            isBufferTime={isBufferTime}
                            beforeEventMinutes={beforeEventMinutes}
                            afterEventMinutes={afterEventMinutes}
                            setParentIsBufferTime={setIsBufferTime}
                            setParentBeforeEventMinutes={setBeforeEventMinutes}
                            setParentAfterEventMinutes={setAfterEventMinutes}
                        />
                        <Box flexDirection="row" justifyContent="space-between" alignItems="center"  style={{ width: '100%'}}>
                            {renderPrevButton()}
                            {renderNextButton()}
                        </Box>
                    </Box>
                )
            
            case 6:
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <CreateMeetingAssistBaseStep7
                            anyoneCanAddSelf={anyoneCanAddSelf}
                            guestsCanSeeOtherGuests={guestsCanSeeOtherGuests}
                            minThresholdCount={minThresholdCount}
                            guaranteeAvailability={guaranteeAvailability}
                            isRecurring={isRecurring}
                            lockAfter={lockAfter}
                            setParentAnyoneCanAddSelf={setAnyoneCanAddSelf}
                            setParentGuestsCanSeeOtherGuests={setGuestsCanSeeOtherGuests}
                            setParentMinThresholdCount={setMinThresholdCount}
                            setParentGuaranteeAvailability={setGuaranteeAvailability}
                            setParentIsRecurring={setIsRecurring}
                            setParentLockAfter={setLockAfter}
                        />
                        <Box flexDirection="row" justifyContent="space-between" alignItems="center"  style={{ width: '100%'}}>
                            {renderPrevButton()}
                            {renderNextButton()}
                        </Box>
                    </Box>
                )
            
            case 7:
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <CreateMeetingAssistRecurStepAlt
                            frequency={frequency}
                            interval={interval}
                            until={until}
                            setParentFrequency={setFrequency}
                            setParentInterval={setInterval}
                            setParentUntil={setUntil}
                        />
                        <Box flexDirection="row" justifyContent="space-between" alignItems="center"  style={{ width: '100%'}}>
                            {renderPrevButton()}
                            {renderNextButton()}
                        </Box>
                    </Box>
                )
            
            case 8:
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <CreateMeetingAssistInvitees
                            invitees={invitees}
                            userId={userId}
                            client={client}
                            hostName={hostName}
                            meetingId={meetingId} 
                            setParentInvitees={setInvitees}
                        />
                         <Box flexDirection="row" justifyContent="space-between" alignItems="center" style={{ width: '100%'}}>
                            {renderPrevButton()}
                            {renderNextButton()}
                        </Box>
                    </Box>
                )
            
            case 9:
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <Box flex={1} style={{ width: '100%' }} p={{ phone: 's', tablet: 'm' }} justifyContent="center" alignItems="center" minHeight="65vh" maxHeight="65vh">
                            <Box p={{ phone: 'm', tablet: 'l'}}>
                                <Text variant="subheaderNormal">
                                    Create Meeting Assist
                                </Text>
                            </Box>
                            <Box pt={{ phone: 'm', tablet: 'l' }}>
                                <Button onClick={createMeetingAssist}>
                                    Create
                                </Button>
                            </Box>
                        </Box>
                        <Box flexDirection="row" justifyContent="space-between" alignItems="center" style={{ width: '100%' }}>
                            {renderPrevButton()}
                            {renderNextButton()}
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
        <Box flex={1} justifyContent="center" alignItems="center" height="100%" style={{ width: '100%' }}>
            <Wizard
                items={[
                    {
                        index: 0,
                        label: 'Set Base',
                    },
                    {
                        index: 1,
                        label: 'Select Virtual Meet',
                    },
                    {
                        index: 2,
                        label: 'Continue Base',
                    },
                     {
                        index: 3,
                        label: 'Set Alarms',
                    },
                     {
                        index: 4,
                        label: 'Continue Base',
                    },
                     {
                        index: 5,
                        label: 'Continue Base',
                    },
                    {
                        index: 6,
                        label: 'Continue Base',
                    },
                    {
                        index: 7,
                        label: 'Create Recurrence',
                    },
                    {
                        index: 8,
                        label: 'Add Invitees',
                    },
                    {
                        index: 9,
                        label: 'Create Event',
                    },
                ]}

                completed={completedStep}
                activeIndex={activeIndex}
            />
            {renderCurrentStep()}
        </Box>
    )
}



export default UserCreateMeetingAssist











