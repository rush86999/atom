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
    cancelIfAnyRefuse: boolean;
    enableAttendeePreferences: boolean;
    attendeeCanModify: boolean;
    expireDate: Date;
    duration: number;
    setParentCancelIfAnyRefuse: Dispatch<SetStateAction<boolean>>;
    setParentEnableAttendeePreferences: Dispatch<SetStateAction<boolean>>;
    setParentAttendeeCanModify: Dispatch<SetStateAction<boolean>>;
    setParentExpireDate: Dispatch<SetStateAction<Date>>;
    setParentDuration: Dispatch<SetStateAction<number>>;
};
declare function CreateMeetingAssistBaseStep5(props: Props): JSX.Element;
export default CreateMeetingAssistBaseStep5;
