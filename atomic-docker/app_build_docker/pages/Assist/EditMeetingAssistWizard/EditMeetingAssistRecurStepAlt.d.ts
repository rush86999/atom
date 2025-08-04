import { Dispatch, SetStateAction } from 'react';
import { RecurrenceFrequencyType } from '@lib/Calendar/types';
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
    frequency: RecurrenceFrequencyType;
    interval: number;
    until: Date;
    setParentFrequency: Dispatch<SetStateAction<RecurrenceFrequencyType>>;
    setParentInterval: Dispatch<SetStateAction<number>>;
    setParentUntil: Dispatch<SetStateAction<Date>>;
};
declare function EditMeetingAssistRecurStepAlt(props: Props): JSX.Element;
export default EditMeetingAssistRecurStepAlt;
