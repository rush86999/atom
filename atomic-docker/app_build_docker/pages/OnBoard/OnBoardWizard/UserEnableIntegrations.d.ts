import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
type Props = {
    sub: string;
    client: ApolloClient<NormalizedCacheObject>;
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
declare function UserEnableIntegrations(props: Props): JSX.Element;
export default UserEnableIntegrations;
