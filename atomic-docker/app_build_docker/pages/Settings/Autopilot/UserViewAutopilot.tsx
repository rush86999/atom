import React, {
    useState,
    useEffect,
} from 'react'

import { Tooltip } from '@chakra-ui/react'
import Switch1 from '@components/Switch'

import Box from '@components/common/Box'
import Text from '@components/common/Text'

import { palette } from '@lib/theme/theme'

import { dayjs } from '@lib/date-utils'
import { deleteAutopilotsGivenUserId, deleteScheduledEvent, listAutopilotsByUserId, triggerAddDailyFeaturesApplyUrl } from '@lib/Settings/Autopilot/AutopilotHelper'
import { AutopilotType, ScheduleAssistWithMeetingQueueBodyType } from '@lib/dataTypes/AutopilotType'
import { v4 as uuid } from 'uuid'
import { useToast } from '@chakra-ui/react'


import { Overlay } from '@rneui/themed'
import Button from '@components/Button'
import { useAppContext } from '@lib/user-context'
import { useRouter } from 'next/router'

import { NextApiRequest, NextApiResponse } from 'next';
import supertokensNode from 'supertokens-node'
import { backendConfig } from '@config/backendConfig'
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

function UserViewAutopilot() {
    const [isAutopilot, setIsAutopilot] = useState<boolean>(false)
    const [isConfirmAutopilot, setIsConfirmAutopilot] = useState<boolean>(false)
    const [isCancelAutopilot, setIsCancelAutopilot] = useState<boolean>(false)

    const { sub, client } = useAppContext()
    const userId = sub
    const toast = useToast()

    console.log(userId, ' userId')

    useEffect(() => {
        (async () => {
            try {
                const autopilots = await listAutopilotsByUserId(client, userId)
                if (autopilots?.length > 0) {
                    setIsAutopilot(true)
                    // setEventIds(autopilots?.map(a => a?.id))
                }
            } catch (e) {
                console.log(e, ' unable to get autopilot values')
            }
        })()
    }, [client, userId])

    const activateAutopilot = async () => {
        try {
            // prod
            const startDate = dayjs().add(1, 'd').format()
            
            // dev
            // const startDate = dayjs().format()

            const scheduleAt = dayjs(startDate).format()
            const timezone = dayjs.tz.guess()

            const bodyFeaturesApply: ScheduleAssistWithMeetingQueueBodyType = {
                userId,
                windowStartDate: startDate,
                windowEndDate: dayjs(startDate).add(6, 'd').format(),
                timezone,
            }

            const autopilotFeaturesApply: AutopilotType = {
                id: uuid(),
                userId,
                scheduleAt,
                timezone,
                payload: bodyFeaturesApply,
                updatedAt: dayjs().format(),
                createdDate: dayjs().format(),
            }

            await triggerAddDailyFeaturesApplyUrl(
                autopilotFeaturesApply,
                bodyFeaturesApply,
            )

        } catch (e) {
            console.log(e, ' unable to activate autopilot')
        }
    }

    const deactivateAutopilot = async () => {
        try {
            const autopilots = await listAutopilotsByUserId(client, userId)
            
            console.log(autopilots, ' autopilots')
            
            for (const autopilot of autopilots) {
                await deleteScheduledEvent(autopilot?.id)
            }

            await deleteAutopilotsGivenUserId(client, userId)


        } catch (e) {
            console.log(e, ' unable to deactivate autopilot')
        }
    }

    const showConfirm = () => setIsConfirmAutopilot(true)

    const hideConfirm = () => {
        setIsConfirmAutopilot(false)
        
    }

    const showCancel = () => setIsCancelAutopilot(true)

    function hideCancel() {
        setIsCancelAutopilot(false)

    }

    const enableAutopilot = async () => {
        try {
            await activateAutopilot()

            hideConfirm()

            toast({
                status: 'success',
                title: 'Activated Autopilot',
                description: 'You have successfully activated autopilot. It will start running tomorrow in AM.',
                duration: 9000,
                isClosable: true,
            })

        } catch (e) {
            console.log(e, ' unable to enable autopilot')
            hideConfirm()
            setIsAutopilot(false)
            toast({
                status: 'error',
                title: 'Oops...',
                description: 'Something went wrong. Please let us know so we can look under the hood.',
                duration: 9000,
                isClosable: true,
            })
        }
    }

    const disableAutopilot = async () => {
        try {
            await deactivateAutopilot()

            hideCancel()

            setIsAutopilot(false)

            toast({
                status: 'info',
                title: 'Deactivated Autopilot',
                description: 'You have deactivated Autopilot. Your calendar will no longer be managed automagically',
                duration: 9000,
                isClosable: true,
            })
        } catch (e) {
            console.log(e, ' unable to disable autopilot')
            hideCancel()
            toast({
                status: 'error',
                title: 'Oops...',
                description: 'Something went wrong. Please let us know so we can look under the hood.',
                duration: 9000,
                isClosable: true,
            })
        }
    }

    const onChangeAutopilot = (value: boolean) => {
        if (value) {
            setIsAutopilot(value)
            showConfirm()  
        } else {
            setIsAutopilot(value)
            showCancel()
        }
    }

    return (
        <Box flex={1} justifyContent="flex-start" alignItems="center"  style={{ width: '100%'}}>
            <Box p="m" mt="l" mb="m" borderRadius="md" backgroundColor="infoBlockBackground" width={{ phone: '90%', tablet: '80%'}} alignItems="center">
                <Text variant="body" textAlign="center" color="infoBlockText">
                    Enable Autopilot to have Atomic automatically plan and optimize your schedule daily. It can apply your trained event templates and smart tags to new and existing events, helping to keep your calendar organized according to your preferences.
                    <Text variant="link" onPress={() => router.push('https://docs.atomiclife.app/docs/features/autopilot')}>
                        {' '}Discover Autopilot strategies
                    </Text>
                </Text>
            </Box>
            <Box flex={1} justifyContent="center" alignItems="center"  style={{ width: '100%'}} minHeight="60vh"> {/* Adjusted minHeight */}
                <Box pt={{ phone: 'm', tablet: 's' }} flexDirection="row" justifyContent="space-between">
                    <Tooltip hasArrow label='Autopilot will apply features & run planner once every day before work start time' bg='purple.700' color='white'>
                        <Box flexDirection="row" justifyContent="flex-start">
                        {
                            isAutopilot
                            ? (
                                <Text variant="buttonLink" pr={{ phone: 's', tablet: 'm' }}>
                                    Autopilot Active
                                </Text>
                            ) : (
                                <Text variant="buttonLink" pr={{ phone: 's', tablet: 'm' }}>
                                    Autopilot Inactive
                                </Text>
                            )
                        }
                        </Box>
                    </Tooltip>
                    <Box flexDirection="row" justifyContent="flex-end" pl={{ phone: 's', tablet: 'm' }}>
                    <Switch1
                        checked={isAutopilot}
                        onValueChange={onChangeAutopilot}
                        style={{marginBottom: 20}}
                    />
                    </Box>
                </Box>
            </Box>
            <Box>
                <Overlay overlayStyle={{ backgroundColor: palette.white, justifyContent: 'center', alignItems: 'center' }} isVisible={isConfirmAutopilot} onBackdropPress={hideConfirm}>
                    <Box justifyContent="center" alignItems="center" style={{ width: '80%', backgroundColor: palette.white}}>
                        <Box pt={{ phone: 'm', tablet: 's' }} justifyContent="center" alignItems="center">
                            <Text variant="optionHeader">
                                Do you want to activate Autopilot?
                            </Text>
                        </Box>
                        <Box justifyContent="center" alignItems="center">
                            <Box pt={{ phone: 'm', tablet: 's' }} justifyContent="center" alignItems="center">
                                <Button onClick={enableAutopilot}>
                                    Okay
                                </Button>  
                            </Box>
                            <Button cancel onClick={hideConfirm}>
                                Cancel
                            </Button>  
                        </Box>
                    </Box>
                </Overlay>
                <Overlay overlayStyle={{ backgroundColor: palette.white, justifyContent: 'center', alignItems: 'center' }} isVisible={isCancelAutopilot} onBackdropPress={hideCancel}>
                    <Box justifyContent="center" alignItems="center" style={{ width: '80%', backgroundColor: palette.white}}>
                        <Box pt={{ phone: 'm', tablet: 's' }} justifyContent="center" alignItems="center">
                            <Text variant="optionHeader">
                                Do you want to disable Autopilot?
                            </Text>
                        </Box>
                        <Box justifyContent="center" alignItems="center">
                            <Box pt={{ phone: 'm', tablet: 's' }} justifyContent="center" alignItems="center">
                                <Button onClick={disableAutopilot}>
                                    Okay
                                </Button>  
                            </Box>
                            <Button disabled onClick={hideCancel}>
                                Cancel
                            </Button>  
                        </Box>
                    </Box>
                </Overlay>
            </Box>
        </Box>
    )

}

export default UserViewAutopilot
