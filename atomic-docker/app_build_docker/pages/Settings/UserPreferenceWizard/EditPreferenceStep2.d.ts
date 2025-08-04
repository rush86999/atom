import { Dispatch, SetStateAction } from 'react';
import { EndTimeType, StartTimeType } from '@lib/dataTypes/User_PreferenceType';
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
    startTimes: StartTimeType[];
    setParentStartTimes: Dispatch<SetStateAction<StartTimeType[]>>;
    endTimes: EndTimeType[];
    setParentEndTimes: Dispatch<SetStateAction<EndTimeType[]>>;
};
declare function EditPreferenceStep2(props: Props): JSX.Element;
export default EditPreferenceStep2;
