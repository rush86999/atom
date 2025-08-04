import { EventType } from '@lib/dataTypes/EventType';
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
    event: EventType;
    hidePrepAndReview: () => void;
    client: ApolloClient<NormalizedCacheObject>;
};
declare function UserPreAndPostForEventModal(props: Props): JSX.Element;
export default UserPreAndPostForEventModal;
