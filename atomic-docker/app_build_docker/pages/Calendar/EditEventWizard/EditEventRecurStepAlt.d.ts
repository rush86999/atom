import { Dispatch, SetStateAction } from 'react';
import { RecurrenceFrequencyType } from '@lib/Assist/types';
import { NextApiRequest, NextApiResponse } from 'next';
import { Day } from '@lib/Schedule/constants';
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
    setParentByWeekDay: Dispatch<SetStateAction<Day[]>>;
};
declare function EditEventRecurStepAlt(props: Props): JSX.Element;
export default EditEventRecurStepAlt;
/** end */
