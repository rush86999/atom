import React, {
    useState,
    useEffect,
    useCallback,
} from 'react'

import Wizard from '@components/Wizard'
import { useToast } from '@chakra-ui/react'
import Box from '@components/common/Box'
import Text from '@components/common/Text'
import Button from '@components/Button'
import RegularCard from '@components/RegularCard'

import { trainEventForPlanning } from '@lib/Calendar/UserTrainCalendarHelper';

import TrainEventBaseStep from '@pages/Calendar/TrainEventWizard/TrainEventBaseStep'
import TrainEventBaseStep2 from '@pages/Calendar/TrainEventWizard/TrainEventBaseStep2'
import TrainEventBaseStep3 from '@pages/Calendar/TrainEventWizard/TrainEventBaseStep3'
import TrainEventBaseStep4 from '@pages/Calendar/TrainEventWizard/TrainEventBaseStep4'
import { ApolloClient, NormalizedCacheObject } from '@apollo/client'
import { getEventWithId } from '@lib/calendarLib/calendarDbHelper'
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
    closeTrainEvent: () => void,
    client: ApolloClient<NormalizedCacheObject>,
    sub: string,
}


function UserTrainEvent(props: Props) {
    const [copyAvailability, setCopyAvailability] = useState<boolean>(false)
    const [copyTimeBlocking, setCopyTimeBlocking] = useState<boolean>(false)
    const [copyTimePreference, setCopyTimePreference] = useState<boolean>(false)
    const [copyReminders, setCopyReminders] = useState<boolean>(false)
    const [copyPriorityLevel, setCopyPriorityLevel] = useState<boolean>(false)
    const [copyModifiable, setCopyModifiable] = useState<boolean>(false)
    const [copyCategories, setCopyCategories] = useState<boolean>(false)
    const [copyIsBreak, setCopyIsBreak] = useState<boolean>(false)
    const [copyIsMeeting, setCopyIsMeeting] = useState<boolean>(false)
    const [copyIsExternalMeeting, setCopyIsExternalMeeting] = useState<boolean>(false)
    const [copyDuration, setCopyDuration] = useState<boolean>(false)
    const [activeIndex, setActiveIndex] = useState<number>(0)
    const [completedStep, setCompletedStep] = useState<number | undefined>()
    const [copyColor, setCopyColor] = useState<boolean>(false)
    
    const toast = useToast()
    const router = useRouter()
    

    const id = props?.id
    const userId = props?.sub
    const client = props?.client
    const closeTrainEvent = props?.closeTrainEvent

    console.log(id, ' id inside userTrainEvent')

    useEffect(() => {
        (async () => {
            try {
                if (!id || !client) {
                    return
                }
                const event = await getEventWithId(client, id)
                if (!event) {
                    console.log('event not found')
                    return
                }
                if (event?.id) {
                    
                    

                    setCopyAvailability(event.copyAvailability)
                    setCopyTimeBlocking(event.copyTimeBlocking)
                    setCopyTimePreference(event.copyTimePreference)
                    setCopyReminders(event.copyReminders)
                    setCopyPriorityLevel(event.copyPriorityLevel)
                    setCopyModifiable(event.copyModifiable)
                    setCopyCategories(event.copyCategories)
                    setCopyIsBreak(event.copyIsBreak)
                    setCopyIsMeeting(event.copyIsMeeting)
                    setCopyIsExternalMeeting(event.copyIsExternalMeeting)
                    setCopyDuration(event.copyDuration)
                    setCopyColor(event.copyColor || false)
                }
            } catch (e) {
                console.log(e, ' error getting event')
            }
        })()
    }, [client, id])

    const trainEvent = async () => {
        try {
            if (!client) {
                return
            }
            await trainEventForPlanning(
                client,
                id,
                copyAvailability,
                copyTimeBlocking,
                copyTimePreference,
                copyReminders,
                copyPriorityLevel,
                copyModifiable,
                copyCategories,
                copyIsBreak,
                copyIsMeeting,
                copyIsExternalMeeting,
                copyDuration,
                copyColor,
            )

            toast({
                title: 'Event trained',
                status: 'success',
                description: 'Event trained successfully',
                duration: 9000,
                isClosable: true,
            })

            closeTrainEvent()
            
        } catch (e) {
            console.log(e, ' error training event')
            toast({
                title: 'Event was trained',
                status: 'error',
                description: 'Event is not trained successfully',
                duration: 9000,
                isClosable: true,
            })
        }
    }

    const onActiveIndexChanged = (index: number) => setActiveIndex(index)
    
    const goToPrevStep = () => {
        const prevActiveIndex = activeIndex
        const newActiveIndex = prevActiveIndex === 0 ? 0 : prevActiveIndex - 1
        setActiveIndex(newActiveIndex)
    }
    
    const renderPrevButton = () => {
        if (activeIndex === 0) {
        return <Box pt={{ phone: 'm', tablet: 's' }} />
        }

        return (
            <Box p={{ phone: 's', tablet: 'm' }}>
                <Button onClick={goToPrevStep}>
                    Back
                </Button>
            </Box>
            )
    }
  
    const goToNextStep = () => {
        const prevActiveIndex = activeIndex
        const prevCompletedStep = completedStep

        if (prevActiveIndex === 4) {
            return
        }

        let newActiveIndex = prevActiveIndex + 1

        if (!prevCompletedStep || (prevCompletedStep < prevActiveIndex)) {
            const newCompletedStep = prevActiveIndex
            setCompletedStep(newCompletedStep)
        }

        if (newActiveIndex !== prevActiveIndex) {
            setActiveIndex(newActiveIndex)
        }
    }

    const renderNextButton = () => {
        if (activeIndex === 4) {
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
       
        switch (activeIndex) {
            case 0:
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <TrainEventBaseStep
                            copyAvailability={copyAvailability}
                            copyTimeBlocking={copyTimeBlocking}
                            copyTimePreference={copyTimePreference}
                            setParentCopyAvailability={setCopyAvailability}
                            setParentCopyTimeBlocking={setCopyTimeBlocking}
                            setParentCopyTimePreference={setCopyTimePreference}
                        />
                        <Box style={{ width: '100%' }} p={{ phone: 's', tablet: 'm' }} flexDirection="row" justifyContent="space-between" alignItems="center">
                            <Box />
                            {renderNextButton()}
                        </Box>
                        <Box>
                            <button className="btn btn-link no-underline hover:no-underline" onClick={closeTrainEvent}>
                                Close
                            </button>
                        </Box>
                    </Box>
                )
            case 1:
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <TrainEventBaseStep2    
                            copyModifiable={copyModifiable}
                            copyCategories={copyCategories}
                            copyIsBreak={copyIsBreak}
                            setParentCopyModifiable={setCopyModifiable}
                            setParentCopyCategories={setCopyCategories}
                            setParentCopyIsBreak={setCopyIsBreak}
                        />
                        <Box style={{ width: '100%' }} flexDirection="row" justifyContent="space-between" alignItems="center">
                            {renderPrevButton()}
                            {renderNextButton()}
                        </Box>
                        <Box>
                            <button className="btn btn-link no-underline hover:no-underline" onClick={closeTrainEvent}>
                                Close
                            </button>
                        </Box>
                    </Box>
                )
            case 2:
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                        <TrainEventBaseStep3
                            copyIsMeeting={copyIsMeeting}
                            copyIsExternalMeeting={copyIsExternalMeeting}
                            copyDuration={copyDuration}
                            setParentCopyIsMeeting={setCopyIsMeeting}
                            setParentCopyIsExternalMeeting={setCopyIsExternalMeeting}
                            setParentCopyDuration={setCopyDuration}
                            copyColor={copyColor}
                            setParentCopyColor={setCopyColor}
                        />
                        <Box style={{ width: '100%' }} p={{ phone: 's', tablet: 'm' }} flexDirection="row" justifyContent="space-between" alignItems="center">
                            {renderPrevButton()}
                            {renderNextButton()}
                        </Box>
                        <Box>
                            <button className="btn btn-link no-underline hover:no-underline" onClick={closeTrainEvent}>
                                Close
                            </button>
                        </Box>
                    </Box>
                )
            case 3:
            return (
                <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center">
                    <TrainEventBaseStep4
                        setParentCopyReminders={setCopyReminders}
                        setParentCopyPriorityLevel={setCopyPriorityLevel}  
                        copyReminders={copyReminders}
                        copyPriorityLevel={copyPriorityLevel}
                    />
                    <Box style={{ width: '100%' }} p={{ phone: 's', tablet: 'm' }} flexDirection="row" justifyContent="space-between" alignItems="center">
                        {renderPrevButton()}
                        {renderNextButton()}
                    </Box>
                    <Box>
                        <button className="btn btn-link no-underline hover:no-underline" onClick={closeTrainEvent}>
                            Close
                        </button>
                    </Box>
                </Box>
            )
            case 4:
                return (
                    <Box style={{ width: '100%' }} flex={1} alignItems="center" justifyContent="center" height="100%">
                        <Box flex={1} style={{ width: '100%' }} justifyContent="center" alignItems="center" height="100%">
                            <Box style={{ width: '100%' }} justifyContent="center" alignItems="center">
                                <Text variant="subheaderNormal">
                                    Train Event
                                </Text>
                            </Box>
                            <Box justifyContent="center" alignItems="center">
                                <Box pt={{ phone: 'm', tablet: 's' }}>
                                    <Button onClick={trainEvent}>
                                        Train
                                    </Button>
                                </Box>
                            </Box>
                        </Box>
                        <Box style={{ width: '100%' }} p={{ phone: 's', tablet: 'm' }} flexDirection="row" justifyContent="flex-start" width="100%">
                            {renderPrevButton()}
                        </Box>
                        <Box>
                            <button className="btn btn-link no-underline hover:no-underline" onClick={closeTrainEvent}>
                                Close
                            </button>
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
                        <button className="btn btn-link no-underline hover:no-underline" onClick={closeTrainEvent}>
                            Close
                        </button>
                    </Box>
                )
        }       
    }

    return (
        <Box style={{ width: '100%' }} height="100%" flex={1} alignItems="center" justifyContent="center">
            <Box p="m" m="m" borderRadius="md" backgroundColor="infoBlockBackground" width={{ phone: '90%', tablet: '80%'}} alignItems="center">
                <Text variant="body" textAlign="center" color="infoBlockText">
                    You are training this event to become a reusable template. When you create new events with similar titles or details in the future, Atomic can automatically apply settings (like duration, color, priority, notes, etc.) from this trained event. You can manage which attributes get copied in Settings &gt; Event Defaults.
                    <Text variant="link" onPress={() => router.push('https://docs.atomiclife.app/docs/features/event-training')}>
                        {' '}Learn more about event training
                    </Text>
                </Text>
            </Box>
             <Wizard
                items={[
                    {
                        index: 0,
                        label: 'Step 1',
                    },
                    {
                        index: 1,
                        label: 'Step 2',
                    },
                    {
                        index: 2,
                        label: 'Step 3',
                    },
                    {
                        index: 3,
                        label: 'Step 4',
                    },
                    {
                        index: 4,
                        label: 'Train Event',
                    },
                ]}

                completed={completedStep}
                activeIndex={activeIndex}
            />
            {renderCurrentStep()}
        </Box>
    )
}

export default UserTrainEvent





