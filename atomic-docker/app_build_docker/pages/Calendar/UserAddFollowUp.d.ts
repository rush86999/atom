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
    id: string;
    closeAddFollowUp: () => void;
    client: ApolloClient<NormalizedCacheObject>;
    sub: string;
};
declare function UserAddFollowUp(props: Props): JSX.Element;
export default UserAddFollowUp;
