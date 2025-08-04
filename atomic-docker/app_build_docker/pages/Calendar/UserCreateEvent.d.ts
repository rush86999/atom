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
    start: Date;
    end: Date;
    closeCreateEvent: () => void;
    client: ApolloClient<NormalizedCacheObject>;
    sub: string;
};
declare function UserCreateEvent(props: Props): JSX.Element;
export default UserCreateEvent;
