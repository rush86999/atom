import { Dispatch, SetStateAction } from 'react';
import { VisibilityType } from '@lib/calendarLib/types';
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
    setParentVisibility: Dispatch<SetStateAction<VisibilityType>>;
    userId: string;
    visibility: VisibilityType;
    alarms: number[];
    setParentAlarms: Dispatch<SetStateAction<number[]>>;
};
declare function CreateEventVisibilityAndAlarmsStep(props: Props): JSX.Element;
export default CreateEventVisibilityAndAlarmsStep;
/** end */
