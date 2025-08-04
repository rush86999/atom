import { NextApiRequest, NextApiResponse } from 'next';
export declare function getServerSideProps({ req, res }: {
    req: NextApiRequest;
    res: NextApiResponse;
}): Promise<{
    props: {
        fromSupertokens: string;
        userId?: undefined;
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
        userId: any;
        fromSupertokens?: undefined;
    };
    redirect?: undefined;
}>;
declare const UserGmailSearchPage: () => JSX.Element;
export default UserGmailSearchPage;
