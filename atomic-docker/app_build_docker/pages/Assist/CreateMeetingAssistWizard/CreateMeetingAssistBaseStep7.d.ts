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
    anyoneCanAddSelf: boolean;
    guestsCanSeeOtherGuests: boolean;
    minThresholdCount: number;
    guaranteeAvailability: boolean;
    isRecurring: boolean;
    lockAfter: boolean;
    setParentAnyoneCanAddSelf: Dispatch<SetStateAction<boolean>>;
    setParentGuestsCanSeeOtherGuests: Dispatch<SetStateAction<boolean>>;
    setParentMinThresholdCount: Dispatch<SetStateAction<number>>;
    setParentGuaranteeAvailability: Dispatch<SetStateAction<boolean>>;
    setParentIsRecurring: Dispatch<SetStateAction<boolean>>;
    setParentLockAfter: Dispatch<SetStateAction<boolean>>;
};
declare function CreateMeetingAssistBaseStep7(props: Props): JSX.Element;
export default CreateMeetingAssistBaseStep7;
