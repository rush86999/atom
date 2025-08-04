import { Dispatch, SetStateAction } from 'react';
import { ConferenceAppType } from '@lib/dataTypes/MeetingAssistType';
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
    isZoomAvailable: boolean;
    isGoogleMeetAvailable: boolean;
    zoomMeet: boolean;
    googleMeet: boolean;
    enableConference: boolean;
    setParentZoomMeet: Dispatch<SetStateAction<boolean>>;
    setParentGoogleMeet: Dispatch<SetStateAction<boolean>>;
    setParentEnableConference: Dispatch<SetStateAction<boolean>>;
    setParentConferenceApp: Dispatch<SetStateAction<ConferenceAppType | null>>;
};
declare function EditMeetingAssistVirtualMeet(props: Props): JSX.Element;
export default EditMeetingAssistVirtualMeet;
