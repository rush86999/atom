import { Dispatch } from 'react';
import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import { NextApiRequest, NextApiResponse } from 'next';
export declare function getServerSideProps({ req, res }: {
    req: NextApiRequest;
    res: NextApiResponse;
}): Promise<{
    props: {
        fromSupertokens: string;
        sub?: undefined;
    };
    redirect?: undefined;
} | {
    redirect: {
        destination: string;
        permanent: boolean;
    };
    props?: undefined;
} | {
    props: {
        sub: any;
        fromSupertokens?: undefined;
    };
    redirect?: undefined;
}>;
type Props = {
    selectedCalendarId: string;
    setParentSelectedCalendarId: Dispatch<string>;
    userId: string;
    client: ApolloClient<NormalizedCacheObject>;
};
declare function UserSelectPrimaryCalendar(props: Props): JSX.Element;
export default UserSelectPrimaryCalendar;
