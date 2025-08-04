import { Dispatch, SetStateAction } from 'react';
import { Person } from '@lib/Calendar/types';
import { ContactType } from '@lib/dataTypes/ContactType';
import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
export type SelectedContactType = ContactType & {
    selected: boolean;
};
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
    attendees: Person[];
    setParentAttendees: Dispatch<SetStateAction<Person[]>>;
    userId: string;
    client: ApolloClient<NormalizedCacheObject>;
};
declare function CreateEventAttendees(props: Props): JSX.Element;
export default CreateEventAttendees;
/** end */
