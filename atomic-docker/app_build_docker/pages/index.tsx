
import config from "@config/config.json";
import Base from "@layouts/Baseof";

import { Tab, TabList, TabPanel, TabPanels, Tabs } from '@chakra-ui/react';
import UserViewCalendar from '@pages/Calendar/UserViewCalendarWeb'
import UserTask from '@pages/Progress/Todo/UserTask'
import UserViewChat from '@pages/Calendar/Chat/UserViewChat'
import SmartSearch from '@components/SmartSearch';
import Dashboard from '@components/Dashboard';
import { NextApiRequest, NextApiResponse } from 'next';
import supertokensNode from 'supertokens-node'
import { backendConfig } from '../config/backendConfig'
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


const Home = () => {

  const { title } = config.site;
  
  return (
    <Base title={title} meta_title={undefined} description={undefined} image={undefined} noindex={undefined} canonical={undefined}>
      <Dashboard />
    </Base>
  )
}

export default Home
