import { TaskType } from '@lib/dataTypes/TaskType';
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
export type DeadlineType = 'soft' | 'hard';
export type TaskPlusType = TaskType & {
    startDate?: string;
    endDate?: string;
    nextDay?: boolean;
};
export type TaskSubType = 'Daily' | 'Weekly' | 'Master' | 'Grocery' | string;
export type DisplayUIType = TaskPlusType;
declare function UserTask(): JSX.Element;
export default UserTask;
