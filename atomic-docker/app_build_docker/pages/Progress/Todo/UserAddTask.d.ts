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
export type TaskNameType = 'Daily' | 'Weekly' | 'Master' | 'Grocery';
export type DeadlineType = 'soft' | 'hard';
type Props = {
    sub: string;
};
declare function UserAddTask(props: Props): JSX.Element | undefined;
export default UserAddTask;
