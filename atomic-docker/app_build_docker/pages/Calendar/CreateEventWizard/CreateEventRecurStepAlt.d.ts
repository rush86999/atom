import { Dispatch, SetStateAction } from 'react';
import { RecurrenceFrequencyType } from '../../../lib/Calendar/types';
import { Day } from '@lib/Schedule/constants';
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
    recurringEndDate: Date;
    setParentRecurringEndDate: Dispatch<SetStateAction<Date>>;
    frequency: RecurrenceFrequencyType;
    setParentFrequency: Dispatch<SetStateAction<RecurrenceFrequencyType>>;
    interval: string;
    setParentInterval: Dispatch<SetStateAction<string>>;
    byWeekDay: Day[];
    setParentWeekDay: Dispatch<SetStateAction<Day[]>>;
};
declare function CreateEventRecurStepAlt(props: Props): JSX.Element;
export default CreateEventRecurStepAlt;
