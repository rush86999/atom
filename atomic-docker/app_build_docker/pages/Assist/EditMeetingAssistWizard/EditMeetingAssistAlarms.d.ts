import { Dispatch, SetStateAction } from 'react';
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
    useDefaultAlarms: boolean;
    alarms: number[];
    setParentAlarms: Dispatch<SetStateAction<number[]>>;
    setParentUseDefaultAlarms: Dispatch<SetStateAction<boolean>>;
};
declare function EditMeetingAssistAlarms(props: Props): JSX.Element;
export default EditMeetingAssistAlarms;
