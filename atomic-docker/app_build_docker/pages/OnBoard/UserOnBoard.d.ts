import { NextApiRequest, NextApiResponse } from 'next';
export declare function getServerSideProps({ req, res }: {
    req: NextApiRequest;
    res: NextApiResponse;
}): Promise<{
    props: {
        fromSupertokens: string;
        sub?: undefined;
        email?: undefined;
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
        email: string | undefined;
        fromSupertokens?: undefined;
    };
    redirect?: undefined;
}>;
type Props = {
    sub: string;
    email: string;
};
declare function UserOnBoard(props: Props): JSX.Element;
export default UserOnBoard;
