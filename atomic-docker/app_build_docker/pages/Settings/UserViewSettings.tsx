import React from 'react'
import Box from '@components/common/Box'
import Text from '@components/common/Text'
import { useRouter } from 'next/router'
import { ScrollView } from 'react-native'
import { NextApiRequest, NextApiResponse } from 'next';
import supertokensNode from 'supertokens-node'
import { backendConfig } from '@config/backendConfig'
import Session from 'supertokens-node/recipe/session'
import AtomAgentSettings from '@components/Settings/AtomAgentSettings'; // Import the new component

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

function UserViewSettings() {
  const router = useRouter()

  const navigateToChangePass = () => router.push({ pathname: '/User/Login/UserChangePassword' })

  const navigateToCalendarIntegrations = () => router.push({ pathname: '/Settings/UserViewCalendarAndContactIntegrations' })

  const navigateToPrimaryCalendar = () => router.push({ pathname: '/Settings/UserSelectPrimaryCalendarForSettings' })

  const navigateToCategories = () => router.push({ pathname: '/Settings/UserEditCategories' })

  const navigateToCalendarPreferences = () => router.push({ pathname: '/Settings/UserCalendarPreferences'})

  const navigateToUserDeleteAccount = () => router.push({ pathname: '/User/Delete/UserDeleteAccount'})

  const navigateToListUserContactInfo = () => router.push({ pathname: '/Contact/ListUserContactInfo'})

  const navigateToUserViewAutopilot = () => router.push({ pathname: '/Settings/Autopilot/UserViewAutopilot'})

  const navigateToUserChatMeetingPreferences = () => router.push({ pathname: '/Settings/UserChatMeetingPreferences'})

  return (
    <ScrollView style={{ flex: 1, width: '100%', minHeight: '65vh', maxHeight: '65vh' }} contentContainerStyle={{ alignItems: 'center'}}>
      <Box flex={1} justifyContent="center" alignItems="center" minHeight="70vh">
        <div className="pt-3">
          <Text variant="buttonLink" onPress={navigateToListUserContactInfo}>
            Your Contact Info
          </Text>
        </div>
        <div className="pt-3">
          <Text variant="buttonLink" onPress={navigateToUserViewAutopilot}>
            Autopilot
          </Text>
        </div>
        <div className="pt-3">
          <Text variant="buttonLink" onPress={navigateToChangePass}>
            Change Password
          </Text>
        </div>
        <div className="pt-3">
          <Text variant="buttonLink" onPress={navigateToCalendarIntegrations}>
            Calendar & Contact Integrations
          </Text>
        </div>
        <div className="pt-3">
          <Text variant="buttonLink" onPress={navigateToPrimaryCalendar}>
            Select Primary Calendar
          </Text>
        </div>
        <div className="pt-3">
          <Text variant="buttonLink" onPress={navigateToCalendarPreferences}>
            Calendar Preferences
          </Text>
        </div>
        <div className="pt-3">
          <Text variant="buttonLink" onPress={navigateToCategories}>
            Edit Tags
          </Text>
        </div>
        <div className="pt-3">
          <Text variant="buttonLink" onPress={navigateToUserChatMeetingPreferences}>
            Meeting Preferences via Chat
          </Text>
        </div>
        <div className="pt-3">
          <Text variant="redLink" onPress={navigateToUserDeleteAccount}>
            Delete Account
          </Text>
        </div>

        {/* Atom Agent Settings Section */}
        <Box width="100%" alignItems="center" mt="l"> {/* Ensure it takes appropriate width and has some margin */}
          <AtomAgentSettings />
        </Box>
        
        {/* Cloud Settings Section */}
        {typeof window !== 'undefined' && !window.__TAURI__ && (
          <Box width="100%" alignItems="center" mt="l">
            <Text variant="sectionHeader">Cloud Settings</Text>
            <Box mt="s">
              <Text variant="buttonLink">
                Cloud Version Available
              </Text>
            </Box>
          </Box>
        )}
      </Box>
    </ScrollView>
  )

}

export default UserViewSettings
